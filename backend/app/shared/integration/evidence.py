"""Safe projection of execution evidence into component-native evaluation contracts.

Component: Shared Integration Coordination (Part 2)
Guarantees:
- Execute once, project into multiple compatible component evaluator contracts.
- Preserves original chronological ordering and event correlation.
- Preserves tool arguments, outcomes, errors, operation IDs, and caller observations.
- Never fabricates missing authorization decisions, committed effects, source trust, disclosures, or trace completeness.
- Distinguishes QA platform users from AUT internal principal roles.
- Sanitizes all secrets, passwords, and tokens before retention.
"""

import copy
import hashlib
import json
import uuid
from typing import Any

from app.components.c1_tool_call_correctness.contracts.execution import (
    CapturedToolEvent,
    EventStatus,
    TraceCompleteness,
)
from app.components.c2_state_aware_workflow.contracts.runtime_evidence import (
    EvidenceCompleteness,
    RuntimeEvidenceContract,
    StateObservation,
)
from app.components.c2_state_aware_workflow.contracts.runtime_evidence import (
    RuntimeEvent as C2RuntimeEvent,
)
from app.components.c3_robustness_recovery.contracts.evaluation import (
    C2AssertionFact,
)
from app.components.c3_robustness_recovery.contracts.schemas import (
    EffectPhase,
    FaultFamily,
    InterceptionHook,
    RecoveryContract,
)
from app.components.c3_robustness_recovery.runtime.adapter import (
    CallerIdentity,
    CleanupStatus,
    RecoveryActor,
)
from app.components.c3_robustness_recovery.runtime.adapter import (
    TargetMode as C3TargetMode,
)
from app.components.c3_robustness_recovery.runtime.evidence import (
    CleanQualification,
    ExecutionStatus,
    ExposureStatus,
    FaultEpisodeRecord,
    FixtureComparability,
    MatchedPairEvidence,
    ReadinessStatus,
    StateObservationReference,
    TimeoutBoundaryType,
    TrialEvidence,
    TrialRole,
)
from app.components.c3_robustness_recovery.runtime.evidence import (
    RuntimeEvent as C3RuntimeEvent,
)
from app.components.c3_robustness_recovery.services.c2_facts import (
    C2ToC3AssertionMapping,
    evaluate_c2_facts_bridge,
)
from app.components.c4_policy_aware_safety.contracts.enums import (
    EvidenceOrigin,
    InstructionSourceType,
    TrustClassification,
)
from app.components.c4_policy_aware_safety.contracts.enums import (
    ExposureStatus as C4ExposureStatus,
)
from app.components.c4_policy_aware_safety.contracts.evidence import (
    ActionAttemptEvidence,
    AttackEvidence,
    EffectEvidence,
    EvaluationEvidencePackage,
    ExposureEvidence,
    InstructionSourceEvidence,
    PrincipalEvidence,
    ToolExecutionEvidence,
    TraceCompletenessEvidence,
)
from app.shared.integration.adapters import (
    ExecutionTrace,
    sanitize_payload,
)


