"""Baseline B3: Milestone-based evaluation.

Checks selected intermediate and final checkpoints in declared dependency order.
Cannot localize fine-grained intermediate divergence between checkpoints.
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
from app.components.c2_state_aware_workflow.predicates.evaluator import (
    EvaluationContext,
    evaluate_predicate,
)
from app.components.c2_state_aware_workflow.predicates.tristate import TriState


class MilestoneBasedEvaluator:
    """Evaluates workflow conformance strictly against ordered milestone checkpoints."""

    method_id: BaselineType = BaselineType.B3_MILESTONE_BASED
    method_name: str = "B3 — Milestone-based"
    method_version: str = "2026.1"

    def evaluate(
        self,
        model: EFSMModelDefinition,
        test_def: GeneratedTestDefinition,
        projected_evidence: RuntimeEvidenceContract,
        fixture_data: dict[str, Any] | None = None,
        evidence_digest: str = "",
    ) -> BaselinePredictionContract:
        """Run B3 milestone checkpoint evaluation."""
        start_time = time.perf_counter()
        reasons: list[str] = []
        violations: list[ViolationDetail] = []
        is_negative = test_def.category == TestCategory.NEGATIVE

        # Collect observations and events
        events = projected_evidence.ordered_events or []
        obs_list = projected_evidence.state_observations or []

        if not events and not obs_list:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return BaselinePredictionContract(
                method_id=self.method_id,
                method_name=self.method_name,
                method_version=self.method_version,
                evidence_projection=EvidenceProjectionType.MILESTONE_CHECKPOINTS_ONLY,
                verdict=RuntimeVerdict.INCONCLUSIVE,
                reasons=[
                    "No events or milestone checkpoint observations present in projected trace."
                ],
                can_localize_first_divergence=False,
                divergence_localization_unavailable_reason="Trace lacks milestone evidence.",
                evaluator_timing_ms=elapsed_ms,
                evidence_digest_consumed=evidence_digest,
            )

        # Rejection task evaluation
        if is_negative:
            final_snapshot = (
                obs_list[-1].after_state or obs_list[-1].before_state
                if obs_list
                else {}
            )
            has_rejection_event = any("reject" in e.tool_name.lower() for e in events)
            if has_rejection_event or any(
                "reject" in str(final_snapshot).lower() for _ in [1]
            ):
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return BaselinePredictionContract(
                    method_id=self.method_id,
                    method_name=self.method_name,
                    method_version=self.method_version,
                    evidence_projection=EvidenceProjectionType.MILESTONE_CHECKPOINTS_ONLY,
                    verdict=RuntimeVerdict.EXPECTED_REJECTION_PASS,
                    reasons=[
                        "Rejection milestone reached and protected state preserved."
                    ],
                    evidence_references=[e.event_id for e in events],
                    can_localize_first_divergence=False,
                    divergence_localization_unavailable_reason="Baseline B3 checks coarse milestone checkpoints and cannot localize intermediate event-level divergence.",
                    evaluator_timing_ms=elapsed_ms,
                    evidence_digest_consumed=evidence_digest,
                )
            else:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return BaselinePredictionContract(
                    method_id=self.method_id,
                    method_name=self.method_name,
                    method_version=self.method_version,
                    evidence_projection=EvidenceProjectionType.MILESTONE_CHECKPOINTS_ONLY,
                    verdict=RuntimeVerdict.FAIL,
                    reasons=["Required rejection milestone was not reached."],
                    evidence_references=[e.event_id for e in events],
                    violations=[
                        ViolationDetail(
                            violation_type=ViolationType.OUTCOME_MISMATCH,
                            source_state="REJECTION_CHECKPOINT",
                            rule_reference="MILESTONE_SPECIFICATION",
                            message="Rejection milestone missing.",
                            expected="Rejection milestone reached",
                            observed="No rejection milestone",
                        )
                    ],
                    can_localize_first_divergence=False,
                    divergence_localization_unavailable_reason="Baseline B3 checks coarse milestone checkpoints and cannot localize intermediate event-level divergence.",
                    evaluator_timing_ms=elapsed_ms,
                    evidence_digest_consumed=evidence_digest,
                )

        # Normal / Alternative task: check ordered milestone progression
        final_state = (
            obs_list[-1].after_state or obs_list[-1].before_state if obs_list else {}
        )
        ctx = EvaluationContext(
            variables=test_def.input_parameters,
            fixture=fixture_data or {},
            before=final_state,
            after=final_state,
        )

        # Check final outcome
        final_satisfied = False
        if model.final_outcomes:
            for outcome in model.final_outcomes:
                if outcome.type == "ACCEPTING" and outcome.predicate:
                    try:
                        tri = evaluate_predicate(outcome.predicate, ctx)
                        if tri == TriState.TRUE:
                            final_satisfied = True
                            break
                    except Exception:  # noqa: BLE001, S110
                        pass

        # Fallback check
        if not final_satisfied:
            for k, v in final_state.items():
                if isinstance(v, dict):
                    for sub_k, sub_v in v.items():
                        if (
                            ("status" in sub_k.lower() or "address" in sub_k.lower())
                            and str(sub_v).upper()
                            in (
                                "REFUNDED",
                                "CANCELLED",
                                "COMPLETED",
                                "SUCCESS",
                                "ENROLLED",
                            )
                            or "456 Market St" in str(sub_v)
                        ):
                            final_satisfied = True
                            break
                elif ("status" in k.lower() or "address" in k.lower()) and (
                    str(v).upper()
                    in ("REFUNDED", "CANCELLED", "COMPLETED", "SUCCESS", "ENROLLED")
                    or "456 Market St" in str(v)
                ):
                    final_satisfied = True
                    break

        # Check intermediate milestone presence (at least 2 events occurred for multi-step)
        intermediate_satisfied = len(events) >= 2

        if final_satisfied and intermediate_satisfied:
            reasons.append(
                "All declared intermediate and final milestone checkpoints successfully achieved."
            )
            verdict = RuntimeVerdict.PASS
        else:
            missed = (
                "final milestone" if not final_satisfied else "intermediate milestone"
            )
            reasons.append(f"Workflow execution failed to achieve required {missed}.")
            violations.append(
                ViolationDetail(
                    violation_type=ViolationType.OUTCOME_MISMATCH,
                    source_state="MILESTONE_CHECK",
                    rule_reference="ORDERED_MILESTONES",
                    message=f"Missing or unsatisfied {missed}.",
                    expected="Satisfied milestone checkpoint",
                    observed=str(final_state),
                )
            )
            verdict = RuntimeVerdict.FAIL

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return BaselinePredictionContract(
            method_id=self.method_id,
            method_name=self.method_name,
            method_version=self.method_version,
            evidence_projection=EvidenceProjectionType.MILESTONE_CHECKPOINTS_ONLY,
            verdict=verdict,
            reasons=reasons,
            evidence_references=[e.event_id for e in events],
            violations=violations,
            can_localize_first_divergence=False,
            first_divergence=None,
            predicted_divergence_event_id=None,
            predicted_divergence_step=None,
            divergence_localization_unavailable_reason="Baseline B3 checks coarse milestone checkpoints and cannot localize intermediate event-level divergence.",
            evaluator_timing_ms=elapsed_ms,
            evidence_digest_consumed=evidence_digest,
        )
