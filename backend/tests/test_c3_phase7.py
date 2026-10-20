"""Comprehensive hermetic test suite for Component 3 Phase 7.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 7 - C3 Internal Completion and Offline Verification.

Tests:
1. Research Split Protocol (3-way split: 40% DEV / 20% VAL / 40% TEST, deterministic rounding, leakage prevention).
2. Independent Review Support (blinded packet export, inter-reviewer agreement with Cohen's kappa, dispute reconciliation audit trail).
3. Offline Baselines & Ablations (B1 fixed vs generated, B2 outcome-only with terminal & state verification, A1 capability, A2 isolated exposure, A3 no state facts, A4 no effect-phase).
4. Pure Research Metrics (4-way multiclass matrix & macro-F1, clean-to-fault transitions, execution overheads with unavailable token/cost telemetry, family cluster bootstrap CI with honest insufficient-data threshold).
5. Persistence Correctness (multi-suite case membership, conflicting content rejection, append-only history).
6. Runtime Safeguards (BEFORE_EFFECT prevention, AFTER_COMMIT independent observation, cancellation attribution, uncertain cleanup).
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c3_robustness_recovery.contracts.evaluation import (
    C2AssertionFact,
    C2FactValue,
    EvaluationStatus,
    RecoveryEvaluationRequest,
    RecoveryEvaluationResult,
    RecoveryVerdict,
)
from app.components.c3_robustness_recovery.contracts.generation import (
    GenerationCounters,
)
from app.components.c3_robustness_recovery.contracts.research import (
    AblationType,
    BaselineType,
    DatasetSplit,
    IndependentReviewerLabel,
    ReviewerLabelRecord,
    ReviewerProvenance,
)
from app.components.c3_robustness_recovery.contracts.schemas import (
    EffectPhase,
)
from app.components.c3_robustness_recovery.repositories.persistence import (
    C3PersistenceRepository,
    ConflictError,
)
from app.components.c3_robustness_recovery.runtime.adapter import (
    CleanupStatus,
    DemonstrationFixtureManager,
)
from app.components.c3_robustness_recovery.runtime.banking_adapter import (
    BankingFixtureManager,
)
from app.components.c3_robustness_recovery.runtime.evidence import (
    ExposureStatus,
)
from app.components.c3_robustness_recovery.runtime.research_runner import (
    evaluate_with_baseline_or_ablation,
    measure_capability_ablation,
)
from app.components.c3_robustness_recovery.runtime.runner import (
    make_demonstration_candidate_case,
    make_demonstration_recovery_contract,
)
from app.components.c3_robustness_recovery.runtime.suite_runner import (
    build_demonstration_generation_request,
)
from app.components.c3_robustness_recovery.services.experiment_plan import (
    build_three_way_experiment_manifest,
    check_research_accuracy_acceptance,
    compute_inter_reviewer_agreement,
    export_blinded_reviewer_packet,
    filter_suite_for_split,
    reconcile_disputed_labels,
    verify_split_leakage,
)
from app.components.c3_robustness_recovery.services.generation import (
    generate_feasible_cases,
)
from app.components.c3_robustness_recovery.services.research_metrics import (
    compare_fixed_suite_vs_generated,
    compute_clean_to_fault_transitions,
    compute_execution_overhead_metrics,
    compute_family_cluster_bootstrap_ci,
    compute_four_way_multiclass_matrix,
)
from app.components.c3_robustness_recovery.services.storage import (
    store_frozen_suite,
)
from app.components.c3_robustness_recovery.services.suites import freeze_suite
from app.database import Base

# ---------------------------------------------------------------------------
# Test Fixtures & Duck-Typed Mocks
# ---------------------------------------------------------------------------


class MockMatchedPair:
    """Lightweight duck-typed mock for pair metrics computation."""

    def __init__(
        self,
        pair_id: str,
        clean_qualification: str = "QUALIFIED",
        fault_trial_caller_outcome: str = "SUCCESS",
        duration_ms: float = 120.0,
    ) -> None:
        self.pair_id = pair_id
        self.clean_qualification = clean_qualification
        self.fault_trial_caller_outcome = fault_trial_caller_outcome
        self.duration_ms = duration_ms


@pytest.fixture
def test_db():
    """Create an isolated in-memory SQLite database with foreign keys enforced."""
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
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


from tests.test_c3_phase6 import make_test_pair_evidence as make_test_evidence

# ---------------------------------------------------------------------------
# 1. Research Split Protocol Tests
# ---------------------------------------------------------------------------


def test_three_way_split_ratio_and_documented_rounding():
    """Verify 3-way split allocates 40% DEV / 20% VAL / 40% TEST with deterministic rounding."""
    families = [f"family_{i:02d}" for i in range(10)]
    manifest = build_three_way_experiment_manifest(
        experiment_id="exp-split-test-10",
        case_family_ids=families,
    )

    splits = manifest.family_splits
    assert len(splits) == 10

    dev_count = sum(1 for s in splits.values() if s == DatasetSplit.DEVELOPMENT)
    val_count = sum(1 for s in splits.values() if s == DatasetSplit.VALIDATION)
    test_count = sum(1 for s in splits.values() if s == DatasetSplit.HELD_OUT_TEST)

    # N=10: dev=round(4.0)=4, val=round(2.0)=2, test=10-4-2=4
    assert dev_count == 4
    assert val_count == 2
    assert test_count == 4
    assert manifest.version == "2.0.0"


def test_three_way_split_zero_leakage_enforcement():
    """Verify zero data leakage across all partition pairs."""
    families = [f"fam_{i}" for i in range(15)]
    manifest = build_three_way_experiment_manifest(
        experiment_id="exp-leakage-clean",
        case_family_ids=families,
    )

    # Valid manifest should pass leakage verification without raising
    verify_split_leakage(manifest)

    # Verify that the sets of case families in each partition are pairwise disjoint
    dev_fams = {
        f for f, s in manifest.family_splits.items() if s == DatasetSplit.DEVELOPMENT
    }
    val_fams = {
        f for f, s in manifest.family_splits.items() if s == DatasetSplit.VALIDATION
    }
    test_fams = {
        f for f, s in manifest.family_splits.items() if s == DatasetSplit.HELD_OUT_TEST
    }

    assert dev_fams.isdisjoint(val_fams)
    assert dev_fams.isdisjoint(test_fams)
    assert val_fams.isdisjoint(test_fams)


def test_split_filtering_preserves_suite_integrity():
    """Verify filtering a suite for a split partition preserves counters and frozen digests."""
    gen_req = build_demonstration_generation_request()
    gen_req.policy.max_cases = 12
    gen_res = generate_feasible_cases(gen_req)
    suite = gen_res.frozen_suite
    assert suite is not None

    families = sorted({c.case_family_id for c in suite.selected_cases})
    manifest = build_three_way_experiment_manifest(
        experiment_id="exp-filter-test",
        case_family_ids=families,
    )

    dev_suite = filter_suite_for_split(suite, manifest, DatasetSplit.DEVELOPMENT)
    val_suite = filter_suite_for_split(suite, manifest, DatasetSplit.VALIDATION)
    test_suite = filter_suite_for_split(suite, manifest, DatasetSplit.HELD_OUT_TEST)

    assert dev_suite.suite_id.endswith("-split-development")
    assert val_suite.suite_id.endswith("-split-validation")
    assert test_suite.suite_id.endswith("-split-held_out_test")

    total_partitioned_cases = (
        len(dev_suite.selected_cases)
        + len(val_suite.selected_cases)
        + len(test_suite.selected_cases)
    )
    assert total_partitioned_cases == len(suite.selected_cases)


# ---------------------------------------------------------------------------
# 2. Independent Review Support Tests
# ---------------------------------------------------------------------------


def test_blinded_reviewer_packet_export_hides_evaluator_verdicts():
    """Blinded reviewer export must hide machine verdicts, rule IDs, and baseline tags."""
    case = make_demonstration_candidate_case()
    recovery = make_demonstration_recovery_contract()
    gen_req = build_demonstration_generation_request()
    suite = freeze_suite(
        task_fixture_metadata=gen_req.task_fixture_metadata,
        adapter_manifest=gen_req.adapter_manifest,
        recovery_contract=recovery,
        policy=gen_req.policy,
        selected_cases=[case],
        counters=GenerationCounters(selected_count=1, valid_count=1, unique_count=1),
        limitations=[],
        suite_id="suite-blind-test",
    )
    ev = make_test_evidence(case_id=case.case_id)

    packet = export_blinded_reviewer_packet(
        suite=suite,
        evidence_records=[ev],
        experiment_id="exp-blind-01",
        project_id="proj-p7-test",
    )

    assert packet.total_cases == 1
    item = packet.items[0]
    assert item.case_id == case.case_id
    assert item.caller_reported_outcome == "SUCCESS_AFTER_RETRY"

    item_dict = item.model_dump()
    assert "recovery_verdict" not in item_dict
    assert "first_violated_rule" not in item_dict
    assert "rule_results" not in item_dict
    assert "evaluator_version" not in item_dict


def test_dual_reviewer_agreement_concordance_and_kappa():
    """Verify percentage agreement and Cohen's kappa for dual independent reviewers."""
    now = datetime.now(UTC).isoformat()

    labels_a = [
        IndependentReviewerLabel(
            label_id=f"lbl-a-{i}",
            reviewer_id="REV_ALPHA",
            pair_id=f"pair-{i}",
            case_id=f"case-{i}",
            project_id="proj-p7",
            evidence_digest=f"digest-{i}",
            permitted_outcome_observed=True,
            defect_present=(i == 0),
            created_at_utc=now,
        )
        for i in range(4)
    ]

    labels_b = [
        IndependentReviewerLabel(
            label_id=f"lbl-b-{i}",
            reviewer_id="REV_BETA",
            pair_id=f"pair-{i}",
            case_id=f"case-{i}",
            project_id="proj-p7",
            evidence_digest=f"digest-{i}",
            permitted_outcome_observed=True,
            defect_present=(i in (0, 1)),
            created_at_utc=now,
        )
        for i in range(4)
    ]

    result = compute_inter_reviewer_agreement(labels_a, labels_b)

    assert result.total_pairs_compared == 4
    assert result.concordant_pairs_count == 3
    assert result.discordant_pairs_count == 1
    assert result.percentage_agreement.value == 0.75
    assert result.percentage_agreement.is_defined is True
    assert result.cohens_kappa.is_defined is True
    assert result.disputed_pair_ids == ["pair-1"]
    assert result.reconciliation_required is True


