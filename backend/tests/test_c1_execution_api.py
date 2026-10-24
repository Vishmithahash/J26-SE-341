import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c1_tool_call_correctness.examples import (
    get_nexacart_refund_example_config,
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


from tests.auth_test_fixtures import AutoSeedingTestClient, seed_test_admin
from app.shared.auth.dependencies import require_active_user


@pytest.fixture
def client(db_session):
    admin_user = seed_test_admin(db_session)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_active_user] = lambda: admin_user
    with AutoSeedingTestClient(db_session, admin_user) as test_client:
        yield test_client
    app.dependency_overrides.clear()



def _setup_promoted_suite(client: TestClient, project_id: str) -> str:
    """Helper to configure project, generate candidates, and promote an accepted suite."""
    cfg_payload = get_nexacart_refund_example_config().model_dump()
    cfg_resp = client.post(
        f"/api/v1/projects/{project_id}/c1/configs", json=cfg_payload
    )
    assert cfg_resp.status_code == 201

    gen_payload = {
        "config_version": 1,
        "max_candidates": 10,
        "max_accepted_cases": 5,
        "seed": 999,
        "auto_promote_suite": True,
    }
    gen_resp = client.post(
        f"/api/v1/projects/{project_id}/c1/generation/jobs",
        json=gen_payload,
    )
    assert gen_resp.status_code == 201
    job_id = gen_resp.json()["job_id"]
    promote_payload = {
        "suite_id": "suite_v1",
        "name": "NexaCart Accepted Suite v1",
    }
    promote_resp = client.post(
        f"/api/v1/projects/{project_id}/c1/generation/jobs/{job_id}/promote-suite",
        json=promote_payload,
    )
    assert promote_resp.status_code == 201
    return "suite_v1"


