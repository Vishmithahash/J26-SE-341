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
    FixtureComparability,
    MatchedPairEvidence,
    ReadinessStatus,
    StateObservationReference,
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
from app.components.c4_policy_aware_safety.contracts.evidence import (
    ActionAttemptEvidence,
    AttackEvidence,
    EvaluationEvidencePackage,
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
        if idx == 0:
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
        has_db_diffs=False,
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
) -> tuple[MatchedPairEvidence, list[C2AssertionFact]]:
    """Project clean and fault execution traces into C3 MatchedPairEvidence and invoke C2 bridge.

    Strict rules:
    - Clean and fault trials must have separate trial IDs and distinct evidence.
    - C2 facts for C3 must be evaluated on the FAULT trial's recovery snapshot, never clean.
    - Clean trial baseline qualification is evaluated independently.
    - Exposure is verified from fault trial trace events.
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
        },
        clean_trial=clean_trial,
        fault_trial=fault_trial,
        readiness_status=ReadinessStatus.READY,
        exposure_assessed=True,
        exposure_status=exposure_status,
        exposure_reasons=exposure_reasons,
        fixture_comparability=FixtureComparability.EQUIVALENT_LOGICAL_STATE
        if (
            clean_trace.initial_state.fingerprint
            and fault_trace.initial_state.fingerprint
            and clean_trace.initial_state.fingerprint
            == fault_trace.initial_state.fingerprint
        )
        else FixtureComparability.NON_EQUIVALENT,
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
        src_type = InstructionSourceType.DIRECT_PROMPT
        if trace.injection_details.get("channel") == "support_ticket":
            src_type = InstructionSourceType.SUPPORT_TICKET
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
        # Injection delivery alone does not confirm agent exposure
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
        effects=[],  # Never fabricate effects
        trace_completeness=trace_completeness,
        attacks=attacks,
        exposure=exposure,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def copy_sanitized(data: Any) -> Any:
    return sanitize_payload(copy.deepcopy(data)) if data is not None else None


def extract_entity_identifiers(
    arguments: dict[str, Any], output: dict[str, Any] | None
) -> dict[str, Any]:
    """Extract standard entity IDs (order_id, customer_id, refund_id) from tool parameters or results."""
    entity_keys = {"order_id", "customer_id", "refund_id", "item_id", "user_id"}
    identifiers: dict[str, Any] = {}
    for src in [arguments, output or {}]:
        for k, v in src.items():
            if k in entity_keys:
                identifiers[k] = v
    return identifiers
