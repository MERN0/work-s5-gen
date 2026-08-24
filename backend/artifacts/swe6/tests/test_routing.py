from artifacts.common.schema import AgentStep
from artifacts.swe6.config import Swe6Config
from artifacts.swe6.graph import routing
from artifacts.swe6.models.test_case import ValidationResult


def _config(max_validation_attempts=2, max_correction_attempts=1, **overrides) -> Swe6Config:
    defaults = dict(
        output_dir="out",
        input_folder="in",
        max_validation_attempts=max_validation_attempts,
        max_correction_attempts=max_correction_attempts,
        agent_chain=[
            AgentStep(index=0, agent_name="verification_agent", max_retries=max_validation_attempts),
            AgentStep(index=1, agent_name="qa_agent", max_retries=max_correction_attempts),
        ],
    )
    defaults.update(overrides)
    return Swe6Config(**defaults)


def test_route_after_validate_finalizes_when_qa_agent_not_selected():
    state = {
        "current_validation": ValidationResult(passed=False, issues=[], attempt=1),
        "config": _config(agent_chain=[]),
        "correction_attempts": 0,
        "validation_attempts": 1,
    }
    assert routing.route_after_validate(state) == "finalize_item"


def test_route_after_prepare_goes_to_generate_when_queue_nonempty():
    state = {"queue": [{"requirement_id": "R1", "aspect": None}]}
    assert routing.route_after_prepare(state) == "generate_test_case"


def test_route_after_prepare_goes_to_build_outputs_when_queue_empty():
    assert routing.route_after_prepare({"queue": []}) == "build_outputs"


def test_route_after_validate_passes_straight_to_finalize():
    state = {
        "current_validation": ValidationResult(passed=True, issues=[], attempt=1),
        "config": _config(),
        "correction_attempts": 0,
        "validation_attempts": 1,
    }
    assert routing.route_after_validate(state) == "finalize_item"


def test_route_after_validate_corrects_when_budget_remains():
    state = {
        "current_validation": ValidationResult(passed=False, issues=[], attempt=1),
        "config": _config(max_validation_attempts=2, max_correction_attempts=1),
        "correction_attempts": 0,
        "validation_attempts": 1,
    }
    assert routing.route_after_validate(state) == "correct_test_case"


def test_route_after_validate_finalizes_when_correction_budget_exhausted():
    state = {
        "current_validation": ValidationResult(passed=False, issues=[], attempt=1),
        "config": _config(max_validation_attempts=2, max_correction_attempts=1),
        "correction_attempts": 1,
        "validation_attempts": 1,
    }
    assert routing.route_after_validate(state) == "finalize_item"


def test_route_after_validate_finalizes_when_validation_budget_exhausted():
    state = {
        "current_validation": ValidationResult(passed=False, issues=[], attempt=2),
        "config": _config(max_validation_attempts=2, max_correction_attempts=5),
        "correction_attempts": 0,
        "validation_attempts": 2,
    }
    assert routing.route_after_validate(state) == "finalize_item"


def test_route_after_validate_uses_qa_agent_step_max_retries_over_config_default():
    # The AgentStep's own max_retries wins over Swe6Config.max_correction_attempts
    # whenever qa_agent is present in agent_chain.
    config = _config(max_correction_attempts=1, agent_chain=[AgentStep(index=0, agent_name="qa_agent", max_retries=5)])
    state = {
        "current_validation": ValidationResult(passed=False, issues=[], attempt=1),
        "config": config,
        "correction_attempts": 2,
        "validation_attempts": 1,
    }
    assert routing.route_after_validate(state) == "correct_test_case"


def test_route_after_finalize_continues_queue_or_builds_outputs():
    assert (
        routing.route_after_finalize({"queue": [{"requirement_id": "R1", "aspect": None}]})
        == "generate_test_case"
    )
    assert routing.route_after_finalize({"queue": []}) == "build_outputs"