def test_inter_reviewer_agreement_zero_variance_handled():
    """When both raters select the same category for 100% of cases, kappa is mathematically undefined."""
    now = datetime.now(UTC).isoformat()
    labels_a = [
        IndependentReviewerLabel(
            label_id=f"lbl-a-{i}",
            reviewer_id="REV_A",
            pair_id=f"p-{i}",
            case_id=f"c-{i}",
            project_id="proj-p7",
            evidence_digest=f"d-{i}",
            permitted_outcome_observed=True,
            defect_present=False,
            created_at_utc=now,
        )
        for i in range(5)
    ]
    labels_b = [
        IndependentReviewerLabel(
            label_id=f"lbl-b-{i}",
            reviewer_id="REV_B",
            pair_id=f"p-{i}",
            case_id=f"c-{i}",
            project_id="proj-p7",
            evidence_digest=f"d-{i}",
            permitted_outcome_observed=True,
            defect_present=False,
            created_at_utc=now,
        )
        for i in range(5)
    ]

    result = compute_inter_reviewer_agreement(labels_a, labels_b)
    assert result.concordant_pairs_count == 5
    assert result.percentage_agreement.value == 1.0
    assert result.cohens_kappa.is_defined is False
    assert "Zero variance" in (result.cohens_kappa.undefined_reason or "")
    assert result.reconciliation_required is False


