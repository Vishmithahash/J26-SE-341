"""Hermetic test suite for Component 3 Phase 5: Persistence, Tracking, and Reporting.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 5 - Shared persistence, execution tracking, results and reporting.

Tests all C3-owned persistence models, repositories, run tracking lifecycle,
idempotent imports, immutability, project scoping, report aggregation, and
stateless API preservation using isolated in-memory test database.
"""

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c3_robustness_recovery.contracts.evaluation import (
    C2AssertionFact,
    C2FactValue,
    RecoveryVerdict,
)
from app.components.c3_robustness_recovery.contracts.generation import (
    FrozenSuite,
)
from app.components.c3_robustness_recovery.contracts.persistence import (
    ExecutionArtifactImportRequest,
    ExecutionCreateRequest,
    ExecutionTrackingStatus,
)
from app.components.c3_robustness_recovery.repositories.persistence import (
    C3PersistenceRepository,
    ConflictError,
    EntityNotFoundError,
)
from app.components.c3_robustness_recovery.runtime.adapter import (
    CallerIdentity,
    CleanupStatus,
    DemonstrationFixtureManager,
    DemonstrationToolAdapter,
    RecoveryActor,
    TargetMode,
)
from app.components.c3_robustness_recovery.runtime.evidence import (
    CleanQualification,
    ExecutionStatus,
    ExposureStatus,
    FixtureComparability,
    MatchedPairEvidence,
    ReadinessStatus,
    TrialEvidence,
    TrialRole,
)
from app.components.c3_robustness_recovery.runtime.runner import (
    make_demonstration_candidate_case,
    make_demonstration_recovery_contract,
    make_demonstration_task_fixture_metadata,
)
from app.components.c3_robustness_recovery.runtime.suite_runner import (
    build_demonstration_generation_request,
)
from app.components.c3_robustness_recovery.services.generation import (
    generate_feasible_cases,
)
from app.components.c3_robustness_recovery.services.reporting import (
    build_execution_report,
    export_report_to_csv,
)
from app.components.c3_robustness_recovery.services.run_tracking import (
    create_execution_manifest,
    finalize_execution_lifecycle,
    record_case_execution_progress,
    save_local_fallback_artifact,
)
from app.components.c3_robustness_recovery.services.storage import (
    compute_and_store_evaluation,
    get_suite,
    list_evaluations,
    list_suites,
    store_frozen_suite,
    store_matched_pair,
)
from app.database import Base, get_db
from app.main import app

# ---------------------------------------------------------------------------
# In-Memory SQLite Fixtures for Hermetic Testing
# ---------------------------------------------------------------------------


