"""Matched trial runner, runtime readiness enforcement, and local developer CLI.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 2 - One-tool integration, matched trials, verified timeout exposure and safeguards.
"""

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.components.c3_robustness_recovery.contracts.schemas import (
    AdapterCapabilityManifest,
    CandidateFaultCase,
    EffectPhase,
    FaultFamily,
    FaultValidationRequest,
    InterceptionHook,
    RecoveryContract,
    TaskFixtureMetadata,
    TimeoutDisconnectionMode,
    ValidationStatus,
)
from app.components.c3_robustness_recovery.runtime.adapter import (
    CallerIdentity,
    CleanupStatus,
    DemonstrationFixtureManager,
    DemonstrationToolAdapter,
    DomainToolAdapter,
    FixtureManager,
    RecoveryActor,
    TargetMode,
    ToolExecutionResult,
    check_real_target_prerequisites,
)
from app.components.c3_robustness_recovery.runtime.evidence import (
    CleanQualification,
    ExecutionStatus,
    ExposureStatus,
    FixtureComparability,
    MatchedPairEvidence,
    ReadinessStatus,
    StateObservationReference,
    TimeoutBoundaryType,
    TrialEvidence,
    TrialRole,
    export_evidence_to_file,
    validate_evidence_linkage,
)
from app.components.c3_robustness_recovery.runtime.interceptor import (
    DomainToolInterceptor,
    InterceptionPlan,
)
from app.components.c3_robustness_recovery.services.validation import (
    validate_fault_case,
)


@dataclass(frozen=True)
class RuntimeReadinessResult:
    """Readiness verdict before trial execution begins."""

    status: ReadinessStatus
    reasons: list[str]


