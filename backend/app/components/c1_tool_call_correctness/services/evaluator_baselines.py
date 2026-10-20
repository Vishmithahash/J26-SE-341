import abc
import time

from app.components.c1_tool_call_correctness.contracts.configuration import (
    ToolDefinition,
)
from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CauseCategory,
)
from app.components.c1_tool_call_correctness.contracts.execution import (
    CapturedToolEvent,
    CaseExecutionDetail,
)
from app.components.c1_tool_call_correctness.contracts.research import (
    BaselineEvaluationResult,
    BaselineType,
)
from app.components.c1_tool_call_correctness.contracts.results import CorrectnessVerdict


class SchemaAndCallBaselineEvaluator:
    """Baseline 1: Shallow schema and expected-call checker.
    Checks only whether the expected tool was invoked and arguments pass basic type schema,
    without deep semantic correctness, state assertions, or cross-field constraints."""

    def evaluate_case(
        self,
        case_execution: CaseExecutionDetail,
        tool_definitions: dict[str, ToolDefinition],
    ) -> BaselineEvaluationResult:
        start_t = time.perf_counter()

        expected_tools = {
            exp.tool_name
            for exp in case_execution.resolved_expectations
            if hasattr(exp, "tool_name")
        }
        captured_tools = {ev.tool_name for ev in case_execution.captured_events}

        # Check call occurrence
        missing_tools = expected_tools - captured_tools
        if missing_tools:
            duration_ms = (time.perf_counter() - start_t) * 1000.0
            return BaselineEvaluationResult(
                baseline_type=BaselineType.SCHEMA_AND_CALL_ONLY,
                case_id=case_execution.case_id,
                is_available=True,
                verdict=CorrectnessVerdict.FAIL,
                cause_category=CauseCategory.AGENT_BEHAVIOUR,
                candidate_code_locations=[],
                evidence_refs=[],
                duration_ms=round(duration_ms, 2),
            )

        # Check shallow argument presence against tool schema
        schema_mismatches = []
        for ev in case_execution.captured_events:
            tool_def = tool_definitions.get(ev.tool_name)
            if tool_def and tool_def.parameters_schema:
                for req_param in tool_def.parameters_schema.required:
                    if req_param not in ev.arguments:
                        schema_mismatches.append(
                            f"Missing required parameter '{req_param}' in tool '{ev.tool_name}'"
                        )

        verdict = (
            CorrectnessVerdict.FAIL if schema_mismatches else CorrectnessVerdict.PASS
        )
        cause = (
            CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT
            if schema_mismatches
            else None
        )

        duration_ms = (time.perf_counter() - start_t) * 1000.0
        return BaselineEvaluationResult(
            baseline_type=BaselineType.SCHEMA_AND_CALL_ONLY,
            case_id=case_execution.case_id,
            is_available=True,
            verdict=verdict,
            cause_category=cause,
            candidate_code_locations=[],
            evidence_refs=[],
            duration_ms=round(duration_ms, 2),
        )


class ModelArgumentJudgeProvider(abc.ABC):
    """Abstract provider for model-based argument evaluation."""

    @abc.abstractmethod
    def judge_arguments(
        self,
        case: CaseExecutionDetail,
        events: list[CapturedToolEvent],
    ) -> tuple[bool, CorrectnessVerdict, str | None]:
        pass


class ModelArgumentEvaluatorBaseline:
    """Baseline 2: Model-based argument evaluator.
    Gracefully records unavailability when no external model provider dependency is configured."""

    def __init__(self, provider: ModelArgumentJudgeProvider | None = None):
        self.provider = provider

    def evaluate_case(
        self,
        case_execution: CaseExecutionDetail,
    ) -> BaselineEvaluationResult:
        if not self.provider:
            return BaselineEvaluationResult(
                baseline_type=BaselineType.MODEL_ARGUMENT_JUDGE,
                case_id=case_execution.case_id,
                is_available=False,
                unavailability_reason="Model argument judge provider is unconfigured or unavailable in this environment.",
                verdict=None,
                duration_ms=0.0,
            )

        start_t = time.perf_counter()
        success, verdict, reason = self.provider.judge_arguments(
            case_execution, case_execution.captured_events
        )
        duration_ms = (time.perf_counter() - start_t) * 1000.0

        if not success:
            return BaselineEvaluationResult(
                baseline_type=BaselineType.MODEL_ARGUMENT_JUDGE,
                case_id=case_execution.case_id,
                is_available=False,
                unavailability_reason=reason or "Provider call failed.",
                verdict=None,
                duration_ms=round(duration_ms, 2),
            )

        return BaselineEvaluationResult(
            baseline_type=BaselineType.MODEL_ARGUMENT_JUDGE,
            case_id=case_execution.case_id,
            is_available=True,
            verdict=verdict,
            duration_ms=round(duration_ms, 2),
        )


