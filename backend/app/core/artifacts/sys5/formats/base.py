"""A FormatProfile is a project's output-workbook shape as a data contract,
not styling. A future second project with different Test Case columns or
headings plugs in as a new formats/<name>_profile.py + one registry entry —
the graph, styling helpers, and Test Cases/Item List logic never change.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.core.artifacts.sys5.excel.raw_grid import RawSheet
from app.core.artifacts.sys5.models.state import PipelineState


@dataclass(frozen=True)
class ColumnSpec:
    key: str
    header: str
    width: int = 20
    wrap: bool = True


@dataclass
class WorkbookBuildContext:
    """Everything a format profile's sheet-data builders might need."""

    state: PipelineState
    supporting_sheets: list[RawSheet]


@dataclass(frozen=True)
class FormatProfile:
    name: str
    test_case_columns: list[ColumnSpec]
    build_cover_page: Callable[[WorkbookBuildContext], dict]
    build_test_pattern: Callable[[WorkbookBuildContext], dict]
    build_configurable_parameters: Callable[[WorkbookBuildContext], dict]