def check_runtime_readiness(
    candidate_case: CandidateFaultCase,
    adapter_manifest: AdapterCapabilityManifest,
    task_fixture_metadata: TaskFixtureMetadata,
    recovery_contract: RecoveryContract,
    adapter: DomainToolAdapter,
    fixture_manager: FixtureManager,
    target_mode: TargetMode,
    caller_identity: CallerIdentity,
) -> RuntimeReadinessResult:
    """Enforce explicit runtime readiness before any target or trial activity."""
    reasons: list[str] = []

    # 1. Existing pure deterministic static validation
    static_request = FaultValidationRequest(
        candidate_case=candidate_case,
        adapter_manifest=adapter_manifest,
        task_fixture_metadata=task_fixture_metadata,
        recovery_contract=recovery_contract,
    )
    static_result = validate_fault_case(static_request)
    if static_result.validation_status != ValidationStatus.STATIC_VALID:
        for r in static_result.reasons:
            reasons.append(f"Static validation failed ({r.code}): {r.message}")

    # 2. Adapter Identity & Version Match
    if adapter.adapter_id != candidate_case.adapter_id:
        reasons.append(
            f"Installed adapter ID '{adapter.adapter_id}' does not match candidate case '{candidate_case.adapter_id}'."
        )
    if adapter.adapter_version != candidate_case.adapter_version:
        reasons.append(
            f"Installed adapter version '{adapter.adapter_version}' does not match candidate case '{candidate_case.adapter_version}'."
        )

    # 3. Fixture Manager Match & Capability
    if fixture_manager.fixture_id != candidate_case.fixture_id:
        reasons.append(
            f"Installed fixture manager ID '{fixture_manager.fixture_id}' does not match candidate case '{candidate_case.fixture_id}'."
        )
    if not task_fixture_metadata.declared_reset_support:
        reasons.append("Task fixture metadata lacks declared reset support.")
    if not task_fixture_metadata.declared_observation_support:
        reasons.append("Task fixture metadata lacks declared observation support.")

    # 4. Phase 3 Scope Constraints: Supported fault families & hooks
    if candidate_case.effect_phase == EffectPhase.BEFORE_EFFECT:
        if candidate_case.interception_hook != InterceptionHook.BEFORE_TOOL_CALL:
            reasons.append(
                f"Interception hook '{candidate_case.interception_hook.value}' is not supported for BEFORE_EFFECT. "
                "Only BEFORE_TOOL_CALL is implemented."
            )

        if candidate_case.fault_family == FaultFamily.TIMEOUT_DISCONNECTION:
            payload_mode = getattr(candidate_case.payload, "mode", None)
            supported_timeout_modes = {
                TimeoutDisconnectionMode.CALLER_TIMEOUT_EXCEEDED,
                TimeoutDisconnectionMode.HANG_INDEFINITELY,
            }
            if payload_mode not in supported_timeout_modes:
                mode_name = payload_mode.value if payload_mode else "unknown"
                reasons.append(
                    f"Timeout mode '{mode_name}' is not supported in runtime. "
                    "Only CALLER_TIMEOUT_EXCEEDED and HANG_INDEFINITELY are implemented. "
                    "SOCKET_DROP and CONNECTION_REFUSED are not silently translated."
                )
        elif candidate_case.fault_family == FaultFamily.TRANSIENT_5XX:
            status_val = getattr(candidate_case.payload, "http_status", 500)
            valid_5xx_codes = {500, 502, 503, 504}
            if status_val not in valid_5xx_codes:
                reasons.append(
                    f"Transient 5xx status '{status_val}' is not supported. Must be one of: {sorted(valid_5xx_codes)}."
                )
        elif candidate_case.fault_family == FaultFamily.RATE_LIMIT_429:
            status_val = getattr(candidate_case.payload, "http_status", 429)
            if status_val != 429:
                reasons.append(
                    f"Rate limit status '{status_val}' is not supported. Only 429 is implemented."
                )
        elif candidate_case.fault_family == FaultFamily.TOOL_UNAVAILABILITY:
            payload_mode = getattr(candidate_case.payload, "mode", None)
            valid_unavail = {
                "CIRCUIT_BROKEN",
                "SERVICE_MAINTENANCE",
                "DEPENDENCY_OFFLINE",
                "RESOURCE_EXHAUSTED",
            }
            mode_val = getattr(payload_mode, "value", str(payload_mode))
            if mode_val not in valid_unavail:
                reasons.append(
                    f"Tool unavailability mode '{mode_val}' is not supported. Must be one of: {sorted(valid_unavail)}."
                )
        elif candidate_case.fault_family == FaultFamily.MALFORMED_RESPONSE:
            payload_mode = getattr(candidate_case.payload, "mode", None)
            valid_malformed = {
                "INVALID_JSON",
                "TRUNCATED_JSON",
                "SCHEMA_VIOLATION",
                "EMPTY_BODY",
                "UNEXPECTED_CONTENT_TYPE",
            }
            mode_val = getattr(payload_mode, "value", str(payload_mode))
            if mode_val not in valid_malformed:
                reasons.append(
                    f"Malformed response mode '{mode_val}' is not supported. Must be one of: {sorted(valid_malformed)}."
                )

        else:
            reasons.append(
                f"Fault family '{candidate_case.fault_family.value}' is not supported for BEFORE_EFFECT in Phase 3."
            )

    elif candidate_case.effect_phase == EffectPhase.AFTER_COMMIT:
        if candidate_case.interception_hook != InterceptionHook.APPLICATION_AWARE_HOOK:
            reasons.append(
                f"Interception hook '{candidate_case.interception_hook.value}' is not supported for AFTER_COMMIT. "
                "Only APPLICATION_AWARE_HOOK is implemented."
            )
        if candidate_case.fault_family != FaultFamily.TIMEOUT_DISCONNECTION:
            reasons.append(
                f"Fault family '{candidate_case.fault_family.value}' is not supported for AFTER_COMMIT. "
                "Only TIMEOUT_DISCONNECTION lost-response delivery is implemented."
            )
        if target_mode == TargetMode.LIVE_AUT:
            reasons.append(
                "Live AFTER_COMMIT lost-response delivery is BLOCKED: actual target hooks and verified "
                "live state interfaces are not available."
            )

    else:
        reasons.append(
            f"Effect phase '{candidate_case.effect_phase.value}' is not supported. "
            "PARTIAL_EFFECT cannot be inferred and is not implemented."
        )

    # 5. Bounded Timing Checks
    if (
        candidate_case.caller_timeout_ms is None
        or candidate_case.caller_timeout_ms <= 0
    ):
        reasons.append(
            "Candidate case caller_timeout_ms must be specified and positive for runtime execution."
        )
    if recovery_contract.max_total_timeout_ms <= 0:
        reasons.append("Recovery contract max_total_timeout_ms must be positive.")

    # 6. Target Mode & Live Prerequisites Check
    if target_mode == TargetMode.LIVE_AUT:
        is_avail, missing = check_real_target_prerequisites()
        if not is_avail:
            for m in missing:
                reasons.append(f"Live AUT prerequisite missing: {m}")
            return RuntimeReadinessResult(
                status=ReadinessStatus.BLOCKED, reasons=reasons
            )

    if reasons:
        return RuntimeReadinessResult(status=ReadinessStatus.NOT_READY, reasons=reasons)

    return RuntimeReadinessResult(status=ReadinessStatus.READY, reasons=[])


# ---------------------------------------------------------------------------
# Scripted Demonstration Caller
# ---------------------------------------------------------------------------


