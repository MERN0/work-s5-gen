from pathlib import Path

from artifacts.sys5.config import Sys5Config

EXAMPLE_CONFIG = {
    "project_name": "tmhc_demo",
    "username": "test@tataelxsi.co.in",
    "version": "V1.0",
    "domain": "automotive",
    "artifact": "SYS5",
    "model": "llm-1-gpt-oss-120b",
    "input_folder_path": "_input_dir",
    "output_folder_path": "_output_dir",
    "output_dir": "_output_dir",
    "uploaded_files": [],
    "agent_chain": [
        {"index": 0, "agent_name": "generation_agent", "agent_description": "", "system_prompt": "", "user_prompt": ""},
        {"index": 1, "agent_name": "verification_agent", "agent_description": "", "system_prompt": "", "user_prompt": ""},
        {"index": 2, "agent_name": "qa_agent", "agent_description": "", "system_prompt": "", "user_prompt": ""},
    ],
    "req_filename": "TE_TMHC_HILS Development & Testing_System Requirements.xlsx",
    "# Sheet-name filter - MUST match an existing sheet in the input files.": "",
    "req_sheet_name": "005",
}


def test_from_raw_parses_the_example_config_unmodified():
    config = Sys5Config.from_raw(EXAMPLE_CONFIG)

    assert config.project_name == "tmhc_demo"
    assert config.model == "llm-1-gpt-oss-120b"
    assert config.output_dir == Path("_output_dir")
    assert config.input_folder == Path("_input_dir")
    assert config.req_sheet_name == "005"
    assert [a.agent_name for a in config.agent_chain] == [
        "generation_agent",
        "verification_agent",
        "qa_agent",
    ]
    # sys5-specific defaults are present even though the raw config never mentions them
    assert config.max_validation_attempts == 2
    assert config.max_correction_attempts == 1
    assert "system qualification" in config.sys5_keywords


def test_from_raw_honors_overrides_for_new_keys():
    raw = dict(EXAMPLE_CONFIG)
    raw["max_correction_attempts"] = 3
    raw["sys5_keywords"] = ["custom keyword"]

    config = Sys5Config.from_raw(raw)

    assert config.max_correction_attempts == 3
    assert config.sys5_keywords == ["custom keyword"]


def test_resolved_project_code_defaults_to_uppercase_project_name():
    config = Sys5Config.from_raw(EXAMPLE_CONFIG)
    assert config.resolved_project_code() == "TMHC_DEMO"


def test_resolved_project_code_honors_explicit_override():
    raw = dict(EXAMPLE_CONFIG)
    raw["project_code"] = "TMHC"
    config = Sys5Config.from_raw(raw)
    assert config.resolved_project_code() == "TMHC"
