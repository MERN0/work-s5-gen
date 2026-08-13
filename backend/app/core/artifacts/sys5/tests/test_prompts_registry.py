"""resolve_prompt(): agent_chain override vs. default, and domain add-on
injection (see prompts/domains.py) - both defaults and overrides should get
the domain block appended, and an unrecognized/blank domain should be a
no-op.
"""
from __future__ import annotations

from app.core.artifacts.sys5.config import AgentSpec
from app.core.artifacts.sys5.prompts import planning_agent
from app.core.artifacts.sys5.prompts.registry import resolve_prompt


def test_resolve_prompt_falls_back_to_default_with_no_domain():
    prompt = resolve_prompt([], planning_agent.AGENT_NAME)
    assert prompt == planning_agent.PLANNING_AGENT_DEFAULT_PROMPT_V1


def test_resolve_prompt_appends_known_domain_to_default():
    prompt = resolve_prompt([], planning_agent.AGENT_NAME, domain="ADAS")
    assert prompt.startswith(planning_agent.PLANNING_AGENT_DEFAULT_PROMPT_V1)
    assert "Advanced Driver Assistance Systems" in prompt


def test_resolve_prompt_appends_known_domain_to_agent_chain_override():
    agent_chain = [AgentSpec(agent_name=planning_agent.AGENT_NAME, prompt_content="Custom planning prompt.")]
    prompt = resolve_prompt(agent_chain, planning_agent.AGENT_NAME, domain="bcm")
    assert prompt.startswith("Custom planning prompt.")
    assert "Body Control Module" in prompt


def test_resolve_prompt_ignores_unrecognized_domain():
    prompt = resolve_prompt([], planning_agent.AGENT_NAME, domain="infotainment")
    assert prompt == planning_agent.PLANNING_AGENT_DEFAULT_PROMPT_V1


def test_resolve_prompt_ignores_blank_domain():
    prompt = resolve_prompt([], planning_agent.AGENT_NAME, domain="")
    assert prompt == planning_agent.PLANNING_AGENT_DEFAULT_PROMPT_V1


def test_resolve_prompt_matches_domain_alias_variants():
    for alias in ("range polygon", "Range_Polygon", "polygon", "  RANGE  "):
        prompt = resolve_prompt([], planning_agent.AGENT_NAME, domain=alias)
        assert "Range/Polygon estimation" in prompt, alias
