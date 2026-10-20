"""Baseline B2: Trace-only evaluation.

Inspects ordered tool-call events against allowed sequences.
Does NOT inspect intermediate or database state effects.
Localizes first sequence divergence when a call deviates from declared allowed paths.
"""

import time
from typing import Any

from app.components.c2_state_aware_workflow.baselines.contracts import (
    BaselinePredictionContract,
    BaselineType,
    EvidenceProjectionType,
)
from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)
from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    FirstDivergenceDetail,
    RuntimeVerdict,
    ViolationDetail,
    ViolationType,
)
from app.components.c2_state_aware_workflow.contracts.runtime_evidence import (
    RuntimeEvidenceContract,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    GeneratedTestDefinition,
    TestCategory,
)


class TraceOnlyEvaluator:
    """Evaluates ordered tool-event sequences against allowed EFSM graph transitions without state inspection."""

    method_id: BaselineType = BaselineType.B2_TRACE_ONLY
    method_name: str = "B2 — Trace-only"
    method_version: str = "2026.1"

    def _extract_allowed_tool_sequences(
        self, model: EFSMModelDefinition, is_negative: bool
    ) -> list[list[str]]:
        """Extract valid tool sequences (including normal, alternative, and rejection sequences)."""
        sequences: list[list[str]] = []

        target_states = set(
            model.rejection_state_ids if is_negative else model.accepting_state_ids
        )

        queue: list[tuple[str, list[str]]] = [(model.initial_state_id, [])]
        visited: set[tuple[str, tuple[str, ...]]] = set()

        while queue and len(sequences) < 25:
            curr_state, seq = queue.pop(0)
            if curr_state in target_states and seq:
                sequences.append(seq)
                continue

            for t in model.transitions:
                if t.source_state == curr_state:
                    tool_name = t.trigger_event
                    new_seq = seq + [tool_name]
                    key = (t.target_state, tuple(new_seq))
                    if key not in visited and len(new_seq) <= 10:
                        visited.add(key)
                        queue.append((t.target_state, new_seq))

        return sequences

    def evaluate(
        self,
        model: EFSMModelDefinition,
        test_def: GeneratedTestDefinition,
        projected_evidence: RuntimeEvidenceContract,
        fixture_data: dict[str, Any] | None = None,
        evidence_digest: str = "",
    ) -> BaselinePredictionContract:
        """Run B2 trace-only evaluation."""
        start_time = time.perf_counter()
        events = projected_evidence.ordered_events or []
        is_negative = test_def.category == TestCategory.NEGATIVE

        # Empty trace handling
        if not events:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return BaselinePredictionContract(
                method_id=self.method_id,
                method_name=self.method_name,
                method_version=self.method_version,
                evidence_projection=EvidenceProjectionType.ORDERED_EVENTS_ONLY,
                verdict=RuntimeVerdict.INCONCLUSIVE,
                reasons=["No tool-call events present in projected trace evidence."],
                can_localize_first_divergence=False,
                divergence_localization_unavailable_reason="Trace contains zero events to evaluate.",
                evaluator_timing_ms=elapsed_ms,
                evidence_digest_consumed=evidence_digest,
            )

        observed_tool_names = [e.tool_name for e in events]
        ev_refs = [e.event_id for e in events]

        allowed_sequences = self._extract_allowed_tool_sequences(model, is_negative)

        # Check if observed tool sequence matches any allowed path prefix or complete path
        matched_seq = None
        for allowed in allowed_sequences:
            if observed_tool_names == allowed:
                matched_seq = allowed
                break

        if matched_seq is not None:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return BaselinePredictionContract(
                method_id=self.method_id,
                method_name=self.method_name,
                method_version=self.method_version,
                evidence_projection=EvidenceProjectionType.ORDERED_EVENTS_ONLY,
                verdict=(
                    RuntimeVerdict.EXPECTED_REJECTION_PASS
                    if is_negative
                    else RuntimeVerdict.PASS
                ),
                reasons=[
                    f"Observed tool call sequence '{' -> '.join(observed_tool_names)}' conforms to declared workflow rules."
                ],
                evidence_references=ev_refs,
                can_localize_first_divergence=True,
                first_divergence=None,
                evaluator_timing_ms=elapsed_ms,
                evidence_digest_consumed=evidence_digest,
            )

        # Divergence detected in tool sequence! Find earliest deviating step
        first_div_idx = 0
        expected_at_div: list[str] = []

        for idx, obs_tool in enumerate(observed_tool_names):
            matching_at_idx = [
                allowed
                for allowed in allowed_sequences
                if len(allowed) > idx and allowed[:idx] == observed_tool_names[:idx]
            ]
            expected_next = sorted({a[idx] for a in matching_at_idx if len(a) > idx})
            if obs_tool not in expected_next:
                first_div_idx = idx
                expected_at_div = expected_next
                break
        else:
            first_div_idx = len(observed_tool_names) - 1

        first_event = events[min(first_div_idx, len(events) - 1)]
        divergence = FirstDivergenceDetail(
            event_index=first_div_idx,
            event_id=first_event.event_id,
            state_at_divergence="TRACE_SEQUENCE",
            attempted_event=first_event.tool_name,
            reason=f"Action '{first_event.tool_name}' unexpected at step {first_div_idx}. Permitted alternatives: {expected_at_div}",
            violation_type=ViolationType.INVALID_TRANSITION,
            expected_alternatives=expected_at_div,
        )

        violation = ViolationDetail(
            violation_type=ViolationType.INVALID_TRANSITION,
            event_index=first_div_idx,
            event_id=first_event.event_id,
            source_state="TRACE_SEQUENCE",
            rule_reference="DECLARED_SEQUENCE_RULES",
            message=divergence.reason,
            expected=str(expected_at_div),
            observed=first_event.tool_name,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return BaselinePredictionContract(
            method_id=self.method_id,
            method_name=self.method_name,
            method_version=self.method_version,
            evidence_projection=EvidenceProjectionType.ORDERED_EVENTS_ONLY,
            verdict=RuntimeVerdict.FAIL,
            reasons=[divergence.reason],
            evidence_references=ev_refs,
            violations=[violation],
            can_localize_first_divergence=True,
            first_divergence=divergence,
            predicted_divergence_event_id=first_event.event_id,
            predicted_divergence_step=first_div_idx,
            evaluator_timing_ms=elapsed_ms,
            evidence_digest_consumed=evidence_digest,
        )
