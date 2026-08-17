from __future__ import annotations

from openpyxl.worksheet.worksheet import Worksheet

from app.core.artifacts.swe6.output.sheets._common import write_sourced_table_sheet


def write_test_pattern_sheet(ws: Worksheet, pattern_data: dict) -> None:
    write_sourced_table_sheet(ws, pattern_data, title="Test Pattern")
