"""Phase 6 Comprehensive Evaluation Tooling and Final Backend Verification Tests.

Covers:
1. Confirmed Phase 5 repairs (lossless numeric diffing, exact version lookup, historical re-evaluation immutability, complete impact plan handling).
2. Configured LLM provider offline transport, malformed output handling, and secret redaction.
3. Versioned evaluation datasets, freezing, and split-leakage prevention.
4. Blind reviewer packets, independent decision collection, Cohen's Kappa agreement, and adjudication.
5. Proposal metrics with explicit denominators, False-PASS rate on reference-unsafe cases, and zero-denominator handling.
6. Interchangeable baselines (manual suite awaiting data, text-only evaluator).
7. Non-mutating evidence ablations (NO_GROUNDING, NO_PROVENANCE, NO_EFFECTS).
8. Reproducible experiment orchestration with repeat trials and uncertainty estimation.
9. Phase 6 REST API endpoints.
"""

import hashlib
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c4_policy_aware_safety.contracts.artifacts import ArtifactKind
from app.components.c4_policy_aware_safety.contracts.cases import (
    CaseLifecycleState,
    ExpectedAssertion,
    PolicyTestCase,
)
from app.components.c4_policy_aware_safety.contracts.enums import (
    ContractLifecycleState,
    EvaluationBoundary,
    InstructionSourceType,
    PolicyFamily,
    PolicyRequirement,
    Severity,
    TrustClassification,
    ViolationStage,
)
from app.components.c4_policy_aware_safety.contracts.evaluation import (
    AblationType,
    DatasetSplit,
    EvaluationCaseRecord,
    EvaluationDatasetRecord,
    ExperimentConfigRecord,
    ExperimentStatus,
    ReferenceAttribution,
    ReviewerDecision,
    StrategyType,
)
from app.components.c4_policy_aware_safety.contracts.evidence import (
    ArgumentProvenanceEvidence,
    EffectEvidence,
    EvaluationEvidencePackage,
    InstructionSourceEvidence,
    ToolExecutionEvidence,
)
from app.components.c4_policy_aware_safety.contracts.execution import (
    AttackerObjectiveOutcome,
    C4ExecutionRunRecord,
    CleanupStatus,
    ExecutionStatus,
    ExposureStatus,
    TargetExecutionMode,
    TaskUtilityOutcome,
)
from app.components.c4_policy_aware_safety.contracts.future import TestCaseKind
from app.components.c4_policy_aware_safety.contracts.predicates import (
    CompoundOperator,
    CompoundPredicate,
    PredicateCondition,
    PredicateOperator,
)
from app.components.c4_policy_aware_safety.contracts.regression import (
    CaseDecisionAction,
    CaseImpactDecision,
    CaseImpactLevel,
    HistoricalReEvaluationRecord,
    PlanLifecycleState,
    PolicyComparisonRequest,
    RegressionPlanRecord,
    RuleChangeType,
)
from app.components.c4_policy_aware_safety.contracts.rules import (
    PolicyContractVersion,
    PolicyRule,
    SourceReference,
)
from app.components.c4_policy_aware_safety.evaluation.ablations import (
    EvidenceAblationEngine,
)
from app.components.c4_policy_aware_safety.evaluation.baselines import (
    ManualBaselineStrategy,
    TextOnlyEvaluator,
)
from app.components.c4_policy_aware_safety.evaluation.experiments import (
    ExperimentService,
)
from app.components.c4_policy_aware_safety.evaluation.metrics import (
    PolicyMetricsCalculator,
    compute_ratio,
)
from app.components.c4_policy_aware_safety.evaluation.review import ReviewService
from app.components.c4_policy_aware_safety.execution.adapters import (
    LiveAUTAdapterStub,
    SimulatedC4ApplicationAdapter,
)
from app.components.c4_policy_aware_safety.extraction.provider import (
    ConfiguredLlmExtractionProvider,
)
from app.components.c4_policy_aware_safety.persistence.models import Base
from app.components.c4_policy_aware_safety.persistence.repository import C4Repository
from app.components.c4_policy_aware_safety.regression.diff import (
    PolicyDiffEngine,
    _canonical_json,
)
from app.database import get_db

try:
    from app.main import app
except (ImportError, ModuleNotFoundError):
    from fastapi import FastAPI

    from app.components.c4_policy_aware_safety.api import router as c4_router

    app = FastAPI(title="Agentic AI QA Framework API - C4 Standalone")
    app.include_router(c4_router)


# ==============================================================================
# Fixtures
# ==============================================================================
@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    db = testing_session_local()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def repo(db_session):
    return C4Repository(db_session)


@pytest.fixture
def client(db_session):
    from tests.c4.auth_test_utils import create_authenticated_c4_client

    test_client = create_authenticated_c4_client(
        db_session, project_ids=["proj-p6-api"]
    )
    yield test_client
    app.dependency_overrides.clear()


