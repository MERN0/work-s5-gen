# sys5 — SYS5 System Qualification Test Case generator

Generates a SYS5 (System Qualification Test Cases) Excel workbook from a SYS2
(System Requirements) workbook plus project-specific supporting docs
(signals, commands, communication matrix, configurable parameters, test
patterns). Entry point: `sys5.generate(config: dict) -> str` (returns a zip
path). See `sys5.py` for the two blocks marked "do not change" — they're the
fixed contract with the caller and must stay exactly as given.

New to this codebase? Read [`HANDOFF.md`](./HANDOFF.md) first — a stage-by-stage
walkthrough of what runs, why, and how a config dict becomes the final workbook.

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
| Reading supporting docs (signals/commands/comm matrix/...) | `excel/supporting_docs_loader.py` |
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

`Sys5Config.domain` (from the config's `domain` key, set by the caller at
the start of a run) picks a domain-specific prompt add-on from
`prompts/domains.py` — currently `bcm`, `adas`, `telematics`,
`range_polygon`, `chassis`, `powertrain` (plus a few free-text spelling
aliases; see `_DOMAIN_ALIASES` in that file). `prompts/registry.py::
resolve_prompt()` is the single choke point every agent call goes through
(planning, generation, verification, qa), so the matching domain block is
appended there — to whichever prompt is in play, our default or an
`agent_chain` override alike. An unrecognized or blank `domain` is a silent
no-op. The add-ons are deliberately just contextual grounding (what the
system typically does, what its tests typically hinge on) and never contain
actual signal/command names, consistent with the "no hallucinated signal"
rule the base prompts already enforce — real signal names still only ever
come from the project's own supporting-doc context.

## What never lands in `output_dir`

Only the final `sys5_<sheet>_<timestamp>.xlsx` may exist in `output_dir`,
because `sys5.py`'s fixed "Step 2" block zips *everything* it finds there.
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

`python -m app.core.artifacts.sys5.sys5` runs the whole `generate()` flow
against a small synthetic requirements file with the LLM client and
`call_structured` stubbed out — no `OPENAI_API_KEY`, network access, or real
project input needed. Useful for checking the wiring (config parsing,
keyword scan, fuzzy matching, graph routing, workbook + intermediate-file
writing) after a change, not for judging output quality.

For a real run, copy `.env.example` to `.env` and fill in `OPENAI_API_KEY`
(and `SYS5_LLM_API_BASE` if your gateway differs from the default) — it's
loaded automatically via `python-dotenv`.

## Known scope boundaries (said out loud on purpose)

- The "no hallucinated signal" guarantee is defense-in-depth (prompt
  instruction + a programmatic token whitelist + an LLM semantic check), not
  a mathematical proof — string matching has irreducible edge cases.
- Only the `"default"` format profile exists (`formats/default_profile.py`).
  A second project with different output columns/headings is a new
  `formats/<name>_profile.py` + one line in `formats/registry.py` — nothing
  else changes.
- `llm/client.py`'s env var names (`OPENAI_API_KEY`, `SYS5_LLM_API_BASE`) are
  placeholders for the on-prem gateway - rename in one place if the real
  deployment differs.

## Running tests

```bash
pip install -r ../../../../requirements.txt   # from this directory, or use the backend/requirements.txt path directly
pytest backend/app/core/artifacts/sys5/tests
```

Most tests need no API key or real files (synthetic `openpyxl.Workbook()`
fixtures, mocked LLM calls). A real end-to-end run needs `OPENAI_API_KEY` set
and a sample SYS2 workbook + supporting docs dropped into an input folder.
