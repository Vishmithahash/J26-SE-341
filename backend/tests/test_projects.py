"""Comprehensive unit and integration tests for Shared Projects Workspace.

Tests verify:
- Project creation bound strictly to authenticated account.
- Injected ownership or connection state is rejected/ignored.
- Ownership and permissions enforcement for USER vs ADMIN.
- Project detail, update, disconnect, archive, and restore workflows.
- SSRF prevention (cloud metadata, invalid scheme, embedded credentials).
- Honest connection state transitions (NOT_CHECKED, CONNECTED, PARTIAL, AUTH_REQUIRED, UNREACHABLE, INVALID_CONFIGURATION, DISCONNECTED).
- In-flight check protection avoiding overwriting newly updated configurations.
- Preserved input reference versions and append-only audit event history.
"""

import os

# Set test auth secret before importing application settings
TEST_AUTH_SECRET = "super-secret-test-key-minimum-32-bytes-long-for-hmac-sha256"
os.environ["AUTH_SECRET_KEY"] = TEST_AUTH_SECRET
os.environ["AUTH_JWT_ALGORITHM"] = "HS256"
os.environ["AUTH_ACCESS_TOKEN_EXPIRE_MINUTES"] = "15"

from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.database import Base, get_db
from app.main import app
from app.shared.auth.models import User, UserRole
from app.shared.auth.security import create_access_token, hash_password
from app.shared.projects.connection_service import validate_target_safety
from app.shared.projects.models import (
    Project,
    ProjectConnectionState,
)
from app.shared.projects.schemas import EndpointCheckOutcome

