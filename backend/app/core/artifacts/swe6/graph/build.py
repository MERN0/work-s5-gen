"""Wires the six nodes into one inspectable state machine. No checkpointer —
this is a synchronous one-shot batch run, not a conversational agent, so
there's nothing to resume across separate invocations.

    START -> load_and_prepare -> [queue empty?] -> build_outputs -> END
                               -> generate_test_case -> validate_test_case
                                    |-> passed                -> finalize_item -> [queue empty?] -> generate_test_case / build_outputs
                                    |-> failed, budget left   -> correct_test_case -> validate_test_case
                                    |-> failed, budget spent  -> finalize_item (flagged)
"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.core.artifacts.swe6.graph import nodes, routing
from app.core.artifacts.swe6.models.state import PipelineState


def build_graph() -> Any:
    """Returns the compiled graph (a langgraph CompiledStateGraph). Typed
    loosely here since that class's import path has moved between langgraph
    versions - callers just use .invoke() on the result."""
    graph = StateGraph(PipelineState)

    graph.add_node("load_and_prepare", nodes.load_and_prepare)
    graph.add_node("generate_test_case", nodes.generate_test_case)
    graph.add_node("validate_test_case", nodes.validate_test_case)
    graph.add_node("correct_test_case", nodes.correct_test_case)
    graph.add_node("finalize_item", nodes.finalize_item)
    graph.add_node("build_outputs", nodes.build_outputs)

    graph.add_edge(START, "load_and_prepare")
    graph.add_conditional_edges("load_and_prepare", routing.route_after_prepare)
    graph.add_edge("generate_test_case", "validate_test_case")
    graph.add_conditional_edges("validate_test_case", routing.route_after_validate)
    graph.add_edge("correct_test_case", "validate_test_case")
    graph.add_conditional_edges("finalize_item", routing.route_after_finalize)
    graph.add_edge("build_outputs", END)

    return graph.compile()
