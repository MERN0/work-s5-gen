from app.core.artifacts.sys5.models.test_case import ActionStep, GeneratedTestCase, VerificationStep
from app.core.artifacts.sys5.validation import rules
from app.core.artifacts.sys5.validation.numbering import render


def _make_test_case(**overrides) -> GeneratedTestCase:
    defaults = dict(
        feature="Slope Assist",
        variant="A1",
        requirement_ids=["REQ-1"],
        test_type="Normal_system",
        objective="Verify slope assist activates",
        description="Test slope assist activation",
        pre_condition="Vehicle powered on",
        input_data=None,
        setup_action_steps=[ActionStep(verb="SET", detail="VehIgn to ON")],
        verification_steps=[
            VerificationStep(verb="VERIFY", detail="SlopeAssistState", expected_result="Active")
        ],
        mode_of_execution="Automated",
        priority="P2",
    )
    defaults.update(overrides)
    return GeneratedTestCase(**defaults)


def test_render_numbers_continuously_from_test_start_to_end_of_test():
    tc = _make_test_case(
        setup_action_steps=[
            ActionStep(verb="SET", detail="Battery voltage to 14V"),
            ActionStep(verb="WAIT", detail="2 seconds"),
        ],
        verification_steps=[
            VerificationStep(verb="VERIFY", detail="SlopeAssistState", expected_result="Active"),
        ],
    )
    steps_text, results_text = render(tc)

    assert steps_text.splitlines() == [
        "1. Test_start",
        "2. SET Battery voltage to 14V",
        "3. WAIT 2 seconds",
        "4. VERIFY SlopeAssistState",
        "5. End_of_test",
    ]
    assert results_text.splitlines() == ["4. Active"]


def test_render_handles_zero_steps():
    tc = _make_test_case(setup_action_steps=[], verification_steps=[])
    steps_text, results_text = render(tc)
    assert steps_text.splitlines() == ["1. Test_start", "2. End_of_test"]
    assert results_text == ""


def test_rules_flag_empty_test_case():
    tc = _make_test_case(setup_action_steps=[], verification_steps=[])
    issues = rules.check_test_case(tc, allowed_tokens=set())
    codes = {i.code for i in issues}
    assert "no_steps" in codes
    assert "no_checkable_outcome" in codes
    assert not rules.passed(issues)


def test_rules_pass_a_well_formed_test_case_with_known_tokens():
    tc = _make_test_case()
    issues = rules.check_test_case(tc, allowed_tokens={"VehIgn", "SlopeAssistState"})
    assert rules.passed(issues)


def test_rules_warn_but_not_fail_on_unrecognized_token():
    tc = _make_test_case(
        setup_action_steps=[ActionStep(verb="SET", detail="HallucinatedSignalXYZ to 1")],
    )
    issues = rules.check_test_case(tc, allowed_tokens={"SlopeAssistState"})
    warning_codes = {i.code for i in issues if i.severity == "warning"}
    assert "unrecognized_token" in warning_codes
    assert rules.passed(issues)  # a warning alone must not fail the deterministic check


def test_rules_require_at_least_one_checkable_verification_step():
    tc = _make_test_case(
        verification_steps=[VerificationStep(verb="VERIFY", detail="Something", expected_result="")]
    )
    issues = rules.check_test_case(tc, allowed_tokens=set())
    codes = {i.code for i in issues}
    assert "no_checkable_outcome" in codes
