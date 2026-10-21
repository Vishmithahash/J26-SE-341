"""Focused integration and authorization tests for Component 2 endpoints.

Verifies:
1. Unauthenticated C2 requests are rejected (401).
2. Inactive user requests are rejected (401).
3. A User can access and manage their own project's C2 records (200/201).
4. A different User cannot list, retrieve, validate, approve, or modify those records (404 Not Found).
5. Admin access follows the existing shared platform policy (can access any project's C2 records).
6. A model identifier from another project cannot bypass project scoping (404 Not Found).
7. Unknown roles are denied (403 Forbidden).
"""

from typing import Any, Generator
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.database import Base, get_db
from app.main import app
from app.shared.auth.dependencies import require_active_user
from app.shared.auth.models import User, UserRole, normalize_email
from app.shared.auth.security import create_access_token, hash_password
from app.shared.projects.models import Project, ProjectLifecycle
from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
)

TEST_AUTH_SECRET = "c2-test-auth-secret-key-32-chars-long!!"

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_c2_test_db() -> Generator[None, None, None]:
    """Create all tables before each test and drop them afterwards."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_settings():
        return Settings(auth_secret_key=TEST_AUTH_SECRET)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def make_user(
    db: Session,
    name: str,
    email: str,
    role: UserRole = UserRole.USER,
    is_active: bool = True,
) -> User:
    canonical = normalize_email(email)
    user = User(
        name=name,
        email=email,
        canonical_email=canonical,
        password_hash=hash_password("password123"),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_project(
    db: Session,
    project_id: str,
    name: str,
    owner_user_id: int,
    lifecycle: str = ProjectLifecycle.ACTIVE.value,
) -> Project:
    project = Project(
        project_id=project_id,
        name=name,
        owner_user_id=owner_user_id,
        backend_base_url="http://localhost:8000",
        backend_health_url="http://localhost:8000/health",
        lifecycle=lifecycle,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def auth_headers(user: User) -> dict[str, str]:
    settings = Settings(auth_secret_key=TEST_AUTH_SECRET)
    token, _ = create_access_token(user.id, settings)
    return {"Authorization": f"Bearer {token}"}


def make_efsm_payload(project_id: str) -> dict[str, Any]:
    efsm = build_synthetic_refund_efsm()
    payload = efsm.model_dump(mode="json")
    payload["project_id"] = project_id
    return payload


# ===========================================================================
# 1. Unauthenticated and Inactive Requests
# ===========================================================================

def test_unauthenticated_c2_requests_rejected(test_client: TestClient, db_session: Session):
    """Verify that unauthenticated requests to C2 endpoints return 401."""
    owner = make_user(db_session, "Alice", "alice@example.com")
    project = make_project(db_session, "proj-alice", "Alice Project", owner.id)

    # 1. Build candidate
    res1 = test_client.post(f"/api/v1/c2/projects/{project.project_id}/models/build", json={})
    assert res1.status_code == 401
    assert "Not authenticated." in res1.json()["detail"]

    # 2. List models
    res2 = test_client.get(f"/api/v1/c2/projects/{project.project_id}/models")
    assert res2.status_code == 401

    # 3. Model validation
    res3 = test_client.post(
        f"/api/v1/c2/projects/{project.project_id}/models/any-model/versions/1.0.0/validate"
    )
    assert res3.status_code == 401

    # 4. Model approve
    res4 = test_client.post(
        f"/api/v1/c2/projects/{project.project_id}/models/any-model/versions/1.0.0/approve",
        json={"reviewer_id": "test", "review_basis": "spec"},
    )
    assert res4.status_code == 401


def test_inactive_user_rejected(test_client: TestClient, db_session: Session):
    """Verify that deactivated user accounts are rejected with 401."""
    inactive_user = make_user(
        db_session, "Deactivated", "deactivated@example.com", is_active=False
    )
    project = make_project(db_session, "proj-inactive", "Inactive Project", inactive_user.id)

    res = test_client.get(
        f"/api/v1/c2/projects/{project.project_id}/models",
        headers=auth_headers(inactive_user),
    )
    assert res.status_code == 401
    assert "inactive" in res.json()["detail"].lower()


# ===========================================================================
# 2. Owner Access (User accesses their own project)
# ===========================================================================

def test_user_can_access_own_project_c2_records(test_client: TestClient, db_session: Session):
    """Verify that a USER can build, read, validate, approve, and draft models in their own project."""
    owner = make_user(db_session, "Bob Owner", "bob@example.com")
    project = make_project(db_session, "proj-bob", "Bob's App", owner.id)
    headers = auth_headers(owner)

    # 1. Direct model creation
    payload = make_efsm_payload(project.project_id)
    res_create = test_client.post(
        f"/api/v1/c2/projects/{project.project_id}/models",
        json=payload,
        headers=headers,
    )
    assert res_create.status_code == 201
    created_model = res_create.json()
    model_id = created_model["model_id"]
    version = created_model["version"]
    assert created_model["lifecycle_status"] == "DRAFT"

    # 2. List models
    res_list = test_client.get(
        f"/api/v1/c2/projects/{project.project_id}/models",
        headers=headers,
    )
    assert res_list.status_code == 200
    assert len(res_list.json()) == 1

    # 3. Get single model
    res_get = test_client.get(
        f"/api/v1/c2/projects/{project.project_id}/models/{model_id}/versions/{version}",
        headers=headers,
    )
    assert res_get.status_code == 200
    assert res_get.json()["model_id"] == model_id

    # 4. Validate model
    res_val = test_client.post(
        f"/api/v1/c2/projects/{project.project_id}/models/{model_id}/versions/{version}/validate",
        headers=headers,
    )
    assert res_val.status_code == 200
    assert res_val.json()["is_valid"] is True

    # 5. Approve model
    res_appr = test_client.post(
        f"/api/v1/c2/projects/{project.project_id}/models/{model_id}/versions/{version}/approve",
        json={
            "reviewer_id": "bob_reviewer",
            "review_basis": "Automated EFSM validation check",
            "review_notes": "All transitions verified.",
            "review_type": "SELF_REPORTED_DEVELOPMENT",
        },
        headers=headers,
    )
    assert res_appr.status_code == 200
    assert res_appr.json()["lifecycle_status"] == "APPROVED"

    # 6. Create new draft
    res_draft = test_client.post(
        f"/api/v1/c2/projects/{project.project_id}/models/{model_id}/versions/{version}/new-draft",
        json={"new_version": "1.1.0", "description": "Iterated draft"},
        headers=headers,
    )
    assert res_draft.status_code == 201
    assert res_draft.json()["version"] == "1.1.0"
    assert res_draft.json()["lifecycle_status"] == "DRAFT"


# ===========================================================================
# 3. Isolation & Non-Owner Rejection (Different User denied)
# ===========================================================================

def test_different_user_cannot_access_or_modify_c2_records(
    test_client: TestClient, db_session: Session
):
    """Verify that User B cannot list, retrieve, validate, approve or modify User A's C2 records."""
    user_a = make_user(db_session, "Alice", "alice@test.com")
    user_b = make_user(db_session, "Mallory", "mallory@test.com")

    project_a = make_project(db_session, "proj-alice", "Alice Private Project", user_a.id)
    headers_a = auth_headers(user_a)
    headers_b = auth_headers(user_b)

    # User A creates a model
    payload_a = make_efsm_payload(project_a.project_id)
    res_create = test_client.post(
        f"/api/v1/c2/projects/{project_a.project_id}/models",
        json=payload_a,
        headers=headers_a,
    )
    assert res_create.status_code == 201
    model_id = res_create.json()["model_id"]
    version = res_create.json()["version"]

    # User B attempts to access project A's C2 resources
    # Following the existing shared Projects access convention, inaccessible projects return 404
    # 1. List models
    res_b_list = test_client.get(
        f"/api/v1/c2/projects/{project_a.project_id}/models",
        headers=headers_b,
    )
    assert res_b_list.status_code == 404
    assert "Project not found" in res_b_list.json()["detail"]

    # 2. Get model
    res_b_get = test_client.get(
        f"/api/v1/c2/projects/{project_a.project_id}/models/{model_id}/versions/{version}",
        headers=headers_b,
    )
    assert res_b_get.status_code == 404

    # 3. Build model
    res_b_build = test_client.post(
        f"/api/v1/c2/projects/{project_a.project_id}/models/build",
        json={"project_id": project_a.project_id, "workflow_name": "Hack"},
        headers=headers_b,
    )
    assert res_b_build.status_code == 404

    # 4. Validate model
    res_b_val = test_client.post(
        f"/api/v1/c2/projects/{project_a.project_id}/models/{model_id}/versions/{version}/validate",
        headers=headers_b,
    )
    assert res_b_val.status_code == 404

    # 5. Approve model
    res_b_appr = test_client.post(
        f"/api/v1/c2/projects/{project_a.project_id}/models/{model_id}/versions/{version}/approve",
        json={"reviewer_id": "mallory", "review_basis": "Exploit"},
        headers=headers_b,
    )
    assert res_b_appr.status_code == 404

    # 6. Create new draft
    res_b_draft = test_client.post(
        f"/api/v1/c2/projects/{project_a.project_id}/models/{model_id}/versions/{version}/new-draft",
        json={"new_version": "2.0.0"},
        headers=headers_b,
    )
    assert res_b_draft.status_code == 404


