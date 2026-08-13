"""Turns the raw SYS2 requirements workbook into Requirement records.

Algorithm, per target sheet:
1. Scan every cell of every row for a config.sys5_keywords hit (substring
   first, fuzzy fallback) — any hit makes that row a candidate requirement.
2. Find the header row by scanning upward from the first matched row (not
   assumed to be row 1).
3. Turn each matched row into a Requirement, picking `requirement_text` from
   a fuzzy-matched "description"-ish header, falling back to the longest
   string cell in the row.
4. Separately, scan the whole sheet for "Label: Value" metadata (handles
   "Feature Group: Ramp / Slope Control" wherever it happens to sit) and
   promote a fuzzy-matched subset into typed FeatureMeta fields.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from rapidfuzz import fuzz

from app.core.artifacts.sys5.config import Sys5Config
from app.core.artifacts.sys5.excel.raw_grid import (
    MAX_HEADER_CELL_LEN,
    RawSheet,
    find_header_row,
    load_workbook_sheets,
    row_to_dict,
)
from app.core.artifacts.sys5.exceptions import RequirementsFileError
from app.core.artifacts.sys5.models.requirement import FeatureMeta, Requirement

logger = logging.getLogger(__name__)

_REQ_TEXT_HEADER_HINTS = ["requirement text", "system requirement", "description", "requirement"]

_FEATURE_META_HINTS = {
    "feature_group": ["feature group"],
    "feature_name": ["feature name"],
    "object_heading": ["object heading"],
    "object_text": ["object text"],
}


def _normalize(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip().lower()


def load_requirements(config: Sys5Config) -> list[Requirement]:
    path = config.input_folder / config.req_filename
    if not path.exists():
        raise RequirementsFileError(f"Requirements file not found: {path}")

    try:
        sheets = load_workbook_sheets(path)
    except Exception as exc:
        raise RequirementsFileError(f"Could not read requirements file {path}: {exc}") from exc

    if config.req_sheet_name:
        sheets = [s for s in sheets if s.name == config.req_sheet_name]
        if not sheets:
            raise RequirementsFileError(f"Sheet '{config.req_sheet_name}' not found in {path.name}")

    logger.info("[sys5] Scanning %d sheet(s) of %s for requirement rows: %s", len(sheets), path.name, [s.name for s in sheets])

    requirements: list[Requirement] = []
    for sheet in sheets:
        requirements.extend(_extract_requirements_from_sheet(sheet, config))
    logger.info("[sys5] Extracted %d requirement row(s) total from %s.", len(requirements), path.name)
    return requirements


def _extract_requirements_from_sheet(sheet: RawSheet, config: Sys5Config) -> list[Requirement]:
    matched_rows = _scan_for_keyword_rows(sheet, config)
    if not matched_rows:
        logger.info("[sys5] Sheet %r: no keyword-matched rows.", sheet.name)
        return []

    header_row_index, header = find_header_row(sheet, anchor_row=matched_rows[0][0])
    logger.info(
        "[sys5] Sheet %r: %d row(s) matched a sys5 keyword; header row=%s.",
        sheet.name, len(matched_rows), header_row_index,
    )
    feature = _extract_feature_meta(sheet)

    requirements = []
    for row_index, matched_keyword in matched_rows:
        row_values = sheet.rows[row_index - 1]
        cells = row_to_dict(row_values, header)
        requirement_text = _pick_requirement_text(cells, row_values, header)
        req_id = _pick_req_id(row_values, sheet.name, row_index)
        logger.info(
            "[sys5] Sheet %r row %d: req_id=%r (matched keyword %r)", sheet.name, row_index, req_id, matched_keyword,
        )
        requirements.append(
            Requirement(
                req_id=req_id,
                source_file=sheet.source_file,
                sheet_name=sheet.name,
                row_index=row_index,
                cells=cells,
                requirement_text=requirement_text,
                matched_keyword=matched_keyword,
                feature=feature,
            )
        )
    return requirements


def _scan_for_keyword_rows(sheet: RawSheet, config: Sys5Config) -> list[tuple[int, str]]:
    matches: list[tuple[int, str]] = []
    for row_index, row_values in sheet.iter_rows():
        hit = _row_matches_keyword(row_values, config)
        if hit:
            matches.append((row_index, hit))
    return matches


def _row_matches_keyword(row_values: list, config: Sys5Config) -> str | None:
    for cell_value in row_values:
        text = _normalize(cell_value)
        if not text:
            continue
        for keyword in config.sys5_keywords:
            kw = keyword.strip().lower()
            if not kw:
                continue
            if kw in text or fuzz.partial_ratio(kw, text) >= config.keyword_match_threshold:
                return keyword
    return None


def _pick_requirement_text(cells: dict, row_values: list, header: list[str] | None) -> str:
    if header:
        for key, value in cells.items():
            key_norm = _normalize(key)
            if isinstance(value, str) and value.strip() and any(
                hint in key_norm for hint in _REQ_TEXT_HEADER_HINTS
            ):
                return value.strip()
    strings = [str(v).strip() for v in row_values if isinstance(v, str) and v.strip()]
    return max(strings, key=len) if strings else ""


def _pick_req_id(row_values: list, sheet_name: str, row_index: int) -> str:
    """The requirement ID always lives in the row's first column - scanning
    every column's *header* for an "id"-ish hint (the old approach) was
    unreliable: substrings like "id" also match unrelated headers ("Valid",
    "Provided", "Guidance", ...), so a header hit earlier in the row than the
    real ID column could silently steal traceability for the wrong value.
    """
    first_cell = row_values[0] if row_values else None
    if first_cell not in (None, ""):
        return str(first_cell).strip()
    return f"{sheet_name}-R{row_index}"


def _extract_feature_meta(sheet: RawSheet) -> FeatureMeta:
    raw_metadata: dict[str, str] = {}
    for _, row_values in sheet.iter_rows():
        for i, cell_value in enumerate(row_values):
            if not isinstance(cell_value, str):
                continue
            text = cell_value.strip()
            if not text or ":" not in text:
                continue
            label, _, value = text.partition(":")
            label, value = label.strip(), value.strip()
            if not label or len(label) >= MAX_HEADER_CELL_LEN:
                continue
            if value:
                raw_metadata[label] = value
            elif i + 1 < len(row_values) and isinstance(row_values[i + 1], str) and row_values[i + 1].strip():
                raw_metadata[label] = row_values[i + 1].strip()

    typed: dict[str, str] = {}
    for field_name, hints in _FEATURE_META_HINTS.items():
        for label, value in raw_metadata.items():
            if any(hint in _normalize(label) for hint in hints):
                typed[field_name] = value
                break

    return FeatureMeta(raw_metadata=raw_metadata, **typed)
