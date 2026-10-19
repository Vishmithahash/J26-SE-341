"""Hermetic test suite for Component 3 Phase 4: Recovery Evaluation.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 4 - Recovery evaluation using evidence and C2 facts.

Tests all fixed recovery rules, the four recovery verdicts, eligibility gates,
C2 fact handling, and confirmed Phase 3 gap corrections without external services,
databases, or live target dependencies.
"""

import asyncio
import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.components.c3_robustness_recovery.contracts.evaluation import (
    C2AssertionFact,
    C2FactValue,
    EvaluationStatus,
    RecoveryEvaluationRequest,
    RecoveryRuleId,
    RecoveryVerdict,
    RuleEvaluationStatus,
)
from app.components.c3_robustness_recovery.contracts.schemas import (
    EffectPhase,
    FaultFamily,
    InterceptionHook,
    TimeoutDisconnectionMode,
)
from app.components.c3_robustness_recovery.runtime.adapter import (
    CallerIdentity,
    CleanupStatus,
    DemonstrationFixtureManager,
    DemonstrationToolAdapter,
    RecoveryActor,
    TargetMode,
)
from app.components.c3_robustness_recovery.runtime.evaluate import run_evaluation_cli
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
from app.components.c3_robustness_recovery.runtime.interceptor import (
    DomainToolInterceptor,
    InterceptionPlan,
)
from app.components.c3_robustness_recovery.runtime.runner import (
    HarnessRunner,
    make_demonstration_candidate_case,
    make_demonstration_recovery_contract,
    make_demonstration_task_fixture_metadata,
)
from app.components.c3_robustness_recovery.runtime.suite_runner import (
    build_demonstration_generation_request,
    run_suite_cli,
)
from app.components.c3_robustness_recovery.services.c2_facts import (
    check_c2_integration_status,
    get_c2_fact_value,
    validate_c2_facts,
)
from app.components.c3_robustness_recovery.services.generation import (
    generate_feasible_cases,
)
from app.components.c3_robustness_recovery.services.recovery_evaluation import (
    evaluate_recovery,
)
from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Test Helpers: Synthetic Evidence Construction
# ---------------------------------------------------------------------------


def make_synthetic_matched_evidence(
    caller_outcome: str = "SUCCESS_AFTER_RETRY",
    retries_count: int = 1,
    tool_calls_count: int = 2,
    exposure_status: ExposureStatus = ExposureStatus.CONFIRMED,
    readiness_status: ReadinessStatus = ReadinessStatus.READY,
    clean_qualification: CleanQualification = CleanQualification.QUALIFIED,
    cleanup_status: CleanupStatus = CleanupStatus.CLEANED_AND_VERIFIED,
    clean_execution_status: ExecutionStatus = ExecutionStatus.COMPLETED,
    fault_execution_status: ExecutionStatus = ExecutionStatus.COMPLETED,
    exposure_assessed: bool = True,
    observed_effects: list[str] | None = None,
) -> MatchedPairEvidence:
    """Construct deterministic hermetic trial pair evidence for testing."""
    pair_id = "pair-eval-demo-001"
    clean_trial = TrialEvidence(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        pair_id=pair_id,
        trial_id="tr-clean-001",
        run_id="run-demo-001",
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
        observed_effects=["order_confirmed_in_clean"],
        execution_status=clean_execution_status,
        caller_outcome="SUCCESS",
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
        evidence_complete=True,
    )

    fault_trial = TrialEvidence(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        pair_id=pair_id,
        trial_id="tr-fault-001",
        run_id="run-demo-001",
        trial_role=TrialRole.FAULT,
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity="SCRIPTED_CALLER",
        recovery_actor=RecoveryActor.SCRIPTED_CALLER,
        fixture_namespace="ns_fault",
        initial_state_fingerprint="fp_fault_init",
        final_state_fingerprint="fp_fault_final",
        events=[],
        episodes=[],
        tool_calls_count=tool_calls_count,
        subsequent_calls_count=retries_count,
        observed_effects=observed_effects
        if observed_effects is not None
        else ["order_created_on_subsequent_call"],
        execution_status=fault_execution_status,
        caller_outcome=caller_outcome,
        cleanup_status=cleanup_status,
        evidence_complete=True,
    )

    return MatchedPairEvidence(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        pair_id=pair_id,
        run_id="run-demo-001",
        readiness_status=readiness_status,
        readiness_reasons=[],
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity=CallerIdentity.SCRIPTED_CALLER,
        configuration_snapshot={},
        clean_trial=clean_trial,
        fault_trial=fault_trial,
        fixture_comparability=FixtureComparability.EQUIVALENT_LOGICAL_STATE,
        clean_qualification=clean_qualification,
        exposure_assessed=exposure_assessed,
        exposure_status=exposure_status,
        exposure_reasons=["Verified exposure"],
        cleanup_status=cleanup_status,
        recovery_verdict=None,
        interpretation_limitations=[],
    )