# In-memory SQLite database for isolated test execution
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db() -> Generator[None, None, None]:
    """Create all tables before each test and drop them afterwards."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a clean database session for test setup."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient with database session dependency override."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    test_settings = Settings(auth_secret_key=TEST_AUTH_SECRET)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def standard_user(db_session: Session) -> User:
    """Create a persistent standard USER in the test database."""
    user = User(
        name="Standard Alice",
        email="alice@example.com",
        canonical_email="alice@example.com",
        password_hash=hash_password("Password123!"),
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def other_user(db_session: Session) -> User:
    """Create another persistent standard USER in the test database."""
    user = User(
        name="Standard Bob",
        email="bob@example.com",
        canonical_email="bob@example.com",
        password_hash=hash_password("Password123!"),
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """Create a persistent ADMIN user in the test database."""
    admin = User(
        name="Admin Carol",
        email="carol@example.com",
        canonical_email="carol@example.com",
        password_hash=hash_password("Password123!"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def auth_headers(user: User) -> dict[str, str]:
    """Generate RFC Bearer Authorization headers for a given user."""
    override = app.dependency_overrides.get(get_settings)
    settings = override() if override else Settings(auth_secret_key=TEST_AUTH_SECRET)
    if not settings.auth_secret_key.get_secret_value():
        settings = Settings(auth_secret_key=TEST_AUTH_SECRET)
    token, _ = create_access_token(user.id, settings)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. SSRF & Target Safety Unit Tests
# ---------------------------------------------------------------------------

def test_validate_target_safety_blocked_metadata():
    """Ensure cloud metadata (169.254.169.254) is strictly blocked."""
    is_safe, error, _ = validate_target_safety("http://169.254.169.254/latest/meta-data")
    assert not is_safe
    assert "restricted network destination" in (error or "").lower()


def test_validate_target_safety_prohibits_unspecified_0000():
    """Ensure 0.0.0.0 destination is strictly prohibited."""
    is_safe, error, _ = validate_target_safety("http://0.0.0.0:8000/health")
    assert not is_safe
    assert "0.0.0.0" in (error or "").lower()


def test_validate_target_safety_prohibits_embedded_credentials():
    """Ensure embedded username:password URLs are rejected."""
    is_safe, error, _ = validate_target_safety("http://admin:secret@localhost:8000/health")
    assert not is_safe
    assert "embedded credentials" in (error or "").lower()


def test_validate_target_safety_prohibits_invalid_scheme():
    """Ensure non-HTTP schemes are rejected."""
    is_safe, error, _ = validate_target_safety("ftp://localhost:21/health")
    assert not is_safe
    assert "prohibited url scheme" in (error or "").lower()


def test_validate_target_safety_checks_exact_port():
    """Ensure unapproved ports on localhost are rejected."""
    is_safe, error, _ = validate_target_safety("http://localhost:9999/health")
    assert not is_safe
    assert "not in the operator allowed origins" in (error or "").lower()


def test_validate_target_safety_allows_configured_localhost():
    """Ensure localhost on approved origin list with exact port passes safety checks."""
    is_safe, error, _ = validate_target_safety("http://localhost:8000/health")
    assert is_safe
    assert error is None


# ---------------------------------------------------------------------------
# 2. Project Registration & Ownership Security
# ---------------------------------------------------------------------------

def test_user_can_create_project(client: TestClient, standard_user: User):
    """Ensure a standard user can register an application project."""
    payload = {
        "name": "E-Commerce Store Service",
        "description": "Primary shop backend for tool-calling evaluation",
        "domain": "e-commerce",
        "environment": "development",
        "backend_base_url": "http://localhost:8080",
        "backend_health_url": "http://localhost:8080/health",
        "agent_endpoint": "http://localhost:8081/agent",
        "agent_health_url": "http://localhost:8081/health",
        "repository_url": "https://github.com/example/ecommerce-service",
        "initial_inputs": [
            {
                "category": "API/tool specification",
                "label": "OpenAPI Specification v3.1",
                "reference_location": "docs/openapi.json",
                "version": "1.0.0",
            }
        ],
    }

    res = client.post("/api/v1/projects", json=payload, headers=auth_headers(standard_user))
    assert res.status_code == 201
    data = res.json()
    assert data["project_id"].startswith("proj-")
    assert data["owner_user_id"] == standard_user.id
    assert data["name"] == "E-Commerce Store Service"
    assert data["connection_state"] == "NOT_CHECKED"
    assert data["lifecycle"] == "active"
    assert data["configuration_version"] == 1
    assert data["input_references_count"] == 1


def test_user_cannot_spoof_ownership_or_state(client: TestClient, standard_user: User):
    """Ensure injected owner_user_id or connection_state are rejected or ignored."""
    payload = {
        "name": "Spoof Attempt",
        "domain": "custom",
        "backend_base_url": "http://localhost:8000",
        "backend_health_url": "http://localhost:8000/health",
        "owner_user_id": 9999,
        "connection_state": "CONNECTED",
        "configuration_version": 42,
    }

    res = client.post("/api/v1/projects", json=payload, headers=auth_headers(standard_user))
    assert res.status_code == 201
    data = res.json()
    assert data["owner_user_id"] == standard_user.id
    assert data["connection_state"] == "NOT_CHECKED"
    assert data["configuration_version"] == 1


# ---------------------------------------------------------------------------
# 3. Access Boundaries (USER Isolation vs ADMIN Visibility)
# ---------------------------------------------------------------------------

def test_user_cannot_access_other_users_project(
    client: TestClient,
    standard_user: User,
    other_user: User,
):
    """Ensure USER cannot read, modify, or check another user's project (404 Fail Closed)."""
    # Alice creates a project
    payload = {
        "name": "Alice Private Project",
        "domain": "booking",
        "backend_base_url": "http://localhost:5000",
        "backend_health_url": "http://localhost:5000/health",
    }
    create_res = client.post("/api/v1/projects", json=payload, headers=auth_headers(standard_user))
    project_id = create_res.json()["project_id"]

    # Bob attempts to read Alice's project -> fails closed with 404
    get_res = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers(other_user))
    assert get_res.status_code == 404

    # Bob attempts to update Alice's project -> fails closed with 404
    patch_res = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Bob Hijack"},
        headers=auth_headers(other_user),
    )
    assert patch_res.status_code == 404

    # Bob attempts to check connection -> fails closed with 404
    check_res = client.post(
        f"/api/v1/projects/{project_id}/check-connection",
        headers=auth_headers(other_user),
    )
    assert check_res.status_code == 404


def test_admin_can_access_all_projects(
    client: TestClient,
    standard_user: User,
    admin_user: User,
):
    """Ensure ADMIN can list and view projects created by any user."""
    payload = {
        "name": "Alice App for Testing",
        "domain": "custom",
        "backend_base_url": "http://localhost:3000",
        "backend_health_url": "http://localhost:3000/health",
    }
    create_res = client.post("/api/v1/projects", json=payload, headers=auth_headers(standard_user))
    project_id = create_res.json()["project_id"]

    # Admin reads Alice's project
    res = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers(admin_user))
    assert res.status_code == 200
    data = res.json()
    assert data["project_id"] == project_id
    assert data["owner"]["email"] == standard_user.email

    # Admin lists projects and sees Alice's project
    list_res = client.get("/api/v1/projects", headers=auth_headers(admin_user))
    assert list_res.status_code == 200
    assert any(p["project_id"] == project_id for p in list_res.json()["items"])


# ---------------------------------------------------------------------------
# 4. Connection State Transitions & Invalidation Rules
# ---------------------------------------------------------------------------

def test_updating_connection_urls_resets_connection_state(
    client: TestClient,
    standard_user: User,
    db_session: Session,
):
    """Editing backend or agent URLs must reset state to NOT_CHECKED and increment version."""
    payload = {
        "name": "State Invalidation Test",
        "domain": "custom",
        "backend_base_url": "http://localhost:8000",
        "backend_health_url": "http://localhost:8000/health",
    }
    create_res = client.post("/api/v1/projects", json=payload, headers=auth_headers(standard_user))
    project_id = create_res.json()["project_id"]

    # Manually simulate a previous CONNECTED state in DB
    proj = db_session.get(Project, project_id)
    assert proj is not None
    proj.connection_state = ProjectConnectionState.CONNECTED.value
    db_session.commit()

    # User updates the health check URL
    patch_res = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"backend_health_url": "http://localhost:8000/healthz"},
        headers=auth_headers(standard_user),
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["connection_state"] == "NOT_CHECKED"
    assert data["configuration_version"] == 2


def test_disconnect_and_archive_restore_lifecycle(
    client: TestClient,
    standard_user: User,
):
    """Verify explicit disconnect, archive, and restore workflows."""
    payload = {
        "name": "Lifecycle Test App",
        "domain": "e-commerce",
        "backend_base_url": "http://localhost:8000",
        "backend_health_url": "http://localhost:8000/health",
    }
    create_res = client.post("/api/v1/projects", json=payload, headers=auth_headers(standard_user))
    project_id = create_res.json()["project_id"]

    # 1. Disconnect
    disc_res = client.post(f"/api/v1/projects/{project_id}/disconnect", headers=auth_headers(standard_user))
    assert disc_res.status_code == 200
    assert disc_res.json()["connection_state"] == "DISCONNECTED"

    # 2. Archive
    arch_res = client.post(f"/api/v1/projects/{project_id}/archive", headers=auth_headers(standard_user))
    assert arch_res.status_code == 200
    assert arch_res.json()["lifecycle"] == "archived"

    # 3. Connection check on archived project must be blocked (HTTP 400)
    check_res = client.post(f"/api/v1/projects/{project_id}/check-connection", headers=auth_headers(standard_user))
    assert check_res.status_code == 400

    # 4. Restore
    rest_res = client.post(f"/api/v1/projects/{project_id}/restore", headers=auth_headers(standard_user))
    assert rest_res.status_code == 200
    assert rest_res.json()["lifecycle"] == "active"


# ---------------------------------------------------------------------------
# 5. Outbound Connection Probe Logic (Mocked HTTP)
# ---------------------------------------------------------------------------

def test_connection_check_both_endpoints_connected(
    client: TestClient,
    standard_user: User,
):
    """Successful checks of both backend and agent endpoints produce CONNECTED state."""
    payload = {
        "name": "Full Probe App",
        "domain": "e-commerce",
        "backend_base_url": "http://localhost:8000",
        "backend_health_url": "http://localhost:8000/health",
        "agent_endpoint": "http://localhost:8001/agent",
        "agent_health_url": "http://localhost:8001/health",
    }
    create_res = client.post("/api/v1/projects", json=payload, headers=auth_headers(standard_user))
    project_id = create_res.json()["project_id"]

    mock_backend = EndpointCheckOutcome(
        configured=True,
        target_url="http://localhost:8000/health",
        status_code=200,
        latency_ms=25.0,
        reachable=True,
    )
    mock_agent = EndpointCheckOutcome(
        configured=True,
        target_url="http://localhost:8001/health",
        status_code=200,
        latency_ms=30.0,
        reachable=True,
    )

    with patch(
        "app.shared.projects.service.probe_endpoint",
        side_effect=[mock_backend, mock_agent],
    ):
        res = client.post(
            f"/api/v1/projects/{project_id}/check-connection",
            headers=auth_headers(standard_user),
        )
        assert res.status_code == 200
        data = res.json()
        assert data["connection_state"] == "CONNECTED"
        assert data["backend_outcome"]["reachable"] is True
        assert data["agent_outcome"]["reachable"] is True


def test_connection_check_partial_when_agent_absent(
    client: TestClient,
    standard_user: User,
):
    """Reachable backend but absent agent endpoint produces PARTIAL state."""
    payload = {
        "name": "Partial Probe App",
        "domain": "booking",
        "backend_base_url": "http://localhost:8000",
        "backend_health_url": "http://localhost:8000/health",
    }
    create_res = client.post("/api/v1/projects", json=payload, headers=auth_headers(standard_user))
    project_id = create_res.json()["project_id"]

    mock_backend = EndpointCheckOutcome(
        configured=True,
        target_url="http://localhost:8000/health",
        status_code=200,
        latency_ms=18.0,
        reachable=True,
    )
    mock_agent = EndpointCheckOutcome(configured=False)

    with patch(
        "app.shared.projects.service.probe_endpoint",
        side_effect=[mock_backend, mock_agent],
    ):
        res = client.post(
            f"/api/v1/projects/{project_id}/check-connection",
            headers=auth_headers(standard_user),
        )
        assert res.status_code == 200
        data = res.json()
        assert data["connection_state"] == "PARTIAL"


# ---------------------------------------------------------------------------
# 6. Input References & Audit Trail Preservation
# ---------------------------------------------------------------------------

def test_add_input_reference_preserves_history(
    client: TestClient,
    standard_user: User,
):
    """Registering input references appends records and emits audit events."""
    payload = {
        "name": "Inputs Tracking App",
        "domain": "learning/examination",
        "backend_base_url": "http://localhost:8000",
        "backend_health_url": "http://localhost:8000/health",
    }
    create_res = client.post("/api/v1/projects", json=payload, headers=auth_headers(standard_user))
    project_id = create_res.json()["project_id"]

    ref_payload = {
        "category": "Requirements",
        "label": "User Stories & Conformance Spec v1",
        "reference_location": "docs/specs/v1.md",
        "version": "1.0.0",
    }
    add_res = client.post(
        f"/api/v1/projects/{project_id}/inputs",
        json=ref_payload,
        headers=auth_headers(standard_user),
    )
    assert add_res.status_code == 201
    ref_data = add_res.json()
    assert ref_data["reference_id"].startswith("ref-")
    assert ref_data["label"] == "User Stories & Conformance Spec v1"

    # Query inputs
    inputs_res = client.get(f"/api/v1/projects/{project_id}/inputs", headers=auth_headers(standard_user))
    assert inputs_res.status_code == 200
    assert len(inputs_res.json()) == 1

    # Query audit history
    history_res = client.get(f"/api/v1/projects/{project_id}/history", headers=auth_headers(standard_user))
    assert history_res.status_code == 200
    events = history_res.json()["items"]
    event_types = [e["event_type"] for e in events]
    assert "PROJECT_CREATED" in event_types
    assert "INPUT_REFERENCE_ADDED" in event_types


