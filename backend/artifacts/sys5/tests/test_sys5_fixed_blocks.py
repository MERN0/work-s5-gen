"""Regression tests for runner.py's generate_sys5(): building Sys5Config from
a GenerationRequest, and zipping only the non-.zip file(s) sitting in the
run's output_dir. run_pipeline is monkeypatched out - these tests never touch
a real LLM or a real requirements file.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

import artifacts.sys5.runner as runner_module
from artifacts.common.schema import GenerationRequest
from artifacts.sys5.config import Sys5Config
from artifacts.sys5.exceptions import RequirementsFileError
from artifacts.sys5.pipeline import PipelineResult


def _request(output_dir: Path, input_dir: Path) -> GenerationRequest:
    return GenerationRequest(
        project_name="tmhc_demo",
        username="tester",
        version="V1.0",
        process_area="sys5",
        output_folder_path=str(output_dir),
        input_folder_path=str(input_dir),
        input_filenames=[],
        agent_chain=[],
        req_filename="reqs.xlsx",
        req_sheet_name="005",
    )


def test_run_extracts_fields_and_zips_only_non_zip_output_dir_files(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    input_dir = tmp_path / "in"
    output_dir.mkdir()
    input_dir.mkdir()

    captured = {}

    def fake_run_pipeline(config: Sys5Config) -> PipelineResult:
        captured["config"] = config
        xlsx_path = output_dir / "sys5_005_20260101_000000.xlsx"
        xlsx_path.write_text("fake workbook content")
        return PipelineResult(xlsx_path=str(xlsx_path), total_test_cases=1, total_requirements=1, errors=[])

    monkeypatch.setattr(runner_module, "run_pipeline", fake_run_pipeline)

    result = runner_module.run(_request(output_dir, input_dir))

    built_config = captured["config"]
    assert built_config.project_name == "tmhc_demo"
    assert built_config.req_sheet_name == "005"
    assert built_config.output_dir == output_dir

    assert result.status == "Completed"
    zip_path = output_dir / result.output_zip_filename
    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert "sys5_005_20260101_000000.xlsx" in names
    assert not any(name.endswith(".zip") for name in names)


def test_run_reraises_sys5_errors_without_producing_a_result(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    input_dir = tmp_path / "in"
    output_dir.mkdir()
    input_dir.mkdir()

    def failing_run_pipeline(config: Sys5Config):
        raise RequirementsFileError("missing file")

    monkeypatch.setattr(runner_module, "run_pipeline", failing_run_pipeline)

    with pytest.raises(RequirementsFileError):
        runner_module.run(_request(output_dir, input_dir))
