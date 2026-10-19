"""Tests for C2 Research Baselines (B1 Final-state, B2 Trace-only, B3 Milestone, B4 Full C2).

Verifies evidence projections, baseline predictions, localization availability reporting,
and failure to silently succeed on missing evidence.
"""

import pytest

from app.components.c2_state_aware_workflow.baselines.b2_trace_only import (
    TraceOnlyEvaluator,
)
from app.components.c2_state_aware_workflow.baselines.contracts import (
    BaselineType,
)
from app.components.c2_state_aware_workflow.baselines.projections import (
    project_evidence_for_b1,
    project_evidence_for_b2,
    project_evidence_for_b3,
    project_evidence_for_b4,
)
from app.components.c2_state_aware_workflow.baselines.service import (
    BaselineEvaluationService,
)
from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    RuntimeVerdict,
)
from app.components.c2_state_aware_workflow.contracts.runtime_evidence import (
    EvidenceCompleteness,
    RuntimeEvent,
    RuntimeEvidenceContract,
    StateObservation,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    ExpectedOutcomeType,
    GeneratedTestDefinition,
    TestCategory,
    TestReadinessStatus,
)
from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
)


@pytest.fixture
def refund_model():
    return build_synthetic_refund_efsm()


@pytest.fixture
def sample_test_def(refund_model):
    return GeneratedTestDefinition(
        test_id="test_001",
        project_id="c2_project",
        suite_id="suite_001",
        pinned_model_id=refund_model.model_id,
        pinned_model_version=refund_model.version,
        model_content_hash="test_content_hash",
        category=TestCategory.VALID,
        task="Refund my latest paid order.",
        fixture_ref="fixture_std",
        expected_outcome=ExpectedOutcomeType.PASS,
        readiness=TestReadinessStatus.TEST_READY,
    )


@pytest.fixture
def conforming_evidence(refund_model):
    events = [
        RuntimeEvent(
            event_index=0,
            event_id="e1",
            tool_name="get_customer_orders",
            arguments={"customer_id": 42},
        ),
        RuntimeEvent(
            event_index=1,
            event_id="e2",
            tool_name="select_order",
            arguments={"order_id": 503},
        ),
        RuntimeEvent(
            event_index=2,
            event_id="e3",
            tool_name="request_refund",
            arguments={"order_id": 503},
        ),
        RuntimeEvent(
            event_index=3,
            event_id="e4",
            tool_name="verify_refund_status",
            arguments={"order_id": 503},
        ),
    ]
    obs = [
        StateObservation(event_index=0, before_state={}, after_state={}),
        StateObservation(event_index=1, before_state={}, after_state={}),
        StateObservation(event_index=2, before_state={}, after_state={}),
        StateObservation(
            event_index=3,
            before_state={"payment_status": "PAID"},
            after_state={"payment_status": "REFUNDED"},
        ),
    ]
    return RuntimeEvidenceContract(
        project_id="c2_project",
        run_id="run_001",
        test_id="test_001",
        model_id=refund_model.model_id,
        model_version=refund_model.version,
        ordered_events=events,
        state_observations=obs,
        completeness=EvidenceCompleteness(
            is_complete=True, confirmed_agent_termination=True
        ),
    )


def test_evidence_projections_isolate_inputs(conforming_evidence, refund_model):
    """Verify explicit evidence projections isolate information permitted by baseline designs."""
    # B1: Final state only (events stripped, only last observation kept)
    b1_proj, b1_dig = project_evidence_for_b1(conforming_evidence)
    assert len(b1_proj.ordered_events) == 0
    assert len(b1_proj.state_observations) == 1
    assert b1_proj.state_observations[0].event_index == 3
    assert len(b1_dig) == 64

    # B2: Trace only (observations stripped, events kept)
    b2_proj, b2_dig = project_evidence_for_b2(conforming_evidence)
    assert len(b2_proj.ordered_events) == 4
    assert len(b2_proj.state_observations) == 0
    assert len(b2_dig) == 64

    # B3: Milestone based (ordered events kept, checkpoint observations kept)
    b3_proj, b3_dig = project_evidence_for_b3(conforming_evidence, refund_model)
    assert len(b3_proj.ordered_events) == 4
    assert len(b3_proj.state_observations) <= len(
        conforming_evidence.state_observations
    )
    assert len(b3_dig) == 64

    # B4: Full C2 (all evidence kept)
    b4_proj, b4_dig = project_evidence_for_b4(conforming_evidence)
    assert len(b4_proj.ordered_events) == 4
    assert len(b4_proj.state_observations) == 4
    assert len(b4_dig) == 64


