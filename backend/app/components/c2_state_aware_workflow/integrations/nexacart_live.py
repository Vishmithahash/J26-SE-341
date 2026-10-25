"""Live C2 runner: generated workflow tests executed by NexaCart's own LLM agent.

Component: C2 - State-Aware Multi-Step Workflow Testing

For every generated VALID, ALTERNATIVE or NEGATIVE case the runner resets a fresh NexaCart harness
fixture for the model's workflow, sends ONLY the case task to NexaCart's agent (oracle isolation:
reference paths, assertions and expected outcomes never leave the QA framework), captures the
ordered tool calls with NexaCart's before / per-step / after snapshots, projects them into C2
runtime evidence and evaluates them against the approved, pinned EFSM.

MUTATED cases are evaluator-sensitivity cases: their mutation operator is applied to the real
evidence of their parent case from the same execution (see ``evaluator/live_mutations.py``).

Nothing is simulated. When NexaCart, the harness or the agent's LLM provider are unavailable the
case is reported ERROR / BLOCKED and receives no verdict.
"""

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)
from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    EvaluationResultContract,
    RuntimeVerdict,
)
from app.components.c2_state_aware_workflow.contracts.runtime_evidence import (
    RuntimeEvidenceContract,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    GeneratedTestDefinition,
    TestCategory,
    TestReadinessStatus,
)
from app.components.c2_state_aware_workflow.evaluator.live_mutations import (
    LiveTraceMutator,
)
from app.components.c2_state_aware_workflow.evaluator.service import (
    WorkflowEvaluationService,
)
from app.components.c2_state_aware_workflow.examples.nexacart_workflows import (
    NexaCartWorkflow,
    nexacart_workflow_for_model,
)
from app.shared.integration.adapters import ExecutionTrace, LiveNexaCartTargetAdapter
from app.shared.integration.evidence import project_c2_evidence

LIVE_RUNNER_ID = "c2_nexacart_live_runner"
LIVE_RUNNER_VERSION = "2026.1"
LIVE_EXECUTION_ORIGIN = "live_nexacart_agent"
# Failures of the agent's LLM provider are infrastructure errors, not workflow behaviour.
INFRASTRUCTURE_AGENT_ERRORS = frozenset({"LLM_PROVIDER_ERROR"})
SCORED_PASS_VERDICTS = frozenset(
    {RuntimeVerdict.PASS.value, RuntimeVerdict.EXPECTED_REJECTION_PASS.value}
)


@dataclass
class LiveC2CaseResult:
    """Outcome of one generated case in a live execution."""

    test_id: str
    category: str
    status: str  # EXECUTED, NOT_EXECUTED, NOT_APPLICABLE, ERROR, CANCELLED
    run_id: str | None = None
    expected_outcome: str | None = None
    verdict: str | None = None
    evaluation_id: str | None = None
    reasons: list[str] = field(default_factory=list)
    observed_states: list[str] = field(default_factory=list)
    first_divergence: dict[str, Any] | None = None
    tool_sequence: list[str] = field(default_factory=list)
    agent_run_id: str | None = None
    agent_status: str | None = None
    final_answer: str | None = None
    covered_transitions: list[str] = field(default_factory=list)
    covered_guard_outcomes: list[str] = field(default_factory=list)
    mutation_type: str | None = None
    parent_test_id: str | None = None
    mutation_detected: bool | None = None
    mutation_details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_record(self) -> dict[str, Any]:
        record = asdict(self)
        record["duration_ms"] = round(self.duration_ms, 1)
        return record


def _covered(result: EvaluationResultContract) -> tuple[list[str], list[str]]:
    cov = result.detailed_coverage
    if cov is None:
        return [], []
    if not isinstance(cov, dict):
        cov = cov.model_dump(mode="json")
    return (
        list((cov.get("transition_coverage") or {}).get("covered_targets") or []),
        list((cov.get("guard_outcome_coverage") or {}).get("covered_targets") or []),
    )


def _apply_result(
    case_result: LiveC2CaseResult, result: EvaluationResultContract
) -> None:
    case_result.verdict = result.verdict.value
    case_result.evaluation_id = result.evaluation_id
    case_result.reasons = list(result.reasons)
    case_result.observed_states = list(result.observed_states)
    case_result.first_divergence = (
        result.first_divergence.model_dump(mode="json")
        if result.first_divergence
        else None
    )
    case_result.covered_transitions, case_result.covered_guard_outcomes = _covered(
        result
    )


