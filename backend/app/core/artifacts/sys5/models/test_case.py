"""Test-case-side data models: the planned test scenarios and the generated
SYS5 test cases themselves, plus validation results.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ModeOfExecution = Literal["Manual", "Automated", "Semi-automated"]
Priority = Literal["P1", "P2", "P3", "P4", "P5"]


class TestAspect(BaseModel):
    """One planned test scenario for a requirement (1-2 lines, doesn't restate
    the requirement itself) — a requirement with N applicable aspects becomes
    N separate test cases.
    """

    aspect_id: str
    title: str
    rationale: str | None = None
    test_type: str | None = None


class ActionStep(BaseModel):
    """A precondition-setup or action step. Only SET/WAIT are valid verbs here —
    enforced by the Literal type itself, not just by prompt instruction."""

    verb: Literal["SET", "WAIT"]
    detail: str
    expected_result: str | None = None


class VerificationStep(BaseModel):
    """A post-condition check. Always VERIFY, always has a checkable outcome."""

    verb: Literal["VERIFY"] = "VERIFY"
    detail: str
    expected_result: str


class GeneratedTestCase(BaseModel):
    """Exactly what the generation/qa agents are asked to produce. Deliberately
    excludes `testcase_id` and `remarks` — those are pipeline-assigned in
    finalize_item, never invented by the LLM.
    """

    feature: str
    variant: str | None = None
    requirement_ids: list[str]
    test_type: str | None = None  # e.g. "Normal_system", "Boundary" — feeds the Item List sheet
    objective: str
    description: str
    pre_condition: str
    input_data: str | None = None
    setup_action_steps: list[ActionStep] = Field(default_factory=list)
    verification_steps: list[VerificationStep] = Field(default_factory=list)
    mode_of_execution: ModeOfExecution
    priority: Priority
    odc_trigger: str | None = None


class TestCase(GeneratedTestCase):
    """A GeneratedTestCase plus the fields the pipeline itself owns."""

    testcase_id: str
    remarks: str | None = None


class ValidationIssue(BaseModel):
    code: str
    message: str
    severity: Literal["error", "warning"] = "error"


class ValidationResult(BaseModel):
    passed: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    semantic_feedback: str | None = None
    attempt: int = 1


class TestAspectPlan(BaseModel):
    """Structured output shape for the planning_agent call — a container
    model since with_structured_output needs a single top-level model, not a
    bare list.
    """

    aspects: list[TestAspect] = Field(default_factory=list)


class SemanticVerdict(BaseModel):
    """Structured output shape for the verification_agent's semantic check."""

    passed: bool
    feedback: str | None = None
