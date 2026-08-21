"""The "default" format profile — the only one needed right now. Test Cases /
Item List are always mechanically generated from `state["results"]`. Cover
Page is templated from config + feature metadata. Test Pattern and
Configurable Parameters are sourced from a matching supporting-doc sheet when
fuzzy sheet-name matching finds one (e.g. a "Test Pattern" or "Application
Parameters" tab), else a minimal labeled placeholder — never fabricated data.
"""
from __future__ import annotations

from datetime import datetime

from artifacts.sys5.excel.raw_grid import RawSheet, find_header_row, row_to_dict
from artifacts.sys5.formats.base import ColumnSpec, FormatProfile, WorkbookBuildContext
from artifacts.sys5.models.requirement import FeatureMeta

DEFAULT_TEST_CASE_COLUMNS: list[ColumnSpec] = [
    ColumnSpec("testcase_id", "TestCase ID", width=16, wrap=False),
    ColumnSpec("feature", "Feature", width=20),
    ColumnSpec("variant", "Variant", width=16),
    ColumnSpec("requirement_ids", "Traceability/Requirement IDs", width=22),
    ColumnSpec("objective", "Objective", width=32),
    ColumnSpec("description", "Description", width=32),
    ColumnSpec("pre_condition", "Pre Condition", width=26),
    ColumnSpec("input_data", "Input data/file", width=20),
    ColumnSpec("test_steps", "Test Steps", width=45),
    ColumnSpec("expected_results", "Expected Results", width=45),
    ColumnSpec("mode_of_execution", "Mode of Execution", width=16, wrap=False),
    ColumnSpec("priority", "Priority", width=10, wrap=False),
    ColumnSpec("odc_trigger", "ODC Trigger", width=20),
]

_TEST_PATTERN_SHEET_HINTS = ["test pattern", "combinatorial", "combination"]
_CONFIGURABLE_PARAMETERS_SHEET_HINTS = ["configurable parameter", "application parameter", "variant"]


def _find_matching_sheet(sheets: list[RawSheet], hints: list[str]) -> RawSheet | None:
    for sheet in sheets:
        name_norm = sheet.name.lower()
        if any(hint in name_norm for hint in hints):
            return sheet
    return None


def _sourced_table(sheet: RawSheet | None) -> dict:
    if sheet is None:
        return {"found": False}
    header_row_index, header = find_header_row(sheet)
    if not header:
        return {"found": False}
    rows = []
    for row_index, row_values in sheet.iter_rows():
        if row_index <= header_row_index:
            continue
        if not any(v not in (None, "") for v in row_values):
            continue
        rows.append({k: v for k, v in row_to_dict(row_values, header).items() if v not in (None,)})
    return {"found": True, "columns": header, "rows": rows, "source_sheet": sheet.name}


def build_test_pattern(ctx: WorkbookBuildContext) -> dict:
    sheet = _find_matching_sheet(ctx.supporting_sheets, _TEST_PATTERN_SHEET_HINTS)
    return _sourced_table(sheet)


def build_configurable_parameters(ctx: WorkbookBuildContext) -> dict:
    sheet = _find_matching_sheet(ctx.supporting_sheets, _CONFIGURABLE_PARAMETERS_SHEET_HINTS)
    return _sourced_table(sheet)


def _first_feature(ctx: WorkbookBuildContext) -> FeatureMeta:
    for enriched in ctx.state["enriched_requirements"].values():
        return enriched.requirement.feature
    return FeatureMeta()


def build_cover_page(ctx: WorkbookBuildContext) -> dict:
    config = ctx.state["config"]
    feature = _first_feature(ctx)
    title = feature.feature_name or config.project_name

    return {
        "title": title,
        "feature_group": feature.feature_group,
        "object_heading": feature.object_heading,
        "doc_meta": {
            "Document No": f"TD/{config.project_name}/{config.artifact or 'SYS5'}",
            "Version": config.version,
            "Created By": config.username,
            "Verified By": config.username,
        },
        "revision_rows": [
            {
                "Revision No": config.version,
                "Change Description": f"Auto-generated SYS5 test cases for {title}",
                "Date": datetime.now().strftime("%Y-%m-%d"),
                "Created by": config.username,
                "Approved by": config.username,
                "Description": f"{config.artifact or 'SYS5'} generation run",
            }
        ],
    }


DEFAULT_FORMAT_PROFILE = FormatProfile(
    name="default",
    test_case_columns=DEFAULT_TEST_CASE_COLUMNS,
    build_cover_page=build_cover_page,
    build_test_pattern=build_test_pattern,
    build_configurable_parameters=build_configurable_parameters,
)