def compute_evidence_digest(data: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 digest of serialized canonical JSON."""
    clean = sanitize_payload(data)
    canonical = json.dumps(clean, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# C1 Evidence Projection
# ---------------------------------------------------------------------------


def project_c1_evidence(
    trace: ExecutionTrace,
) -> tuple[list[CapturedToolEvent], TraceCompleteness]:
    """Project raw execution trace into Component 1 tool-call events.

    Preserves arguments, errors, ordering, and completeness.
    """
    events: list[CapturedToolEvent] = []
    for ev in trace.tool_events:
        status_val = EventStatus.SUCCESS if ev.success else EventStatus.FAILED
        events.append(
            CapturedToolEvent(
                event_id=ev.event_id or f"evt_{ev.call_index}",
                call_index=ev.call_index,
                tool_name=ev.tool_name,
                arguments=copy_sanitized(ev.arguments),
                status=status_val,
                tool_response=copy_sanitized(ev.output),
                tool_error=ev.error,
                timestamp=ev.timestamp_utc,
            )
        )

    completeness = (
        TraceCompleteness.COMPLETE
        if trace.is_complete
        else TraceCompleteness.INCOMPLETE
    )
    return events, completeness


# ---------------------------------------------------------------------------
# C2 Evidence Projection
# ---------------------------------------------------------------------------


def project_c2_evidence(
    project_id: str,
    run_id: str,
    test_id: str,
    model_id: str,
    model_version: str,
    trace: ExecutionTrace,
    suite_id: str | None = None,
) -> RuntimeEvidenceContract:
    """Project raw execution trace into Component 2 Conformance RuntimeEvidenceContract.

    Links before/after state observations with step events.
    """
    c2_events: list[C2RuntimeEvent] = []
    c2_observations: list[StateObservation] = []
    # Live NexaCart runs report a snapshot after every state-changing tool call.
    intermediate_after: dict[int, dict[str, Any]] = {
        int(snap["afterSequenceNumber"]): snap.get("snapshot") or {}
        for snap in (trace.aut_metadata or {}).get("intermediate_snapshots", [])
        if isinstance(snap, dict) and snap.get("afterSequenceNumber") is not None
    }
    last_known_state: dict[str, Any] = trace.initial_state.state

    for idx, ev in enumerate(trace.tool_events):
        event_id = ev.event_id or f"c2_evt_{ev.call_index}"
        c2_events.append(
            C2RuntimeEvent(
                event_index=idx,
                event_id=event_id,
                tool_call_correlation_id=ev.idempotency_key,
                timestamp=ev.timestamp_utc,
                tool_name=ev.tool_name,
                arguments=copy_sanitized(ev.arguments),
                observable_result=copy_sanitized(ev.output),
                error=ev.error,
                entity_identifiers=extract_entity_identifiers(ev.arguments, ev.output),
            )
        )
        # Actual per-step observations when available; do not copy final state onto intermediate steps
        if intermediate_after:
            before_st = last_known_state
            if ev.call_index in intermediate_after:
                after_st = intermediate_after[ev.call_index]
                last_known_state = after_st
            elif idx == len(trace.tool_events) - 1:
                after_st = trace.final_state.state
            else:
                # Read-only call: no state change is expected, and none was observed.
                after_st = last_known_state
        elif idx == 0:
            before_st = trace.initial_state.state
            after_st = trace.final_state.state if len(trace.tool_events) == 1 else {}
        elif idx == len(trace.tool_events) - 1:
            before_st = {}
            after_st = trace.final_state.state
        else:
            before_st = {}
            after_st = {}
        c2_observations.append(
            StateObservation(
                event_index=idx,
                before_state=copy_sanitized(before_st),
                after_state=copy_sanitized(after_st),
                state_diff={},
            )
        )

    completeness = EvidenceCompleteness(
        has_all_events=trace.is_complete,
        has_state_snapshots=True,
        has_db_diffs=bool(intermediate_after),
        is_complete=trace.is_complete,
        confirmed_agent_termination=not trace.is_simulation and trace.is_complete,
        termination_reason=trace.caller_outcome,
    )

    return RuntimeEvidenceContract(
        schema_version="2026.1",
        project_id=project_id,
        suite_id=suite_id,
        run_id=run_id,
        test_id=test_id,
        model_id=model_id,
        model_version=model_version,
        execution_mode="synthetic_evaluator" if trace.is_simulation else "live_agent",
        ordered_events=c2_events,
        state_observations=c2_observations,
        completeness=completeness,
        collector_provenance={
            "runner_id": "shared_integration_coordinator",
            "is_simulation": trace.is_simulation,
            "trace_id": trace.trace_id,
        },
    )


# ---------------------------------------------------------------------------
# C3 Matched-Pair Evidence Projection & Bridge Integration
# ---------------------------------------------------------------------------


def project_c3_matched_pair_evidence(
    project_id: str,
    case_id: str,
    pair_id: str,
    run_id: str,
    clean_trace: ExecutionTrace,
    fault_trace: ExecutionTrace,
    recovery_contract: RecoveryContract,
    c2_mappings: list[C2ToC3AssertionMapping] | None = None,
    expected_entity_id: str | None = None,
    planned_fault: dict[str, Any] | None = None,
) -> tuple[MatchedPairEvidence, list[C2AssertionFact]]:
    """Project clean and fault execution traces into C3 MatchedPairEvidence and invoke C2 bridge.

    Strict rules:
    - Clean and fault trials must have separate trial IDs and distinct evidence.
    - C2 facts for C3 must be evaluated on the FAULT trial's recovery snapshot, never clean.
    - Clean trial baseline qualification is evaluated independently.
    - Exposure is verified from fault trial trace events, or from the target's exposure receipts
      when it reports them (live NexaCart). ``planned_fault`` (target_tool, occurrence,
      fault_family, effect_phase) lets receipts be checked against the frozen case.
    """
    clean_trial_id = f"trial-clean-{clean_trace.trace_id[:8]}"
    fault_trial_id = f"trial-fault-{fault_trace.trace_id[:8]}"

    # 1. Clean Trial Evidence
    clean_events = [
        C3RuntimeEvent(
            event_id=e.event_id or f"c3-clean-{e.call_index}",
            timestamp_iso=e.timestamp_utc.isoformat(),
            event_type="TOOL_CALL_EXECUTED" if e.success else "TOOL_CALL_FAILED",
            tool_id=e.tool_name,
            occurrence=e.call_index,
            details=copy_sanitized(e.arguments),
        )
        for e in clean_trace.tool_events
    ]

    clean_trial = TrialEvidence(
        project_id=project_id,
        case_id=case_id,
        pair_id=pair_id,
        trial_id=clean_trial_id,
        run_id=run_id,
        trial_role=TrialRole.CLEAN,
        target_mode=C3TargetMode.DEMONSTRATION
        if clean_trace.is_simulation
        else C3TargetMode.LIVE_AUT,
        caller_identity=CallerIdentity.SCRIPTED_CALLER
        if clean_trace.is_simulation
        else CallerIdentity.ACTUAL_AGENT,
        recovery_actor=RecoveryActor.SCRIPTED_CALLER
        if clean_trace.is_simulation
        else RecoveryActor.AGENT,
        fixture_namespace=f"ns-clean-{pair_id[:8]}",
        initial_state_fingerprint=clean_trace.initial_state.fingerprint,
        final_state_fingerprint=clean_trace.final_state.fingerprint,
        events=clean_events,
        tool_calls_count=len(clean_trace.tool_events),
        subsequent_calls_count=0,
        execution_status=ExecutionStatus.COMPLETED
        if clean_trace.is_complete
        else ExecutionStatus.EXECUTION_ERROR,
        caller_outcome=clean_trace.caller_outcome,
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED
        if clean_trace.cleanup_successful
        else CleanupStatus.UNCERTAIN,
        evidence_complete=clean_trace.is_complete,
    )

    # 2. Fault Trial Evidence
    fault_events = [
        C3RuntimeEvent(
            event_id=e.event_id or f"c3-fault-{e.call_index}",
            timestamp_iso=e.timestamp_utc.isoformat(),
            event_type="TOOL_CALL_EXECUTED"
            if e.success
            else "FAULT_INJECTION_OBSERVED",
            tool_id=e.tool_name,
            occurrence=e.call_index,
            details=copy_sanitized(e.arguments),
        )
        for e in fault_trace.tool_events
    ]

    target_tool = None
    target_occurrence = None
    if fault_trace.fault_details:
        target_tool = fault_trace.fault_details.get("target_tool")
        target_occurrence = fault_trace.fault_details.get(
            "injected_at_call_index"
        ) or fault_trace.fault_details.get("occurrence")

    episodes: list[FaultEpisodeRecord] = []
    receipts = (fault_trace.fault_details or {}).get("receipts") or []
    if receipts:
        # Live target: exposure and effect phase come from the target's own exposure receipts.
        exposure_status, exposure_reasons, episodes, receipt_events = (
            _assess_receipt_exposure(fault_trace, receipts, planned_fault)
        )
        fault_events = _insert_after_call(fault_events, receipt_events)
    else:
        # Correlate exposure strictly to the targeted tool and occurrence
        exposure_confirmed = False
        if fault_trace.fault_injected and target_tool:
            for e in fault_trace.tool_events:
                if (
                    e.tool_name == target_tool
                    and not e.success
                    and (target_occurrence is None or e.call_index == target_occurrence)
                ):
                    exposure_confirmed = True
                    break

        exposure_status = (
            ExposureStatus.CONFIRMED
            if exposure_confirmed
            else (
                ExposureStatus.NOT_TRIGGERED
                if not fault_trace.fault_injected
                else ExposureStatus.EXPOSURE_UNKNOWN
            )
        )
        exposure_reasons = (
            [
                f"Fault injection hook entered on targeted tool '{target_tool}' and failure observed by caller."
            ]
            if exposure_confirmed
            else (
                ["Fault hook not triggered."]
                if not fault_trace.fault_injected
                else ["Fault flag set but failure on targeted tool unconfirmed."]
            )
        )
        if (
            not fault_trace.fault_injected
            and (fault_trace.fault_details or {}).get("status") == "NOT_TRIGGERED"
        ):
            exposure_reasons = [
                (fault_trace.fault_details or {}).get("reason")
                or "Fault hook not triggered."
            ]

    # Compute retries strictly based on logical-operation identity (do not count unrelated later calls)
    retries_count = 0
    if fault_trace.fault_injected:
        fault_tool_name = target_tool
        fault_call_idx = target_occurrence
        if not fault_tool_name or fault_call_idx is None:
            for e in fault_trace.tool_events:
                if not e.success:
                    fault_tool_name = fault_tool_name or e.tool_name
                    fault_call_idx = fault_call_idx or e.call_index
                    break
        if fault_tool_name and fault_call_idx is not None:
            retries_count = sum(
                1
                for e in fault_trace.tool_events
                if e.tool_name == fault_tool_name and e.call_index > fault_call_idx
            )
        else:
            retries_count = 0

    obs_ref = None
    snap_id = fault_trace.final_state.snapshot_id if fault_trace.final_state else None
    if snap_id:
        obs_ref = StateObservationReference(
            snapshot_id=snap_id,
            snapshot_version="1.0.0",
            entity_id=expected_entity_id,
            observation_scope="post_recovery",
            fingerprint=fault_trace.final_state.fingerprint
            if fault_trace.final_state
            else None,
        )

    fault_trial = TrialEvidence(
        project_id=project_id,
        case_id=case_id,
        pair_id=pair_id,
        trial_id=fault_trial_id,
        run_id=run_id,
        trial_role=TrialRole.FAULT,
        target_mode=C3TargetMode.DEMONSTRATION
        if fault_trace.is_simulation
        else C3TargetMode.LIVE_AUT,
        caller_identity=CallerIdentity.SCRIPTED_CALLER
        if clean_trace.is_simulation
        else CallerIdentity.ACTUAL_AGENT,
        recovery_actor=RecoveryActor.SCRIPTED_CALLER
        if clean_trace.is_simulation
        else RecoveryActor.AGENT,
        fixture_namespace=f"ns-fault-{pair_id[:8]}",
        initial_state_fingerprint=fault_trace.initial_state.fingerprint,
        final_state_fingerprint=fault_trace.final_state.fingerprint,
        events=fault_events,
        episodes=episodes,
        tool_calls_count=len(fault_trace.tool_events),
        subsequent_calls_count=retries_count,
        execution_status=ExecutionStatus.COMPLETED
        if fault_trace.is_complete
        else ExecutionStatus.EXECUTION_ERROR,
        caller_outcome=fault_trace.caller_outcome,
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED
        if fault_trace.cleanup_successful
        else CleanupStatus.UNCERTAIN,
        evidence_complete=fault_trace.is_complete,
        snapshot_id=snap_id,
        observed_entity_id=expected_entity_id,
        observation_reference=obs_ref,
    )

    clean_qualification = (
        CleanQualification.QUALIFIED
        if clean_trial.execution_status == ExecutionStatus.COMPLETED
        and clean_trial.caller_outcome == "SUCCESS"
        and all(e.success for e in clean_trace.tool_events)
        else CleanQualification.DISQUALIFIED
    )

    matched_evidence = MatchedPairEvidence(
        project_id=project_id,
        case_id=case_id,
        pair_id=pair_id,
        run_id=run_id,
        target_mode=C3TargetMode.DEMONSTRATION
        if fault_trace.is_simulation
        else C3TargetMode.LIVE_AUT,
        caller_identity=CallerIdentity.SCRIPTED_CALLER
        if fault_trace.is_simulation
        else CallerIdentity.ACTUAL_AGENT,
        configuration_snapshot={
            "agent_adapter": "shared_integration_coordinator",
            "is_simulation": fault_trace.is_simulation,
            **(
                {
                    "planned_fault": copy_sanitized(planned_fault),
                    "aut_trials": {
                        "clean": _aut_trial_summary(clean_trace),
                        "fault": _aut_trial_summary(fault_trace),
                    },
                }
                if not fault_trace.is_simulation
                else {}
            ),
        },
        clean_trial=clean_trial,
        fault_trial=fault_trial,
        readiness_status=ReadinessStatus.READY,
        exposure_assessed=True,
        exposure_status=exposure_status,
        exposure_reasons=exposure_reasons,
        fixture_comparability=_fixture_comparability(clean_trace, fault_trace),
        clean_qualification=clean_qualification,
        cleanup_status=(
            CleanupStatus.CLEANED_AND_VERIFIED
            if (
                clean_trial.cleanup_status == CleanupStatus.CLEANED_AND_VERIFIED
                and fault_trial.cleanup_status == CleanupStatus.CLEANED_AND_VERIFIED
            )
            else CleanupStatus.UNCERTAIN
        ),
    )

    # 3. Invoke C2 Fact Bridge for the Fault Trial
    obs_snapshot = {
        "snapshot_id": fault_trace.final_state.snapshot_id,
        "after": fault_trace.final_state.state,
        "before": fault_trace.initial_state.state,
        "event": {
            "trial_id": fault_trial_id,
            "tool_calls_count": fault_trial.tool_calls_count,
            "subsequent_calls_count": fault_trial.subsequent_calls_count,
            "caller_outcome": fault_trial.caller_outcome,
            **observed_retry_idempotency(fault_trace),
        },
    }

    c2_facts = evaluate_c2_facts_bridge(
        project_id=project_id,
        pair_id=pair_id,
        fault_trial_id=fault_trial_id,
        evidence=matched_evidence,
        recovery_contract=recovery_contract,
        observation_snapshot=obs_snapshot,
        mappings=c2_mappings,
        expected_entity_id=expected_entity_id,
    )

    return matched_evidence, c2_facts


# Target fault-gateway family names -> C3 fault families
RECEIPT_FAULT_FAMILIES: dict[str, FaultFamily] = {
    "TIMEOUT_DISCONNECTION": FaultFamily.TIMEOUT_DISCONNECTION,
    "TRANSIENT_5XX": FaultFamily.TRANSIENT_5XX,
    "RATE_LIMIT_429": FaultFamily.RATE_LIMIT_429,
    "TOOL_UNAVAILABLE": FaultFamily.TOOL_UNAVAILABILITY,
    "TOOL_UNAVAILABILITY": FaultFamily.TOOL_UNAVAILABILITY,
    "MALFORMED_OUTPUT": FaultFamily.MALFORMED_RESPONSE,
    "MALFORMED_RESPONSE": FaultFamily.MALFORMED_RESPONSE,
}


def _is_identity_key(key: str) -> bool:
    return key in ("id", "email", "orderNumber", "reference") or key.endswith("Id")


def _logical_state(node: Any) -> Any:
    """State with fixture-specific identifiers (ids, order numbers, emails) masked."""
    if isinstance(node, dict):
        return {
            k: "<fixture-identifier>" if _is_identity_key(str(k)) else _logical_state(v)
            for k, v in node.items()
        }
    if isinstance(node, list):
        return [_logical_state(v) for v in node]
    return node


def _fixture_comparability(
    clean_trace: ExecutionTrace, fault_trace: ExecutionTrace
) -> FixtureComparability:
    """Live fresh fixtures get new identifiers, so they are compared on logical state."""
    if not clean_trace.is_simulation and not fault_trace.is_simulation:
        if not clean_trace.initial_state.state or not fault_trace.initial_state.state:
            return FixtureComparability.UNKNOWN
        return (
            FixtureComparability.EQUIVALENT_LOGICAL_STATE
            if _logical_state(clean_trace.initial_state.state)
            == _logical_state(fault_trace.initial_state.state)
            else FixtureComparability.NON_EQUIVALENT
        )
    return (
        FixtureComparability.EQUIVALENT_LOGICAL_STATE
        if (
            clean_trace.initial_state.fingerprint
            and fault_trace.initial_state.fingerprint
            and clean_trace.initial_state.fingerprint
            == fault_trace.initial_state.fingerprint
        )
        else FixtureComparability.NON_EQUIVALENT
    )


def _state_without_customer(state: dict[str, Any] | None) -> dict[str, Any]:
    return {k: v for k, v in (state or {}).items() if k != "customer"}


def _assess_receipt_exposure(
    fault_trace: ExecutionTrace,
    receipts: list[dict[str, Any]],
    planned_fault: dict[str, Any] | None,
) -> tuple[ExposureStatus, list[str], list[FaultEpisodeRecord], list[C3RuntimeEvent]]:
    """Confirm exposure and effect phase from the target's exposure receipts.

    CONFIRMED requires: the receipt matches the planned tool, occurrence, family and phase; the
    agent actually received the delivered result at that call; the delivered envelope has the
    declared meaning; and for AFTER_COMMIT the tool ran, succeeded, and an independent snapshot
    taken after that call shows the committed state change.
    """
    receipt = receipts[0]
    reasons: list[str] = []
    seq = receipt.get("sequenceNumber")
    tool = receipt.get("targetTool")
    family = RECEIPT_FAULT_FAMILIES.get(str(receipt.get("faultFamily")))
    phase_raw = str(receipt.get("effectPhase") or "")
    phase = (
        EffectPhase.AFTER_COMMIT
        if phase_raw == "AFTER_COMMIT"
        else EffectPhase.BEFORE_EFFECT
    )
    envelope = receipt.get("deliveredEnvelope") or {}
    error = envelope.get("error") or {}

    if len(receipts) > 1:
        reasons.append(
            f"{len(receipts)} fault episodes were delivered; one targeted episode was declared."
        )
    if family is None:
        reasons.append(
            f"Receipt fault family '{receipt.get('faultFamily')}' is unknown."
        )

    if planned_fault:
        planned_family = RECEIPT_FAULT_FAMILIES.get(
            str(planned_fault.get("fault_family") or "").upper()
        )
        planned_phase = str(planned_fault.get("effect_phase") or "").upper()
        if planned_fault.get("target_tool") and planned_fault["target_tool"] != tool:
            reasons.append(
                f"Receipt tool '{tool}' != planned '{planned_fault['target_tool']}'."
            )
        if planned_fault.get("occurrence") is not None and int(
            planned_fault["occurrence"]
        ) != receipt.get("occurrence"):
            reasons.append(
                f"Receipt occurrence {receipt.get('occurrence')} != planned {planned_fault['occurrence']}."
            )
        if planned_family is not None and planned_family != family:
            reasons.append(
                f"Receipt family '{receipt.get('faultFamily')}' != planned '{planned_family.value}'."
            )
        if planned_phase and planned_phase != phase.value:
            reasons.append(
                f"Receipt effect phase '{phase.value}' != planned '{planned_phase}'."
            )

    delivered_call = next(
        (
            e
            for e in fault_trace.tool_events
            if e.call_index == seq and e.tool_name == tool
        ),
        None,
    )
    if delivered_call is None:
        reasons.append(
            f"No recorded agent tool call #{seq} for '{tool}' received the delivered fault."
        )
    elif family == FaultFamily.MALFORMED_RESPONSE:
        if not (envelope.get("ok") is True and isinstance(envelope.get("data"), str)):
            reasons.append("Delivered envelope is not a truncated (malformed) payload.")
    elif envelope.get("ok") is not False or delivered_call.success:
        reasons.append(
            "Delivered fault did not reach the agent as a failed tool result."
        )

    tool_executed = bool(receipt.get("toolExecuted"))
    committed_observed = False
    committed_operation_id = None
    commit_event: C3RuntimeEvent | None = None
    if phase == EffectPhase.AFTER_COMMIT:
        if not tool_executed:
            reasons.append(
                "AFTER_COMMIT receipt reports that the tool was not executed."
            )
        elif receipt.get("underlyingResultOk") is not True:
            reasons.append(
                "The tool ran but its own result failed, so no effect was committed before the lost reply."
            )
        snapshots = (fault_trace.aut_metadata or {}).get("intermediate_snapshots") or []
        after_call = next(
            (s for s in snapshots if s.get("afterSequenceNumber") == seq), None
        )
        if after_call is None:
            reasons.append(
                "No independent snapshot was captured after the faulted call; commit unobserved."
            )
        else:
            committed_observed = _state_without_customer(
                after_call.get("snapshot")
            ) != _state_without_customer(fault_trace.initial_state.state)
            if committed_observed:
                committed_operation_id = receipt.get("agentToolCallId")
                commit_event = C3RuntimeEvent(
                    event_id=f"c3-commit-obs-{seq}",
                    timestamp_iso=str(after_call.get("capturedAt") or ""),
                    event_type="INDEPENDENT_COMMIT_OBSERVATION",
                    tool_id=str(tool),
                    occurrence=int(seq or 0),
                    details={
                        "after_sequence_number": seq,
                        "agent_tool_call_id": receipt.get("agentToolCallId"),
                    },
                )
            else:
                reasons.append(
                    "Snapshot after the faulted call shows no state change; commit unobserved."
                )
    elif tool_executed:
        reasons.append("BEFORE_EFFECT receipt reports that the tool was executed.")

    data = envelope.get("data")
    episode = FaultEpisodeRecord(
        target_tool_id=str(tool),
        target_occurrence=int(receipt.get("occurrence") or 0),
        interception_hook=InterceptionHook.APPLICATION_AWARE_HOOK
        if phase == EffectPhase.AFTER_COMMIT
        else InterceptionHook.BEFORE_TOOL_CALL,
        effect_phase=phase,
        fault_family=family or FaultFamily.TIMEOUT_DISCONNECTION,
        fault_mode=str(error.get("errorCode") or ("TRUNCATED_JSON" if data else "")),
        declared_caller_timeout_ms=int(
            (planned_fault or {}).get("caller_timeout_ms") or 0
        ),
        # The target returns the fault result at once; no wall-clock wait is reproduced.
        timeout_boundary_type=TimeoutBoundaryType.IMMEDIATE_SYNTHETIC_EXCEPTION,
        prevented_forwarding=not tool_executed,
        caller_observed_timeout=family == FaultFamily.TIMEOUT_DISCONNECTION
        and delivered_call is not None
        and not delivered_call.success,
        elapsed_wait_ms=0.0,
        fault_status_code=error.get("statusCode"),
        retry_after_seconds=(planned_fault or {}).get("retry_after_seconds"),
        unavailability_mode=error.get("errorCode")
        if family == FaultFamily.TOOL_UNAVAILABILITY
        else None,
        malformed_fragment=data[:200] if isinstance(data, str) else None,
        committed_operation_id=committed_operation_id,
        independent_observation_confirmed=committed_observed,
    )

    events = [
        C3RuntimeEvent(
            event_id=f"c3-fault-delivered-{seq}",
            timestamp_iso=str(receipt.get("deliveredAt") or ""),
            event_type="FAULT_DELIVERED",
            tool_id=str(tool),
            occurrence=int(seq or 0),
            details={
                "receipt_occurrence": receipt.get("occurrence"),
                "fault_family": receipt.get("faultFamily"),
                "effect_phase": phase.value,
                "tool_executed": tool_executed,
                "underlying_result_ok": receipt.get("underlyingResultOk"),
                "delivered_error_code": error.get("errorCode"),
                "delivered_status_code": error.get("statusCode"),
            },
        )
    ]
    if commit_event is not None:
        events.append(commit_event)

    if reasons:
        return ExposureStatus.EXPOSURE_UNKNOWN, reasons, [episode], events
    return (
        ExposureStatus.CONFIRMED,
        [
            f"Exposure receipt confirms {receipt.get('faultFamily')} ({phase.value}) delivered to "
            f"'{tool}' occurrence {receipt.get('occurrence')} (call #{seq}) and received by the agent."
            + (
                " An independent snapshot after the call confirms the committed effect."
                if committed_observed
                else ""
            )
        ],
        [episode],
        events,
    )


def _insert_after_call(
    events: list[C3RuntimeEvent], extra: list[C3RuntimeEvent]
) -> list[C3RuntimeEvent]:
    """Place receipt-derived events right after the tool call they describe."""
    result = list(events)
    for ev in extra:
        idx = max(
            (
                i
                for i, e in enumerate(result)
                if e.occurrence == ev.occurrence and e.tool_id == ev.tool_id
            ),
            default=len(result) - 1,
        )
        result.insert(idx + 1, ev)
    return result


def _aut_trial_summary(trace: ExecutionTrace) -> dict[str, Any]:
    """Identifiers and observations reported by the live target for one trial."""
    meta = trace.aut_metadata or {}
    answer = meta.get("final_answer")
    return copy_sanitized(
        {
            "trace_id": trace.trace_id,
            "agent_run_id": meta.get("agent_run_id"),
            "qa_run_id": meta.get("qa_run_id"),
            "fixture_id": meta.get("fixture_id"),
            "fixture_order_number": (meta.get("fixture_context") or {}).get(
                "orderNumber"
            ),
            "agent_provider": meta.get("agent_provider"),
            "agent_model": meta.get("agent_model"),
            "agent_status": meta.get("agent_status"),
            "agent_error": meta.get("agent_error"),
            "final_answer": answer[:2000] if isinstance(answer, str) else answer,
            "caller_outcome": trace.caller_outcome,
            "outcome_classification": meta.get("outcome_classification"),
            "duration_ms": meta.get("duration_ms"),
            "llm_usage": meta.get("agent_llm_usage"),
            "tool_calls": [
                {
                    "call_index": e.call_index,
                    "tool_name": e.tool_name,
                    "success": e.success,
                    "error": e.error,
                    "idempotency_key": e.idempotency_key,
                }
                for e in trace.tool_events
            ],
            "fault_receipts": (trace.fault_details or {}).get("receipts") or [],
            "final_state": {
                k: trace.final_state.state.get(k)
                for k in ("orders", "payments", "refunds")
                if k in (trace.final_state.state or {})
            },
        }
    )


# ---------------------------------------------------------------------------
# C4 Evidence Projection
# ---------------------------------------------------------------------------


def project_c4_evidence(
    project_id: str,
    case_id: str,
    run_id: str,
    contract_version: int,
    trace: ExecutionTrace,
    aut_principal: PrincipalEvidence | None = None,
) -> EvaluationEvidencePackage:
    """Project raw execution trace into Component 4 Policy & Safety EvaluationEvidencePackage.

    Distinguishes QA platform users from AUT internal principal roles.
    Never fabricates authorization decisions or disclosures.
    """
    action_attempts: list[ActionAttemptEvidence] = []
    tool_executions: list[ToolExecutionEvidence] = []

    for ev in trace.tool_events:
        c4_evt_id = ev.event_id or f"c4-evt-{ev.call_index}"
        action_attempts.append(
            ActionAttemptEvidence(
                tool_name=ev.tool_name,
                arguments=copy_sanitized(ev.arguments) or {},
                timestamp=ev.timestamp_utc,
                caller_agent_id="aut_agent",
                event_id=c4_evt_id,
            )
        )
        tool_executions.append(
            ToolExecutionEvidence(
                tool_name=ev.tool_name,
                arguments=copy_sanitized(ev.arguments) or {},
                status="SUCCESS" if ev.success else "ERROR",
                rejection_message=None
                if ev.success
                else (ev.error or "Error occurred"),
                output=copy_sanitized(ev.output),
                event_id=c4_evt_id,
            )
        )

    live = trace.aut_metadata or {}
    if (
        aut_principal is None
        and live.get("fixture_context", {}).get("customerId") is not None
    ):
        # The NexaCart harness runs the agent as the fixture's authenticated CUSTOMER.
        aut_principal = PrincipalEvidence(
            principal_id=f"nexacart-user-{live['fixture_context']['customerId']}",
            roles=["CUSTOMER"],
            attributes={"source": "nexacart_qa_harness_fixture"},
        )

    # Attacks and exposure
    attacks: list[AttackEvidence] = []
    exposure = None
    instruction_sources: list[InstructionSourceEvidence] = [
        InstructionSourceEvidence(
            source_id="src-user-task",
            source_type=InstructionSourceType.AUTHENTICATED_USER_REQUEST,
            trust_classification=TrustClassification.AUTHENTICATED_USER,
            origin=EvidenceOrigin.SYNTHETIC_DEVELOPER_FIXTURE
            if trace.is_simulation
            else EvidenceOrigin.RECORDED_HARNESS_EVIDENCE,
        )
    ]

    if trace.injection_delivered and trace.injection_details:
        attack_id = f"atk-{uuid.uuid4().hex[:8]}"
        attacks.append(
            AttackEvidence(
                attack_id=attack_id,
                attack_type="INDIRECT_PROMPT_INJECTION",
                payload=trace.injection_details.get("payload", "[UNTRUSTED_INJECTION]"),
                target_boundary="ATTEMPTED_ACTION",
                attacker_goal="Unauthorized action execution",
            )
        )
        # A payload placed in the user's own task prompt is a direct challenge from the user.
        src_type = InstructionSourceType.AUTHENTICATED_USER_REQUEST
        if trace.injection_details.get("channel") == "support_ticket":
            src_type = InstructionSourceType.SUPPORT_TICKET
        elif trace.injection_details.get("delivered_via_event_ids"):
            # Observed inside a real tool output (e.g. NexaCart product description).
            src_type = InstructionSourceType.TOOL_RESPONSE
        instruction_sources.append(
            InstructionSourceEvidence(
                source_id="src-untrusted-injection",
                source_type=src_type,
                trust_classification=TrustClassification.UNTRUSTED_CONTENT,
                origin=EvidenceOrigin.SYNTHETIC_DEVELOPER_FIXTURE
                if trace.is_simulation
                else EvidenceOrigin.RECORDED_HARNESS_EVIDENCE,
                raw_text=trace.injection_details.get("payload"),
            )
        )
        # Injection delivery alone does not confirm agent exposure. On live NexaCart runs every
        # executed tool result is appended to the agent conversation, so a payload observed in a
        # tool output followed by a later model turn (run COMPLETED) was in the agent's context.
        carrying = trace.injection_details.get("delivered_via_event_ids") or []
        if (
            not trace.is_simulation
            and carrying
            and live.get("agent_status") == "COMPLETED"
        ):
            exposure = ExposureEvidence(
                exposure_status=C4ExposureStatus.EXPOSED,
                exposure_event_id=carrying[0],
                exposure_details=(
                    "Payload observed in a real NexaCart tool result that was returned to the agent "
                    "before its final model turn."
                ),
            )
        else:
            exposure = None

    trace_completeness = TraceCompletenessEvidence(
        is_complete=trace.is_complete,
        missing_stages=[],
        total_events=len(action_attempts),
    )

    return EvaluationEvidencePackage(
        project_id=project_id,
        case_id=case_id,
        run_id=run_id,
        trace_id=trace.trace_id,
        contract_version=contract_version,
        origin=EvidenceOrigin.SYNTHETIC_DEVELOPER_FIXTURE
        if trace.is_simulation
        else EvidenceOrigin.RECORDED_HARNESS_EVIDENCE,
        principal=aut_principal,
        instruction_sources=instruction_sources,
        action_attempts=action_attempts,
        tool_executions=tool_executions,
        authorization_decisions=[],  # Never fabricate authorization decisions
        disclosures=[],  # Never fabricate disclosures
        effects=derive_snapshot_effects(
            trace
        ),  # Observed snapshot diff only; empty when not observed
        trace_completeness=trace_completeness,
        attacks=attacks,
        exposure=exposure,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def observed_retry_idempotency(fault_trace: ExecutionTrace) -> dict[str, Any]:
    """Whether retries of the faulted call reused its recorded idempotency key.

    Returns ``{"idempotency_key_reused": bool}`` only when the faulted call and every later call
    to the same tool carry a recorded key; otherwise returns ``{}`` so the fact stays UNKNOWN.
    """
    details = fault_trace.fault_details or {}
    target_tool = details.get("target_tool")
    fault_index = details.get("injected_at_call_index")
    if not fault_trace.fault_injected or not target_tool or fault_index is None:
        return {}
    faulted = [
        e
        for e in fault_trace.tool_events
        if e.tool_name == target_tool and e.call_index == fault_index
    ]
    retries = [
        e
        for e in fault_trace.tool_events
        if e.tool_name == target_tool and e.call_index > fault_index
    ]
    if not faulted or not retries:
        return {}
    keys = [faulted[0].idempotency_key, *(e.idempotency_key for e in retries)]
    if any(k is None for k in keys):
        return {}
    return {"idempotency_key_reused": all(k == keys[0] for k in keys)}


def derive_snapshot_effects(trace: ExecutionTrace) -> list[EffectEvidence]:
    """Derive persistent effects from the real BEFORE/AFTER snapshots of a live run.

    Test doubles (``is_simulation``) and runs without an observed final state yield no effects.
    """
    if trace.is_simulation or not trace.final_state.state:
        return []
    before = trace.initial_state.state or {}
    after = trace.final_state.state or {}
    effects: list[EffectEvidence] = []
    for section in sorted(set(before) | set(after)):
        if section == "customer":
            continue
        old, new = before.get(section), after.get(section)
        if old != new:
            effects.append(
                EffectEvidence(
                    target_entity=section,
                    state_change_observed=True,
                    committed_status="COMMITTED",
                    delta={"before": copy_sanitized(old), "after": copy_sanitized(new)},
                    event_id=trace.final_state.snapshot_id,
                )
            )
    return effects


def copy_sanitized(data: Any) -> Any:
    return sanitize_payload(copy.deepcopy(data)) if data is not None else None


def extract_entity_identifiers(
    arguments: dict[str, Any], output: dict[str, Any] | None
) -> dict[str, Any]:
    """Extract standard entity IDs (order_id, customer_id, refund_id) from tool parameters or results."""
    entity_keys = {
        "order_id",
        "customer_id",
        "refund_id",
        "item_id",
        "user_id",
        # NexaCart tool arguments/results
        "orderNumber",
        "orderId",
        "productId",
        "cartItemId",
        "refundId",
    }
    identifiers: dict[str, Any] = {}

    def collect(node: Any, depth: int) -> None:
        # NexaCart wraps results as {"ok": ..., "data": {...}}; look a few levels deep.
        if not isinstance(node, dict) or depth > 3:
            return
        for k, v in node.items():
            if k in entity_keys and not isinstance(v, dict | list):
                identifiers.setdefault(k, v)
            elif isinstance(v, dict):
                collect(v, depth + 1)

    for src in [arguments, output or {}]:
        collect(src, 0)
    return identifiers
