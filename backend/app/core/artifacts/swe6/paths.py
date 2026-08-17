"""Where things get written. The one rule that matters: `output_dir` may only
ever contain the final .xlsx, because swe6.py's fixed zip step zips *every*
non-.zip file sitting in output_dir. Everything else (enriched-requirement
JSON, raw LLM traces, validation logs) goes under this package's own `_runs/`
directory instead.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

SWE6_PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_RUNS_DIR = SWE6_PACKAGE_DIR / "_runs"


def resolve_intermediate_dir(project_name: str, configured: Path | None) -> Path:
    run_dir = configured if configured is not None else _default_run_dir(project_name)
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _default_run_dir(project_name: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_name)
    return DEFAULT_RUNS_DIR / f"{safe_name}_{timestamp}"


def ensure_output_dir(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir
