"""Item List: a 1:1 summary index of every generated test case. Always
mechanically derived from state["results"] — never templated or sourced from
supporting docs, since its entire purpose is to reflect what was actually
generated.
"""
from __future__ import annotations

from openpyxl.worksheet.worksheet import Worksheet

from artifacts.sys5.models.test_case import TestCase
from artifacts.sys5.output.styles import set_column_widths, style_data_row, style_header_row

_HEADERS = [
    "Sr#",
    "Test type",
    "Feature Name",
    "Test Case ID",
    "Applicable Variants",
    "Execution Required",
    "Remarks",
]
_WIDTHS = [6, 18, 24, 18, 20, 16, 30]


def write_item_list_sheet(ws: Worksheet, results: list[TestCase]) -> None:
    for col_index, header in enumerate(_HEADERS, start=1):
        ws.cell(row=1, column=col_index, value=header)
    style_header_row(ws, row=1, num_columns=len(_HEADERS))
    set_column_widths(ws, _WIDTHS)

    for offset, tc in enumerate(results, start=2):
        values = [
            offset - 1,
            tc.test_type or "Normal",
            tc.feature,
            tc.testcase_id,
            tc.variant or "",
            "Yes",
            tc.remarks or "",
        ]
        for col_index, value in enumerate(values, start=1):
            ws.cell(row=offset, column=col_index, value=value)
        style_data_row(ws, row=offset, num_columns=len(_HEADERS), wrap_columns={7})
