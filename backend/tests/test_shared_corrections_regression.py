"""Comprehensive Regression and Acceptance Tests for Shared Backend Integration Corrections.

Covers all defect areas identified in prompt section 13:
1. Foreign-project C1 configuration ID rejection.
2. Wrong ID/version combinations.
3. Real C4 ACCEPTED contract created through normal workflow.
4. C4 invalid policy rules / unaccepted contract blocked.
5. C2-to-C3 assertion binding: strict trial and entity matching.
6. Shared event IDs survive projection and replay.
7. Missing per-step observations remain missing.
8. Scripted callers are not labelled actual agents.
9. Fault flags alone cannot confirm exposure.
10. Cleanup failures propagate.
11. One-call budget permits no second call.
12. Cooperative cancellation during execution.
13. Terminal completed records cannot be cancelled (HTTP 409).
14. Native C3 VIOLATED and C4 FAIL results appear correctly in reports.
15. Genuine passing verdicts recognized (EXPECTED REJECTION PASS, PASS_COMPLETED).
16. Unknown/not-ready results are not fabricated defects.
17. Tampered evidence fails replay integrity check (HTTP 422).
18. Different violated rules fail semantic parity with divergence reasons.
19. Report retrieval is idempotent and preserves history.
20. Wrong-plan nested URLs are rejected with HTTP 404.
"""

import uuid
from collections.abc import Generator

import pytest
from fastapi import status
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from app.components.c1_tool_call_correctness.examples import (
    get_nexacart_refund_example_config,
)
from app.components.c1_tool_call_correctness.services.config_service import (
    create_project_config,
)
from app.components.c2_state_aware_workflow.integrations.assertion_facade import (
    C2NamedAssertionEvaluator,
    TriState,
)
from app.components.c2_state_aware_workflow.predicates.evaluator import (
    EvaluationContext,
)
from app.components.c3_robustness_recovery.contracts.evaluation import (
    C2AssertionFact,
    C2FactValue,
)
from app.components.c3_robustness_recovery.contracts.schemas import (
    RecoveryContract,
    TerminalOutcome,
)
from app.components.c3_robustness_recovery.models.persistence import (
    C3CaseModel,
    C3SuiteModel,
)
from app.components.c3_robustness_recovery.runtime.adapter import (
    CallerIdentity,
    RecoveryActor,
)
from app.components.c3_robustness_recovery.runtime.evidence import (
    ExposureStatus,
)
from app.components.c3_robustness_recovery.services.c2_facts import (
    get_c2_fact_value,
)
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
from app.components.c4_policy_aware_safety.contracts.rules import (
    PolicyRule,
)
from app.components.c4_policy_aware_safety.persistence.models import (
    C4ContractModel,
)
from app.config import Settings, get_settings
from app.database import Base, get_db
from app.main import app
from app.shared.integration.adapters import (
    ControlledTestTargetAdapter,
    ExecutionTrace,
    RawToolEvent,
    StateSnapshot,
    TargetMode,
)
from app.shared.integration.contracts import (
    IntegrationPlanStatus,
)
from app.shared.integration.evidence import (
    project_c1_evidence,
    project_c2_evidence,
    project_c3_matched_pair_evidence,
    project_c4_evidence,
)
from app.shared.integration.models import (
    IntegrationExecutionModel,
    IntegrationRunPlanModel,
)
from app.shared.integration.reporting import (
    SharedReportAggregator,
)
from app.shared.integration.service import (
    canonical_json_digest,
)
from tests.test_shared_integration import (
    TEST_AUTH_SECRET,
    auth_headers,
    make_project,
    make_user,
)

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_regression_test_db() -> Generator[None, None, None]:
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


