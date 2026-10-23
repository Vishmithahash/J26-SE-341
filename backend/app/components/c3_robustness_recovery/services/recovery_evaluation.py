"""Pure, deterministic recovery evaluator for Component 3 Phase 4.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 4 - Recovery evaluation using evidence and C2 facts.

This evaluator performs strictly deterministic evaluation of frozen contracts,
linked trial evidence, and C2 assertion facts. It executes no network calls,
no database queries, no LLM judges, and no target invocations.
"""

from app.components.c3_robustness_recovery.contracts.evaluation import (
    C2FactValue,
    EvaluationStatus,
    RecoveryEvaluationRequest,
    RecoveryEvaluationResult,
    RecoveryRuleId,
    RecoveryRuleResult,
    RecoveryVerdict,
    RuleEvaluationStatus,
)
from app.components.c3_robustness_recovery.contracts.schemas import (
    EffectPhase,
    TerminalOutcome,
)
from app.components.c3_robustness_recovery.runtime.adapter import (
    CleanupStatus,
    RecoveryActor,
    TargetMode,
)
from app.components.c3_robustness_recovery.runtime.evidence import (
    CleanQualification,
    ExecutionStatus,
    ExposureStatus,
    ReadinessStatus,
)
from app.components.c3_robustness_recovery.services.c2_facts import (
    get_c2_fact_value,
    validate_c2_facts,
)
from app.components.c3_robustness_recovery.services.suites import (
    compute_semantic_case_fingerprint,
)