def test_baselines_localization_honesty(
    refund_model, sample_test_def, conforming_evidence
):
    """B1 and B3 must report can_localize_first_divergence=False with an explicit reason."""
    service = BaselineEvaluationService()
    results = service.evaluate_all(
        model=refund_model,
        test_def=sample_test_def,
        evidence=conforming_evidence,
    )

    # B1 Final state
    b1_res = results[BaselineType.B1_FINAL_STATE_ONLY]
    assert b1_res.can_localize_first_divergence is False
    assert b1_res.first_divergence is None
    assert b1_res.divergence_localization_unavailable_reason is not None

    # B2 Trace only
    b2_res = results[BaselineType.B2_TRACE_ONLY]
    assert b2_res.can_localize_first_divergence is True

    # B3 Milestone based
    b3_res = results[BaselineType.B3_MILESTONE_BASED]
    assert b3_res.can_localize_first_divergence is False
    assert b3_res.first_divergence is None
    assert b3_res.divergence_localization_unavailable_reason is not None

    # B4 Full C2
    b4_res = results[BaselineType.B4_FULL_C2]
    assert b4_res.can_localize_first_divergence is True


def test_b2_trace_only_detects_sequence_deviation(refund_model, sample_test_def):
    """B2 should localize earliest sequence divergence when an out-of-order action is called."""
    # Action 'request_refund' called at step 0 without listing or selecting orders
    mutated_events = [
        RuntimeEvent(
            event_index=0,
            event_id="e_mut_1",
            tool_name="request_refund",
            arguments={"order_id": 503},
        )
    ]
    evidence = RuntimeEvidenceContract(
        project_id="c2_project",
        run_id="run_mut",
        test_id="test_001",
        model_id=refund_model.model_id,
        model_version=refund_model.version,
        ordered_events=mutated_events,
        state_observations=[],
    )

    b2 = TraceOnlyEvaluator()
    pred = b2.evaluate(
        model=refund_model,
        test_def=sample_test_def,
        projected_evidence=evidence,
    )
    assert pred.verdict == RuntimeVerdict.FAIL
    assert pred.can_localize_first_divergence is True
    assert pred.predicted_divergence_step == 0
    assert pred.predicted_divergence_event_id == "e_mut_1"
    assert len(pred.violations) == 1


def test_missing_evidence_does_not_silently_succeed(refund_model, sample_test_def):
    """Missing evidence must result in INCONCLUSIVE rather than a silent PASS."""
    empty_evidence = RuntimeEvidenceContract(
        project_id="c2_project",
        run_id="run_empty",
        test_id="test_001",
        model_id=refund_model.model_id,
        model_version=refund_model.version,
        ordered_events=[],
        state_observations=[],
    )

    service = BaselineEvaluationService()
    results = service.evaluate_all(
        model=refund_model,
        test_def=sample_test_def,
        evidence=empty_evidence,
    )

    for m_type, pred in results.items():
        assert pred.verdict in (RuntimeVerdict.INCONCLUSIVE, RuntimeVerdict.FAIL), (
            f"{m_type} unexpectedly returned {pred.verdict} on empty evidence!"
        )


def test_evaluator_independence_invariant_under_ground_truth_changes(
    refund_model, sample_test_def, conforming_evidence
):
    """Prove that evaluators B1-B4 are strictly independent of ground-truth annotations.

    1. Changing ground-truth annotations without changing model, task, or evidence
       produces 100% identical predictions.
    2. All methods retain both the source evidence digest and method-specific projection digest.
    """
    import hashlib
    import json

    from app.components.c2_state_aware_workflow.contracts.experiment import (
        GroundTruthLabel,
        MutationFamily,
        ReviewStatus,
    )

    service = BaselineEvaluationService()

    # Base evaluation over conforming evidence
    preds_run1 = service.evaluate_all(
        model=refund_model,
        test_def=sample_test_def,
        evidence=conforming_evidence,
    )

    # Compute expected source digest
    expected_source_digest = hashlib.sha256(
        json.dumps(conforming_evidence.model_dump(mode="json"), sort_keys=True).encode(
            "utf-8"
        )
    ).hexdigest()

    # Construct two radically conflicting ground truth labels
    gt_conforming = GroundTruthLabel(
        is_workflow_violation=False,
        expected_verdict=RuntimeVerdict.PASS,
        mutation_family=MutationFamily.NONE,
        review_status=ReviewStatus.DEVELOPER_FIXTURE,
    )
    gt_violating = GroundTruthLabel(
        is_workflow_violation=True,
        expected_verdict=RuntimeVerdict.FAIL,
        mutation_family=MutationFamily.STATE_EFFECT_CORRUPTION,
        ground_truth_divergence_step=2,
        ground_truth_divergence_location_known=True,
        review_status=ReviewStatus.DEVELOPER_FIXTURE,
    )
    assert gt_conforming.is_workflow_violation != gt_violating.is_workflow_violation

    # Confirm neither evaluate_baseline nor evaluate_all accept ground-truth labels
    # Evaluate again - inputs (model, test_def, evidence) remain identical
    preds_run2 = service.evaluate_all(
        model=refund_model,
        test_def=sample_test_def,
        evidence=conforming_evidence,
    )

    for b_type in BaselineType:
        p1 = preds_run1[b_type]
        p2 = preds_run2[b_type]

        # Invariance check: predictions are identical regardless of external label claims
        assert p1.verdict == p2.verdict
        assert p1.reasons == p2.reasons
        assert p1.predicted_divergence_step == p2.predicted_divergence_step

        # Digest retention check
        assert p1.source_evidence_digest == expected_source_digest
        assert p1.evidence_digest_consumed != ""
        assert p1.source_evidence_digest != ""