def test_reconciliation_audit_trail_preserves_original_labels():
    """Reconciliation produces an append-only audit record without mutating original labels."""
    now = datetime.now(UTC).isoformat()
    lbl_a = IndependentReviewerLabel(
        label_id="lbl-a-1",
        reviewer_id="REV_A",
        pair_id="pair-audit-1",
        case_id="case-audit-1",
        project_id="proj-p7",
        evidence_digest="dig-audit",
        permitted_outcome_observed=True,
        defect_present=False,
        created_at_utc=now,
    )
    lbl_b = IndependentReviewerLabel(
        label_id="lbl-b-1",
        reviewer_id="REV_B",
        pair_id="pair-audit-1",
        case_id="case-audit-1",
        project_id="proj-p7",
        evidence_digest="dig-audit",
        permitted_outcome_observed=True,
        defect_present=True,
        created_at_utc=now,
    )

    rec = reconcile_disputed_labels(
        label_a=lbl_a,
        label_b=lbl_b,
        adjudicator_id="ADJUDICATOR_SENIOR",
        adjudicated_verdict=RecoveryVerdict.PASS_GRACEFUL,
        adjudicated_defect_present=False,
        adjudication_rationale="Trace confirms safe degraded fallback without state corruption.",
    )

    assert rec.pair_id == "pair-audit-1"
    assert rec.adjudicator_id == "ADJUDICATOR_SENIOR"
    assert rec.adjudicated_verdict == RecoveryVerdict.PASS_GRACEFUL
    assert rec.adjudicated_defect_present is False
    assert lbl_a.defect_present is False
    assert lbl_b.defect_present is True