# ---------------------------------------------------------------------------
# 1. Eligibility Gates
# ---------------------------------------------------------------------------


def test_eligibility_unconfirmed_exposure_yields_not_evaluated():
    """Unconfirmed or unassessed exposure must yield NOT_EVALUATED and null verdict."""
    evidence = make_synthetic_matched_evidence(
        exposure_status=ExposureStatus.NOT_TRIGGERED
    )
    req = RecoveryEvaluationRequest(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        candidate_case=make_demonstration_candidate_case(),
        recovery_contract=make_demonstration_recovery_contract(),
        matched_evidence=evidence,
    )
    result = evaluate_recovery(req)

    assert result.evaluation_status == EvaluationStatus.NOT_EVALUATED
    assert result.recovery_verdict is None
    assert any(
        "Fault exposure was not confirmed" in r for r in result.non_evaluation_reasons
    )


def test_eligibility_execution_error_yields_not_evaluated():
    """Execution error in harness trial invalidates evaluation."""
    evidence = make_synthetic_matched_evidence(
        fault_execution_status=ExecutionStatus.EXECUTION_ERROR
    )
    req = RecoveryEvaluationRequest(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        candidate_case=make_demonstration_candidate_case(),
        recovery_contract=make_demonstration_recovery_contract(),
        matched_evidence=evidence,
    )
    result = evaluate_recovery(req)

    assert result.evaluation_status == EvaluationStatus.NOT_EVALUATED
    assert result.recovery_verdict is None
    assert any(
        "Trial execution did not complete normally" in r
        for r in result.non_evaluation_reasons
    )


def test_failed_clean_control_retains_qualification_limitation():
    """Failed clean baseline does not erase exposure, but records limitation and evaluates independently."""
    evidence = make_synthetic_matched_evidence(
        clean_qualification=CleanQualification.DISQUALIFIED
    )
    c2_facts = [
        C2AssertionFact(
            assertion_id="state_order_created",
            value=C2FactValue.TRUE,
        )
    ]
    req = RecoveryEvaluationRequest(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        candidate_case=make_demonstration_candidate_case(),
        recovery_contract=make_demonstration_recovery_contract(),
        matched_evidence=evidence,
        c2_facts=c2_facts,
    )
    result = evaluate_recovery(req)

    assert result.evaluation_status == EvaluationStatus.EVALUATED
    assert result.recovery_verdict == RecoveryVerdict.PASS_COMPLETED
    assert len(result.clean_control_limitations) > 0
    assert "DISQUALIFIED" in result.clean_control_limitations[0]


# ---------------------------------------------------------------------------
# 2. Verdict Logic: The Four Authoritative Verdicts
# ---------------------------------------------------------------------------


def test_verdict_pass_completed():
    """All rules satisfied with verified C2 state assertions -> PASS_COMPLETED."""
    evidence = make_synthetic_matched_evidence(
        caller_outcome="SUCCESS_AFTER_RETRY", retries_count=1
    )
    c2_facts = [
        C2AssertionFact(
            assertion_id="state_order_created",
            value=C2FactValue.TRUE,
            provenance="C2_DEMO_FIXTURE",
        )
    ]
    req = RecoveryEvaluationRequest(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        candidate_case=make_demonstration_candidate_case(),
        recovery_contract=make_demonstration_recovery_contract(),
        matched_evidence=evidence,
        c2_facts=c2_facts,
    )
    result = evaluate_recovery(req)

    assert result.evaluation_status == EvaluationStatus.EVALUATED
    assert result.recovery_verdict == RecoveryVerdict.PASS_COMPLETED
    assert result.first_violated_rule is None

    rule_map = {r.rule_id: r.status for r in result.rule_results}
    assert (
        rule_map[RecoveryRuleId.RULE_COMPLETION.value] == RuleEvaluationStatus.SATISFIED
    )
    assert rule_map[RecoveryRuleId.RULE_BUDGETS.value] == RuleEvaluationStatus.SATISFIED
    assert (
        rule_map[RecoveryRuleId.RULE_TRUTHFUL_COMPLETION.value]
        == RuleEvaluationStatus.SATISFIED
    )


def test_verdict_pass_graceful():
    """Caller stopped gracefully under explicitly permitted contract outcome -> PASS_GRACEFUL."""
    # Contract permits DEGRADED_COMPLETION
    contract = make_demonstration_recovery_contract().model_copy(
        update={
            "permitted_terminal_outcomes": [
                "DEGRADED_COMPLETION",
                "SUCCESS_CLEAN_RECOVERY",
            ]
        }
    )
    evidence = make_synthetic_matched_evidence(
        caller_outcome="DEGRADED_COMPLETION", retries_count=0, tool_calls_count=1
    )
    req = RecoveryEvaluationRequest(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        candidate_case=make_demonstration_candidate_case(),
        recovery_contract=contract,
        matched_evidence=evidence,
        c2_facts=[],
    )
    result = evaluate_recovery(req)

    assert result.evaluation_status == EvaluationStatus.EVALUATED
    assert result.recovery_verdict == RecoveryVerdict.PASS_GRACEFUL
    rule_map = {r.rule_id: r.status for r in result.rule_results}
    assert (
        rule_map[RecoveryRuleId.RULE_GRACEFUL_STOPPING.value]
        == RuleEvaluationStatus.SATISFIED
    )


def test_verdict_fail_on_budget_violation():
    """Proven retries budget violation yields FAIL."""
    # Retries = 5, but contract max_retries = 2
    evidence = make_synthetic_matched_evidence(
        caller_outcome="SUCCESS_AFTER_RETRY", retries_count=5
    )
    c2_facts = [
        C2AssertionFact(assertion_id="state_order_created", value=C2FactValue.TRUE)
    ]
    req = RecoveryEvaluationRequest(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        candidate_case=make_demonstration_candidate_case(),
        recovery_contract=make_demonstration_recovery_contract(),
        matched_evidence=evidence,
        c2_facts=c2_facts,
    )
    result = evaluate_recovery(req)

    assert result.evaluation_status == EvaluationStatus.EVALUATED
    assert result.recovery_verdict == RecoveryVerdict.FAIL
    assert result.first_violated_rule == RecoveryRuleId.RULE_BUDGETS.value


def test_verdict_fail_on_duplicate_side_effect():
    """Proven duplicate side effect yields FAIL."""
    evidence = make_synthetic_matched_evidence(caller_outcome="SUCCESS_AFTER_RETRY")
    c2_facts = [
        C2AssertionFact(assertion_id="state_order_created", value=C2FactValue.TRUE),
        C2AssertionFact(
            assertion_id="duplicate_side_effect_detected", value=C2FactValue.TRUE
        ),
    ]
    req = RecoveryEvaluationRequest(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        candidate_case=make_demonstration_candidate_case(),
        recovery_contract=make_demonstration_recovery_contract(),
        matched_evidence=evidence,
        c2_facts=c2_facts,
    )
    result = evaluate_recovery(req)

    assert result.evaluation_status == EvaluationStatus.EVALUATED
    assert result.recovery_verdict == RecoveryVerdict.FAIL
    assert result.first_violated_rule == RecoveryRuleId.RULE_DUPLICATE_EFFECTS.value


def test_verdict_fail_on_untruthful_completion():
    """Caller claimed SUCCESS, but C2 fact proves required state assertion is FALSE -> FAIL."""
    evidence = make_synthetic_matched_evidence(caller_outcome="SUCCESS_AFTER_RETRY")
    c2_facts = [
        C2AssertionFact(
            assertion_id="state_order_created",
            value=C2FactValue.FALSE,  # Proven false!
        )
    ]
    req = RecoveryEvaluationRequest(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        candidate_case=make_demonstration_candidate_case(),
        recovery_contract=make_demonstration_recovery_contract(),
        matched_evidence=evidence,
        c2_facts=c2_facts,
    )
    result = evaluate_recovery(req)

    assert result.evaluation_status == EvaluationStatus.EVALUATED
    assert result.recovery_verdict == RecoveryVerdict.FAIL
    assert result.first_violated_rule == RecoveryRuleId.RULE_COMPLETION.value


def test_verdict_inconclusive_on_missing_required_c2_facts():
    """Missing required state assertion facts with no proven violation -> INCONCLUSIVE."""
    evidence = make_synthetic_matched_evidence(caller_outcome="SUCCESS_AFTER_RETRY")
    # Empty c2_facts -> required 'state_order_created' is UNKNOWN
    req = RecoveryEvaluationRequest(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        candidate_case=make_demonstration_candidate_case(),
        recovery_contract=make_demonstration_recovery_contract(),
        matched_evidence=evidence,
        c2_facts=[],
    )
    result = evaluate_recovery(req)

    assert result.evaluation_status == EvaluationStatus.EVALUATED
    assert result.recovery_verdict == RecoveryVerdict.INCONCLUSIVE
    assert result.first_violated_rule is None


def test_verdict_inconclusive_on_uncertain_cleanup_settling():
    """Uncertain cleanup settling prevents unjustified pass -> INCONCLUSIVE."""
    evidence = make_synthetic_matched_evidence(
        caller_outcome="SUCCESS_AFTER_RETRY",
        cleanup_status=CleanupStatus.UNCERTAIN,
    )
    c2_facts = [
        C2AssertionFact(assertion_id="state_order_created", value=C2FactValue.TRUE)
    ]
    req = RecoveryEvaluationRequest(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        candidate_case=make_demonstration_candidate_case(),
        recovery_contract=make_demonstration_recovery_contract(),
        matched_evidence=evidence,
        c2_facts=c2_facts,
    )
    result = evaluate_recovery(req)

    assert result.evaluation_status == EvaluationStatus.EVALUATED
    assert result.recovery_verdict == RecoveryVerdict.INCONCLUSIVE


def test_missing_unrelated_facts_do_not_hide_proven_violation():
    """Missing unrelated facts do NOT prevent a proven budget or duplicate violation from yielding FAIL."""
    # Retries budget violated (retries=10), while state assertion fact is completely missing (UNKNOWN)
    evidence = make_synthetic_matched_evidence(
        caller_outcome="SUCCESS_AFTER_RETRY", retries_count=10
    )
    req = RecoveryEvaluationRequest(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        candidate_case=make_demonstration_candidate_case(),
        recovery_contract=make_demonstration_recovery_contract(),
        matched_evidence=evidence,
        c2_facts=[],  # missing state fact
    )
    result = evaluate_recovery(req)

    assert result.recovery_verdict == RecoveryVerdict.FAIL
    assert result.first_violated_rule == RecoveryRuleId.RULE_BUDGETS.value


# ---------------------------------------------------------------------------
# 3. C2 Facts Validation & Conflict Detection
# ---------------------------------------------------------------------------


def test_c2_facts_scope_conflict_detection():
    """Contradictory C2 facts (TRUE and FALSE) in identical scope are detected and reject evaluation."""
    facts = [
        C2AssertionFact(
            assertion_id="state_order_created",
            value=C2FactValue.TRUE,
            time_scope="post_recovery",
        ),
        C2AssertionFact(
            assertion_id="state_order_created",
            value=C2FactValue.FALSE,
            time_scope="post_recovery",
        ),
    ]
    is_valid, conflicts = validate_c2_facts(facts)
    assert is_valid is False
    assert len(conflicts) == 1
    assert "both TRUE and FALSE reported simultaneously" in conflicts[0]

    # Evaluator should reject evaluation
    evidence = make_synthetic_matched_evidence()
    req = RecoveryEvaluationRequest(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        candidate_case=make_demonstration_candidate_case(),
        recovery_contract=make_demonstration_recovery_contract(),
        matched_evidence=evidence,
        c2_facts=facts,
    )
    result = evaluate_recovery(req)
    assert result.evaluation_status == EvaluationStatus.NOT_EVALUATED
    assert result.recovery_verdict is None


def test_c2_facts_time_evolution_not_conflicting():
    """Facts changing from FALSE to TRUE across different time scopes are valid."""
    facts = [
        C2AssertionFact(
            assertion_id="state_order_created",
            value=C2FactValue.FALSE,
            time_scope="initial_state",
        ),
        C2AssertionFact(
            assertion_id="state_order_created",
            value=C2FactValue.TRUE,
            time_scope="post_recovery",
        ),
    ]
    is_valid, conflicts = validate_c2_facts(facts)
    assert is_valid is True
    assert len(conflicts) == 0

    val = get_c2_fact_value(facts, "state_order_created", time_scope="post_recovery")
    assert val == C2FactValue.TRUE


def test_c2_integration_status_reports_blocked():
    """check_c2_integration_status reports that live C2 service is blocked."""
    is_avail, msg = check_c2_integration_status()
    assert is_avail is False
    assert "BLOCKED" in msg


# ---------------------------------------------------------------------------
# 4. Phase 3 Gap Corrections & Regressions
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_gap_a_cancellation_near_boundary_never_manufactures_timeout():
    """Gap A: External cancellation near or at boundary never manufactures caller_observed_timeout."""
    trial_id = "test-gap-a-regr"
    plan = InterceptionPlan(
        trial_id=trial_id,
        target_tool_id="demonstration_order_placement",
        target_occurrence=1,
        interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
        effect_phase=EffectPhase.BEFORE_EFFECT,
        fault_family=FaultFamily.TIMEOUT_DISCONNECTION,
        fault_mode=TimeoutDisconnectionMode.CALLER_TIMEOUT_EXCEEDED,
        caller_timeout_ms=50,  # 50ms boundary
    )
    interceptor = DomainToolInterceptor(trial_id=trial_id, plan=plan)

    task = asyncio.create_task(
        interceptor.intercept_call(
            tool_id="demonstration_order_placement",
            tool_version="1.0.0",
            arguments={"quantity": 1},
            forward_callback=lambda: None,
        )
    )
    # Cancel at ~48ms (96% of boundary, previously caught by 90% threshold)
    await asyncio.sleep(0.048)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(interceptor.episode_records) == 1
    ep = interceptor.episode_records[0]
    # Under Phase 4 correction, caller_observed_timeout MUST be False!
    assert ep.caller_observed_timeout is False
    assert "CANCELLATION" in ep.cancellation_reason


