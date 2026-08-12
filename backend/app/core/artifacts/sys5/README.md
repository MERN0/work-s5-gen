# sys5 — SYS5 System Qualification Test Case generator

Generates a SYS5 (System Qualification Test Cases) Excel workbook from a SYS2
(System Requirements) workbook plus project-specific supporting docs
(signals, commands, communication matrix, configurable parameters, test
patterns). Entry point: `sys5.generate(config: dict) -> str` (returns a zip
path). See `sys5.py` for the two blocks marked "do not change" — they're the
fixed contract with the caller and must stay exactly as given.

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

## What never lands in `output_dir`

Only the final `sys5_<sheet>_<timestamp>.xlsx` may exist in `output_dir`,
because `sys5.py`'s fixed "Step 2" block zips *everything* it finds there.
All intermediate JSON (enriched requirements, run log, run summary) goes to
this package's own `_runs/<project>_<timestamp>/` directory instead — see
`paths.py`.

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
