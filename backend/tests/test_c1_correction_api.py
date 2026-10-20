import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c1_tool_call_correctness.contracts.correction import (
    CorrectionStatus,
    ReviewDecision,
)
from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CauseCategory,
    DiagnosisStatus,
)
from app.components.c1_tool_call_correctness.models.persistence import (
    C1CaseDiagnosisModel,
    C1CaseExecutionModel,
    C1ExecutionRunModel,
    C1ProjectConfigModel,
    C1SuiteVersionModel,
)
from app.database import Base, get_db
from app.main import app


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_app_repo(tmp_path):
    """Creates a temporary repository on disk with the application code."""
    app_dir = tmp_path / "app"
    app_dir.mkdir(parents=True)
    refund_file = app_dir / "refund_service.py"
    refund_file.write_text(
        "def process_refund(order_id: str, refund_amount: float):\n"
        "    return {'status': 'processed', 'amount': refund_amount}\n",
        encoding="utf-8",
    )
    return tmp_path


def _setup_seeded_defect(
    db_session, project_id: str, repo_path: str
) -> tuple[str, str, str]:
    """Sets up a database state with a project config, execution run, case execution, and diagnosis."""
    # Config
    cfg = C1ProjectConfigModel(
        id="cfg_001",
        project_id=project_id,
        version=1,
        agent_connection_ref="conn_test",
        tools=[
            {
                "name": "process_refund",
                "description": "Process refund",
                "parameters_schema": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "amount": {"type": "number"},
                    },
                    "required": ["order_id", "amount"],
                },
                "code_mapping": {
                    "file_path": "app/refund_service.py",
                    "function_name": "process_refund",
                },
            }
        ],
        requirements=[],
    )
    db_session.add(cfg)

    # Suite
    suite = C1SuiteVersionModel(
        id="suite_001",
        project_id=project_id,
        suite_id="suite_s1",
        version=1,
        name="Suite 1",
        config_id="cfg_001",
    )
    db_session.add(suite)

    # Execution run
    run = C1ExecutionRunModel(
        id="run_001",
        project_id=project_id,
        suite_id="suite_s1",
        suite_version=1,
        suite_version_id="suite_001",
        config_id="cfg_001",
        status="COMPLETED",
        effective_config={},
        summary={},
    )
    db_session.add(run)

    # Case execution
    case_exec = C1CaseExecutionModel(
        id="exec_001",
        run_id="run_001",
        case_id="case_refund_1",
        attempt_number=1,
        session_id="sess_1",
        readiness_status="CONFIGURED",
        execution_status="EXECUTED",
        verdict="FAIL",
        trace_completeness="COMPLETE",
        resolved_expectations=[
            {
                "tool_name": "process_refund",
                "argument_constraints": [
                    {
                        "argument_name": "amount",
                        "operator": "EQUALS",
                        "expected_value": 50.0,
                    }
                ],
            }
        ],
        captured_events=[
            {
                "event_id": "ev_01",
                "call_index": 0,
                "tool_name": "process_refund",
                "arguments": {"order_id": "ORD-1"},
                "status": "SUCCESS",
            }
        ],
        check_results=[
            {
                "check_id": "chk_1",
                "rule_name": "ARGUMENT_PRESENCE_CHECK",
                "target_tool": "process_refund",
                "target_argument": "amount",
                "verdict": "FAIL",
                "reason_code": "ARGUMENT_MISSING",
                "explanation": "Argument amount missing",
            }
        ],
    )
    db_session.add(case_exec)

    # Corroborating Diagnosis
    diag = C1CaseDiagnosisModel(
        id="diag_defect_001",
        project_id=project_id,
        run_id="run_001",
        case_execution_id="exec_001",
        case_id="case_refund_1",
        attempt_number=1,
        cause_category=CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT.value,
        explanation_summary="Argument mapping mismatch detected in process_refund",
        candidate_code_locations=[
            {
                "file_path": "app/refund_service.py",
                "function_name": "process_refund",
                "line_start": 1,
                "line_end": 2,
                "ranking_score": 1,
                "ranking_criteria": "Parameter mismatch",
                "supporting_evidence": ["chk_1"],
                "uncertainties": [],
            }
        ],
        status=DiagnosisStatus.COMPLETED.value,
        check_explanations=[],
        evidence_refs=["chk_1"],
    )
    db_session.add(diag)
    db_session.commit()

    return "run_001", "case_refund_1", "diag_defect_001"


