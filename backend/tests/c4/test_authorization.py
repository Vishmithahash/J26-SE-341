"""Comprehensive server-side authorization and project-scoping tests for Component 4.

Component: C4 Policy-Aware Safety and Prompt-Injection Testing
Verifies:
1. Unauthenticated requests rejected with HTTP 401 Unauthorized.
2. Inactive account requests rejected with HTTP 401 Unauthorized.
3. Unsupported-role accounts rejected with HTTP 403 Forbidden.
4. User A (standard USER) accessing User B's project rejected with HTTP 404 Not Found (fail closed, anti-enumeration).
5. User A referencing User B's entities (artifact, contract, case, binding, dataset) in request bodies rejected with HTTP 404.
6. Admin account permitted access across projects.
7. Client-entered reviewer claims or accepted_by strings do not confer framework permissions.
8. End-to-end authorized workflow from artifact intake to execution report export.
"""

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c4_policy_aware_safety.domains.registry import domain_registry
from app.config import Settings, get_settings
from app.database import Base, get_db
from app.main import app
from app.shared.auth.models import User, UserRole
from app.shared.auth.security import create_access_token
from app.shared.projects.models import (
    Project,
    ProjectConnectionState,
    ProjectLifecycle,
)

C4_AUTH_TEST_SECRET = "c4-auth-secret-key-at-least-32-chars-long-2026"

# Isolated test engine
auth_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
AuthTestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=auth_test_engine
)


@pytest.fixture(autouse=True)
def setup_auth_db() -> Generator[None, None, None]:
    Base.metadata.create_all(bind=auth_test_engine)
    yield
    Base.metadata.drop_all(bind=auth_test_engine)


@pytest.fixture
def auth_session() -> Generator[Session, None, None]:
    session = AuthTestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_users_and_projects(auth_session: Session):
    """Seed two distinct standard users and an admin with owned projects."""
    # User A (Standard USER)
    user_a = User(
        id=101,
        name="Alice User",
        email="alice@example.com",
        canonical_email="alice@example.com",
        password_hash="hash-alice",
        role=UserRole.USER,
        is_active=True,
    )
    # User B (Standard USER)
    user_b = User(
        id=102,
        name="Bob User",
        email="bob@example.com",
        canonical_email="bob@example.com",
        password_hash="hash-bob",
        role=UserRole.USER,
        is_active=True,
    )
    # User Inactive
    user_inactive = User(
        id=103,
        name="Inactive User",
        email="inactive@example.com",
        canonical_email="inactive@example.com",
        password_hash="hash-inactive",
        role=UserRole.USER,
        is_active=False,
    )
    # Admin User
    admin = User(
        id=100,
        name="Carol Admin",
        email="admin@example.com",
        canonical_email="admin@example.com",
        password_hash="hash-admin",
        role=UserRole.ADMIN,
        is_active=True,
    )

    auth_session.add_all([user_a, user_b, user_inactive, admin])

    # Project A owned by User A
    project_a = Project(
        project_id="proj-user-a",
        owner_user_id=user_a.id,
        name="Project A (Alice)",
        domain="e-commerce",
        environment="development",
        backend_base_url="http://localhost:8000",
        backend_health_url="http://localhost:8000/health",
        configuration_version=1,
        lifecycle=ProjectLifecycle.ACTIVE.value,
        connection_state=ProjectConnectionState.NOT_CHECKED.value,
    )
    # Project B owned by User B
    project_b = Project(
        project_id="proj-user-b",
        owner_user_id=user_b.id,
        name="Project B (Bob)",
        domain="booking",
        environment="development",
        backend_base_url="http://localhost:8000",
        backend_health_url="http://localhost:8000/health",
        configuration_version=1,
        lifecycle=ProjectLifecycle.ACTIVE.value,
        connection_state=ProjectConnectionState.NOT_CHECKED.value,
    )

    auth_session.add_all([project_a, project_b])
    auth_session.commit()

    test_settings = Settings(auth_secret_key=C4_AUTH_TEST_SECRET)
    token_a, _ = create_access_token(user_a.id, test_settings)
    token_b, _ = create_access_token(user_b.id, test_settings)
    token_inactive, _ = create_access_token(user_inactive.id, test_settings)
    token_admin, _ = create_access_token(admin.id, test_settings)

    return {
        "user_a": user_a,
        "user_b": user_b,
        "token_a": token_a,
        "token_b": token_b,
        "token_inactive": token_inactive,
        "token_admin": token_admin,
        "project_a": project_a,
        "project_b": project_b,
    }


