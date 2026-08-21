"""The six LangGraph nodes. Each is `(PipelineState) -> dict`, returning only
the partial state update it owns — see models/state.py for which fields use
LangGraph's append reducer vs. plain overwrite.
"""
from __future__ import annotations

import json
import logging

from artifacts.swe6.config import Swe6Config
from artifacts.swe6.excel.requirements_loader import load_requirements
from artifacts.swe6.excel.supporting_docs_loader import load_supporting_entities
from artifacts.swe6.llm.client import call_structured
from artifacts.swe6.matching.fuzzy_context import enrich_requirement
from artifacts.swe6.models.requirement import EnrichedRequirement
from artifacts.swe6.models.state import PipelineState, QueueItem
from artifacts.swe6.models.test_case import (
    GeneratedTestCase,
    SemanticVerdict,
    TestAspect,
    TestAspectPlan,
    TestCase,
    ValidationIssue,
    ValidationResult,
)
from artifacts.swe6.output.workbook_builder import build_workbook
from artifacts.swe6.paths import ensure_output_dir, resolve_intermediate_dir
from artifacts.swe6.prompts import generation_agent, planning_agent, qa_agent, verification_agent
from artifacts.swe6.prompts.registry import build_messages, is_agent_selected
from artifacts.swe6.validation import rules

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# 1. load_and_prepare
# --------------------------------------------------------------------------


def load_and_prepare(state: PipelineState) -> dict:
    config: Swe6Config = state["config"]
    llm = state["llm"]

    logger.info("[swe6] === load_and_prepare: reading requirements + supporting docs ===")
    requirements = load_requirements(config)
    entities = load_supporting_entities(config)

    if not requirements:
        message = (
            f"No requirements matched swe6_keywords={config.swe6_keywords!r} "
            f"for req_sheet_name={config.req_sheet_name!r} in {config.req_filename!r}. "
            "Producing a workbook with empty Test Cases/Item List sheets - "
            "check the keyword list and sheet name."
        )
        logger.warning(message)
        return {
            "enriched_requirements": {},
            "queue": [],
            "next_test_case_number": 1,
            "errors": [message],
            "run_log": [],
        }

    enriched: dict[str, EnrichedRequirement] = {}
    queue: list[QueueItem] = []
    run_log: list[dict] = []
    errors: list[str] = []

    for requirement in requirements:
        logger.info(
            "[swe6] Processing requirement %s (sheet=%r row=%d): %.120s",
            requirement.req_id, requirement.sheet_name, requirement.row_index, requirement.requirement_text,
        )
        enriched_req = enrich_requirement(requirement, entities, config)
        enriched[requirement.req_id] = enriched_req
        if enriched_req.supporting_context:
            attached = [
                f"{c.entity_type}:{c.source_sheet}#{c.row_index}(score={c.match_score:.0f})"
                for c in enriched_req.supporting_context
            ]
            logger.info(
                "[swe6] Requirement %s: attached %d supporting-context item(s): %s",
                requirement.req_id, len(attached), attached,
            )
        else:
            logger.info("[swe6] Requirement %s: no supporting-context items matched.", requirement.req_id)

        aspects = _plan_aspects(llm, enriched_req, config)
        if not aspects:
            errors.append(f"Planning produced no test aspects for {requirement.req_id}; skipped.")
            run_log.append({"requirement_id": requirement.req_id, "event": "planning_failed"})
            logger.warning("[swe6] Requirement %s: planning produced no test aspects; skipped.", requirement.req_id)
            continue

        logger.info(
            "[swe6] Requirement %s: planned %d test aspect(s): %s",
            requirement.req_id, len(aspects), [a.title for a in aspects],
        )
        for aspect in aspects:
            queue.append(QueueItem(requirement_id=requirement.req_id, aspect=aspect))

    logger.info("[swe6] === load_and_prepare complete: %d requirement(s), %d queued test-case job(s) ===", len(enriched), len(queue))
    return {
        "enriched_requirements": enriched,
        "queue": queue,
        "next_test_case_number": 1,
        "errors": errors,
        "run_log": run_log,
    }


def _plan_aspects(llm, enriched: EnrichedRequirement, config: Swe6Config) -> list[TestAspect]:
    if not is_agent_selected(config.agent_chain, planning_agent.AGENT_NAME):
        # planning_agent wasn't chosen for this run - fall back to one aspect
        # covering the whole requirement instead of skipping it entirely.
        return [TestAspect(aspect_id="A1", title="Full requirement coverage", rationale="planning_agent not selected")]

    user_content = _format_requirement_context(enriched)
    messages = build_messages(config.agent_chain, planning_agent.AGENT_NAME, user_content, config.domain)
    logger.info("[swe6] Calling %s for requirement %s", planning_agent.AGENT_NAME, enriched.requirement.req_id)
    try:
        plan = call_structured(llm, TestAspectPlan, messages, config.structured_output_method)
        return plan.aspects
    except Exception as exc:  # noqa: BLE001 - a planning failure must not crash the whole run
        logger.warning("[swe6] Planning call failed for %s: %s", enriched.requirement.req_id, exc)
        return []


