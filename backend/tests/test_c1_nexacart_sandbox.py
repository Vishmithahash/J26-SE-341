"""C1 sandbox isolation, defect-lab persistence and controlled defects (hermetic).

Real database provisioning, builds and live reruns are exercised by the live defect-lab check
(README section 5C.6). These tests use temporary copies of NexaCart's real tool files when the
NexaCart tree is available (``NEXACART_SOURCE_ROOT``), otherwise those cases are skipped.
"""

import json
import os
import sys
from pathlib import Path

import pytest

from app.components.c1_tool_call_correctness.contracts.configuration import (
    CodeMapping,
    ToolDefinition,
    ToolParameterSchema,
)
from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CandidateCodeLocation,
    CaseDiagnosisRecord,
    CauseCategory,
    DiagnosisStatus,
)
from app.components.c1_tool_call_correctness.services import (
    nexacart_correction,
    nexacart_defect_lab,
    nexacart_sandbox,
)
from app.components.c1_tool_call_correctness.services.nexacart_correction import (
    CONTROLLED_DEFECTS,
    TypeScriptMappingPatchGenerator,
    seed_defect,
)
from app.components.c1_tool_call_correctness.services.sandbox_interface import (
    apply_unified_diff_to_workspace,
)
from app.components.c1_tool_call_correctness.services.source_inspector import (
    SourceInspector,
)
from app.config import get_settings

SCHEMAS = {
    "refund_order": ["orderNumber", "amount", "reason"],
    "cancel_order": ["orderNumber", "reason"],
    "add_to_cart": ["productId", "quantity", "expectedCartVersion"],
    "get_order": ["orderNumber"],
}


def _nexacart_root() -> Path | None:
    root = os.environ.get("NEXACART_SOURCE_ROOT") or get_settings().nexacart_source_root
    candidates = [root, "D:/Research Project/E-Commerce-Platform/backend"]
    for c in candidates:
        if c and (Path(c) / "src/agent-tools/tools").is_dir():
            return Path(c)
    return None


