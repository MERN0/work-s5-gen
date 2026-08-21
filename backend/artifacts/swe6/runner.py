"""SWE6 (Software Qualification Test Cases) generator - the process area's
entry point. Reads SWE.1 software requirements plus project-specific
supporting docs (function/API lists, interface specs, error/return-code
tables, calibration parameters, test patterns) from request.input_folder_path,
and generates a formatted SWE6 test case workbook via a LangGraph pipeline
(per-requirement planning, generation, validation, and correction) built
from request.agent_chain (see graph/build.py).
"""
from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from artifacts.common.paths import output_dir
from artifacts.common.schema import GenerationRequest, GenerationResult
from artifacts.swe6.config import Swe6Config
from artifacts.swe6.exceptions import Swe6Error
from artifacts.swe6.pipeline import run_pipeline

logger = logging.getLogger(__name__)


def run(request: GenerationRequest) -> GenerationResult:
    return generate_swe6(request)


def generate_swe6(request: GenerationRequest) -> GenerationResult:
    # A caller-supplied output_folder_path wins (matches Swe6Config.from_raw's
    # own precedence); otherwise fall back to the standard per-run layout -
    # either way, this is the one directory both the pipeline writes into and
    # the zip step below packages up.
    out_dir = (
        Path(request.output_folder_path)
        if request.output_folder_path
        else output_dir(request.username, request.project_name, request.version, request.process_area or "swe6")
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "[swe6] run() called: project=%s, username=%s, version=%s, language=%s, domain=%s, "
        "input_format=%s, output_format=%s, model=%s",
        request.project_name, request.username, request.version, request.language, request.domain,
        request.input_format, request.output_format, request.model,
    )
    if request.agent_chain:
        logger.info(
            "[swe6] Received agent_chain with %d agent(s): %s",
            len(request.agent_chain), [a.agent_name for a in request.agent_chain],
        )
    else:
        logger.info("[swe6] No agent_chain provided; every agent runs with its built-in default.")

    try:
        swe6_config = Swe6Config.from_raw(
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
        result = run_pipeline(swe6_config)
        logger.info(
            "[swe6] pipeline complete: %d test case(s) from %d requirement(s), xlsx=%s",
            result.total_test_cases, result.total_requirements, result.xlsx_path,
        )
        for error in result.errors:
            logger.warning("[swe6] %s", error)
    except Swe6Error:
        logger.exception("[swe6] pipeline failed")
        raise

    # Build the archive outside out_dir first - shutil.make_archive walks
    # root_dir as it writes, so building the .zip directly inside the
    # directory it's archiving would end up including itself.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_zip_str = shutil.make_archive(str(Path(tmp) / "SWE6_output"), "zip", root_dir=str(out_dir))
        zip_path = out_dir / Path(tmp_zip_str).name
        shutil.move(tmp_zip_str, zip_path)

    return GenerationResult(
        status="Completed",
        output_zip_filename=zip_path.name,
        message="SWE6 generation completed successfully.",
    )
