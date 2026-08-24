"""Shared request/response and agent-chain schema every process area under
backend/artifacts/<process_area>/ builds against. A process area's runner.py
takes a GenerationRequest and returns a GenerationResult; the agent_chain on
the request is a user-chosen, ordered list of AgentStep entries describing
which agents to run and (optionally) the prompt overrides for each.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class AgentStep(BaseModel):
    """One entry in a user-supplied agent_chain.

    `system_prompt`/`user_prompt` left blank (the default) mean "use this
    agent's built-in default prompt" - a process area only overrides the
    ones it wants to customize. `index` is the position of this agent within
    the chain the user picked; process areas that support reordering use it,
    others just use presence/absence of an agent_name.

    `condition_field`/`condition_routes`/`condition_default` are reserved for
    conditional graph routing (which state field to branch on, and where each
    value routes to) - not yet interpreted by swe6/sys5's fixed-topology
    graph (see graph/build.py), just carried through unchanged. `max_retries`
    is interpreted: it's this agent's own retry/attempt budget, and overrides
    the process area's pipeline-wide default whenever this agent is present
    in the chain (see Swe6Config.agent_max_retries()/Sys5Config's twin).

    `model_config`'s `from_attributes=True` lets this be built not just from
    a dict but from any object exposing the same attribute names - e.g. a
    caller's own AgentStep-shaped pydantic model - so a foreign-but-compatible
    agent_chain object still extracts correctly instead of failing validation.
    """

    model_config = {"from_attributes": True}

    index: int
    agent_name: str
    agent_description: str = ""
    system_prompt: str = ""
    user_prompt: str = ""
    condition_field: str | None = None
    condition_routes: dict[str, str] = Field(default_factory=dict)
    condition_default: str = "END"
    max_retries: int = 3


class GenerationRequest(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    username: str = "default_user"
    domain: str = ""
    project_name: str = "default_project"
    version: str = "v1.0"
    process_area: str = ""
    language: str = ""
    input_format: str = ""
    output_format: str = "excel"
    model: str = ""
    input_filenames: list[str] = Field(default_factory=list)
    agent_chain: list[AgentStep] = Field(default_factory=list)

    # Extra fields a real (non-dummy) generator needs beyond what the dummy
    # pass-through touches: where the already-uploaded input files live on
    # disk, which of them is the requirements workbook/sheet, and an optional
    # explicit output location (computed via output_dir() when blank).
    input_folder_path: str = ""
    req_filename: str = ""
    req_sheet_name: str = ""
    output_folder_path: str = ""
    artifact: str = ""


class GenerationResult(BaseModel):
    status: str
    output_zip_filename: str
    message: str = ""
