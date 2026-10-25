"""Live matched-trial runner for frozen C3 suites on NexaCart.

Component: C3 - Robustness and Failure Recovery Testing

Each case runs as a clean trial and a fault trial, each on its own fresh NexaCart harness fixture,
with the same task instruction and NexaCart's own LLM agent (the caller is the actual agent, not
a script). The NexaCart fault gateway delivers the single declared fault and returns an exposure
receipt; exposure, effect phase and the committed effect are confirmed from the receipt and the
harness snapshots. C2 facts are obtained through the C2 assertion bridge on the fault trial, and
the frozen recovery contract is evaluated deterministically.

Nothing is simulated: if NexaCart, the harness or the agent are unavailable, cases are reported
BLOCKED or ERROR and receive no recovery verdict.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.components.c3_robustness_recovery.contracts.evaluation import (
    C2AssertionFact,
    RecoveryEvaluationRequest,
    RecoveryEvaluationResult,
)
from app.components.c3_robustness_recovery.contracts.generation import FrozenSuite
from app.components.c3_robustness_recovery.contracts.schemas import (
    CandidateFaultCase,
    FaultValidationRequest,
    ValidationStatus,
)
from app.components.c3_robustness_recovery.examples.nexacart_recovery import (
    NEXACART_ADAPTER_ID,
    NEXACART_TASKS,
    NexaCartRecoveryTask,
    build_nexacart_adapter_manifest,
)
from app.components.c3_robustness_recovery.runtime.evidence import (
    ExposureStatus,
    MatchedPairEvidence,
    validate_evidence_linkage,
)
from app.components.c3_robustness_recovery.services.c2_facts import (
    normalize_c2_to_c3_mappings,
)
from app.components.c3_robustness_recovery.services.recovery_evaluation import (
    evaluate_recovery,
)
from app.components.c3_robustness_recovery.services.suites import (
    compute_semantic_case_fingerprint,
    verify_suite_integrity,
)
from app.components.c3_robustness_recovery.services.terminal_outcome import (
    classify_live_trace,
)
from app.components.c3_robustness_recovery.services.validation import (
    validate_fault_case,
)
from app.shared.integration.adapters import ExecutionTrace, LiveNexaCartTargetAdapter
from app.shared.integration.evidence import project_c3_matched_pair_evidence

# Gateway family names used by LiveNexaCartTargetAdapter
_C3_TO_GATEWAY_FAMILY = {
    "TOOL_UNAVAILABILITY": "TOOL_UNAVAILABLE",
    "MALFORMED_RESPONSE": "MALFORMED_OUTPUT",
}


@dataclass
class LiveCaseResult:
    """Outcome of one case: evidence, C2 facts and the recovery evaluation (when eligible)."""

    case_id: str
    status: str  # "EXECUTED", "BLOCKED", "UNSUPPORTED", "CANCELLED", "ERROR"
    evidence: MatchedPairEvidence | None = None
    c2_facts: list[C2AssertionFact] = field(default_factory=list)
    evaluation: RecoveryEvaluationResult | None = None
    reasons: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    repetition: int = 1


def task_for_suite(suite: FrozenSuite) -> NexaCartRecoveryTask | None:
    return NEXACART_TASKS.get(suite.task_fixture_metadata.task_id)


def fault_hook_for_case(case: CandidateFaultCase) -> dict[str, Any]:
    """The fault profile sent to the NexaCart gateway for one frozen case."""
    return {
        "target_tool": case.tool_id,
        "occurrence": case.occurrence,
        "fault_family": _C3_TO_GATEWAY_FAMILY.get(
            case.fault_family.value, case.fault_family.value
        ),
        "effect_phase": case.effect_phase.value,
        "interception_hook": case.interception_hook.value,
        "max_faults": case.release_rule.max_fault_count,
        "retry_after_seconds": getattr(case.payload, "retry_after_seconds", None),
    }


class NexaCartLiveSuiteRunner:
    """Runs frozen NexaCart suites as live matched clean/fault trial pairs."""

    def __init__(
        self,
        adapter: LiveNexaCartTargetAdapter | None = None,
        max_suite_duration_sec: float = 3600.0,
        quiet_window_sec: float = 0.0,
    ) -> None:
        self.adapter = adapter or LiveNexaCartTargetAdapter()
        self.max_suite_duration_sec = max_suite_duration_sec
        self.quiet_window_sec = quiet_window_sec
        self.live_capabilities: dict[str, Any] | None = None

    # -- readiness -----------------------------------------------------------

    def check_suite_readiness(self, suite: FrozenSuite) -> list[str]:
        """Reasons the suite cannot run live (empty when ready). Creates no NexaCart data."""
        reasons: list[str] = []
        try:
            verify_suite_integrity(suite)
        except ValueError as exc:
            return [f"Suite integrity verification failed: {exc}"]
        if suite.adapter_manifest.adapter_id != NEXACART_ADAPTER_ID:
            reasons.append(
                f"Suite adapter '{suite.adapter_manifest.adapter_id}' is not the NexaCart QA harness "
                f"('{NEXACART_ADAPTER_ID}')."
            )
        if task_for_suite(suite) is None:
            reasons.append(
                f"No registered NexaCart task definition for task '{suite.task_fixture_metadata.task_id}'."
            )
        status, target_reasons = self.adapter.check_readiness()
        if status.value != "READY":
            reasons.extend(target_reasons)
            return reasons
        try:
            self.live_capabilities = self.adapter.client.get_capabilities()
        except Exception as exc:  # noqa: BLE001
            reasons.append(f"NexaCart harness capabilities unavailable: {exc}")
            return reasons
        live_manifest = build_nexacart_adapter_manifest(self.live_capabilities)
        if live_manifest.adapter_version != suite.adapter_manifest.adapter_version:
            reasons.append(
                f"Installed NexaCart harness version '{live_manifest.adapter_version}' differs from the "
                f"frozen suite's '{suite.adapter_manifest.adapter_version}'."
            )
        return reasons

    def check_case_readiness(
        self, case: CandidateFaultCase, suite: FrozenSuite
    ) -> list[str]:
        """Re-validate the frozen case against the manifest built from the live harness."""
        if self.live_capabilities is None:
            return ["Live harness capabilities were not loaded."]
        live_manifest = build_nexacart_adapter_manifest(self.live_capabilities)
        result = validate_fault_case(
            FaultValidationRequest(
                candidate_case=case,
                adapter_manifest=live_manifest,
                task_fixture_metadata=suite.task_fixture_metadata,
                recovery_contract=suite.recovery_contract,
            )
        )
        if result.validation_status != ValidationStatus.STATIC_VALID:
            return [
                f"Live capability check failed ({r.code}): {r.message}"
                for r in result.reasons
            ]
        return []

    # -- execution -----------------------------------------------------------

    def _run_trial(
        self,
        namespace: str,
        task: NexaCartRecoveryTask,
        role: str,
        fault_hook: dict[str, Any] | None,
    ) -> ExecutionTrace:
        self.adapter.prepare_fixture(
            namespace, {"nexacart_fixture": task.fixture_definition}
        )
        try:
            trace = self.adapter.execute_session(
                namespace=namespace,
                task_prompt=task.instruction,
                permitted_tools=task.associated_tool_ids,
                fault_injection_hook=fault_hook,
                trial_role=role,
            )
        finally:
            cleaned, reusable = self.adapter.cleanup_fixture(namespace)
        trace.cleanup_successful = cleaned
        trace.cleanup_reusable = reusable
        return classify_live_trace(trace, task.outcome_rules)

    def run_case(
        self,
        case: CandidateFaultCase,
        suite: FrozenSuite,
        project_id: str,
        run_id: str,
        repetition: int = 1,
        repetitions: int = 1,
    ) -> LiveCaseResult:
        start = time.perf_counter()
        task = task_for_suite(suite)
        if task is None:
            return LiveCaseResult(
                case.case_id, "BLOCKED", reasons=["Unknown NexaCart task."]
            )

        not_ready = self.check_case_readiness(case, suite)
        if not_ready:
            return LiveCaseResult(
                case.case_id,
                "UNSUPPORTED",
                reasons=not_ready,
                duration_ms=(time.perf_counter() - start) * 1000.0,
            )

        pair_id = f"pair-{uuid4().hex[:12]}"
        fault_hook = fault_hook_for_case(case)
        try:
            clean_trace = self._run_trial(f"c3-{pair_id}-clean", task, "CLEAN", None)
            if self.quiet_window_sec:
                time.sleep(self.quiet_window_sec)
            fault_trace = self._run_trial(
                f"c3-{pair_id}-fault", task, "FAULT", fault_hook
            )
        except Exception as exc:  # noqa: BLE001
            return LiveCaseResult(
                case.case_id,
                "ERROR",
                reasons=[f"Live NexaCart trial failed: {exc}"],
                duration_ms=(time.perf_counter() - start) * 1000.0,
            )

        expected_entity_id = (
            (fault_trace.aut_metadata or {}).get("fixture_context") or {}
        ).get("orderNumber")
        mappings = normalize_c2_to_c3_mappings(task.c2_mappings)
        evidence, c2_facts = project_c3_matched_pair_evidence(
            project_id=project_id,
            case_id=case.case_id,
            pair_id=pair_id,
            run_id=run_id,
            clean_trace=clean_trace,
            fault_trace=fault_trace,
            recovery_contract=suite.recovery_contract,
            c2_mappings=mappings,
            expected_entity_id=str(expected_entity_id) if expected_entity_id else None,
            planned_fault={
                **fault_hook,
                "fault_family": case.fault_family.value,
                "caller_timeout_ms": case.caller_timeout_ms,
            },
        )
        evidence.configuration_snapshot.update(
            {
                "agent_adapter": "c3_nexacart_live_suite_runner",
                "suite_id": suite.suite_id,
                "suite_digest": suite.suite_digest,
                "case_fingerprint": compute_semantic_case_fingerprint(case),
                "task_id": task.task_id,
                "task_version": task.task_version,
                "task_instruction": task.instruction,
                "fixture_id": task.fixture_id,
                "fixture_version": task.fixture_version,
                "adapter_id": suite.adapter_manifest.adapter_id,
                "adapter_version": suite.adapter_manifest.adapter_version,
                "recovery_contract_id": suite.recovery_contract.contract_id,
                "recovery_contract_version": suite.recovery_contract.contract_version,
                "outcome_rules_version": task.outcome_rules.rules_version,
                "agent": (self.live_capabilities or {}).get("agent"),
                "fault_profile": fault_hook,
                "repetition": repetition,
                "repetitions": repetitions,
            }
        )
        if evidence.exposure_status != ExposureStatus.CONFIRMED:
            evidence.interpretation_limitations.append(
                "No recovery verdict: the declared fault was not confirmed as delivered."
            )
        validate_evidence_linkage(evidence)

        evaluation = evaluate_recovery(
            RecoveryEvaluationRequest(
                project_id=project_id,
                case_id=case.case_id,
                candidate_case=case,
                recovery_contract=suite.recovery_contract,
                matched_evidence=evidence,
                c2_facts=c2_facts,
                suite_digest=suite.suite_digest,
                pinned_mappings=mappings,
            )
        )
        return LiveCaseResult(
            case_id=case.case_id,
            status="EXECUTED",
            evidence=evidence,
            c2_facts=c2_facts,
            evaluation=evaluation,
            duration_ms=(time.perf_counter() - start) * 1000.0,
            repetition=repetition,
        )

    def run_suite(
        self,
        suite: FrozenSuite,
        project_id: str,
        run_id: str,
        case_ids: list[str] | None = None,
        on_case_done: Callable[[LiveCaseResult], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
        repetitions: int = 1,
    ) -> tuple[list[LiveCaseResult], str | None]:
        """Run the selected cases in order, each `repetitions` times back to back.

        Every repetition is a separate matched pair, so verdict consistency can be compared.
        Returns the results and an optional halt reason.
        """
        started = time.perf_counter()
        selected = [
            c for c in suite.selected_cases if not case_ids or c.case_id in case_ids
        ]
        results: list[LiveCaseResult] = []
        halt_reason: str | None = None
        runs = [(case, rep) for case in selected for rep in range(1, repetitions + 1)]
        for case, rep in runs:
            if is_cancelled and is_cancelled():
                halt_reason = "Execution cancelled."
            elif time.perf_counter() - started >= self.max_suite_duration_sec:
                halt_reason = f"Suite exceeded maximum total duration of {self.max_suite_duration_sec}s."
            if halt_reason:
                result = LiveCaseResult(
                    case.case_id, "CANCELLED", reasons=[halt_reason], repetition=rep
                )
            else:
                result = self.run_case(
                    case, suite, project_id, run_id, repetition=rep, repetitions=repetitions
                )
                result.repetition = rep
            results.append(result)
            if on_case_done:
                on_case_done(result)
        return results, halt_reason
