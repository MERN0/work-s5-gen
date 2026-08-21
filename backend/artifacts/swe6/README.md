# swe6 — SWE6 Software Qualification Test Case generator

Generates a SWE6 (Software Qualification Test Cases) Excel workbook from a
SWE.1 (Software Requirements) workbook plus project-specific supporting docs
(function/API lists, interface specs, error/return-code tables, calibration
parameters, test patterns). Entry point: `swe6.generate(config: dict) -> str`
(returns a zip path). See `runner.py` for the two blocks marked "do not
change" — they're the fixed contract with the caller and must stay exactly
as given.

This package is a sibling of `../sys5/`, built the same way on purpose —
see [**"How this differs from sys5"**](#how-this-differs-from-sys5) below
before assuming the two are interchangeable.

## Pipeline, in one picture

```
START -> load_and_prepare -> [queue empty?] -> build_outputs -> END
                           -> generate_test_case -> validate_test_case
                                |-> passed               -> finalize_item -> [queue empty?] -> generate_test_case / build_outputs
                                |-> failed, budget left   -> correct_test_case -> validate_test_case
                                |-> failed, budget spent  -> finalize_item (flagged)
```

One LangGraph state machine (`graph/build.py`), no checkpointer — this is a
synchronous, one-shot batch job. `graph/nodes.py` has the six node functions;
`graph/routing.py` has the three routing functions that turn the "process one
queue item" cycle into a loop.

## Where to look for what

| Concern | Module |
|---|---|
| Config parsing/defaults | `config.py` |
| Data models | `models/` |
| Reading the requirements sheet (irregular headers, keyword scan) | `excel/requirements_loader.py` |
| Reading supporting docs (functions/APIs/interfaces/error codes/...) | `excel/supporting_docs_loader.py` |
| Attaching relevant context to a requirement | `matching/fuzzy_context.py` |
| Agent prompts (one file per agent) | `prompts/` |
| Automotive-domain prompt add-ons (bcm/adas/telematics/range_polygon/chassis/powertrain) | `prompts/domains.py` |
| LLM client + retry | `llm/client.py` |
| The graph itself | `graph/` |
| Deterministic test-case checks | `validation/rules.py` |
| Numbered Test Steps / Expected Results rendering | `validation/numbering.py` |
| Output workbook shape for a project | `formats/` |
| Writing the actual .xlsx | `output/` |

## The trickiest rule: continuous step numbering

The LLM never writes the final numbered `Test Steps` / `Expected Results`
strings — it emits typed `TestStep` objects (`models/test_case.py`), and
`validation/numbering.py::render()` is the *only* place that turns them into
the numbered text (`1. Test_start`, ..., `<n>. End_of_test`). Both the
validator and the workbook writer call this same function, so the two output
columns can never desync.

## Automotive-domain prompts

`Swe6Config.domain` (from the config's `domain` key, set by the caller at
the start of a run) picks a domain-specific prompt add-on from
`prompts/domains.py` — currently `bcm`, `adas`, `telematics`,
`range_polygon`, `chassis`, `powertrain` (plus a few free-text spelling
aliases; see `_DOMAIN_ALIASES` in that file). `prompts/registry.py::
resolve_system_prompt()` is the single choke point every agent call goes through
(planning, generation, verification, qa), so the matching domain block is
appended there — to whichever prompt is in play, our default or an
`agent_chain` override alike. An unrecognized or blank `domain` is a silent
no-op. The add-ons are deliberately just contextual grounding (what the
software typically does, what its tests typically hinge on) and never
contain actual function/API/error-code names, consistent with the "no
hallucinated signal" rule the base prompts already enforce — real names
still only ever come from the project's own supporting-doc context.

## What never lands in `output_dir`

Only the final `swe6_<sheet>_<timestamp>.xlsx` may exist in `output_dir`,
because `runner.py`'s fixed "Step 2" block zips *everything* it finds there.
All intermediate artifacts go to this package's own
`_runs/<project>_<timestamp>/` directory instead — see `paths.py`:

- `enriched_requirements.json` — every processed requirement plus its
  attached supporting-doc context, machine-readable.
- `requirements_context.log` — the same information, human-readable: one
  block per requirement with its text and exactly which supporting-doc rows
  were attached to it and why (match score).
- `run_log.jsonl` / `run_summary.json` — per-test-case outcomes and final
  totals/errors.

## Logs

Every module logs via `logging.getLogger(__name__)` and never configures
logging itself — a host app's own logging config decides where these end
up. Key things to expect at INFO level: which sheet(s)/files were scanned
and how many rows matched, which requirement is being processed and what
got fuzzy-matched to it, every agent call (which agent, which
requirement/aspect) and its pass/fail outcome, and retries on transient LLM
errors. Run standalone (see below) to see it all on the console via
`logging_config.configure_logging()`.

## Running standalone without an LLM

`tests/test_swe6_fixed_blocks.py` exercises `runner.run()` end to end
against a small synthetic requirements file with the LLM client and
`call_structured` stubbed out — no `OPENAI_API_KEY`, network access, or real
project input needed. Useful for checking the wiring (config parsing,
keyword scan, fuzzy matching, graph routing, workbook + intermediate-file
writing) after a change, not for judging output quality.

For a real run, copy `.env.example` to `.env` and fill in `OPENAI_API_KEY`
(and `SWE6_LLM_API_BASE` if your gateway differs from the default) — it's
loaded automatically via `python-dotenv`.

## Known scope boundaries (said out loud on purpose)

- The "no hallucinated signal" guarantee is defense-in-depth (prompt
  instruction + a programmatic token whitelist + an LLM semantic check), not
  a mathematical proof — string matching has irreducible edge cases.
- Only the `"default"` format profile exists (`formats/default_profile.py`).
  A second project with different output columns/headings is a new
  `formats/<name>_profile.py` + one line in `formats/registry.py` — nothing
  else changes.
- `llm/client.py`'s env var names (`OPENAI_API_KEY`, `SWE6_LLM_API_BASE`) are
  placeholders for the on-prem gateway - rename in one place if the real
  deployment differs.

## Running tests

```bash
pip install -r ../../../../requirements.txt   # from this directory, or use the backend/requirements.txt path directly
pytest backend/app/core/artifacts/swe6/tests
```

Most tests need no API key or real files (synthetic `openpyxl.Workbook()`
fixtures, mocked LLM calls). A real end-to-end run needs `OPENAI_API_KEY` set
and a sample SWE.1 workbook + supporting docs dropped into an input folder.

## How this differs from sys5

`swe6/` started as a deliberate, near-total copy of `sys5/` — same six-node
LangGraph pipeline, same fuzzy-matching/validation/workbook-building
machinery, same file layout, same test structure. The two are intentionally
allowed to duplicate code; nothing here is imported from `sys5/` or vice
versa. What was actually changed, file by file:

| Area | sys5 | swe6 |
|---|---|---|
| Input artifact | SYS2 (System Requirements) | SWE.1 (Software Requirements) |
| Output artifact | SYS5 (System Qualification Test Cases) | SWE6 (Software Qualification Test Cases) |
| Config class | `Sys5Config` | `Swe6Config` |
| Keyword list (`config.py`) | `DEFAULT_SYS5_KEYWORDS`: `"sys5 test"`, `"sys qt"`, `"system qualification test"`, ... | `DEFAULT_SWE6_KEYWORDS`: `"swe6 test"`, `"sw qt"`, `"software qualification test"`, ... — deliberately non-overlapping, so a SYS2 and a SWE.1 sheet for the same project don't cross-match each other's rows |
| Test case ID pattern | `{project_code}_SQMTC_{n:03d}` | `{project_code}_SWQTC_{n:03d}` |
| Output filename prefix | `sys5_<sheet>_<timestamp>.xlsx` / `.zip` | `swe6_<sheet>_<timestamp>.xlsx` / `.zip` |
| LLM API base env var | `SYS5_LLM_API_BASE` | `SWE6_LLM_API_BASE` (separate variable — same `OPENAI_API_KEY`, in case software-level generation should route to a different model/gateway than system-level) |
| Requirement text header hints | `"system requirement"`, ... | adds `"software requirement"` |
| Supporting-doc entity types (`excel/supporting_docs_loader.py`) | signal / command / comm_matrix / configurable_parameter / test_pattern / library | adds function / api / interface / error_code / return_code / calibration_parameter, on top of the same sys5 set (software still touches signals, so those stay too) |
| **Prompts (all four agents)** | Framed around signals/commands/vehicle behavior — "reference the signal/command name present in supporting context," system-level triggers | Reframed around functions/APIs/return values/error codes — "reference the function/parameter/return value present in supporting context." `planning_agent` specifically adds software-test-design guidance sys5 doesn't need: boundary/equivalence-class analysis, error/exception-path coverage, state-transition coverage |
| **Domain add-ons (`prompts/domains.py`)** | Same six domains (bcm/adas/telematics/range_polygon/chassis/powertrain), described at the vehicle/trigger level (e.g. "which CAN command triggers the behavior") | Same six domains, described at the software/interface level (e.g. "which function/API call triggers the behavior under test, and the return code it produces") |
| `req_id` traceability fix, structured logging, `.env.example`, offline dry run (`__main__` in `runner.py`) | Already present (added in an earlier pass) | Built in from the start, so swe6 launches at parity with sys5's current state rather than sys5's original bare-bones version |

Everything else — the graph shape, the fuzzy-matching tiers and thresholds,
the deterministic validation rules, the workbook's five sheets and column
layout, the `_runs/` intermediate-artifact files, the ODC trigger taxonomy —
is unchanged, because none of it is actually specific to system vs. software
level; it's the pipeline mechanics both artifact types share.