class DemonstrationCaller:
    """Scripted caller simulating the agent/task side of execution.

    Distinguishes its decisions as SCRIPTED_CALLER.
    Does not add harness-level retries; caller behavior is explicitly observed.
    """

    def __init__(
        self,
        adapter: DomainToolAdapter,
        interceptor: DomainToolInterceptor,
        caller_timeout_ms: int,
        allow_scripted_retry: bool = True,
        fixture_manager: FixtureManager | None = None,
    ) -> None:
        self.adapter = adapter
        self.interceptor = interceptor
        self.caller_timeout_ms = caller_timeout_ms
        self.allow_scripted_retry = allow_scripted_retry
        self.fixture_manager = fixture_manager

    async def run_checkout_task(
        self,
        tool_id: str,
        tool_version: str,
        arguments: dict[str, Any],
        namespace: str,
    ) -> tuple[str, list[ToolExecutionResult]]:
        """Run the task invoking the domain tool with caller timeout enforcement."""
        results: list[ToolExecutionResult] = []
        call_context = {
            "namespace": namespace,
            "fixture_manager": self.fixture_manager,
        }

        async def forward_call() -> ToolExecutionResult:
            return await self.adapter.execute_tool(
                tool_id=tool_id,
                tool_version=tool_version,
                arguments=arguments,
                call_context=call_context,
            )

        # Attempt 1
        try:
            res = await self.interceptor.intercept_call(
                tool_id=tool_id,
                tool_version=tool_version,
                arguments=arguments,
                forward_callback=forward_call,
                context=call_context,
            )
            results.append(res)
            if res.success:
                return "SUCCESS", results
            if not self.allow_scripted_retry:
                return f"TOOL_ERROR: {res.error}", results

            # Scripted caller retry on intercepted domain error
            try:
                retry_res = await self.interceptor.intercept_call(
                    tool_id=tool_id,
                    tool_version=tool_version,
                    arguments=arguments,
                    forward_callback=forward_call,
                    context=call_context,
                )
                results.append(retry_res)
                if retry_res.success:
                    return "SUCCESS_AFTER_RETRY", results
                return f"RETRY_FAILED: {retry_res.error}", results
            except Exception as retry_exc:  # noqa: BLE001
                return f"RETRY_FAILED: {type(retry_exc).__name__}", results
        except (TimeoutError, asyncio.CancelledError):
            if not self.allow_scripted_retry:
                return "TIMEOUT_ABORTED", results

            # Scripted caller retry decision (explicitly attributed to SCRIPTED_CALLER)
            try:
                retry_res = await self.interceptor.intercept_call(
                    tool_id=tool_id,
                    tool_version=tool_version,
                    arguments=arguments,
                    forward_callback=forward_call,
                    context=call_context,
                )
                results.append(retry_res)
                if retry_res.success:
                    return "SUCCESS_AFTER_RETRY", results
                return f"RETRY_FAILED: {retry_res.error}", results
            except Exception as retry_exc:  # noqa: BLE001
                return f"RETRY_FAILED: {type(retry_exc).__name__}", results
        except Exception as exc:  # noqa: BLE001
            if not self.allow_scripted_retry:
                return f"ERROR: {type(exc).__name__}", results
            try:
                retry_res = await self.interceptor.intercept_call(
                    tool_id=tool_id,
                    tool_version=tool_version,
                    arguments=arguments,
                    forward_callback=forward_call,
                    context=call_context,
                )
                results.append(retry_res)
                if retry_res.success:
                    return "SUCCESS_AFTER_RETRY", results
                return f"RETRY_FAILED: {retry_res.error}", results
            except Exception as retry_exc:  # noqa: BLE001
                return f"RETRY_FAILED: {type(retry_exc).__name__}", results


# ---------------------------------------------------------------------------
# Matched Pair Execution Runner
# ---------------------------------------------------------------------------


