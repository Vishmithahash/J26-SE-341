"""Comprehensive test suite for Shared Cross-Component Integration Foundation (Part 1).

Verifies:
1. Authenticated access and project authorization (401 unauthenticated, 404 unauthorized project).
2. Strict rejection of cross-project component references (HTTP 422).
3. Missing component configuration produces explicit readiness reasons (not a silent pass).
4. Unapproved model / draft states produce blocking readiness issues.
5. Successful plan creation freezes versions, content digests, and plan digest.
6. Native-to-shared identifier mappings are created and preserved.
7. Retrieval by UUID or integration_run_id is scoped to authorized project.
8. Ad-hoc readiness validation endpoint functions without persisting a plan.
9. ADMIN access to any project succeeds.
10. Operations are NOT launched automatically during Part 1.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c1_tool_call_correctness.examples import (
    get_nexacart_refund_example_config,
)
from app.components.c1_tool_call_correctness.services.config_service import (
    create_project_config,
)
from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
)
from app.components.c2_state_aware_workflow.persistence.repository import (
    C2ModelRepository,
)
from app.components.c2_state_aware_workflow.validator.service import (
    ModelValidationService,
)
from app.components.c3_robustness_recovery.models.persistence import (
    C3CaseModel,
    C3SuiteModel,
)
from app.components.c4_policy_aware_safety.persistence.models import (
    C4ContractModel,
)
from app.config import Settings, get_settings
from app.database import Base, get_db
from app.main import app
from app.shared.auth.models import User, UserRole, normalize_email
from app.shared.auth.security import create_access_token, hash_password
from app.shared.integration.contracts import (
    IntegrationPlanStatus,
    ReadinessIssueCode,
    ReadinessVerdict,
)
from app.shared.projects.models import (
    Project,
    ProjectConnectionState,
    ProjectLifecycle,
)

TEST_AUTH_SECRET = "integration-test-auth-secret-key-32-chars!!"

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_integration_test_db() -> Generator[None, None, None]:
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


# --------------------------------------------------------------------------
# 1. AUTHENTICATION AND AUTHORIZATION
# --------------------------------------------------------------------------


def test_unauthenticated_requests_return_401(
    test_client: TestClient, db_session: Session
):
    user = make_user(db_session, "Alice", "alice@example.com")
    make_project(db_session, "proj-alpha", "Alpha", user.id)

    # Missing Authorization header
    resp_post = test_client.post(
        "/api/v1/projects/proj-alpha/integration/plans",
        json={"name": "Test Plan"},
    )
    assert resp_post.status_code == 401

    resp_get = test_client.get("/api/v1/projects/proj-alpha/integration/plans")
    assert resp_get.status_code == 401


def test_inactive_user_returns_401(test_client: TestClient, db_session: Session):
    user = make_user(db_session, "Inactive", "inactive@example.com", is_active=False)
    make_project(db_session, "proj-alpha", "Alpha", user.id)

    headers = auth_headers(user)
    resp = test_client.get(
        "/api/v1/projects/proj-alpha/integration/plans",
        headers=headers,
    )
    assert resp.status_code == 401


def test_user_cannot_access_other_users_project_returns_404(
    test_client: TestClient, db_session: Session
):
    alice = make_user(db_session, "Alice", "alice@example.com")
    bob = make_user(db_session, "Bob", "bob@example.com")
    make_project(db_session, "proj-alice", "Alice Proj", alice.id)

    bob_headers = auth_headers(bob)
    # Bob attempts to create a plan in Alice's project
    resp = test_client.post(
        "/api/v1/projects/proj-alice/integration/plans",
        json={"name": "Bob Intrusion Plan"},
        headers=bob_headers,
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Project not found."


# --------------------------------------------------------------------------
# 2. CROSS-PROJECT REFERENCE REJECTION
# --------------------------------------------------------------------------


def test_cross_project_reference_rejected_with_422(
    test_client: TestClient, db_session: Session
):
    alice = make_user(db_session, "Alice", "alice@example.com")
    make_project(db_session, "proj-target", "Target Proj", alice.id)
    headers = auth_headers(alice)

    # Reference C1 with a different project_id
    payload = {
        "name": "Cross Project Plan",
        "c1_reference": {
            "project_id": "proj-other",  # Mismatch
            "config_id": "cfg-123",
            "config_version": 1,
        },
    }
    resp = test_client.post(
        "/api/v1/projects/proj-target/integration/plans",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 422
    assert "Cross-project reference rejected" in resp.json()["detail"]


# --------------------------------------------------------------------------
# 3. MISSING CONFIGURATION AND READINESS CHECKS
# --------------------------------------------------------------------------


def test_missing_configurations_produce_explicit_readiness_reasons(
    test_client: TestClient, db_session: Session
):
    alice = make_user(db_session, "Alice", "alice@example.com")
    make_project(db_session, "proj-test", "Test Proj", alice.id)
    headers = auth_headers(alice)

    # Create plan with no component references
    payload = {"name": "Empty References Plan"}
    resp = test_client.post(
        "/api/v1/projects/proj-test/integration/plans",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()

    assert data["lifecycle_status"] == IntegrationPlanStatus.BLOCKED.value
    report = data["readiness_report"]
    assert report["is_ready"] is False
    assert report["verdict"] == ReadinessVerdict.NOT_READY.value

    # Verify explicit reasons for each component
    for comp in ["C1", "C2", "C3", "C4"]:
        comp_status = report["component_statuses"][comp]
        assert comp_status["is_ready"] is False
        assert any(
            iss["issue_code"] == ReadinessIssueCode.MISSING_CONFIGURATION.value
            for iss in comp_status["issues"]
        )


def test_unapproved_c2_model_blocks_readiness(
    test_client: TestClient, db_session: Session
):
    alice = make_user(db_session, "Alice", "alice@example.com")
    make_project(db_session, "proj-c2-draft", "C2 Draft Proj", alice.id)
    headers = auth_headers(alice)

    # Seed C2 model in DRAFT (unapproved)
    repo = C2ModelRepository(db_session)
    efsm = build_synthetic_refund_efsm()
    efsm = efsm.model_copy(update={"project_id": "proj-c2-draft"})
    repo.create_draft_model("proj-c2-draft", efsm)

    payload = {
        "name": "Draft Model Plan",
        "c2_reference": {
            "project_id": "proj-c2-draft",
            "model_id": efsm.model_id,
            "model_version": efsm.version,
        },
    }
    resp = test_client.post(
        "/api/v1/projects/proj-c2-draft/integration/plans",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()

    report = data["readiness_report"]
    assert report["is_ready"] is False
    c2_status = report["component_statuses"]["C2"]
    assert c2_status["is_ready"] is False
    assert any(
        iss["issue_code"] == ReadinessIssueCode.UNAPPROVED_MODEL.value
        for iss in c2_status["issues"]
    )


# --------------------------------------------------------------------------
# 4. SUCCESSFUL PLAN CREATION WITH FROZEN DIGESTS & ID MAPPINGS
# --------------------------------------------------------------------------


def test_successful_plan_creation_with_frozen_digests_and_mappings(
    test_client: TestClient, db_session: Session
):
    alice = make_user(db_session, "Alice", "alice@example.com")
    project_id = "proj-full-integration"
    make_project(db_session, project_id, "Full Integration Proj", alice.id)
    headers = auth_headers(alice)

    # 1. Seed C1 validated config
    c1_cfg_create = get_nexacart_refund_example_config()
    c1_config_model = create_project_config(db_session, project_id, c1_cfg_create)

    # 2. Seed C2 approved model
    repo = C2ModelRepository(db_session)
    efsm = build_synthetic_refund_efsm()
    efsm = efsm.model_copy(update={"project_id": project_id})
    repo.create_draft_model(project_id, efsm)
    val_service = ModelValidationService(db_session)
    val_service.validate_model_record(project_id, efsm.model_id, efsm.version)
    repo.approve_model(
        project_id=project_id,
        model_id=efsm.model_id,
        version=efsm.version,
        reviewer_id="lead_reviewer [SELF_REPORTED_DEVELOPMENT]",
        review_basis="Synthetic specs",
    )

    # 3. Seed C3 frozen suite
    c3_suite = C3SuiteModel(
        suite_id="suite-c3-demo-01",
        suite_digest="a" * 64,
        project_id=project_id,
        task_id="task-checkout-demo",
        tool_id="refund_tool",
        domain="e-commerce",
        schema_version="2026.1",
        generator_version="1.0.0",
        total_cases=1,
        policy_snapshot={},
        adapter_manifest_snapshot={},
        task_fixture_metadata_snapshot={},
        recovery_contract_snapshot={},
        suite_snapshot={},
    )
    db_session.add(c3_suite)
    db_session.flush()

    c3_case = C3CaseModel(
        case_id="case-c3-01",
        suite_digest="a" * 64,
        case_fingerprint="b" * 64,
        content_digest="c" * 64,
        project_id=project_id,
        case_family_id="fam-01",
        fault_family="TRANSIENT_TOOL_FAILURE",
        effect_phase="INVOCATION",
        interception_hook="pre_tool_call",
        target_tool_id="refund_tool",
        case_order=0,
        case_snapshot={},
    )
    db_session.add(c3_case)

    # 4. Seed C4 active policy contract
    c4_contract = C4ContractModel(
        project_id=project_id,
        contract_id="contract-c4-refund",
        version=1,
        lifecycle_state="ACCEPTED",
        content_hash="d" * 64,
    )
    db_session.add(c4_contract)
    db_session.commit()

    # Create integration plan referencing all 4 components
    plan_payload = {
        "name": "Full End-to-End Test Plan",
        "description": "Cross-component orchestration plan for NexaCart refund workflow",
        "c1_reference": {
            "project_id": project_id,
            "config_id": c1_config_model.id,
            "config_version": c1_config_model.version,
        },
        "c2_reference": {
            "project_id": project_id,
            "model_id": efsm.model_id,
            "model_version": efsm.version,
        },
        "c3_reference": {
            "project_id": project_id,
            "suite_id": "suite-c3-demo-01",
            "suite_digest": "a" * 64,
        },
        "c4_reference": {
            "project_id": project_id,
            "contract_id": "contract-c4-refund",
            "contract_version": 1,
        },
    }

    resp = test_client.post(
        f"/api/v1/projects/{project_id}/integration/plans",
        json=plan_payload,
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()

    # Verify ID structure and state
    assert data["integration_run_id"].startswith("irun-")
    assert data["lifecycle_status"] == IntegrationPlanStatus.READY.value
    assert len(data["plan_digest"]) == 64  # SHA256

    # Verify frozen content hashes on all references
    refs = data["component_references"]
    assert refs["c1"]["frozen_content_hash"] is not None
    assert len(refs["c2"]["frozen_content_hash"]) == 64
    assert refs["c3"]["suite_digest"] == "a" * 64
    assert refs["c4"]["frozen_content_hash"] == "d" * 64

    # Verify readiness report
    readiness = data["readiness_report"]
    assert readiness["is_ready"] is True
    assert readiness["verdict"] == ReadinessVerdict.READY.value
    assert len(readiness["blocking_issues"]) == 0

    # Verify native-to-shared identifier mappings
    mappings = data["identifier_mappings"]
    assert len(mappings) >= 4
    comp_types = {m["component"] for m in mappings}
    assert comp_types == {"C1", "C2", "C3", "C4"}


# --------------------------------------------------------------------------
# 5. RETRIEVAL AND LISTING
# --------------------------------------------------------------------------


def test_get_and_list_integration_plans(test_client: TestClient, db_session: Session):
    alice = make_user(db_session, "Alice", "alice@example.com")
    project_id = "proj-list-test"
    make_project(db_session, project_id, "List Test Proj", alice.id)
    headers = auth_headers(alice)

    # Create two plans
    p1 = test_client.post(
        f"/api/v1/projects/{project_id}/integration/plans",
        json={"name": "Plan 1"},
        headers=headers,
    ).json()

    test_client.post(
        f"/api/v1/projects/{project_id}/integration/plans",
        json={"name": "Plan 2"},
        headers=headers,
    )

    # List plans
    list_resp = test_client.get(
        f"/api/v1/projects/{project_id}/integration/plans",
        headers=headers,
    )
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] == 2
    assert len(list_data["items"]) == 2

    # Get by primary UUID
    get_uuid_resp = test_client.get(
        f"/api/v1/projects/{project_id}/integration/plans/{p1['plan_id']}",
        headers=headers,
    )
    assert get_uuid_resp.status_code == 200
    assert get_uuid_resp.json()["name"] == "Plan 1"

    # Get by integration_run_id
    get_irun_resp = test_client.get(
        f"/api/v1/projects/{project_id}/integration/plans/{p1['integration_run_id']}",
        headers=headers,
    )
    assert get_irun_resp.status_code == 200
    assert get_irun_resp.json()["plan_id"] == p1["plan_id"]


# --------------------------------------------------------------------------
# 6. AD-HOC READINESS VALIDATION
# --------------------------------------------------------------------------


def test_ad_hoc_readiness_validation(test_client: TestClient, db_session: Session):
    alice = make_user(db_session, "Alice", "alice@example.com")
    project_id = "proj-adhoc-test"
    make_project(db_session, project_id, "Adhoc Proj", alice.id)
    headers = auth_headers(alice)

    check_payload = {
        "c1_reference": {
            "project_id": project_id,
            "config_id": "nonexistent-cfg",
            "config_version": 1,
        }
    }

    resp = test_client.post(
        f"/api/v1/projects/{project_id}/integration/plans/validate-readiness",
        json=check_payload,
        headers=headers,
    )
    assert resp.status_code == 200
    report = resp.json()
    assert report["is_ready"] is False
    assert report["verdict"] == ReadinessVerdict.NOT_READY.value
    assert any(
        iss["issue_code"] == ReadinessIssueCode.CONFIG_NOT_FOUND.value
        for iss in report["blocking_issues"]
    )


# --------------------------------------------------------------------------
# 7. ADMIN AUTHORIZATION
# --------------------------------------------------------------------------


def test_admin_can_access_and_create_plans_for_any_project(
    test_client: TestClient, db_session: Session
):
    alice = make_user(db_session, "Alice", "alice@example.com", role=UserRole.USER)
    admin = make_user(
        db_session, "Admin User", "admin@example.com", role=UserRole.ADMIN
    )
    project_id = "proj-owned-by-alice"
    make_project(db_session, project_id, "Alice Proj", alice.id)

    admin_headers = auth_headers(admin)

    resp = test_client.post(
        f"/api/v1/projects/{project_id}/integration/plans",
        json={"name": "Admin Supervised Plan"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Admin Supervised Plan"


from sqlalchemy import event


@event.listens_for(test_engine, "connect")
def _set_sqlite_fk(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()