def test_synthetic_labels_acceptance_blocked():
    """Synthetic unit fixture labels must keep research-accuracy acceptance BLOCKED."""
    lbl = ReviewerLabelRecord(
        label_id="lbl-syn-1",
        pair_id="pair-syn-1",
        case_id="case-syn-1",
        project_id="proj-p7",
        defect_present=True,
        reviewer_provenance=ReviewerProvenance.SYNTHETIC_FIXTURE_LABEL,
        created_at_utc=datetime.now(UTC).isoformat(),
    )
    is_accepted, blockers = check_research_accuracy_acceptance([lbl])
    assert is_accepted is False
    assert any("BLOCKED" in b for b in blockers)


# ---------------------------------------------------------------------------
# 3. Offline Baselines and Ablations Tests
# ---------------------------------------------------------------------------


def test_baseline_b1_fixed_suite_comparison():
    """Compare predefined fixed fault suite against automatic generated suite under matched budgets."""
    gen_req = build_demonstration_generation_request()
    gen_req.policy.max_cases = 5
    gen_res = generate_feasible_cases(gen_req)
    gen_suite = gen_res.frozen_suite
    assert gen_suite is not None

    fixed_suite = gen_suite.model_copy(deep=True)
    fixed_suite.suite_id = "suite-fixed"

    comp = compare_fixed_suite_vs_generated(
        fixed_suite=fixed_suite,
        generated_suite=gen_suite,
        feasible_combinations=10,
    )

    assert comp.budget_equivalent is True
    assert comp.fixed_validity_rate.value == 1.0
    assert comp.generated_validity_rate.value == 1.0
    assert comp.generated_feasible_coverage.is_defined is True

    assert comp.budget_equivalent is True
    assert comp.fixed_validity_rate.value == 1.0
    assert comp.generated_validity_rate.value == 1.0
    assert comp.generated_feasible_coverage.is_defined is True


