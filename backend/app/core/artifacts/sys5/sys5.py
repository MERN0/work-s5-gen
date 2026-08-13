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


if __name__ == "__main__":
    # Dry-runs the whole generate() flow end to end - Excel loading, keyword
    # scan, fuzzy matching, the LangGraph pipeline, workbook + intermediate
    # artifact writing, and the final zip step - against a small synthetic
    # input file, with the LLM entirely stubbed out. No OPENAI_API_KEY,
    # network access, or real project input is needed; this only checks that
    # the wiring works, not that a real model produces good test cases.
    #
    # Run with: python -m app.core.artifacts.sys5.sys5
    import shutil
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    import openpyxl

    from app.core.artifacts.sys5.logging_config import configure_logging
    from app.core.artifacts.sys5.paths import DEFAULT_RUNS_DIR
    from app.core.artifacts.sys5.models.test_case import (
        ActionStep,
        GeneratedTestCase,
        SemanticVerdict,
        TestAspect,
        TestAspectPlan,
        VerificationStep,
    )

    configure_logging()

    def _fake_build_chat_model(config):
        # Never actually invoked - call_structured is stubbed too, so no
        # ChatOpenAI instance is needed, just a placeholder to carry around.
        return object()

    def _fake_call_structured(llm, output_model, system_prompt, user_content, structured_output_method="json_schema"):
        if output_model is TestAspectPlan:
            return TestAspectPlan(
                aspects=[TestAspect(aspect_id="A1", title="Nominal activation", rationale="dry run")]
            )
        if output_model is GeneratedTestCase:
            return GeneratedTestCase(
                feature="Dummy Feature",
                requirement_ids=["1"],
                test_type="Normal_system",
                objective="Verify the switch turns the light on",
                description="Dry-run generated test case",
                pre_condition="System powered on",
                setup_action_steps=[ActionStep(verb="SET", detail="Press the switch")],
                verification_steps=[
                    VerificationStep(verb="VERIFY", detail="Light state", expected_result="Light is ON")
                ],
                mode_of_execution="Manual",
                priority="P3",
            )
        if output_model is SemanticVerdict:
            return SemanticVerdict(passed=True, feedback=None)
        raise AssertionError(f"dry run: no stub configured for output_model={output_model}")

    tmp_dir = Path(tempfile.mkdtemp(prefix="sys5_dry_run_"))
    input_dir, output_dir = tmp_dir / "input", tmp_dir / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reqs"
    ws.append(["Feature Group:", "Demo Feature"])
    ws.append(["ID", "Requirement Text", "Verification Method"])
    ws.append(["1", "When the switch is pressed, the system shall turn on the light.", "sys5 test"])
    wb.save(input_dir / "requirements.xlsx")

    dummy_config = {
        "project_name": "dry_run",
        "username": "local_dev",
        "output_folder_path": str(output_dir),
        "input_folder_path": str(input_dir),
        "req_filename": "requirements.xlsx",
        "model": "dummy-model",
        "agent_chain": [],
    }

    try:
        with patch("app.core.artifacts.sys5.pipeline.build_chat_model", _fake_build_chat_model), \
             patch("app.core.artifacts.sys5.graph.nodes.call_structured", _fake_call_structured):
            zip_path = generate(dummy_config)
        print(f"\n[sys5 dry run] OK - wrote {zip_path}")
        print(f"[sys5 dry run] intermediate artifacts (enriched_requirements.json, "
              f"requirements_context.log, run_log.jsonl, run_summary.json) under {DEFAULT_RUNS_DIR}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