# --------------------------------------------------------------------------
# 2. generate_test_case
# --------------------------------------------------------------------------


def generate_test_case(state: PipelineState) -> dict:
    config: Swe6Config = state["config"]
    llm = state["llm"]
    item = state["queue"][0]
    enriched = state["enriched_requirements"][item["requirement_id"]]

    user_content = _format_generation_context(enriched, item["aspect"])

    if not is_agent_selected(config.agent_chain, generation_agent.AGENT_NAME):
        logger.warning(
            "[swe6] %s not selected in agent_chain; cannot generate a test case for requirement %s.",
            generation_agent.AGENT_NAME, item["requirement_id"],
        )
        generated = _stub_test_case(enriched, item["aspect"], reason="generation_agent not included in agent_chain")
        return {
            "current_item": item,
            "current_test_case": generated,
            "current_validation": None,
            "validation_attempts": config.max_validation_attempts,
            "correction_attempts": config.max_correction_attempts,
        }

    messages = build_messages(config.agent_chain, generation_agent.AGENT_NAME, user_content, config.domain)

    logger.info(
        "[swe6] Calling %s for requirement %s, aspect %r (%s)",
        generation_agent.AGENT_NAME, item["requirement_id"], item["aspect"].aspect_id, item["aspect"].title,
    )
    try:
        generated = call_structured(
            llm, GeneratedTestCase, messages, config.structured_output_method
        )
        validation_attempts, correction_attempts = 0, 0
        logger.info(
            "[swe6] Generated test case draft for requirement %s, aspect %r.",
            item["requirement_id"], item["aspect"].aspect_id,
        )
    except Exception as exc:  # noqa: BLE001 - degrade to a flagged stub, never crash the run
        logger.warning("[swe6] Generation call failed for %s: %s", item["requirement_id"], exc)
        generated = _stub_test_case(enriched, item["aspect"], reason=str(exc))
        # Pre-max both budgets so the next validate routes straight to finalize_item
        # instead of spending further LLM calls on an item that's already doomed.
        validation_attempts = config.max_validation_attempts
        correction_attempts = config.max_correction_attempts

    return {
        "current_item": item,
        "current_test_case": generated,
        "current_validation": None,
        "validation_attempts": validation_attempts,
        "correction_attempts": correction_attempts,
    }


def _stub_test_case(enriched: EnrichedRequirement, aspect: TestAspect, reason: str) -> GeneratedTestCase:
    return GeneratedTestCase(
        feature=enriched.requirement.feature.feature_name or enriched.requirement.feature.feature_group or "",
        variant=None,
        requirement_ids=[enriched.requirement.req_id],
        test_type=None,
        objective=f"[GENERATION FAILED] {aspect.title}",
        description=f"Test case generation failed: {reason}",
        pre_condition="",
        input_data=None,
        setup_action_steps=[],
        verification_steps=[],
        mode_of_execution="Manual",
        priority="P3",
        odc_trigger=None,
    )


# --------------------------------------------------------------------------
# 3. validate_test_case
# --------------------------------------------------------------------------


def validate_test_case(state: PipelineState) -> dict:
    config: Swe6Config = state["config"]
    item = state["current_item"]
    test_case = state["current_test_case"]
    enriched = state["enriched_requirements"][item["requirement_id"]]
    attempt = state["validation_attempts"] + 1

    issues: list[ValidationIssue] = rules.check_test_case(test_case, enriched.allowed_signal_tokens)
    deterministic_passed = rules.passed(issues)
    logger.info(
        "[swe6] Deterministic checks for requirement %s, aspect %r (attempt %d): %s (%d issue(s))",
        item["requirement_id"], item["aspect"].aspect_id, attempt,
        "passed" if deterministic_passed else "FAILED", len(issues),
    )

    semantic_feedback = None
    overall_passed = deterministic_passed
    if deterministic_passed:
        overall_passed, semantic_feedback = _run_semantic_check(state, enriched, item, test_case, issues)

    logger.info(
        "[swe6] Validation result for requirement %s, aspect %r (attempt %d): %s",
        item["requirement_id"], item["aspect"].aspect_id, attempt, "PASSED" if overall_passed else "FAILED",
    )
    result = ValidationResult(
        passed=overall_passed, issues=issues, semantic_feedback=semantic_feedback, attempt=attempt
    )
    return {"current_validation": result, "validation_attempts": attempt}