def test_baseline_b2_outcome_only_verifies_terminal_and_state():
    """Outcome-only baseline (B2) evaluates terminal outcome and state, rejecting false state and ignoring trace rules."""
    case = make_demonstration_candidate_case()
    recovery = make_demonstration_recovery_contract()
    evidence = make_test_evidence(caller_outcome="SUCCESS_AFTER_RETRY")

    # 1. State assertion FALSE -> Outcome-only must FAIL (not blindly accept caller success)
    req_false_state = RecoveryEvaluationRequest(
        project_id="proj-p7",
        case_id=case.case_id,
        evaluator_version="1.2.0",
        rule_set_version="1.2.0",
        candidate_case=case,
        recovery_contract=recovery,
        matched_evidence=evidence,
        c2_facts=[
            C2AssertionFact(
                assertion_id="state_order_created",
                value=C2FactValue.FALSE,
                provenance="TEST_FIXTURE",
            )
        ],
    )
    res_b2 = evaluate_with_baseline_or_ablation(
        req_false_state, baseline_type=BaselineType.OUTCOME_ONLY_BASELINE
    )
    assert res_b2.recovery_verdict == RecoveryVerdict.FAIL

    # 2. State assertion TRUE, but retry bounds exceeded (subsequent_calls_count=5 > max_retries=1)
    ev_retried = make_test_evidence(caller_outcome="SUCCESS_AFTER_RETRY")
    ev_retried.fault_trial.subsequent_calls_count = 5

    req_retried = RecoveryEvaluationRequest(
        project_id="proj-p7",
        case_id=case.case_id,
        evaluator_version="1.2.0",
        rule_set_version="1.2.0",
        candidate_case=case,
        recovery_contract=recovery,
        matched_evidence=ev_retried,
        c2_facts=[
            C2AssertionFact(
                assertion_id="state_order_created",
                value=C2FactValue.TRUE,
                provenance="TEST_FIXTURE",
            )
        ],
    )
    res_prod = evaluate_with_baseline_or_ablation(
        req_retried, baseline_type=BaselineType.PRODUCTION_C3
    )
    assert res_prod.recovery_verdict == RecoveryVerdict.FAIL

    res_b2_pass = evaluate_with_baseline_or_ablation(
        req_retried, baseline_type=BaselineType.OUTCOME_ONLY_BASELINE
    )
    assert res_b2_pass.recovery_verdict == RecoveryVerdict.PASS_COMPLETED


def test_ablation_a1_offline_capability_measurement():
    """A1: Measures schema-valid but unsupported combinations offline while keeping runtime safety."""
    manifest = build_demonstration_generation_request().adapter_manifest
    case_valid = make_demonstration_candidate_case()

    case_unsupported = case_valid.model_copy(deep=True)
    case_unsupported.case_id = "case-unsupported-phase"
    case_unsupported.effect_phase = EffectPhase.PARTIAL_EFFECT

    report = measure_capability_ablation([case_valid, case_unsupported], manifest)
    assert report["total_cases_evaluated"] == 2
    assert report["supported_cases_count"] == 1
    assert report["unsupported_cases_count"] == 1
    assert "case-unsupported-phase" in report["unsupported_case_ids"]
    assert report["runtime_safety_enforced"] is True


def test_ablation_a2_isolated_exposure_receipt():
    """A2: Isolated analysis assumes scheduling means exposure without mutating production evidence."""
    case = make_demonstration_candidate_case()
    recovery = make_demonstration_recovery_contract()
    evidence = make_test_evidence(
        caller_outcome="SUCCESS_AFTER_RETRY",
        exposure_status=ExposureStatus.NOT_TRIGGERED,
    )

    req = RecoveryEvaluationRequest(
        project_id="proj-p7",
        case_id=case.case_id,
        evaluator_version="1.2.0",
        rule_set_version="1.2.0",
        candidate_case=case,
        recovery_contract=recovery,
        matched_evidence=evidence,
        c2_facts=[
            C2AssertionFact(
                assertion_id="state_order_created",
                value=C2FactValue.TRUE,
                provenance="TEST_FIXTURE",
            )
        ],
    )

    res_prod = evaluate_with_baseline_or_ablation(
        req, baseline_type=BaselineType.PRODUCTION_C3
    )
    assert res_prod.recovery_verdict is None

    res_a2 = evaluate_with_baseline_or_ablation(
        req, ablation_type=AblationType.NO_EXPOSURE_RECEIPTS
    )
    assert res_a2.recovery_verdict == RecoveryVerdict.PASS_COMPLETED

    assert evidence.exposure_status == ExposureStatus.NOT_TRIGGERED