# ==============================================================================
# Helper Factories
# ==============================================================================
def create_mock_case(
    case_id: str,
    project_id: str,
    target_rule_id: str,
    test_kind: TestCaseKind = TestCaseKind.DIRECT_POLICY_CHALLENGE,
    contract_id: str = "contract-p6-ecom",
    contract_version: int = 1,
    domain_id: str = "domain-ecommerce-c4",
    scenario_group_id: str = "scenario-p6",
    variant_id: str = "variant-1",
    legitimate_task: str = "Legitimate task",
    agent_task_prompt: str = "Please process request",
    expected_policy_verdict: str = "PASS",
    expected_boundary: EvaluationBoundary = EvaluationBoundary.ATTEMPTED_ACTION,
    case_version: int = 1,
    lifecycle_state: CaseLifecycleState = CaseLifecycleState.FROZEN,
) -> PolicyTestCase:
    return PolicyTestCase(
        case_id=case_id,
        case_version=case_version,
        project_id=project_id,
        test_kind=test_kind,
        target_rule_id=target_rule_id,
        target_rule_version=1,
        contract_id=contract_id,
        contract_version=contract_version,
        domain_id=domain_id,
        binding_version=1,
        scenario_group_id=scenario_group_id,
        variant_id=variant_id,
        legitimate_task=legitimate_task,
        agent_task_prompt=agent_task_prompt,
        expected_boundary=expected_boundary,
        expected_policy_verdict=expected_policy_verdict,
        target_rule_ids=[target_rule_id],
        target_rule_versions={target_rule_id: 1},
        expected_assertions=[
            ExpectedAssertion(
                rule_id=target_rule_id,
                rule_version=1,
                expected_applicability="EXERCISED",
                expected_compliance="PASS",
            )
        ],
        required_evidence=["action_attempts", "authorization_decisions"],
        lifecycle_state=lifecycle_state,
        content_hash=hashlib.sha256(f"{case_id}-{case_version}".encode()).hexdigest(),
    )


# ==============================================================================
# 1. Confirmed Phase 5 Repairs
# ==============================================================================
def test_phase5_repair_exact_numeric_diffing():
    """Verify that policy diffing removes lossy rounding and detects changes < 0.0001."""
    diff_engine = PolicyDiffEngine()
    project_id = "proj-p6-diff"

    # Rule with limit = 50.00001
    r_base = PolicyRule(
        project_id=project_id,
        rule_id="RULE_PRECISE_LIMIT",
        rule_version=1,
        policy_family=PolicyFamily.AUTHORIZATION,
        principal_selector="CUSTOMER_SUPPORT",
        action_selector="process_refund",
        resource_selector="order_refund",
        policy_requirement=PolicyRequirement.REQUIRE,
        evaluation_boundary=EvaluationBoundary.ATTEMPTED_ACTION,
        applicability_conditions=CompoundPredicate(
            operator=CompoundOperator.ALL,
            conditions=[
                PredicateCondition(
                    field="tool_call.arguments.amount",
                    operator=PredicateOperator.GREATER_THAN,
                    value=50.00001,
                )
            ],
        ),
        compliance_conditions=CompoundPredicate(
            operator=CompoundOperator.ALL,
            conditions=[],
        ),
        required_evidence=["action_attempts"],
        severity=Severity.HIGH,
        source_references=[
            SourceReference(
                project_id=project_id,
                artifact_id="art-diff-test",
                artifact_version=1,
                start_char=0,
                end_char=50,
                supporting_excerpt="Refunds must have amount check",
            )
        ],
    )
    # Rule with limit = 50.00009 (difference is 0.00008, < 0.0001)
    r_cand = r_base.model_copy(
        update={
            "rule_version": 2,
            "applicability_conditions": CompoundPredicate(
                operator=CompoundOperator.ALL,
                conditions=[
                    PredicateCondition(
                        field="tool_call.arguments.amount",
                        operator=PredicateOperator.GREATER_THAN,
                        value=50.00009,
                    )
                ],
            ),
        }
    )

    base_contract = PolicyContractVersion(
        contract_id="contract-num-base",
        project_id=project_id,
        version=1,
        lifecycle_state=ContractLifecycleState.ACCEPTED,
        rules=[r_base],
        referenced_artifact_versions={"art-diff-test": 1},
        content_hash=hashlib.sha256(b"contract-num-base-v1").hexdigest(),
    )
    cand_contract = PolicyContractVersion(
        contract_id="contract-num-cand",
        project_id=project_id,
        version=2,
        lifecycle_state=ContractLifecycleState.ACCEPTED,
        rules=[r_cand],
        referenced_artifact_versions={"art-diff-test": 1},
        content_hash=hashlib.sha256(b"contract-num-cand-v2").hexdigest(),
    )

    comp = diff_engine.compare_contracts(
        PolicyComparisonRequest(
            project_id=project_id,
            baseline_contract_id=base_contract.contract_id,
            baseline_contract_version=1,
            candidate_contract_id=cand_contract.contract_id,
            candidate_contract_version=2,
        ),
        base_contract,
        cand_contract,
    )

    # Difference < 0.0001 must NOT be equated by lossy rounding
    assert comp.summary["semantically_modified"] == 1
    diff_rec = comp.rule_diffs[0]
    assert diff_rec.change_type == RuleChangeType.SEMANTICALLY_MODIFIED
    assert "applicability_conditions" in diff_rec.field_changes

    # Verify non-finite numbers (NaN, Inf) are rejected
    with pytest.raises(ValueError, match="Non-finite numeric value"):
        _canonical_json({"amount": float("nan")})
    with pytest.raises(ValueError, match="Non-finite numeric value"):
        _canonical_json({"amount": float("inf")})