def _run_semantic_check(state, enriched, item, test_case, issues) -> tuple[bool, str | None]:
    config: Swe6Config = state["config"]
    llm = state["llm"]

    if not is_agent_selected(config.agent_chain, verification_agent.AGENT_NAME):
        # verification_agent wasn't chosen for this run - accept whatever
        # already passed the deterministic checks, no semantic opinion asked.
        return True, None

    user_content = _format_verification_context(enriched, item["aspect"], test_case, issues)
    messages = build_messages(config.agent_chain, verification_agent.AGENT_NAME, user_content, config.domain)
    logger.info("[swe6] Calling %s for requirement %s, aspect %r", verification_agent.AGENT_NAME, item["requirement_id"], item["aspect"].aspect_id)
    try:
        verdict = call_structured(llm, SemanticVerdict, messages, config.structured_output_method)
        return verdict.passed, verdict.feedback
    except Exception as exc:  # noqa: BLE001 - no semantic opinion available; accept the deterministic pass
        logger.warning("[swe6] Verification call failed for %s: %s", item["requirement_id"], exc)
        return True, None


# --------------------------------------------------------------------------
# 4. correct_test_case
# --------------------------------------------------------------------------


def correct_test_case(state: PipelineState) -> dict:
    config: Swe6Config = state["config"]
    item = state["current_item"]
    enriched = state["enriched_requirements"][item["requirement_id"]]
    test_case = state["current_test_case"]
    validation = state["current_validation"]

    llm = state["llm"]
    user_content = _format_correction_context(enriched, item["aspect"], test_case, validation)
    messages = build_messages(config.agent_chain, qa_agent.AGENT_NAME, user_content, config.domain)

    logger.info(
        "[swe6] Calling %s for requirement %s, aspect %r (correction attempt %d)",
        qa_agent.AGENT_NAME, item["requirement_id"], item["aspect"].aspect_id, state["correction_attempts"] + 1,
    )
    try:
        corrected = call_structured(
            llm, GeneratedTestCase, messages, config.structured_output_method
        )
    except Exception as exc:  # noqa: BLE001 - keep the previous draft; validate will re-flag it
        logger.warning("[swe6] Correction call failed for %s: %s", item["requirement_id"], exc)
        corrected = test_case

    return {"current_test_case": corrected, "correction_attempts": state["correction_attempts"] + 1}


# --------------------------------------------------------------------------
# 5. finalize_item
# --------------------------------------------------------------------------


def finalize_item(state: PipelineState) -> dict:
    config: Swe6Config = state["config"]
    item = state["current_item"]
    generated = state["current_test_case"]
    validation = state["current_validation"]

    n = state["next_test_case_number"]
    testcase_id = config.test_case_id_pattern.format(project_code=config.resolved_project_code(), n=n)
    remarks = _remarks_from_validation(validation)

    final_test_case = TestCase(**generated.model_dump(), testcase_id=testcase_id, remarks=remarks)

    logger.info(
        "[swe6] Finalized requirement %s, aspect %r -> %s (passed=%s, attempts=%d)%s",
        item["requirement_id"], item["aspect"].aspect_id, testcase_id, validation.passed, validation.attempt,
        f" remarks={remarks!r}" if remarks else "",
    )

    run_log_entry = {
        "requirement_id": item["requirement_id"],
        "aspect_id": item["aspect"].aspect_id,
        "testcase_id": testcase_id,
        "passed": validation.passed,
        "attempts": validation.attempt,
    }

    return {
        "results": [final_test_case],
        "run_log": [run_log_entry],
        "queue": state["queue"][1:],
        "next_test_case_number": n + 1,
        "current_item": None,
        "current_test_case": None,
        "current_validation": None,
        "validation_attempts": 0,
        "correction_attempts": 0,
    }


def _remarks_from_validation(validation: ValidationResult) -> str | None:
    if validation.passed:
        return None
    parts = [f"{issue.severity}:{issue.code}:{issue.message}" for issue in validation.issues]
    if validation.semantic_feedback:
        parts.append(f"semantic:{validation.semantic_feedback}")
    return "; ".join(parts) if parts else None


# --------------------------------------------------------------------------
# 6. build_outputs
# --------------------------------------------------------------------------


def build_outputs(state: PipelineState) -> dict:
    config: Swe6Config = state["config"]
    logger.info("[swe6] === build_outputs: writing workbook + intermediate artifacts ===")
    ensure_output_dir(config.output_dir)
    run_dir = resolve_intermediate_dir(config.project_name, config.intermediate_dir)

    xlsx_path = build_workbook(state, config)
    _write_intermediate_artifacts(run_dir, state)

    logger.info("[swe6] swe6 workbook written to %s", xlsx_path)
    logger.info("[swe6] Intermediate artifacts (enriched requirements, per-requirement context log, run log/summary) written to %s", run_dir)
    return {"run_log": [{"event": "build_outputs", "xlsx_path": str(xlsx_path)}]}


