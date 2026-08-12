"""Synthetic fixtures mirroring the real project layout: metadata (Feature
Group:/Feature Name:) scattered above a header that isn't on row 1, and a
requirement row whose "Verification Method"-style column carries a
"SYS Qualification Test" keyword alongside a "Precondition:/Test Procedure:"
authored block - the real shape observed in the project's own System
Requirements sheet, not just a simplified stand-in for it.
"""
from __future__ import annotations

import openpyxl
import pytest

from app.core.artifacts.sys5.config import Sys5Config
from app.core.artifacts.sys5.excel.requirements_loader import load_requirements
from app.core.artifacts.sys5.exceptions import RequirementsFileError


@pytest.fixture
def requirements_workbook(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "005"

    ws.append(["Feature Group:", "Ramp / Slope Control"])
    ws.append(["Feature Name:", "005 - Ramp / Slope Control"])
    ws.append([])
    ws.append(
        ["id", "Requirement Text", "Object Type", "Verification Method", "Precondition/Procedure", "Status"]
    )
    ws.append([1, "Note: Normal Operation, no error", "Information", "", "", "Approved"])
    ws.append(
        [
            2,
            "When VehIgn is Active (ON) then the Motor Control Unit shall translate "
            "the requested speed to Motor speed as per the command law graph.",
            "Functional Requirement",
            "SYS Qualification Test",
            "Precondition:\n1. Set the battery voltage to 14V\n2. No faults present\n\n"
            "Test Procedure:\n1. Send target speed in steps of 10% via LIN",
            "Approved",
        ]
    )
    ws.append([3, "An informational note about payroll schedules, not a test requirement.", "Information", "", "", "Approved"])

    path = tmp_path / "requirements.xlsx"
    wb.save(path)
    return path


def _config(tmp_path, req_filename: str, **overrides) -> Sys5Config:
    defaults = dict(
        output_dir=tmp_path / "out",
        input_folder=tmp_path,
        req_filename=req_filename,
        req_sheet_name="005",
    )
    defaults.update(overrides)
    return Sys5Config(**defaults)


def test_load_requirements_finds_only_the_keyword_matched_row(tmp_path, requirements_workbook):
    config = _config(tmp_path, requirements_workbook.name)
    requirements = load_requirements(config)

    assert len(requirements) == 1
    assert "Motor Control Unit shall translate" in requirements[0].requirement_text


def test_load_requirements_extracts_feature_metadata_from_anywhere_on_sheet(tmp_path, requirements_workbook):
    config = _config(tmp_path, requirements_workbook.name)
    requirements = load_requirements(config)

    feature = requirements[0].feature
    assert feature.feature_group == "Ramp / Slope Control"
    assert feature.feature_name == "005 - Ramp / Slope Control"


def test_load_requirements_captures_authored_precondition_block_in_cells(tmp_path, requirements_workbook):
    config = _config(tmp_path, requirements_workbook.name)
    requirements = load_requirements(config)

    cells = requirements[0].cells
    assert "Precondition:" in cells["Precondition/Procedure"]


def test_load_requirements_processes_all_sheets_when_sheet_name_blank(tmp_path, requirements_workbook):
    config = _config(tmp_path, requirements_workbook.name, req_sheet_name="")
    requirements = load_requirements(config)
    assert len(requirements) == 1


def test_load_requirements_raises_for_missing_file(tmp_path):
    config = _config(tmp_path, "does_not_exist.xlsx")
    with pytest.raises(RequirementsFileError):
        load_requirements(config)


def test_load_requirements_raises_for_missing_sheet(tmp_path, requirements_workbook):
    config = _config(tmp_path, requirements_workbook.name, req_sheet_name="999")
    with pytest.raises(RequirementsFileError):
        load_requirements(config)
