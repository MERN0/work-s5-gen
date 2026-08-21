"""Where every agent's prompt lives, and how a project's `agent_chain`
override (if any) takes precedence over our default. This module is the
intended scrape point for later seeding a database that backs a prompt-editing
UI, so agent naming here must stay in sync with `AGENT_NAME` in each
prompts/<agent>.py file.

Also where a project's `domain` (bcm/adas/telematics/range_polygon/chassis/
powertrain - see domains.py) gets folded in: every agent's prompt gets the
matching domain add-on appended, whether that prompt is our default or an
agent_chain override, since domain grounding is useful regardless of who
authored the base prompt.
"""
from __future__ import annotations

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from artifacts.common.schema import AgentStep
from artifacts.swe6.prompts import generation_agent, planning_agent, qa_agent, verification_agent
from artifacts.swe6.prompts.domains import resolve_domain_prompt

DEFAULT_PROMPTS: dict[str, str] = {
    planning_agent.AGENT_NAME: planning_agent.PLANNING_AGENT_DEFAULT_PROMPT_V1,
    generation_agent.AGENT_NAME: generation_agent.GENERATION_AGENT_DEFAULT_PROMPT_V1,
    verification_agent.AGENT_NAME: verification_agent.VERIFICATION_AGENT_DEFAULT_PROMPT_V1,
    qa_agent.AGENT_NAME: qa_agent.QA_AGENT_DEFAULT_PROMPT_V1,
}


def is_agent_selected(agent_chain: list[AgentStep], agent_name: str) -> bool:
    """Whether the caller's agent_chain includes this agent at all - graph
    nodes use this to decide whether the agentic step runs, not just which
    prompt it runs with.
    """
    return any(step.agent_name == agent_name for step in agent_chain)


def resolve_system_prompt(agent_chain: list[AgentStep], agent_name: str, domain: str = "") -> str:
    """A non-empty `system_prompt` for `agent_name` in agent_chain overrides
    our default; otherwise (including when the agent isn't listed at all)
    we fall back to DEFAULT_PROMPTS. Either way, if `domain` (Swe6Config.domain)
    matches a known automotive domain, its add-on from domains.py is appended
    - unrecognized/blank domains are a no-op.
    """
    base = DEFAULT_PROMPTS[agent_name]
    for step in agent_chain:
        if step.agent_name == agent_name and step.system_prompt.strip():
            base = step.system_prompt
            break

    domain_addon = resolve_domain_prompt(domain)
    return f"{base}\n\n{domain_addon}" if domain_addon else base


def resolve_user_prefix(agent_chain: list[AgentStep], agent_name: str) -> str:
    """A non-empty `user_prompt` for `agent_name` in agent_chain is prepended
    to the dynamically-built, per-item user content (see graph/nodes.py's
    `_format_*_context` helpers) - blank (the default) means the dynamic
    context is the entire human message, unchanged from before agent_chain
    supported per-agent user prompts.
    """
    for step in agent_chain:
        if step.agent_name == agent_name and step.user_prompt.strip():
            return step.user_prompt
    return ""


def build_messages(
    agent_chain: list[AgentStep], agent_name: str, user_content: str, domain: str = ""
) -> list[BaseMessage]:
    """The full LangChain message pair (system + human) for one agent call -
    see llm/client.py::call_structured, which is what actually invokes them.
    """
    system_prompt = resolve_system_prompt(agent_chain, agent_name, domain)
    user_prefix = resolve_user_prefix(agent_chain, agent_name)
    human_content = f"{user_prefix}\n\n{user_content}" if user_prefix else user_content
    return [SystemMessage(content=system_prompt), HumanMessage(content=human_content)]