def test_isolated_environment_drops_qa_secrets_and_nexacart_keys(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        'DATABASE_URL="postgresql://u:p@localhost:5432/nxc_c1_sbx_x"\nJWT_SECRET="s"\nPORT="3000"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("DATABASE_URL", "postgresql://qa@localhost/qa_db")
    monkeypatch.setenv("NEXACART_QA_ADMIN_PASSWORD", "x")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("PORT", "8000")
    monkeypatch.setenv("C1_HARMLESS", "kept")
    env = nexacart_sandbox.isolated_environment(tmp_path, {"PORT": "3205"})
    assert (
        "DATABASE_URL" not in env
    )  # NexaCart reads its sandbox URL from the copy's .env
    assert "NEXACART_QA_ADMIN_PASSWORD" not in env
    assert "GEMINI_API_KEY" not in env
    assert env["PORT"] == "3205"
    assert env["C1_HARMLESS"] == "kept"


def test_env_file_update_and_database_naming(tmp_path):
    (tmp_path / ".env").write_text(
        '# comment\nDATABASE_URL="postgresql://u:p@localhost:5432/nexacart?schema=public"\nNODE_ENV=development\n',
        encoding="utf-8",
    )
    nexacart_sandbox.set_env_value(
        tmp_path, "DATABASE_URL", "postgresql://u:p@localhost:5432/nxc_c1_sbx_a"
    )
    values = nexacart_sandbox.read_env_file(tmp_path)
    assert values["DATABASE_URL"].endswith("/nxc_c1_sbx_a")
    assert values["NODE_ENV"] == "development"
    workspace = tmp_path / "verify-Ab12-CD"
    name = nexacart_sandbox._database_name(workspace)
    assert name.startswith(nexacart_sandbox.SANDBOX_DB_PREFIX)
    assert name == name.lower() and len(name) <= 63


def test_drop_database_only_touches_sandbox_databases(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        'DATABASE_URL="postgresql://u:p@localhost:5432/nexacart"\n', encoding="utf-8"
    )
    (tmp_path / nexacart_sandbox.MARKER_FILE).write_text(
        json.dumps({"database": "nexacart"}), encoding="utf-8"
    )
    calls = []

    class _Psycopg:
        Error = Exception

        @staticmethod
        def connect(*a, **k):
            calls.append(a)
            raise AssertionError("must not connect for a non-sandbox database")

    monkeypatch.setitem(sys.modules, "psycopg", _Psycopg)
    nexacart_sandbox.drop_database(tmp_path)  # 'nexacart' lacks the sandbox prefix
    assert calls == []


def test_dead_process_is_not_alive():
    assert nexacart_sandbox.pid_alive(None) is False
    assert nexacart_sandbox.pid_alive(4_000_000_000 // 1000 * 999) is False


def _lab_root(tmp_path, monkeypatch, registry: dict) -> None:
    monkeypatch.setattr(nexacart_correction, "WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(nexacart_defect_lab, "_LABS", {})
    monkeypatch.setattr(nexacart_defect_lab, "_LOADED", False)
    (tmp_path / "labs.json").write_text(json.dumps(registry), encoding="utf-8")


def test_lab_interrupted_while_building_fails_cleanly_after_restart(
    tmp_path, monkeypatch
):
    workspace = tmp_path / "lab-x"
    workspace.mkdir()
    _lab_root(
        tmp_path,
        monkeypatch,
        {
            "p1": {
                "project_id": "p1",
                "defect_id": "refund_order_number_mapping",
                "status": "BUILDING",
                "workspace": str(workspace),
            }
        },
    )
    lab = nexacart_defect_lab.get_lab("p1")
    assert (
        lab.status == "FAILED"
        and "restarted while this lab was building" in lab.message
    )
    assert not workspace.exists()
    saved = json.loads((tmp_path / "labs.json").read_text(encoding="utf-8"))
    assert saved["p1"]["status"] == "FAILED"


def test_running_lab_is_readopted_when_its_process_is_healthy(tmp_path, monkeypatch):
    workspace = tmp_path / "lab-y"
    workspace.mkdir()
    _lab_root(
        tmp_path,
        monkeypatch,
        {
            "p2": {
                "project_id": "p2",
                "defect_id": "get_order_number_mapping",
                "status": "RUNNING",
                "workspace": str(workspace),
                "port": 3207,
                "base_url": "http://localhost:3207/api/v1",
                "pid": 4242,
            }
        },
    )
    monkeypatch.setattr(
        nexacart_correction.NexaCartInstance, "is_alive", lambda self: True
    )
    monkeypatch.setattr(
        nexacart_correction.NexaCartInstance, "is_healthy", lambda self: True
    )
    lab = nexacart_defect_lab.get_lab("p2")
    assert lab.status == "RUNNING" and lab.pid == 4242 and lab.recovered_at
    assert "Re-adopted" in lab.message


def test_running_lab_with_dead_process_is_restarted_from_its_build(
    tmp_path, monkeypatch
):
    workspace = tmp_path / "lab-z"
    (workspace / "dist/src").mkdir(parents=True)
    (workspace / "dist/src/main.js").write_text("", encoding="utf-8")
    _lab_root(
        tmp_path,
        monkeypatch,
        {
            "p3": {
                "project_id": "p3",
                "defect_id": "cancel_order_reason_mapping",
                "status": "RUNNING",
                "workspace": str(workspace),
                "port": 3208,
                "base_url": "http://localhost:3208/api/v1",
                "pid": 1,
            }
        },
    )
    started = []
    monkeypatch.setattr(
        nexacart_correction.NexaCartInstance, "is_alive", lambda self: False
    )
    monkeypatch.setattr(nexacart_correction.NexaCartInstance, "stop", lambda self: None)
    monkeypatch.setattr(
        nexacart_correction.NexaCartInstance,
        "start",
        lambda self: (started.append(self.port), setattr(self, "pid", 777)),
    )
    monkeypatch.setattr(
        nexacart_correction.NexaCartInstance,
        "wait_healthy",
        lambda self, timeout=0: True,
    )
    lab = nexacart_defect_lab.get_lab("p3")
    assert started == [3208]
    assert lab.status == "RUNNING" and lab.pid == 777 and "Restarted" in lab.message


@pytest.mark.parametrize("defect_id", sorted(CONTROLLED_DEFECTS))
def test_each_controlled_defect_is_seeded_located_and_repaired(defect_id, tmp_path):
    root = _nexacart_root()
    if root is None:
        pytest.skip("NexaCart source tree not available")
    defect = CONTROLLED_DEFECTS[defect_id]
    target = tmp_path / defect.file_path
    target.parent.mkdir(parents=True)
    original = (root / defect.file_path).read_text(encoding="utf-8")
    target.write_text(original, encoding="utf-8")

    diff = seed_defect(tmp_path, defect)
    assert defect.replace in diff
    inspected = SourceInspector(tmp_path).inspect_function(defect.file_path, "execute")
    schema = SCHEMAS[defect.tool_name]
    assert set(schema) - set(
        inspected.parameters
    )  # a schema argument is no longer read

    tool = ToolDefinition(
        name=defect.tool_name,
        description=defect.tool_name,
        parameters_schema=ToolParameterSchema(
            properties={k: {"type": "string"} for k in schema}, required=schema
        ),
        code_mapping=CodeMapping(file_path=defect.file_path, function_name="execute"),
    )
    diagnosis = CaseDiagnosisRecord(
        diagnosis_id="d",
        project_id="p",
        run_id="r",
        case_execution_id="c",
        case_id="k",
        attempt_number=1,
        requirement_version="v1",
        evaluator_version="v1",
        explanation_version="v1",
        status=DiagnosisStatus.COMPLETED,
        cause_category=CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT,
        explanation_summary="",
        candidate_code_locations=[
            CandidateCodeLocation(
                file_path=defect.file_path,
                function_name="execute",
                line_start=inspected.line_start,
                line_end=inspected.line_end,
                ranking_score=1,
                ranking_criteria="test",
            )
        ],
    )
    patch = TypeScriptMappingPatchGenerator().generate_candidate_patch(
        diagnosis, diagnosis.candidate_code_locations[0], tmp_path, tool
    )
    assert patch is not None, defect_id
    ok, err = apply_unified_diff_to_workspace(tmp_path, patch.diff_content)
    assert ok, err
    assert target.read_text(encoding="utf-8") == original