class NexaCartLiveWorkflowRunner:
    """Runs generated C2 cases against NexaCart's agent through the external QA harness."""

    def __init__(
        self,
        adapter: LiveNexaCartTargetAdapter | None = None,
        max_suite_duration_sec: float = 3600.0,
    ) -> None:
        self.adapter = adapter or LiveNexaCartTargetAdapter()
        self.max_suite_duration_sec = max_suite_duration_sec
        self.capabilities: dict[str, Any] | None = None

    # -- readiness -----------------------------------------------------------

    def check_readiness(self, model: EFSMModelDefinition) -> list[str]:
        """Reasons the model's workflow cannot run live (empty when ready). Creates no data."""
        reasons: list[str] = []
        if nexacart_workflow_for_model(model.model_id) is None:
            reasons.append(
                f"Model '{model.model_id}' has no NexaCart fixture binding; live execution needs "
                "one of the NexaCart reference workflows."
            )
        status, target_reasons = self.adapter.check_readiness()
        if status.value != "READY":
            return reasons + target_reasons
        try:
            self.capabilities = self.adapter.client.get_capabilities()
        except Exception as exc:  # noqa: BLE001
            return reasons + [f"NexaCart harness capabilities unavailable: {exc}"]
        harness_tools = {t.get("name") for t in self.capabilities.get("tools", [])}
        missing = sorted(
            {m.tool_name for m in model.event_mappings} - harness_tools - {None}
        )
        if missing:
            reasons.append(
                f"Model events are not NexaCart agent tools: {missing}. The model cannot align "
                "with live traces."
            )
        return reasons

    # -- live execution ------------------------------------------------------

    def _run_agent(
        self, namespace: str, workflow: NexaCartWorkflow, task: str
    ) -> ExecutionTrace:
        self.adapter.prepare_fixture(
            namespace, {"nexacart_fixture": workflow.fixture_definition}
        )
        try:
            trace = self.adapter.execute_session(
                namespace=namespace,
                task_prompt=task,
                permitted_tools=[],
                trial_role="C2",
            )
        finally:
            cleaned, reusable = self.adapter.cleanup_fixture(namespace)
        trace.cleanup_successful = cleaned
        trace.cleanup_reusable = reusable
        return trace

    def _provenance(
        self,
        case: GeneratedTestDefinition,
        workflow: NexaCartWorkflow,
        trace: ExecutionTrace,
    ) -> dict[str, Any]:
        meta = trace.aut_metadata or {}
        return {
            "runner_id": LIVE_RUNNER_ID,
            "runner_version": LIVE_RUNNER_VERSION,
            "intended_execution_mode": case.execution_mode.value,
            "actual_execution_origin": LIVE_EXECUTION_ORIGIN,
            "is_live_execution": True,
            "application": "NexaCart",
            "base_url": getattr(self.adapter, "base_url", None),
            "harness_version": (self.capabilities or {}).get("harnessVersion"),
            "agent": (self.capabilities or {}).get("agent"),
            "agent_run_id": meta.get("agent_run_id"),
            "agent_status": meta.get("agent_status"),
            "agent_provider": meta.get("agent_provider"),
            "agent_model": meta.get("agent_model"),
            "agent_error": meta.get("agent_error"),
            "final_answer": meta.get("final_answer"),
            "qa_run_id": meta.get("qa_run_id"),
            "nexacart_fixture_id": meta.get("fixture_id"),
            "fixture_definition_id": workflow.fixture_id,
            "fixture_context": meta.get("fixture_context"),
            "trace_id": trace.trace_id,
            "caller_outcome": trace.caller_outcome,
            "agent_payload": {"task": case.task},
            "observation_capabilities": [
                "ordered_tool_calls",
                "before_snapshot",
                "snapshot_after_each_state_changing_call",
                "after_snapshot",
            ],
            # NexaCart's own LLM agent ran; only the shared services are not wired in yet
            "live_capabilities_available": True,
            "unavailable_live_capabilities": ["shared_intake_service", "unified_report_aggregator"],
            "observation_errors": meta.get("observation_errors") or [],
            "agent_duration_ms": meta.get("duration_ms"),
        }

    def run_live_case(
        self,
        db: Session,
        project_id: str,
        suite_id: str,
        case: GeneratedTestDefinition,
        workflow: NexaCartWorkflow,
        run_id: str,
    ) -> tuple[LiveC2CaseResult, RuntimeEvidenceContract | None]:
        start = time.perf_counter()
        case_result = LiveC2CaseResult(
            test_id=case.test_id,
            category=case.category.value,
            status="EXECUTED",
            run_id=run_id,
            expected_outcome=case.expected_outcome.value,
        )
        try:
            trace = self._run_agent(f"c2-{run_id}", workflow, case.task)
        except Exception as exc:  # noqa: BLE001
            case_result.status = "ERROR"
            case_result.reasons = [f"Live NexaCart run failed: {exc}"]
            case_result.duration_ms = (time.perf_counter() - start) * 1000.0
            return case_result, None

        meta = trace.aut_metadata or {}
        case_result.agent_run_id = meta.get("agent_run_id")
        case_result.agent_status = meta.get("agent_status")
        case_result.final_answer = meta.get("final_answer")
        case_result.tool_sequence = [ev.tool_name for ev in trace.tool_events]
        if trace.caller_outcome in INFRASTRUCTURE_AGENT_ERRORS:
            case_result.status = "ERROR"
            case_result.reasons = [
                f"NexaCart agent run ended with {trace.caller_outcome}: "
                f"{(meta.get('agent_error') or {}).get('message', '')}".strip()
                + " No workflow verdict is given for an LLM provider failure."
            ]
            case_result.duration_ms = (time.perf_counter() - start) * 1000.0
            return case_result, None

        evidence = project_c2_evidence(
            project_id=project_id,
            run_id=run_id,
            test_id=case.test_id,
            model_id=case.pinned_model_id,
            model_version=case.pinned_model_version,
            trace=trace,
            suite_id=suite_id,
        )
        provenance = self._provenance(case, workflow, trace)
        evidence = evidence.model_copy(
            update={
                "model_content_hash": case.model_content_hash,
                "collector_provenance": provenance,
            }
        )
        result = WorkflowEvaluationService(db).evaluate_test_run(
            project_id=project_id,
            suite_id=suite_id,
            test_id=case.test_id,
            evidence=evidence,
            fixture_data=meta.get("fixture_context"),
            runner_id=LIVE_RUNNER_ID,
            execution_provenance=provenance,
        )
        _apply_result(case_result, result)
        case_result.duration_ms = (time.perf_counter() - start) * 1000.0
        return case_result, evidence

    def run_mutated_case(
        self,
        db: Session,
        project_id: str,
        suite_id: str,
        case: GeneratedTestDefinition,
        model: EFSMModelDefinition,
        parent_result: LiveC2CaseResult,
        parent_evidence: RuntimeEvidenceContract | None,
        run_id: str,
    ) -> LiveC2CaseResult:
        start = time.perf_counter()
        provenance = case.mutation_provenance
        case_result = LiveC2CaseResult(
            test_id=case.test_id,
            category=case.category.value,
            status="NOT_APPLICABLE",
            run_id=run_id,
            expected_outcome=RuntimeVerdict.FAIL.value,
            mutation_type=provenance.mutation_type.value if provenance else None,
            parent_test_id=parent_result.test_id,
        )
        if provenance is None:
            case_result.reasons = ["Mutated case has no mutation provenance."]
            return case_result
        if parent_evidence is None or parent_result.verdict not in SCORED_PASS_VERDICTS:
            case_result.reasons = [
                (
                    f"Parent case {parent_result.test_id} did not produce a conforming live trace "
                    f"(verdict {parent_result.verdict or parent_result.status}); mutation sensitivity "
                    "is measured on conforming traces only."
                )
            ]
            return case_result

        fixture_context = parent_evidence.collector_provenance.get("fixture_context")
        mutation = LiveTraceMutator(model).mutate(
            parent=parent_evidence,
            provenance=provenance,
            test_id=case.test_id,
            run_id=run_id,
            fixture_context=fixture_context,
        )
        case_result.agent_run_id = parent_result.agent_run_id
        if not mutation.applied or mutation.evidence is None:
            case_result.reasons = [mutation.reason]
            case_result.duration_ms = (time.perf_counter() - start) * 1000.0
            return case_result

        evidence = mutation.evidence
        case_result.status = "EXECUTED"
        case_result.mutation_details = mutation.details
        case_result.tool_sequence = [ev.tool_name for ev in evidence.ordered_events]
        result = WorkflowEvaluationService(db).evaluate_test_run(
            project_id=project_id,
            suite_id=suite_id,
            test_id=case.test_id,
            evidence=evidence,
            fixture_data=fixture_context,
            runner_id=LIVE_RUNNER_ID,
            execution_provenance=evidence.collector_provenance,
        )
        _apply_result(case_result, result)
        case_result.reasons = [mutation.reason, *case_result.reasons]
        case_result.mutation_detected = result.verdict == RuntimeVerdict.FAIL
        case_result.duration_ms = (time.perf_counter() - start) * 1000.0
        return case_result

    def record_without_agent(
        self,
        db: Session,
        project_id: str,
        suite_id: str,
        case: GeneratedTestDefinition,
        run_id: str,
    ) -> LiveC2CaseResult:
        """MODEL NOT READY / TEST NOT READY: verdict from the evaluator, no agent run."""
        evidence = RuntimeEvidenceContract(
            project_id=project_id,
            suite_id=suite_id,
            run_id=run_id,
            test_id=case.test_id,
            model_id=case.pinned_model_id,
            model_version=case.pinned_model_version,
            execution_mode="not_executed",
            collector_provenance={
                "runner_id": LIVE_RUNNER_ID,
                "is_live_execution": False,
                "reason": "Not executed: the model or test is not ready.",
            },
        )
        result = WorkflowEvaluationService(db).evaluate_test_run(
            project_id=project_id,
            suite_id=suite_id,
            test_id=case.test_id,
            evidence=evidence,
            runner_id=LIVE_RUNNER_ID,
        )
        case_result = LiveC2CaseResult(
            test_id=case.test_id,
            category=case.category.value,
            status="NOT_EXECUTED",
            run_id=run_id,
            expected_outcome=case.expected_outcome.value,
        )
        _apply_result(case_result, result)
        return case_result

    # -- suite ---------------------------------------------------------------

    def run_cases(
        self,
        db: Session,
        project_id: str,
        suite_id: str,
        cases: list[GeneratedTestDefinition],
        model: EFSMModelDefinition,
        model_is_approved: bool,
        execution_id: str,
        all_cases: dict[str, GeneratedTestDefinition] | None = None,
        on_case_done: Callable[[LiveC2CaseResult], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> tuple[list[LiveC2CaseResult], str | None]:
        """Run live cases first, then mutants on their parents' live evidence."""
        workflow = nexacart_workflow_for_model(model.model_id)
        started = time.perf_counter()
        lookup = all_cases or {c.test_id: c for c in cases}
        results: list[LiveC2CaseResult] = []
        live: dict[str, tuple[LiveC2CaseResult, RuntimeEvidenceContract | None]] = {}
        halt_reason: str | None = None
        counter = 0

        def next_run_id() -> str:
            nonlocal counter
            counter += 1
            return f"{execution_id}-{counter:03d}"

        def emit(result: LiveC2CaseResult) -> None:
            results.append(result)
            if on_case_done:
                on_case_done(result)

        def halted() -> str | None:
            if is_cancelled and is_cancelled():
                return "Execution cancelled."
            if time.perf_counter() - started >= self.max_suite_duration_sec:
                return f"Suite exceeded maximum total duration of {self.max_suite_duration_sec}s."
            return None

        def run_live(case: GeneratedTestDefinition) -> None:
            nonlocal halt_reason
            halt_reason = halt_reason or halted()
            if halt_reason:
                emit(
                    LiveC2CaseResult(
                        case.test_id,
                        case.category.value,
                        "CANCELLED",
                        reasons=[halt_reason],
                    )
                )
                return
            if (
                not model_is_approved
                or case.readiness == TestReadinessStatus.TEST_NOT_READY
            ):
                emit(
                    self.record_without_agent(
                        db, project_id, suite_id, case, next_run_id()
                    )
                )
                return
            result, evidence = self.run_live_case(
                db, project_id, suite_id, case, workflow, next_run_id()
            )
            live[case.test_id] = (result, evidence)
            emit(result)

        ordered = [c for c in cases if c.category != TestCategory.MUTATED]
        mutants = [c for c in cases if c.category == TestCategory.MUTATED]
        for case in ordered:
            run_live(case)

        for case in mutants:
            parent_id = (
                case.mutation_provenance.parent_case_id
                if case.mutation_provenance
                else None
            )
            if parent_id and parent_id not in live and parent_id in lookup:
                run_live(lookup[parent_id])  # the parent's live trace is needed first
            halt_reason = halt_reason or halted()
            if halt_reason:
                emit(
                    LiveC2CaseResult(
                        case.test_id,
                        case.category.value,
                        "CANCELLED",
                        reasons=[halt_reason],
                    )
                )
                continue
            if (
                not model_is_approved
                or case.readiness == TestReadinessStatus.TEST_NOT_READY
            ):
                emit(
                    self.record_without_agent(
                        db, project_id, suite_id, case, next_run_id()
                    )
                )
                continue
            parent = live.get(parent_id or "")
            if parent is None:
                emit(
                    LiveC2CaseResult(
                        case.test_id,
                        case.category.value,
                        "NOT_APPLICABLE",
                        parent_test_id=parent_id,
                        mutation_type=case.mutation_provenance.mutation_type.value
                        if case.mutation_provenance
                        else None,
                        reasons=[f"Parent case '{parent_id}' was not executed live."],
                    )
                )
                continue
            emit(
                self.run_mutated_case(
                    db,
                    project_id,
                    suite_id,
                    case,
                    model,
                    parent[0],
                    parent[1],
                    next_run_id(),
                )
            )
        return results, halt_reason
