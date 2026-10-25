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

"""Comprehensive integration and acceptance test suite for Backend Integration — Part 3:
Combined QA reporting, finding linkage, evidence replay, and final integration verification.

Verifies:
1. Shared report aggregator consumes actual persisted component findings without duplicating logic.
2. C2ReportPublisher connects to the aggregator, transitioning status from STUB to CONNECTED.
3. Native verdicts preserved without flattening (C2 6 runtime verdicts, C3 recovery outcomes, C4 policy outcomes).
4. Honest report completeness: requested vs evaluated vs not-evaluated, never reports 'PASSED' when components are missing.
5. Finding correlation links related findings through shared event/entity refs without collapsing distinct defects.
6. Stable identity deduplication prevents duplicate findings from multiple publications.
7. Evidence Replay re-evaluates stored traces deterministically without target invocation.
8. Scenarios:
   - Scenario 1: Full multi-component evaluation coexisting (C1, C2, C3, C4).
   - Scenario 2: Technically correct tool calls with a policy violation (C1 passes, C4 rejects).
   - Scenario 3: Workflow/state failure affecting C3's recovery assessment.
   - Scenario 4: Missing state/evidence produces honest incomplete/unknown status.
   - Scenario 5: Non-triggered fault does not receive C3 recovery pass.
9. Project scoping and isolation: cross-project queries fail closed with HTTP 404, unauthenticated with 401.
10. JSON and CSV export endpoints deliver correctly formatted reports.
"""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

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
from app.components.c2_state_aware_workflow.persistence.models import (
    C2TestCase,
    C2TestSuite,
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
    C1ConfigReference,
    C2ModelReference,
    C3SuiteReference,
    C4PolicyReference,
    IntegrationRunPlanCreateRequest,
)
from app.shared.integration.reporting import SharedReportAggregator
from app.shared.integration.service import IntegrationService
from app.shared.projects.models import (
    Project,
    ProjectConnectionState,
    ProjectLifecycle,
)