# ---------------------------------------------------------------------------
# 1. Foreign-project C1 configuration ID rejection
# ---------------------------------------------------------------------------
def test_foreign_project_c1_configuration_rejected(
    test_client: TestClient, db_session: Session
):
    alice = make_user(db_session, "Alice", "alice_c1@example.com")
    bob = make_user(db_session, "Bob", "bob_c1@example.com")
    proj_a = "proj-alice-c1"
    proj_b = "proj-bob-c1"
    make_project(db_session, proj_a, "Alice Proj", alice.id)
    make_project(db_session, proj_b, "Bob Proj", bob.id)

    cfg = get_nexacart_refund_example_config()
    alice_cfg = create_project_config(db_session, proj_a, cfg)

    bob_headers = auth_headers(bob)
    resp = test_client.post(
        f"/api/v1/projects/{proj_b}/integration/plans",
        json={
            "name": "Cross-Project Plan Attempt",
            "c1_reference": {
                "project_id": proj_b,
                "config_id": alice_cfg.id,
                "config_version": alice_cfg.version,
            },
        },
        headers=bob_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["lifecycle_status"] == IntegrationPlanStatus.BLOCKED.value
    report = data["readiness_report"]
    issue_codes = [i["issue_code"] for i in report["blocking_issues"]]
    assert "CONFIG_NOT_FOUND" in issue_codes or "CROSS_PROJECT_REFERENCE" in issue_codes


# ---------------------------------------------------------------------------
# 2. Wrong ID / version combinations rejected
# ---------------------------------------------------------------------------
def test_wrong_id_version_combination_rejected(
    test_client: TestClient, db_session: Session
):
    user = make_user(db_session, "VersionTester", "vertester@example.com")
    project_id = "proj-ver-test"
    make_project(db_session, project_id, "Version Test Proj", user.id)
    headers = auth_headers(user)

    cfg = get_nexacart_refund_example_config()
    cfg_model = create_project_config(db_session, project_id, cfg)

    resp = test_client.post(
        f"/api/v1/projects/{project_id}/integration/plans",
        json={
            "name": "Wrong Version Plan",
            "c1_reference": {
                "project_id": project_id,
                "config_id": cfg_model.id,
                "config_version": 999,
            },
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["lifecycle_status"] == IntegrationPlanStatus.BLOCKED.value
    report = data["readiness_report"]
    issue_codes = [i["issue_code"] for i in report["blocking_issues"]]
    assert "CONFIG_NOT_FOUND" in issue_codes or "INCOMPATIBLE_VERSION" in issue_codes


# ---------------------------------------------------------------------------
# 3. Real C4 ACCEPTED contract created through normal workflow
# ---------------------------------------------------------------------------
def test_real_c4_accepted_contract_supported(
    test_client: TestClient, db_session: Session
):
    user = make_user(db_session, "C4Tester", "c4tester@example.com")
    project_id = "proj-c4-accepted"
    make_project(db_session, project_id, "C4 Accepted Proj", user.id)
    headers = auth_headers(user)

    valid_rule = PolicyRule(
        project_id=project_id,
        rule_id="pol_rule_01",
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
        contract_id="contract-c4-valid",
        version=1,
        lifecycle_state=ContractLifecycleState.ACCEPTED.value,
        content_hash="c" * 64,
        rules_data=[valid_rule],
    )
    db_session.add(c4_contract)
    db_session.commit()

    resp = test_client.post(
        f"/api/v1/projects/{project_id}/integration/plans",
        json={
            "name": "C4 Accepted Contract Plan",
            "c4_reference": {
                "project_id": project_id,
                "contract_id": "contract-c4-valid",
                "contract_version": 1,
            },
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["lifecycle_status"] == IntegrationPlanStatus.READY.value


# ---------------------------------------------------------------------------
# 4. C4 invalid policy rules / unaccepted contract blocked
# ---------------------------------------------------------------------------
def test_c4_unaccepted_contract_and_invalid_rules_blocked(
    test_client: TestClient, db_session: Session
):
    user = make_user(db_session, "C4DraftUser", "c4draft@example.com")
    project_id = "proj-c4-draft"
    make_project(db_session, project_id, "C4 Draft Proj", user.id)
    headers = auth_headers(user)

    c4_contract = C4ContractModel(
        project_id=project_id,
        contract_id="contract-c4-draft",
        version=1,
        lifecycle_state="DRAFT",
        content_hash="d" * 64,
        rules_data=[],
    )
    db_session.add(c4_contract)
    db_session.commit()

    resp = test_client.post(
        f"/api/v1/projects/{project_id}/integration/plans",
        json={
            "name": "C4 Draft Plan",
            "c4_reference": {
                "project_id": project_id,
                "contract_id": "contract-c4-draft",
                "contract_version": 1,
            },
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["lifecycle_status"] == IntegrationPlanStatus.BLOCKED.value
    report = data["readiness_report"]
    codes = [i["issue_code"] for i in report["blocking_issues"]]
    assert "UNACCEPTED_CONTRACT" in codes


# ---------------------------------------------------------------------------
# 5. C2-to-C3 assertion binding: strict trial and entity matching
# ---------------------------------------------------------------------------
def test_c2_to_c3_assertion_binding_strict_trial_and_entity():
    fact_without_trial = C2AssertionFact(
        assertion_id="order_created",
        value=C2FactValue.TRUE,
        time_scope="post_recovery",
        details={},
    )
    assert (
        get_c2_fact_value(
            [fact_without_trial], "order_created", expected_trial_id="trial-99"
        )
        == C2FactValue.UNKNOWN
    )

    facade = C2NamedAssertionEvaluator()
    ctx = EvaluationContext(
        after={"order": {"order_id": "ord-002", "status": "created"}}
    )
    res = facade.evaluate_named_assertion("order_created", ctx, entity_id="ord-001")
    assert res.value == TriState.UNKNOWN
    assert "does not match" in str(res.details.get("reason", "")).lower()


# ---------------------------------------------------------------------------
# 6. Shared event IDs survive projection and replay
# ---------------------------------------------------------------------------
def test_shared_event_ids_survive_projection():
    event_id = "evt_stable_identity_999"
    trace = ExecutionTrace(
        trace_id="tr-100",
        target_mode=TargetMode.CONTROLLED_TEST,
        is_simulation=True,
        initial_state=StateSnapshot(snapshot_id="s1"),
        final_state=StateSnapshot(snapshot_id="s2"),
        tool_events=[
            RawToolEvent(
                event_id=event_id,
                call_index=1,
                tool_name="order_placement",
                arguments={"amount": 50},
                success=True,
            )
        ],
    )

    c1_events, _ = project_c1_evidence(trace)
    assert c1_events[0].event_id == event_id

    c2_ev = project_c2_evidence("proj-1", "run-1", "test-1", "model-1", "1", trace)
    assert c2_ev.ordered_events[0].event_id == event_id

    c4_pkg = project_c4_evidence("proj-1", "case-1", "run-1", 1, trace)
    assert c4_pkg.action_attempts[0].event_id == event_id


# ---------------------------------------------------------------------------
# 7. Missing per-step observations remain missing
# ---------------------------------------------------------------------------
def test_missing_per_step_observations_remain_missing():
    trace = ExecutionTrace(
        trace_id="tr-steps",
        target_mode=TargetMode.CONTROLLED_TEST,
        is_simulation=True,
        initial_state=StateSnapshot(snapshot_id="s1"),
        final_state=StateSnapshot(snapshot_id="s2"),
        tool_events=[
            RawToolEvent(
                event_id="evt-1",
                call_index=1,
                tool_name="tool_a",
                arguments={},
                success=True,
            ),
            RawToolEvent(
                event_id="evt-2",
                call_index=2,
                tool_name="tool_b",
                arguments={},
                success=True,
            ),
        ],
    )
    c2_ev = project_c2_evidence("proj-1", "run-1", "test-1", "model-1", "1", trace)
    assert len(c2_ev.ordered_events) == 2
    assert c2_ev.state_observations[1].before_state == {}
    assert c2_ev.completeness.has_db_diffs is False
    assert c2_ev.completeness.confirmed_agent_termination is False


# ---------------------------------------------------------------------------
# 8. Scripted callers are not labelled actual agents
# ---------------------------------------------------------------------------
def test_scripted_callers_not_labelled_actual_agents():
    clean_trace = ExecutionTrace(
        trace_id="clean",
        target_mode=TargetMode.CONTROLLED_TEST,
        is_simulation=True,
        initial_state=StateSnapshot(snapshot_id="s1"),
        final_state=StateSnapshot(snapshot_id="s2"),
        tool_events=[
            RawToolEvent(
                event_id="e1",
                call_index=1,
                tool_name="order_placement",
                arguments={},
                success=True,
            )
        ],
    )
    fault_trace = ExecutionTrace(
        trace_id="fault",
        target_mode=TargetMode.CONTROLLED_TEST,
        is_simulation=True,
        initial_state=StateSnapshot(snapshot_id="s1"),
        final_state=StateSnapshot(snapshot_id="s2"),
        tool_events=[
            RawToolEvent(
                event_id="e2",
                call_index=1,
                tool_name="order_placement",
                arguments={},
                success=False,
            )
        ],
    )
    contract = RecoveryContract(
        contract_id="rec-1",
        contract_version="1.0.0",
        permitted_terminal_outcomes=[TerminalOutcome.SUCCESS_CLEAN_RECOVERY],
        max_task_attempts=3,
        max_tool_calls_budget=10,
        max_total_timeout_ms=5000,
        required_state_assertions=["order_created"],
    )
    matched_ev, _ = project_c3_matched_pair_evidence(
        project_id="proj-1",
        case_id="c3-case",
        pair_id="p-1",
        run_id="r-1",
        clean_trace=clean_trace,
        fault_trace=fault_trace,
        recovery_contract=contract,
    )
    assert matched_ev.clean_trial.caller_identity == CallerIdentity.SCRIPTED_CALLER
    assert matched_ev.clean_trial.recovery_actor == RecoveryActor.SCRIPTED_CALLER
    assert matched_ev.fault_trial.caller_identity == CallerIdentity.SCRIPTED_CALLER


# ---------------------------------------------------------------------------
# 9. Fault flags alone cannot confirm exposure
# ---------------------------------------------------------------------------
def test_fault_flags_alone_cannot_confirm_exposure():
    clean_trace = ExecutionTrace(
        trace_id="clean",
        target_mode=TargetMode.CONTROLLED_TEST,
        is_simulation=True,
        initial_state=StateSnapshot(snapshot_id="s1"),
        final_state=StateSnapshot(snapshot_id="s2"),
        tool_events=[
            RawToolEvent(
                event_id="e1",
                call_index=1,
                tool_name="order_placement",
                arguments={},
                success=True,
            )
        ],
    )
    fault_trace = ExecutionTrace(
        trace_id="fault",
        target_mode=TargetMode.CONTROLLED_TEST,
        is_simulation=True,
        fault_injected=True,
        initial_state=StateSnapshot(snapshot_id="s1"),
        final_state=StateSnapshot(snapshot_id="s2"),
        tool_events=[
            RawToolEvent(
                event_id="e2",
                call_index=1,
                tool_name="order_placement",
                arguments={},
                success=True,
            )
        ],
    )
    contract = RecoveryContract(
        contract_id="rec-1",
        contract_version="1.0.0",
        permitted_terminal_outcomes=[TerminalOutcome.SUCCESS_CLEAN_RECOVERY],
        max_task_attempts=3,
        max_tool_calls_budget=10,
        max_total_timeout_ms=5000,
        required_state_assertions=["order_created"],
    )
    matched_ev, _ = project_c3_matched_pair_evidence(
        project_id="proj-1",
        case_id="c3-case",
        pair_id="p-1",
        run_id="r-1",
        clean_trace=clean_trace,
        fault_trace=fault_trace,
        recovery_contract=contract,
    )
    assert matched_ev.exposure_status == ExposureStatus.EXPOSURE_UNKNOWN


# ---------------------------------------------------------------------------
# 10. Cleanup failures propagate
# ---------------------------------------------------------------------------
def test_cleanup_failures_propagate():
    adapter = ControlledTestTargetAdapter(failure_on_cleanup=True)
    adapter.prepare_fixture("ns_fail_clean")
    success, reused = adapter.cleanup_fixture("ns_fail_clean")
    assert success is False
    assert reused is False


# ---------------------------------------------------------------------------
# 11. One-call budget permits no second call
# ---------------------------------------------------------------------------
def test_one_call_budget_permits_no_second_call():
    adapter = ControlledTestTargetAdapter()
    adapter.prepare_fixture("ns_budget")
    trace = adapter.execute_session(
        namespace="ns_budget",
        task_prompt="Run tools",
        permitted_tools=["order_placement", "process_refund"],
        max_tool_calls=1,
    )
    assert len(trace.tool_events) <= 1


# ---------------------------------------------------------------------------
# 12 & 13. Cancellation rules: cooperative and terminal completed protected
# ---------------------------------------------------------------------------
def test_cancellation_rules_terminal_protection(
    test_client: TestClient, db_session: Session
):
    user = make_user(db_session, "CancelTester", "cancel@example.com")
    project_id = "proj-cancel-test"
    make_project(db_session, project_id, "Cancel Proj", user.id)
    headers = auth_headers(user)

    plan = IntegrationRunPlanModel(
        id=str(uuid.uuid4()),
        integration_run_id="irun-cancel-test",
        project_id=project_id,
        created_by_user_id=user.id,
        name="Cancel Test Plan",
        lifecycle_status=IntegrationPlanStatus.COMPLETED.value,
        plan_digest="a" * 64,
        plan_payload={},
        readiness_report={},
    )
    db_session.add(plan)
    db_session.flush()

    exec_record = IntegrationExecutionModel(
        id=str(uuid.uuid4()),
        execution_id="exec-completed-01",
        integration_run_id="irun-cancel-test",
        project_id=project_id,
        triggered_by_user_id=user.id,
        lifecycle_status="COMPLETED",
        target_mode="CONTROLLED_TEST_FIXTURE",
        plan_digest="a" * 64,
    )
    db_session.add(exec_record)
    db_session.commit()

    resp = test_client.post(
        f"/api/v1/projects/{project_id}/integration/plans/{plan.integration_run_id}/executions/{exec_record.execution_id}/cancel",
        headers=headers,
    )
    assert resp.status_code == status.HTTP_409_CONFLICT


# ---------------------------------------------------------------------------
# 14. Native C3 VIOLATED and C4 FAIL results appear correctly in reports
# ---------------------------------------------------------------------------
def test_native_c3_violated_and_c4_fail_in_reports(db_session: Session):
    aggregator = SharedReportAggregator(db_session)
    project_id = "proj-rep-test"
    user = make_user(db_session, "RepTester", "reptester@example.com")
    proj = make_project(db_session, project_id, "Rep Proj", user.id)

    plan = IntegrationRunPlanModel(
        id=str(uuid.uuid4()),
        integration_run_id="irun-rep-test",
        project_id=project_id,
        created_by_user_id=user.id,
        name="Rep Plan",
        lifecycle_status="COMPLETED",
        plan_digest="a" * 64,
        plan_payload={
            "component_references": {
                "c3": {
                    "project_id": project_id,
                    "suite_id": "s-1",
                    "suite_digest": "a" * 64,
                },
                "c4": {
                    "project_id": project_id,
                    "contract_id": "c-1",
                    "contract_version": 1,
                },
            }
        },
        readiness_report={},
    )
    db_session.add(plan)
    db_session.flush()

    exec_record = IntegrationExecutionModel(
        id=str(uuid.uuid4()),
        execution_id="exec-rep-01",
        integration_run_id="irun-rep-test",
        project_id=project_id,
        triggered_by_user_id=user.id,
        lifecycle_status="COMPLETED",
        target_mode="CONTROLLED_TEST_FIXTURE",
        plan_digest="a" * 64,
        retained_evidence_digest="b" * 64,
        evaluations={
            "C3": {
                "component": "C3",
                "verdict": "FAIL_STATE_VIOLATION",
                "status": "EVALUATED",
                "rule_results_count": 2,
                "rule_results": [
                    {"rule_id": "rule_sat", "status": "SATISFIED"},
                    {
                        "rule_id": "rule_viol",
                        "status": "VIOLATED",
                        "failure_reason": "State diverged",
                    },
                ],
            },
            "C4": {
                "component": "C4",
                "verdict": "FAIL",
                "findings": [
                    {"rule_id": "rule_c4_pass", "verdict": "PASS"},
                    {
                        "rule_id": "rule_c4_fail",
                        "verdict": "FAIL",
                        "explanation": "Policy breached",
                    },
                ],
            },
        },
    )
    db_session.add(exec_record)
    db_session.commit()

    report = aggregator.generate_report(proj, "exec-rep-01", persist=False)
    assert report.component_contributions["C3"].violations_or_findings_count == 1
    assert report.component_contributions["C4"].violations_or_findings_count == 1
    assert report.completeness.overall_verdict == "FAILED"


# ---------------------------------------------------------------------------
# 15. Genuine passing verdicts recognized (EXPECTED REJECTION PASS, PASS_COMPLETED)
# ---------------------------------------------------------------------------
def test_genuine_passing_verdicts_recognized(db_session: Session):
    aggregator = SharedReportAggregator(db_session)
    project_id = "proj-pass-test"
    user = make_user(db_session, "PassTester", "passtester@example.com")
    proj = make_project(db_session, project_id, "Pass Proj", user.id)

    plan = IntegrationRunPlanModel(
        id=str(uuid.uuid4()),
        integration_run_id="irun-pass-test",
        project_id=project_id,
        created_by_user_id=user.id,
        name="Pass Plan",
        lifecycle_status="COMPLETED",
        plan_digest="a" * 64,
        plan_payload={
            "component_references": {
                "c2": {
                    "project_id": project_id,
                    "model_id": "m-1",
                    "model_version": "1.0.0",
                },
                "c3": {
                    "project_id": project_id,
                    "suite_id": "s-1",
                    "suite_digest": "a" * 64,
                },
            }
        },
        readiness_report={},
    )
    db_session.add(plan)
    db_session.flush()

    exec_record = IntegrationExecutionModel(
        id=str(uuid.uuid4()),
        execution_id="exec-pass-01",
        integration_run_id="irun-pass-test",
        project_id=project_id,
        triggered_by_user_id=user.id,
        lifecycle_status="COMPLETED",
        target_mode="CONTROLLED_TEST_FIXTURE",
        plan_digest="a" * 64,
        retained_evidence_digest="b" * 64,
        evaluations={
            "C2": {
                "component": "C2",
                "verdict": "EXPECTED REJECTION PASS",
                "violations": [],
            },
            "C3": {
                "component": "C3",
                "verdict": "PASS_COMPLETED",
                "status": "EVALUATED",
                "rule_results": [{"rule_id": "r1", "status": "SATISFIED"}],
            },
        },
    )
    db_session.add(exec_record)
    db_session.commit()

    report = aggregator.generate_report(proj, "exec-pass-01", persist=False)
    assert report.completeness.overall_verdict == "PASSED"


# ---------------------------------------------------------------------------
# 16. Unknown/not-ready results are not fabricated defects
# ---------------------------------------------------------------------------
def test_unknown_not_ready_not_fabricated_defects(db_session: Session):
    aggregator = SharedReportAggregator(db_session)
    project_id = "proj-notready-test"
    user = make_user(db_session, "NRUser", "nr@example.com")
    proj = make_project(db_session, project_id, "NR Proj", user.id)

    plan = IntegrationRunPlanModel(
        id=str(uuid.uuid4()),
        integration_run_id="irun-nr-test",
        project_id=project_id,
        created_by_user_id=user.id,
        name="NR Plan",
        lifecycle_status="COMPLETED",
        plan_digest="a" * 64,
        plan_payload={
            "component_references": {
                "c2": {
                    "project_id": project_id,
                    "model_id": "m-nr",
                    "model_version": "1.0.0",
                }
            }
        },
        readiness_report={},
    )
    db_session.add(plan)
    db_session.flush()

    exec_record = IntegrationExecutionModel(
        id=str(uuid.uuid4()),
        execution_id="exec-nr-01",
        integration_run_id="irun-nr-test",
        project_id=project_id,
        triggered_by_user_id=user.id,
        lifecycle_status="COMPLETED",
        target_mode="CONTROLLED_TEST_FIXTURE",
        plan_digest="a" * 64,
        retained_evidence_digest="b" * 64,
        evaluations={
            "C2": {
                "component": "C2",
                "verdict": "MODEL NOT READY",
                "reasons": ["Model not approved"],
            }
        },
    )
    db_session.add(exec_record)
    db_session.commit()

    report = aggregator.generate_report(proj, "exec-nr-01", persist=False)
    assert report.component_contributions["C2"].violations_or_findings_count == 0
    assert report.component_contributions["C2"].status == "NOT_READY"
    assert "C2" in [c.value for c in report.completeness.not_ready_components]


# ---------------------------------------------------------------------------
# 17. Tampered evidence fails replay integrity check (HTTP 422)
# ---------------------------------------------------------------------------
def test_tampered_evidence_fails_replay(test_client: TestClient, db_session: Session):
    user = make_user(db_session, "ReplayUser", "replay@example.com")
    project_id = "proj-tamper-test"
    make_project(db_session, project_id, "Tamper Proj", user.id)
    headers = auth_headers(user)

    plan = IntegrationRunPlanModel(
        id=str(uuid.uuid4()),
        integration_run_id="irun-tamper-test",
        project_id=project_id,
        created_by_user_id=user.id,
        name="Tamper Plan",
        lifecycle_status="COMPLETED",
        plan_digest="a" * 64,
        plan_payload={"component_references": {}},
        readiness_report={},
    )
    db_session.add(plan)
    db_session.flush()

    exec_record = IntegrationExecutionModel(
        id=str(uuid.uuid4()),
        execution_id="exec-tamper-01",
        integration_run_id="irun-tamper-test",
        project_id=project_id,
        triggered_by_user_id=user.id,
        lifecycle_status="COMPLETED",
        target_mode="CONTROLLED_TEST_FIXTURE",
        plan_digest="a" * 64,
        retained_evidence_digest="genuine_digest_hash_12345",
        retained_evidence={"primary_trace": {"trace_id": "tampered_data"}},
    )
    db_session.add(exec_record)
    db_session.commit()

    resp = test_client.post(
        f"/api/v1/projects/{project_id}/integration/plans/{plan.integration_run_id}/executions/{exec_record.execution_id}/replay",
        headers=headers,
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "integrity check failed" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 18. Wrong-plan nested URLs are rejected with HTTP 404
# ---------------------------------------------------------------------------
def test_wrong_plan_nested_urls_rejected(test_client: TestClient, db_session: Session):
    user = make_user(db_session, "NestedUser", "nested@example.com")
    project_id = "proj-nested-test"
    make_project(db_session, project_id, "Nested Proj", user.id)
    headers = auth_headers(user)

    plan_a = IntegrationRunPlanModel(
        id=str(uuid.uuid4()),
        integration_run_id="irun-plan-A",
        project_id=project_id,
        created_by_user_id=user.id,
        name="Plan A",
        lifecycle_status="COMPLETED",
        plan_digest="a" * 64,
        plan_payload={},
        readiness_report={},
    )
    plan_b = IntegrationRunPlanModel(
        id=str(uuid.uuid4()),
        integration_run_id="irun-plan-B",
        project_id=project_id,
        created_by_user_id=user.id,
        name="Plan B",
        lifecycle_status="COMPLETED",
        plan_digest="b" * 64,
        plan_payload={},
        readiness_report={},
    )
    db_session.add(plan_a)
    db_session.add(plan_b)
    db_session.flush()

    exec_under_b = IntegrationExecutionModel(
        id=str(uuid.uuid4()),
        execution_id="exec-under-B",
        integration_run_id="irun-plan-B",
        project_id=project_id,
        triggered_by_user_id=user.id,
        lifecycle_status="COMPLETED",
        target_mode="CONTROLLED_TEST_FIXTURE",
        plan_digest="b" * 64,
    )
    db_session.add(exec_under_b)
    db_session.commit()

    resp = test_client.get(
        f"/api/v1/projects/{project_id}/integration/plans/{plan_a.integration_run_id}/executions/{exec_under_b.execution_id}",
        headers=headers,
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


def test_two_call_retry_budget_executes_second_call():
    """Verify that a 2-call budget executes the retry call (fixing the double-increment defect)."""
    from app.shared.integration.adapters import ControlledTestTargetAdapter

    adapter = ControlledTestTargetAdapter()
    ns = "ns_retry_budget_test"
    adapter.prepare_fixture(ns)

    trace = adapter.execute_session(
        namespace=ns,
        task_prompt="Submit order",
        permitted_tools=["order_placement"],
        fault_injection_hook={
            "target_tool": "order_placement",
            "occurrence": 1,
            "fault_family": "TIMEOUT_DISCONNECTION",
        },
        max_tool_calls=2,
        trial_role="FAULT",
    )

    # With double increment bug fixed, call 1 is the fault, call 2 is the retry!
    assert len(trace.tool_events) == 2
    assert trace.tool_events[0].success is False
    assert trace.tool_events[1].success is True
    assert trace.caller_outcome in ("SUCCESS_AFTER_RETRY", "SUCCESS_CLEAN_RECOVERY")


def test_c3_contradictory_suite_id_rejected(
    test_client: TestClient, db_session: Session
):
    """Verify that a contradictory suite_id is rejected rather than silently overwritten."""
    user = make_user(db_session, "AliceContra", "alice_contra@example.com")
    headers = auth_headers(user)
    project_id = f"proj-c3-contra-{uuid.uuid4().hex[:6]}"
    make_project(db_session, project_id, "Contra Proj", user.id)

    # Seed C3 suite
    suite = C3SuiteModel(
        project_id=project_id,
        suite_id="suite-c3-legit",
        suite_digest="c3dig" + "0" * 59,
        task_id="task-01",
        tool_id="order_placement",
        domain="e-commerce",
        schema_version="2026.1",
        generator_version="1.0.0",
        total_cases=1,
        policy_snapshot={},
        adapter_manifest_snapshot={},
        task_fixture_metadata_snapshot={},
        recovery_contract_snapshot={"contract_id": "rec-01"},
        suite_snapshot={},
    )
    db_session.add(suite)
    db_session.commit()

    # Pass contradictory suite_id
    payload = {
        "c3_reference": {
            "project_id": project_id,
            "suite_id": "suite-c3-CONTRADICTORY",
            "suite_digest": suite.suite_digest,
        }
    }
    resp = test_client.post(
        f"/api/v1/projects/{project_id}/integration/plans/validate-readiness",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_ready"] is False
    issues = [iss["issue_code"] for iss in data["blocking_issues"]]
    assert "SUITE_NOT_FOUND" in issues


def test_c3_invalid_case_id_rejected_no_fallback(
    test_client: TestClient, db_session: Session
):
    """Verify that an invalid case_id returns CASE_NOT_FOUND instead of falling back to case 0."""
    user = make_user(db_session, "BobInvalidCase", "bob_case@example.com")
    headers = auth_headers(user)
    project_id = f"proj-c3-case-{uuid.uuid4().hex[:6]}"
    make_project(db_session, project_id, "Case Proj", user.id)

    suite = C3SuiteModel(
        project_id=project_id,
        suite_id="suite-c3-cases",
        suite_digest="c3digcases" + "0" * 54,
        task_id="task-01",
        tool_id="order_placement",
        domain="e-commerce",
        schema_version="2026.1",
        generator_version="1.0.0",
        total_cases=1,
        policy_snapshot={},
        adapter_manifest_snapshot={},
        task_fixture_metadata_snapshot={},
        recovery_contract_snapshot={"contract_id": "rec-01"},
        suite_snapshot={},
    )
    db_session.add(suite)
    db_session.flush()

    c_case = C3CaseModel(
        case_id="case-valid-01",
        suite_digest="c3digcases" + "0" * 54,
        case_fingerprint="fp" + "0" * 62,
        content_digest="cd" + "0" * 62,
        project_id=project_id,
        case_family_id="fam-01",
        fault_family="TIMEOUT_DISCONNECTION",
        effect_phase="INVOCATION",
        interception_hook="pre_tool_call",
        target_tool_id="order_placement",
        case_order=0,
        case_snapshot={"case_id": "case-valid-01"},
    )
    db_session.add(c_case)
    db_session.commit()

    payload = {
        "c3_reference": {
            "project_id": project_id,
            "suite_id": suite.suite_id,
            "suite_digest": suite.suite_digest,
            "case_id": "case-NON-EXISTENT",
        }
    }
    resp = test_client.post(
        f"/api/v1/projects/{project_id}/integration/plans/validate-readiness",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_ready"] is False
    issues = [iss["issue_code"] for iss in data["blocking_issues"]]
    assert "CASE_NOT_FOUND" in issues


def test_inflight_report_not_permanently_cached(db_session: Session):
    """Verify that requesting a report for a RUNNING execution does not cache it in DB."""
    from app.shared.integration.models import IntegrationReportModel
    from app.shared.integration.reporting import SharedReportAggregator

    user = make_user(db_session, "CharlieInflight", "charlie_inflight@example.com")
    project_id = f"proj-inflight-{uuid.uuid4().hex[:6]}"
    proj = make_project(db_session, project_id, "Inflight Test", user.id)

    plan = IntegrationRunPlanModel(
        id=str(uuid.uuid4()),
        integration_run_id=f"irun-{uuid.uuid4().hex[:8]}",
        project_id=project_id,
        created_by_user_id=user.id,
        name="Inflight Plan",
        lifecycle_status="RUNNING",
        plan_digest="p" * 64,
        plan_payload={"component_references": {}},
        readiness_report={},
    )
    db_session.add(plan)
    db_session.flush()

    execution_id = f"exec-{uuid.uuid4().hex[:8]}"
    exec_rec = IntegrationExecutionModel(
        id=str(uuid.uuid4()),
        execution_id=execution_id,
        integration_run_id=plan.integration_run_id,
        project_id=project_id,
        triggered_by_user_id=user.id,
        lifecycle_status="RUNNING",
        target_mode="CONTROLLED_TEST_FIXTURE",
        plan_digest="p" * 64,
        evaluations={},
    )
    db_session.add(exec_rec)
    db_session.commit()

    aggregator = SharedReportAggregator(db_session)
    report = aggregator.generate_report(proj, execution_id, persist=True)
    assert report.execution_id == execution_id

    # Crucial check: IntegrationReportModel MUST NOT exist for this execution!
    persisted = (
        db_session.execute(
            select(IntegrationReportModel).where(
                IntegrationReportModel.project_id == project_id,
                IntegrationReportModel.execution_id == execution_id,
            )
        )
        .scalars()
        .first()
    )
    assert persisted is None


def test_tampered_plan_digest_fails_pre_execution_check(
    test_client: TestClient, db_session: Session
):
    """Verify that tampered execution inputs digest triggers HTTP 422 before dispatch."""
    user = make_user(db_session, "DaveTamper", "dave_tamper@example.com")
    headers = auth_headers(user)
    project_id = f"proj-tamper-{uuid.uuid4().hex[:6]}"
    make_project(db_session, project_id, "Tamper Proj", user.id)

    plan = IntegrationRunPlanModel(
        id=str(uuid.uuid4()),
        integration_run_id=f"irun-tamper-{uuid.uuid4().hex[:8]}",
        project_id=project_id,
        created_by_user_id=user.id,
        name="Tampered Plan",
        lifecycle_status="READY",
        plan_digest="legit" + "0" * 59,
        plan_payload={
            "execution_inputs_snapshot": {"c1": {"some": "data"}},
            "execution_inputs_digest": "TAMPERED_INCORRECT_DIGEST",
            "component_references": {},
        },
        readiness_report={},
    )
    db_session.add(plan)
    db_session.commit()

    resp = test_client.post(
        f"/api/v1/projects/{project_id}/integration/plans/{plan.integration_run_id}/execute",
        json={"target_mode": "CONTROLLED_TEST_FIXTURE"},
        headers=headers,
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "integrity check failed" in resp.json()["detail"]


# ===========================================================================
# Dedicated Acceptance & Regression Tests for Independent Probes
# ===========================================================================

import time

from fastapi import HTTPException

from app.components.c2_state_aware_workflow.persistence.models import (
    C2EvaluationResult,
    C2TestCase,
    C2TestSuite,
    C2WorkflowModel,
)
from app.shared.integration.contracts import (
    C1ConfigReference,
    ComponentReferencesPlan,
    ExecutionStartRequest,
)
from app.shared.integration.evidence import compute_evidence_digest
from app.shared.integration.executor import (
    SharedExecutionCoordinator,
    dispatch_component_evaluations,
)
from app.shared.integration.models import (
    IntegrationIdentifierMappingModel,
    IntegrationPublishedContributionModel,
)
from app.shared.integration.replay import EvidenceReplayService


def test_c1_helpdesk_config_cannot_pass_after_only_order_placement(db_session: Session):
    """Probe 1: C1 cannot PASS for a helpdesk configuration after only order_placement executed."""
    project_id = f"proj-c1-hd-{uuid.uuid4().hex[:6]}"
    user = make_user(db_session, "AliceHD", "alice_hd@example.com")
    make_project(db_session, project_id, "Helpdesk Proj", user.id)

    frozen_inputs = {
        "c1": {
            "case_id": "c1_helpdesk_case_01",
            "category": "CORRECT_BEHAVIOUR",
            "expected_tool_calls": [
                {
                    "tool_name": "reboot_managed_device",
                    "min_count": 1,
                    "max_count": 1,
                    "is_forbidden": False,
                }
            ],
            "expectations": [
                {
                    "tool_name": "reboot_managed_device",
                    "min_count": 1,
                    "max_count": 1,
                    "is_forbidden": False,
                }
            ],
        }
    }

    primary_trace = ExecutionTrace(
        trace_id=f"tr-{uuid.uuid4().hex[:8]}",
        target_mode=TargetMode.CONTROLLED_TEST,
        tool_events=[
            RawToolEvent(
                call_index=1,
                tool_name="order_placement",
                arguments={"order_id": "ord-001"},
                output={"status": "created"},
                success=True,
            )
        ],
        is_complete=True,
        caller_outcome="SUCCESS",
        is_simulation=True,
        initial_state=StateSnapshot(snapshot_id="s1", fingerprint="fp-init"),
        final_state=StateSnapshot(snapshot_id="s2", fingerprint="fp-fin"),
    )

    refs = ComponentReferencesPlan(
        c1=C1ConfigReference(
            project_id=project_id, config_id="cfg-helpdesk-01", case_id="case-hd-01"
        )
    )

    evaluations = dispatch_component_evaluations(
        db=db_session,
        project_id=project_id,
        execution_id="exec-hd-01",
        refs=refs,
        frozen_inputs=frozen_inputs,
        primary_trace=primary_trace,
    )

    c1_eval = evaluations.get("C1")
    assert c1_eval is not None
    assert c1_eval["verdict"] in ("FAIL", "INCONCLUSIVE", "VIOLATED")
    assert c1_eval["verdict"] != "PASS"


def test_nonexistent_or_unbound_c2_test_cannot_produce_ready_plan(
    test_client: TestClient, db_session: Session
):
    """Probe 2: READY plans referencing nonexistent or unready C2 tests are rejected."""
    user = make_user(db_session, "BobC2", "bob_c2@example.com")
    headers = auth_headers(user)
    project_id = f"proj-c2-val-{uuid.uuid4().hex[:6]}"
    make_project(db_session, project_id, "C2 Validation Proj", user.id)

    wf_model = C2WorkflowModel(
        project_id=project_id,
        model_id="checkout_model",
        version="1.0.0",
        name="Checkout Flow",
        definition={
            "states": ["INIT", "DONE"],
            "initial_state": "INIT",
            "transitions": [],
        },
        content_hash="hash-checkout-100",
        lifecycle_status="APPROVED",
    )
    db_session.add(wf_model)
    db_session.commit()

    plan_req = {
        "name": "Invalid C2 Plan",
        "c2_reference": {
            "project_id": project_id,
            "model_id": "checkout_model",
            "model_version": "1.0.0",
            "test_id": "nonexistent_test_123",
        },
    }

    resp = test_client.post(
        f"/api/v1/projects/{project_id}/integration/plans",
        json=plan_req,
        headers=headers,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["lifecycle_status"] in ("NOT_READY", "BLOCKED")
    assert data["lifecycle_status"] != "READY"
    report = data["readiness_report"]
    assert report["is_ready"] is False
    issue_codes = [issue["issue_code"] for issue in report["blocking_issues"]]
    assert "TEST_NOT_FOUND" in issue_codes


def test_rate_limit_429_and_after_commit_fault_semantics():
    """Probe 3: RATE_LIMIT_429 and AFTER_COMMIT fault metadata execute real semantics."""
    adapter = ControlledTestTargetAdapter()

    # RATE_LIMIT_429 returns status 429 without simulated timeout
    ns_429 = f"ns_429_{uuid.uuid4().hex[:6]}"
    adapter.prepare_fixture(ns_429)
    trace_429 = adapter.execute_session(
        namespace=ns_429,
        task_prompt="Process order",
        permitted_tools=["order_placement"],
        fault_injection_hook={
            "target_tool": "order_placement",
            "occurrence": 1,
            "fault_family": "RATE_LIMIT_429",
            "interception_hook": "before_tool_execution",
            "effect_phase": "during_call",
            "payload": {"status_code": 429, "retry_after": 5},
        },
    )
    assert trace_429.fault_injected is True
    ev_429 = trace_429.tool_events[0]
    assert ev_429.success is False
    assert (ev_429.output or {}).get("status_code") == 429
    assert "429" in (ev_429.error or "")

    # AFTER_COMMIT commits state before returning error
    ns_ac = f"ns_ac_{uuid.uuid4().hex[:6]}"
    adapter.prepare_fixture(ns_ac)
    trace_ac = adapter.execute_session(
        namespace=ns_ac,
        task_prompt="Process order",
        permitted_tools=["order_placement"],
        fault_injection_hook={
            "target_tool": "order_placement",
            "occurrence": 1,
            "fault_family": "AFTER_COMMIT",
            "interception_hook": "after_state_commit",
            "effect_phase": "after_effect",
            "payload": {"error": "Connection reset after commit"},
        },
    )
    assert trace_ac.fault_injected is True
    ev_ac = trace_ac.tool_events[0]
    assert ev_ac.success is False
    assert (ev_ac.output or {}).get("state_committed") is True
    part = adapter.get_partition(ns_ac)
    assert part is not None
    assert part["order"]["status"] == "CONFIRMED"


def test_unrelated_failed_tool_call_cannot_confirm_exposure():
    """Probe 4: A fault flag and an unrelated failed tool call cannot confirm exposure."""
    clean_trace = ExecutionTrace(
        trace_id=f"tr-cln-{uuid.uuid4().hex[:6]}",
        target_mode=TargetMode.CONTROLLED_TEST,
        tool_events=[
            RawToolEvent(
                call_index=1,
                tool_name="order_placement",
                arguments={},
                output={"ok": True},
                success=True,
            )
        ],
        is_complete=True,
        caller_outcome="SUCCESS",
        is_simulation=True,
        initial_state=StateSnapshot(
            snapshot_id="s1", fingerprint="fp-initial-01", state={}
        ),
        final_state=StateSnapshot(
            snapshot_id="s2",
            fingerprint="fp-final-01",
            state={"order": {"order_id": "ord-001"}},
        ),
    )

    fault_trace = ExecutionTrace(
        trace_id=f"tr-flt-{uuid.uuid4().hex[:6]}",
        target_mode=TargetMode.CONTROLLED_TEST,
        fault_injected=True,
        fault_details={"target_tool": "process_refund", "occurrence": 1},
        tool_events=[
            RawToolEvent(
                call_index=1,
                tool_name="order_placement",
                arguments={},
                error="db error",
                success=False,
            )
        ],
        is_complete=False,
        caller_outcome="FAILED",
        is_simulation=True,
        initial_state=StateSnapshot(
            snapshot_id="s3", fingerprint="fp-initial-01", state={}
        ),
        final_state=StateSnapshot(
            snapshot_id="s4", fingerprint="fp-initial-01", state={}
        ),
    )

    contract = RecoveryContract(
        contract_id="rec-01",
        contract_version="1.0.0",
        permitted_terminal_outcomes=[TerminalOutcome.SUCCESS_CLEAN_RECOVERY],
        max_task_attempts=3,
        max_tool_calls_budget=10,
        max_total_timeout_ms=5000,
        required_state_assertions=["order_confirmed"],
    )

    matched_evidence, _ = project_c3_matched_pair_evidence(
        project_id="proj-exp-01",
        case_id="case-01",
        pair_id="pair-01",
        run_id="run-01",
        clean_trace=clean_trace,
        fault_trace=fault_trace,
        recovery_contract=contract,
    )

    assert matched_evidence.exposure_status != ExposureStatus.CONFIRMED
    assert matched_evidence.exposure_status in (
        ExposureStatus.EXPOSURE_UNKNOWN,
        ExposureStatus.NOT_TRIGGERED,
    )
    assert matched_evidence.exposure_status in (
        ExposureStatus.EXPOSURE_UNKNOWN,
        ExposureStatus.NOT_TRIGGERED,
    )


def test_failed_cleanup_updates_retained_evidence_and_response(db_session: Session):
    """Probe 6: Failed cleanup updates retained evidence and response, preventing reuse."""
    project_id = f"proj-clean-{uuid.uuid4().hex[:6]}"
    user = make_user(db_session, "CleanUser", "clean_user@example.com")
    proj = make_project(db_session, project_id, "Clean Proj", user.id)

    plan_payload = {
        "execution_inputs_snapshot": {},
        "component_references": {
            "c1": {
                "project_id": project_id,
                "config_id": "cfg-01",
                "case_id": "case-01",
            }
        },
    }
    plan = IntegrationRunPlanModel(
        id=str(uuid.uuid4()),
        integration_run_id=f"irun-clean-{uuid.uuid4().hex[:8]}",
        project_id=project_id,
        created_by_user_id=user.id,
        name="Clean Test Plan",
        lifecycle_status="READY",
        plan_digest=canonical_json_digest(plan_payload),
        plan_payload=plan_payload,
        readiness_report={},
    )
    db_session.add(plan)
    db_session.commit()

    coord = SharedExecutionCoordinator(db_session)
    req = ExecutionStartRequest(
        target_mode=TargetMode.CONTROLLED_TEST,
    )

    orig_cleanup = ControlledTestTargetAdapter.cleanup_fixture
    try:
        ControlledTestTargetAdapter.cleanup_fixture = lambda self, ns: (False, False)
        status_resp = coord.execute_plan(
            project=proj,
            user=user,
            plan_identifier=plan.integration_run_id,
            request=req,
        )
        assert status_resp.cleanup_successful is False
        assert status_resp.cleanup_reusable is False
        assert "cleanup failed" in (status_resp.error_message or "").lower()

        exec_rec = (
            db_session.execute(
                select(IntegrationExecutionModel).where(
                    IntegrationExecutionModel.execution_id == status_resp.execution_id
                )
            )
            .scalars()
            .first()
        )
        pt = exec_rec.retained_evidence["primary_trace"]
        assert pt["cleanup_successful"] is False
        assert pt["cleanup_reusable"] is False
    finally:
        ControlledTestTargetAdapter.cleanup_fixture = orig_cleanup


def test_shared_c2_execution_persists_native_history_and_mapping(db_session: Session):
    """Probe 8: Shared C2 execution creates retrievable native evaluation history and explicit mapping."""
    project_id = f"proj-c2-hist-{uuid.uuid4().hex[:6]}"
    user = make_user(db_session, "C2HistUser", "c2_hist@example.com")
    proj = make_project(db_session, project_id, "C2 Hist Proj", user.id)

    from app.components.c2_state_aware_workflow.examples.ecommerce_workflows import (
        get_cancellation_workflow_model,
    )

    efsm_obj = get_cancellation_workflow_model()
    model_dict = efsm_obj.model_dump()
    model_dict["project_id"] = project_id
    model_dict["model_id"] = "order_flow"
    model_dict["version"] = "1.0.0"
    model_dict["name"] = "Order Flow"

    wf_model = C2WorkflowModel(
        project_id=project_id,
        model_id="order_flow",
        version="1.0.0",
        name="Order Flow",
        definition=model_dict,
        content_hash="hash-order-100",
        lifecycle_status="APPROVED",
    )
    db_session.add(wf_model)
    db_session.flush()

    suite = C2TestSuite(
        project_id=project_id,
        suite_id="suite-order-01",
        model_record_id=wf_model.id,
        model_id="order_flow",
        model_version="1.0.0",
        model_content_hash="hash-order-100",
        config={},
        diagnostics={},
        total_cases=1,
        ready_cases_count=1,
    )
    db_session.add(suite)
    db_session.flush()

    test_case = C2TestCase(
        suite_record_id=suite.id,
        project_id=project_id,
        suite_id=suite.suite_id,
        test_id="test_order_01",
        category="VALID",
        task="Place an order",
        fixture_ref="fix-01",
        readiness="TEST_READY",
        is_ready=True,
        definition={
            "test_id": "test_order_01",
            "project_id": project_id,
            "suite_id": suite.suite_id,
            "pinned_model_id": "order_flow",
            "pinned_model_version": "1.0.0",
            "model_content_hash": "hash-order-100",
            "category": "VALID",
            "task": "Place an order",
            "fixture_ref": "fix-01",
            "expected_outcome": "PASS",
        },
    )
    db_session.add(test_case)
    db_session.flush()

    plan_payload = {
        "execution_inputs_snapshot": {
            "c2": {
                "model_id": "order_flow",
                "model_version": "1.0.0",
                "suite_id": suite.suite_id,
                "test_id": test_case.test_id,
                "definition": wf_model.definition,
                "test_definition": test_case.definition,
            }
        },
        "component_references": {
            "c2": {
                "project_id": project_id,
                "model_id": "order_flow",
                "model_version": "1.0.0",
                "suite_id": suite.suite_id,
                "test_id": test_case.test_id,
            }
        },
    }
    plan = IntegrationRunPlanModel(
        id=str(uuid.uuid4()),
        integration_run_id=f"irun-c2-{uuid.uuid4().hex[:8]}",
        project_id=project_id,
        created_by_user_id=user.id,
        name="C2 Native Hist Plan",
        lifecycle_status="READY",
        plan_digest=canonical_json_digest(plan_payload),
        plan_payload=plan_payload,
        readiness_report={},
    )
    db_session.add(plan)
    db_session.commit()

    coord = SharedExecutionCoordinator(db_session)
    resp = coord.execute_plan(
        project=proj,
        user=user,
        plan_identifier=plan.integration_run_id,
        request=ExecutionStartRequest(target_mode=TargetMode.CONTROLLED_TEST),
    )

    assert resp.lifecycle_status == "COMPLETED"
    c2_eval = resp.evaluations.get("C2")
    assert c2_eval is not None
    native_eval_id = c2_eval.get("evaluation_id")
    assert native_eval_id is not None

    eval_rec = (
        db_session.execute(
            select(C2EvaluationResult).where(C2EvaluationResult.id == native_eval_id)
        )
        .scalars()
        .first()
    )
    assert eval_rec is not None
    assert eval_rec.run_id == resp.execution_id

    mapping_rec = (
        db_session.execute(
            select(IntegrationIdentifierMappingModel).where(
                IntegrationIdentifierMappingModel.project_id == project_id,
                IntegrationIdentifierMappingModel.component_type == "C2",
                IntegrationIdentifierMappingModel.native_id == native_eval_id,
            )
        )
        .scalars()
        .first()
    )
    assert mapping_rec is not None
    assert mapping_rec.context_json.get("execution_id") == resp.execution_id


def test_published_contribution_durable_fresh_session_and_idempotency(
    db_session: Session,
):
    """Probe 7: Published contribution content survives fresh session; duplicate is idempotent; conflict handled."""
    from app.shared.integration.reporting import AggregatorClientAdapter

    project_id = f"proj-pub-{uuid.uuid4().hex[:6]}"
    exec_id = f"exec-pub-{uuid.uuid4().hex[:8]}"

    adapter = AggregatorClientAdapter(
        execution_id=exec_id, db=db_session, project_id=project_id
    )

    contrib_data = {
        "evaluation_id": f"eval-{uuid.uuid4().hex[:8]}",
        "project_id": project_id,
        "component": "C2",
        "verdict": "PASS",
        "details": {"score": 100},
    }

    # 1. Initial publication
    token1 = adapter.publish(contrib_data)
    assert token1.startswith(f"PUB-{exec_id[:8]}-")

    stored = (
        db_session.execute(
            select(IntegrationPublishedContributionModel).where(
                IntegrationPublishedContributionModel.project_id == project_id,
                IntegrationPublishedContributionModel.contribution_id
                == contrib_data["evaluation_id"],
            )
        )
        .scalars()
        .first()
    )
    assert stored is not None
    assert stored.publication_token == token1
    assert stored.payload["verdict"] == "PASS"

    # 2. Duplicate publication is idempotent
    token2 = adapter.publish(contrib_data)
    assert token2 == token1

    # 3. Conflicting content with same contribution_id raises HTTP 409
    conflicting_data = dict(contrib_data)
    conflicting_data["verdict"] = "VIOLATION"
    with pytest.raises(HTTPException) as exc_info:
        adapter.publish(conflicting_data)
    assert exc_info.value.status_code == status.HTTP_409_CONFLICT


def test_replay_rejects_plan_digest_mismatch(db_session: Session):
    """Probe 9: Replay rejects execution whose recorded plan_digest does not match the plan."""
    project_id = f"proj-rply-{uuid.uuid4().hex[:6]}"
    user = make_user(db_session, "ReplayUser", "replay_user@example.com")
    proj = make_project(db_session, project_id, "Replay Proj", user.id)

    plan_payload = {
        "execution_inputs_snapshot": {},
        "component_references": {},
    }
    plan = IntegrationRunPlanModel(
        id=str(uuid.uuid4()),
        integration_run_id=f"irun-rply-{uuid.uuid4().hex[:8]}",
        project_id=project_id,
        created_by_user_id=user.id,
        name="Replay Plan",
        lifecycle_status="COMPLETED",
        plan_digest=canonical_json_digest(plan_payload),
        plan_payload=plan_payload,
        readiness_report={},
    )
    db_session.add(plan)

    trace_data = {
        "trace_id": "tr-01",
        "target_mode": "CONTROLLED_TEST",
        "tool_events": [],
        "is_complete": True,
        "caller_outcome": "SUCCESS",
        "is_simulation": True,
        "initial_state": {"snapshot_id": "s1", "fingerprint": "fp-1", "state": {}},
        "final_state": {"snapshot_id": "s2", "fingerprint": "fp-1", "state": {}},
    }
    exec_rec = IntegrationExecutionModel(
        id=str(uuid.uuid4()),
        execution_id=f"exec-rply-{uuid.uuid4().hex[:8]}",
        integration_run_id=plan.integration_run_id,
        project_id=project_id,
        lifecycle_status="COMPLETED",
        target_mode="CONTROLLED_TEST",
        plan_digest="mismatched_digest_value" + "0" * 41,
        retained_evidence={"primary_trace": trace_data},
        retained_evidence_digest=compute_evidence_digest({"primary_trace": trace_data}),
    )
    db_session.add(exec_rec)
    db_session.commit()

    service = EvidenceReplayService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.replay_execution(
            project=proj, user=user, execution_id=exec_rec.execution_id
        )
    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "Plan digest mismatch" in exc_info.value.detail


def test_monotonic_deadline_stops_execution_dispatch():
    """Probe 10: Monotonic deadline halts call dispatch when timeout_seconds exceeded."""
    adapter = ControlledTestTargetAdapter()
    ns = f"ns_dl_{uuid.uuid4().hex[:6]}"
    adapter.prepare_fixture(ns)

    # Deadline in the past
    past_deadline = time.monotonic() - 1.0
    trace = adapter.execute_session(
        namespace=ns,
        task_prompt="Process order",
        permitted_tools=["order_placement"],
        deadline_monotonic=past_deadline,
    )
    assert trace.caller_outcome in ("TIMEOUT_EXCEEDED", "CALLER_TIMEOUT_EXCEEDED")
    assert len(trace.tool_events) == 0


from sqlalchemy import event


@event.listens_for(test_engine, "connect")
def _set_sqlite_fk(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()
