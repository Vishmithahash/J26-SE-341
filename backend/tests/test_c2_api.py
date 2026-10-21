"""Tests for C2 REST API endpoints and compatibility with existing health routes."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
    get_refund_workflow_input,
)
from app.database import Base, get_db
from app.main import app


from app.config import Settings, get_settings
from app.shared.auth.models import User, UserRole
from app.shared.auth.security import create_access_token, hash_password
from app.shared.projects.models import Project

TEST_SECRET = "c2-test-auth-secret-key-32-chars-long!!"


@pytest.fixture
def client_with_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Seed authenticated user and project
    db = testing_session_local()
    user = User(
        name="Evaluator Dasith",
        email="evaluator@test.com",
        canonical_email="evaluator@test.com",
        password_hash=hash_password("password123"),
        role=UserRole.USER,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    user_id = user.id
    project = Project(
        project_id="research_project_nexacart",
        name="NexaCart",
        owner_user_id=user_id,
        backend_base_url="http://localhost:8000",
        backend_health_url="http://localhost:8000/health",
        lifecycle="active",
    )
    db.add(project)
    db.commit()
    db.close()

    def override_get_db():
        session = testing_session_local()
        try:
            yield session
        finally:
            session.close()

    settings = Settings(auth_secret_key=TEST_SECRET)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: settings

    token, _ = create_access_token(user_id, settings)
    with TestClient(app) as test_client:
        test_client.headers["Authorization"] = f"Bearer {token}"
        yield test_client
    app.dependency_overrides.clear()


def test_existing_health_routes_remain_compatible(client_with_db: TestClient):
    # Verify root endpoint
    res_root = client_with_db.get("/")
    assert res_root.status_code == 200
    assert res_root.json() == {
        "message": "Agentic AI QA Framework API",
        "status": "running",
    }

    # Verify health endpoint
    res_health = client_with_db.get("/health")
    assert res_health.status_code == 200
    assert res_health.json() == {"status": "healthy"}

    # Verify health db endpoint
    res_health_db = client_with_db.get("/health/db")
    assert res_health_db.status_code == 200
    assert res_health_db.json() == {"status": "healthy", "database": "connected"}


def test_c2_api_build_validate_approve_lifecycle(client_with_db: TestClient):
    project_id = "research_project_nexacart"
    workflow_input = get_refund_workflow_input()

    # 1. POST /build
    res_build = client_with_db.post(
        f"/api/v1/c2/projects/{project_id}/models/build",
        json=workflow_input.model_dump(mode="json"),
    )
    assert res_build.status_code == 201, res_build.text
    data_build = res_build.json()
    model_id = data_build["model_id"]
    version = data_build["version"]
    assert data_build["lifecycle_status"] == "VALIDATED"  # auto_validate=True default

    # 2. GET /projects/{project_id}/models
    res_list = client_with_db.get(f"/api/v1/c2/projects/{project_id}/models")
    assert res_list.status_code == 200
    models_list = res_list.json()
    assert len(models_list) >= 1
    assert any(m["model_id"] == model_id for m in models_list)

    # 3. GET /projects/{project_id}/models/{model_id}/versions/{version}
    res_get = client_with_db.get(
        f"/api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}"
    )
    assert res_get.status_code == 200
    assert res_get.json()["model_id"] == model_id

    # 4. GET /validation-reports
    res_reports = client_with_db.get(
        f"/api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/validation-reports"
    )
    assert res_reports.status_code == 200
    reports = res_reports.json()
    assert len(reports) >= 1
    assert reports[0]["is_valid"] is True

    # 5. GET /readiness (before approval)
    res_readiness_pre = client_with_db.get(
        f"/api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/readiness"
    )
    assert res_readiness_pre.status_code == 200
    readiness_pre = res_readiness_pre.json()
    assert readiness_pre["readiness"] == "MODEL NOT READY"
    assert (
        "Model has not been explicitly reviewed and approved."
        in readiness_pre["reasons"]
    )

    # 6. POST /approve
    res_approve = client_with_db.post(
        f"/api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/approve",
        json={
            "reviewer_id": "evaluator_dasith",
            "review_basis": "Automated validation report and synthetic test inspection",
            "review_notes": "Accepted candidate model for testing.",
            "review_type": "SELF_REPORTED_DEVELOPMENT",
        },
    )
    assert res_approve.status_code == 200
    data_approved = res_approve.json()
    assert data_approved["lifecycle_status"] == "APPROVED"
    assert (
        "evaluator_dasith [SELF_REPORTED_DEVELOPMENT]" in data_approved["approved_by"]
    )

    # 7. GET /readiness (after approval)
    res_readiness_post = client_with_db.get(
        f"/api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/readiness"
    )
    assert res_readiness_post.status_code == 200
    readiness_post = res_readiness_post.json()
    assert readiness_post["readiness"] == "READY"
    assert readiness_post["is_approved"] is True

    # 8. POST /new-draft (create version 1.1.0)
    res_new_draft = client_with_db.post(
        f"/api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/new-draft",
        json={
            "new_version": "1.1.0",
            "description": "Next iteration of refund workflow",
        },
    )
    assert res_new_draft.status_code == 201
    new_draft_data = res_new_draft.json()
    assert new_draft_data["version"] == "1.1.0"
    assert new_draft_data["lifecycle_status"] == "DRAFT"
    assert new_draft_data["approved_by"] is None


def test_c2_api_direct_model_creation(client_with_db: TestClient):
    efsm = build_synthetic_refund_efsm()
    project_id = efsm.project_id

    # Create draft model
    res = client_with_db.post(
        f"/api/v1/c2/projects/{project_id}/models",
        json=efsm.model_dump(mode="json"),
    )
    assert res.status_code == 201
    assert res.json()["lifecycle_status"] == "DRAFT"

    # Trigger validation explicitly
    res_val = client_with_db.post(
        f"/api/v1/c2/projects/{project_id}/models/{efsm.model_id}/versions/{efsm.version}/validate"
    )
    assert res_val.status_code == 200
    assert res_val.json()["is_valid"] is True
