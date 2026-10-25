import time
import uuid

from app.components.c1_tool_call_correctness.contracts.configuration import (
    ToolDefinition,
)
from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CandidateCodeLocation,
    CaseDiagnosisRecord,
    CauseCategory,
    CheckExplanationDetail,
    DiagnosisStatus,
    EvidenceAvailability,
    ExplanationMethod,
)
from app.components.c1_tool_call_correctness.contracts.execution import (
    CaseExecutionDetail,
    ExecutionReasonCode,
    TraceCompleteness,
)
from app.components.c1_tool_call_correctness.contracts.results import (
    CorrectnessVerdict,
)
from app.components.c1_tool_call_correctness.services.source_inspector import (
    InspectedFunction,
    SourceInspectionError,
    SourceInspector,
)


class DiagnosisEngine:
    """Supported Root Cause Diagnosis Engine.
    Version: c1-diagnosis-v1.0
    Guarantees:
    - Never blames application code merely because an agent called the wrong tool.
    - Code localisation claims require verified AST source evidence.
    - Accurately classifies into:
      1. SUPPORTED_APPLICATION_CODE_DEFECT
      2. AGENT_BEHAVIOUR
      3. SPECIFICATION_OR_EXPECTATION_PROBLEM
      4. UNKNOWN
    - Never invents line numbers, file paths, or arbitrary numeric confidence scores.
    """

    DIAGNOSIS_VERSION = "c1-diagnosis-v1.0"

    def diagnose_case(
        self,
        project_id: str,
        run_id: str,
        case_execution: CaseExecutionDetail,
        check_explanations: list[CheckExplanationDetail],
        tool_definitions: dict[str, ToolDefinition],
        source_inspector: SourceInspector | None = None,
        expected_code_version: str | None = None,
        retrieval_duration_ms: float = 0.0,
    ) -> CaseDiagnosisRecord:
        """Diagnose the supported cause of failure or inconclusive result for a case execution."""
        start_time = time.perf_counter()
        diagnosis_id = f"diag_{uuid.uuid4().hex[:12]}"

        # Collect evidence references from all checks
        all_evidence_refs: list[str] = []
        for chk in check_explanations:
            all_evidence_refs.extend(chk.evidence_refs)
        all_evidence_refs = list(dict.fromkeys(all_evidence_refs))

        # Check if case actually passed
        if case_execution.verdict == CorrectnessVerdict.PASS:
            analysis_ms = (time.perf_counter() - start_time) * 1000.0
            return CaseDiagnosisRecord(
                diagnosis_id=diagnosis_id,
                project_id=project_id,
                run_id=run_id,
                case_execution_id=case_execution.execution_id,
                case_id=case_execution.case_id,
                attempt_number=case_execution.attempt_number,
                requirement_version="v1.0",
                evaluator_version="c1-evaluator-v1.0",
                explanation_version=self.DIAGNOSIS_VERSION,
                status=DiagnosisStatus.COMPLETED,
                cause_category=CauseCategory.UNKNOWN,
                explanation_summary="Case evaluation PASSED. No failure diagnosis required.",
                check_explanations=[],
                candidate_code_locations=[],
                evidence_refs=all_evidence_refs,
                explanation_method=ExplanationMethod.DETERMINISTIC_RULE_DERIVATION,
                metrics={
                    "retrieval_ms": round(retrieval_duration_ms, 2),
                    "analysis_ms": round(analysis_ms, 2),
                    "total_duration_ms": round(retrieval_duration_ms + analysis_ms, 2),
                },
            )

        # 0. A rejected call whose schema argument the implementation never reads is a supported
        # code defect from the recorded call alone; later, unrecorded events cannot change it.
        recorded = (
            self._recorded_rejection_defect(
                case_execution, tool_definitions, source_inspector
            )
            if source_inspector is not None
            else None
        )

        # 1. Check for Ambiguous, Missing, or Incomplete Evidence -> UNKNOWN
        incomplete = (
            case_execution.trace_completeness
            in (
                TraceCompleteness.INCOMPLETE,
                TraceCompleteness.CORRUPTED,
                TraceCompleteness.MISSING,
            )
            or case_execution.execution_status.value == "EXECUTION_ERROR"
        )
        if incomplete and recorded is not None:
            candidate, reason_text, source_hash = recorded
            analysis_ms = (time.perf_counter() - start_time) * 1000.0
            return CaseDiagnosisRecord(
                diagnosis_id=diagnosis_id,
                project_id=project_id,
                run_id=run_id,
                case_execution_id=case_execution.execution_id,
                case_id=case_execution.case_id,
                attempt_number=case_execution.attempt_number,
                requirement_version="v1.0",
                evaluator_version="c1-evaluator-v1.0",
                explanation_version=self.DIAGNOSIS_VERSION,
                status=DiagnosisStatus.COMPLETED,
                cause_category=CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT,
                explanation_summary=(
                    reason_text + f" The run itself did not complete normally (trace "
                    f"{case_execution.trace_completeness.value}); this finding rests only on "
                    "the recorded rejected call(s)."
                ),
                check_explanations=check_explanations,
                candidate_code_locations=[candidate],
                evidence_refs=all_evidence_refs,
                source_hash=source_hash,
                explanation_method=ExplanationMethod.DETERMINISTIC_RULE_DERIVATION,
                metrics={
                    "retrieval_ms": round(retrieval_duration_ms, 2),
                    "analysis_ms": round(analysis_ms, 2),
                    "total_duration_ms": round(retrieval_duration_ms + analysis_ms, 2),
                },
            )
        if case_execution.trace_completeness in (
            TraceCompleteness.INCOMPLETE,
            TraceCompleteness.CORRUPTED,
            TraceCompleteness.MISSING,
        ) or any(
            c.evidence_availability
            in (
                EvidenceAvailability.MISSING,
                EvidenceAvailability.INSUFFICIENT,
            )
            for c in check_explanations
        ):
            analysis_ms = (time.perf_counter() - start_time) * 1000.0
            summary = (
                f"Execution trace is marked as '{case_execution.trace_completeness.value}' "
                "or corroborating evidence is insufficient. Failure cause cannot be conclusively established."
            )
            return CaseDiagnosisRecord(
                diagnosis_id=diagnosis_id,
                project_id=project_id,
                run_id=run_id,
                case_execution_id=case_execution.execution_id,
                case_id=case_execution.case_id,
                attempt_number=case_execution.attempt_number,
                requirement_version="v1.0",
                evaluator_version="c1-evaluator-v1.0",
                explanation_version=self.DIAGNOSIS_VERSION,
                status=DiagnosisStatus.INSUFFICIENT_EVIDENCE,
                cause_category=CauseCategory.UNKNOWN,
                explanation_summary=summary,
                check_explanations=check_explanations,
                candidate_code_locations=[],
                evidence_refs=all_evidence_refs,
                explanation_method=ExplanationMethod.DETERMINISTIC_RULE_DERIVATION,
                metrics={
                    "retrieval_ms": round(retrieval_duration_ms, 2),
                    "analysis_ms": round(analysis_ms, 2),
                    "total_duration_ms": round(retrieval_duration_ms + analysis_ms, 2),
                },
            )

        # 2. Check for Specification / Expectation Inconsistencies
        # e.g., expectation requires an argument that tool schema doesn't accept, or tool is not declared
        spec_problem_detected, spec_explanation = self._check_specification_consistency(
            case_execution=case_execution,
            check_explanations=check_explanations,
            tool_definitions=tool_definitions,
        )
        if spec_problem_detected:
            analysis_ms = (time.perf_counter() - start_time) * 1000.0
            return CaseDiagnosisRecord(
                diagnosis_id=diagnosis_id,
                project_id=project_id,
                run_id=run_id,
                case_execution_id=case_execution.execution_id,
                case_id=case_execution.case_id,
                attempt_number=case_execution.attempt_number,
                requirement_version="v1.0",
                evaluator_version="c1-evaluator-v1.0",
                explanation_version=self.DIAGNOSIS_VERSION,
                status=DiagnosisStatus.COMPLETED,
                cause_category=CauseCategory.SPECIFICATION_OR_EXPECTATION_PROBLEM,
                explanation_summary=spec_explanation,
                check_explanations=check_explanations,
                candidate_code_locations=[],
                evidence_refs=all_evidence_refs,
                explanation_method=ExplanationMethod.DETERMINISTIC_RULE_DERIVATION,
                metrics={
                    "retrieval_ms": round(retrieval_duration_ms, 2),
                    "analysis_ms": round(analysis_ms, 2),
                    "total_duration_ms": round(retrieval_duration_ms + analysis_ms, 2),
                },
            )

        # 3. Source Inspection & Application Code Defect Analysis
        candidates: list[CandidateCodeLocation] = []
        source_hash: str | None = None
        code_defect_detected = False
        code_defect_explanation: str | None = None

        if source_inspector is not None:
            (
                code_defect_detected,
                candidates,
                source_hash,
                code_defect_explanation,
            ) = self._analyze_code_defects(
                check_explanations=check_explanations,
                tool_definitions=tool_definitions,
                source_inspector=source_inspector,
                expected_code_version=expected_code_version,
                case_execution=case_execution,
            )

        if code_defect_detected and candidates:
            analysis_ms = (time.perf_counter() - start_time) * 1000.0
            return CaseDiagnosisRecord(
                diagnosis_id=diagnosis_id,
                project_id=project_id,
                run_id=run_id,
                case_execution_id=case_execution.execution_id,
                case_id=case_execution.case_id,
                attempt_number=case_execution.attempt_number,
                requirement_version="v1.0",
                evaluator_version="c1-evaluator-v1.0",
                explanation_version=self.DIAGNOSIS_VERSION,
                status=DiagnosisStatus.COMPLETED,
                cause_category=CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT,
                explanation_summary=(
                    code_defect_explanation
                    or "Supported application code defect identified through AST source inspection."
                ),
                check_explanations=check_explanations,
                candidate_code_locations=candidates,
                evidence_refs=all_evidence_refs,
                source_hash=source_hash,
                explanation_method=ExplanationMethod.DETERMINISTIC_RULE_DERIVATION,
                metrics={
                    "retrieval_ms": round(retrieval_duration_ms, 2),
                    "analysis_ms": round(analysis_ms, 2),
                    "total_duration_ms": round(retrieval_duration_ms + analysis_ms, 2),
                },
            )

        # 4. If not spec issue, not incomplete evidence, and no code defect found -> AGENT_BEHAVIOUR
        # (e.g. agent selected wrong tool, hallucinated values, omitted validly declared arguments)
        analysis_ms = (time.perf_counter() - start_time) * 1000.0
        agent_explanation = self._summarize_agent_behavior(check_explanations)

        return CaseDiagnosisRecord(
            diagnosis_id=diagnosis_id,
            project_id=project_id,
            run_id=run_id,
            case_execution_id=case_execution.execution_id,
            case_id=case_execution.case_id,
            attempt_number=case_execution.attempt_number,
            requirement_version="v1.0",
            evaluator_version="c1-evaluator-v1.0",
            explanation_version=self.DIAGNOSIS_VERSION,
            status=DiagnosisStatus.COMPLETED,
            cause_category=CauseCategory.AGENT_BEHAVIOUR,
            explanation_summary=agent_explanation,
            check_explanations=check_explanations,
            candidate_code_locations=[],  # No code locations blamed for agent behavior!
            evidence_refs=all_evidence_refs,
            source_hash=source_hash,
            explanation_method=ExplanationMethod.DETERMINISTIC_RULE_DERIVATION,
            metrics={
                "retrieval_ms": round(retrieval_duration_ms, 2),
                "analysis_ms": round(analysis_ms, 2),
                "total_duration_ms": round(retrieval_duration_ms + analysis_ms, 2),
            },
        )

    def _check_specification_consistency(
        self,
        case_execution: CaseExecutionDetail,
        check_explanations: list[CheckExplanationDetail],
        tool_definitions: dict[str, ToolDefinition],
    ) -> tuple[bool, str]:
        """Verifies whether test expectations contradict tool definitions or task specification."""
        if not tool_definitions:
            return False, ""

        for exp in case_execution.resolved_expectations:
            tool_name = exp.tool_name
            if not tool_name:
                continue

            tool_def = tool_definitions.get(tool_name)
            # If an expectation mandates invoking a tool that doesn't exist in project tools
            if not exp.is_forbidden and (exp.min_count or 0) > 0 and not tool_def:
                return (
                    True,
                    f"Specification error: Expected required tool '{tool_name}' is not defined in project tools.",
                )

            # Check if expected argument is missing from tool parameter schema
            if tool_def:
                for arg_constraint in getattr(exp, "argument_constraints", []):
                    param_name = getattr(arg_constraint, "argument_name", None)
                    if (
                        param_name
                        and param_name not in tool_def.parameters_schema.properties
                    ):
                        return (
                            True,
                            (
                                f"Specification inconsistency: Expectation requires argument '{param_name}', "
                                f"but tool '{tool_name}' schema does not declare it."
                            ),
                        )

        return False, ""

    def _analyze_code_defects(
        self,
        check_explanations: list[CheckExplanationDetail],
        tool_definitions: dict[str, ToolDefinition],
        source_inspector: SourceInspector,
        expected_code_version: str | None = None,
        case_execution: CaseExecutionDetail | None = None,
    ) -> tuple[bool, list[CandidateCodeLocation], str | None, str | None]:
        """Inspects source files for tools linked to failing checks to detect parameter mismatches or runtime errors."""
        candidates: list[CandidateCodeLocation] = []
        overall_source_hash: str | None = None
        defect_reasons: list[str] = []
        inspected_tools: set[str] = set()

        for chk in check_explanations:
            tool_name = chk.tool_name
            if not tool_name or tool_name in inspected_tools:
                continue

            tool_def = tool_definitions.get(tool_name)
            if not tool_def or not tool_def.code_mapping:
                continue

            mapping = tool_def.code_mapping
            if not mapping.file_path or not mapping.function_name:
                continue

            # Check git_ref / code_version staleness
            uncertainties: list[str] = []
            if (
                expected_code_version
                and mapping.git_ref
                and mapping.git_ref != expected_code_version
            ):
                uncertainties.append(
                    f"Code mapping version '{mapping.git_ref}' does not match run code version '{expected_code_version}'."
                )

            # Safely inspect repository function using AST
            try:
                inspected: InspectedFunction | None = source_inspector.inspect_function(
                    file_path=mapping.file_path,
                    function_name=mapping.function_name,
                )
            except SourceInspectionError as e:
                # Security violation or unreadable file: cannot produce supported code defect
                uncertainties.append(f"Source inspection constraint: {e}")
                continue

            if not inspected:
                continue

            overall_source_hash = inspected.source_hash
            if inspected.file_path.endswith((".ts", ".js")):
                inspected_tools.add(tool_name)
                found = self._typescript_mapping_defect(
                    tool_name, tool_def, inspected, case_execution, uncertainties
                )
                if found is not None:
                    candidate, reason_text = found
                    candidates.append(candidate)
                    defect_reasons.append(reason_text)
                continue

            # Defect Scenario A: Tool definition / call parameter mismatch against backend code signature
            # e.g., Tool schema declares 'amount', but backend function parameter is 'refund_amount'
            schema_props = set(tool_def.parameters_schema.properties.keys())
            fn_params = set(inspected.parameters)

            # If check failed on missing or mismatched argument
            is_arg_failure = any(
                code in chk.violated_requirement
                for code in (
                    ExecutionReasonCode.ARGUMENT_MISSING.value,
                    ExecutionReasonCode.ARGUMENT_VALUE_MISMATCH.value,
                    "ARGUMENT_PRESENCE_CHECK",
                    "ARGUMENT_VALUE_CHECK",
                )
            )

            # Check if there is an argument name discrepancy between tool schema and code signature
            schema_not_in_code = schema_props - fn_params
            code_not_in_schema = fn_params - schema_props

            if is_arg_failure and (schema_not_in_code or code_not_in_schema):
                ranking_criteria = (
                    "Parameter name discrepancy detected between tool definition schema and "
                    "backend function signature in AST."
                )
                defect_desc = (
                    f"Argument mapping defect in '{inspected.file_path}': Function '{inspected.function_name}' "
                    f"declares parameters {sorted(fn_params)}, but tool schema declares {sorted(schema_props)}."
                )
                defect_reasons.append(defect_desc)

                candidates.append(
                    CandidateCodeLocation(
                        file_path=inspected.file_path,
                        function_name=inspected.function_name,
                        line_start=inspected.line_start,
                        line_end=inspected.line_end,
                        ranking_score=1,
                        ranking_criteria=ranking_criteria,
                        supporting_evidence=[
                            chk.check_id,
                            f"schema_params={sorted(schema_props)}",
                            f"code_params={sorted(fn_params)}",
                        ],
                        uncertainties=uncertainties,
                    )
                )

            # Defect Scenario B: Tool execution failure at runtime (CALL_EXECUTION_FAILED)
            elif (
                ExecutionReasonCode.CALL_EXECUTION_FAILED.value
                in chk.violated_requirement
            ):
                ranking_criteria = "Runtime execution failure occurred during mapped tool function execution."
                defect_desc = (
                    f"Runtime failure in '{inspected.file_path}' inside function '{inspected.function_name}': "
                    f"{chk.observed_behavior}."
                )
                defect_reasons.append(defect_desc)

                candidates.append(
                    CandidateCodeLocation(
                        file_path=inspected.file_path,
                        function_name=inspected.function_name,
                        line_start=inspected.line_start,
                        line_end=inspected.line_end,
                        ranking_score=1,
                        ranking_criteria=ranking_criteria,
                        supporting_evidence=[
                            chk.check_id,
                            chk.observed_behavior,
                        ],
                        uncertainties=uncertainties,
                    )
                )

        if candidates:
            # Sort candidates by ranking_score ascending
            candidates.sort(key=lambda c: c.ranking_score)
            summary = "; ".join(defect_reasons)
            return True, candidates, overall_source_hash, summary

        return False, [], overall_source_hash, None

    def _recorded_rejection_defect(
        self,
        case_execution: CaseExecutionDetail,
        tool_definitions: dict[str, ToolDefinition],
        source_inspector: SourceInspector,
    ) -> tuple[CandidateCodeLocation, str, str] | None:
        """TypeScript mapping rule applied to every tool with a rejected recorded call."""
        rejected_tools = dict.fromkeys(
            e.tool_name
            for e in case_execution.captured_events
            if e.status.value == "FAILED"
        )
        for tool_name in rejected_tools:
            tool_def = tool_definitions.get(tool_name)
            mapping = tool_def.code_mapping if tool_def else None
            if not mapping or not mapping.file_path or not mapping.function_name:
                continue
            if not mapping.file_path.endswith((".ts", ".js")):
                continue
            try:
                inspected = source_inspector.inspect_function(
                    mapping.file_path, mapping.function_name
                )
            except SourceInspectionError:
                continue
            if inspected is None:
                continue
            found = self._typescript_mapping_defect(
                tool_name, tool_def, inspected, case_execution, []
            )
            if found is not None:
                return found[0], found[1], inspected.source_hash
        return None

    @staticmethod
    def _typescript_mapping_defect(
        tool_name: str,
        tool_def: ToolDefinition,
        inspected: InspectedFunction,
        case_execution: CaseExecutionDetail | None,
        uncertainties: list[str],
    ) -> tuple[CandidateCodeLocation, str] | None:
        """Evidence rule for tool implementations (e.g. NexaCart TypeScript tools).

        A supported code defect needs ALL of: a recorded call that the application rejected,
        argument keys the agent supplied that the tool schema declares, and an implementation
        that never reads one of those keys. A rejected call without that mismatch is a business
        or validation rejection of the agent's input (HTTP 4xx), not evidence against the code.
        """
        if case_execution is None:
            return None
        schema_props = set(tool_def.parameters_schema.properties.keys())
        code_keys = set(inspected.parameters)
        failed_calls = [
            e
            for e in case_execution.captured_events
            if e.tool_name == tool_name and e.status.value == "FAILED"
        ]
        for event in failed_calls:
            supplied = set(event.arguments) & schema_props
            unread = sorted(supplied - code_keys)
            if not unread:
                status = (
                    ((event.tool_response or {}).get("error") or {}).get("statusCode")
                    if isinstance(event.tool_response, dict)
                    else None
                )
                uncertainties.append(
                    f"Call #{event.call_index} to '{tool_name}' was rejected"
                    f"{f' with HTTP {status}' if status else ''}: {event.tool_error}. The "
                    "implementation reads every schema argument the agent supplied, so this is "
                    "treated as a rejection of the agent's input, not a code defect."
                )
                continue
            extra = sorted(code_keys - schema_props)
            reason_text = (
                f"Argument mapping defect in '{inspected.file_path}' ({inspected.function_name}, "
                f"lines {inspected.line_start}-{inspected.line_end}): the agent supplied schema "
                f"argument(s) {unread} in call #{event.call_index}, but the implementation never "
                f"reads them"
                + (
                    f" (it reads {extra}, which the schema does not declare)"
                    if extra
                    else ""
                )
                + f"; the application rejected the call: {event.tool_error}."
            )
            return (
                CandidateCodeLocation(
                    file_path=inspected.file_path,
                    function_name=inspected.function_name,
                    line_start=inspected.line_start,
                    line_end=inspected.line_end,
                    ranking_score=1,
                    ranking_criteria=(
                        "Schema argument supplied by the agent is never read by the tool "
                        "implementation, and the application rejected the call."
                    ),
                    supporting_evidence=[
                        event.event_id,
                        f"supplied_arguments={sorted(event.arguments)}",
                        f"schema_params={sorted(schema_props)}",
                        f"code_reads={sorted(code_keys)}",
                        f"tool_error={event.tool_error}",
                    ],
                    uncertainties=list(uncertainties),
                ),
                reason_text,
            )
        return None

    def _summarize_agent_behavior(
        self, check_explanations: list[CheckExplanationDetail]
    ) -> str:
        """Summarizes agent failure reasons when application code and specification are verified correct."""
        summaries: list[str] = []
        for chk in check_explanations:
            if chk.what_was_observed.startswith("Self-corrected after a rejected call"):
                summaries.append(
                    f"Agent made a rejected call to '{chk.tool_name}' and then corrected "
                    "itself; the rejected call is still an incorrect tool call."
                )
            elif "FORBIDDEN_TOOL" in chk.violated_requirement:
                summaries.append(f"Agent invoked forbidden tool '{chk.tool_name}'.")
            elif "REQUIRED_TOOL" in chk.violated_requirement:
                summaries.append(
                    f"Agent failed to invoke required tool '{chk.tool_name}'."
                )
            elif (
                "ARGUMENT_MISSING" in chk.violated_requirement
                or "ARGUMENT_PRESENCE" in chk.violated_requirement
            ):
                summaries.append(
                    f"Agent omitted required parameter for tool '{chk.tool_name}'."
                )
            elif (
                "ARGUMENT_VALUE" in chk.violated_requirement
                or "ARGUMENT_TYPE" in chk.violated_requirement
            ):
                summaries.append(
                    f"Agent supplied incorrect argument value for tool '{chk.tool_name}'."
                )
            else:
                summaries.append(chk.what_was_observed)
            if chk.argument_provenance:
                summaries.append(chk.argument_provenance)

        if not summaries:
            return "Agent behavior failed to satisfy expected declarative tool-call requirements."
        return "Agent behaviour failure: " + " ".join(summaries)
