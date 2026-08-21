"""Compiles the pipeline's non-agentic scaffold (load/prepare, finalize,
build outputs) together with whichever agentic nodes the caller's
agent_chain actually selected, in the sequence LangGraph needs to run a
per-requirement test-case loop. Tool nodes are not wired in yet - only the
four LLM agents (planning_agent, generation_agent, verification_agent,
qa_agent) are recognized; unrecognized agent_name entries are ignored. No
checkpointer - this is a synchronous one-shot batch run, not a
conversational agent, so there's nothing to resume across separate
invocations.

    START -> load_and_prepare -> [queue empty?] -> build_outputs -> END
                               -> generate_test_case -> validate_test_case
                                    |-> passed                          -> finalize_item -> [queue empty?] -> generate_test_case / build_outputs
                                    |-> failed, qa_agent selected & budget left -> correct_test_case -> validate_test_case
                                    |-> failed, qa_agent not selected or budget spent -> finalize_item (flagged)

planning_agent and verification_agent are optional sub-steps inside
load_and_prepare/validate_test_case rather than separate graph nodes (see
graph/nodes.py); whether they're selected is decided per-call from
Swe6Config.agent_chain, not from the graph's static shape. qa_agent is the
one agent that changes the graph's actual topology: the correct_test_case
node (and its edges) is only compiled in when qa_agent is present in the
agent_chain the caller passed in.
"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from artifacts.common.schema import AgentStep
from artifacts.swe6.graph import nodes, routing
from artifacts.swe6.models.state import PipelineState
from artifacts.swe6.prompts import qa_agent
from artifacts.swe6.prompts.registry import is_agent_selected


def build_graph(agent_chain: list[AgentStep] | None = None) -> Any:
    """Returns the compiled graph (a langgraph CompiledStateGraph), built
    from the given agent_chain (an empty/omitted chain falls back to every
    agent's default prompt, same as before agent_chain selection existed).
    Typed loosely here since that class's import path has moved between
    langgraph versions - callers just use .invoke() on the result."""
    agent_chain = agent_chain or []
    graph = StateGraph(PipelineState)

    graph.add_node("load_and_prepare", nodes.load_and_prepare)
    graph.add_node("generate_test_case", nodes.generate_test_case)
    graph.add_node("validate_test_case", nodes.validate_test_case)
    graph.add_node("finalize_item", nodes.finalize_item)
    graph.add_node("build_outputs", nodes.build_outputs)

    graph.add_edge(START, "load_and_prepare")
    graph.add_conditional_edges("load_and_prepare", routing.route_after_prepare)
    graph.add_edge("generate_test_case", "validate_test_case")

    if is_agent_selected(agent_chain, qa_agent.AGENT_NAME):
        graph.add_node("correct_test_case", nodes.correct_test_case)
        graph.add_edge("correct_test_case", "validate_test_case")
        graph.add_conditional_edges(
            "validate_test_case", routing.route_after_validate, ["finalize_item", "correct_test_case"]
        )
    else:
        graph.add_conditional_edges("validate_test_case", routing.route_after_validate, ["finalize_item"])

    graph.add_conditional_edges("finalize_item", routing.route_after_finalize)
    graph.add_edge("build_outputs", END)

    return graph.compile()