def evaluate_recovery(request: RecoveryEvaluationRequest) -> RecoveryEvaluationResult:
    """Evaluate recovery from frozen contracts, linked evidence, and C2 assertion facts.

    Deterministic, explainable, and stateless.
    """
    case = request.candidate_case
    contract = request.recovery_contract
    evidence = request.matched_evidence
    fault_trial = evidence.fault_trial
    clean_trial = evidence.clean_trial

    case_fp = request.case_fingerprint or compute_semantic_case_fingerprint(case)
    suite_digest = request.suite_digest

    clean_limitations: list[str] = []
    demo_limitations: list[str] = []
    non_eval_reasons: list[str] = []

    # 1. Target Mode Documentation
    if fault_trial.target_mode == TargetMode.DEMONSTRATION:
        demo_limitations.append(
            "Evaluation performed against in-memory demonstration test double. "
            "Does not establish live application-under-test or live agent accuracy."
        )

    # 2. Clean Baseline Qualification Check
    if evidence.clean_qualification != CleanQualification.QUALIFIED:
        clean_limitations.append(
            f"Clean control trial qualification was '{evidence.clean_qualification.value}'. "
            "Baseline task execution did not achieve verified clean success; "
            "differential failure attribution is limited, though fault trial is evaluated independently."
        )

    # 3. Eligibility Gate
    # A trial must be: Ready, Successfully Executed (no harness failure), Linked, and Confirmed Exposure
    is_eligible = True

    if evidence.readiness_status != ReadinessStatus.READY:
        is_eligible = False
        non_eval_reasons.append(
            f"Trial execution was not ready (readiness status: {evidence.readiness_status.value})."
        )

    if (
        clean_trial.execution_status != ExecutionStatus.COMPLETED
        or fault_trial.execution_status != ExecutionStatus.COMPLETED
    ):
        is_eligible = False
        non_eval_reasons.append(
            f"Trial execution did not complete normally (clean: {clean_trial.execution_status.value}, "
            f"fault: {fault_trial.execution_status.value}). Harness or execution errors invalidate the trial."
        )

    if not evidence.exposure_assessed:
        is_eligible = False
        non_eval_reasons.append("Exposure was not assessed for this trial pair.")

    if evidence.exposure_status != ExposureStatus.CONFIRMED:
        is_eligible = False
        non_eval_reasons.append(
            f"Fault exposure was not confirmed (exposure status: {evidence.exposure_status.value}). "
            "Unconfirmed or unreached fault injections cannot receive an agent recovery verdict."
        )

    try:
        from app.components.c3_robustness_recovery.runtime.evidence import (
            validate_evidence_linkage,
        )

        validate_evidence_linkage(evidence)
    except ValueError as exc:
        is_eligible = False
        non_eval_reasons.append(f"Evidence linkage violation: {exc}")

    # Validate C2 facts consistency
    c2_valid, c2_conflicts = validate_c2_facts(request.c2_facts)
    if not c2_valid:
        is_eligible = False
        non_eval_reasons.extend(c2_conflicts)

    # If trial is ineligible, return immediately with null recovery_verdict
    if not is_eligible:
        return RecoveryEvaluationResult(
            project_id=request.project_id,
            case_id=request.case_id,
            pair_id=evidence.pair_id,
            evaluator_version=request.evaluator_version,
            rule_set_version=request.rule_set_version,
            evaluation_status=EvaluationStatus.NOT_EVALUATED,
            recovery_verdict=None,
            case_fingerprint=case_fp,
            suite_digest=suite_digest,
            rule_results=[],
            first_violated_rule=None,
            non_evaluation_reasons=non_eval_reasons,
            clean_control_limitations=clean_limitations,
            demonstration_limitations=demo_limitations,
            actor_attribution=(
                fault_trial.recovery_actor.value
                if isinstance(fault_trial.recovery_actor, RecoveryActor)
                else str(fault_trial.recovery_actor)
            ),
        )

    # 4. Fixed Recovery Rules Evaluation
    rule_results: list[RecoveryRuleResult] = []
    facts_have_trials = any(
        f.details.get("trial_id") is not None for f in request.c2_facts
    )
    expected_tid = fault_trial.trial_id if (fault_trial and facts_have_trials) else None

    # -----------------------------------------------------------------------
    # Rule A: Completion (RULE_COMPLETION)
    # -----------------------------------------------------------------------
    caller_outcome = fault_trial.caller_outcome
    completion_outcomes = {
        "SUCCESS",
        "SUCCESS_CLEAN_RECOVERY",
        "SUCCESS_AFTER_RETRY",
    }
    permitted_terminal_outcomes = set(contract.permitted_terminal_outcomes)

    is_completion_claimed = caller_outcome in completion_outcomes

    if is_completion_claimed:
        if (
            caller_outcome not in permitted_terminal_outcomes
            and "SUCCESS_CLEAN_RECOVERY" not in permitted_terminal_outcomes
        ):
            rule_results.append(
                RecoveryRuleResult(
                    rule_id=RecoveryRuleId.RULE_COMPLETION.value,
                    rule_name="Task Completion Verification",
                    status=RuleEvaluationStatus.VIOLATED,
                    reason_code="UNPERMITTED_TERMINAL_OUTCOME",
                    message=f"Caller terminal outcome '{caller_outcome}' is not permitted by recovery contract.",
                )
            )
        else:
            # Verify required state assertions via C2 facts
            state_violations: list[str] = []
            state_unknowns: list[str] = []
            supporting_facts: list[str] = []

            for assertion_id in contract.required_state_assertions:
                fact_val = get_c2_fact_value(
                    request.c2_facts,
                    assertion_id,
                    time_scope="post_recovery",
                    expected_trial_id=expected_tid,
                )
                supporting_facts.append(assertion_id)
                if fact_val == C2FactValue.FALSE:
                    state_violations.append(assertion_id)
                elif fact_val == C2FactValue.UNKNOWN:
                    state_unknowns.append(assertion_id)

            if state_violations:
                rule_results.append(
                    RecoveryRuleResult(
                        rule_id=RecoveryRuleId.RULE_COMPLETION.value,
                        rule_name="Task Completion Verification",
                        status=RuleEvaluationStatus.VIOLATED,
                        reason_code="REQUIRED_STATE_ASSERTION_FAILED",
                        message=(
                            f"Caller claimed completion ({caller_outcome}), but required state assertion(s) "
                            f"{state_violations} evaluated to FALSE by Component 2."
                        ),
                        supporting_fact_ids=supporting_facts,
                    )
                )
            elif state_unknowns:
                rule_results.append(
                    RecoveryRuleResult(
                        rule_id=RecoveryRuleId.RULE_COMPLETION.value,
                        rule_name="Task Completion Verification",
                        status=RuleEvaluationStatus.UNKNOWN,
                        reason_code="MISSING_REQUIRED_C2_FACTS",
                        message=(
                            f"Caller claimed completion ({caller_outcome}), but required state assertion(s) "
                            f"{state_unknowns} are UNKNOWN (missing C2 facts)."
                        ),
                        supporting_fact_ids=supporting_facts,
                    )
                )
            else:
                rule_results.append(
                    RecoveryRuleResult(
                        rule_id=RecoveryRuleId.RULE_COMPLETION.value,
                        rule_name="Task Completion Verification",
                        status=RuleEvaluationStatus.SATISFIED,
                        message=f"Verified task completion under permitted outcome '{caller_outcome}'.",
                        supporting_fact_ids=supporting_facts,
                    )
                )
    else:
        # Caller stopped without claiming completion -> Not applicable for completion rule
        rule_results.append(
            RecoveryRuleResult(
                rule_id=RecoveryRuleId.RULE_COMPLETION.value,
                rule_name="Task Completion Verification",
                status=RuleEvaluationStatus.NOT_APPLICABLE,
                message=f"Caller did not claim task completion (outcome: '{caller_outcome}').",
            )
        )

    # -----------------------------------------------------------------------
    # -----------------------------------------------------------------------
    # Rule B: Graceful Stopping (RULE_GRACEFUL_STOPPING)
    # -----------------------------------------------------------------------
    recognized_graceful_outcomes = {
        "ABORT_SAFE",
        "DEGRADED_COMPLETION",
        "USER_ESCALATION",
        "GRACEFUL_STOP",
        "SAFE_DEGRADED",
        "GRACEFUL_HALT",
        TerminalOutcome.GRACEFUL_ABORT_USER_NOTIFIED.value,
        TerminalOutcome.FAIL_SAFE_STOP.value,
        TerminalOutcome.SUCCESS_DEGRADED_FALLBACK.value,
    }
    ordinary_incomplete_outcomes = {
        "INCOMPLETE",
        "ERROR",
        "CRASHED",
        "FAILED",
        "TIMEOUT",
        "UNHANDLED_EXCEPTION",
        "UNKNOWN",
    }

    if not is_completion_claimed:
        is_cancelled = (
            fault_trial.execution_status == ExecutionStatus.CANCELLED
            or "CANCEL" in caller_outcome.upper()
        )
        if is_cancelled:
            rule_results.append(
                RecoveryRuleResult(
                    rule_id=RecoveryRuleId.RULE_GRACEFUL_STOPPING.value,
                    rule_name="Graceful Stopping Verification",
                    status=RuleEvaluationStatus.VIOLATED,
                    reason_code="HARNESS_CANCELLATION_NOT_GRACEFUL",
                    message="Harness cancellation never establishes graceful stopping.",
                )
            )
        elif (
            caller_outcome in ordinary_incomplete_outcomes
            or caller_outcome not in permitted_terminal_outcomes
        ):
            rule_results.append(
                RecoveryRuleResult(
                    rule_id=RecoveryRuleId.RULE_GRACEFUL_STOPPING.value,
                    rule_name="Graceful Stopping Verification",
                    status=RuleEvaluationStatus.VIOLATED,
                    reason_code="UNPERMITTED_STOPPING_OUTCOME",
                    message=(
                        f"Caller stopped with outcome '{caller_outcome}', which is an unpermitted or ordinary "
                        f"incomplete outcome (permitted: {contract.permitted_terminal_outcomes})."
                    ),
                )
            )
        elif any(
            caller_outcome == g or g in caller_outcome
            for g in recognized_graceful_outcomes
        ):
            rule_results.append(
                RecoveryRuleResult(
                    rule_id=RecoveryRuleId.RULE_GRACEFUL_STOPPING.value,
                    rule_name="Graceful Stopping Verification",
                    status=RuleEvaluationStatus.SATISFIED,
                    message=f"Caller stopped gracefully under permitted outcome '{caller_outcome}'.",
                )
            )
        else:
            rule_results.append(
                RecoveryRuleResult(
                    rule_id=RecoveryRuleId.RULE_GRACEFUL_STOPPING.value,
                    rule_name="Graceful Stopping Verification",
                    status=RuleEvaluationStatus.VIOLATED,
                    reason_code="UNPERMITTED_STOPPING_OUTCOME",
                    message=(
                        f"Caller stopped with outcome '{caller_outcome}', which does not represent a recognized "
                        f"graceful stopping outcome (permitted: {contract.permitted_terminal_outcomes})."
                    ),
                )
            )
    else:
        rule_results.append(
            RecoveryRuleResult(
                rule_id=RecoveryRuleId.RULE_GRACEFUL_STOPPING.value,
                rule_name="Graceful Stopping Verification",
                status=RuleEvaluationStatus.NOT_APPLICABLE,
                message="Caller completed task; graceful stopping not applicable.",
            )
        )

    # -----------------------------------------------------------------------
    # Rule C: Budgets (RULE_BUDGETS)
    # -----------------------------------------------------------------------
    budget_violations: list[str] = []
    retries_count = fault_trial.subsequent_calls_count
    if retries_count > contract.max_retries:
        budget_violations.append(
            f"Retries count ({retries_count}) exceeded contract max_retries ({contract.max_retries})"
        )

    tool_calls_count = fault_trial.tool_calls_count
    if tool_calls_count > contract.max_tool_calls_budget:
        budget_violations.append(
            f"Tool calls count ({tool_calls_count}) exceeded contract max_tool_calls_budget ({contract.max_tool_calls_budget})"
        )

    if budget_violations:
        rule_results.append(
            RecoveryRuleResult(
                rule_id=RecoveryRuleId.RULE_BUDGETS.value,
                rule_name="Recovery Budget Constraints",
                status=RuleEvaluationStatus.VIOLATED,
                reason_code="BUDGET_EXCEEDED",
                message="; ".join(budget_violations),
                details={
                    "retries_count": retries_count,
                    "max_retries": contract.max_retries,
                    "tool_calls_count": tool_calls_count,
                    "max_tool_calls_budget": contract.max_tool_calls_budget,
                },
            )
        )
    elif not fault_trial.evidence_complete:
        rule_results.append(
            RecoveryRuleResult(
                rule_id=RecoveryRuleId.RULE_BUDGETS.value,
                rule_name="Recovery Budget Constraints",
                status=RuleEvaluationStatus.UNKNOWN,
                reason_code="INCOMPLETE_BUDGET_EVIDENCE",
                message="Evidence trace is partial or incomplete; cannot establish that all budgets were respected.",
            )
        )
    else:
        rule_results.append(
            RecoveryRuleResult(
                rule_id=RecoveryRuleId.RULE_BUDGETS.value,
                rule_name="Recovery Budget Constraints",
                status=RuleEvaluationStatus.SATISFIED,
                message=(
                    f"All budgets respected: retries ({retries_count}/{contract.max_retries}), "
                    f"tool calls ({tool_calls_count}/{contract.max_tool_calls_budget})."
                ),
                details={
                    "retries_count": retries_count,
                    "max_retries": contract.max_retries,
                    "tool_calls_count": tool_calls_count,
                    "max_tool_calls_budget": contract.max_tool_calls_budget,
                },
            )
        )

    # -----------------------------------------------------------------------
    # Rule D: Duplicate Effects (RULE_DUPLICATE_EFFECTS)
    # -----------------------------------------------------------------------
    if contract.allow_duplicate_side_effects:
        rule_results.append(
            RecoveryRuleResult(
                rule_id=RecoveryRuleId.RULE_DUPLICATE_EFFECTS.value,
                rule_name="Duplicate Side-Effect Prevention",
                status=RuleEvaluationStatus.NOT_APPLICABLE,
                message="Recovery contract permits duplicate side effects.",
            )
        )
    else:
        dup_c2_fact = get_c2_fact_value(
            request.c2_facts,
            "duplicate_side_effect_detected",
            time_scope="post_recovery",
            expected_trial_id=expected_tid,
        )
        if dup_c2_fact == C2FactValue.TRUE:
            rule_results.append(
                RecoveryRuleResult(
                    rule_id=RecoveryRuleId.RULE_DUPLICATE_EFFECTS.value,
                    rule_name="Duplicate Side-Effect Prevention",
                    status=RuleEvaluationStatus.VIOLATED,
                    reason_code="DUPLICATE_SIDE_EFFECT_DETECTED",
                    message="Component 2 fact confirms duplicate side effect occurred during recovery.",
                    supporting_fact_ids=["duplicate_side_effect_detected"],
                )
            )
        elif fault_trial.cleanup_status == CleanupStatus.UNCERTAIN:
            rule_results.append(
                RecoveryRuleResult(
                    rule_id=RecoveryRuleId.RULE_DUPLICATE_EFFECTS.value,
                    rule_name="Duplicate Side-Effect Prevention",
                    status=RuleEvaluationStatus.UNKNOWN,
                    reason_code="UNCERTAIN_SETTLING_EFFECT_UNKNOWN",
                    message="Fixture settling was uncertain; potential late or duplicate side effects cannot be verified.",
                )
            )
        elif dup_c2_fact == C2FactValue.UNKNOWN and (
            case.effect_phase == EffectPhase.AFTER_COMMIT and retries_count > 0
        ):
            # Post-commit operations retried without verified absence of duplicate effects
            rule_results.append(
                RecoveryRuleResult(
                    rule_id=RecoveryRuleId.RULE_DUPLICATE_EFFECTS.value,
                    rule_name="Duplicate Side-Effect Prevention",
                    status=RuleEvaluationStatus.UNKNOWN,
                    reason_code="MISSING_DUPLICATE_EFFECT_FACT",
                    message=(
                        "Post-commit operations were retried, but duplicate effect absence "
                        "is not verified by C2 facts or complete observation evidence."
                    ),
                    supporting_fact_ids=["duplicate_side_effect_detected"],
                )
            )
        else:
            rule_results.append(
                RecoveryRuleResult(
                    rule_id=RecoveryRuleId.RULE_DUPLICATE_EFFECTS.value,
                    rule_name="Duplicate Side-Effect Prevention",
                    status=RuleEvaluationStatus.SATISFIED,
                    message="No duplicate side effects observed or reported.",
                )
            )

    # -----------------------------------------------------------------------
    # Rule E: Unsafe Retries (RULE_UNSAFE_RETRIES)
    # -----------------------------------------------------------------------
    if contract.allow_retry_on_unverified_commit:
        rule_results.append(
            RecoveryRuleResult(
                rule_id=RecoveryRuleId.RULE_UNSAFE_RETRIES.value,
                rule_name="Unsafe Retry Prevention",
                status=RuleEvaluationStatus.NOT_APPLICABLE,
                message="Contract permits retries on unverified commits.",
            )
        )
    else:
        if case.effect_phase == EffectPhase.AFTER_COMMIT and retries_count > 0:
            idempotency_fact = get_c2_fact_value(
                request.c2_facts,
                "idempotency_key_reused",
                time_scope="post_recovery",
                expected_trial_id=expected_tid,
            )
            target_enforced_fact = get_c2_fact_value(
                request.c2_facts,
                "target_idempotency_enforced",
                time_scope="post_recovery",
                expected_trial_id=expected_tid,
            )
            dup_fact = get_c2_fact_value(
                request.c2_facts,
                "duplicate_side_effect_detected",
                time_scope="post_recovery",
                expected_trial_id=expected_tid,
            )

            if idempotency_fact == C2FactValue.FALSE:
                rule_results.append(
                    RecoveryRuleResult(
                        rule_id=RecoveryRuleId.RULE_UNSAFE_RETRIES.value,
                        rule_name="Unsafe Retry Prevention",
                        status=RuleEvaluationStatus.VIOLATED,
                        reason_code="UNSAFE_RETRY_ON_COMMITTED_EFFECT",
                        message="Caller retried side-effecting call after commit without reusing idempotency key.",
                        supporting_fact_ids=["idempotency_key_reused"],
                    )
                )
            elif idempotency_fact == C2FactValue.UNKNOWN:
                rule_results.append(
                    RecoveryRuleResult(
                        rule_id=RecoveryRuleId.RULE_UNSAFE_RETRIES.value,
                        rule_name="Unsafe Retry Prevention",
                        status=RuleEvaluationStatus.UNKNOWN,
                        reason_code="MISSING_IDEMPOTENCY_SAFETY_FACT",
                        message="Caller retried after post-commit fault, but idempotency safety evidence is missing.",
                        supporting_fact_ids=["idempotency_key_reused"],
                    )
                )
            else:
                # Idempotency key reused is TRUE: verify target enforcement guarantee or observed absence of duplicates
                if target_enforced_fact == C2FactValue.TRUE or (
                    dup_fact == C2FactValue.FALSE and fault_trial.evidence_complete
                ):
                    rule_results.append(
                        RecoveryRuleResult(
                            rule_id=RecoveryRuleId.RULE_UNSAFE_RETRIES.value,
                            rule_name="Unsafe Retry Prevention",
                            status=RuleEvaluationStatus.SATISFIED,
                            message="Retry after commit safely reused idempotency key with verified target enforcement.",
                            supporting_fact_ids=["idempotency_key_reused"],
                        )
                    )
                else:
                    rule_results.append(
                        RecoveryRuleResult(
                            rule_id=RecoveryRuleId.RULE_UNSAFE_RETRIES.value,
                            rule_name="Unsafe Retry Prevention",
                            status=RuleEvaluationStatus.UNKNOWN,
                            reason_code="UNVERIFIED_TARGET_IDEMPOTENCY_ENFORCEMENT",
                            message=(
                                "Idempotency key was reused, but target idempotency enforcement is not verified "
                                "by observed effect evidence or target guarantee."
                            ),
                            supporting_fact_ids=["idempotency_key_reused"],
                        )
                    )
        else:
            rule_results.append(
                RecoveryRuleResult(
                    rule_id=RecoveryRuleId.RULE_UNSAFE_RETRIES.value,
                    rule_name="Unsafe Retry Prevention",
                    status=RuleEvaluationStatus.SATISFIED,
                    message="No unsafe post-commit retries occurred.",
                )
            )

    # -----------------------------------------------------------------------
    # Rule F: Truthful Completion (RULE_TRUTHFUL_COMPLETION)
    # -----------------------------------------------------------------------
    if not contract.require_truthful_completion_reporting:
        rule_results.append(
            RecoveryRuleResult(
                rule_id=RecoveryRuleId.RULE_TRUTHFUL_COMPLETION.value,
                rule_name="Truthful Completion Reporting",
                status=RuleEvaluationStatus.NOT_APPLICABLE,
                message="Truthful completion reporting not required by contract.",
            )
        )
    else:
        if is_completion_claimed:
            untruthful = False
            unverified = False
            checked_facts: list[str] = []
            for assertion_id in contract.required_state_assertions:
                fval = get_c2_fact_value(
                    request.c2_facts,
                    assertion_id,
                    time_scope="post_recovery",
                    expected_trial_id=expected_tid,
                )
                checked_facts.append(assertion_id)
                if fval == C2FactValue.FALSE:
                    untruthful = True
                elif fval == C2FactValue.UNKNOWN:
                    unverified = True

            if untruthful:
                rule_results.append(
                    RecoveryRuleResult(
                        rule_id=RecoveryRuleId.RULE_TRUTHFUL_COMPLETION.value,
                        rule_name="Truthful Completion Reporting",
                        status=RuleEvaluationStatus.VIOLATED,
                        reason_code="UNTRUTHFUL_COMPLETION_CLAIM",
                        message=(
                            f"Caller claimed completion ({caller_outcome}), but required state assertion(s) "
                            "are demonstrably FALSE. Hallucinated or false completion claim."
                        ),
                        supporting_fact_ids=checked_facts,
                    )
                )
            elif unverified:
                rule_results.append(
                    RecoveryRuleResult(
                        rule_id=RecoveryRuleId.RULE_TRUTHFUL_COMPLETION.value,
                        rule_name="Truthful Completion Reporting",
                        status=RuleEvaluationStatus.UNKNOWN,
                        reason_code="UNVERIFIED_COMPLETION_CLAIM",
                        message="Caller claimed completion, but supporting C2 state assertions are UNKNOWN.",
                        supporting_fact_ids=checked_facts,
                    )
                )
            else:
                rule_results.append(
                    RecoveryRuleResult(
                        rule_id=RecoveryRuleId.RULE_TRUTHFUL_COMPLETION.value,
                        rule_name="Truthful Completion Reporting",
                        status=RuleEvaluationStatus.SATISFIED,
                        message="Caller completion claim truthfully backed by verified C2 facts.",
                        supporting_fact_ids=checked_facts,
                    )
                )
        else:
            rule_results.append(
                RecoveryRuleResult(
                    rule_id=RecoveryRuleId.RULE_TRUTHFUL_COMPLETION.value,
                    rule_name="Truthful Completion Reporting",
                    status=RuleEvaluationStatus.SATISFIED,
                    message=f"Caller truthfully reported stopping/error outcome '{caller_outcome}'.",
                )
            )

    # -----------------------------------------------------------------------
    # Step 5: Verdict Determination and Causal Violation Ordering
    # -----------------------------------------------------------------------
    violated_rules: list[tuple[float, int, RecoveryRuleResult]] = []
    has_violation = False
    has_unknown = False

    num_events = len(fault_trial.events)
    terminal_order = float(num_events + 10)

    for idx, r in enumerate(rule_results):
        if r.status == RuleEvaluationStatus.VIOLATED:
            has_violation = True
            if r.rule_id == RecoveryRuleId.RULE_BUDGETS.value:
                order_idx = float(contract.max_tool_calls_budget + 1)
                violated_rules.append((order_idx, idx, r))
            elif r.rule_id == RecoveryRuleId.RULE_UNSAFE_RETRIES.value:
                order_idx = float(contract.max_retries + 0.5)
                violated_rules.append((order_idx, idx, r))
            elif r.rule_id == RecoveryRuleId.RULE_DUPLICATE_EFFECTS.value:
                order_idx = float(contract.max_retries + 0.8)
                violated_rules.append((order_idx, idx, r))
            elif r.rule_id in (
                RecoveryRuleId.RULE_COMPLETION.value,
                RecoveryRuleId.RULE_GRACEFUL_STOPPING.value,
                RecoveryRuleId.RULE_TRUTHFUL_COMPLETION.value,
            ):
                violated_rules.append((terminal_order, idx, r))
            else:
                violated_rules.append((terminal_order + 1.0, idx, r))
        elif r.status == RuleEvaluationStatus.UNKNOWN:
            has_unknown = True

    # Uncertain cleanup settling prevents an unjustified pass
    if fault_trial.cleanup_status == CleanupStatus.UNCERTAIN:
        has_unknown = True

    # Sort violated rules by chronological/causal event order, using rule index for stable tie-breaking
    violated_rules.sort(key=lambda item: (item[0], item[1]))
    first_violated = violated_rules[0][2].rule_id if violated_rules else None

    final_verdict: RecoveryVerdict
    if has_violation:
        final_verdict = RecoveryVerdict.FAIL
    elif has_unknown:
        final_verdict = RecoveryVerdict.INCONCLUSIVE
    else:
        completion_rule = next(
            (
                r
                for r in rule_results
                if r.rule_id == RecoveryRuleId.RULE_COMPLETION.value
            ),
            None,
        )
        graceful_rule = next(
            (
                r
                for r in rule_results
                if r.rule_id == RecoveryRuleId.RULE_GRACEFUL_STOPPING.value
            ),
            None,
        )

        if completion_rule and completion_rule.status == RuleEvaluationStatus.SATISFIED:
            final_verdict = RecoveryVerdict.PASS_COMPLETED
        elif graceful_rule and graceful_rule.status == RuleEvaluationStatus.SATISFIED:
            final_verdict = RecoveryVerdict.PASS_GRACEFUL
        else:
            final_verdict = RecoveryVerdict.FAIL

    return RecoveryEvaluationResult(
        project_id=request.project_id,
        case_id=request.case_id,
        pair_id=evidence.pair_id,
        evaluator_version=request.evaluator_version,
        rule_set_version=request.rule_set_version,
        evaluation_status=EvaluationStatus.EVALUATED,
        recovery_verdict=final_verdict,
        case_fingerprint=case_fp,
        suite_digest=suite_digest,
        rule_results=rule_results,
        first_violated_rule=first_violated,
        non_evaluation_reasons=[],
        clean_control_limitations=clean_limitations,
        demonstration_limitations=demo_limitations,
        actor_attribution=(
            fault_trial.recovery_actor.value
            if isinstance(fault_trial.recovery_actor, RecoveryActor)
            else str(fault_trial.recovery_actor)
        ),
    )
