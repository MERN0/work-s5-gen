"""Requirement-side data models: what we extract from SYS2 requirement sheets
and the supporting-doc context we attach to each requirement before generation.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FeatureMeta(BaseModel):
    """Sheet-scoped metadata (constant for the whole run of one requirement sheet),
    e.g. "Feature Group: Ramp / Slope Control" found somewhere on the sheet.
    """

    feature_group: str | None = None
    feature_name: str | None = None
    object_heading: str | None = None
    object_text: str | None = None
    raw_metadata: dict[str, str] = Field(default_factory=dict)


class Requirement(BaseModel):
    """One row from the requirements sheet that matched a SYS5 keyword."""

    req_id: str
    source_file: str
    sheet_name: str
    row_index: int
    cells: dict[str, Any] = Field(default_factory=dict)
    requirement_text: str
    matched_keyword: str
    feature: FeatureMeta = Field(default_factory=FeatureMeta)


class SupportingContextItem(BaseModel):
    """One row from a supporting doc (signals/commands/comm matrix/etc.) judged
    relevant to a requirement by fuzzy matching. `entity_type` is a soft,
    display-only guess based on the source sheet name — never used to filter
    candidates out of matching, since sheet naming varies too much per project.
    """

    entity_type: str = "other"
    source_file: str
    source_sheet: str
    row_index: int
    fields: dict[str, str] = Field(default_factory=dict)
    match_score: float = 0.0


class EnrichedRequirement(BaseModel):
    """A Requirement plus everything the generation agent is allowed to reference."""

    requirement: Requirement
    supporting_context: list[SupportingContextItem] = Field(default_factory=list)
    allowed_signal_tokens: set[str] = Field(default_factory=set)