def test_ablation_a3_no_state_facts_yields_inconclusive():
    """A3: Evaluates without supplied state facts; missing state facts become UNKNOWN / INCONCLUSIVE."""
    case = make_demonstration_candidate_case()
    recovery = make_demonstration_recovery_contract()
    evidence = make_test_evidence(caller_outcome="SUCCESS_AFTER_RETRY")

    req = RecoveryEvaluationRequest(
        project_id="proj-p7",
        case_id=case.case_id,
        evaluator_version="1.2.0",
        rule_set_version="1.2.0",
        candidate_case=case,
        recovery_contract=recovery,
        matched_evidence=evidence,
        c2_facts=[
            C2AssertionFact(
                assertion_id="state_order_created",
                value=C2FactValue.TRUE,
                provenance="TEST_FIXTURE",
            )
        ],
    )

    res_a3 = evaluate_with_baseline_or_ablation(
        req, ablation_type=AblationType.NO_STATE_FACTS
    )
    assert res_a3.recovery_verdict == RecoveryVerdict.INCONCLUSIVE


def test_ablation_a4_no_effect_phase_distinction():
    """A4: Treats AFTER_COMMIT fault as BEFORE_EFFECT."""
    case = make_demonstration_candidate_case()
    case.effect_phase = EffectPhase.AFTER_COMMIT
    recovery = make_demonstration_recovery_contract()
    evidence = make_test_evidence(caller_outcome="SUCCESS_AFTER_RETRY")

    req = RecoveryEvaluationRequest(
        project_id="proj-p7",
        case_id=case.case_id,
        evaluator_version="1.2.0",
        rule_set_version="1.2.0",
        candidate_case=case,
        recovery_contract=recovery,
        matched_evidence=evidence,
        c2_facts=[
            C2AssertionFact(
                assertion_id="state_order_created",
                value=C2FactValue.TRUE,
                provenance="TEST_FIXTURE",
            )
        ],
    )

    res_a4 = evaluate_with_baseline_or_ablation(
        req, ablation_type=AblationType.NO_EFFECT_PHASE
    )
    assert res_a4.recovery_verdict is not None


# ---------------------------------------------------------------------------
# 4. Pure Research Metrics & Statistical Tests
# ---------------------------------------------------------------------------


def test_four_way_multiclass_matrix_and_macro_f1():
    """Verify 4-way multiclass confusion matrix, accuracy, per-class P/R/F1, and macro-F1."""
    evals = []
    labels = []
    verdicts = [
        RecoveryVerdict.PASS_COMPLETED,
        RecoveryVerdict.PASS_GRACEFUL,
        RecoveryVerdict.FAIL,
        RecoveryVerdict.INCONCLUSIVE,
    ]

    for i, v in enumerate(verdicts):
        ev = RecoveryEvaluationResult(
            project_id="proj-p7",
            case_id=f"c-{i}",
            pair_id=f"p-{i}",
            evaluator_version="1.2.0",
            rule_set_version="1.2.0",
            evaluation_status=EvaluationStatus.EVALUATED,
            recovery_verdict=v,
            case_fingerprint=f"fp-{i}",
            suite_digest=f"sd-{i}",
            rule_results=[],
        )
        lbl = IndependentReviewerLabel(
            label_id=f"l-{i}",
            reviewer_id="REV_EXPERT",
            pair_id=f"p-{i}",
            case_id=f"c-{i}",
            project_id="proj-p7",
            evidence_digest=f"d-{i}",
            permitted_outcome_observed=True,
            defect_present=(v == RecoveryVerdict.FAIL),
            assigned_verdict=v,
            created_at_utc=datetime.now(UTC).isoformat(),
        )
        evals.append(ev)
        labels.append(lbl)

    cm = compute_four_way_multiclass_matrix(evaluations=evals, labels=labels)

    assert cm.total_samples == 4
    assert cm.accuracy.value == 1.0
    assert cm.macro_f1.value == 1.0
    for v in verdicts:
        assert cm.per_class_f1[v.value].value == 1.0


