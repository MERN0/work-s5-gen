"""Deterministic (non-LLM) checks run on every generated test case before it's
ever shown to the LLM verification agent. Cheap, fast, and catches the
mechanical failure modes (empty test case, nothing to verify, an unrecognized
token) without spending an LLM call.

The token whitelist check is intentionally a *warning*, not a hard error:
string-based matching of identifier-like tokens against the attached
supporting-doc context is defense-in-depth, not a proof of correctness — it
has false positives (a legitimate token phrased slightly differently than the
source sheet) and false negatives (a hallucinated token that happens to look
like an existing one). Treat `unrecognized_token` warnings as a strong hint
for the qa_agent correction pass and for a human reviewer, not an automatic
rejection.
"""
from __future__ import annotations

import re

from artifacts.swe6.models.test_case import GeneratedTestCase, ValidationIssue

_IDENTIFIER_LIKE = re.compile(r"\b[A-Za-z][A-Za-z0-9_]*\b")


def _looks_like_identifier(token: str) -> bool:
    """Heuristic: plain English words aren't identifiers; signal/command names
    like `FanARespRPM` or `VBattSply_NormOperUMax` are — they contain a digit,
    an underscore, or a camelCase transition.
    """
    if len(token) < 3:
        return False
    has_digit = any(c.isdigit() for c in token)
    has_underscore = "_" in token
    has_camel_case = any(a.islower() and b.isupper() for a, b in zip(token, token[1:]))
    return has_digit or has_underscore or has_camel_case


def check_test_case(test_case: GeneratedTestCase, allowed_tokens: set[str]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    all_steps = [*test_case.setup_action_steps, *test_case.verification_steps]

    if not all_steps:
        issues.append(
            ValidationIssue(code="no_steps", message="Test case has no steps at all.", severity="error")
        )

    if not any(s.expected_result for s in test_case.verification_steps):
        issues.append(
            ValidationIssue(
                code="no_checkable_outcome",
                message="No verification step has an expected result to check.",
                severity="error",
            )
        )

    allowed_lower = {t.lower() for t in allowed_tokens}
    for step in all_steps:
        for token in _IDENTIFIER_LIKE.findall(step.detail):
            if not _looks_like_identifier(token):
                continue
            if token.lower() not in allowed_lower:
                issues.append(
                    ValidationIssue(
                        code="unrecognized_token",
                        message=(
                            f"Step references '{token}', which isn't in the requirement's "
                            "attached supporting-doc context."
                        ),
                        severity="warning",
                    )
                )

    return issues


def passed(issues: list[ValidationIssue]) -> bool:
    return not any(issue.severity == "error" for issue in issues)