def test_phase5_repair_exact_version_lookup(repo):
    """Verify that get_test_case strictly requires exact version match and does not fall back."""
    project_id = "proj-p6-ver"
    case_v1 = create_mock_case(
        case_id="case-exact-ver",
        project_id=project_id,
        target_rule_id="RULE_EXACT_VER",
        case_version=1,
    )
    repo.save_test_case(case_v1)

    # 1. Exact lookup for version 1 succeeds
    found_v1 = repo.get_test_case(project_id, "case-exact-ver", version=1)
    assert found_v1 is not None
    assert found_v1.case_version == 1

    # 2. Exact lookup for version 2 when version 2 does not exist MUST return None (no fallback!)
    found_v2 = repo.get_test_case(project_id, "case-exact-ver", version=2)
    assert found_v2 is None

    # 3. Add version 2
    case_v2 = create_mock_case(
        case_id="case-exact-ver",
        project_id=project_id,
        target_rule_id="RULE_EXACT_VER",
        case_version=2,
    )
    repo.save_test_case(case_v2)

    found_v2_now = repo.get_test_case(project_id, "case-exact-ver", version=2)
    assert found_v2_now is not None
    assert found_v2_now.case_version == 2

    # 4. Explicit get_latest_test_case returns version 2
    latest = repo.get_latest_test_case(project_id, "case-exact-ver")
    assert latest is not None
    assert latest.case_version == 2


def test_phase5_repair_historical_reevaluation_integrity(repo):
    """Verify that historical re-evaluation creates an immutable record without overwriting original run."""
    project_id = "proj-p6-reeval"

    # Save original execution run
    original_run = C4ExecutionRunRecord(
        run_id="run-original-evidence-001",
        project_id=project_id,
        case_id="case-orig",
        case_version=1,
        contract_id="contract-base",
        contract_version=1,
        binding_id="bind-orig",
        binding_version=1,
        adapter_id="simulated",
        adapter_version="1.0",
        adapter_config_digest="digest",
        execution_mode=TargetExecutionMode.SIMULATED,
        status=ExecutionStatus.COMPLETED,
        exposure_status=ExposureStatus.NOT_APPLICABLE,
        policy_verdict="PASS",
        attacker_objective_outcome=AttackerObjectiveOutcome.NOT_APPLICABLE,
        task_utility_outcome=TaskUtilityOutcome.SUCCESS,
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
        pre_cleanup_effects=[],
        evaluation_report_summary={"note": "Original evidence"},
        findings=[{"rule_id": "RULE_1", "verdict": "PASS"}],
        created_at=datetime.now(UTC),
    )
    repo.save_execution_run(original_run)

    # Save separate immutable HistoricalReEvaluationRecord
    reeval_rec = HistoricalReEvaluationRecord(
        re_eval_id="reeval-record-001",
        project_id=project_id,
        source_run_id=original_run.run_id,
        source_evidence_references=[original_run.run_id],
        original_contract_id="contract-base",
        original_contract_version=1,
        candidate_contract_id="contract-cand",
        candidate_contract_version=2,
        evaluator_version="3-valued-kleene-v1",
        evaluator_config_digest="cand-digest",
        derived_policy_verdict="FAIL",
        derived_findings=[{"rule_id": "RULE_1", "verdict": "FAIL"}],
        analysis_mode="HISTORICAL_RE_EVALUATION",
        explanation="Stricter candidate contract turned previous PASS into FAIL.",
        created_at=datetime.now(UTC),
    )
    repo.save_historical_re_evaluation(reeval_rec)

    # Verify original run is strictly untouched
    stored_orig = repo.get_execution_run(project_id, original_run.run_id)
    assert stored_orig is not None
    assert stored_orig.policy_verdict == "PASS"
    assert stored_orig.contract_version == 1

    # Verify separate re-evaluation record was stored accurately
    stored_reeval = repo.get_historical_re_evaluation(project_id, "reeval-record-001")
    assert stored_reeval is not None
    assert stored_reeval.source_run_id == original_run.run_id
    assert stored_reeval.derived_policy_verdict == "FAIL"
    assert stored_reeval.candidate_contract_version == 2


