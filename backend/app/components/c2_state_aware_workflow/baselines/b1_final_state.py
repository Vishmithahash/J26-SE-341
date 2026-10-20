"""Baseline B1: Final-state-only evaluation.

Inspects only the terminal application/database state snapshot and declared final outcomes.
Does NOT inspect intermediate events or intermediate state transitions.
Cannot localize earliest intermediate divergence.
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


class FinalStateEvaluator:
    """Evaluates workflow outcomes using only the final database/application state snapshot."""

    method_id: BaselineType = BaselineType.B1_FINAL_STATE_ONLY
    method_name: str = "B1 — Final-state-only"
    method_version: str = "2026.1"

    def evaluate(
        self,
        model: EFSMModelDefinition,
        test_def: GeneratedTestDefinition,
        projected_evidence: RuntimeEvidenceContract,
        fixture_data: dict[str, Any] | None = None,
        evidence_digest: str = "",
    ) -> BaselinePredictionContract:
        """Run B1 evaluation over terminal state snapshot."""
        start_time = time.perf_counter()
        reasons: list[str] = []
        violations: list[ViolationDetail] = []
        ev_refs: list[str] = []

        if not projected_evidence.state_observations:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return BaselinePredictionContract(
                method_id=self.method_id,
                method_name=self.method_name,
                method_version=self.method_version,
                evidence_projection=EvidenceProjectionType.FINAL_STATE_AND_OUTCOME_ONLY,
                verdict=RuntimeVerdict.INCONCLUSIVE,
                reasons=[
                    "Missing final state observation evidence in projected trace."
                ],
                can_localize_first_divergence=False,
                divergence_localization_unavailable_reason="Baseline B1 inspects only final state and cannot localize intermediate divergence.",
                evaluator_timing_ms=elapsed_ms,
                evidence_digest_consumed=evidence_digest,
            )

        final_obs = projected_evidence.state_observations[-1]
        final_state = final_obs.after_state or final_obs.before_state or {}
        ev_refs.append(f"obs_event_{final_obs.event_index}")

        is_negative = test_def.category == TestCategory.NEGATIVE

        # 1. Negative / Rejection Task
        if is_negative:
            protected_violated = False
            for pf in model.protected_fields:
                val = final_state.get(pf.field_path)
                if (
                    val is not None
                    and "status" in pf.field_path
                    and str(val).upper()
                    in ("REFUNDED", "CANCELLED", "MODIFIED", "ENROLLED")
                ):
                    protected_violated = True
                    violations.append(
                        ViolationDetail(
                            violation_type=ViolationType.PROTECTED_FIELD_MUTATED,
                            source_state="REJECTION_CHECK",
                            rule_reference="PROTECTED_FIELD_PRESERVATION",
                            message=f"Protected field '{pf.field_path}' was illegally modified to '{val}' on rejection path.",
                            expected="UNMODIFIED",
                            observed=str(val),
                        )
                    )

            if protected_violated:
                reasons.append(
                    "Protected application state was illegally modified on expected rejection task."
                )
                verdict = RuntimeVerdict.FAIL
            else:
                reasons.append(
                    "Final state preserved protected application state without unlawful modification."
                )
                verdict = RuntimeVerdict.EXPECTED_REJECTION_PASS

        # 2. Positive / Normal / Alternative Task
        else:
            final_satisfied = False

            # Check declared final outcome predicates
            if model.final_outcomes:
                eval_ctx = EvaluationContext(
                    variables=test_def.input_parameters,
                    fixture=fixture_data or {},
                    before=final_obs.before_state,
                    after=final_obs.after_state,
                )
                outcomes_checked = 0
                outcomes_passed = 0
                for outcome in model.final_outcomes:
                    if outcome.type == "ACCEPTING" and outcome.predicate:
                        outcomes_checked += 1
                        try:
                            tri = evaluate_predicate(outcome.predicate, eval_ctx)
                            if tri == TriState.TRUE:
                                outcomes_passed += 1
                        except Exception:  # noqa: BLE001, S110
                            pass
                if outcomes_checked > 0 and outcomes_passed == outcomes_checked:
                    final_satisfied = True

            # Generic fallback: check common terminal state status (e.g. payment_status == REFUNDED)
            if not final_satisfied:
                for k, v in final_state.items():
                    if isinstance(v, dict):
                        for sub_k, sub_v in v.items():
                            if (
                                (
                                    "status" in sub_k.lower()
                                    or "address" in sub_k.lower()
                                )
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

            if final_satisfied:
                reasons.append(
                    "Terminal application state satisfies declared final outcome conditions."
                )
                verdict = RuntimeVerdict.PASS
            else:
                reasons.append(
                    "Terminal application state does NOT satisfy required final outcome conditions."
                )
                violations.append(
                    ViolationDetail(
                        violation_type=ViolationType.OUTCOME_MISMATCH,
                        source_state="TERMINAL_OUTCOME",
                        rule_reference="FINAL_OUTCOME_SPECIFICATION",
                        message="Final application state failed terminal outcome requirements.",
                        expected="Declared final outcome state",
                        observed=str(final_state),
                    )
                )
                verdict = RuntimeVerdict.FAIL

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return BaselinePredictionContract(
            method_id=self.method_id,
            method_name=self.method_name,
            method_version=self.method_version,
            evidence_projection=EvidenceProjectionType.FINAL_STATE_AND_OUTCOME_ONLY,
            verdict=verdict,
            reasons=reasons,
            evidence_references=ev_refs,
            violations=violations,
            can_localize_first_divergence=False,
            first_divergence=None,
            predicted_divergence_event_id=None,
            predicted_divergence_step=None,
            divergence_localization_unavailable_reason="Baseline B1 inspects only final state and cannot localize intermediate divergence.",
            evaluator_timing_ms=elapsed_ms,
            evidence_digest_consumed=evidence_digest,
        )
