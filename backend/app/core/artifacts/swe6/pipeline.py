"""run_pipeline(): the one place the LLM client and the compiled graph get
built, and where the initial PipelineState is seeded. Client construction
happens here, first — a bad key/base_url/model must fail immediately, before
any Excel parsing is attempted.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.artifacts.swe6.config import Swe6Config
from app.core.artifacts.swe6.graph.build import build_graph
from app.core.artifacts.swe6.llm.client import build_chat_model
from app.core.artifacts.swe6.models.state import PipelineState


@dataclass
class PipelineResult:
    xlsx_path: str
    total_test_cases: int
    total_requirements: int
    errors: list[str]


def run_pipeline(config: Swe6Config) -> PipelineResult:
    llm = build_chat_model(config)
    graph = build_graph()

    initial_state: PipelineState = {
        "config": config,
        "llm": llm,
        "enriched_requirements": {},
        "queue": [],
        "next_test_case_number": 1,
        "current_item": None,
        "current_test_case": None,
        "current_validation": None,
        "validation_attempts": 0,
        "correction_attempts": 0,
        "results": [],
        "run_log": [],
        "errors": [],
    }

    final_state = graph.invoke(initial_state, {"recursion_limit": _recursion_limit(config)})

    xlsx_path = ""
    for entry in reversed(final_state["run_log"]):
        if entry.get("event") == "build_outputs":
            xlsx_path = entry.get("xlsx_path", "")
            break

    return PipelineResult(
        xlsx_path=xlsx_path,
        total_test_cases=len(final_state["results"]),
        total_requirements=len(final_state["enriched_requirements"]),
        errors=final_state["errors"],
    )


def _recursion_limit(config: Swe6Config) -> int:
    """Each queue item passes through generate -> validate -> [correct ->
    validate]* -> finalize. Budget generously (assume up to ~600 requirement
    rows per the input-file spec) so a large batch never hits LangGraph's
    recursion ceiling.
    """
    steps_per_item = 2 + 2 * config.max_correction_attempts
    return max(50, steps_per_item * 600 + 50)
