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


from app.shared.auth.dependencies import require_active_user
from app.shared.auth.models import User, UserRole
from app.shared.projects.models import Project


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
    admin_user = User(
        id=1,
        name="Admin",
        email="admin@test.com",
        canonical_email="admin@test.com",
        password_hash="fake",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.merge(admin_user)
    for pid in ["proj_gen_api_test", "proj_limits_test", "proj_alpha_gen", "proj_beta_gen"]:
        db_session.merge(
            Project(
                project_id=pid,
                owner_user_id=1,
                name=pid,
                backend_base_url="http://localhost:8000",
                backend_health_url="http://localhost:8000/health",
            )
        )
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_active_user] = lambda: admin_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()



def test_generation_job_lifecycle_and_api_endpoints(client):
    project_id = "proj_gen_api_test"

    # 1. Setup base project config
    cfg_payload = get_nexacart_refund_example_config().model_dump()
    cfg_resp = client.post(
        f"/api/v1/projects/{project_id}/c1/configs", json=cfg_payload
    )
    assert cfg_resp.status_code == 201
    config_id = cfg_resp.json()["id"]

    # 2. Trigger candidate generation job
    gen_payload = {
        "config_version": 1,
        "max_candidates": 10,
        "max_accepted_cases": 5,
        "seed": 12345,
        "auto_promote_suite": False,
    }
    job_resp = client.post(
        f"/api/v1/projects/{project_id}/c1/generation/jobs",
        json=gen_payload,
    )
    assert job_resp.status_code == 201, job_resp.text
    job_data = job_resp.json()
    job_id = job_data["job_id"]
    assert job_data["status"] == "COMPLETED"
    assert job_data["summary"]["total_generated"] >= 5
    assert job_data["summary"]["selected_count"] >= 1
    assert len(job_data["content_hash"]) == 64

    # 3. Retrieve generation job status
    get_job = client.get(f"/api/v1/projects/{project_id}/c1/generation/jobs/{job_id}")
    assert get_job.status_code == 200
    assert get_job.json()["job_id"] == job_id

    # 4. Inspect candidates and validation issues
    cand_resp = client.get(
        f"/api/v1/projects/{project_id}/c1/generation/jobs/{job_id}/candidates"
    )
    assert cand_resp.status_code == 200
    candidates = cand_resp.json()
    assert len(candidates) >= 5
    # Inspect candidate fields
    first_c = candidates[0]
    assert "case_id" in first_c
    assert "fixture_plan" in first_c
    assert "canonical_hash" in first_c
    assert "expected_tool_calls" in first_c

    # 5. Retrieve isolated agent-facing tasks
    agent_tasks_resp = client.get(
        f"/api/v1/projects/{project_id}/c1/generation/jobs/{job_id}/agent-tasks"
    )
    assert agent_tasks_resp.status_code == 200
    agent_tasks = agent_tasks_resp.json()
    assert len(agent_tasks) >= 1
    for task in agent_tasks:
        assert "task_prompt" in task
        assert "context_inputs" in task
        assert "permitted_tools" in task
        # Verify strict isolation from QA expectations
        assert "expected_tool_calls" not in task
        assert "argument_constraints" not in task
        assert "expected_value" not in task

    # 6. Promote candidates to accepted suite
    promote_payload = {
        "suite_id": "suite_nexacart_gen_v1",
        "name": "NexaCart Generated Acceptance Suite",
    }
    promote_resp = client.post(
        f"/api/v1/projects/{project_id}/c1/generation/jobs/{job_id}/promote-suite",
        json=promote_payload,
    )
    assert promote_resp.status_code == 201
    suite_data = promote_resp.json()
    assert suite_data["suite_id"] == "suite_nexacart_gen_v1"
    assert suite_data["is_immutable"] is True

    # Verify referenced config was frozen
    check_cfg = client.get(f"/api/v1/projects/{project_id}/c1/configs/{config_id}")
    assert check_cfg.json()["is_immutable"] is True

    # 7. Retrieve isolated agent view for a specific case in the accepted suite
    suite_cases_first_id = candidates[0]["case_id"]
    agent_view_resp = client.get(
        f"/api/v1/projects/{project_id}/c1/suites/suite_nexacart_gen_v1/cases/{suite_cases_first_id}/agent-view"
    )
    assert agent_view_resp.status_code == 200
    agent_case = agent_view_resp.json()
    assert agent_case["case_id"] == suite_cases_first_id
    assert "expected_tool_calls" not in agent_case


def test_generation_request_limit_and_reference_validation(client):
    project_id = "proj_limits_test"
    cfg_payload = get_nexacart_refund_example_config().model_dump()
    client.post(f"/api/v1/projects/{project_id}/c1/configs", json=cfg_payload)

    # 1. max_accepted_cases > max_candidates is rejected
    bad_limits = {
        "config_version": 1,
        "max_candidates": 5,
        "max_accepted_cases": 10,
    }
    resp = client.post(
        f"/api/v1/projects/{project_id}/c1/generation/jobs", json=bad_limits
    )
    assert resp.status_code == 422
    assert "max_accepted_cases" in resp.json()["detail"]

    # 2. Unresolved requirement references rejected
    bad_reqs = {
        "config_version": 1,
        "requirement_ids": ["REQ-NONEXISTENT-999"],
    }
    resp = client.post(
        f"/api/v1/projects/{project_id}/c1/generation/jobs", json=bad_reqs
    )
    assert resp.status_code == 422
    assert "Unresolved requirement references" in resp.json()["detail"]

    # 3. Unresolved tool references rejected
    bad_tools = {
        "config_version": 1,
        "tool_names": ["ghost_tool_xyz"],
    }
    resp = client.post(
        f"/api/v1/projects/{project_id}/c1/generation/jobs", json=bad_tools
    )
    assert resp.status_code == 422
    assert "Unresolved tool references" in resp.json()["detail"]


def test_generation_project_security_and_isolation(client):
    proj_a = "proj_alpha_gen"
    proj_b = "proj_beta_gen"

    cfg_payload = get_nexacart_refund_example_config().model_dump()
    client.post(f"/api/v1/projects/{proj_a}/c1/configs", json=cfg_payload)

    gen_payload = {"config_version": 1}
    job_resp = client.post(
        f"/api/v1/projects/{proj_a}/c1/generation/jobs", json=gen_payload
    )
    job_id = job_resp.json()["job_id"]

    # 1. Header mismatch rejected with 403 Forbidden
    forbid_resp = client.get(
        f"/api/v1/projects/{proj_a}/c1/generation/jobs/{job_id}",
        headers={"X-Project-ID": proj_b},
    )
    assert forbid_resp.status_code == 403
    assert "Cross-project access denied" in forbid_resp.json()["detail"]

    # 2. Cross-project query for proj_a job under proj_b route returns 404
    cross_resp = client.get(f"/api/v1/projects/{proj_b}/c1/generation/jobs/{job_id}")
    assert cross_resp.status_code == 404
