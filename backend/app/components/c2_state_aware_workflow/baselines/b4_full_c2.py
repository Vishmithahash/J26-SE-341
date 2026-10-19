"""Baseline B4: Full C2 State-Aware Alignment Evaluator.

Invokes the full state-aware conformance evaluation engine over complete permitted evidence.
Features fine-grained Kleene logic guard solving, before/after diffing, entity continuity, and first-divergence localization.
"""

from typing import Any

from app.components.c2_state_aware_workflow.baselines.contracts import (
    BaselinePredictionContract,
    BaselineType,
    EvidenceProjectionType,
)
from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)
from app.components.c2_state_aware_workflow.contracts.runtime_evidence import (
    RuntimeEvidenceContract,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    GeneratedTestDefinition,
)
from app.components.c2_state_aware_workflow.evaluator.engine import (
    ConformanceEvaluationEngine,
)


class FullC2Evaluator:
    """Invokes actual C2 state-aware conformance evaluation engine over full permitted evidence."""

    method_id: BaselineType = BaselineType.B4_FULL_C2
    method_name: str = "B4 — Full C2 State-Aware Alignment"
    method_version: str = "2026.1"

    def __init__(self, max_configurations: int = 500):
        self.engine = ConformanceEvaluationEngine(max_configurations=max_configurations)

    def evaluate(
        self,
        model: EFSMModelDefinition,
        test_def: GeneratedTestDefinition,
        projected_evidence: RuntimeEvidenceContract,
        fixture_data: dict[str, Any] | None = None,
        evidence_digest: str = "",
        model_is_approved: bool = True,
        pinned_content_hash: str | None = None,
    ) -> BaselinePredictionContract:
        """Run B4 full state-aware conformance evaluation."""
        eval_result = self.engine.evaluate(
            model=model,
            test_def=test_def,
            evidence=projected_evidence,
            fixture_data=fixture_data,
            model_is_approved=model_is_approved,
            pinned_content_hash=pinned_content_hash,
        )

        first_div = eval_result.first_divergence
        pred_event_id = first_div.event_id if first_div else None
        pred_step = first_div.event_index if first_div else None

        return BaselinePredictionContract(
            method_id=self.method_id,
            method_name=self.method_name,
            method_version=self.method_version,
            evidence_projection=EvidenceProjectionType.FULL_PERMITTED_EVIDENCE,
            verdict=eval_result.verdict,
            reasons=eval_result.reasons,
            evidence_references=eval_result.evidence_references,
            violations=eval_result.violations,
            can_localize_first_divergence=True,
            first_divergence=first_div,
            predicted_divergence_event_id=pred_event_id,
            predicted_divergence_step=pred_step,
            evaluator_timing_ms=eval_result.evaluator_timing_ms,
            evidence_digest_consumed=evidence_digest,
            detailed_coverage=eval_result.detailed_coverage,
            evaluated_at=eval_result.evaluated_at,
        )