@pytest.mark.anyio
async def test_gap_b_after_commit_contradictory_event_ordering_rejected():
    """Gap B: Contradictory event sequence in AFTER_COMMIT prevents confirmed exposure."""
    fixture_mgr = DemonstrationFixtureManager()
    adapter = DemonstrationToolAdapter(fixture_manager=fixture_mgr)
    runner = HarnessRunner(adapter=adapter, fixture_manager=fixture_mgr)

    case = make_demonstration_candidate_case().model_copy(
        update={
            "effect_phase": EffectPhase.AFTER_COMMIT,
            "interception_hook": InterceptionHook.APPLICATION_AWARE_HOOK,
            "required_observations": ["committed_order_verified"],
        }
    )
    contract = make_demonstration_recovery_contract().model_copy(
        update={"allow_retry_on_unverified_commit": True}
    )

    evidence = await runner.run_matched_pair(
        candidate_case=case,
        adapter_manifest=adapter.get_manifest(),
        task_fixture_metadata=make_demonstration_task_fixture_metadata(),
        recovery_contract=contract,
        target_mode=TargetMode.DEMONSTRATION,
    )
    assert evidence.exposure_status == ExposureStatus.CONFIRMED

    # Artificially corrupt the event sequence order (withholding before commit observation)
    corrupted_events = list(evidence.fault_trial.events)
    # Swap events
    if len(corrupted_events) >= 3:
        corrupted_events[1], corrupted_events[2] = (
            corrupted_events[2],
            corrupted_events[1],
        )
        corrupted_fault = evidence.fault_trial.model_copy(
            update={"events": corrupted_events}
        )
        plan = InterceptionPlan(
            trial_id="test",
            target_tool_id=case.tool_id,
            target_occurrence=1,
            interception_hook=case.interception_hook,
            effect_phase=case.effect_phase,
            fault_family=case.fault_family,
            fault_mode=case.payload.mode,
            caller_timeout_ms=case.caller_timeout_ms,
        )
        status, reasons = runner._evaluate_exposure(corrupted_fault, plan)
        assert status == ExposureStatus.EXPOSURE_UNKNOWN
        assert any("Contradictory event order" in r for r in reasons)


@pytest.mark.anyio
async def test_gap_d_suite_runner_consumes_frozen_artifact_file():
    """Gap D: Suite runner loads generated frozen suite JSON file and executes cases without mutation."""
    # Generate suite artifact
    gen_req = build_demonstration_generation_request()
    gen_resp = generate_feasible_cases(gen_req)
    assert gen_resp.frozen_suite is not None
    suite = gen_resp.frozen_suite

    with tempfile.TemporaryDirectory() as tmpdir:
        suite_file = Path(tmpdir) / "frozen_suite.json"
        with open(suite_file, "w", encoding="utf-8") as f:  # noqa: ASYNC230
            f.write(suite.model_dump_json(indent=2))

        # Run CLI with --synthetic --suite-file
        exit_code = await run_suite_cli(
            ["--synthetic", "--suite-file", str(suite_file), "--export-dir", tmpdir]
        )
        assert exit_code == 0


# ---------------------------------------------------------------------------
# 5. Stateless API & Offline CLI Verification
# ---------------------------------------------------------------------------


