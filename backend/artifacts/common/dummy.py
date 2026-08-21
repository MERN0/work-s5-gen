"""dummy_generate(): the pass-through placeholder a process area's runner.py
returns from `run()` until a real implementation is written in its place -
kept here so a not-yet-implemented process area can still be wired up and
exercised end to end.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from artifacts.common.paths import output_dir
from artifacts.common.schema import GenerationRequest, GenerationResult


def dummy_generate(request: GenerationRequest, process_area_label: str) -> GenerationResult:
    out_dir = output_dir(request.username, request.project_name, request.version, request.process_area)

    dummy_file = out_dir / f"{process_area_label}_output.txt"
    lines = [
        f"{process_area_label} dummy generation output",
        f"Generated at: {datetime.utcnow().isoformat()}Z",
        f"Username: {request.username}",
        f"Domain: {request.domain}",
        f"Project: {request.project_name} (V{request.version})",
        f"Process area: {request.process_area}",
        f"Language: {request.language}",
        f"Input format: {request.input_format}",
        f"Output format: {request.output_format}",
        f"Model: {request.model}",
        f"Input files: {', '.join(request.input_filenames) if request.input_filenames else '(none)'}",
        "",
        "Agent chain executed (dummy pass-through):",
    ]
    for step in sorted(request.agent_chain, key=lambda a: a.index):
        lines.append(f"  [{step.index}] {step.agent_name} - {step.agent_description}")
        lines.append(f"        system_prompt: {step.system_prompt[:200]}")

    dummy_file.write_text("\n".join(lines), encoding="utf-8")

    # zip the entire output directory for this run.
    zip_base = out_dir / f"{process_area_label}_output"
    zip_path_str = shutil.make_archive(str(zip_base), "zip", root_dir=str(out_dir))
    zip_path = Path(zip_path_str)

    return GenerationResult(
        status="Completed",
        output_zip_filename=zip_path.name,
        message=f"{process_area_label} dummy generation completed successfully.",
    )
