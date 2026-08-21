from __future__ import annotations

from openpyxl.worksheet.worksheet import Worksheet

from artifacts.sys5.output.sheets._common import write_sourced_table_sheet


def write_configurable_parameters_sheet(ws: Worksheet, params_data: dict) -> None:
    write_sourced_table_sheet(ws, params_data, title="Configurable Parameters")
