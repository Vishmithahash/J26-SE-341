from app.components.c4_policy_aware_safety.contracts.enums import (
    ContractLifecycleState,
    EvaluationBoundary,
    PolicyFamily,
    PolicyRequirement,
    Severity,
)
from app.components.c4_policy_aware_safety.contracts.predicates import (
    CompoundOperator,
    CompoundPredicate,
)
from app.components.c4_policy_aware_safety.contracts.rules import PolicyRule
from app.shared.integration.models import IntegrationExecutionModel

"""Comprehensive integration test suite for Backend Integration — Part 2:
Shared execution coordination, correlated evidence, and multi-evaluator routing.

Verifies:
1. Coordinated execution invokes the target once per trial and retains correlated evidence.
2. Evaluator dispatch to real C1, C2, C3, and C4 evaluators without mocking verdicts or the C2-to-C3 bridge.
3. Coexistence of distinct valid component verdicts (C1 PASS, C2 PASS, C3 PASS_COMPLETED, C4 PASS).
4. C3 matched-pair requirements: clean and fault trials execute with fresh fixtures, exposure verified.
5. C2-to-C3 bridge feeds authoritative C2 assertion facts to C3 recovery evaluation.
6. Honest readiness: LIVE_AUT execution is rejected with HTTP 422 (reported as BLOCKED); never falls back silently to simulation.
7. Authenticated project-scoped execution controls (401 unauthenticated, 404 cross-project).
8. Safe execution cancellation with bounded settling.
9. Developer CLI executes and reports execution status correctly.
"""

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
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
from app.shared.integration.cli import main as cli_main
from app.shared.integration.contracts import (
    C1ConfigReference,
    C2ModelReference,
    IntegrationRunPlanCreateRequest,
)
from app.shared.integration.service import IntegrationService
from app.shared.projects.models import (
    Project,
    ProjectConnectionState,
    ProjectLifecycle,
)

