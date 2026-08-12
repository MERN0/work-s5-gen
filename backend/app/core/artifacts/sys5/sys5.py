import logging
import os
import zipfile
from datetime import datetime

from app.core.artifacts.sys5.config import Sys5Config
from app.core.artifacts.sys5.exceptions import Sys5Error
from app.core.artifacts.sys5.pipeline import run_pipeline

logger = logging.getLogger(__name__)

def generate(config: dict) -> str:
    """
    SYS5 (System Qualification Test Cases) generator.

    Reads SYS2 system requirements plus project-specific supporting docs
    (signals, commands, communication matrix, configurable parameters, test
    patterns) from input_folder_path, and generates a formatted SYS5 test
    case workbook via a LangGraph pipeline (per-requirement planning,
    generation, validation, and correction). Returns the output zip path.
    Accepts the standardized SME6-compatible config payload; agent_chain
    prompt overrides are honored per agent (see prompts/registry.py).
    """
#####Donot change this part in code
    project_name = config.get("project_name", "default_project")
    username = config.get("username", "default_user")
    version = config.get("version", "v1.0")
    language = config.get("language", "")
    domain = config.get("domain", "")
    artifact = config.get("artifact", "")
    input_format = config.get("input_format", "")
    output_format = config.get("output_format", "excel")
    model = config.get("model", "")
    output_dir = config.get("output_folder_path") or config.get("output_dir", ".")
    input_folder = config.get("input_folder_path", "")
    uploaded_files = config.get("uploaded_files", [])
    agent_chain = config.get("agent_chain", []) or []
######

    logger.info(
        f"[sys5] generate() called: project={project_name}, username={username}, version={version}, "
        f"language={language}, domain={domain}, artifact={artifact}, input_format={input_format}, output_format={output_format}, model={model}, "
        f"project_name, username, version, language, domain, artifact, "
        f"input_format, output_format, model,"
    )

    if agent_chain:
        agent_names = [a.get("agent_name", "?") for a in agent_chain]
        logger.info(
            f"[sys5] Received agent_chain with {len(agent_chain)} agent(s): {agent_names} "
            f"(prompts NOT extracted - dummy generator),"
        )
    else:
        logger.info("[sys5] No agent_chain provided.")

    os.makedirs(output_dir, exist_ok=True)

    # Step 1: run the real SYS5 pipeline. It builds a validated Sys5Config
    # from the raw dict, runs the LangGraph generation pipeline, and writes
    # ONLY the final formatted .xlsx into output_dir - all intermediate JSON/
    # logs go under this package's own _runs/ directory instead, since Step 2
    # below zips everything it finds sitting in output_dir.
    try:
        sys5_config = Sys5Config.from_raw(config)
        result = run_pipeline(sys5_config)
        logger.info(
            "[sys5] pipeline complete: %d test case(s) from %d requirement(s), xlsx=%s",
            result.total_test_cases,
            result.total_requirements,
            result.xlsx_path,
        )
        for error in result.errors:
            logger.warning("[sys5] %s", error)
    except Sys5Error:
        logger.exception("[sys5] pipeline failed")
        raise

#####Donot change this part in code
    # Step 2: Zip all files from output_dir
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(output_dir, f"sys5_{project_name}_{timestamp}.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename in os.listdir(output_dir):
            file_path = os.path.join(output_dir, filename)
            if os.path.isfile(file_path) and not filename.endswith(".zip"):
                zf.write(file_path, arcname=filename)

    return zip_path
#########
