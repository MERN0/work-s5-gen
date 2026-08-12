"""Regression tests for the two "do not change" blocks in sys5.py: the raw
config -> field extraction (now feeding Sys5Config.from_raw) and the
zip-only-non-zip-files-from-output_dir behavior. run_pipeline is monkeypatched
out - these tests never touch a real LLM or a real requirements file.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from app.core.artifacts.sys5 import sys5
from app.core.artifacts.sys5.config import Sys5Config
from app.core.artifacts.sys5.exceptions import RequirementsFileError
from app.core.artifacts.sys5.pipeline import PipelineResult


def _raw_config(output_dir: Path, input_dir: Path) -> dict:
    return {
        "project_name": "tmhc_demo",
        "username": "tester",
        "version": "V1.0",
        "output_folder_path": str(output_dir),
        "input_folder_path": str(input_dir),
        "uploaded_files": [],
        "agent_chain": [],
        "req_filename": "reqs.xlsx",
        "req_sheet_name": "005",
    }


def test_generate_extracts_fields_and_zips_only_non_zip_output_dir_files(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    input_dir = tmp_path / "in"
    input_dir.mkdir()

    captured = {}

    def fake_run_pipeline(config: Sys5Config) -> PipelineResult:
        captured["config"] = config
        xlsx_path = output_dir / "sys5_005_20260101_000000.xlsx"
        xlsx_path.write_text("fake workbook content")
        return PipelineResult(xlsx_path=str(xlsx_path), total_test_cases=1, total_requirements=1, errors=[])

    monkeypatch.setattr(sys5, "run_pipeline", fake_run_pipeline)

    zip_path = sys5.generate(_raw_config(output_dir, input_dir))

    # Top block: raw dict fields must have reached Sys5Config unchanged.
    built_config = captured["config"]
    assert built_config.project_name == "tmhc_demo"
    assert built_config.req_sheet_name == "005"
    assert built_config.output_dir == output_dir

    # Bottom block: only the non-.zip file(s) already sitting in output_dir get zipped.
    assert Path(zip_path).exists()
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    assert "sys5_005_20260101_000000.xlsx" in names
    assert not any(name.endswith(".zip") for name in names)


def test_generate_reraises_sys5_errors_without_producing_a_zip(tmp_path, monkeypatch):
    output_dir = tmp_path / "out"
    input_dir = tmp_path / "in"
    input_dir.mkdir()

    def failing_run_pipeline(config: Sys5Config):
        raise RequirementsFileError("missing file")

    monkeypatch.setattr(sys5, "run_pipeline", failing_run_pipeline)

    with pytest.raises(RequirementsFileError):
        sys5.generate(_raw_config(output_dir, input_dir))
