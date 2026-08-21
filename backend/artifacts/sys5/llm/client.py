"""Builds the ChatOpenAI client and wraps structured-output calls with bounded
retry on transient errors only. Client construction is validated once, up
front in pipeline.py, before the graph runs at all — a bad key/URL/model
should fail immediately and loudly, not after Excel parsing has already run.
"""
from __future__ import annotations

import logging
import os
from typing import TypeVar

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
from pydantic import BaseModel
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from artifacts.sys5.config import Sys5Config
from artifacts.sys5.exceptions import LlmClientError

# Picks up OPENAI_API_KEY / SYS5_LLM_API_BASE from a local .env file (see
# .env.example) without ever overriding a value already set in the real
# environment - safe to call unconditionally at import time.
load_dotenv()

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# On-prem gateway address confirmed by the project owner; env var names are
# placeholders and can be renamed to match the real deployment in one place.
DEFAULT_API_BASE = "http://10.1.2.186:4000"

_TRANSIENT_ERRORS = (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError)


def build_chat_model(config: Sys5Config) -> ChatOpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise LlmClientError("OPENAI_API_KEY is not set in the environment.")
    api_base = os.environ.get("SYS5_LLM_API_BASE", DEFAULT_API_BASE)

    logger.info("[sys5] Building LLM client: model=%r api_base=%r temperature=%s", config.model, api_base, config.llm_temperature)
    try:
        return ChatOpenAI(
            model=config.model,
            openai_api_key=api_key,
            openai_api_base=api_base,
            temperature=config.llm_temperature,
        )
    except Exception as exc:
        raise LlmClientError(f"Could not construct ChatOpenAI client: {exc}") from exc


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(_TRANSIENT_ERRORS),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _invoke_structured(structured_llm, messages: list[BaseMessage]):
    return structured_llm.invoke(messages)


def call_structured(
    llm: ChatOpenAI,
    output_model: type[T],
    messages: list[BaseMessage],
    structured_output_method: str = "json_schema",
) -> T:
    """Ask the LLM for `output_model`-shaped structured output, given a
    LangChain SystemMessage/HumanMessage pair (see prompts/registry.py's
    build_messages()). Retries a bounded number of times on transient API
    errors only; callers (see graph/nodes.py) are expected to catch whatever
    escapes and degrade gracefully rather than let one bad call crash the
    whole run.
    """
    logger.debug(
        "[sys5] LLM request: output_model=%s method=%s (%d message(s))",
        output_model.__name__, structured_output_method, len(messages),
    )
    structured_llm = llm.with_structured_output(output_model, method=structured_output_method)
    result = _invoke_structured(structured_llm, messages)
    logger.debug("[sys5] LLM response received for output_model=%s", output_model.__name__)
    return result
