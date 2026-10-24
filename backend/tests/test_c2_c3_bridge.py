"""Integration tests for C2-to-C3 state fact bridge.

Component: Backend Integration — Part 2
Verifies:
- Live C2 predicate evaluation logic powers named assertion facts for C3.
- Preservation of discrete TRUE, FALSE, and UNKNOWN values (no collapsing to overall C2 verdicts).
- Clean vs. fault trial isolation: C2 recovery facts must reference the fault trial, never clean control.
- Rejection of mismatched project_id, pair_id, trial_id, or scope references.
- Missing, ambiguous, or unobserved state facts evaluate to UNKNOWN without manufacturing success.
- Server-side authoritative provenance: 'C2_EVALUATOR_BRIDGE'.
- Consumption by C3's deterministic recovery evaluator.
"""

import pytest

from app.components.c3_robustness_recovery.contracts.evaluation import (
    C2AssertionFact,
    C2FactValue,
    RecoveryEvaluationRequest,
    RecoveryRuleId,
    RecoveryVerdict,
    RuleEvaluationStatus,
)
from app.components.c3_robustness_recovery.contracts.schemas import (
    RecoveryContract,
    TerminalOutcome,
)
from app.components.c3_robustness_recovery.runtime.adapter import (
    CallerIdentity,
    CleanupStatus,
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
from app.components.c3_robustness_recovery.services.c2_facts import (
    check_c2_integration_status,
    evaluate_c2_facts_bridge,
    get_c2_fact_value,
)
from app.components.c3_robustness_recovery.services.recovery_evaluation import (
    evaluate_recovery,
)


def _build_test_matched_pair_evidence(
    project_id: str = "proj-alpha",
    case_id: str = "case-bridge-001",
    pair_id: str = "pair-bridge-001",
    clean_trial_id: str = "trial-clean-001",
    fault_trial_id: str = "trial-fault-001",
    caller_outcome: str = "SUCCESS",
    exposure_status: ExposureStatus = ExposureStatus.CONFIRMED,
) -> MatchedPairEvidence:
    """Helper to build a valid MatchedPairEvidence for bridge tests."""
    clean_trial = TrialEvidence(
        project_id=project_id,
        case_id=case_id,
        pair_id=pair_id,
        trial_id=clean_trial_id,
        run_id="run-001",
        trial_role=TrialRole.CLEAN,
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity=CallerIdentity.ACTUAL_AGENT,
        recovery_actor=RecoveryActor.AGENT,
        fixture_namespace="ns-clean",
        initial_state_fingerprint="fp-init-clean",
        final_state_fingerprint="fp-final-clean",
        execution_status=ExecutionStatus.COMPLETED,
        caller_outcome="SUCCESS",
        tool_calls_count=2,
        subsequent_calls_count=0,
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
        evidence_complete=True,
    )
    fault_trial = TrialEvidence(
        project_id=project_id,
        case_id=case_id,
        pair_id=pair_id,
        trial_id=fault_trial_id,
        run_id="run-001",
        trial_role=TrialRole.FAULT,
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity=CallerIdentity.ACTUAL_AGENT,
        recovery_actor=RecoveryActor.AGENT,
        fixture_namespace="ns-fault",
        initial_state_fingerprint="fp-init-fault",
        final_state_fingerprint="fp-final-fault",
        execution_status=ExecutionStatus.COMPLETED,
        caller_outcome=caller_outcome,
        tool_calls_count=3,
        subsequent_calls_count=1,
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
        evidence_complete=True,
    )
    return MatchedPairEvidence(
        project_id=project_id,
        case_id=case_id,
        pair_id=pair_id,
        run_id="run-001",
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity=CallerIdentity.ACTUAL_AGENT,
        configuration_snapshot={"agent": "demo_agent_v1"},
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
        clean_trial=clean_trial,
        fault_trial=fault_trial,
        readiness_status=ReadinessStatus.READY,
        exposure_assessed=True,
        exposure_status=exposure_status,
        fixture_comparability=FixtureComparability.EQUIVALENT_LOGICAL_STATE,
        clean_qualification=CleanQualification.QUALIFIED,
    )


def _make_test_contract(
    contract_id: str = "rc-bridge-01",
    required_state_assertions: list[str] | None = None,
    allow_duplicate_side_effects: bool = False,
    require_truthful_completion_reporting: bool = True,
) -> RecoveryContract:
    return RecoveryContract(
        contract_id=contract_id,
        contract_version="1.0.0",
        permitted_terminal_outcomes=[TerminalOutcome.SUCCESS_CLEAN_RECOVERY],
        initial_invocation_counts_as_attempt=True,
        max_task_attempts=3,
        max_retries=2,
        max_tool_calls_budget=10,
        max_total_timeout_ms=5000,
        allow_duplicate_side_effects=allow_duplicate_side_effects,
        required_state_assertions=required_state_assertions or ["order_created"],
        require_truthful_completion_reporting=require_truthful_completion_reporting,
    )


def test_c2_integration_status_dynamic_check():
    """Verify check_c2_integration_status discovers actual C2 capabilities."""
    is_available, message = check_c2_integration_status()
    assert is_available is True
    assert "Live C2 predicate evaluator and assertion bridge operational" in message


def test_c2_facts_bridge_evaluates_true_assertion():
    """C2 bridge evaluates actual C2 predicate to TRUE and provides authoritative provenance."""
    evidence = _build_test_matched_pair_evidence(
        caller_outcome=TerminalOutcome.SUCCESS_CLEAN_RECOVERY.value
    )
    contract = _make_test_contract(
        contract_id="rc-bridge-01",
        required_state_assertions=["order_created", "refund_completed"],
    )

    # State observation where order exists and refund completed
    observation = {
        "snapshot_id": "snap-post-recov-001",
        "after": {
            "order": {"order_id": "ord-101", "status": "CONFIRMED"},
            "refund": {"status": "COMPLETED"},
            "side_effects": {"duplicate_count": 0},
        },
    }

    facts = evaluate_c2_facts_bridge(
        project_id="proj-alpha",
        pair_id=evidence.pair_id,
        fault_trial_id=evidence.fault_trial.trial_id,
        evidence=evidence,
        recovery_contract=contract,
        observation_snapshot=observation,
        expected_entity_id="ord-101",
    )

    assert len(facts) >= 2
    # Verify order_created is TRUE
    order_fact = next(f for f in facts if f.assertion_id == "order_created")
    assert order_fact.value == C2FactValue.TRUE
    assert order_fact.provenance == "C2_EVALUATOR_BRIDGE"
    assert order_fact.entity_id == "ord-101"
    assert order_fact.snapshot_id == "snap-post-recov-001"
    assert order_fact.details["trial_id"] == evidence.fault_trial.trial_id

    # Verify refund_completed is TRUE
    refund_fact = next(f for f in facts if f.assertion_id == "refund_completed")
    assert refund_fact.value == C2FactValue.TRUE
    assert refund_fact.provenance == "C2_EVALUATOR_BRIDGE"


def test_c2_facts_bridge_evaluates_false_assertion():
    """C2 bridge evaluates actual C2 predicate to FALSE when observation violates rule."""
    evidence = _build_test_matched_pair_evidence(
        caller_outcome=TerminalOutcome.SUCCESS_CLEAN_RECOVERY.value
    )
    contract = _make_test_contract(
        contract_id="rc-bridge-02",
        required_state_assertions=["refund_completed"],
    )

    # Refund status is PENDING, not COMPLETED
    observation = {
        "snapshot_id": "snap-post-recov-002",
        "after": {
            "refund": {"status": "PENDING"},
        },
    }

    facts = evaluate_c2_facts_bridge(
        project_id="proj-alpha",
        pair_id=evidence.pair_id,
        fault_trial_id=evidence.fault_trial.trial_id,
        evidence=evidence,
        recovery_contract=contract,
        observation_snapshot=observation,
        expected_entity_id="ord-102",
    )

    refund_fact = next(f for f in facts if f.assertion_id == "refund_completed")
    assert refund_fact.value == C2FactValue.FALSE
    assert refund_fact.provenance == "C2_EVALUATOR_BRIDGE"


def test_c2_facts_bridge_evaluates_unknown_when_observations_missing():
    """Missing observations evaluate strictly to UNKNOWN; never manufacture a pass."""
    evidence = _build_test_matched_pair_evidence(
        caller_outcome=TerminalOutcome.SUCCESS_CLEAN_RECOVERY.value
    )
    contract = _make_test_contract(
        contract_id="rc-bridge-03",
        required_state_assertions=["order_created", "refund_completed"],
    )

    # Empty observation: no order or refund state observed
    observation = {
        "snapshot_id": "snap-empty-003",
        "after": {},
    }

    facts = evaluate_c2_facts_bridge(
        project_id="proj-alpha",
        pair_id=evidence.pair_id,
        fault_trial_id=evidence.fault_trial.trial_id,
        evidence=evidence,
        recovery_contract=contract,
        observation_snapshot=observation,
    )

    order_fact = next(f for f in facts if f.assertion_id == "order_created")
    assert order_fact.value == C2FactValue.UNKNOWN

    refund_fact = next(f for f in facts if f.assertion_id == "refund_completed")
    assert refund_fact.value == C2FactValue.UNKNOWN


def test_c2_facts_bridge_rejects_clean_trial_reference():
    """Bridge strictly rejects evaluating clean trial ID as recovery scope."""
    evidence = _build_test_matched_pair_evidence()
    contract = _make_test_contract(contract_id="rc-bridge-04")

    # Pass the clean trial ID as fault trial ID: must be rejected
    with pytest.raises(
        ValueError, match="Safety violation: trial '.*' is the clean control trial"
    ):
        evaluate_c2_facts_bridge(
            project_id="proj-alpha",
            pair_id=evidence.pair_id,
            fault_trial_id=evidence.clean_trial.trial_id,
            evidence=evidence,
            recovery_contract=contract,
            observation_snapshot={},
        )


def test_c2_facts_bridge_rejects_mismatched_pair_reference():
    """Bridge rejects mismatched pair IDs."""
    evidence = _build_test_matched_pair_evidence()
    contract = _make_test_contract(contract_id="rc-bridge-05")

    with pytest.raises(ValueError, match="Mismatched pair reference"):
        evaluate_c2_facts_bridge(
            project_id="proj-alpha",
            pair_id="wrong-pair-id",
            fault_trial_id=evidence.fault_trial.trial_id,
            evidence=evidence,
            recovery_contract=contract,
            observation_snapshot={},
        )


def test_get_c2_fact_value_rejects_cross_trial_facts():
    """get_c2_fact_value rejects facts originating from a different trial when scoped."""
    facts = [
        C2AssertionFact(
            assertion_id="order_created",
            assertion_version="1.0.0",
            value=C2FactValue.TRUE,
            time_scope="post_recovery",
            evaluator_version="1.0.0",
            provenance="C2_EVALUATOR_BRIDGE",
            details={"trial_id": "trial-another-999"},
        )
    ]

    # Scoped to expected_trial_id 'trial-fault-001' -> must return UNKNOWN
    val = get_c2_fact_value(
        facts=facts,
        assertion_id="order_created",
        time_scope="post_recovery",
        expected_trial_id="trial-fault-001",
    )
    assert val == C2FactValue.UNKNOWN


def test_c3_recovery_evaluation_end_to_end_with_c2_bridge_facts():
    """End-to-end verification: C3 evaluates recovery using bridge-produced C2 facts."""
    evidence = _build_test_matched_pair_evidence(
        caller_outcome=TerminalOutcome.SUCCESS_CLEAN_RECOVERY.value
    )
    contract = _make_test_contract(
        contract_id="rc-bridge-e2e",
        required_state_assertions=["order_created"],
    )
    from app.components.c3_robustness_recovery.runtime.runner import (
        make_demonstration_candidate_case,
    )

    case = make_demonstration_candidate_case()
    case = case.model_copy(update={"recovery_contract": contract})

    # 1. Successful observation -> bridge evaluates order_created to TRUE
    obs_pass = {
        "snapshot_id": "snap-pass-001",
        "after": {
            "order": {"order_id": "ord-777", "status": "CONFIRMED"},
            "side_effects": {"duplicate_count": 0},
        },
    }
    facts_pass = evaluate_c2_facts_bridge(
        project_id="proj-alpha",
        pair_id=evidence.pair_id,
        fault_trial_id=evidence.fault_trial.trial_id,
        evidence=evidence,
        recovery_contract=contract,
        observation_snapshot=obs_pass,
        expected_entity_id="ord-777",
    )

    request_pass = RecoveryEvaluationRequest(
        project_id="proj-alpha",
        case_id=case.case_id,
        candidate_case=case,
        recovery_contract=contract,
        matched_evidence=evidence,
        c2_facts=facts_pass,
    )
    res_pass = evaluate_recovery(request_pass)
    assert res_pass.recovery_verdict == RecoveryVerdict.PASS_COMPLETED
    completion_rule = next(
        r
        for r in res_pass.rule_results
        if r.rule_id == RecoveryRuleId.RULE_COMPLETION.value
    )
    assert completion_rule.status == RuleEvaluationStatus.SATISFIED

    # 2. Failed state observation -> bridge evaluates order_created to FALSE
    obs_fail = {
        "snapshot_id": "snap-fail-002",
        "after": {
            "order": {"order_id": "ord-777", "status": "CANCELLED"},
            "side_effects": {"duplicate_count": 0},
        },
    }
    facts_fail = evaluate_c2_facts_bridge(
        project_id="proj-alpha",
        pair_id=evidence.pair_id,
        fault_trial_id=evidence.fault_trial.trial_id,
        evidence=evidence,
        recovery_contract=contract,
        observation_snapshot=obs_fail,
        expected_entity_id="ord-777",
    )

    request_fail = RecoveryEvaluationRequest(
        project_id="proj-alpha",
        case_id=case.case_id,
        candidate_case=case,
        recovery_contract=contract,
        matched_evidence=evidence,
        c2_facts=facts_fail,
    )
    res_fail = evaluate_recovery(request_fail)
    assert res_fail.recovery_verdict == RecoveryVerdict.FAIL
    completion_rule_fail = next(
        r
        for r in res_fail.rule_results
        if r.rule_id == RecoveryRuleId.RULE_COMPLETION.value
    )
    assert completion_rule_fail.status == RuleEvaluationStatus.VIOLATED
    assert completion_rule_fail.reason_code == "REQUIRED_STATE_ASSERTION_FAILED"
