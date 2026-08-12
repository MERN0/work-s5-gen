"""Two-tier fuzzy matching that attaches relevant supporting-doc rows to a
requirement, and derives the literal signal/command token whitelist used by
the deterministic validator.

Tier 1 (row-level): match the whole requirement sentence against each
entity's full row text with `token_set_ratio` — good for long requirement
sentences vs. short entity rows, since it scores partial containment well
instead of penalizing length mismatch.

Tier 2 (token-level): match each entity's individual short field values
(likely identifiers) against the requirement text with a tighter threshold —
catches entities tier 1 misses when only one specific signal/command name
in a row is actually relevant.

`allowed_signal_tokens` is the union of every field value across ALL attached
context items, not just the substrings that triggered a match — the
generation agent legitimately needs to reference an entire command name or
value, not merely the fragment that happened to score well.

Honesty note (see also validation/rules.py): this is defense-in-depth, not a
mathematical guarantee against every hallucination — string matching has
irreducible false positive/negative edges (abbreviations, unit suffixes).
"""
from __future__ import annotations

from rapidfuzz import fuzz, process

from app.core.artifacts.sys5.config import Sys5Config
from app.core.artifacts.sys5.excel.supporting_docs_loader import SupportingEntity
from app.core.artifacts.sys5.models.requirement import (
    EnrichedRequirement,
    Requirement,
    SupportingContextItem,
)

_MAX_TOKEN_FIELD_LEN = 40


def enrich_requirement(
    requirement: Requirement, entities: list[SupportingEntity], config: Sys5Config
) -> EnrichedRequirement:
    if not entities:
        return EnrichedRequirement(requirement=requirement, supporting_context=[], allowed_signal_tokens=set())

    combined: dict[SupportingEntity, float] = _tier1_row_matches(requirement, entities, config)
    for entity, score in _tier2_token_matches(requirement, entities, config).items():
        combined[entity] = max(combined.get(entity, 0.0), score)

    ranked = sorted(combined.items(), key=lambda kv: kv[1], reverse=True)
    ranked = ranked[: config.max_supporting_context_items]

    context_items = [
        SupportingContextItem(
            entity_type=entity.entity_type,
            source_file=entity.source_file,
            source_sheet=entity.source_sheet,
            row_index=entity.row_index,
            fields=entity.fields,
            match_score=score,
        )
        for entity, score in ranked
    ]

    return EnrichedRequirement(
        requirement=requirement,
        supporting_context=context_items,
        allowed_signal_tokens=_collect_allowed_tokens(context_items),
    )


def _tier1_row_matches(
    requirement: Requirement, entities: list[SupportingEntity], config: Sys5Config
) -> dict[SupportingEntity, float]:
    choices = [e.searchable_text for e in entities]
    results = process.extract(
        requirement.requirement_text,
        choices,
        scorer=fuzz.token_set_ratio,
        limit=config.max_supporting_context_items,
    )
    return {
        entities[index]: score
        for _, score, index in results
        if score >= config.fuzzy_match_threshold
    }


def _tier2_token_matches(
    requirement: Requirement, entities: list[SupportingEntity], config: Sys5Config
) -> dict[SupportingEntity, float]:
    req_text = requirement.requirement_text
    matched: dict[SupportingEntity, float] = {}
    for entity in entities:
        best_score = max(
            (
                fuzz.partial_ratio(value, req_text)
                for value in entity.fields.values()
                if value and len(value) <= _MAX_TOKEN_FIELD_LEN
            ),
            default=0.0,
        )
        if best_score >= config.token_match_threshold:
            matched[entity] = best_score
    return matched


def _collect_allowed_tokens(context_items: list[SupportingContextItem]) -> set[str]:
    tokens: set[str] = set()
    for item in context_items:
        for value in item.fields.values():
            if value:
                tokens.add(value.strip())
    return tokens