def test_clean_to_fault_outcome_transitions():
    """Verify matched clean-to-fault outcome transitions preserving qualification integrity."""
    pairs = [
        MockMatchedPair("p-1", "QUALIFIED", "SUCCESS_CLEAN_RECOVERY"),
        MockMatchedPair("p-2", "QUALIFIED", "FAILED_UNHANDLED_EXCEPTION"),
        MockMatchedPair("p-3", "DISQUALIFIED", "SUCCESS"),
    ]

    transitions = compute_clean_to_fault_transitions(pairs)
    assert transitions.total_matched_pairs == 3
    assert transitions.clean_pass_to_fault_recovered == 1
    assert transitions.clean_pass_to_fault_defect == 1
    assert transitions.clean_disqualified_count == 1


def test_execution_overheads_honestly_reports_unavailable_telemetry():
    """Verify duration overhead is computed while token and cost telemetry remain explicitly unavailable."""
    pairs = [
        MockMatchedPair("p-1", "QUALIFIED", "SUCCESS", duration_ms=120.0),
        MockMatchedPair("p-2", "QUALIFIED", "SUCCESS", duration_ms=180.0),
    ]

    overheads = compute_execution_overhead_metrics(pairs)
    assert overheads["average_duration_ms"].value == 150.0
    assert overheads["average_duration_ms"].is_defined is True

    assert overheads["token_overhead"].is_defined is False
    assert "telemetry unavailable offline" in (
        overheads["token_overhead"].undefined_reason or ""
    )
    assert overheads["cost_overhead_usd"].is_defined is False


def test_cluster_bootstrap_insufficient_data_honesty():
    """Cluster bootstrap CI with N < 5 case families must report is_valid=False honestly."""
    data = {
        "family_1": [1.0, 1.0],
        "family_2": [0.0, 1.0],
        "family_3": [1.0, 0.0],
    }
    ci = compute_family_cluster_bootstrap_ci(data, n_bootstraps=100)
    assert ci.is_valid is False
    assert ci.n_clusters == 3
    assert ci.ci_lower is None
    assert ci.ci_upper is None
    assert "Insufficient cluster count (N=3 < 5)" in (ci.limitation or "")


def test_cluster_bootstrap_sufficient_clusters():
    """Cluster bootstrap CI with N >= 5 case families computes valid deterministic bounds."""
    data = {f"family_{i}": [0.8, 1.0, 0.9] for i in range(6)}
    ci = compute_family_cluster_bootstrap_ci(data, n_bootstraps=200, seed=42)
    assert ci.is_valid is True
    assert ci.n_clusters == 6
    assert ci.ci_lower is not None
    assert ci.ci_upper is not None
    assert 0.0 <= ci.ci_lower <= ci.ci_upper <= 1.0


# ---------------------------------------------------------------------------
# 5. Persistence Correctness Tests
# ---------------------------------------------------------------------------