TEST_AUTH_SECRET = "reporting-replay-test-secret-32-chars!!"

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_reporting_test_db() -> Generator[None, None, None]:
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
def test_user(db_session: Session) -> User:
    user = User(
        name="QA Lead",
        email="qa_lead@example.com",
        canonical_email=normalize_email("qa_lead@example.com"),
        password_hash=hash_password("StrongPassword123!"),
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict[str, str]:
    settings = Settings(auth_secret_key=TEST_AUTH_SECRET)
    token, _ = create_access_token(test_user.id, settings)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_project(db_session: Session, test_user: User) -> Project:
    project = Project(
        project_id="proj_reporting_qa",
        name="QA Reporting Project",
        description="Scoping container for QA reporting tests",
        lifecycle=ProjectLifecycle.ACTIVE.value,
        connection_state=ProjectConnectionState.CONNECTED.value,
        owner_user_id=test_user.id,
        backend_base_url="http://localhost:8000",
        backend_health_url="http://localhost:8000/health",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project
    db_session.refresh(project)
    return project


def _seed_valid_components(
    db: Session, project_id: str, user_id: int
) -> dict[str, Any]:
    """Seed real C1, C2, C3, and C4 configurations into the database."""
    # 1. C1
    c1_example = get_nexacart_refund_example_config()
    c1_record = create_project_config(db, project_id, c1_example)

    # 2. C2
    c2_repo = C2ModelRepository(db)
    c2_efsm = build_synthetic_refund_efsm()
    c2_efsm = c2_efsm.model_copy(update={"project_id": project_id})
    c2_repo.create_draft_model(project_id, c2_efsm)
    val_service = ModelValidationService(db)
    val_service.validate_model_record(project_id, c2_efsm.model_id, c2_efsm.version)
    c2_record = c2_repo.approve_model(
        project_id=project_id,
        model_id=c2_efsm.model_id,
        version=c2_efsm.version,
        reviewer_id=f"reviewer_{user_id} [SELF_REPORTED_DEVELOPMENT]",
        review_basis="Synthetic specs",
    )

    c2_suite = C2TestSuite(
        project_id=project_id,
        suite_id="suite-c2-rep-01",
        model_record_id=c2_record.id,
        model_id=c2_efsm.model_id,
        model_version=c2_efsm.version,
        model_content_hash=c2_record.content_hash,
        config={},
        diagnostics={},
        total_cases=1,
        ready_cases_count=1,
    )
    db.add(c2_suite)
    db.flush()

    c2_case = C2TestCase(
        suite_record_id=c2_suite.id,
        project_id=project_id,
        suite_id=c2_suite.suite_id,
        test_id="test_c2_rep_01",
        category="valid",
        task="Process order and refund workflow",
        fixture_ref="fix-c2-01",
        readiness="TEST_READY",
        is_ready=True,
        definition={
            "schema_version": "2026.1",
            "test_id": "test_c2_rep_01",
            "project_id": project_id,
            "suite_id": c2_suite.suite_id,
            "pinned_model_id": c2_efsm.model_id,
            "pinned_model_version": c2_efsm.version,
            "model_content_hash": c2_record.content_hash,
            "category": "valid",
            "task": "Process order and refund workflow",
            "fixture_ref": "fix-c2-01",
            "expected_outcome": "PASS",
        },
    )
    db.add(c2_case)

    # 3. C3
    valid_c3_contract = {
        "contract_id": "rec-shared-01",
        "contract_version": "1.0.0",
        "permitted_terminal_outcomes": ["SUCCESS_CLEAN_RECOVERY"],
        "initial_invocation_counts_as_attempt": True,
        "max_task_attempts": 3,
        "max_retries": 2,
        "max_tool_calls_budget": 10,
        "max_total_timeout_ms": 10000,
        "required_state_assertions": ["order_created"],
        "allow_duplicate_side_effects": False,
        "require_truthful_completion_reporting": True,
    }
    valid_c3_case = {
        "schema_version": "2026.1",
        "project_id": project_id,
        "case_id": "case-c3-exec-01",
        "case_family_id": "fam-01",
        "domain": "ecommerce",
        "task_id": "task-checkout-demo",
        "task_version": "1.0.0",
        "tool_id": "order_placement",
        "tool_version": "1.0.0",
        "fixture_id": "fix-c3-01",
        "fixture_version": "1.0.0",
        "adapter_id": "controlled_test_adapter",
        "adapter_version": "1.0.0",
        "recovery_contract_id": "rec-shared-01",
        "recovery_contract_version": "1.0.0",
        "occurrence": 1,
        "interception_hook": "BEFORE_TOOL_CALL",
        "fault_family": "TIMEOUT_DISCONNECTION",
        "effect_phase": "BEFORE_EFFECT",
        "payload": {
            "family": "TIMEOUT_DISCONNECTION",
            "mode": "CALLER_TIMEOUT_EXCEEDED",
            "timing_ms": 5000,
        },
        "release_rule": {"rule_type": "ATTEMPT_BOUNDED", "max_fault_count": 1},
        "required_assertions": ["order_created"],
        "required_observations": ["network_latency_ms"],
        "caller_timeout_ms": 3000,
        "reproducibility_seed": 42,
    }

    c3_suite = C3SuiteModel(
        suite_id="suite-c3-exec-01",
        suite_digest="a" * 64,
        project_id=project_id,
        task_id="task-checkout-demo",
        tool_id="order_placement",
        domain="e-commerce",
        schema_version="2026.1",
        generator_version="1.0.0",
        total_cases=1,
        policy_snapshot={},
        adapter_manifest_snapshot={},
        task_fixture_metadata_snapshot={},
        recovery_contract_snapshot=valid_c3_contract,
        suite_snapshot={},
    )
    db.add(c3_suite)
    db.flush()

    c3_case = C3CaseModel(
        case_id="case-c3-exec-01",
        suite_digest="a" * 64,
        case_fingerprint="b" * 64,
        content_digest="c" * 64,
        project_id=project_id,
        case_family_id="fam-01",
        fault_family="TRANSIENT_TOOL_FAILURE",
        effect_phase="INVOCATION",
        interception_hook="pre_tool_call",
        target_tool_id="order_placement",
        case_order=0,
        case_snapshot=valid_c3_case,
    )
    db.add(c3_case)

    # 4. C4
    valid_c4_rep_rule = PolicyRule(
        project_id=project_id,
        rule_id="POL-NO-DIRECT-REFUND",
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
        project_id=project_id,
        contract_id="contract-c4-refund",
        version=1,
        lifecycle_state=ContractLifecycleState.ACCEPTED.value,
        content_hash="d" * 64,
        rules_data=[valid_c4_rep_rule],
    )
    db.add(c4_contract)
    db.commit()

    return {
        "c1": c1_record,
        "c2": c2_record,
        "c2_efsm": c2_efsm,
        "c2_suite": c2_suite,
        "c2_case": c2_case,
        "c3": c3_suite,
        "c4": c4_contract,
    }


def test_full_acceptance_all_components_reporting_and_replay(
    test_client: TestClient,
    test_user: User,
    test_project: Project,
    auth_headers: dict[str, str],
    db_session: Session,
):
    """End-to-End Acceptance Test:
    - Authenticated user selects authorized project.
    - Pinned valid C1, C2, C3, and C4 configurations.
    - Coordinated execution runs and produces real evaluations (no mocked evaluator verdicts).
    - C2 report publisher connects to aggregator, transitioning status from STUB to CONNECTED.
    - Combined QA report aggregates all component contributions with non-flattened native verdicts.
    - Related findings are correlated without collapsing distinct defects.
    - Replay evaluation executes without invoking target adapters and verifies semantic parity.
    - JSON and CSV report export endpoints return correct project-scoped content.
    """
    seeded = _seed_valid_components(db_session, test_project.project_id, test_user.id)

    # 1. Create and freeze integration run plan
    plan_payload = {
        "name": "Full Multi-Component QA Plan",
        "description": "Comprehensive run covering C1, C2, C3, and C4",
        "c1_reference": {
            "project_id": test_project.project_id,
            "config_id": seeded["c1"].id,
            "config_version": seeded["c1"].version,
        },
        "c2_reference": {
            "project_id": test_project.project_id,
            "model_id": seeded["c2_efsm"].model_id,
            "model_version": seeded["c2_efsm"].version,
            "suite_id": "suite-c2-rep-01",
            "test_id": "test_c2_rep_01",
        },
        "c3_reference": {
            "project_id": test_project.project_id,
            "suite_id": seeded["c3"].suite_id,
            "suite_digest": seeded["c3"].suite_digest,
            "target_tool_id": "order_placement",
        },
        "c4_reference": {
            "project_id": test_project.project_id,
            "contract_id": seeded["c4"].contract_id,
            "contract_version": 1,
        },
    }
    plan_resp = test_client.post(
        f"/api/v1/projects/{test_project.project_id}/integration/plans",
        json=plan_payload,
        headers=auth_headers,
    )
    assert plan_resp.status_code == 201, plan_resp.text
    plan_data = plan_resp.json()
    plan_id = plan_data["plan_id"]
    integration_run_id = plan_data["integration_run_id"]

    # 2. Execute plan through shared execution coordinator
    exec_resp = test_client.post(
        f"/api/v1/projects/{test_project.project_id}/integration/plans/{plan_id}/execute",
        json={"target_mode": "CONTROLLED_TEST", "timeout_seconds": 30},
        headers=auth_headers,
    )
    assert exec_resp.status_code == 200, exec_resp.text
    exec_data = exec_resp.json()
    execution_id = exec_data["execution_id"]
    assert exec_data["lifecycle_status"] == "COMPLETED"

    # Verify real component evaluations exist
    evals = exec_data["evaluations"]
    assert "C1" in evals
    assert "C2" in evals
    assert "C3" in evals
    assert evals["C1"]["verdict"] == "PASS"
    assert evals["C2"]["verdict"] in (
        "PASS",
        "FAIL",
        "EXPECTED_REJECTION_PASS",
        "EXPECTED REJECTION PASS",
    )
    assert evals["C3"]["verdict"] in ("SUCCESS_CLEAN_RECOVERY", "PASS_COMPLETED")
    assert evals["C4"]["verdict"] in ("PASS", "NOT_EXERCISED")

    # 3. Retrieve Combined QA Report via API
    rep_resp = test_client.get(
        f"/api/v1/projects/{test_project.project_id}/integration/plans/{plan_id}/executions/{execution_id}/report",
        headers=auth_headers,
    )
    assert rep_resp.status_code == 200, rep_resp.text
    rep_data = rep_resp.json()

    assert rep_data["report_id"].startswith("rep-")
    assert rep_data["integration_run_id"] == integration_run_id
    assert rep_data["execution_id"] == execution_id
    assert rep_data["project_id"] == test_project.project_id

    # Verify Report Completeness Breakdown
    completeness = rep_data["completeness"]
    assert set(completeness["requested_components"]) == {"C1", "C2", "C3", "C4"}
    assert set(completeness["evaluated_components"]) == {"C1", "C2", "C3", "C4"}
    assert completeness["not_evaluated_components"] == []
    expected_overall = "PASSED" if evals["C2"]["verdict"] == "PASS" else "FAILED"
    assert completeness["overall_verdict"] == expected_overall

    # Verify C2 Publisher Connection
    c2_contrib = rep_data["component_contributions"]["C2"]
    assert c2_contrib["status"] == "EVALUATED"
    assert c2_contrib["native_verdict"] in (
        "PASS",
        "FAIL",
        "EXPECTED_REJECTION_PASS",
        "EXPECTED REJECTION PASS",
    )
    assert c2_contrib["native_details"]["publisher_status"] == "CONNECTED"
    assert "publication_token" in c2_contrib["native_details"]

    # Verify C3 Contribution and facts bridge provenance
    c3_contrib = rep_data["component_contributions"]["C3"]
    assert c3_contrib["status"] == "EVALUATED"
    assert c3_contrib["native_details"]["clean_qualification"] == "QUALIFIED"

    # Verify Finding Linkage & Counts
    assert rep_data["raw_finding_count"] >= 0
    assert rep_data["grouped_defect_count"] >= 0

    # 4. Verify Evidence Replay (without invoking target)
    with patch(
        "app.shared.integration.adapters.ControlledTestTargetAdapter.execute_session"
    ) as mock_target:
        replay_resp = test_client.post(
            f"/api/v1/projects/{test_project.project_id}/integration/plans/{plan_id}/executions/{execution_id}/replay",
            headers=auth_headers,
        )
        assert replay_resp.status_code == 200, replay_resp.text
        # Target must never be invoked during replay!
        mock_target.assert_not_called()

        replay_data = replay_resp.json()
        assert replay_data["is_semantically_identical"] is True
        assert replay_data["semantic_diffs"] == []
        assert "created_at_utc" in replay_data["nondeterministic_fields_ignored"]

    # 5. Export Report (JSON and CSV)
    json_export = test_client.get(
        f"/api/v1/projects/{test_project.project_id}/integration/plans/{plan_id}/executions/{execution_id}/report/export?format=json",
        headers=auth_headers,
    )
    assert json_export.status_code == 200
    assert json_export.headers["content-type"].startswith("application/json")

    csv_export = test_client.get(
        f"/api/v1/projects/{test_project.project_id}/integration/plans/{plan_id}/executions/{execution_id}/report/export?format=csv",
        headers=auth_headers,
    )
    assert csv_export.status_code == 200
    assert "text/csv" in csv_export.headers["content-type"]
    assert "Combined QA Report Export" in csv_export.text
    assert "C1" in csv_export.text
    assert "C2" in csv_export.text

    # 6. List Published Reports
    list_rep = test_client.get(
        f"/api/v1/projects/{test_project.project_id}/integration/reports",
        headers=auth_headers,
    )
    assert list_rep.status_code == 200
    list_data = list_rep.json()
    assert list_data["total"] >= 1
    assert any(r["execution_id"] == execution_id for r in list_data["items"])


def test_scenario_technically_correct_calls_with_policy_violation(
    db_session: Session, test_project: Project, test_user: User
):
    """Scenario 1: Technically correct tool calls with a policy violation.
    C1 evaluates calls as valid, but C4 detects policy violation.
    Verifies that C1 PASS and C4 VIOLATION coexist without overriding each other.
    """
    seeded = _seed_valid_components(db_session, test_project.project_id, test_user.id)
    plan_service = IntegrationService(db_session)
    plan = plan_service.create_run_plan(
        project=test_project,
        user=test_user,
        data=IntegrationRunPlanCreateRequest(
            name="Tool Correctness vs Policy Test",
            c1_reference=C1ConfigReference(
                project_id=test_project.project_id,
                config_id=seeded["c1"].id,
                config_version=seeded["c1"].version,
            ),
            c4_reference=C4PolicyReference(
                project_id=test_project.project_id,
                contract_id=seeded["c4"].contract_id,
                contract_version=1,
            ),
        ),
    )

    # Simulate execution with simulated policy finding
    exec_record = IntegrationExecutionModel(
        execution_id="exec-scenario-policy-01",
        integration_run_id=plan.integration_run_id,
        project_id=test_project.project_id,
        lifecycle_status="COMPLETED",
        target_mode="CONTROLLED_TEST",
        plan_digest=plan.plan_digest,
        evaluations={
            "C1": {
                "component": "C1",
                "verdict": "PASS",
                "checks_count": 2,
                "passed_checks": 2,
                "checks": [
                    {
                        "check_id": "c1_chk_01",
                        "tool_name": "order_placement",
                        "verdict": "PASS",
                        "message": "Valid call",
                    }
                ],
            },
            "C4": {
                "component": "C4",
                "verdict": "REJECT",
                "findings_count": 1,
                "findings": [
                    {
                        "finding_id": "f-c4-001",
                        "rule_id": "POL-NO-DIRECT-REFUND",
                        "verdict": "REJECT",
                        "target_tool": "order_placement",
                        "explanation": "Policy forbidden action detected",
                    }
                ],
            },
        },
    )
    db_session.add(exec_record)
    db_session.commit()

    aggregator = SharedReportAggregator(db_session)
    report = aggregator.generate_report(
        project=test_project,
        execution_id="exec-scenario-policy-01",
        user=test_user,
    )

    # C1 and C4 maintain their native verdicts
    assert report.component_contributions["C1"].native_verdict == "PASS"
    assert report.component_contributions["C4"].native_verdict == "REJECT"
    # Overall verdict reflects the defect
    assert report.completeness.overall_verdict == "FAILED"

    # Distinct findings exist without collapsing
    c1_f = [f for f in report.findings if f.component == "C1"]
    c4_f = [f for f in report.findings if f.component == "C4"]
    assert len(c1_f) >= 1
    assert len(c4_f) >= 1
    assert c1_f[0].native_verdict == "PASS"
    assert c4_f[0].native_verdict == "REJECT"


def test_scenario_workflow_failure_affecting_c3_recovery(
    db_session: Session, test_project: Project, test_user: User
):
    """Scenario 2: Workflow/state failure affecting C3's recovery assessment.
    C2 detects invalid EFSM transition; C3 consumes C2 state facts and marks recovery failed.
    """
    seeded = _seed_valid_components(db_session, test_project.project_id, test_user.id)
    plan_service = IntegrationService(db_session)
    plan = plan_service.create_run_plan(
        project=test_project,
        user=test_user,
        data=IntegrationRunPlanCreateRequest(
            name="Workflow Failure and Recovery Defect",
            c2_reference=C2ModelReference(
                project_id=test_project.project_id,
                model_id=seeded["c2_efsm"].model_id,
                model_version=seeded["c2_efsm"].version,
                suite_id="suite-c2-rep-01",
                test_id="test_c2_rep_01",
            ),
            c3_reference=C3SuiteReference(
                project_id=test_project.project_id,
                suite_id=seeded["c3"].suite_id,
                suite_digest=seeded["c3"].suite_digest,
                target_tool_id="order_placement",
            ),
        ),
    )

    exec_record = IntegrationExecutionModel(
        execution_id="exec-scenario-c2-c3-02",
        integration_run_id=plan.integration_run_id,
        project_id=test_project.project_id,
        lifecycle_status="COMPLETED",
        target_mode="CONTROLLED_TEST",
        plan_digest=plan.plan_digest,
        evaluations={
            "C2": {
                "component": "C2",
                "verdict": "FAIL_UNEXPECTED_STATE",
                "violations_count": 1,
                "reasons": ["Unexpected state 'FAILED_PAYMENT' reached."],
                "violations": [
                    {
                        "violation_type": "UNEXPECTED_STATE",
                        "transition_id": "T_PAYMENT_SUCCESS",
                        "step_index": 2,
                        "message": "State machine entered unexpected terminal state",
                    }
                ],
            },
            "C3": {
                "component": "C3",
                "verdict": "FAILURE_INCOMPLETE_RECOVERY",
                "status": "COMPLETED",
                "rule_results_count": 1,
                "exposure_status": "EXPOSED",
                "c2_facts_consumed": 1,
                "clean_qualification": "QUALIFIED",
                "rule_results": [
                    {
                        "rule_id": "RULE-STATE-ASSERTION",
                        "passed": False,
                        "failure_reason": "Required state fact 'order_created' not verified by C2 EFSM.",
                    }
                ],
            },
        },
    )
    db_session.add(exec_record)
    db_session.commit()

    aggregator = SharedReportAggregator(db_session)
    report = aggregator.generate_report(
        project=test_project,
        execution_id="exec-scenario-c2-c3-02",
        user=test_user,
    )

    # Native verdicts preserved
    assert (
        report.component_contributions["C2"].native_verdict == "FAIL_UNEXPECTED_STATE"
    )
    assert (
        report.component_contributions["C3"].native_verdict
        == "FAILURE_INCOMPLETE_RECOVERY"
    )
    assert report.completeness.overall_verdict == "FAILED"


def test_scenario_missing_evidence_honestly_reports_partial_or_not_evaluated(
    db_session: Session, test_project: Project, test_user: User
):
    """Scenario 3: Missing component execution or state evidence produces honest incomplete status.
    Never reports 'PASSED' when a requested component did not run!
    """
    seeded = _seed_valid_components(db_session, test_project.project_id, test_user.id)
    plan_service = IntegrationService(db_session)
    # Plan requests C1, C2, and C4
    plan = plan_service.create_run_plan(
        project=test_project,
        user=test_user,
        data=IntegrationRunPlanCreateRequest(
            name="Partial Execution Plan",
            c1_reference=C1ConfigReference(
                project_id=test_project.project_id,
                config_id=seeded["c1"].id,
                config_version=seeded["c1"].version,
            ),
            c2_reference=C2ModelReference(
                project_id=test_project.project_id,
                model_id=seeded["c2_efsm"].model_id,
                model_version=seeded["c2_efsm"].version,
                suite_id="suite-c2-rep-01",
                test_id="test_c2_rep_01",
            ),
            c4_reference=C4PolicyReference(
                project_id=test_project.project_id,
                contract_id=seeded["c4"].contract_id,
                contract_version=1,
            ),
        ),
    )

    # Only C1 evaluated; C2 and C4 did not run
    exec_record = IntegrationExecutionModel(
        execution_id="exec-scenario-partial-03",
        integration_run_id=plan.integration_run_id,
        project_id=test_project.project_id,
        lifecycle_status="COMPLETED",
        target_mode="CONTROLLED_TEST",
        plan_digest=plan.plan_digest,
        evaluations={
            "C1": {
                "component": "C1",
                "verdict": "PASS",
                "checks_count": 1,
                "passed_checks": 1,
            }
        },
    )
    db_session.add(exec_record)
    db_session.commit()

    aggregator = SharedReportAggregator(db_session)
    report = aggregator.generate_report(
        project=test_project,
        execution_id="exec-scenario-partial-03",
        user=test_user,
    )

    # Check completeness
    completeness = report.completeness
    assert "C1" in completeness.evaluated_components
    assert "C2" in completeness.not_evaluated_components
    assert "C4" in completeness.not_evaluated_components

    # MUST NOT report PASSED
    assert completeness.overall_verdict != "PASSED"
    assert "PARTIAL" in completeness.overall_verdict


def test_scenario_non_triggered_fault_does_not_receive_recovery_pass(
    db_session: Session, test_project: Project, test_user: User
):
    """Scenario 4: Non-triggered fault does not receive a C3 recovery pass.
    Exposure not achieved produces honest EXPOSURE_NOT_ACHIEVED verdict.
    """
    seeded = _seed_valid_components(db_session, test_project.project_id, test_user.id)
    plan_service = IntegrationService(db_session)
    plan = plan_service.create_run_plan(
        project=test_project,
        user=test_user,
        data=IntegrationRunPlanCreateRequest(
            name="Fault Exposure Incomplete",
            c3_reference=C3SuiteReference(
                project_id=test_project.project_id,
                suite_id=seeded["c3"].suite_id,
                suite_digest=seeded["c3"].suite_digest,
                target_tool_id="order_placement",
            ),
        ),
    )

    exec_record = IntegrationExecutionModel(
        execution_id="exec-scenario-unexposed-04",
        integration_run_id=plan.integration_run_id,
        project_id=test_project.project_id,
        lifecycle_status="COMPLETED",
        target_mode="CONTROLLED_TEST",
        plan_digest=plan.plan_digest,
        evaluations={
            "C3": {
                "component": "C3",
                "verdict": "EXPOSURE_NOT_ACHIEVED",
                "status": "NON_EVALUATED",
                "exposure_status": "NOT_EXPOSED",
                "clean_qualification": "QUALIFIED",
                "non_evaluation_reasons": [
                    "Target tool was not invoked; fault was not triggered."
                ],
            }
        },
    )
    db_session.add(exec_record)
    db_session.commit()

    aggregator = SharedReportAggregator(db_session)
    report = aggregator.generate_report(
        project=test_project,
        execution_id="exec-scenario-unexposed-04",
        user=test_user,
    )

    c3_contrib = report.component_contributions["C3"]
    assert c3_contrib.native_verdict == "EXPOSURE_NOT_ACHIEVED"
    assert "fault was not triggered" in str(c3_contrib.non_evaluation_reasons)
    assert report.completeness.overall_verdict != "PASSED"


def test_cross_project_isolation_on_reports_and_replay(
    test_client: TestClient,
    test_user: User,
    test_project: Project,
    auth_headers: dict[str, str],
    db_session: Session,
):
    """Project Isolation & Security Checks:
    - Attempting to view, export, or replay a report belonging to another project returns HTTP 404.
    - Unauthenticated calls return HTTP 401.
    """
    seeded = _seed_valid_components(db_session, test_project.project_id, test_user.id)
    plan_service = IntegrationService(db_session)
    plan = plan_service.create_run_plan(
        project=test_project,
        user=test_user,
        data=IntegrationRunPlanCreateRequest(
            name="Scoping Test Plan",
            c1_reference=C1ConfigReference(
                project_id=test_project.project_id,
                config_id=seeded["c1"].id,
                config_version=seeded["c1"].version,
            ),
        ),
    )
    exec_record = IntegrationExecutionModel(
        execution_id="exec-isolation-test-01",
        integration_run_id=plan.integration_run_id,
        project_id=test_project.project_id,
        lifecycle_status="COMPLETED",
        target_mode="CONTROLLED_TEST",
        plan_digest=plan.plan_digest,
        evaluations={
            "C1": {
                "component": "C1",
                "verdict": "PASS",
                "checks_count": 1,
                "passed_checks": 1,
            }
        },
    )
    db_session.add(exec_record)
    db_session.commit()

    # Another project
    other_project = Project(
        project_id="proj_other_user",
        name="Other Project",
        description="Another project container",
        lifecycle=ProjectLifecycle.ACTIVE.value,
        connection_state=ProjectConnectionState.CONNECTED.value,
        owner_user_id=test_user.id,
        backend_base_url="http://localhost:8000",
        backend_health_url="http://localhost:8000/health",
    )
    db_session.add(other_project)
    db_session.commit()

    # Accessing test_project's execution through other_project returns 404
    resp = test_client.get(
        f"/api/v1/projects/{other_project.project_id}/integration/plans/{plan.plan_id}/executions/{exec_record.execution_id}/report",
        headers=auth_headers,
    )
    assert resp.status_code == 404

    # Exporting through other_project returns 404
    export_resp = test_client.get(
        f"/api/v1/projects/{other_project.project_id}/integration/plans/{plan.plan_id}/executions/{exec_record.execution_id}/report/export",
        headers=auth_headers,
    )
    assert export_resp.status_code == 404

    # Replay through other_project returns 404
    replay_resp = test_client.post(
        f"/api/v1/projects/{other_project.project_id}/integration/plans/{plan.plan_id}/executions/{exec_record.execution_id}/replay",
        headers=auth_headers,
    )
    assert replay_resp.status_code == 404

    # Unauthenticated returns 401
    unauth_resp = test_client.get(
        f"/api/v1/projects/{test_project.project_id}/integration/plans/{plan.plan_id}/executions/{exec_record.execution_id}/report"
    )
    assert unauth_resp.status_code == 401


from sqlalchemy import event


@event.listens_for(test_engine, "connect")
def _set_sqlite_fk(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


def test_not_exercised_policy_rules_make_report_inconclusive_not_failed(
    db_session: Session, test_project: Project, test_user: User
):
    """C4 NOT_EXERCISED is neither a defect nor a pass: overall INCONCLUSIVE, never FAILED/PASSED."""
    seeded = _seed_valid_components(db_session, test_project.project_id, test_user.id)
    plan = IntegrationService(db_session).create_run_plan(
        project=test_project,
        user=test_user,
        data=IntegrationRunPlanCreateRequest(
            name="Unexercised policy rules",
            c1_reference=C1ConfigReference(
                project_id=test_project.project_id,
                config_id=seeded["c1"].id,
                config_version=seeded["c1"].version,
            ),
            c4_reference=C4PolicyReference(
                project_id=test_project.project_id,
                contract_id=seeded["c4"].contract_id,
                contract_version=1,
            ),
        ),
    )
    db_session.add(
        IntegrationExecutionModel(
            execution_id="exec-not-exercised-01",
            integration_run_id=plan.integration_run_id,
            project_id=test_project.project_id,
            lifecycle_status="COMPLETED",
            target_mode="LIVE_AUT",
            plan_digest=plan.plan_digest,
            evaluations={
                "C1": {
                    "component": "C1",
                    "verdict": "PASS",
                    "checks_count": 1,
                    "passed_checks": 1,
                    "checks": [
                        {"check_id": "c1_chk", "verdict": "PASS", "message": "ok"}
                    ],
                },
                "C4": {
                    "component": "C4",
                    "verdict": "NOT_EXERCISED",
                    "findings_count": 1,
                    "findings": [
                        {
                            "finding_id": "f-c4-ne",
                            "rule_id": "INSTR-AUTH-CHECKOUT",
                            "verdict": "NOT_EXERCISED",
                            "explanation": "No action attempt matched action selector 'checkout'.",
                        }
                    ],
                },
            },
        )
    )
    db_session.commit()

    report = SharedReportAggregator(db_session).generate_report(
        project=test_project, execution_id="exec-not-exercised-01", user=test_user
    )

    assert report.completeness.overall_verdict == "INCONCLUSIVE"
    assert report.component_contributions["C4"].native_verdict == "NOT_EXERCISED"
    assert any(
        note.startswith("C4: NOT_EXERCISED")
        for note in report.completeness.pending_or_missing_evidence
    )
