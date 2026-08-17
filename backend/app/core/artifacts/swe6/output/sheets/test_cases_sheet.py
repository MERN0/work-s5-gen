"""Writes the main Test Cases sheet — the one sheet whose name matches the
input requirements sheet name (req_sheet_name). Column layout comes entirely
from the active FormatProfile, so a project needing different/renamed/
reordered columns just supplies a different `test_case_columns` list.
"""
from __future__ import annotations

from openpyxl.worksheet.worksheet import Worksheet

from app.core.artifacts.swe6.formats.base import FormatProfile
from app.core.artifacts.swe6.models.test_case import TestCase
from app.core.artifacts.swe6.output.styles import set_column_widths, style_data_row, style_header_row
from app.core.artifacts.swe6.validation.numbering import render


def write_test_cases_sheet(ws: Worksheet, results: list[TestCase], profile: FormatProfile) -> None:
    columns = profile.test_case_columns
    for col_index, column in enumerate(columns, start=1):
        ws.cell(row=1, column=col_index, value=column.header)
    style_header_row(ws, row=1, num_columns=len(columns))
    set_column_widths(ws, [c.width for c in columns])

    wrap_columns = {i for i, c in enumerate(columns, start=1) if c.wrap}

    for row_offset, test_case in enumerate(results, start=2):
        row_data = _test_case_to_row(test_case)
        for col_index, column in enumerate(columns, start=1):
            ws.cell(row=row_offset, column=col_index, value=row_data.get(column.key, ""))
        style_data_row(ws, row=row_offset, num_columns=len(columns), wrap_columns=wrap_columns)

    ws.freeze_panes = "A2"


def _test_case_to_row(tc: TestCase) -> dict:
    steps_text, results_text = render(tc)
    return {
        "testcase_id": tc.testcase_id,
        "feature": tc.feature,
        "variant": tc.variant or "",
        "requirement_ids": ", ".join(tc.requirement_ids),
        "objective": tc.objective,
        "description": tc.description,
        "pre_condition": tc.pre_condition,
        "input_data": tc.input_data or "",
        "test_steps": steps_text,
        "expected_results": results_text,
        "mode_of_execution": tc.mode_of_execution,
        "priority": tc.priority,
        "odc_trigger": tc.odc_trigger or "",
    }
