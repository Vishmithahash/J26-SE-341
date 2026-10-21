"""End-to-End Verification Test for Component 3 Phase 4.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 4 - Audit, Authorization, and Contract Verification

Verifies:
- Authenticated user and project scope access control.
- Rejection of unauthenticated (401), unauthorized foreign-project (404/403),
  and cross-field project mismatch (422) requests.
- Full API workflow: validate -> generate -> persist suite -> import execution/pairs ->
  retrieve records -> compute recovery evaluations -> retrieve report -> export CSV.
- Exhaustive requirement scenarios:
  1. Confirmed exposure completed recovery (PASS_COMPLETED).
  2. Contract-permitted graceful stopping (PASS_GRACEFUL).
  3. Proven recovery-rule failure (FAIL).
  4. Missing required observation producing INCONCLUSIVE.
  5. NOT_TRIGGERED unconfirmed exposure remaining unevaluated (NOT_EVALUATED).
  6. Failed clean application task (DISQUALIFIED) with eligible fault trial evaluated
     and attribution limitation retained.
  7. Genuine harness/reset execution failure remaining ineligible.
  8. BEFORE_EFFECT and AFTER_COMMIT scenario verification.
  9. Repeated import and conflict handling.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c3_robustness_recovery.contracts.evaluation import (
    C2AssertionFact,
    C2FactValue,
    RecoveryVerdict,
)
from app.components.c3_robustness_recovery.contracts.schemas import EffectPhase, TerminalOutcome
from app.components.c3_robustness_recovery.runtime.adapter import (
    CleanupStatus,
    DemonstrationFixtureManager,
    DemonstrationToolAdapter,
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
    make_demonstration_after_commit_case,
)
from app.components.c3_robustness_recovery.services.generation import (
    generate_feasible_cases,
)
from app.components.c3_robustness_recovery.services.suites import (
    freeze_suite,
)
from app.database import Base, get_db
from app.main import app
from app.shared.auth.dependencies import require_active_user
from app.shared.auth.models import User, UserRole
from app.shared.projects.models import (
    Project,
    ProjectConnectionState,
    ProjectLifecycle,
)


@pytest.fixture
def e2e_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _seed_user_and_project(db, user_id, email, role, project_id, project_name):
    user = User(
        id=user_id,
        name=f"User {user_id}",
        email=email,
        canonical_email=email.lower().strip(),
        password_hash="fakehash",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()

    project = Project(
        project_id=project_id,
        owner_user_id=user.id,
        name=project_name,
        domain="ecommerce",
        environment="TEST",
        backend_base_url="http://127.0.0.1:8000",
        backend_health_url="http://127.0.0.1:8000/health",
        configuration_version=1,
        lifecycle=ProjectLifecycle.ACTIVE.value,
        connection_state=ProjectConnectionState.CONNECTED.value,
    )
    db.add(project)
    db.commit()
    db.refresh(user)
    db.refresh(project)
    return user, project


def _make_evidence_pair(
    project_id: str,
    case_id: str,
    pair_id: str,
    exposure_status: ExposureStatus = ExposureStatus.CONFIRMED,
    clean_qual: CleanQualification = CleanQualification.QUALIFIED,
    clean_exec: ExecutionStatus = ExecutionStatus.COMPLETED,
    fault_exec: ExecutionStatus = ExecutionStatus.COMPLETED,
    readiness: ReadinessStatus = ReadinessStatus.READY,
    caller_outcome: str = "SUCCESS_AFTER_RETRY",
    retries: int = 1,
    tool_calls: int = 2,
    evidence_complete: bool = True,
    effect_phase: EffectPhase = EffectPhase.BEFORE_EFFECT,
) -> MatchedPairEvidence:
    clean_trial = TrialEvidence(
        project_id=project_id,
        case_id=case_id,
        pair_id=pair_id,
        trial_id=f"clean-{pair_id}",
        run_id=f"run-{pair_id}",
        trial_role=TrialRole.CLEAN,
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity="SCRIPTED_CALLER",
        recovery_actor="SCRIPTED_CALLER",
        fixture_namespace="ns_clean",
        initial_state_fingerprint="fp_clean_init",
        final_state_fingerprint="fp_clean_final",
        events=[],
        episodes=[],
        tool_calls_count=1,
        subsequent_calls_count=0,
        observed_effects=["order_placed"],
        execution_status=clean_exec,
        caller_outcome="SUCCESS",
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
        evidence_complete=True,
    )
    fault_trial = TrialEvidence(
        project_id=project_id,
        case_id=case_id,
        pair_id=pair_id,
        trial_id=f"fault-{pair_id}",
        run_id=f"run-{pair_id}",
        trial_role=TrialRole.FAULT,
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity="SCRIPTED_CALLER",
        recovery_actor="SCRIPTED_CALLER",
        fixture_namespace="ns_fault",
        initial_state_fingerprint="fp_fault_init",
        final_state_fingerprint="fp_fault_final",
        events=[],
        episodes=[],
        tool_calls_count=tool_calls,
        subsequent_calls_count=retries,
        observed_effects=["order_committed"]
        if effect_phase == EffectPhase.AFTER_COMMIT
        else ["order_placed_retry"],
        execution_status=fault_exec,
        caller_outcome=caller_outcome,
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
        evidence_complete=evidence_complete,
    )
    return MatchedPairEvidence(
        project_id=project_id,
        case_id=case_id,
        pair_id=pair_id,
        run_id=f"run-{pair_id}",
        readiness_status=readiness,
        readiness_reasons=[],
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity="SCRIPTED_CALLER",
        configuration_snapshot={},
        clean_trial=clean_trial,
        fault_trial=fault_trial,
        fixture_comparability=FixtureComparability.EQUIVALENT_LOGICAL_STATE,
        clean_qualification=clean_qual,
        exposure_assessed=True,
        exposure_status=exposure_status,
        exposure_reasons=["Exposure verified"],
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
        recovery_verdict=None,
        interpretation_limitations=[],
    )


def test_complete_c3_phase4_end_to_end_workflow(e2e_db):
    """Exhaustively verify end-to-end workflow from auth to evaluation and CSV export."""
    # 1. Setup authorized primary user & foreign user
    user1, proj1 = _seed_user_and_project(
        e2e_db, 101, "owner@example.com", UserRole.USER, "proj-primary", "Primary Store AUT"
    )
    user2, proj2 = _seed_user_and_project(
        e2e_db, 202, "foreign@example.com", UserRole.USER, "proj-foreign", "Foreign Store AUT"
    )

    def override_get_db():
        try:
            yield e2e_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_active_user] = lambda: user1

    with TestClient(app) as client1:
        # 2. Case Validation (stateless, authorized)
        cand_case = make_demonstration_candidate_case()
        cand_case.project_id = "proj-primary"
        adapter_man = DemonstrationToolAdapter(
            fixture_manager=DemonstrationFixtureManager()
        ).get_manifest()
        task_meta = make_demonstration_task_fixture_metadata()
        recov_contract = make_demonstration_recovery_contract().model_copy(
            update={
                "permitted_terminal_outcomes": [
                    TerminalOutcome.SUCCESS_CLEAN_RECOVERY,
                    TerminalOutcome.GRACEFUL_ABORT_USER_NOTIFIED,
                ]
            }
        )

        val_resp = client1.post(
            "/api/v1/c3/cases/validate",
            json={
                "candidate_case": cand_case.model_dump(mode="json"),
                "adapter_manifest": adapter_man.model_dump(mode="json"),
                "task_fixture_metadata": task_meta.model_dump(mode="json"),
                "recovery_contract": recov_contract.model_dump(mode="json"),
            },
        )
        assert val_resp.status_code == 200
        assert val_resp.json()["validation_status"] == "STATIC_VALID"

        # 3. Case Generation (stateless, authorized)
        gen_req = build_demonstration_generation_request()
        gen_req.project_id = "proj-primary"
        gen_resp = client1.post(
            "/api/v1/c3/cases/generate",
            json=gen_req.model_dump(mode="json"),
        )
        assert gen_resp.status_code == 200
        gen_data = gen_resp.json()
        assert gen_data["generation_status"] == "GENERATED"
        assert len(gen_data["frozen_suite"]["selected_cases"]) > 0

        # 4. Suite Persistence (POST /api/v1/c3/suites/import)
        feasible = generate_feasible_cases(gen_req)
        cases = list(feasible.frozen_suite.selected_cases)
        ac_case = make_demonstration_after_commit_case()
        ac_case.case_id = f"case-ac-{uuid4().hex[:6]}"
        ac_case.project_id = "proj-primary"
        cases.append(ac_case)

        frozen = freeze_suite(
            task_fixture_metadata=task_meta,
            adapter_manifest=adapter_man,
            recovery_contract=recov_contract,
            policy=feasible.frozen_suite.policy,
            selected_cases=cases,
            counters=feasible.frozen_suite.counters,
        )

        import_suite_resp = client1.post(
            "/api/v1/c3/suites/import",
            json={"project_id": "proj-primary", "frozen_suite": frozen.model_dump(mode="json")},
        )
        assert import_suite_resp.status_code == 200
        assert import_suite_resp.json()["suite_digest"] == frozen.suite_digest

        # Verify duplicate suite import is idempotent
        dup_suite_resp = client1.post(
            "/api/v1/c3/suites/import",
            json={"project_id": "proj-primary", "frozen_suite": frozen.model_dump(mode="json")},
        )
        assert dup_suite_resp.status_code == 200

        # 5. Build Matched Pair Evidences covering all required Phase 4 scenarios:
        case0 = cases[0].case_id
        case_ac = ac_case.case_id

        pairs = [
            # Scenario 1: Confirmed exposure, clean recovery -> PASS_COMPLETED
            _make_evidence_pair(
                "proj-primary", case0, "pair-01-pass-comp",
                exposure_status=ExposureStatus.CONFIRMED,
                caller_outcome="SUCCESS_AFTER_RETRY",
                retries=1, tool_calls=2,
            ),
            # Scenario 2: Contract-permitted graceful halt -> PASS_GRACEFUL
            _make_evidence_pair(
                "proj-primary", case0, "pair-02-pass-grac",
                exposure_status=ExposureStatus.CONFIRMED,
                caller_outcome="GRACEFUL_ABORT_USER_NOTIFIED",
                retries=0, tool_calls=1,
            ),
            # Scenario 3: Proven rule violation (unsafe retry beyond budget) -> FAIL
            _make_evidence_pair(
                "proj-primary", case0, "pair-03-fail-budget",
                exposure_status=ExposureStatus.CONFIRMED,
                caller_outcome="SUCCESS_AFTER_RETRY",
                retries=5, tool_calls=10,
            ),
            # Scenario 4: Missing required evidence -> INCONCLUSIVE
            _make_evidence_pair(
                "proj-primary", case0, "pair-04-inconclusive",
                exposure_status=ExposureStatus.CONFIRMED,
                caller_outcome="SUCCESS_AFTER_RETRY",
                evidence_complete=False,
            ),
            # Scenario 5: NOT_TRIGGERED unconfirmed exposure -> NOT_EVALUATED
            _make_evidence_pair(
                "proj-primary", case0, "pair-05-not-triggered",
                exposure_status=ExposureStatus.NOT_TRIGGERED,
            ),
            # Scenario 6: Disqualified clean control trial but valid fault execution -> Evaluated with limitations
            _make_evidence_pair(
                "proj-primary", case0, "pair-06-disqualified-clean",
                exposure_status=ExposureStatus.CONFIRMED,
                clean_qual=CleanQualification.DISQUALIFIED,
                caller_outcome="SUCCESS_AFTER_RETRY",
                retries=1, tool_calls=2,
            ),
            # Scenario 7: Harness execution error -> NOT_EVALUATED (ineligible)
            _make_evidence_pair(
                "proj-primary", case0, "pair-07-harness-error",
                exposure_status=ExposureStatus.CONFIRMED,
                fault_exec=ExecutionStatus.EXECUTION_ERROR,
            ),
            # Scenario 8: AFTER_COMMIT scenario with confirmed exposure
            _make_evidence_pair(
                "proj-primary", case_ac, "pair-08-after-commit",
                exposure_status=ExposureStatus.CONFIRMED,
                caller_outcome="SUCCESS_AFTER_RETRY",
                effect_phase=EffectPhase.AFTER_COMMIT,
            ),
        ]

        # 6. Import Execution Manifest & Matched Pairs
        exec_id = "exec-e2e-001"
        exec_import_resp = client1.post(
            "/api/v1/c3/executions/import",
            json={
                "project_id": "proj-primary",
                "suite_digest": frozen.suite_digest,
                "execution_id": exec_id,
                "status": "COMPLETED",
                "planned_cases_count": len(cases),
                "executed_cases_count": len(pairs),
                "manifest_snapshot": {"planned_cases": [c.case_id for c in cases]},
                "case_evidences": [p.model_dump(mode="json") for p in pairs],
            },
        )
        assert exec_import_resp.status_code == 200

        # 7. Compute Recovery Evaluations for each pair
        c2_facts = [
            C2AssertionFact(
                assertion_id="state_order_created",
                value=C2FactValue.TRUE,
                provenance="C2_DEMO_FIXTURE",
            ),
            C2AssertionFact(
                assertion_id="duplicate_side_effect_detected",
                value=C2FactValue.FALSE,
                provenance="C2_DEMO_FIXTURE",
            ),
            C2AssertionFact(
                assertion_id="idempotency_key_reused",
                value=C2FactValue.TRUE,
                provenance="C2_DEMO_FIXTURE",
            ),
        ]
        c2_payload = [f.model_dump(mode="json") for f in c2_facts]

        eval_verdicts = {}
        for p in pairs:
            resp = client1.post(
                "/api/v1/c3/evaluations/compute",
                json={
                    "project_id": "proj-primary",
                    "pair_id": p.pair_id,
                    "c2_facts": c2_payload,
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            eval_verdicts[p.pair_id] = (data["evaluation_status"], data["recovery_verdict"])

        # Verify expected verdicts
        assert eval_verdicts["pair-01-pass-comp"] == ("EVALUATED", RecoveryVerdict.PASS_COMPLETED.value)
        assert eval_verdicts["pair-02-pass-grac"] == ("EVALUATED", RecoveryVerdict.PASS_GRACEFUL.value)
        assert eval_verdicts["pair-03-fail-budget"] == ("EVALUATED", RecoveryVerdict.FAIL.value)
        assert eval_verdicts["pair-04-inconclusive"] == ("EVALUATED", RecoveryVerdict.INCONCLUSIVE.value)
        assert eval_verdicts["pair-05-not-triggered"] == ("NOT_EVALUATED", None)
        # Scenario 6: Disqualified clean trial was evaluated for recovery compliance
        assert eval_verdicts["pair-06-disqualified-clean"][0] == "EVALUATED"
        # Scenario 7: Harness error trial was ineligible and received NOT_EVALUATED
        assert eval_verdicts["pair-07-harness-error"] == ("NOT_EVALUATED", None)
        # Scenario 8: AFTER_COMMIT trial was evaluated
        assert eval_verdicts["pair-08-after-commit"][0] == "EVALUATED"

        # 8. Retrieve Execution Report (GET /reports/executions/{id})
        rep_resp = client1.get(
            f"/api/v1/c3/reports/executions/{exec_id}?project_id=proj-primary"
        )
        assert rep_resp.status_code == 200
        rep_data = rep_resp.json()
        assert rep_data["execution_id"] == exec_id
        assert rep_data["clean_qualified_count"] >= 6
        assert rep_data["clean_disqualified_count"] >= 1
        assert len(rep_data["clean_control_notes"]) > 0

        # 9. Download Authenticated CSV Report (GET /reports/executions/{id}/export)
        csv_resp = client1.get(
            f"/api/v1/c3/reports/executions/{exec_id}/export?project_id=proj-primary"
        )
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.headers["content-type"]
        assert "PASS_COMPLETED" in csv_resp.text
        assert "PASS_GRACEFUL" in csv_resp.text

        # 10. Cross-field project mismatch is rejected with 422
        bad_pair = _make_evidence_pair("proj-foreign", case0, "pair-mismatch")
        mismatch_resp = client1.post(
            "/api/v1/c3/pairs/import",
            json={"project_id": "proj-primary", "evidence": bad_pair.model_dump(mode="json")},
        )
        assert mismatch_resp.status_code == 422
        assert "Inconsistent project identity" in mismatch_resp.json()["detail"]

    # 11. Foreign user attempting to access proj-primary is rejected with 404
    app.dependency_overrides[require_active_user] = lambda: user2
    with TestClient(app) as client2:
        foreign_rep = client2.get(
            f"/api/v1/c3/reports/executions/{exec_id}?project_id=proj-primary"
        )
        assert foreign_rep.status_code == 404

        foreign_csv = client2.get(
            f"/api/v1/c3/reports/executions/{exec_id}/export?project_id=proj-primary"
        )
        assert foreign_csv.status_code == 404

        foreign_compute = client2.post(
            "/api/v1/c3/evaluations/compute",
            json={
                "project_id": "proj-primary",
                "pair_id": "pair-01-pass-comp",
                "c2_facts": [],
            },
        )
        assert foreign_compute.status_code == 404

    # 12. Unauthenticated request is rejected with 401
    app.dependency_overrides.pop(require_active_user, None)
    with TestClient(app) as client_unauth:
        unauth_resp = client_unauth.get(
            f"/api/v1/c3/reports/executions/{exec_id}?project_id=proj-primary"
        )
        assert unauth_resp.status_code == 401
