from typing import Any

from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CheckExplanationDetail,
    EvidenceAvailability,
    SourceRelationshipStatus,
)
from app.components.c1_tool_call_correctness.contracts.execution import (
    CapturedToolEvent,
    ExecutionReasonCode,
    TraceCompleteness,
)
from app.components.c1_tool_call_correctness.contracts.results import (
    CheckLevelResult,
    CorrectnessVerdict,
)


class ExplanationEngine:
    """Produces versioned, deterministic, evidence-linked explanations for check outcomes.
    Version: c1-explanation-v1.0
    Guarantees:
    - Never fabricates mismatches when evidence is missing.
    - Does not claim contextual provenance merely from value equality.
    - Explicitly separates observed behavior, violated requirement, supported findings, and uncertainties.
    """

    EXPLANATION_VERSION = "c1-explanation-v1.0"

    def explain_case_checks(
        self,
        check_results: list[CheckLevelResult],
        captured_events: list[CapturedToolEvent],
        trace_completeness: TraceCompleteness,
    ) -> list[CheckExplanationDetail]:
        """Derives structured explanations for all failing or inconclusive checks in a case execution."""
        explanations: list[CheckExplanationDetail] = []
        events_by_id = {e.event_id: e for e in captured_events}
        events_by_tool: dict[str, list[CapturedToolEvent]] = {}
        for ev in captured_events:
            events_by_tool.setdefault(ev.tool_name, []).append(ev)

        for check in check_results:
            # We explain FAIL and INCONCLUSIVE checks, as well as checks explicitly requested
            if check.verdict == CorrectnessVerdict.PASS:
                continue

            explanation = self.explain_single_check(
                check=check,
                captured_events=captured_events,
                events_by_id=events_by_id,
                events_by_tool=events_by_tool,
                trace_completeness=trace_completeness,
            )
            explanations.append(explanation)

        return explanations

    def explain_single_check(
        self,
        check: CheckLevelResult,
        captured_events: list[CapturedToolEvent],
        events_by_id: dict[str, CapturedToolEvent],
        events_by_tool: dict[str, list[CapturedToolEvent]],
        trace_completeness: TraceCompleteness,
    ) -> CheckExplanationDetail:
        """Derives a deterministic explanation for a single check."""
        matched_call_id: str | None = None
        relevant_args: dict[str, Any] = {}
        recorded_output: Any = None
        evidence_availability = EvidenceAvailability.COMPLETE
        source_relationship_status = SourceRelationshipStatus.UNKNOWN
        evidence_supported_findings: list[str] = []
        uncertainties: list[str] = []

        # Find matching tool event if applicable
        tool_events = events_by_tool.get(check.target_tool or "", [])
        matched_event: CapturedToolEvent | None = None
        if tool_events:
            matched_event = tool_events[0]
            matched_call_id = matched_event.event_id
            relevant_args = matched_event.arguments
            recorded_output = matched_event.tool_response or matched_event.tool_error

        # Determine evidence availability based on trace completeness
        if trace_completeness == TraceCompleteness.MISSING:
            evidence_availability = EvidenceAvailability.MISSING
            uncertainties.append(
                "Execution trace is missing entirely; inability to observe actions is not evidence of absence."
            )
        elif trace_completeness in (
            TraceCompleteness.INCOMPLETE,
            TraceCompleteness.CORRUPTED,
        ):
            evidence_availability = EvidenceAvailability.PARTIAL
            uncertainties.append(
                f"Execution trace is marked as {trace_completeness.value}; unrecorded events may have occurred."
            )
        elif (
            not check.evidence_refs and check.verdict == CorrectnessVerdict.INCONCLUSIVE
        ):
            evidence_availability = EvidenceAvailability.INSUFFICIENT
            uncertainties.append(
                "Insufficient corroborating evidence captured to establish verdict conclusively."
            )

        reason = check.reason_code
        rule = check.rule_name

        # 1. Wrong Tool / Forbidden Tool
        if reason == ExecutionReasonCode.FORBIDDEN_TOOL_INVOKED.value:
            what_observed = (
                f"Tool '{check.target_tool}' was invoked {check.actual_value} time(s) "
                f"despite being declared forbidden."
            )
            violated_req = (
                f"Rule '{rule}': Invocation of forbidden tool '{check.target_tool}'."
            )
            expected_behavior = f"Tool '{check.target_tool}' must not be invoked."
            observed_behavior = f"Invoked {check.actual_value} time(s)."
            evidence_supported_findings.append(
                f"Observed forbidden call to '{check.target_tool}' at event '{matched_call_id}'."
            )

        # 2. Required Tool Missing
        elif reason == ExecutionReasonCode.REQUIRED_TOOL_MISSING.value:
            what_observed = f"Required tool '{check.target_tool}' was absent from captured execution trace."
            violated_req = f"Rule '{rule}': Expected mandatory invocation of tool '{check.target_tool}'."
            expected_behavior = f"Tool '{check.target_tool}' must be invoked."
            observed_behavior = "Tool was never invoked."
            evidence_supported_findings.append(
                f"No event matching tool name '{check.target_tool}' was found among {len(captured_events)} captured event(s)."
            )
            if trace_completeness != TraceCompleteness.COMPLETE:
                uncertainties.append(
                    "Trace was not complete; cannot definitively conclude whether tool was invoked after cutoff."
                )

        # 3. Missing Argument
        elif reason == ExecutionReasonCode.ARGUMENT_MISSING.value:
            what_observed = f"Argument '{check.target_argument}' was omitted from tool call to '{check.target_tool}'."
            violated_req = f"Rule '{rule}': Mandatory argument '{check.target_argument}' was not provided."
            expected_behavior = (
                f"Argument '{check.target_argument}' must be present in tool call."
            )
            observed_behavior = f"Argument '{check.target_argument}' is missing from call arguments {list(relevant_args.keys())}."
            evidence_supported_findings.append(
                f"Call arguments at event '{matched_call_id}' did not contain key '{check.target_argument}'."
            )

        # 4. Incorrect Argument Value
        elif reason in (
            ExecutionReasonCode.ARGUMENT_VALUE_MISMATCH.value,
            ExecutionReasonCode.ARGUMENT_TYPE_MISMATCH.value,
        ):
            what_observed = (
                f"Argument '{check.target_argument}' had value '{check.actual_value}', "
                f"which violates expected constraint '{check.expected_value}'."
            )
            violated_req = f"Rule '{rule}': Argument value constraint for '{check.target_argument}' failed."
            expected_behavior = f"Argument '{check.target_argument}' must satisfy {check.expected_value}."
            observed_behavior = f"Observed value: {check.actual_value!r}."
            evidence_supported_findings.append(
                f"Captured payload for event '{matched_call_id}' specifies '{check.target_argument}' = {check.actual_value!r}."
            )

        # 5. Contextual Source Relationship Mismatch
        elif reason in (
            ExecutionReasonCode.SOURCE_VALUE_MISMATCH.value,
            ExecutionReasonCode.SOURCE_RECORD_MISSING.value,
            ExecutionReasonCode.SOURCE_PATH_MISSING.value,
        ):
            what_observed = (
                f"Contextual source mapping failed for '{check.target_argument}': "
                f"observed '{check.actual_value}', expected '{check.expected_value}'."
            )
            violated_req = f"Rule '{rule}': Argument '{check.target_argument}' must derive from specified source context."
            expected_behavior = (
                f"Value should match source context: {check.expected_value}."
            )
            observed_behavior = f"Observed value: {check.actual_value!r}."
            evidence_supported_findings.append(
                f"Context verification failed for field '{check.target_argument}'."
            )
            # Rule: Do not claim argument provenance merely because its value equals a value in a previous response.
            if matched_event and matched_event.source_tags.get(
                check.target_argument or ""
            ):
                source_relationship_status = SourceRelationshipStatus.OBSERVED
                evidence_supported_findings.append(
                    "Explicit provenance tags corroborated source relationship."
                )
            else:
                source_relationship_status = SourceRelationshipStatus.UNKNOWN
                uncertainties.append(
                    "Contextual provenance is uncorroborated: value similarity alone does not establish true source origin."
                )

        # 6. Call Execution Failed (runtime error in tool)
        elif reason == ExecutionReasonCode.CALL_EXECUTION_FAILED.value:
            err_msg = (
                matched_event.tool_error
                if matched_event
                else "Tool call execution failed at runtime."
            )
            what_observed = f"Tool '{check.target_tool}' raised a runtime execution error: {err_msg}."
            violated_req = f"Rule '{rule}': Tool call must execute successfully without runtime errors."
            expected_behavior = "Tool execution must succeed with EventStatus.SUCCESS."
            observed_behavior = f"Runtime error: {err_msg}."
            evidence_supported_findings.append(
                f"Runtime failure recorded in tool execution trace for '{check.target_tool}'."
            )

        # 7. Incomplete Trace / Missing Evidence
        elif reason in (
            ExecutionReasonCode.INCOMPLETE_TRACE_MISSING_TOOL.value,
            ExecutionReasonCode.INSUFFICIENT_EVIDENCE_UNASSESSABLE.value,
        ):
            what_observed = "Evaluation could not be performed due to incomplete execution evidence or trace truncation."
            violated_req = (
                f"Rule '{rule}': Verification requires complete execution trace."
            )
            expected_behavior = "Complete evidence trace required for evaluation."
            observed_behavior = f"Trace status: {trace_completeness.value}; Check verdict: INCONCLUSIVE."
            evidence_availability = EvidenceAvailability.INSUFFICIENT
            uncertainties.append(
                "Missing execution evidence prevents validating or falsifying this requirement."
            )

        # Fallback / Generic
        else:
            what_observed = (
                check.explanation
                or f"Check '{check.check_id}' evaluated to {check.verdict.value}."
            )
            violated_req = f"Rule '{rule}': Evaluation criterion failed."
            expected_behavior = f"Expected: {check.expected_value}."
            observed_behavior = f"Observed: {check.actual_value}."
            evidence_supported_findings.append(
                f"Check reason code recorded as '{reason}'."
            )

        return CheckExplanationDetail(
            check_id=check.check_id,
            matched_call_id=matched_call_id,
            tool_name=check.target_tool,
            expected_behavior=expected_behavior,
            observed_behavior=observed_behavior,
            relevant_arguments=relevant_args,
            recorded_tool_outputs=recorded_output,
            evidence_refs=check.evidence_refs,
            evidence_availability=evidence_availability,
            source_relationship_status=source_relationship_status,
            what_was_observed=what_observed,
            violated_requirement=violated_req,
            evidence_supported_findings=evidence_supported_findings,
            uncertainties=uncertainties,
        )