# ===========================================================================
# 4. Administrative Access Policy
# ===========================================================================

def test_admin_can_access_any_project_c2_records(test_client: TestClient, db_session: Session):
    """Verify that an ADMIN user follows the existing shared policy and can access any project's C2 records."""
    owner = make_user(db_session, "Regular User", "regular@test.com", role=UserRole.USER)
    admin = make_user(db_session, "Platform Admin", "admin@test.com", role=UserRole.ADMIN)

    project = make_project(db_session, "proj-regular", "Regular App", owner.id)
    headers_owner = auth_headers(owner)
    headers_admin = auth_headers(admin)

    # Owner creates model
    payload = make_efsm_payload(project.project_id)
    res_create = test_client.post(
        f"/api/v1/c2/projects/{project.project_id}/models",
        json=payload,
        headers=headers_owner,
    )
    assert res_create.status_code == 201
    model_id = res_create.json()["model_id"]
    version = res_create.json()["version"]

    # Admin lists models in the user's project
    res_admin_list = test_client.get(
        f"/api/v1/c2/projects/{project.project_id}/models",
        headers=headers_admin,
    )
    assert res_admin_list.status_code == 200
    assert len(res_admin_list.json()) == 1

    # Admin validates model
    res_admin_val = test_client.post(
        f"/api/v1/c2/projects/{project.project_id}/models/{model_id}/versions/{version}/validate",
        headers=headers_admin,
    )
    assert res_admin_val.status_code == 200
    assert res_admin_val.json()["is_valid"] is True

    # Admin approves model
    res_admin_appr = test_client.post(
        f"/api/v1/c2/projects/{project.project_id}/models/{model_id}/versions/{version}/approve",
        json={
            "reviewer_id": "admin_auditor",
            "review_basis": "Platform compliance audit",
            "review_notes": "Validated and approved by admin.",
            "review_type": "ADMIN_AUDIT",
        },
        headers=headers_admin,
    )
    assert res_admin_appr.status_code == 200
    assert res_admin_appr.json()["lifecycle_status"] == "APPROVED"


