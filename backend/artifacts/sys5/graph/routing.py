"""Conditional-edge routing functions — pure functions of state, each
returning the literal name of the next node. This is what turns the "process
one queue item" cycle into a loop without any Python-level for-loop wrapping
subgraph.invoke() calls: LangGraph re-enters the graph at the returned node.
"""
from __future__ import annotations

from typing import Literal

from artifacts.sys5.models.state import PipelineState
from artifacts.sys5.prompts import qa_agent, verification_agent
from artifacts.sys5.prompts.registry import is_agent_selected


def route_after_prepare(state: PipelineState) -> Literal["generate_test_case", "build_outputs"]:
    return "generate_test_case" if state["queue"] else "build_outputs"


def route_after_validate(state: PipelineState) -> Literal["finalize_item", "correct_test_case"]:
    result = state["current_validation"]
    if result.passed:
        return "finalize_item"

    config = state["config"]
    if not is_agent_selected(config.agent_chain, qa_agent.AGENT_NAME):
        # qa_agent wasn't chosen for this run - never a correction loop, just finalize as-is.
        return "finalize_item"

    # Each agent's own AgentStep.max_retries (when it's in agent_chain) is the
    # operative budget; config.max_correction_attempts/max_validation_attempts
    # is only the fallback for when that agent isn't in the chain at all.
    max_correction_attempts = config.agent_max_retries(qa_agent.AGENT_NAME, config.max_correction_attempts)
    max_validation_attempts = config.agent_max_retries(verification_agent.AGENT_NAME, config.max_validation_attempts)
    can_correct = state["correction_attempts"] < max_correction_attempts
    can_reattempt = state["validation_attempts"] < max_validation_attempts
    return "correct_test_case" if (can_correct and can_reattempt) else "finalize_item"


def route_after_finalize(state: PipelineState) -> Literal["generate_test_case", "build_outputs"]:
    return "generate_test_case" if state["queue"] else "build_outputs"
