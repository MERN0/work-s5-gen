"""Builds a flat, searchable index of every row in every supporting-doc sheet
(function lists, API/interface specs, error/return-code tables, calibration
parameters, test patterns, plus the signal/command/comm-matrix tabs a
software module still touches — names and shapes vary per project). No
column names are ever hardcoded here: shape genuinely differs project to
project, so the only thing extracted generically is "every non-empty row's
values," left for matching/fuzzy_context.py to search over.

Deliberately includes every OTHER tab of the requirements workbook itself
(e.g. an "Error Codes" or "API Specification" tab living alongside "Software
Requirements" in the same file) — that's a real observed project layout, not
just separate files.
"""
from __future__ import annotations

import logging
from pathlib import Path

from artifacts.swe6.config import Swe6Config
from artifacts.swe6.excel.raw_grid import RawSheet, find_header_row, load_workbook_sheets, row_to_dict

logger = logging.getLogger(__name__)

_ENTITY_TYPE_HINTS: dict[str, str] = {
    "function": "function",
    "api": "api",
    "interface": "interface",
    "error": "error_code",
    "return code": "return_code",
    "calibrat": "calibration_parameter",
    "signal": "signal",
    "command": "command",
    "librar": "library",
    "compound": "compound_command",
    "communicat": "comm_matrix",
    "matrix": "comm_matrix",
    "network": "comm_matrix",  # real project tabs are often named e.g. "BEV Response Network Rel"
    "parameter": "configurable_parameter",
    "pattern": "test_pattern",
    "combinat": "test_pattern",
}


class SupportingEntity:
    """One non-empty row from a supporting-doc sheet, pre-indexed for fuzzy
    search. An internal, ephemeral record (not a pydantic model, never
    serialized) — matching/fuzzy_context.py turns hits into the pydantic
    SupportingContextItem that actually gets attached to a requirement.
    """

    __slots__ = ("entity_type", "source_file", "source_sheet", "row_index", "fields", "searchable_text")

    def __init__(self, entity_type, source_file, source_sheet, row_index, fields, searchable_text):
        self.entity_type = entity_type
        self.source_file = source_file
        self.source_sheet = source_sheet
        self.row_index = row_index
        self.fields = fields
        self.searchable_text = searchable_text


def load_supporting_sheets(config: Swe6Config) -> list[RawSheet]:
    """Every sheet of every candidate supporting-doc file, as raw grids. Used
    both to build the fuzzy-search entity index below and, later, by the
    format profile to locate a project's Test Pattern / Configurable
    Parameters tab by name (see formats/default_profile.py).
    """
    candidates = _candidate_files(config)
    logger.info("[swe6] Supporting-doc candidate file(s): %s", [p.name for p in candidates])
    sheets: list[RawSheet] = []
    for path in candidates:
        try:
            loaded = load_workbook_sheets(path)
        except Exception as exc:
            logger.warning("[swe6] Skipping unreadable supporting file %s: %s", path.name, exc)
            continue  # corrupt/unreadable supporting file: skip, never fatal
        logger.info("[swe6] %s: loaded %d sheet(s): %s", path.name, len(loaded), [s.name for s in loaded])
        sheets.extend(loaded)
    return sheets


def load_supporting_entities(config: Swe6Config) -> list[SupportingEntity]:
    entities: list[SupportingEntity] = []
    for sheet in load_supporting_sheets(config):
        sheet_entities = _sheet_to_entities(sheet)
        entity_types = sorted({e.entity_type for e in sheet_entities})
        logger.info(
            "[swe6] Sheet %r (%s): indexed %d row(s) as supporting entities (types=%s).",
            sheet.name, sheet.source_file, len(sheet_entities), entity_types,
        )
        entities.extend(sheet_entities)
    return entities


def _candidate_files(config: Swe6Config) -> list[Path]:
    if config.uploaded_files:
        return [config.input_folder / name for name in config.uploaded_files]
    files: list[Path] = []
    for pattern in ("*.xlsx", "*.xlsm"):
        files.extend(config.input_folder.glob(pattern))
    return files


def _guess_entity_type(sheet_name: str) -> str:
    name_norm = sheet_name.lower()
    for hint, entity_type in _ENTITY_TYPE_HINTS.items():
        if hint in name_norm:
            return entity_type
    return "other"


def _sheet_to_entities(sheet: RawSheet) -> list[SupportingEntity]:
    entity_type = _guess_entity_type(sheet.name)
    header_row_index, header = find_header_row(sheet)

    entities = []
    for row_index, row_values in sheet.iter_rows():
        if header_row_index is not None and row_index <= header_row_index:
            continue
        if not any(v not in (None, "") for v in row_values):
            continue
        fields = {
            k: str(v) for k, v in row_to_dict(row_values, header).items() if v not in (None, "")
        }
        searchable_text = " ".join(str(v) for v in row_values if isinstance(v, (str, int, float)))
        if not searchable_text.strip():
            continue
        entities.append(
            SupportingEntity(
                entity_type=entity_type,
                source_file=sheet.source_file,
                source_sheet=sheet.name,
                row_index=row_index,
                fields=fields,
                searchable_text=searchable_text,
            )
        )
    return entities
