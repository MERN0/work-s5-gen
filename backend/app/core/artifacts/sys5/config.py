"""Sys5Config: the typed, defaulted config the rest of the pipeline works
against, built from the raw dict that sys5.py's generate() receives.

New sys5-specific keys (keyword lists, attempt limits, ID scheme, etc.) all
have defaults, so the example config in the project brief works unmodified —
a project only needs to override the ones it cares about.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.artifacts.sys5.exceptions import Sys5ConfigError

DEFAULT_SYS5_KEYWORDS: list[str] = [
    "sys5 test",
    "sys5",
    "sys test",
    "sys qt",
    "sys qualification test",
    "system qualification",
    "system qualification test",
    "sqmtc",
]

# Raw dict keys already handled explicitly in from_raw() below — excluded from
# the generic passthrough so we never pass the same field twice to Sys5Config(...).
_RAW_KEYS_HANDLED_EXPLICITLY = {
    "project_name", "username", "version", "language", "domain", "artifact",
    "input_format", "output_format", "model", "output_dir", "output_folder_path",
    "input_folder_path", "input_folder", "uploaded_files", "agent_chain",
    "req_filename", "req_sheet_name",
}


class AgentSpec(BaseModel):
    agent_name: str
    agent_version: str = "V1.0"
    prompt_content: str = ""


class Sys5Config(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    # --- standard fields (mirrors what sys5.py's fixed block already extracts) ---
    project_name: str = "default_project"
    username: str = "default_user"
    version: str = "v1.0"
    language: str = ""
    domain: str = ""
    artifact: str = ""
    input_format: str = ""
    output_format: str = "excel"
    model: str = ""
    output_dir: Path
    input_folder: Path
    uploaded_files: list[str] = Field(default_factory=list)
    agent_chain: list[AgentSpec] = Field(default_factory=list)
    req_filename: str = ""
    req_sheet_name: str = ""  # "" means: process every sheet in the workbook

    # --- sys5-specific knobs, all defaulted ---
    sys5_keywords: list[str] = Field(default_factory=lambda: list(DEFAULT_SYS5_KEYWORDS))
    keyword_match_threshold: int = 85
    fuzzy_match_threshold: int = 60
    token_match_threshold: int = 85
    max_supporting_context_items: int = 25
    max_validation_attempts: int = 2
    max_correction_attempts: int = 1
    fallback_priority: str = "P3"
    fallback_mode_of_execution: str = "Manual"
    format_profile: str = "default"
    test_case_id_pattern: str = "{project_code}_SQMTC_{n:03d}"
    project_code: str | None = None
    llm_temperature: float = 0.1
    structured_output_method: Literal["json_schema", "function_calling"] = "json_schema"
    intermediate_dir: Path | None = None

    def resolved_project_code(self) -> str:
        return self.project_code or self.project_name.upper()

    @classmethod
    def from_raw(cls, config: dict[str, Any]) -> "Sys5Config":
        output_dir = config.get("output_folder_path") or config.get("output_dir", ".")
        input_folder = config.get("input_folder_path", "")

        extra = {
            k: v
            for k, v in config.items()
            if k in cls.model_fields and k not in _RAW_KEYS_HANDLED_EXPLICITLY
        }

        try:
            return cls(
                project_name=config.get("project_name", "default_project"),
                username=config.get("username", "default_user"),
                version=config.get("version", "v1.0"),
                language=config.get("language", ""),
                domain=config.get("domain", ""),
                artifact=config.get("artifact", ""),
                input_format=config.get("input_format", ""),
                output_format=config.get("output_format", "excel"),
                model=config.get("model", ""),
                output_dir=Path(output_dir),
                input_folder=Path(input_folder) if input_folder else Path("."),
                uploaded_files=config.get("uploaded_files", []) or [],
                agent_chain=[AgentSpec(**a) for a in (config.get("agent_chain") or [])],
                req_filename=config.get("req_filename", ""),
                req_sheet_name=config.get("req_sheet_name", ""),
                **extra,
            )
        except Sys5ConfigError:
            raise
        except Exception as exc:
            raise Sys5ConfigError(f"Could not build Sys5Config from raw config: {exc}") from exc