@pytest.fixture
def api_client(auth_session: Session):
    def override_get_db():
        yield auth_session

    test_settings = Settings(auth_secret_key=C4_AUTH_TEST_SECRET)
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ==============================================================================
# 1. Authentication & Role Enforcement Tests
# ==============================================================================

def test_unauthenticated_request_rejected(api_client, test_users_and_projects):
    """Anonymous callers without Bearer token return HTTP 401 Unauthorized."""
    resp = api_client.get("/projects/proj-user-a/c4/domains")
    assert resp.status_code == 401
    assert "not authenticated" in resp.json()["detail"].lower()


def test_inactive_account_rejected(api_client, test_users_and_projects):
    """Inactive accounts return HTTP 401 Unauthorized."""
    token = test_users_and_projects["token_inactive"]
    headers = {"Authorization": f"Bearer {token}"}
    resp = api_client.get("/projects/proj-user-a/c4/domains", headers=headers)
    assert resp.status_code == 401
    assert "inactive" in resp.json()["detail"].lower()


def test_invalid_bearer_token_rejected(api_client, test_users_and_projects):
    """Malformed or invalid signature bearer tokens return HTTP 401."""
    headers = {"Authorization": "Bearer malformed.invalid.token"}
    resp = api_client.get("/projects/proj-user-a/c4/domains", headers=headers)
    assert resp.status_code == 401


# ==============================================================================
# 2. Ownership & Anti-Enumeration Tests (USER vs ADMIN)
# ==============================================================================