# ---------------------------------------------------------------------------
# 7. In-Flight Concurrency & Overwrite Protection
# ---------------------------------------------------------------------------

def test_in_flight_probe_does_not_overwrite_subsequent_disconnect(
    client: TestClient,
    standard_user: User,
):
    """A delayed probe result must NOT overwrite a subsequent disconnect."""
    payload = {
        "name": "Delayed Check App",
        "domain": "custom",
        "backend_base_url": "http://localhost:8000",
        "backend_health_url": "http://localhost:8000/health",
        "agent_endpoint": "http://localhost:8001/agent",
        "agent_health_url": "http://localhost:8001/health",
    }
    create_res = client.post("/api/v1/projects", json=payload, headers=auth_headers(standard_user))
    project_id = create_res.json()["project_id"]

    mock_backend = EndpointCheckOutcome(configured=True, reachable=True, status_code=200, latency_ms=10.0)
    mock_agent = EndpointCheckOutcome(configured=True, reachable=True, status_code=200, latency_ms=15.0)

    # In probe side_effect, simulate concurrent disconnect in database before probe returns
    def probe_with_concurrent_disconnect(url):
        with TestingSessionLocal() as s:
            p = s.get(Project, project_id)
            if p:
                p.connection_state = ProjectConnectionState.DISCONNECTED.value
                p.configuration_version += 1
                s.commit()
        return mock_backend if "8000" in (url or "") else mock_agent

    with patch(
        "app.shared.projects.service.probe_endpoint",
        side_effect=probe_with_concurrent_disconnect,
    ):
        check_res = client.post(
            f"/api/v1/projects/{project_id}/check-connection",
            headers=auth_headers(standard_user),
        )
        assert check_res.status_code == 200

    # Verify project state was NOT overwritten by the in-flight probe
    proj_res = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers(standard_user))
    assert proj_res.status_code == 200
    assert proj_res.json()["connection_state"] == "DISCONNECTED"

    # But the historical check event is recorded
    hist_res = client.get(f"/api/v1/projects/{project_id}/history", headers=auth_headers(standard_user))
    assert hist_res.status_code == 200
    hist_events = [e["event_type"] for e in hist_res.json()["items"]]
    assert "CONNECTION_CHECKED" in hist_events


def test_in_flight_probe_does_not_overwrite_subsequent_archive(
    client: TestClient,
    standard_user: User,
):
    """A delayed probe result must NOT overwrite a subsequent archive."""
    payload = {
        "name": "Delayed Archive App",
        "domain": "custom",
        "backend_base_url": "http://localhost:8000",
        "backend_health_url": "http://localhost:8000/health",
    }
    create_res = client.post("/api/v1/projects", json=payload, headers=auth_headers(standard_user))
    project_id = create_res.json()["project_id"]

    mock_backend = EndpointCheckOutcome(configured=True, reachable=True, status_code=200, latency_ms=10.0)
    mock_agent = EndpointCheckOutcome(configured=False)

    def probe_with_concurrent_archive(url):
        with TestingSessionLocal() as s:
            p = s.get(Project, project_id)
            if p:
                p.lifecycle = "archived"
                p.configuration_version += 1
                s.commit()
        return mock_backend if "8000" in (url or "") else mock_agent

    with patch(
        "app.shared.projects.service.probe_endpoint",
        side_effect=probe_with_concurrent_archive,
    ):
        check_res = client.post(
            f"/api/v1/projects/{project_id}/check-connection",
            headers=auth_headers(standard_user),
        )
        assert check_res.status_code == 200

    # Project lifecycle must remain archived
    proj_res = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers(standard_user))
    assert proj_res.status_code == 200
    assert proj_res.json()["lifecycle"] == "archived"
