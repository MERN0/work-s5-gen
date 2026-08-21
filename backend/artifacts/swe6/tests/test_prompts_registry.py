"""resolve_system_prompt(): agent_chain override vs. default, and domain
add-on injection (see prompts/domains.py) - both defaults and overrides
should get the domain block appended, and an unrecognized/blank domain
should be a no-op. Also covers is_agent_selected() and build_messages().
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from artifacts.common.schema import AgentStep
from artifacts.swe6.prompts import planning_agent
from artifacts.swe6.prompts.registry import build_messages, is_agent_selected, resolve_system_prompt


def test_resolve_system_prompt_falls_back_to_default_with_no_domain():
    prompt = resolve_system_prompt([], planning_agent.AGENT_NAME)
    assert prompt == planning_agent.PLANNING_AGENT_DEFAULT_PROMPT_V1


def test_resolve_system_prompt_appends_known_domain_to_default():
    prompt = resolve_system_prompt([], planning_agent.AGENT_NAME, domain="ADAS")
    assert prompt.startswith(planning_agent.PLANNING_AGENT_DEFAULT_PROMPT_V1)
    assert "Advanced Driver Assistance Systems (ADAS) software" in prompt


def test_resolve_system_prompt_appends_known_domain_to_agent_chain_override():
    agent_chain = [
        AgentStep(index=0, agent_name=planning_agent.AGENT_NAME, system_prompt="Custom planning prompt.")
    ]
    prompt = resolve_system_prompt(agent_chain, planning_agent.AGENT_NAME, domain="bcm")
    assert prompt.startswith("Custom planning prompt.")
    assert "Body Control Module (BCM) software" in prompt


def test_resolve_system_prompt_ignores_unrecognized_domain():
    prompt = resolve_system_prompt([], planning_agent.AGENT_NAME, domain="infotainment")
    assert prompt == planning_agent.PLANNING_AGENT_DEFAULT_PROMPT_V1


def test_resolve_system_prompt_ignores_blank_domain():
    prompt = resolve_system_prompt([], planning_agent.AGENT_NAME, domain="")
    assert prompt == planning_agent.PLANNING_AGENT_DEFAULT_PROMPT_V1


def test_resolve_system_prompt_matches_domain_alias_variants():
    for alias in ("range polygon", "Range_Polygon", "polygon", "  RANGE  "):
        prompt = resolve_system_prompt([], planning_agent.AGENT_NAME, domain=alias)
        assert "Range/Polygon estimation" in prompt, alias


def test_is_agent_selected():
    agent_chain = [AgentStep(index=0, agent_name=planning_agent.AGENT_NAME)]
    assert is_agent_selected(agent_chain, planning_agent.AGENT_NAME)
    assert not is_agent_selected(agent_chain, "generation_agent")
    assert not is_agent_selected([], planning_agent.AGENT_NAME)


def test_build_messages_uses_default_when_chain_empty():
    messages = build_messages([], planning_agent.AGENT_NAME, "the user content")
    assert len(messages) == 2
    assert isinstance(messages[0], SystemMessage)
    assert messages[0].content == planning_agent.PLANNING_AGENT_DEFAULT_PROMPT_V1
    assert isinstance(messages[1], HumanMessage)
    assert messages[1].content == "the user content"


def test_build_messages_prepends_user_prompt_override():
    agent_chain = [AgentStep(index=0, agent_name=planning_agent.AGENT_NAME, user_prompt="Focus on boundaries.")]
    messages = build_messages(agent_chain, planning_agent.AGENT_NAME, "the user content")
    assert messages[1].content == "Focus on boundaries.\n\nthe user content"
