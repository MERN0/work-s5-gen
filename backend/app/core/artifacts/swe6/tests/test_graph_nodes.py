"""Node-level control-flow tests with call_structured monkeypatched — no real
LLM call, deterministic and fast. Exercises the generate -> validate ->
correct -> finalize cycle each node is responsible for.
"""
from __future__ import annotations

import app.core.artifacts.swe6.graph.nodes as nodes_module
from app.core.artifacts.swe6.config import Swe6Config
from app.core.artifacts.swe6.models.requirement import EnrichedRequirement, FeatureMeta, Requirement
from app.core.artifacts.swe6.models.test_case import (
    ActionStep,
    GeneratedTestCase,
    SemanticVerdict,
    TestAspect,
    ValidationResult,
    VerificationStep,
)


def _config(**overrides) -> Swe6Config:
    defaults = dict(
        project_name="tmhc_demo",
        output_dir="out",
        input_folder="in",
        max_validation_attempts=2,
        max_correction_attempts=1,
    )
    defaults.update(overrides)
    return Swe6Config(**defaults)


def _enriched() -> EnrichedRequirement:
    requirement = Requirement(
        req_id="R1",
        source_file="reqs.xlsx",
        sheet_name="005",
        row_index=10,
        cells={},
        requirement_text="When VehIgn is Active then...",
        matched_keyword="sw qualification test",
        feature=FeatureMeta(),
    )
    return EnrichedRequirement(requirement=requirement, supporting_context=[], allowed_signal_tokens={"VehIgn"})


def _aspect() -> TestAspect:
    return TestAspect(aspect_id="A1", title="Basic activation")


def _valid_generated_test_case() -> GeneratedTestCase:
    return GeneratedTestCase(
        feature="Slope Assist",
        variant="A1",
        requirement_ids=["R1"],
        test_type="Normal_system",
        objective="Verify",
        description="Test",
        pre_condition="Powered on",
        input_data=None,
        setup_action_steps=[ActionStep(verb="SET", detail="VehIgn to ON")],
        verification_steps=[VerificationStep(verb="VERIFY", detail="VehIgn", expected_result="ON")],
        mode_of_execution="Automated",
        priority="P2",
    )


def test_generate_test_case_populates_current_test_case(monkeypatch):
    state = {
        "config": _config(),
        "llm": object(),
        "enriched_requirements": {"R1": _enriched()},
        "queue": [{"requirement_id": "R1", "aspect": _aspect()}],
    }
    monkeypatch.setattr(nodes_module, "call_structured", lambda *a, **k: _valid_generated_test_case())

    update = nodes_module.generate_test_case(state)

    assert update["current_test_case"].objective == "Verify"
    assert update["validation_attempts"] == 0
    assert update["correction_attempts"] == 0


def test_generate_test_case_falls_back_to_stub_on_llm_failure(monkeypatch):
    config = _config()
    state = {
        "config": config,
        "llm": object(),
        "enriched_requirements": {"R1": _enriched()},
        "queue": [{"requirement_id": "R1", "aspect": _aspect()}],
    }

    def boom(*a, **k):
        raise RuntimeError("LLM gateway unreachable")

    monkeypatch.setattr(nodes_module, "call_structured", boom)

    update = nodes_module.generate_test_case(state)

    assert update["current_test_case"].setup_action_steps == []
    assert update["validation_attempts"] == config.max_validation_attempts
    assert update["correction_attempts"] == config.max_correction_attempts


def test_validate_test_case_runs_semantic_check_only_after_deterministic_pass(monkeypatch):
    state = {
        "config": _config(),
        "llm": object(),
        "enriched_requirements": {"R1": _enriched()},
        "current_item": {"requirement_id": "R1", "aspect": _aspect()},
        "current_test_case": _valid_generated_test_case(),
        "validation_attempts": 0,
    }
    monkeypatch.setattr(
        nodes_module, "call_structured", lambda *a, **k: SemanticVerdict(passed=True, feedback=None)
    )

    update = nodes_module.validate_test_case(state)

    assert update["current_validation"].passed is True
    assert update["validation_attempts"] == 1


def test_validate_test_case_skips_semantic_check_when_deterministic_check_fails(monkeypatch):
    empty_test_case = _valid_generated_test_case()
    empty_test_case.setup_action_steps = []
    empty_test_case.verification_steps = []

    state = {
        "config": _config(),
        "llm": object(),
        "enriched_requirements": {"R1": _enriched()},
        "current_item": {"requirement_id": "R1", "aspect": _aspect()},
        "current_test_case": empty_test_case,
        "validation_attempts": 0,
    }

    def fail_if_called(*a, **k):
        raise AssertionError("semantic check must not run when deterministic checks already failed")

    monkeypatch.setattr(nodes_module, "call_structured", fail_if_called)

    update = nodes_module.validate_test_case(state)

    assert update["current_validation"].passed is False


def test_correct_test_case_replaces_current_test_case(monkeypatch):
    corrected = _valid_generated_test_case()
    corrected.objective = "Corrected objective"

    state = {
        "config": _config(),
        "llm": object(),
        "enriched_requirements": {"R1": _enriched()},
        "current_item": {"requirement_id": "R1", "aspect": _aspect()},
        "current_test_case": _valid_generated_test_case(),
        "current_validation": ValidationResult(passed=False, issues=[], attempt=1),
        "correction_attempts": 0,
    }
    monkeypatch.setattr(nodes_module, "call_structured", lambda *a, **k: corrected)

    update = nodes_module.correct_test_case(state)

    assert update["current_test_case"].objective == "Corrected objective"
    assert update["correction_attempts"] == 1


def test_finalize_item_assigns_id_and_shrinks_queue():
    state = {
        "config": _config(),
        "enriched_requirements": {"R1": _enriched()},
        "current_item": {"requirement_id": "R1", "aspect": _aspect()},
        "current_test_case": _valid_generated_test_case(),
        "current_validation": ValidationResult(passed=True, issues=[], attempt=1),
        "queue": [
            {"requirement_id": "R1", "aspect": _aspect()},
            {"requirement_id": "R2", "aspect": TestAspect(aspect_id="A2", title="Next")},
        ],
        "next_test_case_number": 1,
    }

    update = nodes_module.finalize_item(state)

    assert update["results"][0].testcase_id == "TMHC_DEMO_SWQTC_001"
    assert update["next_test_case_number"] == 2
    assert len(update["queue"]) == 1
    assert update["queue"][0]["requirement_id"] == "R2"
