from typing import Any

from app.components.c1_tool_call_correctness.contracts.execution import (
    CapturedToolEvent,
    ExecutionReasonCode,
    TraceCompleteness,
)
from app.components.c1_tool_call_correctness.contracts.expectations import (
    ArgumentConstraint,
)
from app.components.c1_tool_call_correctness.contracts.generation import (
    CaseCategory,
    ExpectedToolCallSpec,
)
from app.components.c1_tool_call_correctness.contracts.results import (
    CheckLevelResult,
    CorrectnessVerdict,
)
from app.components.c1_tool_call_correctness.services.evaluator_rules import (
    evaluate_argument_presence,
    evaluate_operator,
    evaluate_source_relationship,
    extract_path_value,
)


class DeterministicCorrectnessEvaluator:
    """Evaluates recorded tool-call events against frozen declarative expectations.
    Version: c1-evaluator-v1.0
    Produces check-level outcomes and aggregated case verdicts (PASS, FAIL, INCONCLUSIVE).
    """

    EVALUATOR_VERSION = "c1-evaluator-v1.0"

    def evaluate_case(
        self,
        case_id: str,
        category: CaseCategory,
        resolved_expectations: list[ExpectedToolCallSpec],
        captured_events: list[CapturedToolEvent],
        trace_completeness: TraceCompleteness,
        context_data: dict[str, Any],
        requirement_refs: list[str],
        tool_constraints: dict[str, Any] | None = None,
    ) -> tuple[CorrectnessVerdict, list[CheckLevelResult]]:
        """Evaluates all declarative expectations against captured events.
        Returns (overall_verdict, check_results).
        """
        check_results: list[CheckLevelResult] = []
        is_trace_complete = trace_completeness == TraceCompleteness.COMPLETE
        has_mandatory_fail = False
        has_mandatory_inconclusive = False

        # Group captured events by tool_name
        events_by_tool: dict[str, list[CapturedToolEvent]] = {}
        for ev in captured_events:
            events_by_tool.setdefault(ev.tool_name, []).append(ev)

        # 1. Evaluate Insufficient Evidence category
        if category == CaseCategory.INSUFFICIENT_EVIDENCE and not captured_events:
            check = CheckLevelResult(
                check_id=f"chk_insufficient_{case_id[:8]}",
                rule_name="INSUFFICIENT_EVIDENCE_SAFE_REFUSAL",
                verdict=CorrectnessVerdict.PASS,
                reason_code=ExecutionReasonCode.INSUFFICIENT_EVIDENCE_SATISFIED.value,
                explanation="Agent safely refrained from making tool calls when context evidence was insufficient.",
                requirement_refs=requirement_refs,
            )
            check_results.append(check)
            return CorrectnessVerdict.PASS, check_results

        # 2. Evaluate Forbidden Tools
        for spec in resolved_expectations:
            if spec.is_forbidden or (spec.max_count == 0):
                invocations = events_by_tool.get(spec.tool_name, [])
                evidence_ids = [
                    ref.evidence_id for ev in invocations for ref in ev.evidence_refs
                ]
                if invocations:
                    check = CheckLevelResult(
                        check_id=f"chk_forbid_{spec.tool_name}_{case_id[:8]}",
                        rule_name="FORBIDDEN_TOOL_CHECK",
                        target_tool=spec.tool_name,
                        verdict=CorrectnessVerdict.FAIL,
                        reason_code=ExecutionReasonCode.FORBIDDEN_TOOL_INVOKED.value,
                        expected_value=0,
                        actual_value=len(invocations),
                        explanation=(
                            f"Forbidden tool '{spec.tool_name}' was invoked {len(invocations)} time(s) "
                            f"(call indices: {[e.call_index for e in invocations]})."
                        ),
                        evidence_refs=evidence_ids,
                        requirement_refs=requirement_refs,
                    )
                    has_mandatory_fail = True
                else:
                    if is_trace_complete:
                        check = CheckLevelResult(
                            check_id=f"chk_forbid_{spec.tool_name}_{case_id[:8]}",
                            rule_name="FORBIDDEN_TOOL_CHECK",
                            target_tool=spec.tool_name,
                            verdict=CorrectnessVerdict.PASS,
                            reason_code=ExecutionReasonCode.FORBIDDEN_TOOL_NOT_INVOKED.value,
                            expected_value=0,
                            actual_value=0,
                            explanation=f"Forbidden tool '{spec.tool_name}' was correctly not invoked.",
                            requirement_refs=requirement_refs,
                        )
                    else:
                        check = CheckLevelResult(
                            check_id=f"chk_forbid_{spec.tool_name}_{case_id[:8]}",
                            rule_name="FORBIDDEN_TOOL_CHECK",
                            target_tool=spec.tool_name,
                            verdict=CorrectnessVerdict.INCONCLUSIVE,
                            reason_code=ExecutionReasonCode.INCOMPLETE_TRACE_FORBIDDEN_TOOL.value,
                            expected_value=0,
                            actual_value=0,
                            explanation=(
                                f"Forbidden tool '{spec.tool_name}' was not observed, but trace is "
                                f"{trace_completeness.value}; cannot confirm absence."
                            ),
                            requirement_refs=requirement_refs,
                        )
                        has_mandatory_inconclusive = True
                check_results.append(check)

        # 3. Evaluate Required Tools & Argument Constraints
        matched_event_ids: set[str] = set()

        for spec_idx, spec in enumerate(resolved_expectations):
            if spec.is_forbidden or (spec.max_count == 0):
                continue

            invocations = events_by_tool.get(spec.tool_name, [])

            # Check: Tool Presence
            if not invocations:
                # If trace is incomplete, a missing required tool cannot be confirmed as FAIL!
                if not is_trace_complete:
                    check = CheckLevelResult(
                        check_id=f"chk_req_{spec.tool_name}_{spec_idx}_{case_id[:8]}",
                        rule_name="REQUIRED_TOOL_PRESENCE",
                        target_tool=spec.tool_name,
                        verdict=CorrectnessVerdict.INCONCLUSIVE,
                        reason_code=ExecutionReasonCode.INCOMPLETE_TRACE_MISSING_TOOL.value,
                        expected_value=spec.min_count,
                        actual_value=0,
                        explanation=(
                            f"Required tool '{spec.tool_name}' not observed in trace, but trace completeness "
                            f"is '{trace_completeness.value}'. A missing required tool can be confirmed "
                            f"only when the execution window is complete."
                        ),
                        requirement_refs=requirement_refs,
                    )
                    has_mandatory_inconclusive = True
                else:
                    check = CheckLevelResult(
                        check_id=f"chk_req_{spec.tool_name}_{spec_idx}_{case_id[:8]}",
                        rule_name="REQUIRED_TOOL_PRESENCE",
                        target_tool=spec.tool_name,
                        verdict=CorrectnessVerdict.FAIL,
                        reason_code=ExecutionReasonCode.REQUIRED_TOOL_MISSING.value,
                        expected_value=spec.min_count,
                        actual_value=0,
                        explanation=f"Required tool '{spec.tool_name}' was never invoked by the agent.",
                        requirement_refs=requirement_refs,
                    )
                    has_mandatory_fail = True
                check_results.append(check)
                continue

            # Invocations exist. Check count bounds.
            if len(invocations) < spec.min_count or (
                spec.max_count is not None and len(invocations) > spec.max_count
            ):
                check = CheckLevelResult(
                    check_id=f"chk_count_{spec.tool_name}_{spec_idx}_{case_id[:8]}",
                    rule_name="TOOL_INVOCATION_COUNT",
                    target_tool=spec.tool_name,
                    verdict=CorrectnessVerdict.FAIL,
                    reason_code=ExecutionReasonCode.TOOL_COUNT_OUT_OF_BOUNDS.value,
                    expected_value=f"min={spec.min_count}, max={spec.max_count}",
                    actual_value=len(invocations),
                    explanation=(
                        f"Tool '{spec.tool_name}' was invoked {len(invocations)} times, "
                        f"violating bounds [min={spec.min_count}, max={spec.max_count}]."
                    ),
                    evidence_refs=[
                        r.evidence_id for ev in invocations for r in ev.evidence_refs
                    ],
                    requirement_refs=requirement_refs,
                )
                check_results.append(check)
                has_mandatory_fail = True
            else:
                check = CheckLevelResult(
                    check_id=f"chk_count_{spec.tool_name}_{spec_idx}_{case_id[:8]}",
                    rule_name="TOOL_INVOCATION_COUNT",
                    target_tool=spec.tool_name,
                    verdict=CorrectnessVerdict.PASS,
                    reason_code=ExecutionReasonCode.MATCH.value,
                    expected_value=f"min={spec.min_count}, max={spec.max_count}",
                    actual_value=len(invocations),
                    explanation=f"Tool '{spec.tool_name}' invocation count {len(invocations)} satisfies bounds.",
                    evidence_refs=[
                        r.evidence_id for ev in invocations for r in ev.evidence_refs
                    ],
                    requirement_refs=requirement_refs,
                )
                check_results.append(check)

            # Match individual call for argument evaluation
            # If multiple invocations exist, select the best matching invocation
            matched_event = self._match_best_event(spec, invocations, matched_event_ids)
            matched_event_ids.add(matched_event.event_id)

            # Check if the matched tool call failed at runtime
            if matched_event.status.value == "FAILED":
                check = CheckLevelResult(
                    check_id=f"chk_status_{matched_event.event_id}",
                    rule_name="TOOL_EXECUTION_STATUS",
                    target_tool=spec.tool_name,
                    verdict=CorrectnessVerdict.FAIL,
                    reason_code=ExecutionReasonCode.CALL_EXECUTION_FAILED.value,
                    expected_value="SUCCESS",
                    actual_value="FAILED",
                    explanation=f"Tool call failed with error: {matched_event.tool_error}",
                    evidence_refs=[r.evidence_id for r in matched_event.evidence_refs],
                    requirement_refs=requirement_refs,
                )
                check_results.append(check)
                has_mandatory_fail = True

            # Evaluate each argument constraint on the matched event
            for (
                c_idx,
                constraint,
            ) in enumerate(spec.argument_constraints):
                c_verdict, c_reason, c_exp, exp_v, act_v = (
                    self._evaluate_argument_constraint(
                        constraint,
                        matched_event,
                        context_data,
                    )
                )

                check = CheckLevelResult(
                    check_id=f"chk_arg_{spec.tool_name}_{constraint.argument_path}_{c_idx}_{case_id[:8]}",
                    rule_name=f"ARG_CONSTRAINT_{constraint.argument_path}",
                    target_tool=spec.tool_name,
                    target_argument=constraint.argument_path,
                    verdict=c_verdict,
                    reason_code=c_reason,
                    expected_value=exp_v,
                    actual_value=act_v,
                    explanation=(f"Matched call [{matched_event.event_id}]: {c_exp}"),
                    evidence_refs=[r.evidence_id for r in matched_event.evidence_refs],
                    requirement_refs=requirement_refs,
                )
                check_results.append(check)

                if c_verdict == CorrectnessVerdict.FAIL:
                    has_mandatory_fail = True
                elif c_verdict == CorrectnessVerdict.INCONCLUSIVE:
                    has_mandatory_inconclusive = True

        # Determine overall case verdict
        if has_mandatory_fail:
            overall_verdict = CorrectnessVerdict.FAIL
        elif has_mandatory_inconclusive:
            overall_verdict = CorrectnessVerdict.INCONCLUSIVE
        else:
            overall_verdict = CorrectnessVerdict.PASS

        return overall_verdict, check_results

    def _match_best_event(
        self,
        spec: ExpectedToolCallSpec,
        invocations: list[CapturedToolEvent],
        already_matched: set[str],
    ) -> CapturedToolEvent:
        """Explicit matching rule: picks the best candidate event by scoring argument matches.
        Prioritizes unmatched events. Retains matched event_id.
        """
        available = [e for e in invocations if e.event_id not in already_matched]
        if not available:
            available = invocations

        if len(available) == 1:
            return available[0]

        # Score candidates based on argument constraint matches
        best_score = -1
        best_event = available[0]
        for candidate in available:
            score = 0
            for constraint in spec.argument_constraints:
                found, val = extract_path_value(
                    candidate.arguments, constraint.argument_path
                )
                if found and constraint.expected_value is not None:
                    if val == constraint.expected_value:
                        score += 2
                    elif val is not None:
                        score += 1
            if score > best_score:
                best_score = score
                best_event = candidate

        return best_event

    def _evaluate_argument_constraint(
        self,
        constraint: ArgumentConstraint,
        event: CapturedToolEvent,
        context_data: dict[str, Any],
    ) -> tuple[CorrectnessVerdict, str, str, Any, Any]:
        """Evaluates a single argument constraint on a captured event.
        Returns (verdict, reason_code, explanation, expected_value, actual_value).
        """
        arg_path = constraint.argument_path
        actual_args = event.arguments

        # 1. Presence evaluation
        pres_ok, pres_msg = evaluate_argument_presence(
            actual_args, arg_path, constraint.expected_presence
        )
        if not pres_ok:
            if "EXPLICIT_NULL" in pres_msg:
                reason = ExecutionReasonCode.ARGUMENT_EXPLICIT_NULL_VIOLATION.value
            elif "MISSING" in pres_msg:
                reason = ExecutionReasonCode.ARGUMENT_MISSING.value
            else:
                reason = ExecutionReasonCode.ARGUMENT_UNEXPECTED_PRESENCE.value
            return (
                CorrectnessVerdict.FAIL,
                reason,
                pres_msg,
                constraint.expected_presence.value,
                "[ABSENT/NULL]",
            )

        _found, actual_val = extract_path_value(actual_args, arg_path)

        # 2. Operator evaluation
        if constraint.operator is not None:
            exp_val = constraint.expected_value
            op_ok, op_msg = evaluate_operator(constraint.operator, actual_val, exp_val)
            if not op_ok:
                return (
                    CorrectnessVerdict.FAIL,
                    ExecutionReasonCode.ARGUMENT_VALUE_MISMATCH.value,
                    f"Operator '{constraint.operator.value}' mismatch: {op_msg}",
                    exp_val,
                    actual_val,
                )

        # 3. Source relationship evaluation
        if constraint.source_relationship is not None:
            rel = constraint.source_relationship
            rec_id = rel.source_record_id
            if rec_id not in context_data:
                return (
                    CorrectnessVerdict.INCONCLUSIVE,
                    ExecutionReasonCode.SOURCE_RECORD_MISSING.value,
                    f"Context record '{rec_id}' not found in prepared fixture data.",
                    rec_id,
                    None,
                )

            found_src, src_val = extract_path_value(
                context_data[rec_id], rel.source_path
            )
            if not found_src:
                return (
                    CorrectnessVerdict.INCONCLUSIVE,
                    ExecutionReasonCode.SOURCE_PATH_MISSING.value,
                    f"Source path '{rel.source_path}' not found in record '{rec_id}'.",
                    rel.source_path,
                    None,
                )

            rel_ok, rel_msg = evaluate_source_relationship(
                actual_val, context_data, rel
            )
            if not rel_ok:
                return (
                    CorrectnessVerdict.FAIL,
                    ExecutionReasonCode.SOURCE_VALUE_MISMATCH.value,
                    f"Source relationship mismatch: {rel_msg}",
                    src_val,
                    actual_val,
                )

        return (
            CorrectnessVerdict.PASS,
            ExecutionReasonCode.MATCH.value,
            f"Argument '{arg_path}' satisfies all presence, operator, and source constraints.",
            constraint.expected_value,
            actual_val,
        )