def test_api_evaluate_endpoint_happy_path():
    """POST /api/v1/c3/recovery/evaluate returns HTTP 200 with PASS_COMPLETED."""
    evidence = make_synthetic_matched_evidence(caller_outcome="SUCCESS_AFTER_RETRY")
    c2_facts = [
        {
            "assertion_id": "state_order_created",
            "value": "TRUE",
            "provenance": "C2_DEMO_FIXTURE",
        }
    ]
    payload = {
        "project_id": "proj-qa-001",
        "case_id": "case-c3-demo-001",
        "evaluator_version": "1.0.0",
        "rule_set_version": "1.0.0",
        "candidate_case": make_demonstration_candidate_case().model_dump(mode="json"),
        "recovery_contract": make_demonstration_recovery_contract().model_dump(
            mode="json"
        ),
        "matched_evidence": evidence.model_dump(mode="json"),
        "c2_facts": c2_facts,
    }

    resp = client.post("/api/v1/c3/recovery/evaluate", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["evaluation_status"] == "EVALUATED"
    assert data["recovery_verdict"] == "PASS_COMPLETED"
    assert len(data["rule_results"]) == 6
    assert data["first_violated_rule"] is None


def test_api_evaluate_endpoint_structural_validation_error():
    """POST /api/v1/c3/recovery/evaluate returns HTTP 422 on malformed body."""
    resp = client.post("/api/v1/c3/recovery/evaluate", json={"bad_field": 123})
    assert resp.status_code == 422
    data = resp.json()
    assert "detail" in data


def test_api_and_cli_evaluation_parity():
    """Offline evaluate CLI and API produce exact identical evaluation verdicts."""
    evidence = make_synthetic_matched_evidence(caller_outcome="SUCCESS_AFTER_RETRY")

    with tempfile.TemporaryDirectory() as tmpdir:
        ev_file = Path(tmpdir) / "evidence.json"
        with open(ev_file, "w", encoding="utf-8") as f:
            f.write(evidence.model_dump_json(indent=2))

        # Run CLI with --synthetic-facts
        exit_code = run_evaluation_cli(
            [
                "--evidence-file",
                str(ev_file),
                "--synthetic-facts",
                "--export-dir",
                tmpdir,
            ]
        )
        assert exit_code == 0

        # Find exported eval artifact
        eval_files = list(Path(tmpdir).glob("eval_*.json"))
        assert len(eval_files) == 1
        with open(eval_files[0], encoding="utf-8") as f:
            cli_res = json.load(f)

    # Now run API with exact same inputs
    c2_facts = [
        {
            "assertion_id": "state_order_created",
            "value": "TRUE",
            "provenance": "C2_DEMO_FIXTURE",
        }
    ]
    payload = {
        "project_id": evidence.project_id,
        "case_id": evidence.case_id,
        "candidate_case": make_demonstration_candidate_case().model_dump(mode="json"),
        "recovery_contract": make_demonstration_recovery_contract().model_dump(
            mode="json"
        ),
        "matched_evidence": evidence.model_dump(mode="json"),
        "c2_facts": c2_facts,
    }
    api_resp = client.post("/api/v1/c3/recovery/evaluate", json=payload)
    assert api_resp.status_code == 200
    api_res = api_resp.json()

    assert (
        cli_res["recovery_verdict"] == api_res["recovery_verdict"] == "PASS_COMPLETED"
    )
    assert cli_res["evaluation_status"] == api_res["evaluation_status"] == "EVALUATED"


def test_static_endpoints_preserve_null_recovery_verdict():
    from app.components.c3_robustness_recovery.contracts.schemas import (
        FaultValidationRequest,
    )

    val_req = FaultValidationRequest(
        candidate_case=make_demonstration_candidate_case(),
        adapter_manifest=DemonstrationToolAdapter(
            fixture_manager=DemonstrationFixtureManager()
        ).get_manifest(),
        task_fixture_metadata=make_demonstration_task_fixture_metadata(),
        recovery_contract=make_demonstration_recovery_contract(),
    )
    val_resp = client.post(
        "/api/v1/c3/cases/validate", json=val_req.model_dump(mode="json")
    )
    assert val_resp.status_code == 200
    assert val_resp.json()["recovery_verdict"] is None

    gen_req = build_demonstration_generation_request()
    gen_resp = client.post(
        "/api/v1/c3/cases/generate", json=gen_req.model_dump(mode="json")
    )
    assert gen_resp.status_code == 200
    assert gen_resp.json()["recovery_verdict"] is None


# ---------------------------------------------------------------------------
# 6. Confirmed Phase 4 Audit Defect Regression Tests
# ---------------------------------------------------------------------------


def test_audit_graceful_stopping_permitted_outcome_without_completion_assertions():
    """A permitted graceful stop branch does not fail solely because completion state was not satisfied."""
    contract = make_demonstration_recovery_contract().model_copy(
        update={
            "permitted_terminal_outcomes": ["ABORT_SAFE"],
            "required_state_assertions": ["state_order_created"],
        }
    )
    # Caller safely aborted; task completion state was NOT created
    evidence = make_synthetic_matched_evidence(
        caller_outcome="ABORT_SAFE", retries_count=0, tool_calls_count=1
    )
    req = RecoveryEvaluationRequest(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        candidate_case=make_demonstration_candidate_case(),
        recovery_contract=contract,
        matched_evidence=evidence,
        c2_facts=[],  # No completion facts
    )
    result = evaluate_recovery(req)

    assert result.evaluation_status == EvaluationStatus.EVALUATED
    assert result.recovery_verdict == RecoveryVerdict.PASS_GRACEFUL
    rule_map = {r.rule_id: r for r in result.rule_results}
    assert (
        rule_map[RecoveryRuleId.RULE_COMPLETION.value].status
        == RuleEvaluationStatus.NOT_APPLICABLE
    )
    assert (
        rule_map[RecoveryRuleId.RULE_GRACEFUL_STOPPING.value].status
        == RuleEvaluationStatus.SATISFIED
    )


def test_audit_ordinary_incomplete_task_not_automatically_graceful():
    """Ordinary incomplete task is not automatically graceful stopping."""
    contract = make_demonstration_recovery_contract().model_copy(
        update={"permitted_terminal_outcomes": ["ABORT_SAFE", "SUCCESS_CLEAN_RECOVERY"]}
    )
    evidence = make_synthetic_matched_evidence(
        caller_outcome="INCOMPLETE", retries_count=0, tool_calls_count=1
    )
    req = RecoveryEvaluationRequest(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        candidate_case=make_demonstration_candidate_case(),
        recovery_contract=contract,
        matched_evidence=evidence,
        c2_facts=[],
    )
    result = evaluate_recovery(req)

    assert result.evaluation_status == EvaluationStatus.EVALUATED
    assert result.recovery_verdict == RecoveryVerdict.FAIL
    rule_map = {r.rule_id: r for r in result.rule_results}
    assert (
        rule_map[RecoveryRuleId.RULE_GRACEFUL_STOPPING.value].status
        == RuleEvaluationStatus.VIOLATED
    )
    assert (
        rule_map[RecoveryRuleId.RULE_GRACEFUL_STOPPING.value].reason_code
        == "UNPERMITTED_STOPPING_OUTCOME"
    )


def test_audit_harness_cancellation_never_graceful():
    """Harness cancellation never establishes graceful stopping."""
    contract = make_demonstration_recovery_contract().model_copy(
        update={"permitted_terminal_outcomes": ["ABORT_SAFE", "SUCCESS_CLEAN_RECOVERY"]}
    )
    # Caller had CANCELLED status
    evidence = make_synthetic_matched_evidence(
        caller_outcome="CANCELLED_BY_HARNESS", retries_count=0
    )
    req = RecoveryEvaluationRequest(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        candidate_case=make_demonstration_candidate_case(),
        recovery_contract=contract,
        matched_evidence=evidence,
        c2_facts=[],
    )
    result = evaluate_recovery(req)

    assert result.recovery_verdict == RecoveryVerdict.FAIL
    rule_map = {r.rule_id: r for r in result.rule_results}
    assert (
        rule_map[RecoveryRuleId.RULE_GRACEFUL_STOPPING.value].status
        == RuleEvaluationStatus.VIOLATED
    )
    assert (
        rule_map[RecoveryRuleId.RULE_GRACEFUL_STOPPING.value].reason_code
        == "HARNESS_CANCELLATION_NOT_GRACEFUL"
    )


def test_audit_distinct_effects_across_workflow_not_duplicates():
    """Multiple distinct effects across legitimate workflow are not automatically duplicates."""
    evidence = make_synthetic_matched_evidence(
        caller_outcome="SUCCESS_AFTER_RETRY",
        observed_effects=["cart_item_added", "order_placed"],
    )
    c2_facts = [
        C2AssertionFact(assertion_id="state_order_created", value=C2FactValue.TRUE)
    ]
    req = RecoveryEvaluationRequest(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        candidate_case=make_demonstration_candidate_case(),
        recovery_contract=make_demonstration_recovery_contract(),
        matched_evidence=evidence,
        c2_facts=c2_facts,
    )
    result = evaluate_recovery(req)

    assert result.evaluation_status == EvaluationStatus.EVALUATED
    rule_map = {r.rule_id: r for r in result.rule_results}
    assert (
        rule_map[RecoveryRuleId.RULE_DUPLICATE_EFFECTS.value].status
        == RuleEvaluationStatus.SATISFIED
    )


def test_audit_repeated_observations_of_one_effect_not_duplicates():
    """Repeated observations of one effect are not counted as duplicates."""
    evidence = make_synthetic_matched_evidence(
        caller_outcome="SUCCESS_AFTER_RETRY",
        observed_effects=["order_placed", "order_placed"],  # repeated observation
    )
    c2_facts = [
        C2AssertionFact(assertion_id="state_order_created", value=C2FactValue.TRUE)
    ]
    req = RecoveryEvaluationRequest(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        candidate_case=make_demonstration_candidate_case(),
        recovery_contract=make_demonstration_recovery_contract(),
        matched_evidence=evidence,
        c2_facts=c2_facts,
    )
    result = evaluate_recovery(req)

    rule_map = {r.rule_id: r for r in result.rule_results}
    assert (
        rule_map[RecoveryRuleId.RULE_DUPLICATE_EFFECTS.value].status
        == RuleEvaluationStatus.SATISFIED
    )


def test_audit_retry_safety_idempotency_key_alone_unverified_target():
    """Idempotency key reuse without verified target enforcement yields UNKNOWN in AFTER_COMMIT."""
    contract = make_demonstration_recovery_contract().model_copy(
        update={"allow_retry_on_unverified_commit": False}
    )
    case = make_demonstration_candidate_case().model_copy(
        update={"effect_phase": EffectPhase.AFTER_COMMIT}
    )
    evidence = make_synthetic_matched_evidence(
        caller_outcome="SUCCESS_AFTER_RETRY", retries_count=1
    )
    # Only idempotency_key_reused = TRUE, without target_idempotency_enforced or duplicate_side_effect_detected
    c2_facts = [
        C2AssertionFact(assertion_id="state_order_created", value=C2FactValue.TRUE),
        C2AssertionFact(assertion_id="idempotency_key_reused", value=C2FactValue.TRUE),
    ]
    req = RecoveryEvaluationRequest(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        candidate_case=case,
        recovery_contract=contract,
        matched_evidence=evidence,
        c2_facts=c2_facts,
    )
    result = evaluate_recovery(req)

    assert result.recovery_verdict == RecoveryVerdict.INCONCLUSIVE
    rule_map = {r.rule_id: r for r in result.rule_results}
    assert (
        rule_map[RecoveryRuleId.RULE_UNSAFE_RETRIES.value].status
        == RuleEvaluationStatus.UNKNOWN
    )
    assert (
        rule_map[RecoveryRuleId.RULE_UNSAFE_RETRIES.value].reason_code
        == "UNVERIFIED_TARGET_IDEMPOTENCY_ENFORCEMENT"
    )


def test_audit_retry_safety_target_enforcement_verified():
    """Idempotency key reuse with verified target enforcement yields SATISFIED."""
    contract = make_demonstration_recovery_contract().model_copy(
        update={"allow_retry_on_unverified_commit": False}
    )
    case = make_demonstration_candidate_case().model_copy(
        update={"effect_phase": EffectPhase.AFTER_COMMIT}
    )
    evidence = make_synthetic_matched_evidence(
        caller_outcome="SUCCESS_AFTER_RETRY", retries_count=1
    )
    c2_facts = [
        C2AssertionFact(assertion_id="state_order_created", value=C2FactValue.TRUE),
        C2AssertionFact(assertion_id="idempotency_key_reused", value=C2FactValue.TRUE),
        C2AssertionFact(
            assertion_id="target_idempotency_enforced", value=C2FactValue.TRUE
        ),
        C2AssertionFact(
            assertion_id="duplicate_side_effect_detected", value=C2FactValue.FALSE
        ),
    ]
    req = RecoveryEvaluationRequest(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        candidate_case=case,
        recovery_contract=contract,
        matched_evidence=evidence,
        c2_facts=c2_facts,
    )
    result = evaluate_recovery(req)

    assert result.recovery_verdict == RecoveryVerdict.PASS_COMPLETED
    rule_map = {r.rule_id: r for r in result.rule_results}
    assert (
        rule_map[RecoveryRuleId.RULE_UNSAFE_RETRIES.value].status
        == RuleEvaluationStatus.SATISFIED
    )


def test_audit_fact_scoping_conflicts_prevent_unjustified_passes():
    """Matching facts with conflicting values in same scope return UNKNOWN to prevent unjustified pass."""
    facts = [
        C2AssertionFact(
            assertion_id="state_order_created",
            assertion_version="1.0.0",
            value=C2FactValue.TRUE,
            time_scope="post_recovery",
        ),
        C2AssertionFact(
            assertion_id="state_order_created",
            assertion_version="2.0.0",
            value=C2FactValue.FALSE,
            time_scope="post_recovery",
        ),
    ]
    val = get_c2_fact_value(facts, "state_order_created", time_scope="post_recovery")
    assert val == C2FactValue.UNKNOWN


def test_audit_causal_ordering_selects_earliest_observable_violation():
    """Causal ordering selects the budget violation that occurred during execution before completion."""
    evidence = make_synthetic_matched_evidence(
        caller_outcome="SUCCESS_AFTER_RETRY",
        retries_count=5,  # Exceeded budget (max 1)
    )
    c2_facts = [
        C2AssertionFact(
            assertion_id="state_order_created",
            value=C2FactValue.FALSE,  # Also false completion
        )
    ]
    req = RecoveryEvaluationRequest(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        candidate_case=make_demonstration_candidate_case(),
        recovery_contract=make_demonstration_recovery_contract(),
        matched_evidence=evidence,
        c2_facts=c2_facts,
    )
    result = evaluate_recovery(req)

    assert result.recovery_verdict == RecoveryVerdict.FAIL
    # Budget violation happened during execution, prior to terminal completion check
    assert result.first_violated_rule == RecoveryRuleId.RULE_BUDGETS.value


def test_audit_incomplete_traces_prevent_budget_satisfaction():
    """Incomplete trace prevents verifying total budget -> UNKNOWN."""
    evidence = make_synthetic_matched_evidence(caller_outcome="SUCCESS_AFTER_RETRY")
    evidence.fault_trial.evidence_complete = False
    c2_facts = [
        C2AssertionFact(assertion_id="state_order_created", value=C2FactValue.TRUE)
    ]
    req = RecoveryEvaluationRequest(
        project_id="proj-qa-001",
        case_id="case-c3-demo-001",
        candidate_case=make_demonstration_candidate_case(),
        recovery_contract=make_demonstration_recovery_contract(),
        matched_evidence=evidence,
        c2_facts=c2_facts,
    )
    result = evaluate_recovery(req)

    rule_map = {r.rule_id: r for r in result.rule_results}
    assert (
        rule_map[RecoveryRuleId.RULE_BUDGETS.value].status
        == RuleEvaluationStatus.UNKNOWN
    )
    assert (
        rule_map[RecoveryRuleId.RULE_BUDGETS.value].reason_code
        == "INCOMPLETE_BUDGET_EVIDENCE"
    )
    assert result.recovery_verdict == RecoveryVerdict.INCONCLUSIVE
