"""output_dir(): the one place a process area's per-run output folder gets
computed, so every runner.py (and the dummy pass-through) agree on the same
layout: <root>/<username>/<project_name>/<version>/<process_area>/.
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_OUTPUT_ROOT = Path(os.environ.get("ARTIFACTS_OUTPUT_ROOT", "_generated"))


def output_dir(username: str, project_name: str, version: str, process_area: str) -> Path:
    out_dir = DEFAULT_OUTPUT_ROOT / username / project_name / version / process_area
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
