"""The single source of truth for rendering the Test Steps / Expected Results
output columns. The LLM never authors these numbered strings directly (LLMs
are unreliable at sequential counting, and asking it to keep two separate
numbered strings in lockstep compounds that risk) — it emits typed TestStep
objects, and this pure function renders both columns from them. Both the
validator and the workbook writer call this, so the two columns can never
desync from each other.
"""
from __future__ import annotations

from artifacts.swe6.models.test_case import GeneratedTestCase
from artifacts.swe6.validation.constants import TEST_END_MARKER, TEST_START_MARKER


def render(test_case: GeneratedTestCase) -> tuple[str, str]:
    """Numbering starts at 1 (`1. Test_start`), continues through every
    setup/action step and then every verification step in order, and ends at
    `<n>. End_of_test`. Expected Results only gets an entry for steps that
    have a checkable outcome (mainly VERIFY steps, occasionally an observable
    WAIT) — its numbers still line up with the matching Test Steps number.
    """
    steps = [*test_case.setup_action_steps, *test_case.verification_steps]

    step_lines = [f"1. {TEST_START_MARKER}"]
    result_lines: list[str] = []
    for offset, step in enumerate(steps):
        n = offset + 2
        step_lines.append(f"{n}. {step.verb} {step.detail}")
        if step.expected_result:
            result_lines.append(f"{n}. {step.expected_result}")
    step_lines.append(f"{len(steps) + 2}. {TEST_END_MARKER}")

    return "\n".join(step_lines), "\n".join(result_lines)