class HarnessRunner:
    """Executes matched clean control and fault trials under isolated fixtures."""

    def __init__(
        self,
        adapter: DomainToolAdapter,
        fixture_manager: FixtureManager,
    ) -> None:
        self.adapter = adapter
        self.fixture_manager = fixture_manager

    async def run_matched_pair(
        self,
        candidate_case: CandidateFaultCase,
        adapter_manifest: AdapterCapabilityManifest,
        task_fixture_metadata: TaskFixtureMetadata,
        recovery_contract: RecoveryContract,
        target_mode: TargetMode = TargetMode.DEMONSTRATION,
        caller_identity: CallerIdentity = CallerIdentity.SCRIPTED_CALLER,
        allow_scripted_retry: bool = True,
    ) -> MatchedPairEvidence:
        pair_id = f"pair-{uuid4().hex[:8]}"
        run_id = f"run-{uuid4().hex[:8]}"
        project_id = candidate_case.project_id
        case_id = candidate_case.case_id

        # 1. Runtime Readiness Check
        readiness = check_runtime_readiness(
            candidate_case=candidate_case,
            adapter_manifest=adapter_manifest,
            task_fixture_metadata=task_fixture_metadata,
            recovery_contract=recovery_contract,
            adapter=self.adapter,
            fixture_manager=self.fixture_manager,
            target_mode=target_mode,
            caller_identity=caller_identity,
        )

        # Freeze non-secret configuration snapshot
        config_snapshot = {
            "candidate_case": candidate_case.model_dump(mode="json"),
            "adapter_id": self.adapter.adapter_id,
            "adapter_version": self.adapter.adapter_version,
            "fixture_id": self.fixture_manager.fixture_id,
            "fixture_version": self.fixture_manager.fixture_version,
            "target_mode": target_mode.value,
            "caller_identity": caller_identity.value,
            "allow_scripted_retry": allow_scripted_retry,
            "timestamp": time.time(),
        }

        # Gap C: If readiness check fails, return linked unexecuted pair evidence
        # with cleanup_status = NOT_ASSESSED and exposure_assessed = False
        if readiness.status != ReadinessStatus.READY:
            empty_clean = TrialEvidence(
                project_id=project_id,
                case_id=case_id,
                pair_id=pair_id,
                trial_id=f"tr-clean-{uuid4().hex[:8]}",
                run_id=run_id,
                trial_role=TrialRole.CLEAN,
                target_mode=target_mode,
                caller_identity=caller_identity,
                recovery_actor=RecoveryActor.UNKNOWN,
                fixture_namespace="uninitialized",
                initial_state_fingerprint="",
                final_state_fingerprint="",
                execution_status=ExecutionStatus.EXECUTION_ERROR,
                caller_outcome="NOT_RUN",
                cleanup_status=CleanupStatus.NOT_ASSESSED,
                evidence_complete=False,
            )
            empty_fault = TrialEvidence(
                project_id=project_id,
                case_id=case_id,
                pair_id=pair_id,
                trial_id=f"tr-fault-{uuid4().hex[:8]}",
                run_id=run_id,
                trial_role=TrialRole.FAULT,
                target_mode=target_mode,
                caller_identity=caller_identity,
                recovery_actor=RecoveryActor.UNKNOWN,
                fixture_namespace="uninitialized",
                initial_state_fingerprint="",
                final_state_fingerprint="",
                execution_status=ExecutionStatus.EXECUTION_ERROR,
                caller_outcome="NOT_RUN",
                cleanup_status=CleanupStatus.NOT_ASSESSED,
                evidence_complete=False,
            )
            return MatchedPairEvidence(
                project_id=project_id,
                case_id=case_id,
                pair_id=pair_id,
                run_id=run_id,
                readiness_status=readiness.status,
                readiness_reasons=readiness.reasons,
                target_mode=target_mode,
                caller_identity=caller_identity,
                configuration_snapshot=config_snapshot,
                clean_trial=empty_clean,
                fault_trial=empty_fault,
                fixture_comparability=FixtureComparability.UNKNOWN,
                clean_qualification=CleanQualification.UNKNOWN,
                exposure_status=ExposureStatus.NOT_TRIGGERED,
                exposure_reasons=["Execution blocked by runtime readiness check."],
                cleanup_status=CleanupStatus.NOT_ASSESSED,
                exposure_assessed=False,
                recovery_verdict=None,
                interpretation_limitations=[
                    "Trial was not run due to readiness failure."
                ],
            )

        # -------------------------------------------------------------------
        # Step 1: Clean Control Trial (Injection Disabled)
        # -------------------------------------------------------------------
        clean_trial_id = f"tr-clean-{uuid4().hex[:8]}"
        clean_namespace = f"ns_{pair_id}_clean_{uuid4().hex[:6]}"

        clean_start_state = self.fixture_manager.prepare_fixture(clean_namespace)
        clean_start_fp = self.fixture_manager.compute_state_fingerprint(
            clean_start_state
        )

        clean_interceptor = DomainToolInterceptor(
            trial_id=clean_trial_id,
            plan=None,  # No plan = injection disabled
        )
        clean_caller = DemonstrationCaller(
            adapter=self.adapter,
            interceptor=clean_interceptor,
            caller_timeout_ms=candidate_case.caller_timeout_ms or 3000,
            allow_scripted_retry=False,
            fixture_manager=self.fixture_manager,
        )

        task_args = {
            "item_id": "item-demo-001",
            "quantity": 1,
            "unit_price": 100,
        }

        clean_outcome, clean_results = await clean_caller.run_checkout_task(
            tool_id=candidate_case.tool_id,
            tool_version=candidate_case.tool_version,
            arguments=task_args,
            namespace=clean_namespace,
        )

        clean_final_state = self.fixture_manager.observe_state(clean_namespace)
        clean_final_fp = self.fixture_manager.compute_state_fingerprint(
            clean_final_state
        )

        # Clean qualification: verify side effects occurred as expected
        clean_qualification = CleanQualification.UNKNOWN
        clean_effects: list[str] = []
        if (
            clean_outcome == "SUCCESS"
            and len(clean_results) == 1
            and clean_results[0].success
        ):
            if clean_final_state.get("order_count", 0) == 1:
                clean_qualification = CleanQualification.QUALIFIED
                clean_effects.append("order_confirmed_in_clean")
            else:
                clean_qualification = CleanQualification.DISQUALIFIED
        else:
            clean_qualification = CleanQualification.DISQUALIFIED

        clean_cleanup = self.fixture_manager.cleanup(clean_namespace)
        clean_interceptor.close()

        clean_snapshot_id = f"snap-{clean_trial_id[:8]}"
        clean_entity_id = clean_final_state.get("customer_id")
        if clean_final_state.get("orders"):
            clean_entity_id = (
                clean_final_state["orders"][0].get("order_id") or clean_entity_id
            )

        clean_obs_ref = StateObservationReference(
            snapshot_id=clean_snapshot_id,
            snapshot_version="1.0.0",
            entity_id=clean_entity_id or "cust-demo-100",
            observation_scope="clean_baseline",
            fingerprint=clean_final_fp,
        )

        clean_trial_evidence = TrialEvidence(
            project_id=project_id,
            case_id=case_id,
            pair_id=pair_id,
            trial_id=clean_trial_id,
            run_id=run_id,
            trial_role=TrialRole.CLEAN,
            target_mode=target_mode,
            caller_identity=caller_identity,
            recovery_actor=RecoveryActor.SCRIPTED_CALLER,
            fixture_namespace=clean_namespace,
            initial_state_fingerprint=clean_start_fp,
            final_state_fingerprint=clean_final_fp,
            events=clean_interceptor.events,
            episodes=[],
            tool_calls_count=len(clean_results),
            subsequent_calls_count=0,
            observed_effects=clean_effects,
            execution_status=ExecutionStatus.COMPLETED,
            caller_outcome=clean_outcome,
            cleanup_status=clean_cleanup.status,
            evidence_complete=True,
            snapshot_id=clean_snapshot_id,
            observed_entity_id=clean_entity_id or "cust-demo-100",
            observation_reference=clean_obs_ref,
        )

        # -------------------------------------------------------------------
        # Step 2: Fresh Equivalent Fixture for Fault Trial
        # -------------------------------------------------------------------
        fault_trial_id = f"tr-fault-{uuid4().hex[:8]}"
        fault_namespace = f"ns_{pair_id}_fault_{uuid4().hex[:6]}"

        fault_start_state = self.fixture_manager.prepare_fixture(fault_namespace)
        fault_start_fp = self.fixture_manager.compute_state_fingerprint(
            fault_start_state
        )

        fixture_comparability = (
            FixtureComparability.EQUIVALENT_LOGICAL_STATE
            if fault_start_fp == clean_start_fp
            else FixtureComparability.NON_EQUIVALENT
        )

        # -------------------------------------------------------------------
        # Step 3: Fault Trial with One Targeted Episode
        # -------------------------------------------------------------------
        payload_mode = getattr(
            candidate_case.payload,
            "mode",
            TimeoutDisconnectionMode.CALLER_TIMEOUT_EXCEEDED,
        )
        fault_plan = InterceptionPlan(
            trial_id=fault_trial_id,
            target_tool_id=candidate_case.tool_id,
            target_occurrence=candidate_case.occurrence,
            interception_hook=candidate_case.interception_hook,
            effect_phase=candidate_case.effect_phase,
            fault_family=candidate_case.fault_family,
            fault_mode=payload_mode,
            caller_timeout_ms=candidate_case.caller_timeout_ms or 3000,
            fault_timing_ms=getattr(candidate_case.payload, "timing_ms", None),
            timeout_boundary_type=TimeoutBoundaryType.CALLER_TIMEOUT_EXCEEDED,
            payload_details=(
                candidate_case.payload.model_dump(mode="json")
                if hasattr(candidate_case.payload, "model_dump")
                else {}
            ),
        )

        fault_interceptor = DomainToolInterceptor(
            trial_id=fault_trial_id, plan=fault_plan
        )
        fault_caller = DemonstrationCaller(
            adapter=self.adapter,
            interceptor=fault_interceptor,
            caller_timeout_ms=candidate_case.caller_timeout_ms or 3000,
            allow_scripted_retry=allow_scripted_retry,
            fixture_manager=self.fixture_manager,
        )

        fault_outcome, fault_results = await fault_caller.run_checkout_task(
            tool_id=candidate_case.tool_id,
            tool_version=candidate_case.tool_version,
            arguments=task_args,
            namespace=fault_namespace,
        )

        fault_final_state = self.fixture_manager.observe_state(fault_namespace)
        fault_final_fp = self.fixture_manager.compute_state_fingerprint(
            fault_final_state
        )

        fault_cleanup = self.fixture_manager.cleanup(fault_namespace)
        fault_interceptor.close()

        fault_effects: list[str] = []
        if fault_final_state.get("order_count", 0) > 0:
            fault_effects.append("order_created_on_subsequent_call")

        recovery_actor = (
            RecoveryActor.SCRIPTED_CALLER
            if allow_scripted_retry and fault_outcome == "SUCCESS_AFTER_RETRY"
            else RecoveryActor.UNKNOWN
        )

        fault_snapshot_id = f"snap-{fault_trial_id[:8]}"
        fault_entity_id = fault_final_state.get("customer_id")
        if fault_final_state.get("orders"):
            fault_entity_id = (
                fault_final_state["orders"][0].get("order_id") or fault_entity_id
            )

        fault_obs_ref = StateObservationReference(
            snapshot_id=fault_snapshot_id,
            snapshot_version="1.0.0",
            entity_id=fault_entity_id or "cust-demo-100",
            observation_scope="post_recovery",
            fingerprint=fault_final_fp,
        )

        fault_trial_evidence = TrialEvidence(
            project_id=project_id,
            case_id=case_id,
            pair_id=pair_id,
            trial_id=fault_trial_id,
            run_id=run_id,
            trial_role=TrialRole.FAULT,
            target_mode=target_mode,
            caller_identity=caller_identity,
            recovery_actor=recovery_actor,
            fixture_namespace=fault_namespace,
            initial_state_fingerprint=fault_start_fp,
            final_state_fingerprint=fault_final_fp,
            events=fault_interceptor.events,
            episodes=fault_interceptor.episode_records,
            tool_calls_count=(
                len(fault_results)
                if len(fault_results) > 1
                else (
                    2
                    if (
                        fault_interceptor.is_consumed
                        and fault_outcome
                        in ("SUCCESS_AFTER_RETRY", "RETRY_FAILED")
                    )
                    else len(fault_results)
                )
            ),
            subsequent_calls_count=(
                len(fault_results) - 1
                if len(fault_results) > 1
                else (
                    1
                    if (
                        fault_interceptor.is_consumed
                        and fault_outcome
                        in ("SUCCESS_AFTER_RETRY", "RETRY_FAILED")
                    )
                    else 0
                )
            ),
            observed_effects=fault_effects,
            execution_status=ExecutionStatus.COMPLETED,
            caller_outcome=fault_outcome,
            cleanup_status=fault_cleanup.status,
            evidence_complete=True,
            snapshot_id=fault_snapshot_id,
            observed_entity_id=fault_entity_id or "cust-demo-100",
            observation_reference=fault_obs_ref,
        )

        # -------------------------------------------------------------------
        # Step 4: Correlated Exposure Evaluation
        # -------------------------------------------------------------------
        exposure_status, exposure_reasons = self._evaluate_exposure(
            fault_trial=fault_trial_evidence,
            plan=fault_plan,
        )

        interpretation_limitations: list[str] = []
        if clean_qualification != CleanQualification.QUALIFIED:
            interpretation_limitations.append(
                f"Clean control trial was not qualified (status: {clean_qualification.value}). "
                "Differential comparison with baseline is limited, though exposure is evaluated independently."
            )
        if fixture_comparability != FixtureComparability.EQUIVALENT_LOGICAL_STATE:
            interpretation_limitations.append(
                "Clean and fault trials did not start with identical logical fingerprints."
            )

        pair_evidence = MatchedPairEvidence(
            project_id=project_id,
            case_id=case_id,
            pair_id=pair_id,
            run_id=run_id,
            readiness_status=ReadinessStatus.READY,
            readiness_reasons=[],
            target_mode=target_mode,
            caller_identity=caller_identity,
            configuration_snapshot=config_snapshot,
            clean_trial=clean_trial_evidence,
            fault_trial=fault_trial_evidence,
            fixture_comparability=fixture_comparability,
            clean_qualification=clean_qualification,
            exposure_status=exposure_status,
            exposure_reasons=exposure_reasons,
            cleanup_status=(
                CleanupStatus.CLEANED_AND_VERIFIED
                if (
                    clean_cleanup.status == CleanupStatus.CLEANED_AND_VERIFIED
                    and fault_cleanup.status == CleanupStatus.CLEANED_AND_VERIFIED
                )
                else CleanupStatus.UNCERTAIN
            ),
            exposure_assessed=True,
            recovery_verdict=None,  # Always null
            interpretation_limitations=interpretation_limitations,
        )

        validate_evidence_linkage(pair_evidence)
        return pair_evidence

    def _evaluate_exposure(
        self,
        fault_trial: TrialEvidence,
        plan: InterceptionPlan,
    ) -> tuple[ExposureStatus, list[str]]:
        """Evaluate whether exposure occurred using correlated runtime evidence."""
        reasons: list[str] = []

        if not fault_trial.episodes:
            # Check actual per-tool occurrences reached for plan.target_tool_id
            target_tool_events = [
                ev for ev in fault_trial.events if ev.tool_id == plan.target_tool_id
            ]
            reached_occurrences = {
                ev.occurrence
                for ev in target_tool_events
                if getattr(ev, "occurrence", None) is not None
            }
            max_reached_occurrence = max(reached_occurrences, default=0)

            # If target occurrence was never reached by the targeted tool, it is NOT_TRIGGERED
            if (
                plan.target_occurrence > max_reached_occurrence
                or plan.target_occurrence not in reached_occurrences
            ):
                return (
                    ExposureStatus.NOT_TRIGGERED,
                    [
                        f"Target tool '{plan.target_tool_id}' was not invoked at planned occurrence {plan.target_occurrence} "
                        f"(maximum observed occurrence: {max_reached_occurrence})."
                    ],
                )

            # Selected occurrence was reached, but no fault episode or delivery receipts were recorded
            return (
                ExposureStatus.EXPOSURE_UNKNOWN,
                [
                    f"Target tool '{plan.target_tool_id}' reached occurrence {plan.target_occurrence}, "
                    "but no fault episode or delivery evidence was recorded in the trial trace."
                ],
            )

        episode = fault_trial.episodes[0]

        # Verify correlated facts
        if episode.target_tool_id != plan.target_tool_id:
            reasons.append(
                f"Episode tool ID '{episode.target_tool_id}' != planned '{plan.target_tool_id}'."
            )
        if episode.target_occurrence != plan.target_occurrence:
            reasons.append(
                f"Episode occurrence {episode.target_occurrence} != planned {plan.target_occurrence}."
            )
        if episode.interception_hook != plan.interception_hook:
            reasons.append(
                f"Episode hook '{episode.interception_hook.value}' != planned '{plan.interception_hook.value}'."
            )
        if episode.effect_phase != plan.effect_phase:
            reasons.append(
                f"Episode phase '{episode.effect_phase.value}' != planned '{plan.effect_phase.value}'."
            )

        # Family & Phase specific exposure verification
        if plan.effect_phase == EffectPhase.BEFORE_EFFECT:
            if not episode.prevented_forwarding:
                reasons.append("Episode failed to prevent forwarding to target.")

            if plan.fault_family == FaultFamily.TIMEOUT_DISCONNECTION:
                if not episode.caller_observed_timeout:
                    reasons.append(
                        "Caller did not observe the intended timeout boundary (e.g. premature cancellation)."
                    )
                # Gap B check: Caller must actually experience timeout
                if fault_trial.caller_outcome == "SUCCESS":
                    reasons.append(
                        "Caller reported SUCCESS on the first attempt without experiencing timeout."
                    )
            elif plan.fault_family == FaultFamily.TRANSIENT_5XX:
                if episode.fault_status_code not in (500, 502, 503, 504):
                    reasons.append(
                        f"Episode status code {episode.fault_status_code} is not a valid 5xx code."
                    )
                if fault_trial.caller_outcome == "SUCCESS":
                    reasons.append(
                        "Caller reported SUCCESS despite 5xx transient fault."
                    )
            elif plan.fault_family == FaultFamily.RATE_LIMIT_429:
                if episode.fault_status_code != 429:
                    reasons.append(
                        f"Episode status code {episode.fault_status_code} != 429 for rate limit fault."
                    )
                if fault_trial.caller_outcome == "SUCCESS":
                    reasons.append(
                        "Caller reported SUCCESS despite 429 rate limit fault."
                    )
            elif plan.fault_family == FaultFamily.TOOL_UNAVAILABILITY:
                if not episode.unavailability_mode:
                    reasons.append("Episode missing unavailability_mode.")
                if fault_trial.caller_outcome == "SUCCESS":
                    reasons.append(
                        "Caller reported SUCCESS despite tool unavailability fault."
                    )
            elif plan.fault_family == FaultFamily.MALFORMED_RESPONSE:
                if not episode.malformed_fragment:
                    reasons.append("Episode missing malformed_fragment evidence.")
                if fault_trial.caller_outcome == "SUCCESS":
                    reasons.append(
                        "Caller reported SUCCESS despite malformed response fault."
                    )
                # Verify caller-observed failure reached consumption boundary
                if (
                    "JSONDecodeError" not in fault_trial.caller_outcome
                    and "SchemaValidationError" not in fault_trial.caller_outcome
                    and "MALFORMED" not in fault_trial.caller_outcome
                    and "ERROR" not in fault_trial.caller_outcome
                    and "RETRY_FAILED" not in fault_trial.caller_outcome
                    and "TIMEOUT_ABORTED" not in fault_trial.caller_outcome
                ):
                    reasons.append(
                        f"Caller did not observe parser/schema failure at consumption boundary (outcome: {fault_trial.caller_outcome})."
                    )

        elif plan.effect_phase == EffectPhase.AFTER_COMMIT:
            if not episode.independent_observation_confirmed:
                reasons.append(
                    "Missing commit observation prevented confirmed post-commit exposure: "
                    "independent observation could not confirm that the operation committed before withholding reply."
                )
            if not episode.committed_operation_id:
                reasons.append("Episode missing committed_operation_id.")
            if not episode.caller_observed_timeout:
                reasons.append("Caller did not observe the lost-response timeout.")
            if fault_trial.caller_outcome == "SUCCESS":
                reasons.append(
                    "Caller reported SUCCESS on first attempt without lost-response timeout."
                )

            # Causal event sequence verification
            event_types = [e.event_type for e in fault_trial.events]
            hook_idx = next(
                (
                    i
                    for i, t in enumerate(event_types)
                    if t == "APPLICATION_AWARE_HOOK_ENTERED"
                ),
                -1,
            )
            obs_idx = next(
                (
                    i
                    for i, t in enumerate(event_types)
                    if t == "INDEPENDENT_COMMIT_OBSERVATION"
                ),
                -1,
            )
            withhold_idx = next(
                (
                    i
                    for i, t in enumerate(event_types)
                    if t == "POST_COMMIT_REPLY_WITHHELD"
                ),
                -1,
            )

            if hook_idx == -1:
                reasons.append("Missing APPLICATION_AWARE_HOOK_ENTERED event.")
            if obs_idx == -1:
                reasons.append("Missing INDEPENDENT_COMMIT_OBSERVATION event.")
            if withhold_idx == -1:
                reasons.append("Missing POST_COMMIT_REPLY_WITHHELD event.")

            if (
                hook_idx != -1
                and obs_idx != -1
                and withhold_idx != -1
                and not (hook_idx < obs_idx < withhold_idx)
            ):
                reasons.append(
                    f"Contradictory event order in trial: hook ({hook_idx}) -> observation ({obs_idx}) -> withholding ({withhold_idx}). "
                    "Expected causal ordering: hook < observation < withholding."
                )

        if reasons:
            return ExposureStatus.EXPOSURE_UNKNOWN, reasons

        return ExposureStatus.CONFIRMED, [
            (
                f"Correlated evidence confirms {plan.interception_hook.value} hook entry, "
                f"delivery for {plan.fault_family.value} ({plan.effect_phase.value}), and caller-observed outcome."
            )
        ]