def test_full_execution_run_lifecycle_and_apis(client):
    """Verifies run start, retrieval, check results, evidence pointers, and agent isolation."""
    project_id = "proj_exec_test_01"
    suite_id = _setup_promoted_suite(client, project_id)

    # 1. Start execution run
    exec_req = {
        "suite_id": suite_id,
        "suite_version": 1,
        "idempotency_key": "idemp_run_01",
        "deadline_seconds": 30,
        "evaluator_version": "c1-evaluator-v1.0",
        "adapter_override": "AUTO",
    }
    run_resp = client.post(
        f"/api/v1/projects/{project_id}/c1/runs",
        json=exec_req,
        headers={"X-Project-ID": project_id},
    )
    assert run_resp.status_code == 201, run_resp.text
    run_data = run_resp.json()
    run_id = run_data["summary"]["run_id"]
    assert run_data["summary"]["status"] == "COMPLETED"
    assert run_data["summary"]["total_cases"] >= 1
    assert len(run_data["case_executions"]) >= 1

    # 2. Idempotency check: duplicate submission must return identical run without extra executions
    dup_resp = client.post(
        f"/api/v1/projects/{project_id}/c1/runs",
        json=exec_req,
        headers={"X-Project-ID": project_id},
    )
    assert dup_resp.status_code == 201
    assert dup_resp.json()["summary"]["run_id"] == run_id

    # 3. Retrieve run by ID
    get_resp = client.get(
        f"/api/v1/projects/{project_id}/c1/runs/{run_id}",
        headers={"X-Project-ID": project_id},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["summary"]["run_id"] == run_id

    # 4. Inspect Case Execution Detail & verify Agent Isolation
    first_case = run_data["case_executions"][0]
    case_id = first_case["case_id"]

    case_resp = client.get(
        f"/api/v1/projects/{project_id}/c1/runs/{run_id}/cases/{case_id}",
        headers={"X-Project-ID": project_id},
    )
    assert case_resp.status_code == 200
    case_detail = case_resp.json()
    assert case_detail["case_id"] == case_id
    assert case_detail["attempt_number"] == 1
    assert case_detail["verdict"] in ("PASS", "FAIL", "INCONCLUSIVE")
    assert len(case_detail["check_results"]) >= 1

    # Strict isolation verification: agent_task_sent must NOT contain QA expectations or answers
    agent_task = case_detail["agent_task_sent"]
    assert "task_prompt" in agent_task
    assert "context_inputs" in agent_task
    assert "permitted_tools" in agent_task
    assert "expected_tool_calls" not in agent_task
    assert "argument_constraints" not in agent_task

    # 5. Rerun creating attempt 2
    rerun_resp = client.post(
        f"/api/v1/projects/{project_id}/c1/runs/{run_id}/rerun",
        headers={"X-Project-ID": project_id},
    )
    assert rerun_resp.status_code == 200
    rerun_data = rerun_resp.json()
    assert rerun_data["summary"]["status"] == "COMPLETED"

    # Verify attempt 2 exists for the case
    case_rerun_resp = client.get(
        f"/api/v1/projects/{project_id}/c1/runs/{run_id}/cases/{case_id}",
        headers={"X-Project-ID": project_id},
    )
    assert case_rerun_resp.status_code == 200
    assert case_rerun_resp.json()["attempt_number"] == 2


def test_list_runs_filtering_and_cancellation(client):
    """Verifies listing runs with verdict filter and run cancellation."""
    project_id = "proj_filter_cancel"
    suite_id = _setup_promoted_suite(client, project_id)

    # Start run with wrong tool override
    exec_req = {
        "suite_id": suite_id,
        "suite_version": 1,
        "adapter_override": "WRONG_TOOL",
    }
    client.post(
        f"/api/v1/projects/{project_id}/c1/runs",
        json=exec_req,
        headers={"X-Project-ID": project_id},
    )

    # Start another run with auto correct
    exec_req_2 = {
        "suite_id": suite_id,
        "suite_version": 1,
        "adapter_override": "AUTO",
    }
    resp_2 = client.post(
        f"/api/v1/projects/{project_id}/c1/runs",
        json=exec_req_2,
        headers={"X-Project-ID": project_id},
    )
    run_2_id = resp_2.json()["summary"]["run_id"]

    # List all runs
    list_all = client.get(
        f"/api/v1/projects/{project_id}/c1/runs",
        headers={"X-Project-ID": project_id},
    )
    assert list_all.status_code == 200
    assert len(list_all.json()) >= 2

    # Filter by PASS
    list_pass = client.get(
        f"/api/v1/projects/{project_id}/c1/runs?verdict=PASS",
        headers={"X-Project-ID": project_id},
    )
    assert list_pass.status_code == 200
    assert all(r["passed_cases"] > 0 for r in list_pass.json())

    # Cancel endpoint
    cancel_resp = client.post(
        f"/api/v1/projects/{project_id}/c1/runs/{run_2_id}/cancel",
        headers={"X-Project-ID": project_id},
    )
    assert cancel_resp.status_code == 200


def test_cross_project_authorization_and_adapter_readiness(client):
    """Verifies authorization header boundaries and live adapter readiness diagnostic endpoint."""
    project_id = "proj_auth_test"
    _setup_promoted_suite(client, project_id)

    # 1. Cross-project header mismatch -> 403 Forbidden
    auth_fail_resp = client.get(
        f"/api/v1/projects/{project_id}/c1/runs",
        headers={"X-Project-ID": "proj_intruder"},
    )
    assert auth_fail_resp.status_code == 403

    # 2. Check adapter readiness endpoint
    readiness_resp = client.get(
        f"/api/v1/projects/{project_id}/c1/adapter/readiness",
        headers={"X-Project-ID": project_id},
    )
    assert readiness_resp.status_code == 200
    readiness_data = readiness_resp.json()
    assert readiness_data["project_id"] == project_id
    assert "is_ready" in readiness_data
    assert "diagnostics" in readiness_data
    assert (
        "unsupported" in readiness_data["diagnostics"].lower()
        or "mock" in readiness_data["diagnostics"].lower()
        or "ready" in readiness_data["diagnostics"].lower()
        or "protocol" in readiness_data["diagnostics"].lower()
    )
