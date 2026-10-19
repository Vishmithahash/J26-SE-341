"""Conformance evaluation engine for C2: computes exactly the six runtime verdicts.

Verdicts:
1. PASS
2. EXPECTED REJECTION PASS
3. FAIL
4. INCONCLUSIVE
5. MODEL NOT READY
6. TEST NOT READY

Impartiality rule: Verdicts are computed strictly from reference model, test definition,
and observed evidence. Intended mutation annotations have zero influence on the computed verdict.
"""

import time
from typing import Any

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
    ExpectedOutcomeType,
    GeneratedTestDefinition,
    TestReadinessStatus,
)
from app.components.c2_state_aware_workflow.evaluator.alignment import (
    TraceToEFSMAlignmentEngine,
)
from app.components.c2_state_aware_workflow.evaluator.normalizer import TraceNormalizer
from app.components.c2_state_aware_workflow.persistence.hashing import (
    compute_model_content_hash,
)


class ConformanceEvaluationEngine:
    """Evaluates runtime evidence against pinned EFSM models and test definitions."""

    def __init__(self, max_configurations: int = 200):
        self.max_configurations = max_configurations

    def evaluate(
        self,
        model: EFSMModelDefinition,
        test_def: GeneratedTestDefinition,
        evidence: RuntimeEvidenceContract,
        fixture_data: dict[str, Any] | None = None,
        model_is_approved: bool = True,
        pinned_content_hash: str | None = None,
    ) -> EvaluationResultContract:
        """Execute full conformance evaluation pipeline and emit one of the six exact verdicts."""
        start_time = time.perf_counter()

        # 1. Check MODEL NOT READY
        if not model_is_approved:
            return EvaluationResultContract(
                verdict=RuntimeVerdict.MODEL_NOT_READY,
                reasons=["Reference EFSM model is not in APPROVED lifecycle state."],
                model_id=model.model_id,
                model_version=model.version,
                model_content_hash=pinned_content_hash
                or compute_model_content_hash(model.model_dump(mode="json")),
                test_id=test_def.test_id,
                test_version=test_def.generator_version,
                fixture_version=test_def.fixture_version,
                evaluator_timing_ms=(time.perf_counter() - start_time) * 1000.0,
            )

        calculated_hash = compute_model_content_hash(model.model_dump(mode="json"))
        if pinned_content_hash and pinned_content_hash != calculated_hash:
            return EvaluationResultContract(
                verdict=RuntimeVerdict.MODEL_NOT_READY,
                reasons=[
                    f"Model content hash mismatch: expected '{pinned_content_hash}', calculated '{calculated_hash}'."
                ],
                model_id=model.model_id,
                model_version=model.version,
                model_content_hash=calculated_hash,
                test_id=test_def.test_id,
                test_version=test_def.generator_version,
                fixture_version=test_def.fixture_version,
                evaluator_timing_ms=(time.perf_counter() - start_time) * 1000.0,
            )

        # 2. Check TEST NOT READY
        if test_def.readiness == TestReadinessStatus.TEST_NOT_READY:
            return EvaluationResultContract(
                verdict=RuntimeVerdict.TEST_NOT_READY,
                reasons=test_def.readiness_reasons
                or ["Test definition flagged as TEST_NOT_READY."],
                model_id=model.model_id,
                model_version=model.version,
                model_content_hash=calculated_hash,
                test_id=test_def.test_id,
                test_version=test_def.generator_version,
                fixture_version=test_def.fixture_version,
                evaluator_timing_ms=(time.perf_counter() - start_time) * 1000.0,
            )

        # 3. Trace normalization and evidence audit
        normalizer = TraceNormalizer(model)
        normalized_trace = normalizer.normalize(evidence)

        # 4. Alignment execution
        alignment_engine = TraceToEFSMAlignmentEngine(
            model=model,
            max_configurations=self.max_configurations,
        )
        alignment_res = alignment_engine.align(
            trace=normalized_trace,
            test_def=test_def,
            fixture_data=fixture_data,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        # 5. Determine Verdict
        if alignment_res.is_inconclusive:
            return EvaluationResultContract(
                verdict=RuntimeVerdict.INCONCLUSIVE,
                reasons=[
                    alignment_res.inconclusive_reason
                    or "Evidence insufficient for definitive conclusion."
                ],
                model_id=model.model_id,
                model_version=model.version,
                model_content_hash=calculated_hash,
                test_id=test_def.test_id,
                test_version=test_def.generator_version,
                fixture_version=test_def.fixture_version,
                observed_states=alignment_res.observed_states,
                evidence_references=[
                    evt.event_id for evt in normalized_trace.ordered_events
                ],
                evaluator_timing_ms=elapsed_ms,
            )

        if not alignment_res.is_aligned:
            reasons = [v.message for v in alignment_res.violations]
            return EvaluationResultContract(
                verdict=RuntimeVerdict.FAIL,
                reasons=reasons or ["Workflow conformance check failed."],
                model_id=model.model_id,
                model_version=model.version,
                model_content_hash=calculated_hash,
                test_id=test_def.test_id,
                test_version=test_def.generator_version,
                fixture_version=test_def.fixture_version,
                expected_states=model.accepting_state_ids,
                observed_states=alignment_res.observed_states,
                violations=alignment_res.violations,
                first_divergence=alignment_res.first_divergence,
                evidence_references=[
                    evt.event_id for evt in normalized_trace.ordered_events
                ],
                coverage=alignment_res.coverage,
                evaluator_timing_ms=elapsed_ms,
            )

        # Workflow aligned! Distinguish PASS from EXPECTED REJECTION PASS
        is_negative = (
            test_def.expected_outcome == ExpectedOutcomeType.EXPECTED_REJECTION_PASS
            or test_def.category.value == "negative"
        )

        final_verdict = (
            RuntimeVerdict.EXPECTED_REJECTION_PASS
            if is_negative
            else RuntimeVerdict.PASS
        )
        pass_reason = (
            "Agent correctly rejected ineligible request without modifying protected state."
            if is_negative
            else "All transitions, guards, entity continuity conditions, and state effects verified."
        )

        return EvaluationResultContract(
            verdict=final_verdict,
            reasons=[pass_reason],
            model_id=model.model_id,
            model_version=model.version,
            model_content_hash=calculated_hash,
            test_id=test_def.test_id,
            test_version=test_def.generator_version,
            fixture_version=test_def.fixture_version,
            expected_states=model.rejection_state_ids
            if is_negative
            else model.accepting_state_ids,
            observed_states=alignment_res.observed_states,
            violations=[],
            first_divergence=None,
            evidence_references=[
                evt.event_id for evt in normalized_trace.ordered_events
            ],
            coverage=alignment_res.coverage,
            evaluator_timing_ms=elapsed_ms,
        )