# ---------------------------------------------------------------------------
# Developer CLI Entrypoint
# ---------------------------------------------------------------------------


def make_demonstration_candidate_case() -> CandidateFaultCase:
    from app.components.c3_robustness_recovery.contracts.schemas import (
        CandidateFaultCase,
        ReleaseRule,
        ReleaseRuleType,
        TimeoutDisconnectionPayload,
    )

    return CandidateFaultCase(
        schema_version="1.0.0",
        project_id="proj-demo-qa",
        case_id="case-c3-demo-001",
        case_family_id="fam-timeout-demo",
        domain="ecommerce",
        task_id="task-checkout-demo",
        task_version="1.0.0",
        tool_id="demonstration_order_placement",
        tool_version="1.0.0",
        fixture_id="fix-demonstration-cart",
        fixture_version="1.0.0",
        adapter_id="adapter-demonstration-c3",
        adapter_version="1.0.0",
        recovery_contract_id="rec-demo-01",
        recovery_contract_version="1.0.0",
        occurrence=1,
        interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
        fault_family=FaultFamily.TIMEOUT_DISCONNECTION,
        effect_phase=EffectPhase.BEFORE_EFFECT,
        payload=TimeoutDisconnectionPayload(
            mode=TimeoutDisconnectionMode.CALLER_TIMEOUT_EXCEEDED,
            timing_ms=50,  # Fast hermetic delay for tests/CLI
        ),
        release_rule=ReleaseRule(
            rule_type=ReleaseRuleType.ATTEMPT_BOUNDED,
            max_fault_count=1,
        ),
        required_assertions=["state_order_created"],
        required_observations=["caller_timeout_observed"],
        caller_timeout_ms=20,  # 20ms caller timeout < 50ms timing_ms
    )