def test_correction_api_full_lifecycle(client, db_session, mock_app_repo):
    """End-to-end test of correction request, sandbox verification, diff inspection, and review."""
    project_id = "proj_corr_api"
    _run_id, _case_id, diag_id = _setup_seeded_defect(
        db_session, project_id, str(mock_app_repo)
    )

    # 1. Request correction attempt
    attempt_payload = {
        "diagnosis_id": diag_id,
        "source_root_path": str(mock_app_repo),
        "allowed_paths": ["app/refund_service.py"],
        "idempotency_key": "corr_key_001",
    }
    resp = client.post(
        f"/api/v1/projects/{project_id}/c1/corrections/attempts",
        json=attempt_payload,
    )
    assert resp.status_code == 200
    corr_data = resp.json()

    corr_id = corr_data["correction_id"]
    assert corr_data["project_id"] == project_id
    assert corr_data["diagnosis_id"] == diag_id
    assert corr_data["status"] == CorrectionStatus.VERIFIED.value
    assert corr_data["is_verified"] is True
    assert corr_data["candidate_patch"] is not None

    patch_hash = corr_data["candidate_patch"]["patch_hash"]
    assert len(patch_hash) == 64

    # 2. Idempotency test: repeated request with same key returns identical record
    idemp_resp = client.post(
        f"/api/v1/projects/{project_id}/c1/corrections/attempts",
        json=attempt_payload,
    )
    assert idemp_resp.status_code == 200
    assert idemp_resp.json()["correction_id"] == corr_id

    # 3. GET /corrections/{correction_id}
    get_resp = client.get(f"/api/v1/projects/{project_id}/c1/corrections/{corr_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["correction_id"] == corr_id
    assert len(get_resp.json()["verification_results"]) == 6

    # 4. GET /corrections/{correction_id}/diff
    diff_resp = client.get(
        f"/api/v1/projects/{project_id}/c1/corrections/{corr_id}/diff"
    )
    assert diff_resp.status_code == 200
    diff_data = diff_resp.json()
    assert diff_data["correction_id"] == corr_id
    assert diff_data["patch_hash"] == patch_hash
    assert "process_refund" in diff_data["diff_content"]
    assert diff_data["is_verified"] is True

    # 5. Review: Rejection on mismatched patch hash
    stale_review_payload = {
        "decision": ReviewDecision.ACCEPTED.value,
        "reviewer": "danuka",
        "target_patch_hash": "wrong_hash_9999",
        "reason": "Approved",
    }
    stale_resp = client.post(
        f"/api/v1/projects/{project_id}/c1/corrections/{corr_id}/review",
        json=stale_review_payload,
    )
    assert stale_resp.status_code == 400
    assert "Review target mismatch" in stale_resp.json()["detail"]

    # 6. Review: Successful acceptance with matching patch hash
    valid_review_payload = {
        "decision": ReviewDecision.ACCEPTED.value,
        "reviewer": "danuka",
        "target_patch_hash": patch_hash,
        "reason": "Verified fix for refund_amount parameter mapping defect.",
    }
    review_resp = client.post(
        f"/api/v1/projects/{project_id}/c1/corrections/{corr_id}/review",
        json=valid_review_payload,
    )
    assert review_resp.status_code == 200
    reviewed_data = review_resp.json()
    assert reviewed_data["review"]["decision"] == ReviewDecision.ACCEPTED.value
    assert reviewed_data["review"]["reviewer"] == "danuka"
    assert reviewed_data["review"]["audit_ref"] is not None

    # 7. GET /corrections (list history)
    list_resp = client.get(f"/api/v1/projects/{project_id}/c1/corrections")
    assert list_resp.status_code == 200
    history = list_resp.json()
    assert len(history) >= 1
    item = next(h for h in history if h["correction_id"] == corr_id)
    assert item["is_verified"] is True
    assert item["review_decision"] == ReviewDecision.ACCEPTED.value