# ===========================================================================
# 5. Project Scoping Protection (Model ID from another project cannot bypass)
# ===========================================================================

def test_model_from_another_project_cannot_bypass_scoping(
    test_client: TestClient, db_session: Session
):
    """Verify that referencing a model_id belonging to project B under project A is rejected with 404."""
    user = make_user(db_session, "Multi-Project User", "multi@test.com")
    project_a = make_project(db_session, "proj-a", "Project Alpha", user.id)
    project_b = make_project(db_session, "proj-b", "Project Beta", user.id)
    headers = auth_headers(user)

    # Create model in project B
    payload_b = make_efsm_payload(project_b.project_id)
    res_b = test_client.post(
        f"/api/v1/c2/projects/{project_b.project_id}/models",
        json=payload_b,
        headers=headers,
    )
    assert res_b.status_code == 201
    model_b_id = res_b.json()["model_id"]
    version_b = res_b.json()["version"]

    # Now attempt to read, validate, approve, or draft model B under project A
    # 1. Get model
    res_cross_get = test_client.get(
        f"/api/v1/c2/projects/{project_a.project_id}/models/{model_b_id}/versions/{version_b}",
        headers=headers,
    )
    assert res_cross_get.status_code == 404

    # 2. Validate
    res_cross_val = test_client.post(
        f"/api/v1/c2/projects/{project_a.project_id}/models/{model_b_id}/versions/{version_b}/validate",
        headers=headers,
    )
    assert res_cross_val.status_code == 404

    # 3. Approve
    res_cross_appr = test_client.post(
        f"/api/v1/c2/projects/{project_a.project_id}/models/{model_b_id}/versions/{version_b}/approve",
        json={"reviewer_id": "sneaky", "review_basis": "bypass"},
        headers=headers,
    )
    assert res_cross_appr.status_code == 404

    # 4. New draft
    res_cross_draft = test_client.post(
        f"/api/v1/c2/projects/{project_a.project_id}/models/{model_b_id}/versions/{version_b}/new-draft",
        json={"new_version": "2.0.0"},
        headers=headers,
    )
    assert res_cross_draft.status_code == 404


# ===========================================================================
# 6. Unknown Role Denial
# ===========================================================================

def test_unknown_role_is_denied(test_client: TestClient, db_session: Session):
    """Verify that accounts with an unknown role are denied with 403 Forbidden."""
    owner = make_user(db_session, "Owner", "owner_for_role@test.com")
    project = make_project(db_session, "proj-role-test", "Role Test", owner.id)

    # Mock require_active_user to return a user object with an invalid role
    mock_user = MagicMock()
    mock_user.id = 999
    mock_user.is_active = True
    mock_user.role = "UNKNOWN_ROLE"

    app.dependency_overrides[require_active_user] = lambda: mock_user
    try:
        res = test_client.get(f"/api/v1/c2/projects/{project.project_id}/models")
        assert res.status_code == 403
        assert "Access denied for account role" in res.json()["detail"]
    finally:
        del app.dependency_overrides[require_active_user]