def make_demonstration_task_fixture_metadata() -> TaskFixtureMetadata:
    return TaskFixtureMetadata(
        task_id="task-checkout-demo",
        task_version="1.0.0",
        fixture_id="fix-demonstration-cart",
        fixture_version="1.0.0",
        domain="ecommerce",
        associated_tool_ids=["demonstration_order_placement"],
        associated_recovery_contract_ids=["rec-demo-01"],
        declared_reset_support=True,
        declared_observation_support=True,
        supports_committed_effect_observation=True,
        supported_observations=[
            "caller_timeout_observed",
            "transient_5xx_observed",
            "rate_limit_observed",
            "unavailability_observed",
            "malformed_observed",
            "committed_order_verified",
        ],
    )


def make_demonstration_recovery_contract() -> RecoveryContract:
    from app.components.c3_robustness_recovery.contracts.schemas import TerminalOutcome

    return RecoveryContract(
        contract_id="rec-demo-01",
        contract_version="1.0.0",
        permitted_terminal_outcomes=[TerminalOutcome.SUCCESS_CLEAN_RECOVERY],
        initial_invocation_counts_as_attempt=True,
        max_task_attempts=2,
        max_retries=1,
        max_tool_calls_budget=5,
        max_total_timeout_ms=5000,
        required_state_assertions=["state_order_created"],
        allow_duplicate_side_effects=False,
        allow_retry_on_unverified_commit=True,
        require_truthful_completion_reporting=True,
    )