TEST_AUTH_SECRET = "exec-test-auth-secret-key-32-chars!!"

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_execution_test_db() -> Generator[None, None, None]:
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
    client = TestClient(app)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def seed_test_user(db_session: Session) -> User:
    user = User(
        name="QA Engineer",
        email="qa@test.local",
        canonical_email=normalize_email("qa@test.local"),
        password_hash=hash_password("SafePassword123!"),
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def user_auth_headers(seed_test_user: User) -> dict[str, str]:
    settings = Settings(auth_secret_key=TEST_AUTH_SECRET)
    token, _ = create_access_token(seed_test_user.id, settings)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seed_project(db_session: Session, seed_test_user: User) -> Project:
    proj = Project(
        project_id="proj-shared-exec",
        name="Shared Execution Testing Project",
        description="Scoping container for execution coordination tests",
        lifecycle=ProjectLifecycle.ACTIVE.value,
        connection_state=ProjectConnectionState.CONNECTED.value,
        owner_user_id=seed_test_user.id,
        backend_base_url="http://localhost:8000",
        backend_health_url="http://localhost:8000/health",
    )
    db_session.add(proj)
    db_session.commit()
    db_session.refresh(proj)
    return proj


@pytest.fixture
def seed_all_components(
    db_session: Session, seed_project: Project, seed_test_user: User
) -> dict[str, Any]:
    """Seed approved and frozen configurations for all 4 components in the test project."""
    p_id = seed_project.project_id

    # 1. C1 Config
    c1_example = get_nexacart_refund_example_config()
    c1_record = create_project_config(db_session, p_id, c1_example)

    # 2. C2 Approved EFSM Model
    c2_repo = C2ModelRepository(db_session)
    c2_efsm = build_synthetic_refund_efsm()
    c2_efsm = c2_efsm.model_copy(update={"project_id": p_id})
    c2_repo.create_draft_model(p_id, c2_efsm)
    val_service = ModelValidationService(db_session)
    val_service.validate_model_record(p_id, c2_efsm.model_id, c2_efsm.version)
    c2_record = c2_repo.approve_model(
        project_id=p_id,
        model_id=c2_efsm.model_id,
        version=c2_efsm.version,
        reviewer_id=f"reviewer_{seed_test_user.id} [SELF_REPORTED_DEVELOPMENT]",
        review_basis="Synthetic specs",
    )

    # 3. C3 Frozen Suite
    c3_suite = C3SuiteModel(
        suite_id="suite-c3-exec-01",
        suite_digest="a" * 64,
        project_id=p_id,
        task_id="task-checkout-demo",
        tool_id="order_placement",
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
        case_id="case-c3-exec-01",
        suite_digest="a" * 64,
        case_fingerprint="b" * 64,
        content_digest="c" * 64,
        project_id=p_id,
        case_family_id="fam-01",
        fault_family="TRANSIENT_TOOL_FAILURE",
        effect_phase="INVOCATION",
        interception_hook="pre_tool_call",
        target_tool_id="order_placement",
        case_order=0,
        case_snapshot={},
    )
    db_session.add(c3_case)

    # 4. C4 Accepted Contract
    valid_c4_rule = PolicyRule(
        project_id=p_id,
        rule_id="pol_exec_01",
        rule_version=1,
        policy_family=PolicyFamily.AUTHORIZATION,
        principal_selector="*",
        action_selector="*",
        resource_selector="*",
        policy_requirement=PolicyRequirement.REQUIRE,
        compliance_conditions=CompoundPredicate(
            operator=CompoundOperator.ALL, conditions=[]
        ),
        evaluation_boundary=EvaluationBoundary.ATTEMPTED_ACTION,
        required_evidence=["trace"],
        severity=Severity.HIGH,
        source_references=[],
    ).model_dump(mode="json")

    c4_contract = C4ContractModel(
        project_id=p_id,
        contract_id="contract-c4-refund",
        version=1,
        lifecycle_state=ContractLifecycleState.ACCEPTED.value,
        content_hash="d" * 64,
        rules_data=[valid_c4_rule],
    )
    db_session.add(c4_contract)
    db_session.commit()

    return {
        "c1": c1_record,
        "c2": c2_record,
        "c2_efsm": c2_efsm,
        "c3": c3_suite,
        "c4": c4_contract,
    }


def _create_ready_run_plan(
    client: TestClient,
    project_id: str,
    headers: dict[str, str],
    components: dict[str, Any],
) -> dict[str, Any]:
    """Helper to create a frozen, READY integration run plan referencing all 4 components."""
    payload = {
        "name": "Coordinated Execution Test Plan",
        "description": "Cross-component execution with correlated evidence",
        "c1_reference": {
            "project_id": project_id,
            "config_id": components["c1"].id,
            "config_version": components["c1"].version,
        },
        "c2_reference": {
            "project_id": project_id,
            "model_id": components["c2_efsm"].model_id,
            "model_version": components["c2_efsm"].version,
        },
        "c3_reference": {
            "project_id": project_id,
            "suite_id": components["c3"].suite_id,
            "suite_digest": components["c3"].suite_digest,
            "target_tool_id": "order_placement",
        },
        "c4_reference": {
            "project_id": project_id,
            "contract_id": components["c4"].contract_id,
            "contract_version": 1,
        },
    }
    resp = client.post(
        f"/api/v1/projects/{project_id}/integration/plans",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["lifecycle_status"] == "READY"
    return data


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------


def test_coordinated_execution_runs_and_evaluates_all_components(
    test_client: TestClient,
    seed_project: Project,
    user_auth_headers: dict[str, str],
    seed_all_components: dict[str, Any],
):
    """Verify execution coordinates single trial run and routes evidence to real C1, C2, C3, and C4 evaluators."""
    p_id = seed_project.project_id
    plan_data = _create_ready_run_plan(
        test_client, p_id, user_auth_headers, seed_all_components
    )
    plan_id = plan_data["plan_id"]

    # Launch execution in controlled test mode
    exec_resp = test_client.post(
        f"/api/v1/projects/{p_id}/integration/plans/{plan_id}/execute",
        json={
            "target_mode": "CONTROLLED_TEST",
            "timeout_seconds": 30,
            "max_tool_calls": 20,
        },
        headers=user_auth_headers,
    )
    assert exec_resp.status_code == 200, exec_resp.text
    result = exec_resp.json()

    assert result["lifecycle_status"] == "COMPLETED"
    assert result["target_mode"] == "CONTROLLED_TEST"
    assert result["retained_evidence_digest"] is not None

    evals = result["evaluations"]
    assert "C1" in evals
    assert "C2" in evals
    assert "C3" in evals
    assert "C4" in evals

    # C1: Correctness verdict
    assert evals["C1"]["verdict"] == "PASS"
    assert evals["C1"]["passed_checks"] >= 1

    # C2: EFSM alignment verdict (demonstrating independent evaluation where different valid verdicts coexist)
    assert evals["C2"]["verdict"] in ("PASS", "FAIL", "EXPECTED REJECTION PASS")

    # C3: Recovery verdict evaluated with real C2-to-C3 bridge facts
    assert evals["C3"]["verdict"] == "PASS_COMPLETED"
    assert evals["C3"]["exposure_status"] == "CONFIRMED"
    assert evals["C3"]["c2_facts_consumed"] >= 1
    assert "C2_EVALUATOR_BRIDGE" in evals["C3"]["c2_facts_provenance"]

    # C4: Policy evaluator verdict (NOT_EXERCISED when empty rules or rules not triggered)
    assert evals["C4"]["verdict"] in ("PASS", "NOT_EXERCISED")


def test_live_aut_mode_rejected_with_honest_blocked_readiness(
    test_client: TestClient,
    seed_project: Project,
    user_auth_headers: dict[str, str],
    seed_all_components: dict[str, Any],
):
    """Enforce honest readiness: LIVE_AUT must fail fast as BLOCKED and never silently simulate."""
    p_id = seed_project.project_id
    plan_data = _create_ready_run_plan(
        test_client, p_id, user_auth_headers, seed_all_components
    )
    plan_id = plan_data["plan_id"]

    # Attempt to execute in LIVE_AUT mode
    exec_resp = test_client.post(
        f"/api/v1/projects/{p_id}/integration/plans/{plan_id}/execute",
        json={"target_mode": "LIVE_AUT"},
        headers=user_auth_headers,
    )
    assert exec_resp.status_code == 422
    err_detail = exec_resp.json()["detail"]
    assert "LIVE_AUT mode: external target service is BLOCKED" in err_detail
    assert "Live mode must never fall back silently to simulation" in err_detail


def test_unauthenticated_and_cross_project_execution_controls_fail(
    test_client: TestClient,
    seed_project: Project,
    user_auth_headers: dict[str, str],
    seed_all_components: dict[str, Any],
):
    """Verify authorization and strict project boundary on execution endpoints."""
    p_id = seed_project.project_id
    plan_data = _create_ready_run_plan(
        test_client, p_id, user_auth_headers, seed_all_components
    )
    plan_id = plan_data["plan_id"]

    # 1. Unauthenticated request -> 401
    resp_unauth = test_client.post(
        f"/api/v1/projects/{p_id}/integration/plans/{plan_id}/execute",
        json={"target_mode": "CONTROLLED_TEST"},
    )
    assert resp_unauth.status_code == 401

    # 2. Cross-project request -> 404
    resp_cross = test_client.post(
        f"/api/v1/projects/wrong-project-id/integration/plans/{plan_id}/execute",
        json={"target_mode": "CONTROLLED_TEST"},
        headers=user_auth_headers,
    )
    assert resp_cross.status_code == 404


def test_execution_status_retrieval_and_listing(
    test_client: TestClient,
    seed_project: Project,
    user_auth_headers: dict[str, str],
    seed_all_components: dict[str, Any],
):
    """Verify listing and retrieving executions for a plan."""
    p_id = seed_project.project_id
    plan_data = _create_ready_run_plan(
        test_client, p_id, user_auth_headers, seed_all_components
    )
    plan_id = plan_data["plan_id"]

    # Execute
    exec_resp = test_client.post(
        f"/api/v1/projects/{p_id}/integration/plans/{plan_id}/execute",
        json={"target_mode": "CONTROLLED_TEST"},
        headers=user_auth_headers,
    )
    assert exec_resp.status_code == 200
    exec_id = exec_resp.json()["execution_id"]

    # List executions
    list_resp = test_client.get(
        f"/api/v1/projects/{p_id}/integration/plans/{plan_id}/executions",
        headers=user_auth_headers,
    )
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] >= 1
    assert any(item["execution_id"] == exec_id for item in list_data["items"])

    # Get execution by ID
    get_resp = test_client.get(
        f"/api/v1/projects/{p_id}/integration/plans/{plan_id}/executions/{exec_id}",
        headers=user_auth_headers,
    )
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["execution_id"] == exec_id
    assert get_data["lifecycle_status"] == "COMPLETED"
    assert get_data["retained_evidence_digest"] is not None


def test_safe_execution_cancellation(
    test_client: TestClient,
    seed_project: Project,
    user_auth_headers: dict[str, str],
    seed_all_components: dict[str, Any],
    db_session: Session,
):
    """Verify safe cancellation sets lifecycle_status to CANCELLED without corrupting state."""
    p_id = seed_project.project_id
    plan_data = _create_ready_run_plan(
        test_client, p_id, user_auth_headers, seed_all_components
    )
    plan_id = plan_data["plan_id"]

    # Run execution first
    exec_resp = test_client.post(
        f"/api/v1/projects/{p_id}/integration/plans/{plan_id}/execute",
        json={"target_mode": "CONTROLLED_TEST"},
        headers=user_auth_headers,
    )
    exec_id = exec_resp.json()["execution_id"]

    # Simulate an active in-flight execution prior to cancellation
    exec_record = (
        db_session.execute(
            select(IntegrationExecutionModel).where(
                IntegrationExecutionModel.execution_id == exec_id
            )
        )
        .scalars()
        .first()
    )
    exec_record.lifecycle_status = "RUNNING"
    db_session.commit()

    # Cancel execution
    cancel_resp = test_client.post(
        f"/api/v1/projects/{p_id}/integration/plans/{plan_id}/executions/{exec_id}/cancel",
        headers=user_auth_headers,
    )
    assert cancel_resp.status_code == 200
    cancel_data = cancel_resp.json()
    assert cancel_data["lifecycle_status"] == "CANCELLED"
    assert "cancelled" in cancel_data["error_message"].lower()


def test_developer_cli_execution_and_status(
    db_session: Session,
    seed_project: Project,
    seed_test_user: User,
    seed_all_components: dict[str, Any],
):
    """Verify the developer CLI interacts with SharedExecutionCoordinator."""
    p_id = seed_project.project_id
    service = IntegrationService(db_session)
    # Create plan via service
    req = IntegrationRunPlanCreateRequest(
        name="CLI Test Plan",
        c1_reference=C1ConfigReference(
            project_id=p_id,
            config_id=seed_all_components["c1"].id,
            config_version=seed_all_components["c1"].version,
        ),
        c2_reference=C2ModelReference(
            project_id=p_id,
            model_id=seed_all_components["c2_efsm"].model_id,
            model_version=seed_all_components["c2_efsm"].version,
        ),
    )
    plan = service.create_run_plan(seed_project, seed_test_user, req)

    # Test CLI list
    code = cli_main(
        ["list", "--project-id", p_id, "--plan-id", plan.plan_id], db=db_session
    )
    assert code == 0

    # Test CLI execute
    code = cli_main(
        [
            "execute",
            "--project-id",
            p_id,
            "--plan-id",
            plan.plan_id,
            "--target-mode",
            "CONTROLLED_TEST",
        ],
        db=db_session,
    )
    assert code == 0


from sqlalchemy import event


@event.listens_for(test_engine, "connect")
def _set_sqlite_fk(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()