def _write_intermediate_artifacts(run_dir, state: PipelineState) -> None:
    enriched_data = {
        req_id: enriched.model_dump(mode="json") for req_id, enriched in state["enriched_requirements"].items()
    }
    (run_dir / "enriched_requirements.json").write_text(
        json.dumps(enriched_data, indent=2, default=str), encoding="utf-8"
    )

    _write_requirements_context_log(run_dir, state)

    with (run_dir / "run_log.jsonl").open("w", encoding="utf-8") as f:
        for entry in state["run_log"]:
            f.write(json.dumps(entry, default=str) + "\n")

    summary = {
        "total_test_cases": len(state["results"]),
        "total_requirements": len(state["enriched_requirements"]),
        "errors": state["errors"],
    }
    (run_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def _write_requirements_context_log(run_dir, state: PipelineState) -> None:
    """A plain-text, human-scannable companion to enriched_requirements.json:
    for each requirement actually processed, its text and exactly which
    supporting-doc rows were attached to it (and why - the match score).
    """
    lines: list[str] = []
    for req_id, enriched in state["enriched_requirements"].items():
        req = enriched.requirement
        lines.append(f"=== {req_id} ===")
        lines.append(f"Source: {req.sheet_name!r} row {req.row_index} ({req.source_file}, matched keyword {req.matched_keyword!r})")
        lines.append(f"Requirement text: {req.requirement_text}")
        if not enriched.supporting_context:
            lines.append("Supporting context: none matched.")
        else:
            lines.append(f"Supporting context ({len(enriched.supporting_context)} item(s), highest match first):")
            for item in sorted(enriched.supporting_context, key=lambda i: i.match_score, reverse=True):
                field_str = ", ".join(f"{k}={v}" for k, v in item.fields.items())
                lines.append(
                    f"  [{item.entity_type} | {item.source_sheet}#{item.row_index} | "
                    f"score={item.match_score:.0f}] {field_str}"
                )
        lines.append("")

    (run_dir / "requirements_context.log").write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------
# Prompt context formatting — shared by the node functions above
# --------------------------------------------------------------------------


def _format_supporting_context(enriched: EnrichedRequirement) -> str:
    if not enriched.supporting_context:
        return "Supporting context: none found."
    lines = ["Supporting context (only reference values that appear here):"]
    for item in enriched.supporting_context:
        field_str = ", ".join(f"{k}={v}" for k, v in item.fields.items())
        lines.append(f"  [{item.entity_type} | {item.source_sheet}] {field_str}")
    return "\n".join(lines)


def _format_requirement_context(enriched: EnrichedRequirement) -> str:
    req = enriched.requirement
    lines = [
        f"Requirement ID: {req.req_id}",
        f"Requirement text: {req.requirement_text}",
        f"Feature: {req.feature.feature_name or req.feature.feature_group or ''}",
        "",
        _format_supporting_context(enriched),
    ]
    return "\n".join(lines)


def _format_generation_context(enriched: EnrichedRequirement, aspect: TestAspect) -> str:
    req = enriched.requirement
    lines = [
        f"Requirement ID: {req.req_id}",
        f"Requirement text: {req.requirement_text}",
        f"Feature: {req.feature.feature_name or req.feature.feature_group or ''}",
        f"Planned test aspect: {aspect.title}" + (f" ({aspect.rationale})" if aspect.rationale else ""),
        "",
        "Other columns from the requirement row (may include an authored "
        "Precondition/Test Procedure/Success Criteria block - treat as "
        "authoritative if present):",
    ]
    for key, value in req.cells.items():
        if value not in (None, "") and str(value) != req.requirement_text:
            lines.append(f"  {key}: {value}")
    lines.append("")
    lines.append(_format_supporting_context(enriched))
    return "\n".join(lines)


def _format_verification_context(enriched, aspect, test_case, issues) -> str:
    lines = [
        _format_generation_context(enriched, aspect),
        "",
        "Generated test case:",
        test_case.model_dump_json(indent=2),
    ]
    if issues:
        lines.append("Deterministic checks already passed except these warnings:")
        for issue in issues:
            lines.append(f"  {issue.severity}: {issue.message}")
    return "\n".join(lines)


def _format_correction_context(enriched, aspect, test_case, validation) -> str:
    lines = [
        _format_generation_context(enriched, aspect),
        "",
        "Previous test case (needs correction):",
        test_case.model_dump_json(indent=2),
        "",
        "Validation issues to fix:",
    ]
    for issue in validation.issues:
        lines.append(f"  {issue.severity} [{issue.code}]: {issue.message}")
    if validation.semantic_feedback:
        lines.append(f"Semantic feedback: {validation.semantic_feedback}")
    return "\n".join(lines)
