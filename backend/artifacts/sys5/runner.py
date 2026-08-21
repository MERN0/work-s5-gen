"""SYS5 (System Qualification Test Cases) generator - the process area's
entry point. Reads SYS2 system requirements plus project-specific supporting
docs (signals, commands, communication matrix, configurable parameters, test
patterns) from request.input_folder_path, and generates a formatted SYS5
test case workbook via a LangGraph pipeline (per-requirement planning,
generation, validation, and correction) built from request.agent_chain (see
graph/build.py).
"""
from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from artifacts.common.paths import output_dir
from artifacts.common.schema import GenerationRequest, GenerationResult
from artifacts.sys5.config import Sys5Config
from artifacts.sys5.exceptions import Sys5Error
from artifacts.sys5.pipeline import run_pipeline

logger = logging.getLogger(__name__)


def run(request: GenerationRequest) -> GenerationResult:
    return generate_sys5(request)


def generate_sys5(request: GenerationRequest) -> GenerationResult:
    # A caller-supplied output_folder_path wins (matches Sys5Config.from_raw's
    # own precedence); otherwise fall back to the standard per-run layout -
    # either way, this is the one directory both the pipeline writes into and
    # the zip step below packages up.
    out_dir = (
        Path(request.output_folder_path)
        if request.output_folder_path
        else output_dir(request.username, request.project_name, request.version, request.process_area or "sys5")
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "[sys5] run() called: project=%s, username=%s, version=%s, language=%s, domain=%s, "
        "input_format=%s, output_format=%s, model=%s",
        request.project_name, request.username, request.version, request.language, request.domain,
        request.input_format, request.output_format, request.model,
    )
    if request.agent_chain:
        logger.info(
            "[sys5] Received agent_chain with %d agent(s): %s",
            len(request.agent_chain), [a.agent_name for a in request.agent_chain],
        )
    else:
        logger.info("[sys5] No agent_chain provided; every agent runs with its built-in default.")

    try:
        sys5_config = Sys5Config.from_raw(
            {
                "project_name": request.project_name,
                "username": request.username,
                "version": request.version,
                "language": request.language,
                "domain": request.domain,
                "artifact": request.artifact,
                "input_format": request.input_format,
                "output_format": request.output_format,
                "model": request.model,
                "output_folder_path": str(out_dir),
                "input_folder_path": request.input_folder_path,
                "uploaded_files": request.input_filenames,
                "agent_chain": request.agent_chain,
                "req_filename": request.req_filename,
                "req_sheet_name": request.req_sheet_name,
            }
        )
        result = run_pipeline(sys5_config)
        logger.info(
            "[sys5] pipeline complete: %d test case(s) from %d requirement(s), xlsx=%s",
            result.total_test_cases, result.total_requirements, result.xlsx_path,
        )
        for error in result.errors:
            logger.warning("[sys5] %s", error)
    except Sys5Error:
        logger.exception("[sys5] pipeline failed")
        raise

    # Build the archive outside out_dir first - shutil.make_archive walks
    # root_dir as it writes, so building the .zip directly inside the
    # directory it's archiving would end up including itself.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_zip_str = shutil.make_archive(str(Path(tmp) / "SYS5_output"), "zip", root_dir=str(out_dir))
        zip_path = out_dir / Path(tmp_zip_str).name
        shutil.move(tmp_zip_str, zip_path)

    return GenerationResult(
        status="Completed",
        output_zip_filename=zip_path.name,
        message="SYS5 generation completed successfully.",
    )