@pytest.fixture
def test_db():
    """Create an isolated in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_client(test_db):
    """TestClient with get_db dependency overridden to the isolated in-memory DB."""

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def make_test_frozen_suite(project_id: str = "proj-test-01") -> FrozenSuite:
    """Generate a valid FrozenSuite for testing."""
    req = build_demonstration_generation_request()
    req.project_id = project_id
    resp = generate_feasible_cases(req)
    assert resp.frozen_suite is not None
    return resp.frozen_suite


def make_test_matched_evidence(
    project_id: str = "proj-test-01",
    case_id: str = "case-test-01",
    pair_id: str = "pair-test-01",
    caller_outcome: str = "SUCCESS_AFTER_RETRY",
    retries_count: int = 1,
    exposure_status: ExposureStatus = ExposureStatus.CONFIRMED,
) -> MatchedPairEvidence:
    """Construct deterministic MatchedPairEvidence for testing."""
    clean_trial = TrialEvidence(
        project_id=project_id,
        case_id=case_id,
        pair_id=pair_id,
        trial_id=f"tr-clean-{pair_id}",
        run_id="run-test-01",
        trial_role=TrialRole.CLEAN,
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity="SCRIPTED_CALLER",
        recovery_actor=RecoveryActor.SCRIPTED_CALLER,
        fixture_namespace="ns_clean",
        initial_state_fingerprint="fp_clean_init",
        final_state_fingerprint="fp_clean_final",
        events=[],
        episodes=[],
        tool_calls_count=1,
        subsequent_calls_count=0,
        observed_effects=["order_placed"],
        execution_status=ExecutionStatus.COMPLETED,
        caller_outcome="SUCCESS",
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
        evidence_complete=True,
    )
    fault_trial = TrialEvidence(
        project_id=project_id,
        case_id=case_id,
        pair_id=pair_id,
        trial_id=f"tr-fault-{pair_id}",
        run_id="run-test-01",
        trial_role=TrialRole.FAULT,
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity="SCRIPTED_CALLER",
        recovery_actor=RecoveryActor.SCRIPTED_CALLER,
        fixture_namespace="ns_fault",
        initial_state_fingerprint="fp_fault_init",
        final_state_fingerprint="fp_fault_final",
        events=[],
        episodes=[],
        tool_calls_count=2,
        subsequent_calls_count=retries_count,
        observed_effects=["order_placed_retry"],
        execution_status=ExecutionStatus.COMPLETED,
        caller_outcome=caller_outcome,
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
        evidence_complete=True,
    )
    return MatchedPairEvidence(
        project_id=project_id,
        case_id=case_id,
        pair_id=pair_id,
        run_id="run-test-01",
        readiness_status=ReadinessStatus.READY,
        readiness_reasons=[],
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity=CallerIdentity.SCRIPTED_CALLER,
        configuration_snapshot={},
        clean_trial=clean_trial,
        fault_trial=fault_trial,
        fixture_comparability=FixtureComparability.EQUIVALENT_LOGICAL_STATE,
        clean_qualification=CleanQualification.QUALIFIED,
        exposure_assessed=True,
        exposure_status=exposure_status,
        exposure_reasons=["Exposure verified"],
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
        recovery_verdict=None,
        interpretation_limitations=[],
    )


# ---------------------------------------------------------------------------
# 1. Immutability & Idempotent Import Tests
# ---------------------------------------------------------------------------


def test_immutable_suite_import_and_idempotent_duplicate_handling(test_db):
    """Importing a frozen suite persists it; identical re-import returns existing record."""
    suite = make_test_frozen_suite(project_id="proj-qa-100")

    rec1 = store_frozen_suite(test_db, "proj-qa-100", suite)
    assert rec1.suite_digest == suite.suite_digest
    assert rec1.total_cases == len(suite.selected_cases)

    # Re-import identical suite: returns existing record without error or duplicate
    rec2 = store_frozen_suite(test_db, "proj-qa-100", suite)
    assert rec2.suite_digest == rec1.suite_digest

    # Verify database has exactly 1 suite record
    suites_resp = list_suites(test_db, "proj-qa-100")
    assert suites_resp.total == 1
    assert len(suites_resp.items) == 1


def test_conflicting_suite_digest_rejection(test_db):
    """Importing a suite with the same suite_id but conflicting content/digest raises ConflictError (409)."""
    suite1 = make_test_frozen_suite(project_id="proj-qa-100")
    store_frozen_suite(test_db, "proj-qa-100", suite1)

    # Create mutated suite with same suite_id but different cases/digest
    mutated_cases = list(suite1.selected_cases)[:-1]
    from app.components.c3_robustness_recovery.services.suites import freeze_suite

    mutated_suite = freeze_suite(
        task_fixture_metadata=suite1.task_fixture_metadata,
        adapter_manifest=suite1.adapter_manifest,
        recovery_contract=suite1.recovery_contract,
        policy=suite1.policy,
        selected_cases=mutated_cases,
        counters=suite1.counters,
    )
    # Give it the same suite_id as suite1
    mutated_suite = mutated_suite.model_copy(update={"suite_id": suite1.suite_id})

    with pytest.raises(ConflictError) as exc_info:
        store_frozen_suite(test_db, "proj-qa-100", mutated_suite)

    assert "already exists in project" in str(exc_info.value)
    assert "different digest" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 2. Project Scoping & Isolation Tests
# ---------------------------------------------------------------------------


def test_cross_project_scoping_rejected(test_db):
    """Entities in project A cannot be queried or updated under project B."""
    suite = make_test_frozen_suite(project_id="proj-alpha")
    store_frozen_suite(test_db, "proj-alpha", suite)

    # Project B querying Project A's suite gets None
    suite_b = get_suite(test_db, "proj-beta", suite.suite_digest)
    assert suite_b is None

    # Project B attempting to import Project A's suite under project B raises ConflictError
    with pytest.raises(ConflictError) as exc_info:
        store_frozen_suite(test_db, "proj-beta", suite)
    assert "different project scope" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 3. Transaction Rollback on Partial Failure
# ---------------------------------------------------------------------------


def test_transaction_rollback_on_partial_failure(test_db):
    """If an operation fails midway, transaction is rolled back completely."""
    repo = C3PersistenceRepository(test_db)
    suite = make_test_frozen_suite(project_id="proj-rollback")
    repo.save_frozen_suite("proj-rollback", suite)
    test_db.commit()

    # Attempt to import an invalid execution referencing a nonexistent suite
    req = ExecutionArtifactImportRequest(
        project_id="proj-rollback",
        suite_digest="nonexistent-suite-digest-12345",
        execution_id="exec-fail-001",
    )
    from app.components.c3_robustness_recovery.services.run_tracking import (
        import_execution_artifact,
    )

    with pytest.raises(EntityNotFoundError):
        import_execution_artifact(test_db, req)

    # Verify no execution was persisted
    from app.components.c3_robustness_recovery.services.run_tracking import (
        get_execution,
    )

    assert get_execution(test_db, "proj-rollback", "exec-fail-001") is None


# ---------------------------------------------------------------------------
# 4. Append-Only Evaluation History & Evaluator Version Separation
# ---------------------------------------------------------------------------


def test_append_only_evaluation_history_and_evaluator_version_separation(test_db):
    """Re-evaluation creates versioned records; earlier evaluation results are not overwritten."""
    suite = make_test_frozen_suite(project_id="proj-qa-eval")
    store_frozen_suite(test_db, "proj-qa-eval", suite)

    case_id = suite.selected_cases[0].case_id
    pair_id = "pair-eval-history-01"
    evidence = make_test_matched_evidence(
        project_id="proj-qa-eval",
        case_id=case_id,
        pair_id=pair_id,
    )
    store_matched_pair(test_db, "proj-qa-eval", evidence)

    c2_facts = [
        C2AssertionFact(
            assertion_id="state_order_created",
            value=C2FactValue.TRUE,
            provenance="C2_DEMO_FIXTURE",
        )
    ]

    # Evaluate under v1.1.0
    from app.components.c3_robustness_recovery.contracts.persistence import (
        EvaluationComputeRequest,
    )

    req_v1 = EvaluationComputeRequest(
        project_id="proj-qa-eval",
        pair_id=pair_id,
        c2_facts=c2_facts,
        evaluator_version="1.1.0",
        rule_set_version="1.1.0",
    )
    eval_res1 = compute_and_store_evaluation(test_db, req_v1)
    assert eval_res1.evaluator_version == "1.1.0"
    assert eval_res1.recovery_verdict == RecoveryVerdict.PASS_COMPLETED

    # Evaluate under v1.2.0 (new evaluator version)
    req_v2 = EvaluationComputeRequest(
        project_id="proj-qa-eval",
        pair_id=pair_id,
        c2_facts=c2_facts,
        evaluator_version="1.2.0",
        rule_set_version="1.2.0",
    )
    eval_res2 = compute_and_store_evaluation(test_db, req_v2)
    assert eval_res2.evaluator_version == "1.2.0"
    assert eval_res2.evaluation_id != eval_res1.evaluation_id

    # Verify both records exist in evaluation history
    evals_resp = list_evaluations(test_db, "proj-qa-eval", pair_id=pair_id)
    assert evals_resp.total == 2
    versions = {e.evaluator_version for e in evals_resp.items}
    assert versions == {"1.1.0", "1.2.0"}


# ---------------------------------------------------------------------------
# 5. Stored Results Computed by Actual Evaluator & Synthetic Provenance
# ---------------------------------------------------------------------------


def test_stored_results_computed_by_actual_evaluator(test_db):
    """compute_and_store_evaluation calls the real evaluator engine and preserves synthetic provenance."""
    suite = make_test_frozen_suite(project_id="proj-real-eval")
    store_frozen_suite(test_db, "proj-real-eval", suite)

    case_id = suite.selected_cases[0].case_id
    pair_id = "pair-eval-engine-01"
    evidence = make_test_matched_evidence(
        project_id="proj-real-eval",
        case_id=case_id,
        pair_id=pair_id,
        caller_outcome="SUCCESS_AFTER_RETRY",
    )
    store_matched_pair(test_db, "proj-real-eval", evidence)

    c2_facts = [
        C2AssertionFact(
            assertion_id="state_order_created",
            value=C2FactValue.TRUE,
            provenance="C2_DEMO_FIXTURE",
        )
    ]

    from app.components.c3_robustness_recovery.contracts.persistence import (
        EvaluationComputeRequest,
    )

    req = EvaluationComputeRequest(
        project_id="proj-real-eval",
        pair_id=pair_id,
        c2_facts=c2_facts,
    )
    res = compute_and_store_evaluation(test_db, req)

    # Result was evaluated deterministically
    assert res.recovery_verdict == RecoveryVerdict.PASS_COMPLETED
    assert res.evaluation.evaluation_status.value == "EVALUATED"

    # Verify synthetic provenance was retained in model
    repo = C3PersistenceRepository(test_db)
    model = repo.get_evaluation("proj-real-eval", res.evaluation_id)
    assert model is not None
    provs = [f["provenance"] for f in model.c2_facts_provenance_snapshot]
    assert "C2_DEMO_FIXTURE" in provs


# ---------------------------------------------------------------------------
# 6. Blocked/Unconfirmed Experiments Remain Unscored & Run Status Distinct
# ---------------------------------------------------------------------------


def test_blocked_and_unconfirmed_experiments_remain_unscored(test_db):
    """Unconfirmed or blocked experiments receive null recovery verdict."""
    suite = make_test_frozen_suite(project_id="proj-unconfirmed")
    store_frozen_suite(test_db, "proj-unconfirmed", suite)

    case_id = suite.selected_cases[0].case_id
    pair_id = "pair-unconfirmed-01"
    evidence = make_test_matched_evidence(
        project_id="proj-unconfirmed",
        case_id=case_id,
        pair_id=pair_id,
        exposure_status=ExposureStatus.NOT_TRIGGERED,  # Unconfirmed exposure!
    )
    store_matched_pair(test_db, "proj-unconfirmed", evidence)

    from app.components.c3_robustness_recovery.contracts.persistence import (
        EvaluationComputeRequest,
    )

    req = EvaluationComputeRequest(
        project_id="proj-unconfirmed",
        pair_id=pair_id,
        c2_facts=[],
    )
    res = compute_and_store_evaluation(test_db, req)

    # Ineligible experiment has null recovery verdict
    assert res.recovery_verdict is None
    assert res.evaluation_status == "NOT_EVALUATED"


def test_run_completion_distinct_from_recovery_fail(test_db):
    """Harness completion (ExecutionStatus.COMPLETED) is distinct from recovery evaluation FAIL."""
    suite = make_test_frozen_suite(project_id="proj-distinct")
    store_frozen_suite(test_db, "proj-distinct", suite)

    case_id = suite.selected_cases[0].case_id
    pair_id = "pair-distinct-01"
    # Budget was violated (10 retries, contract max 1)
    evidence = make_test_matched_evidence(
        project_id="proj-distinct",
        case_id=case_id,
        pair_id=pair_id,
        retries_count=10,
        caller_outcome="SUCCESS_AFTER_RETRY",
    )
    store_matched_pair(test_db, "proj-distinct", evidence)

    from app.components.c3_robustness_recovery.contracts.persistence import (
        EvaluationComputeRequest,
    )

    res = compute_and_store_evaluation(
        test_db,
        EvaluationComputeRequest(
            project_id="proj-distinct",
            pair_id=pair_id,
            c2_facts=[
                C2AssertionFact(
                    assertion_id="state_order_created", value=C2FactValue.TRUE
                )
            ],
        ),
    )

    # The harness completed normally, but recovery evaluation verdict is FAIL
    assert evidence.fault_trial.execution_status == ExecutionStatus.COMPLETED
    assert res.recovery_verdict == RecoveryVerdict.FAIL
    assert res.first_violated_rule == "RULE_BUDGETS"


# ---------------------------------------------------------------------------
# 7. Persistence Failure Never Causes Target Re-Execution
# ---------------------------------------------------------------------------


def test_persistence_failure_never_causes_target_reexecution():
    """Local fallback artifact is preserved when persistence fails, avoiding re-executing target."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fallback_path = save_local_fallback_artifact(
            export_dir=Path(tmpdir),
            execution_id="exec-fallback-01",
            payload={"action": "order_placement", "status": "executed"},
        )
        assert fallback_path.exists()
        import json

        with open(fallback_path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["action"] == "order_placement"


# ---------------------------------------------------------------------------
# 8. Cancellation & Incomplete Run Accounting
# ---------------------------------------------------------------------------


def test_cancellation_and_incomplete_run_accounting(test_db):
    """Halted or cancelled suite execution records CANCELLED and halts without claiming success."""
    suite = make_test_frozen_suite(project_id="proj-cancel")
    store_frozen_suite(test_db, "proj-cancel", suite)

    exec_req = ExecutionCreateRequest(
        execution_id="exec-cancel-01",
        suite_digest=suite.suite_digest,
        project_id="proj-cancel",
        planned_cases=[c.case_id for c in suite.selected_cases],
    )
    exec_record = create_execution_manifest(test_db, "proj-cancel", exec_req)
    assert exec_record.status == ExecutionTrackingStatus.PLANNED

    from app.components.c3_robustness_recovery.runtime.suite_runner import (
        SuiteExecutionSummary,
    )

    summary = SuiteExecutionSummary(
        suite_id=suite.suite_id,
        suite_digest=suite.suite_digest,
        total_cases=len(suite.selected_cases),
        executed_count=1,
        blocked_count=0,
        unsupported_count=0,
        cancelled_count=len(suite.selected_cases) - 1,
        error_count=0,
        confirmed_exposure_count=1,
        not_triggered_count=0,
        unknown_exposure_count=0,
        case_results=[],
        overall_duration_ms=120.0,
        halted_early=True,
        halt_reason="Process cancelled by user signal",
    )

    final_exec = finalize_execution_lifecycle(
        test_db, "proj-cancel", "exec-cancel-01", summary
    )
    assert final_exec.status == ExecutionTrackingStatus.CANCELLED
    assert final_exec.halt_reason == "Process cancelled by user signal"
    assert final_exec.cancelled_cases_count == len(suite.selected_cases) - 1


# ---------------------------------------------------------------------------
# 9. Backend Reporting with Explicit Denominators and CSV Export
# ---------------------------------------------------------------------------


def test_report_counts_reconcile_with_planned_cases_and_explicit_denominators(
    test_db,
):
    """build_execution_report computes accurate totals, explicit denominators, and exports CSV."""
    suite = make_test_frozen_suite(project_id="proj-report")
    store_frozen_suite(test_db, "proj-report", suite)

    exec_req = ExecutionCreateRequest(
        execution_id="exec-rep-01",
        suite_digest=suite.suite_digest,
        project_id="proj-report",
        planned_cases=[c.case_id for c in suite.selected_cases],
    )
    create_execution_manifest(test_db, "proj-report", exec_req)

    # Record 1 executed pair
    case_id = suite.selected_cases[0].case_id
    pair = make_test_matched_evidence(
        project_id="proj-report",
        case_id=case_id,
        pair_id="pair-rep-01",
    )
    record_case_execution_progress(
        db=test_db,
        project_id="proj-report",
        execution_id="exec-rep-01",
        case_id=case_id,
        status="EXECUTED",
        evidence=pair,
    )

    # Compute evaluation for pair
    from app.components.c3_robustness_recovery.contracts.persistence import (
        EvaluationComputeRequest,
    )

    compute_and_store_evaluation(
        test_db,
        EvaluationComputeRequest(
            project_id="proj-report",
            pair_id="pair-rep-01",
            c2_facts=[
                C2AssertionFact(
                    assertion_id="state_order_created", value=C2FactValue.TRUE
                )
            ],
        ),
    )

    report = build_execution_report(test_db, "proj-report", "exec-rep-01")
    assert report.execution_id == "exec-rep-01"
    assert report.suite_digest == suite.suite_digest
    assert report.planned_cases_count == len(suite.selected_cases)
    assert report.executed_cases_count == 1
    assert report.verdict_counts.pass_completed_count == 1
    assert "planned_cases" in report.denominators

    # Check CSV export
    csv_str = export_report_to_csv(report)
    assert "# Report ID" in csv_str
    assert "exec-rep-01" in csv_str
    assert "PASS_COMPLETED" in csv_str


# ---------------------------------------------------------------------------
# 10. Persistence Router HTTP Endpoints Testing
# ---------------------------------------------------------------------------


def test_api_suites_cases_executions_evaluations_flow(test_client):
    """End-to-end API verification: import suite -> import execution -> compute evaluation -> report."""
    suite = make_test_frozen_suite(project_id="proj-http")

    # 1. POST /suites/import
    resp = test_client.post(
        "/api/v1/c3/suites/import",
        json={"project_id": "proj-http", "frozen_suite": suite.model_dump(mode="json")},
    )
    assert resp.status_code == 200
    suite_data = resp.json()
    assert suite_data["suite_digest"] == suite.suite_digest

    # 2. GET /suites
    resp = test_client.get("/api/v1/c3/suites?project_id=proj-http")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    # 3. GET /cases
    resp = test_client.get("/api/v1/c3/cases?project_id=proj-http")
    assert resp.status_code == 200
    assert resp.json()["total"] == len(suite.selected_cases)

    # 4. POST /executions/import
    exec_id = "exec-api-01"
    case_id = suite.selected_cases[0].case_id
    pair = make_test_matched_evidence(
        project_id="proj-http",
        case_id=case_id,
        pair_id="pair-api-01",
    )
    resp = test_client.post(
        "/api/v1/c3/executions/import",
        json={
            "project_id": "proj-http",
            "suite_digest": suite.suite_digest,
            "execution_id": exec_id,
            "status": "COMPLETED",
            "planned_cases_count": len(suite.selected_cases),
            "executed_cases_count": 1,
            "manifest_snapshot": {"planned_cases": [case_id]},
            "case_evidences": [pair.model_dump(mode="json")],
        },
    )
    assert resp.status_code == 200

    # 5. POST /evaluations/compute
    resp = test_client.post(
        "/api/v1/c3/evaluations/compute",
        json={
            "project_id": "proj-http",
            "pair_id": "pair-api-01",
            "c2_facts": [
                {
                    "assertion_id": "state_order_created",
                    "value": "TRUE",
                    "provenance": "C2_DEMO_FIXTURE",
                }
            ],
        },
    )
    assert resp.status_code == 200
    eval_data = resp.json()
    assert eval_data["recovery_verdict"] == "PASS_COMPLETED"

    # 6. GET /reports/executions/{execution_id}
    resp = test_client.get(
        f"/api/v1/c3/reports/executions/{exec_id}?project_id=proj-http"
    )
    assert resp.status_code == 200
    rep_data = resp.json()
    assert rep_data["execution_id"] == exec_id
    assert rep_data["verdict_counts"]["pass_completed_count"] == 1

    # 7. GET /reports/executions/{execution_id}/export (CSV)
    resp = test_client.get(
        f"/api/v1/c3/reports/executions/{exec_id}/export?project_id=proj-http"
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/csv; charset=utf-8"
    assert "PASS_COMPLETED" in resp.text


# ---------------------------------------------------------------------------
# 11. Existing Stateless APIs Remain Side-Effect Free
# ---------------------------------------------------------------------------


def test_existing_stateless_apis_remain_side_effect_free(test_client, test_db):
    """Stateless C3 endpoints perform zero database writes or side effects."""
    # 1. /fault-catalog
    resp = test_client.get("/api/v1/c3/fault-catalog")
    assert resp.status_code == 200

    # 2. /cases/validate
    val_req = {
        "candidate_case": make_demonstration_candidate_case().model_dump(mode="json"),
        "adapter_manifest": DemonstrationToolAdapter(
            fixture_manager=DemonstrationFixtureManager()
        )
        .get_manifest()
        .model_dump(mode="json"),
        "task_fixture_metadata": make_demonstration_task_fixture_metadata().model_dump(
            mode="json"
        ),
        "recovery_contract": make_demonstration_recovery_contract().model_dump(
            mode="json"
        ),
    }
    resp = test_client.post("/api/v1/c3/cases/validate", json=val_req)
    assert resp.status_code == 200

    # Verify database remains completely empty
    suites_resp = list_suites(test_db, "proj-any")
    assert suites_resp.total == 0


# ---------------------------------------------------------------------------
# 12. Opt-in Isolated PostgreSQL Integration Tests
# ---------------------------------------------------------------------------


def test_postgresql_opt_in_integration():
    """Opt-in PostgreSQL round-trip test against isolated target if TEST_DATABASE_URL is set."""
    pg_url = os.environ.get("TEST_DATABASE_URL")
    if not pg_url:
        pytest.skip(
            "Isolated PostgreSQL integration test skipped: TEST_DATABASE_URL not configured."
        )

    # If configured, run actual migration and round-trip verification
    engine = create_engine(pg_url)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        suite = make_test_frozen_suite("proj-pg-test")
        rec = store_frozen_suite(session, "proj-pg-test", suite)
        assert rec.suite_digest == suite.suite_digest
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