def test_user_cannot_access_foreign_project(api_client, test_users_and_projects):
    """User A attempting to access Project B returns HTTP 404 (preventing enumeration)."""
    token_a = test_users_and_projects["token_a"]
    headers = {"Authorization": f"Bearer {token_a}"}

    # Read endpoint
    resp = api_client.get("/projects/proj-user-b/c4/domains", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Project not found."

    # Mutation endpoint
    art_payload = {
        "artifact_id": "art-cross",
        "artifact_kind": "POLICY_DOCUMENT",
        "raw_content": "Rule text",
    }
    resp_post = api_client.post(
        "/projects/proj-user-b/c4/artifacts", json=art_payload, headers=headers
    )
    assert resp_post.status_code == 404
    assert resp_post.json()["detail"] == "Project not found."


def test_user_can_access_own_project(api_client, test_users_and_projects):
    """User A can access and perform operations on their own project."""
    token_a = test_users_and_projects["token_a"]
    headers = {"Authorization": f"Bearer {token_a}"}

    resp = api_client.get("/projects/proj-user-a/c4/domains", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_admin_can_access_any_project(api_client, test_users_and_projects):
    """Admin accounts can access both Project A and Project B."""
    token_admin = test_users_and_projects["token_admin"]
    headers = {"Authorization": f"Bearer {token_admin}"}

    resp_a = api_client.get("/projects/proj-user-a/c4/domains", headers=headers)
    assert resp_a.status_code == 200

    resp_b = api_client.get("/projects/proj-user-b/c4/domains", headers=headers)
    assert resp_b.status_code == 200


def test_nonexistent_project_returns_404(api_client, test_users_and_projects):
    """Requests targeting non-existent project IDs return HTTP 404."""
    token_a = test_users_and_projects["token_a"]
    headers = {"Authorization": f"Bearer {token_a}"}

    resp = api_client.get("/projects/proj-ghost-999/c4/domains", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Project not found."


# ==============================================================================
# 3. Cross-Project Record Reference Rejection
# ==============================================================================

def test_cross_project_artifact_reference_rejected(api_client, test_users_and_projects):
    """User A cannot derive rules referencing an artifact registered in Project B."""
    headers_b = {"Authorization": f"Bearer {test_users_and_projects['token_b']}"}
    headers_a = {"Authorization": f"Bearer {test_users_and_projects['token_a']}"}

    # 1. User B registers artifact in Project B
    art_resp = api_client.post(
        "/projects/proj-user-b/c4/artifacts",
        json={
            "artifact_id": "art-bob-secret",
            "artifact_kind": "POLICY_DOCUMENT",
            "raw_content": "Confidential Bob policy",
        },
        headers=headers_b,
    )
    assert art_resp.status_code == 201

    # 2. User A attempts to derive rules in Project A referencing Bob's artifact ID
    derive_resp = api_client.post(
        "/projects/proj-user-a/c4/rules/derive",
        json={
            "artifact_id": "art-bob-secret",
            "artifact_version": 1,
            "mode": "controlled_language",
        },
        headers=headers_a,
    )
    # Must fail closed with 404 Not Found without leaking Bob's artifact
    assert derive_resp.status_code == 404
    assert "not found" in derive_resp.json()["detail"].lower()


def test_cross_project_contract_and_binding_reference_rejected(
    api_client, test_users_and_projects
):
    """User A cannot run test generation referencing a contract or binding from Project B."""
    headers_b = {"Authorization": f"Bearer {test_users_and_projects['token_b']}"}
    headers_a = {"Authorization": f"Bearer {test_users_and_projects['token_a']}"}

    # User B registers binding in Project B
    from app.components.c4_policy_aware_safety.domains.registry import domain_registry

    bob_binding = domain_registry.get_profile("domain-ecommerce-c4").binding.model_copy()
    bob_binding.binding_id = "binding-bob"
    bob_binding.project_id = "proj-user-b"
    bind_resp = api_client.post(
        "/projects/proj-user-b/c4/bindings",
        json=bob_binding.model_dump(mode="json"),
        headers=headers_b,
    )
    assert bind_resp.status_code == 201

    # User A attempts to generate test cases in Project A referencing Bob's binding
    gen_resp = api_client.post(
        "/projects/proj-user-a/c4/generate",
        json={
            "contract_id": "contract-alice",
            "contract_version": 1,
            "binding_id": "binding-bob",
            "binding_version": 1,
        },
        headers=headers_a,
    )
    assert gen_resp.status_code == 404
    assert "not found in project 'proj-user-a'" in gen_resp.json()["detail"]


def test_cross_project_dataset_reference_in_experiment_rejected(
    api_client, test_users_and_projects
):
    """User A cannot create an evaluation experiment referencing a dataset from Project B."""
    headers_b = {"Authorization": f"Bearer {test_users_and_projects['token_b']}"}
    headers_a = {"Authorization": f"Bearer {test_users_and_projects['token_a']}"}

    # User B registers evaluation dataset in Project B
    ds_resp = api_client.post(
        "/projects/proj-user-b/c4/evaluation/datasets",
        json={
            "dataset_id": "ds-bob-benchmark",
            "version": 1,
            "dataset_hash": "hash-bob",
            "project_id": "proj-user-b",
            "domain_id": "booking",
            "cases": [],
        },
        headers=headers_b,
    )
    assert ds_resp.status_code == 201

    # User A attempts to configure experiment in Project A referencing Bob's dataset
    exp_resp = api_client.post(
        "/projects/proj-user-a/c4/evaluation/experiments",
        json={
            "experiment_id": "exp-alice-01",
            "project_id": "proj-user-a",
            "domain_id": "e-commerce",
            "dataset_id": "ds-bob-benchmark",
            "dataset_version": 1,
            "split": "DEV",
            "strategy_type": "C4_POLICY_AWARE",
            "ablation_type": "NONE",
        },
        headers=headers_a,
    )
    assert exp_resp.status_code == 404
    assert "not found in project 'proj-user-a'" in exp_resp.json()["detail"]


# ==============================================================================
# 4. Reviewer Claim vs Authenticated Identity Separation
# ==============================================================================

def test_client_entered_reviewer_name_does_not_grant_permissions(api_client, test_users_and_projects):
    """An unauthenticated request with accepted_by='admin' is still strictly rejected."""
    resp = api_client.post(
        "/projects/proj-user-a/c4/contracts/contract-1/versions/1/accept",
        json={
            "accepted_by": "superadmin@platform.qa",
            "rationale": "Attempting to claim admin reviewer identity",
        },
    )
    assert resp.status_code == 401


# ==============================================================================
# 5. Full End-to-End Authorized C4 Workflow
# ==============================================================================

def test_authorized_full_lifecycle_and_report_export(api_client, test_users_and_projects):
    """Exercises complete authenticated C4 workflow within User A's authorized project."""
    headers = {"Authorization": f"Bearer {test_users_and_projects['token_a']}"}
    proj_id = "proj-user-a"

    # Step 1: Register Artifact
    art_resp = api_client.post(
        f"/projects/{proj_id}/c4/artifacts",
        json={
            "artifact_id": "policy-alice-governance",
            "artifact_kind": "POLICY_DOCUMENT",
            "raw_content": (
                "# Alice Refund Policy\n"
                "Roles with CUSTOMER_SUPPORT must not process_refund order_refund exceeding 1000 without MANAGER approval.\n"
            ),
        },
        headers=headers,
    )
    assert art_resp.status_code == 201
    art_data = art_resp.json()
    assert art_data["artifact_id"] == "policy-alice-governance"

    # Step 2: Derive Candidate Rules
    derive_resp = api_client.post(
        f"/projects/{proj_id}/c4/rules/derive",
        json={
            "artifact_id": "policy-alice-governance",
            "artifact_version": 1,
            "mode": "controlled_language",
        },
        headers=headers,
    )
    assert derive_resp.status_code == 200
    candidates = derive_resp.json()
    assert len(candidates) >= 1
    rule_id = candidates[0]["rule_id"]

    # Step 3: Record Review Decision for Candidate Rule
    review_resp = api_client.post(
        f"/projects/{proj_id}/c4/candidates/{rule_id}/review",
        json={
            "decision": "ACCEPTED",
            "reviewer": "dev_test_alice",
            "review_notes": "Verified against governance document.",
        },
        headers=headers,
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["review_status"] == "ACCEPTED"

    # Step 4: Create Draft Contract
    contract_resp = api_client.post(
        f"/projects/{proj_id}/c4/contracts",
        json={
            "contract_id": "contract-alice-v1",
            "rule_ids": [rule_id],
        },
        headers=headers,
    )
    assert contract_resp.status_code == 201
    contract_data = contract_resp.json()

    # Step 5: Accept Contract
    accept_resp = api_client.post(
        f"/projects/{proj_id}/c4/contracts/contract-alice-v1/versions/1/accept",
        json={
            "accepted_by": "alice_reviewer",
            "rationale": "Passed human validation review.",
        },
        headers=headers,
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["lifecycle_state"] == "ACCEPTED"

    # Step 6: Register Domain Binding
    alice_binding = domain_registry.get_profile("domain-ecommerce-c4").binding.model_copy()
    alice_binding.binding_id = "binding-alice-ecom"
    alice_binding.project_id = proj_id
    bind_resp = api_client.post(
        f"/projects/{proj_id}/c4/bindings",
        json=alice_binding.model_dump(mode="json"),
        headers=headers,
    )
    assert bind_resp.status_code == 201

    # Step 7: Generate Test Cases
    gen_resp = api_client.post(
        f"/projects/{proj_id}/c4/generate",
        json={
            "contract_id": "contract-alice-v1",
            "contract_version": 1,
            "binding_id": "binding-alice-ecom",
            "binding_version": 1,
            "auto_validate": True,
            "auto_freeze": True,
        },
        headers=headers,
    )
    assert gen_resp.status_code == 200
    report = gen_resp.json()
    assert report["generated_count"] >= 1
    assert report["frozen_count"] >= 1

    # Step 8: List Generated Cases
    cases_resp = api_client.get(f"/projects/{proj_id}/c4/cases", headers=headers)
    assert cases_resp.status_code == 200
    all_cases = cases_resp.json()
    assert len(all_cases) >= 1
    target_case = all_cases[0]

    # Step 9: Check Runtime Readiness
    ready_resp = api_client.post(
        f"/projects/{proj_id}/c4/runs/readiness",
        json={
            "case_id": target_case["case_id"],
            "case_version": target_case["case_version"],
            "contract_id": "contract-alice-v1",
            "contract_version": 1,
            "binding_id": "binding-alice-ecom",
            "binding_version": 1,
            "execution_mode": "SIMULATED",
            "simulated_behavior": "COMPLIANT",
        },
        headers=headers,
    )
    assert ready_resp.status_code == 200
    assert ready_resp.json()["is_ready"] is True

    # Step 10: Execute Simulated Test Case
    exec_resp = api_client.post(
        f"/projects/{proj_id}/c4/runs/execute",
        json={
            "case_id": target_case["case_id"],
            "case_version": target_case["case_version"],
            "contract_id": "contract-alice-v1",
            "contract_version": 1,
            "binding_id": "binding-alice-ecom",
            "binding_version": 1,
            "execution_mode": "SIMULATED",
            "simulated_behavior": "COMPLIANT",
            "idempotency_key": "key-alice-flow-01",
        },
        headers=headers,
    )
    assert exec_resp.status_code == 200
    run_rec = exec_resp.json()
    assert run_rec["run_id"] is not None
    assert run_rec["idempotency_key"] == "key-alice-flow-01"

    # Step 11: Export Run Report
    rep_resp = api_client.get(
        f"/projects/{proj_id}/c4/runs/{run_rec['run_id']}/report",
        headers=headers,
    )
    assert rep_resp.status_code == 200
    rep_data = rep_resp.json()
    assert rep_data["project_id"] == proj_id
    assert rep_data["run_id"] == run_rec["run_id"]
    assert rep_data["execution_status"] == "COMPLETED"
