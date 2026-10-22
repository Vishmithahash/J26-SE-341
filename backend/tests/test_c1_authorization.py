"""Comprehensive authentication and authorization tests for Component 1 (C1) routes.

Verifies:
1. Unauthenticated requests to C1 routes return 401 Unauthorized.
2. Inactive account requests return 401 Unauthorized.
3. Unsupported / unknown account roles return 403 Forbidden.
4. Caller-supplied X-Project-ID mismatch returns 403 Forbidden.
5. Matching or omitted X-Project-ID succeeds for authorized caller.
6. Non-existent project returns 404 Not Found (safe policy, prevents enumeration).
7. Access to another user's project by a standard USER returns 404 Not Found (safe policy).
8. Project owner (USER) can access and configure their own project (201 Created / 200 OK).
9. ADMIN can access any valid project regardless of owner.
"""

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c1_tool_call_correctness.examples import (
    get_nexacart_refund_example_config,
)
from app.config import Settings, get_settings
from app.database import Base, get_db
from app.main import app
from app.shared.auth.dependencies import require_active_user
from app.shared.auth.models import User, UserRole, normalize_email
from app.shared.auth.security import create_access_token, hash_password
from app.shared.projects.models import (
    Project,
    ProjectConnectionState,
    ProjectLifecycle,
)

TEST_AUTH_SECRET = "c1-test-auth-secret-key-32-chars-long!!"

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_c1_test_db() -> Generator[None, None, None]:
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
        connection_state=ProjectConnectionState.NOT_CHECKED.value,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def auth_headers(user: User) -> dict[str, str]:
    settings = Settings(auth_secret_key=TEST_AUTH_SECRET)
    token, _ = create_access_token(user.id, settings)
    return {"Authorization": f"Bearer {token}"}


def make_c1_payload() -> dict[str, Any]:
    return get_nexacart_refund_example_config().model_dump(mode="json")


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


def test_unauthenticated_c1_request_returns_401(
    test_client: TestClient, db_session: Session
):
    user = make_user(db_session, "Alice", "alice@example.com")
    make_project(db_session, "proj-alpha", "Alpha", user.id)

    # No Authorization header
    resp = test_client.get("/api/v1/projects/proj-alpha/c1/configs")
    assert resp.status_code == 401


def test_inactive_user_c1_request_returns_401(
    test_client: TestClient, db_session: Session
):
    user = make_user(
        db_session, "Inactive User", "inactive@example.com", is_active=False
    )
    make_project(db_session, "proj-alpha", "Alpha", user.id)

    headers = auth_headers(user)
    resp = test_client.get("/api/v1/projects/proj-alpha/c1/configs", headers=headers)
    assert resp.status_code == 401


def test_invalid_role_c1_request_returns_403(
    test_client: TestClient, db_session: Session
):
    user = make_user(db_session, "Alice", "alice@example.com")
    make_project(db_session, "proj-alpha", "Alpha", user.id)

    mock_user = User(
        id=999,
        name="Bogus Role User",
        email="bogus@example.com",
        canonical_email="bogus@example.com",
        password_hash="fake",
        role="UNSUPPORTED_ROLE",  # type: ignore
        is_active=True,
    )
    app.dependency_overrides[require_active_user] = lambda: mock_user

    try:
        resp = test_client.get("/api/v1/projects/proj-alpha/c1/configs")
        assert resp.status_code == 403
        assert "Forbidden: role not authorized" in resp.json()["detail"]
    finally:
        del app.dependency_overrides[require_active_user]


def test_cross_project_header_mismatch_returns_403(
    test_client: TestClient, db_session: Session
):
    user = make_user(db_session, "Alice", "alice@example.com")
    make_project(db_session, "proj-alpha", "Alpha", user.id)

    headers = auth_headers(user)
    headers["X-Project-ID"] = "proj-other"  # Mismatch with route proj-alpha

    resp = test_client.get("/api/v1/projects/proj-alpha/c1/configs", headers=headers)
    assert resp.status_code == 403
    assert "Cross-project access denied" in resp.json()["detail"]


def test_matching_project_header_succeeds(test_client: TestClient, db_session: Session):
    user = make_user(db_session, "Alice", "alice@example.com")
    make_project(db_session, "proj-alpha", "Alpha", user.id)

    headers = auth_headers(user)
    headers["X-Project-ID"] = "proj-alpha"

    resp = test_client.get("/api/v1/projects/proj-alpha/c1/configs", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_nonexistent_project_returns_404(test_client: TestClient, db_session: Session):
    user = make_user(db_session, "Alice", "alice@example.com")

    headers = auth_headers(user)
    resp = test_client.get(
        "/api/v1/projects/proj-nonexistent/c1/configs", headers=headers
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Project not found."


def test_user_cannot_access_other_users_project_returns_404(
    test_client: TestClient, db_session: Session
):
    alice = make_user(db_session, "Alice", "alice@example.com")
    bob = make_user(db_session, "Bob", "bob@example.com")
    make_project(db_session, "proj-alice", "Alice Proj", alice.id)

    bob_headers = auth_headers(bob)
    # Bob attempts to access Alice's project
    resp = test_client.get(
        "/api/v1/projects/proj-alice/c1/configs", headers=bob_headers
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Project not found."


def test_project_owner_can_create_and_read_c1_config(
    test_client: TestClient, db_session: Session
):
    alice = make_user(db_session, "Alice", "alice@example.com")
    make_project(db_session, "proj-alice", "Alice Proj", alice.id)

    headers = auth_headers(alice)
    payload = make_c1_payload()

    # Create config
    post_resp = test_client.post(
        "/api/v1/projects/proj-alice/c1/configs",
        json=payload,
        headers=headers,
    )
    assert post_resp.status_code == 201
    cfg_data = post_resp.json()
    assert cfg_data["project_id"] == "proj-alice"

    # List configs
    get_resp = test_client.get(
        "/api/v1/projects/proj-alice/c1/configs", headers=headers
    )
    assert get_resp.status_code == 200
    assert len(get_resp.json()) == 1


def test_admin_can_access_any_project_c1_routes(
    test_client: TestClient, db_session: Session
):
    alice = make_user(db_session, "Alice", "alice@example.com", role=UserRole.USER)
    admin = make_user(
        db_session, "Super Admin", "admin@example.com", role=UserRole.ADMIN
    )
    make_project(db_session, "proj-alice", "Alice Proj", alice.id)

    admin_headers = auth_headers(admin)
    resp = test_client.get(
        "/api/v1/projects/proj-alice/c1/configs", headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json() == []
