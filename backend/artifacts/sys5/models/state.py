"""LangGraph state schema. A TypedDict (not a BaseModel) so nodes can return
partial updates cheaply, and so `results`/`run_log`/`errors` can use LangGraph's
`Annotated[list[X], operator.add]` reducer — a node just returns the one new
item and LangGraph appends it, no read-modify-write of the whole list.
`queue` deliberately has no reducer: it shrinks explicitly in finalize_item.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from artifacts.sys5.config import Sys5Config
from artifacts.sys5.models.requirement import EnrichedRequirement
from artifacts.sys5.models.test_case import GeneratedTestCase, TestAspect, TestCase, ValidationResult


class QueueItem(TypedDict):
    requirement_id: str
    aspect: TestAspect


class PipelineState(TypedDict):
    config: Sys5Config
    # Typed loosely (not as ChatOpenAI) so this module doesn't need to import
    # langchain-openai just to describe the state shape. Built once in
    # pipeline.py, before the graph runs, and reused by every node - node
    # functions must never construct their own client.
    llm: Any
    enriched_requirements: dict[str, EnrichedRequirement]
    queue: list[QueueItem]
    next_test_case_number: int

    current_item: QueueItem | None
    # Note: current_test_case is a GeneratedTestCase (no testcase_id yet) —
    # the id is only assigned once, in finalize_item, when it's wrapped into
    # a full TestCase and appended to `results`.
    current_test_case: GeneratedTestCase | None
    current_validation: ValidationResult | None
    validation_attempts: int
    correction_attempts: int

    results: Annotated[list[TestCase], operator.add]
    run_log: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[str], operator.add]
