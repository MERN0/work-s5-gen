from app.core.artifacts.swe6.config import Swe6Config
from app.core.artifacts.swe6.excel.supporting_docs_loader import SupportingEntity
from app.core.artifacts.swe6.matching.fuzzy_context import enrich_requirement
from app.core.artifacts.swe6.models.requirement import FeatureMeta, Requirement


def _config(**overrides) -> Swe6Config:
    defaults = dict(output_dir="out", input_folder="in")
    defaults.update(overrides)
    return Swe6Config(**defaults)


def _requirement(text: str) -> Requirement:
    return Requirement(
        req_id="R1",
        source_file="reqs.xlsx",
        sheet_name="005",
        row_index=10,
        cells={},
        requirement_text=text,
        matched_keyword="software qualification",
        feature=FeatureMeta(),
    )


def test_enrich_requirement_finds_relevant_entities_by_row_text():
    requirement = _requirement(
        "When VehIgn is Active then the Fan Controller shall report FanARespRPM."
    )
    entities = [
        SupportingEntity(
            entity_type="signal",
            source_file="comm_matrix.xlsx",
            source_sheet="BEV Response Network Rel",
            row_index=26,
            fields={"Signal Name": "FanARespRPM", "Signal Function": "Fan Actual Speed"},
            searchable_text="Fan Response FanA FanARespRPM Fan Actual Speed",
        ),
        SupportingEntity(
            entity_type="other",
            source_file="unrelated.xlsx",
            source_sheet="Unrelated",
            row_index=2,
            fields={"Note": "Completely unrelated content about payroll schedules"},
            searchable_text="Completely unrelated content about payroll schedules",
        ),
    ]

    enriched = enrich_requirement(requirement, entities, _config())

    matched_sheets = {item.source_sheet for item in enriched.supporting_context}
    assert "BEV Response Network Rel" in matched_sheets
    assert "Unrelated" not in matched_sheets
    assert "FanARespRPM" in enriched.allowed_signal_tokens


def test_enrich_requirement_with_no_entities_returns_empty_context():
    requirement = _requirement("Some requirement text")
    enriched = enrich_requirement(requirement, [], _config())
    assert enriched.supporting_context == []
    assert enriched.allowed_signal_tokens == set()


def test_enrich_requirement_respects_max_supporting_context_items():
    requirement = _requirement("Verify FanARespRPM behavior under all conditions.")
    entities = [
        SupportingEntity(
            entity_type="signal",
            source_file="comm_matrix.xlsx",
            source_sheet="Sheet1",
            row_index=i,
            fields={"Signal Name": f"FanARespRPM_{i}"},
            searchable_text=f"FanARespRPM behavior condition {i}",
        )
        for i in range(10)
    ]

    enriched = enrich_requirement(requirement, entities, _config(max_supporting_context_items=3))
    assert len(enriched.supporting_context) <= 3