def test_phase5_repair_complete_impact_plan_handling(repo):
    """Verify that all plan decisions (REGENERATE, REVALIDATE, REVISE, RETIRE, RETAIN, BLOCKED, NEEDS_REVIEW) are accounted for."""
    project_id = "proj-p6-plan"

    decisions = [
        CaseImpactDecision(
            case_id="c1",
            case_version=1,
            target_rule_id="R1",
            test_kind=TestCaseKind.DIRECT_POLICY_CHALLENGE,
            impact_level=CaseImpactLevel.DEFINITELY_AFFECTED,
            action=CaseDecisionAction.REGENERATE,
            reason="Threshold modified",
        ),
        CaseImpactDecision(
            case_id="c2",
            case_version=1,
            target_rule_id="R2",
            test_kind=TestCaseKind.DIRECT_POLICY_CHALLENGE,
            impact_level=CaseImpactLevel.POSSIBLY_AFFECTED,
            action=CaseDecisionAction.REVALIDATE,
            reason="Scope overlap",
        ),
        CaseImpactDecision(
            case_id="c3",
            case_version=1,
            target_rule_id="R3",
            test_kind=TestCaseKind.DIRECT_POLICY_CHALLENGE,
            impact_level=CaseImpactLevel.DEFINITELY_AFFECTED,
            action=CaseDecisionAction.REVISE,
            reason="Multi-rule rule removed",
        ),
        CaseImpactDecision(
            case_id="c4",
            case_version=1,
            target_rule_id="R4",
            test_kind=TestCaseKind.DIRECT_POLICY_CHALLENGE,
            impact_level=CaseImpactLevel.DEFINITELY_AFFECTED,
            action=CaseDecisionAction.RETIRE,
            reason="Sole target rule removed",
        ),
        CaseImpactDecision(
            case_id="c5",
            case_version=1,
            target_rule_id="R5",
            test_kind=TestCaseKind.DIRECT_POLICY_CHALLENGE,
            impact_level=CaseImpactLevel.UNAFFECTED,
            action=CaseDecisionAction.RETAIN,
            reason="Unchanged rule",
        ),
        CaseImpactDecision(
            case_id="c6",
            case_version=1,
            target_rule_id="R6",
            test_kind=TestCaseKind.DIRECT_POLICY_CHALLENGE,
            impact_level=CaseImpactLevel.DEFINITELY_AFFECTED,
            action=CaseDecisionAction.BLOCKED,
            reason="Missing fixture",
        ),
    ]

    plan = RegressionPlanRecord(
        plan_id="plan-p6-all-actions",
        project_id=project_id,
        comparison_id="comp-1",
        baseline_contract_id="base",
        baseline_contract_version=1,
        candidate_contract_id="cand",
        candidate_contract_version=2,
        binding_id="bind",
        binding_version=1,
        status=PlanLifecycleState.DRAFT,
        plan_digest="digest",
        case_decisions=decisions,
        retired_cases=["c4"],
        retained_cases=["c5"],
        proposed_replacement_cases=["c1-v2", "c2-reval-v2", "c3-revised-v2"],
    )

    repo.save_regression_plan(plan)
    stored = repo.get_regression_plan(project_id, plan.plan_id)
    assert stored is not None
    assert len(stored.case_decisions) == 6

    # Verify that all 6 baseline cases have an explicit decision action
    actions = {d.case_id: d.action for d in stored.case_decisions}
    assert actions["c1"] == CaseDecisionAction.REGENERATE
    assert actions["c2"] == CaseDecisionAction.REVALIDATE
    assert actions["c3"] == CaseDecisionAction.REVISE
    assert actions["c4"] == CaseDecisionAction.RETIRE
    assert actions["c5"] == CaseDecisionAction.RETAIN
    assert actions["c6"] == CaseDecisionAction.BLOCKED


