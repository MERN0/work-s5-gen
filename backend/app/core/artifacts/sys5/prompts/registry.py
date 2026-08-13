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

from app.core.artifacts.sys5.config import AgentSpec
from app.core.artifacts.sys5.prompts import generation_agent, planning_agent, qa_agent, verification_agent
from app.core.artifacts.sys5.prompts.domains import resolve_domain_prompt

DEFAULT_PROMPTS: dict[str, str] = {
    planning_agent.AGENT_NAME: planning_agent.PLANNING_AGENT_DEFAULT_PROMPT_V1,
    generation_agent.AGENT_NAME: generation_agent.GENERATION_AGENT_DEFAULT_PROMPT_V1,
    verification_agent.AGENT_NAME: verification_agent.VERIFICATION_AGENT_DEFAULT_PROMPT_V1,
    qa_agent.AGENT_NAME: qa_agent.QA_AGENT_DEFAULT_PROMPT_V1,
}


def resolve_prompt(agent_chain: list[AgentSpec], agent_name: str, domain: str = "") -> str:
    """A non-empty `prompt_content` for `agent_name` in agent_chain overrides
    our default; otherwise (including when the agent isn't listed at all,
    e.g. planning_agent in the example config) we fall back to DEFAULT_PROMPTS.
    Either way, if `domain` (Sys5Config.domain) matches a known automotive
    domain, its add-on from domains.py is appended - unrecognized/blank
    domains are a no-op.
    """
    base = DEFAULT_PROMPTS[agent_name]
    for spec in agent_chain:
        if spec.agent_name == agent_name and spec.prompt_content.strip():
            base = spec.prompt_content
            break

    domain_addon = resolve_domain_prompt(domain)
    return f"{base}\n\n{domain_addon}" if domain_addon else base