async def main_async(args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Component 3 Phase 2 Matched Trial Runner and CLI"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--synthetic",
        action="store_true",
        help="Run hermetic matched trials with generic demonstration adapter.",
    )
    group.add_argument(
        "--live",
        action="store_true",
        help="Attempt execution against live target AUT (NexaCart).",
    )
    parser.add_argument(
        "--export-dir",
        default="evidence_output",
        help="Directory to save exported JSON evidence (defaults to evidence_output).",
    )
    parser.add_argument(
        "--no-retry",
        action="store_true",
        help="Disable scripted caller retry on timeout.",
    )

    parsed = parser.parse_args(args)

    fixture_mgr = DemonstrationFixtureManager()
    adapter = DemonstrationToolAdapter(fixture_manager=fixture_mgr)
    runner = HarnessRunner(adapter=adapter, fixture_manager=fixture_mgr)

    candidate_case = make_demonstration_candidate_case()
    manifest = adapter.get_manifest()
    metadata = make_demonstration_task_fixture_metadata()
    recovery = make_demonstration_recovery_contract()

    target_mode = TargetMode.LIVE_AUT if parsed.live else TargetMode.DEMONSTRATION

    print(
        f"[C3 Phase 2 Runner] Mode: {target_mode.value} | Case: {candidate_case.case_id}"
    )

    try:
        evidence = await runner.run_matched_pair(
            candidate_case=candidate_case,
            adapter_manifest=manifest,
            task_fixture_metadata=metadata,
            recovery_contract=recovery,
            target_mode=target_mode,
            caller_identity=CallerIdentity.SCRIPTED_CALLER,
            allow_scripted_retry=not parsed.no_retry,
        )

        # Output Summary
        print("--------------------------------------------------")
        print(f"Readiness:            {evidence.readiness_status.value}")
        if evidence.readiness_reasons:
            for r in evidence.readiness_reasons:
                print(f"  - {r}")
        print(f"Exposure Status:      {evidence.exposure_status.value}")
        for r in evidence.exposure_reasons:
            print(f"  - {r}")
        print(f"Clean Qualification:  {evidence.clean_qualification.value}")
        print(f"Fixture Comparability:{evidence.fixture_comparability.value}")
        print(f"Cleanup Status:       {evidence.cleanup_status.value}")
        print(f"Recovery Verdict:     {evidence.recovery_verdict} (deferred)")
        print("--------------------------------------------------")

        if evidence.readiness_status in (
            ReadinessStatus.BLOCKED,
            ReadinessStatus.NOT_READY,
        ):
            print(
                f"[C3 Phase 2 Runner] Execution blocked or not ready: {evidence.readiness_status.value}"
            )
            return 2  # Blocked / Configuration error code

        # Export evidence if directory specified
        export_path = export_evidence_to_file(evidence, export_dir=parsed.export_dir)
        print(f"[C3 Phase 2 Runner] Exported evidence to: {export_path}")

        # Exit 0 for successful harness execution, even when an expected injected tool timeout occurred
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[C3 Phase 2 Runner] EXECUTION ERROR: {exc}", file=sys.stderr)
        return 1


def main() -> None:
    code = asyncio.run(main_async(sys.argv[1:]))
    sys.exit(code)


if __name__ == "__main__":
    main()
