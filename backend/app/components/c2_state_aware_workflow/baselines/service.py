"""Baseline evaluation orchestrator service.

Evaluates frozen execution evidence across B1, B2, B3, and B4 using explicit evidence projections.
"""

import hashlib
import json
from typing import Any

from app.components.c2_state_aware_workflow.baselines.b1_final_state import (
    FinalStateEvaluator,
)
from app.components.c2_state_aware_workflow.baselines.b2_trace_only import (
    TraceOnlyEvaluator,
)
from app.components.c2_state_aware_workflow.baselines.b3_milestone import (
    MilestoneBasedEvaluator,
)
from app.components.c2_state_aware_workflow.baselines.b4_full_c2 import FullC2Evaluator
from app.components.c2_state_aware_workflow.baselines.contracts import (
    BaselinePredictionContract,
    BaselineType,
)
from app.components.c2_state_aware_workflow.baselines.projections import (
    project_evidence_for_b1,
    project_evidence_for_b2,
    project_evidence_for_b3,
    project_evidence_for_b4,
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


class BaselineEvaluationService:
    """Evaluates runtime evidence across all 4 baselines with isolated projections."""

    def __init__(self, max_configurations: int = 500):
        self.b1 = FinalStateEvaluator()
        self.b2 = TraceOnlyEvaluator()
        self.b3 = MilestoneBasedEvaluator()
        self.b4 = FullC2Evaluator(max_configurations=max_configurations)

    def evaluate_baseline(
        self,
        baseline_type: BaselineType,
        model: EFSMModelDefinition,
        test_def: GeneratedTestDefinition,
        evidence: RuntimeEvidenceContract,
        fixture_data: dict[str, Any] | None = None,
        model_is_approved: bool = True,
        pinned_content_hash: str | None = None,
    ) -> BaselinePredictionContract:
        """Evaluate a single baseline over its permitted projection."""
        source_digest = hashlib.sha256(
            json.dumps(evidence.model_dump(mode="json"), sort_keys=True).encode("utf-8")
        ).hexdigest()

        pred: BaselinePredictionContract
        match baseline_type:
            case BaselineType.B1_FINAL_STATE_ONLY:
                proj, digest = project_evidence_for_b1(evidence)
                pred = self.b1.evaluate(
                    model=model,
                    test_def=test_def,
                    projected_evidence=proj,
                    fixture_data=fixture_data,
                    evidence_digest=digest,
                )
            case BaselineType.B2_TRACE_ONLY:
                proj, digest = project_evidence_for_b2(evidence)
                pred = self.b2.evaluate(
                    model=model,
                    test_def=test_def,
                    projected_evidence=proj,
                    fixture_data=fixture_data,
                    evidence_digest=digest,
                )
            case BaselineType.B3_MILESTONE_BASED:
                proj, digest = project_evidence_for_b3(evidence, model=model)
                pred = self.b3.evaluate(
                    model=model,
                    test_def=test_def,
                    projected_evidence=proj,
                    fixture_data=fixture_data,
                    evidence_digest=digest,
                )
            case BaselineType.B4_FULL_C2:
                proj, digest = project_evidence_for_b4(evidence)
                pred = self.b4.evaluate(
                    model=model,
                    test_def=test_def,
                    projected_evidence=proj,
                    fixture_data=fixture_data,
                    evidence_digest=digest,
                    model_is_approved=model_is_approved,
                    pinned_content_hash=pinned_content_hash,
                )

        return pred.model_copy(update={"source_evidence_digest": source_digest})

    def evaluate_all(
        self,
        model: EFSMModelDefinition,
        test_def: GeneratedTestDefinition,
        evidence: RuntimeEvidenceContract,
        fixture_data: dict[str, Any] | None = None,
        model_is_approved: bool = True,
        pinned_content_hash: str | None = None,
    ) -> dict[BaselineType, BaselinePredictionContract]:
        """Evaluate all four methods (B1-B4) over the exact same frozen execution evidence."""
        results: dict[BaselineType, BaselinePredictionContract] = {}
        for b_type in [
            BaselineType.B1_FINAL_STATE_ONLY,
            BaselineType.B2_TRACE_ONLY,
            BaselineType.B3_MILESTONE_BASED,
            BaselineType.B4_FULL_C2,
        ]:
            results[b_type] = self.evaluate_baseline(
                baseline_type=b_type,
                model=model,
                test_def=test_def,
                evidence=evidence,
                fixture_data=fixture_data,
                model_is_approved=model_is_approved,
                pinned_content_hash=pinned_content_hash,
            )
        return results
