"""Builds the ChatOpenAI client and wraps structured-output calls with bounded
retry on transient errors only. Client construction is validated once, up
front in pipeline.py, before the graph runs at all — a bad key/URL/model
should fail immediately and loudly, not after Excel parsing has already run.
"""
from __future__ import annotations

import os
from typing import TypeVar

from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.artifacts.sys5.config import Sys5Config
from app.core.artifacts.sys5.exceptions import LlmClientError

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
)
def _invoke_structured(structured_llm, messages: list[tuple[str, str]]):
    return structured_llm.invoke(messages)


def call_structured(
    llm: ChatOpenAI,
    output_model: type[T],
    system_prompt: str,
    user_content: str,
    structured_output_method: str = "json_schema",
) -> T:
    """Ask the LLM for `output_model`-shaped structured output. Retries a
    bounded number of times on transient API errors only; callers (see
    graph/nodes.py) are expected to catch whatever escapes and degrade
    gracefully rather than let one bad call crash the whole run.
    """
    structured_llm = llm.with_structured_output(output_model, method=structured_output_method)
    messages = [("system", system_prompt), ("user", user_content)]
    return _invoke_structured(structured_llm, messages)