class AblatedDiagnosisEngine:
    """Ablation engine for reduced-evidence and unlinked diagnosis comparisons.
    Supports:
    - UNLINKED_DIAGNOSIS: Evaluates without check explanation links.
    - REDUCED_EVIDENCE_NO_REQUIREMENTS: Strips requirements context.
    - REDUCED_EVIDENCE_NO_SOURCE: Strips AST source inspection.
    - REDUCED_EVIDENCE_NO_CODE: Strips code access entirely (diagnoses solely from error messages)."""

    def run_ablated_diagnosis(
        self,
        case_execution: CaseExecutionDetail,
        ablation_type: BaselineType,
    ) -> BaselineEvaluationResult:
        start_t = time.perf_counter()

        if ablation_type == BaselineType.UNLINKED_DIAGNOSIS:
            # Diagnose directly from case error message without evidence links
            err = (case_execution.error_message or "").lower()
            if "argument" in err or "missing" in err or "signature" in err:
                cause = CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT
            elif "not found" in err or "unrecognized" in err:
                cause = CauseCategory.AGENT_BEHAVIOUR
            else:
                cause = CauseCategory.UNKNOWN

            duration_ms = (time.perf_counter() - start_t) * 1000.0
            return BaselineEvaluationResult(
                baseline_type=ablation_type,
                case_id=case_execution.case_id,
                is_available=True,
                verdict=case_execution.verdict,
                cause_category=cause,
                candidate_code_locations=[],
                evidence_refs=[],  # Unlinked ablation: no evidence links
                duration_ms=round(duration_ms, 2),
            )

        elif ablation_type == BaselineType.REDUCED_EVIDENCE_NO_REQUIREMENTS:
            # Diagnosis without task requirement context
            err = (case_execution.error_message or "").lower()
            cause = (
                CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT
                if "parameter" in err or "argument" in err
                else CauseCategory.AGENT_BEHAVIOUR
            )
            duration_ms = (time.perf_counter() - start_t) * 1000.0
            return BaselineEvaluationResult(
                baseline_type=ablation_type,
                case_id=case_execution.case_id,
                is_available=True,
                verdict=case_execution.verdict,
                cause_category=cause,
                candidate_code_locations=[],
                evidence_refs=[
                    ev.check_id
                    for ev in case_execution.captured_events
                    if hasattr(ev, "check_id")
                ],
                duration_ms=round(duration_ms, 2),
            )

        elif ablation_type == BaselineType.REDUCED_EVIDENCE_NO_SOURCE:
            # Diagnosis without AST source inspection
            err = (case_execution.error_message or "").lower()
            cause = (
                CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT
                if "argument" in err
                else CauseCategory.UNKNOWN
            )
            duration_ms = (time.perf_counter() - start_t) * 1000.0
            return BaselineEvaluationResult(
                baseline_type=ablation_type,
                case_id=case_execution.case_id,
                is_available=True,
                verdict=case_execution.verdict,
                cause_category=cause,
                candidate_code_locations=[],  # No source inspector -> no candidate locations
                evidence_refs=[],
                duration_ms=round(duration_ms, 2),
            )

        elif ablation_type == BaselineType.REDUCED_EVIDENCE_NO_CODE:
            # Diagnosis with no application code access
            duration_ms = (time.perf_counter() - start_t) * 1000.0
            return BaselineEvaluationResult(
                baseline_type=ablation_type,
                case_id=case_execution.case_id,
                is_available=True,
                verdict=case_execution.verdict,
                cause_category=CauseCategory.UNKNOWN,
                candidate_code_locations=[],
                evidence_refs=[],
                duration_ms=round(duration_ms, 2),
            )

        duration_ms = (time.perf_counter() - start_t) * 1000.0
        return BaselineEvaluationResult(
            baseline_type=ablation_type,
            case_id=case_execution.case_id,
            is_available=False,
            unavailability_reason=f"Unknown baseline or ablation type: {ablation_type}",
            duration_ms=round(duration_ms, 2),
        )


schema_baseline_evaluator = SchemaAndCallBaselineEvaluator()
model_baseline_evaluator = ModelArgumentEvaluatorBaseline()
ablated_diagnosis_engine = AblatedDiagnosisEngine()