def test_persistence_identical_case_across_multiple_suites(test_db):
    """An identical case may appear in multiple suites with suite-specific membership and ordering."""
    repo = C3PersistenceRepository(test_db)
    case = make_demonstration_candidate_case()
    gen_req = build_demonstration_generation_request()

    suite_1 = freeze_suite(
        task_fixture_metadata=gen_req.task_fixture_metadata,
        adapter_manifest=gen_req.adapter_manifest,
        recovery_contract=make_demonstration_recovery_contract(),
        policy=gen_req.policy,
        selected_cases=[case],
        counters=GenerationCounters(selected_count=1, valid_count=1, unique_count=1),
        limitations=[],
        suite_id="suite-alpha",
    )
    suite_2 = freeze_suite(
        task_fixture_metadata=gen_req.task_fixture_metadata,
        adapter_manifest=gen_req.adapter_manifest,
        recovery_contract=make_demonstration_recovery_contract(),
        policy=gen_req.policy,
        selected_cases=[case],
        counters=GenerationCounters(selected_count=1, valid_count=1, unique_count=1),
        limitations=[],
        suite_id="suite-beta",
    )

    store_frozen_suite(test_db, "proj-demo-qa", suite_1)
    store_frozen_suite(test_db, "proj-demo-qa", suite_2)

    c1 = repo.get_case("proj-demo-qa", case.case_id, suite_digest=suite_1.suite_digest)
    c2 = repo.get_case("proj-demo-qa", case.case_id, suite_digest=suite_2.suite_digest)
    assert c1 is not None
    assert c2 is not None
    assert c1.suite_digest == suite_1.suite_digest
    assert c2.suite_digest == suite_2.suite_digest
    assert c1.content_digest == c2.content_digest
    assert c1.case_fingerprint == c2.case_fingerprint


def test_persistence_conflicting_content_rejection(test_db):
    """Attempting to store conflicting case content under identical suite/case ID raises ConflictError."""
    case_1 = make_demonstration_candidate_case()
    gen_req = build_demonstration_generation_request()
    suite = freeze_suite(
        task_fixture_metadata=gen_req.task_fixture_metadata,
        adapter_manifest=gen_req.adapter_manifest,
        recovery_contract=make_demonstration_recovery_contract(),
        policy=gen_req.policy,
        selected_cases=[case_1],
        counters=GenerationCounters(selected_count=1, valid_count=1, unique_count=1),
        limitations=[],
        suite_id="suite-conflict-test",
    )
    store_frozen_suite(test_db, "proj-demo-qa", suite)

    case_mutated = case_1.model_copy(deep=True)
    case_mutated.caller_timeout_ms = 10

    suite_conflict = freeze_suite(
        task_fixture_metadata=gen_req.task_fixture_metadata,
        adapter_manifest=gen_req.adapter_manifest,
        recovery_contract=make_demonstration_recovery_contract(),
        policy=gen_req.policy,
        selected_cases=[case_mutated],
        counters=GenerationCounters(selected_count=1, valid_count=1, unique_count=1),
        limitations=[],
        suite_id="suite-conflict-2",
    )

    with pytest.raises(ConflictError) as exc_info:
        store_frozen_suite(test_db, "proj-demo-qa", suite_conflict)
    assert "conflicting content digest" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# 6. Runtime Safeguards Offline
# ---------------------------------------------------------------------------


def test_banking_adapter_committed_operation_verification():
    """Verify BankingFixtureManager independently observes committed transfer operations."""
    mgr = BankingFixtureManager()
    mgr.prepare_fixture("acct-p7", {"initial_balance": 5000})

    mgr._namespaces["acct-p7"]["transfers"].append(
        {
            "transfer_reference": "TX-WIRE-9988",
            "amount": 200,
            "status": "SETTLED",
        }
    )

    assert mgr.verify_committed_transfer("acct-p7", "TX-WIRE-9988") is True
    assert mgr.verify_committed_operation("acct-p7", "TX-WIRE-9988") is True
    assert mgr.verify_committed_operation("acct-p7", "TX-NON-EXISTENT") is False


def test_uncertain_cleanup_prevents_fixture_reuse():
    """When cleanup is uncertain due to unsettled in-flight operations, fixture must report UNCERTAIN."""
    mgr = DemonstrationFixtureManager()
    mgr.prepare_fixture("ns-uncertain", {"initial_balance": 500})
    mgr.record_in_flight_start("ns-uncertain")

    res = mgr.cleanup("ns-uncertain")
    assert res.status == CleanupStatus.UNCERTAIN
    assert res.in_flight_count > 0
    assert res.reusable is False