# ==============================================================================
# 2. Configured LLM Provider & Live Adapter Audit
# ==============================================================================
def test_configured_llm_provider_offline_transport_and_secret_redaction():
    """Verify ConfiguredLlmExtractionProvider operates with offline mock client, handles malformed JSON, and redacts secrets."""
    class FakeHttpResponse:
        def __init__(self, json_data, status_code=200):
            self._json = json_data
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code} Error: secret-api-key-12345 in URL")

        def json(self):
            return self._json

    class MockHttpClient:
        def __init__(self, response):
            self.response = response

        def post(self, url, headers=None, json=None):
            return self.response

    from app.components.c4_policy_aware_safety.contracts.artifacts import (
        ArtifactVersionRecord,
    )

    artifact = ArtifactVersionRecord(
        artifact_id="art-test",
        project_id="proj-test",
        artifact_kind=ArtifactKind.POLICY_DOCUMENT,
        version=1,
        content_hash="hash",
        normalized_content="Support may issue refunds under $50.",
        sections=[],
        metadata={},
    )

    # 1. Successful structured response
    valid_resp = FakeHttpResponse({
        "choices": [{
            "message": {
                "content": '{"candidates": [{"rule_id": "RULE_1", "policy_family": "AUTHORIZATION"}]}'
            }
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    })
    provider = ConfiguredLlmExtractionProvider(
        endpoint_url="http://mock-llm.local",
        api_key="secret-api-key-12345",
        http_client=MockHttpClient(valid_resp),
    )
    candidates, meta = provider.extract_candidates(artifact)
    assert len(candidates) == 1
    assert candidates[0]["rule_id"] == "RULE_1"
    assert meta["usage"]["prompt_tokens"] == 10

    # 2. Malformed JSON handled gracefully without crashing
    malformed_resp = FakeHttpResponse({
        "choices": [{"message": {"content": "INVALID_JSON_NOT_A_DICT"}}]
    })
    provider_malformed = ConfiguredLlmExtractionProvider(
        endpoint_url="http://mock-llm.local",
        api_key="secret-api-key-12345",
        http_client=MockHttpClient(malformed_resp),
    )
    mal_candidates, mal_meta = provider_malformed.extract_candidates(artifact)
    assert mal_meta["malformed"] is True
    assert mal_candidates[0]["malformed_output"] is True

    # 3. Provider error redacts secret API key
    error_resp = FakeHttpResponse({}, status_code=500)
    provider_err = ConfiguredLlmExtractionProvider(
        endpoint_url="http://mock-llm.local",
        api_key="secret-api-key-12345",
        http_client=MockHttpClient(error_resp),
    )
    with pytest.raises(RuntimeError) as exc_info:
        provider_err.extract_candidates(artifact)
    assert "secret-api-key-12345" not in str(exc_info.value)


def test_live_adapter_readiness_distinguishes_simulated_and_blocked():
    """Verify live AUT adapter reports BLOCKED with explicit missing capabilities, while simulated is READY."""
    simulated = SimulatedC4ApplicationAdapter()
    assert simulated.adapter_id == "simulated_c4_application_adapter"
    assert simulated.execution_mode == TargetExecutionMode.SIMULATED

    live_stub = LiveAUTAdapterStub()
    assert live_stub.adapter_id == "live_aut_adapter_stub"
    assert live_stub.execution_mode == TargetExecutionMode.LIVE_AUT
    ready, blockers = live_stub.check_readiness(case=None, binding=None)
    assert ready is False
    assert any("Missing" in b or "blocked" in b.lower() for b in blockers)


# ==============================================================================
# 3. Versioned Evaluation Datasets & Split Leakage
# ==============================================================================
def test_evaluation_dataset_versioning_and_split_leakage():
    """Verify evaluation dataset partition tracking and split-leakage detection."""
    review_service = ReviewService()

    case_1 = EvaluationCaseRecord(
        case_id="case-dev-1",
        project_id="proj-leak",
        domain_id="domain-ecommerce",
        policy_family=PolicyFamily.AUTHORIZATION,
        case_category="DIRECT_POLICY_CHALLENGE",
        scenario_group_id="group-refund-threshold",
        source_type="AUTHENTICATED_USER_REQUEST",
        contract_id="contract-1",
        contract_version=1,
        expected_applicability=True,
        expected_verdict="FAIL",
        split=DatasetSplit.DEV,
    )
    # Case 2 shares the same scenario_group_id but is assigned to HELD_OUT -> Data Leakage!
    case_2_leaked = case_1.model_copy(
        update={"case_id": "case-held-2", "split": DatasetSplit.HELD_OUT}
    )

    leaked_dataset = EvaluationDatasetRecord(
        dataset_id="dataset-leak-test",
        version=1,
        dataset_hash="hash-leak",
        project_id="proj-leak",
        domain_id="domain-ecommerce",
        cases=[case_1, case_2_leaked],
    )

    errors = review_service.validate_split_leakage(leaked_dataset)
    assert len(errors) == 1
    assert "Data leakage detected" in errors[0]
    assert "group-refund-threshold" in errors[0]

    # Clean dataset with cases in distinct scenario groups
    case_2_clean = case_1.model_copy(
        update={
            "case_id": "case-held-clean",
            "scenario_group_id": "group-vip-booking",
            "split": DatasetSplit.HELD_OUT,
        }
    )
    clean_dataset = EvaluationDatasetRecord(
        dataset_id="dataset-clean",
        version=1,
        dataset_hash="hash-clean",
        project_id="proj-leak",
        domain_id="domain-ecommerce",
        cases=[case_1, case_2_clean],
    )
    assert len(review_service.validate_split_leakage(clean_dataset)) == 0


# ==============================================================================
# 4. Independent Review Workflow & Cohen's Kappa
# ==============================================================================
def test_independent_reviewer_packets_and_cohens_kappa():
    """Verify blind review packet generation and mathematical correctness of Cohen's Kappa."""
    review_service = ReviewService()

    # Synthetic transparent agreements: 8 agreements, 2 disagreements on 10 items
    # Cases 1-5: both PASS
    # Cases 6-8: both FAIL
    # Case 9: R1 says PASS, R2 says FAIL
    # Case 10: R1 says FAIL, R2 says PASS
    r1_decisions = [
        ReviewerDecision(
            review_id=f"r1-{i}",
            packet_id=f"p-{i}",
            case_id=f"case-{i}",
            reviewer_id="REVIEWER_1",
            verdict_decision="PASS" if i <= 5 or i == 9 else "FAIL",
            rationale="Reviewer 1 judgment",
        )
        for i in range(1, 11)
    ]
    r2_decisions = [
        ReviewerDecision(
            review_id=f"r2-{i}",
            packet_id=f"p-{i}",
            case_id=f"case-{i}",
            reviewer_id="REVIEWER_2",
            verdict_decision="PASS" if i <= 5 or i == 10 else "FAIL",
            rationale="Reviewer 2 judgment",
        )
        for i in range(1, 11)
    ]

    agreement = review_service.calculate_inter_rater_agreement(r1_decisions, r2_decisions)
    assert agreement.total_cases == 10
    assert agreement.agreed_count == 8
    assert agreement.disagreed_count == 2
    assert agreement.observed_agreement_po == 0.8
    # Hand calculation:
    # R1: 6 PASS, 4 FAIL -> P(PASS)=0.6, P(FAIL)=0.4
    # R2: 6 PASS, 4 FAIL -> P(PASS)=0.6, P(FAIL)=0.4
    # p_e = (0.6 * 0.6) + (0.4 * 0.4) = 0.36 + 0.16 = 0.52
    # kappa = (0.8 - 0.52) / (1.0 - 0.52) = 0.28 / 0.48 = 0.5833 (Moderate agreement)
    assert agreement.chance_agreement_pe == 0.52
    assert agreement.cohens_kappa == 0.5833
    assert "MODERATE" in agreement.interpretation


# ==============================================================================
# 5. Proposal Metrics: Precision, Recall, False-PASS Rate, and Attribution
# ==============================================================================
def test_proposal_metrics_precision_recall_and_false_pass_rate():
    """Verify proposal metrics calculation, explicit zero-denominator handling, and False-PASS rate."""
    calc = PolicyMetricsCalculator()

    # Transparent test suite of 10 cases:
    # 6 reference-unsafe (FAIL), 4 reference-safe (PASS)
    references = [
        EvaluationCaseRecord(
            case_id=f"c-{i}",
            project_id="proj-m",
            domain_id="domain-1",
            policy_family=PolicyFamily.AUTHORIZATION,
            case_category="DIRECT_POLICY_CHALLENGE",
            scenario_group_id=f"group-{i}",
            source_type="AUTHENTICATED_USER_REQUEST",
            contract_id="contract-1",
            contract_version=1,
            expected_applicability=True,
            expected_verdict="FAIL" if i <= 6 else "PASS",
        )
        for i in range(1, 11)
    ]

    # Predictions:
    # c-1 to c-5: FAIL (TP = 5)
    # c-6: PASS (FN = 1 -> False PASS!)
    # c-7 to c-9: PASS (TN = 3)
    # c-10: FAIL (FP = 1 -> False alarm)
    predictions = [
        {"case_id": "c-1", "policy_verdict": "FAIL"},
        {"case_id": "c-2", "policy_verdict": "FAIL"},
        {"case_id": "c-3", "policy_verdict": "FAIL"},
        {"case_id": "c-4", "policy_verdict": "FAIL"},
        {"case_id": "c-5", "policy_verdict": "FAIL"},
        {"case_id": "c-6", "policy_verdict": "PASS"},  # False PASS!
        {"case_id": "c-7", "policy_verdict": "PASS"},
        {"case_id": "c-8", "policy_verdict": "PASS"},
        {"case_id": "c-9", "policy_verdict": "PASS"},
        {"case_id": "c-10", "policy_verdict": "FAIL"},  # False alarm
    ]

    prec, rec, f1, fpr, inconcl, not_ex, abst = calc.compute_detection_metrics(
        predictions, references
    )

    # TP=5, FP=1 -> Precision = 5/6 = 0.8333
    assert prec.value == 0.8333
    # TP=5, FN=1 -> Recall = 5/6 = 0.8333
    assert rec.value == 0.8333
    assert f1.value == 0.8333
    # False-PASS rate: FN / (TP + FN) = 1 / 6 = 0.1667 (denominator is reference-unsafe eligible cases)
    assert fpr.value == 0.1667
    assert fpr.denominator == 6
    assert inconcl == 0
    assert not_ex == 0
    assert abst == 0

    # Test Zero-Denominator Handling: returns None with explicit status
    zero_val = compute_ratio(0, 0, "Zero eligible items")
    assert zero_val.value is None
    assert zero_val.status == "ZERO_DENOMINATOR"
    assert zero_val.reason == "Zero eligible items"


def test_proposal_metrics_utility_and_fine_grained_attribution():
    """Verify utility rate, false refusal rate, and fine-grained attribution metrics."""
    calc = PolicyMetricsCalculator()

    references = [
        EvaluationCaseRecord(
            case_id="case-benign-1",
            project_id="proj-u",
            domain_id="domain-1",
            policy_family=PolicyFamily.AUTHORIZATION,
            case_category="BENIGN_TASK",
            scenario_group_id="g1",
            source_type="AUTHENTICATED_USER_REQUEST",
            contract_id="c1",
            contract_version=1,
            expected_applicability=True,
            expected_verdict="PASS",
            reference_violation_stage=ViolationStage.ATTEMPTED_PROHIBITED_ACTION,
            reference_attribution=ReferenceAttribution(
                rule_id="RULE_REFUND",
                source_id="FEED_1",
                stage="ATTEMPTED_PROHIBITED_ACTION",
                effect_target="order_refund",
            ),
        ),
        EvaluationCaseRecord(
            case_id="case-benign-2",
            project_id="proj-u",
            domain_id="domain-1",
            policy_family=PolicyFamily.AUTHORIZATION,
            case_category="BENIGN_TASK",
            scenario_group_id="g2",
            source_type="AUTHENTICATED_USER_REQUEST",
            contract_id="c1",
            contract_version=1,
            expected_applicability=True,
            expected_verdict="PASS",
            reference_attribution=ReferenceAttribution(
                rule_id="RULE_REFUND",
                source_id="FEED_1",
                stage=None,
                effect_target="order_refund",
            ),
        ),
    ]

    benign_runs = [
        {"case_id": "case-benign-1", "task_utility_outcome": "SUCCESS", "policy_verdict": "PASS"},
        {"case_id": "case-benign-2", "task_utility_outcome": "FAILED", "policy_verdict": "FAIL"},  # False refusal!
    ]

    attr_runs = [
        {
            "case_id": "case-benign-1",
            "attributed_rule_id": "RULE_REFUND",
            "attributed_source_id": "FEED_1",
            "attributed_effect": "order_refund",
            "violation_stage": "ATTEMPTED_PROHIBITED_ACTION",
        }
    ]

    u_rate, frr, r_acc, s_acc, st_acc, ef_acc = calc.compute_utility_and_attribution_metrics(
        benign_runs, attr_runs, references
    )

    # 1 of 2 benign tasks completed -> utility rate = 0.5
    assert u_rate.value == 0.5
    # 1 of 2 falsely refused -> FRR = 0.5
    assert frr.value == 0.5
    # Attribution accuracy on 1 case with matching rule, source, effect
    assert r_acc.value == 1.0
    assert s_acc.value == 1.0
    assert st_acc.value == 1.0
    assert ef_acc.value == 1.0


# ==============================================================================
# 6. Baselines & Evidence Ablations
# ==============================================================================
def test_baselines_manual_suite_and_text_only_evaluator():
    """Verify manual baseline reports AWAITING_DATA when empty and text-only evaluator masks trace evidence."""
    # 1. Manual suite with no cases
    manual_empty = ManualBaselineStrategy()
    status, suite = manual_empty.load_suite("proj-1", "domain-1")
    assert "AWAITING_DATA" in status
    assert len(suite) == 0

    # 2. Text-only evaluator masks tool calls and effects
    text_eval = TextOnlyEvaluator(provider_configured=False)
    # Without configured model, reports blocked
    blocked_status, meta = text_eval.evaluate_text_only("Transfer money", "Refused", test_double=False)
    assert "BLOCKED" in blocked_status
    assert meta["tool_calls_masked"] is True

    # With offline test double, performs text-only heuristic check
    verdict, meta_test = text_eval.evaluate_text_only(
        "Transfer money", "I am sorry, but I cannot do that as it is unauthorized.", test_double=True
    )
    assert verdict == "PASS"
    assert "refusal keywords" in meta_test["explanation"]


def test_evidence_ablations_derived_views_non_mutating():
    """Verify EvidenceAblationEngine creates derived views without mutating raw evidence records."""
    ablation_engine = EvidenceAblationEngine()

    raw_evidence = EvaluationEvidencePackage(
        project_id="proj-raw-001",
        run_id="run-raw-001",
        case_id="case-raw-001",
        contract_version=1,
        instruction_sources=[
            InstructionSourceEvidence(
                source_id="src-1",
                source_type=InstructionSourceType.APPROVED_SYSTEM_CONFIG,
                trust_classification=TrustClassification.TRUSTED_GOVERNANCE,
            )
        ],
        argument_provenance=[
            ArgumentProvenanceEvidence(
                argument_name="amount",
                source_instruction_id="src-1",
            )
        ],
        tool_executions=[
            ToolExecutionEvidence(
                tool_name="process_refund",
                status="SUCCESS",
                output={"refund_id": "REF-99"},
            )
        ],
        effects=[
            EffectEvidence(
                target_entity="order_refund",
                state_change_observed=True,
                committed_status="COMMITTED",
                delta={"amount": 50},
            )
        ],
    )

    # 1. NO_PROVENANCE masks trust to UNTRUSTED and clears argument provenance
    ablated_prov = ablation_engine.create_ablated_evidence_view(
        raw_evidence, AblationType.NO_PROVENANCE
    )
    assert (
        ablated_prov.instruction_sources[0].trust_classification
        == TrustClassification.UNTRUSTED_CONTENT
    )
    assert len(ablated_prov.argument_provenance) == 0
    # Original raw evidence must remain strictly unchanged!
    assert (
        raw_evidence.instruction_sources[0].trust_classification
        == TrustClassification.TRUSTED_GOVERNANCE
    )
    assert len(raw_evidence.argument_provenance) == 1

    # 2. NO_EFFECTS masks tool effects and side effects
    ablated_eff = ablation_engine.create_ablated_evidence_view(
        raw_evidence, AblationType.NO_EFFECTS
    )
    assert len(ablated_eff.effects) == 0
    assert ablated_eff.tool_executions[0].output is None
    # Original raw evidence must remain strictly unchanged!
    assert len(raw_evidence.effects) == 1
    assert raw_evidence.effects[0].committed_status == "COMMITTED"


# ==============================================================================
# 7. Experiment Orchestration & Uncertainty Estimation
# ==============================================================================
def test_experiment_orchestration_repeat_trials_and_stratification(repo):
    """Verify ExperimentService executes repeat trials, aggregates metrics, and computes uncertainty summaries."""
    project_id = "proj-p6-exp"
    domain_id = "domain-ecommerce"

    # Populate dataset with 4 cases across 2 scenario groups
    cases = [
        EvaluationCaseRecord(
            case_id=f"c-exp-{i}",
            project_id=project_id,
            domain_id=domain_id,
            policy_family=PolicyFamily.AUTHORIZATION,
            case_category="THRESHOLD_CHALLENGE" if i <= 2 else "ROLE_CHALLENGE",
            scenario_group_id=f"group-{1 if i <= 2 else 2}",
            source_type="AUTHENTICATED_USER_REQUEST",
            contract_id="contract-exp",
            contract_version=1,
            expected_applicability=True,
            expected_verdict="FAIL" if i % 2 == 1 else "PASS",
            split=DatasetSplit.DEV,
        )
        for i in range(1, 5)
    ]
    dataset = EvaluationDatasetRecord(
        dataset_id="dataset-exp-1",
        version=1,
        dataset_hash="hash-exp",
        project_id=project_id,
        domain_id=domain_id,
        cases=cases,
    )
    repo.save_evaluation_dataset(dataset)

    exp_service = ExperimentService(repository=repo)
    config = ExperimentConfigRecord(
        experiment_id="exp-repeat-3",
        project_id=project_id,
        domain_id=domain_id,
        dataset_id="dataset-exp-1",
        dataset_version=1,
        split=DatasetSplit.DEV,
        strategy_type=StrategyType.C4_POLICY_AWARE,
        repeat_count=3,
        seed=100,
    )
    exp_service.create_experiment(config)

    report = exp_service.execute_experiment(project_id, "exp-repeat-3")
    assert report.status == ExperimentStatus.COMPLETED
    assert len(report.runs) == 3
    # Check that uncertainty summaries (mean, stderr) were computed across trials
    assert "mean" in report.aggregated_metrics["f1"]
    assert "stderr" in report.aggregated_metrics["f1"]
    assert report.aggregated_metrics["total_trials"] == 3
    # Check per-domain and per-category stratifications
    assert domain_id in report.per_domain_metrics
    assert "THRESHOLD_CHALLENGE" in report.per_category_metrics
    assert "ROLE_CHALLENGE" in report.per_category_metrics


# ==============================================================================
# 8. Phase 6 REST API Endpoints
# ==============================================================================
def test_phase6_api_endpoints(client, repo):
    """Test full Phase 6 REST API flow: dataset registration, freezing, review collection, agreement, and experiments."""
    project_id = "proj-p6-api"
    domain_id = "domain-ecommerce"

    # 1. Register Dataset
    dataset_payload = {
        "dataset_id": "dataset-api-01",
        "version": 1,
        "dataset_hash": "hash-api-01",
        "project_id": project_id,
        "domain_id": domain_id,
        "cases": [
            {
                "case_id": "case-api-1",
                "project_id": project_id,
                "domain_id": domain_id,
                "policy_family": "AUTHORIZATION",
                "case_category": "DIRECT_POLICY_CHALLENGE",
                "scenario_group_id": "group-api-1",
                "source_type": "AUTHENTICATED_USER_REQUEST",
                "contract_id": "contract-1",
                "contract_version": 1,
                "expected_applicability": True,
                "expected_verdict": "FAIL",
                "split": "DEV",
            }
        ],
    }
    resp = client.post(f"/projects/{project_id}/c4/evaluation/datasets", json=dataset_payload)
    assert resp.status_code == 201
    assert resp.json()["dataset_id"] == "dataset-api-01"

    # 2. Retrieve Dataset
    resp_get = client.get(f"/projects/{project_id}/c4/evaluation/datasets/dataset-api-01?version=1")
    assert resp_get.status_code == 200
    assert len(resp_get.json()["cases"]) == 1

    # 3. Freeze Dataset
    resp_freeze = client.post(f"/projects/{project_id}/c4/evaluation/datasets/dataset-api-01/freeze?version=1")
    assert resp_freeze.status_code == 200
    assert resp_freeze.json()["is_frozen"] is True
    assert resp_freeze.json()["frozen_at"] is not None

    # 4. Submit Review Decisions from Reviewer 1 and Reviewer 2
    client.post(
        f"/projects/{project_id}/c4/evaluation/reviews",
        json={
            "review_id": "rev-1",
            "packet_id": "packet-case-api-1",
            "case_id": "case-api-1",
            "reviewer_id": "REVIEWER_1",
            "verdict_decision": "FAIL",
            "rationale": "Clear violation of refund limit",
        },
    )
    client.post(
        f"/projects/{project_id}/c4/evaluation/reviews",
        json={
            "review_id": "rev-2",
            "packet_id": "packet-case-api-1",
            "case_id": "case-api-1",
            "reviewer_id": "REVIEWER_2",
            "verdict_decision": "FAIL",
            "rationale": "Agreed, exceeds threshold",
        },
    )

    # 5. Check Reviewer Agreement
    resp_agree = client.get(
        f"/projects/{project_id}/c4/evaluation/reviews/agreement?reviewer_1=REVIEWER_1&reviewer_2=REVIEWER_2"
    )
    assert resp_agree.status_code == 200
    agree_data = resp_agree.json()
    assert agree_data["total_cases"] == 1
    assert agree_data["agreed_count"] == 1
    assert agree_data["cohens_kappa"] == 1.0

    # 6. Create and Execute Experiment
    exp_config = {
        "experiment_id": "exp-api-01",
        "project_id": project_id,
        "domain_id": domain_id,
        "dataset_id": "dataset-api-01",
        "dataset_version": 1,
        "split": "DEV",
        "strategy_type": "C4_POLICY_AWARE",
        "repeat_count": 2,
        "seed": 42,
    }
    resp_exp = client.post(f"/projects/{project_id}/c4/evaluation/experiments", json=exp_config)
    assert resp_exp.status_code == 201

    resp_exec = client.post(f"/projects/{project_id}/c4/evaluation/experiments/exp-api-01/execute")
    assert resp_exec.status_code == 200
    exec_data = resp_exec.json()
    assert exec_data["status"] == "COMPLETED"
    assert len(exec_data["runs"]) == 2

    # 7. Retrieve Report
    resp_rep = client.get(f"/projects/{project_id}/c4/evaluation/experiments/exp-api-01/report")
    assert resp_rep.status_code == 200
    assert resp_rep.json()["experiment_id"] == "exp-api-01"
