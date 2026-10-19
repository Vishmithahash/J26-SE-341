"""Comprehensive unit and integration tests for C2 State-Aware Evaluation (Part B).

Covers:
1. Resettable synthetic SUT & independent state observer.
2. Trace normalizer with sequence audits and anomaly detection.
3. Trace-to-EFSM alignment with non-deterministic branching.
4. Earliest first-proven-divergence localisation.
5. All six runtime verdicts:
   - PASS
   - EXPECTED REJECTION PASS
   - FAIL (skipped step, reordered, repeated, wrong entity, missing effect, protected mutation, premature termination)
   - INCONCLUSIVE (missing observations, truncated trace, sequence gaps)
   - MODEL NOT READY
   - TEST NOT READY
6. Non-interference: changing mutation labels does not affect computed verdicts.
7. Generality: custom customer and order IDs with different timestamps.
"""

import pytest

from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    RuntimeVerdict,
    ViolationType,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    ExpectedOutcomeType,
    GeneratedTestDefinition,
    TestCategory,
    TestReadinessStatus,
)
from app.components.c2_state_aware_workflow.evaluator.engine import (
    ConformanceEvaluationEngine,
)
from app.components.c2_state_aware_workflow.evaluator.fixtures import (
    ControlledTraceFixtures,
    ScriptedDemonstrationAgent,
)
from app.components.c2_state_aware_workflow.evaluator.normalizer import TraceNormalizer
from app.components.c2_state_aware_workflow.evaluator.observer import (
    IndependentStateObserver,
)
from app.components.c2_state_aware_workflow.evaluator.sut import SyntheticRefundSUT
from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
    build_synthetic_unpaid_order_rejection_efsm,
)


@pytest.fixture
def refund_model():
    return build_synthetic_refund_efsm()


@pytest.fixture
def unpaid_rejection_model():
    return build_synthetic_unpaid_order_rejection_efsm()


@pytest.fixture
def valid_test_def():
    return GeneratedTestDefinition(
        test_id="test_refund_503_valid",
        project_id="test_proj",
        pinned_model_id="c2_refund_efsm_nexacart",
        pinned_model_version="1.0.0",
        model_content_hash="",
        category=TestCategory.VALID,
        task="Refund my latest paid order (Customer 42)",
        fixture_ref="fixture_default",
        expected_outcome=ExpectedOutcomeType.PASS,
        readiness=TestReadinessStatus.TEST_READY,
    )


@pytest.fixture
def rejection_test_def():
    return GeneratedTestDefinition(
        test_id="test_reject_502_unpaid",
        project_id="test_proj",
        pinned_model_id="c2_unpaid_rejection_efsm_nexacart",
        pinned_model_version="1.0.0",
        model_content_hash="",
        category=TestCategory.NEGATIVE,
        task="Refund unpaid order 502 for Customer 42",
        fixture_ref="fixture_default",
        expected_outcome=ExpectedOutcomeType.EXPECTED_REJECTION_PASS,
        readiness=TestReadinessStatus.TEST_READY,
    )


# 1. Independent SUT and Observer
def test_independent_sut_and_state_observer():
    """Verify SUT provides independent mutable state and observer captures before/after diffs."""
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)

    # State before any action
    init_state = sut.get_state_snapshot()
    assert init_state["order_503_payment_status"] == "PAID"
    assert init_state["payment_status"] == "PENDING"

    # Observe get_customer_orders (read-only)
    observer.observe_tool_call(
        event_index=0,
        event_id="evt_001",
        tool_name="get_customer_orders",
        tool_callable=sut.get_customer_orders,
        arguments={"customer_id": 42},
    )
    assert len(observer.events) == 1
    assert len(observer.observations) == 1
    # Read-only action produces empty state diff for domain entities
    obs = observer.observations[0]
    assert (
        obs.before_state["order_503_payment_status"]
        == obs.after_state["order_503_payment_status"]
    )

    # Observe request_refund (state mutation)
    observer.observe_tool_call(
        event_index=1,
        event_id="evt_002",
        tool_name="request_refund",
        tool_callable=sut.request_refund,
        arguments={
            "customer_id": 42,
            "order_id": 503,
            "reason": "damaged",
            "api_key": "secret_123",
        },
    )
    assert len(observer.events) == 2
    obs2 = observer.observations[1]
    assert obs2.before_state["order_503_payment_status"] == "PAID"
    assert obs2.after_state["order_503_payment_status"] == "REFUNDED"
    assert obs2.after_state["payment_status"] == "REFUNDED"

    # Check secret redaction
    assert observer.events[1].arguments["api_key"] == "[REDACTED]"


# 2. Trace Normalizer Audits
def test_trace_normalizer_audits_sequence_and_anomalies(refund_model):
    """Verify normalizer flags duplicate event IDs and sequence gaps without silently repairing."""
    normalizer = TraceNormalizer(refund_model)
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)

    clean_ev = agent.run_happy_path(
        project_id="p1",
        test_id="t1",
        run_id="r1",
        model_id=refund_model.model_id,
        model_version=refund_model.version,
    )
    norm_clean = normalizer.normalize(clean_ev)
    assert norm_clean.has_audit_anomalies is False

    # Broken correlation fixture
    broken_ev = ControlledTraceFixtures.create_broken_correlation_trace(clean_ev)
    norm_broken = normalizer.normalize(broken_ev)
    assert norm_broken.has_audit_anomalies is True
    assert any(
        "Conflicting duplicate event ID" in d or "Sequence index gap" in d
        for d in norm_broken.diagnostics
    )


# 3. Valid Workflows: PASS and EXPECTED REJECTION PASS
def test_evaluation_happy_path_verdict_pass(refund_model, valid_test_def):
    """Standard valid refund workflow achieves PASS verdict."""
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)

    evidence = agent.run_happy_path(
        project_id=valid_test_def.project_id,
        test_id=valid_test_def.test_id,
        run_id="run_happy_01",
        model_id=refund_model.model_id,
        model_version=refund_model.version,
    )

    engine = ConformanceEvaluationEngine()
    result = engine.evaluate(
        model=refund_model, test_def=valid_test_def, evidence=evidence
    )

    assert result.verdict == RuntimeVerdict.PASS
    assert len(result.violations) == 0
    assert result.first_divergence is None
    assert result.coverage.transitions_covered >= 4


def test_evaluation_inspection_alternative_verdict_pass(refund_model, valid_test_def):
    """Permitted alternative with optional order details inspection achieves PASS."""
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)

    evidence = agent.run_inspection_alternative(
        project_id=valid_test_def.project_id,
        test_id=valid_test_def.test_id,
        run_id="run_alt_01",
        model_id=refund_model.model_id,
        model_version=refund_model.version,
    )

    engine = ConformanceEvaluationEngine()
    result = engine.evaluate(
        model=refund_model, test_def=valid_test_def, evidence=evidence
    )

    assert result.verdict == RuntimeVerdict.PASS
    assert len(result.violations) == 0
    assert "ORDER_DETAILS_INSPECTED" in result.observed_states


def test_evaluation_unpaid_order_expected_rejection_pass(
    unpaid_rejection_model, rejection_test_def
):
    """Negative task to refund unpaid order 502 correctly achieves EXPECTED REJECTION PASS."""
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)

    evidence = agent.run_unpaid_order_rejection(
        project_id=rejection_test_def.project_id,
        test_id=rejection_test_def.test_id,
        run_id="run_unpaid_01",
        model_id=unpaid_rejection_model.model_id,
        model_version=unpaid_rejection_model.version,
    )

    engine = ConformanceEvaluationEngine()
    result = engine.evaluate(
        model=unpaid_rejection_model, test_def=rejection_test_def, evidence=evidence
    )

    assert result.verdict == RuntimeVerdict.EXPECTED_REJECTION_PASS
    assert len(result.violations) == 0


def test_rejecting_unpaid_order_does_not_satisfy_positive_task(
    refund_model, valid_test_def
):
    """Rejecting unpaid order 502 must FAIL when the task was to refund latest paid order 503."""
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)

    evidence = agent.run_unpaid_order_rejection(
        project_id=valid_test_def.project_id,
        test_id=valid_test_def.test_id,
        run_id="run_unpaid_wrong_task",
        model_id=refund_model.model_id,
        model_version=refund_model.version,
    )

    engine = ConformanceEvaluationEngine()
    result = engine.evaluate(
        model=refund_model, test_def=valid_test_def, evidence=evidence
    )

    assert result.verdict == RuntimeVerdict.FAIL
    assert any(
        v.violation_type == ViolationType.OUTCOME_MISMATCH for v in result.violations
    )


# 4. Flawed Execution and Divergence Localisation (FAIL Verdicts)
def test_evaluation_skipped_step_first_divergence(refund_model, valid_test_def):
    """Skipping select_order localises earliest divergence at request_refund."""
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)

    evidence = agent.run_flawed_demonstration(
        flaw_type="skipped_step",
        project_id=valid_test_def.project_id,
        test_id=valid_test_def.test_id,
        run_id="run_skip_01",
        model_id=refund_model.model_id,
        model_version=refund_model.version,
    )

    engine = ConformanceEvaluationEngine()
    result = engine.evaluate(
        model=refund_model, test_def=valid_test_def, evidence=evidence
    )

    assert result.verdict == RuntimeVerdict.FAIL
    assert result.first_divergence is not None
    assert result.first_divergence.event_index == 1
    assert result.first_divergence.attempted_event == "request_refund"
    assert result.first_divergence.state_at_divergence == "PAID_ORDERS_RETRIEVED"


def test_evaluation_reordered_step_divergence(refund_model, valid_test_def):
    """Reordering actions localises divergence at out-of-order action."""
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)

    evidence = agent.run_flawed_demonstration(
        flaw_type="reordered_step",
        project_id=valid_test_def.project_id,
        test_id=valid_test_def.test_id,
        run_id="run_reorder_01",
        model_id=refund_model.model_id,
        model_version=refund_model.version,
    )

    engine = ConformanceEvaluationEngine()
    result = engine.evaluate(
        model=refund_model, test_def=valid_test_def, evidence=evidence
    )

    assert result.verdict == RuntimeVerdict.FAIL
    assert result.first_divergence is not None
    assert result.first_divergence.attempted_event == "request_refund"


def test_evaluation_wrong_entity_divergence_with_valid_order_501(
    refund_model, valid_test_def
):
    """Selecting order 503 but refunding valid order 501 triggers ENTITY_MISMATCH violation."""
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)

    evidence = agent.run_flawed_demonstration(
        flaw_type="wrong_entity",
        project_id=valid_test_def.project_id,
        test_id=valid_test_def.test_id,
        run_id="run_wrong_entity_01",
        model_id=refund_model.model_id,
        model_version=refund_model.version,
    )

    engine = ConformanceEvaluationEngine()
    result = engine.evaluate(
        model=refund_model, test_def=valid_test_def, evidence=evidence
    )

    assert result.verdict == RuntimeVerdict.FAIL
    assert result.first_divergence is not None
    assert result.first_divergence.violation_type == ViolationType.ENTITY_MISMATCH
    assert "order_id 501" in result.first_divergence.reason


def test_evaluation_repeated_step_divergence(refund_model, valid_test_def):
    """Calling non-repeatable request_refund twice localises divergence at duplicate call."""
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)

    evidence = agent.run_flawed_demonstration(
        flaw_type="repeated_step",
        project_id=valid_test_def.project_id,
        test_id=valid_test_def.test_id,
        run_id="run_repeat_01",
        model_id=refund_model.model_id,
        model_version=refund_model.version,
    )

    engine = ConformanceEvaluationEngine()
    result = engine.evaluate(
        model=refund_model, test_def=valid_test_def, evidence=evidence
    )

    assert result.verdict == RuntimeVerdict.FAIL
    assert result.first_divergence is not None
    assert result.first_divergence.event_index == 3
    assert result.first_divergence.attempted_event == "request_refund"


def test_evaluation_missing_effect_divergence(refund_model, valid_test_def):
    """Success tool response without expected state effect produces MISSING_EFFECT failure."""
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)

    base_ev = agent.run_happy_path(
        project_id=valid_test_def.project_id,
        test_id=valid_test_def.test_id,
        run_id="run_base_missing_eff",
        model_id=refund_model.model_id,
        model_version=refund_model.version,
    )
    evidence = ControlledTraceFixtures.create_missing_effect_trace(base_ev)

    engine = ConformanceEvaluationEngine()
    result = engine.evaluate(
        model=refund_model, test_def=valid_test_def, evidence=evidence
    )

    assert result.verdict == RuntimeVerdict.FAIL
    assert result.first_divergence is not None
    assert result.first_divergence.violation_type == ViolationType.MISSING_EFFECT


def test_evaluation_protected_state_mutation_divergence(
    unpaid_rejection_model, rejection_test_def
):
    """Mutating protected fields on negative rejection path produces PROTECTED_FIELD_MUTATED failure."""
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)

    base_ev = agent.run_unpaid_order_rejection(
        project_id=rejection_test_def.project_id,
        test_id=rejection_test_def.test_id,
        run_id="run_base_prot",
        model_id=unpaid_rejection_model.model_id,
        model_version=unpaid_rejection_model.version,
    )
    evidence = ControlledTraceFixtures.create_protected_state_change_trace(base_ev)

    engine = ConformanceEvaluationEngine()
    result = engine.evaluate(
        model=unpaid_rejection_model, test_def=rejection_test_def, evidence=evidence
    )

    assert result.verdict == RuntimeVerdict.FAIL
    assert any(
        v.violation_type == ViolationType.PROTECTED_FIELD_MUTATED
        for v in result.violations
    )


def test_evaluation_premature_termination(refund_model, valid_test_def):
    """Confirmed agent termination before terminal state produces PREMATURE_TERMINATION failure."""
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)

    evidence = agent.run_flawed_demonstration(
        flaw_type="premature_termination",
        project_id=valid_test_def.project_id,
        test_id=valid_test_def.test_id,
        run_id="run_premature_01",
        model_id=refund_model.model_id,
        model_version=refund_model.version,
    )

    engine = ConformanceEvaluationEngine()
    result = engine.evaluate(
        model=refund_model, test_def=valid_test_def, evidence=evidence
    )

    assert result.verdict == RuntimeVerdict.FAIL
    assert any(
        v.violation_type == ViolationType.PREMATURE_TERMINATION
        for v in result.violations
    )


# 5. Inconclusive Verdicts
def test_evaluation_inconclusive_on_missing_observations_and_truncated_trace(
    refund_model, valid_test_def
):
    """Missing mandatory state snapshots or collector truncation yield INCONCLUSIVE."""
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)

    base_ev = agent.run_happy_path(
        project_id=valid_test_def.project_id,
        test_id=valid_test_def.test_id,
        run_id="run_base_inconclusive",
        model_id=refund_model.model_id,
        model_version=refund_model.version,
    )

    # 1. Missing mandatory observations
    missing_obs_ev = ControlledTraceFixtures.create_missing_observations_trace(base_ev)
    engine = ConformanceEvaluationEngine()
    res1 = engine.evaluate(
        model=refund_model, test_def=valid_test_def, evidence=missing_obs_ev
    )
    assert res1.verdict == RuntimeVerdict.INCONCLUSIVE
    assert "Missing mandatory" in res1.reasons[0]

    # 2. Truncated trace without confirmed agent termination
    trunc_ev = ControlledTraceFixtures.create_truncated_trace(base_ev)
    res2 = engine.evaluate(
        model=refund_model, test_def=valid_test_def, evidence=trunc_ev
    )
    assert res2.verdict == RuntimeVerdict.INCONCLUSIVE
    assert "truncated" in res2.reasons[0].lower()


# 6. Model & Test Readiness Verdicts
def test_evaluation_model_not_ready_and_test_not_ready(refund_model, valid_test_def):
    """Unapproved model or infeasible test emit MODEL NOT READY and TEST NOT READY."""
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)

    evidence = agent.run_happy_path(
        project_id=valid_test_def.project_id,
        test_id=valid_test_def.test_id,
        run_id="run_ready_check",
        model_id=refund_model.model_id,
        model_version=refund_model.version,
    )

    engine = ConformanceEvaluationEngine()

    # 1. Model unapproved -> MODEL NOT READY
    res_unapproved = engine.evaluate(
        model=refund_model,
        test_def=valid_test_def,
        evidence=evidence,
        model_is_approved=False,
    )
    assert res_unapproved.verdict == RuntimeVerdict.MODEL_NOT_READY

    # 2. Tampered content hash -> MODEL NOT READY
    res_tampered = engine.evaluate(
        model=refund_model,
        test_def=valid_test_def,
        evidence=evidence,
        model_is_approved=True,
        pinned_content_hash="tampered_hash_12345",
    )
    assert res_tampered.verdict == RuntimeVerdict.MODEL_NOT_READY

    # 3. Test not ready -> TEST NOT READY
    not_ready_test_def = valid_test_def.model_copy(
        update={
            "readiness": TestReadinessStatus.TEST_NOT_READY,
            "readiness_reasons": ["Unresolvable fixture reference"],
        }
    )
    res_test_not_ready = engine.evaluate(
        model=refund_model,
        test_def=not_ready_test_def,
        evidence=evidence,
        model_is_approved=True,
    )
    assert res_test_not_ready.verdict == RuntimeVerdict.TEST_NOT_READY


# 7. Impartiality: Mutation labels do not influence verdicts
def test_impartiality_mutation_labels_do_not_influence_verdict(
    refund_model, valid_test_def
):
    """Changing intended mutation provenance annotations has ZERO effect on verdict."""
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)

    evidence = agent.run_happy_path(
        project_id=valid_test_def.project_id,
        test_id=valid_test_def.test_id,
        run_id="run_impartial",
        model_id=refund_model.model_id,
        model_version=refund_model.version,
    )

    engine = ConformanceEvaluationEngine()

    # Without mutation
    res1 = engine.evaluate(
        model=refund_model, test_def=valid_test_def, evidence=evidence
    )
    assert res1.verdict == RuntimeVerdict.PASS

    # Injecting synthetic mutation metadata onto test definition without changing model or evidence
    from app.components.c2_state_aware_workflow.contracts.test_definition import (
        MutationProvenance,
        MutationType,
    )

    mutated_test_def = valid_test_def.model_copy(
        update={
            "category": TestCategory.MUTATED,
            "mutation_provenance": MutationProvenance(
                mutation_type=MutationType.SKIPPED_STEP,
                description="Synthetic label",
            ),
        }
    )
    res2 = engine.evaluate(
        model=refund_model, test_def=mutated_test_def, evidence=evidence
    )
    assert res2.verdict == RuntimeVerdict.PASS  # Still PASS!


# 8. Generality: custom customer and order IDs
def test_generality_custom_customer_and_order_ids(refund_model):
    """SUT and evaluator work generically with different customer IDs, order IDs, and dates."""
    custom_fixture = {
        "customer_id": 99,
        "customer_email": "vip99@example.com",
        "orders": [
            {
                "order_id": 801,
                "customer_id": 99,
                "status": "PAID",
                "payment_status": "PAID",
                "amount": 200.0,
                "ordered_at": "2026-11-01T10:00:00Z",
            },
            {
                "order_id": 802,
                "customer_id": 99,
                "status": "PAID",
                "payment_status": "PAID",
                "amount": 300.0,
                "ordered_at": "2026-11-05T12:00:00Z",
            },
        ],
    }

    sut = SyntheticRefundSUT(custom_fixture)
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)

    evidence = agent.run_happy_path(
        project_id="p_custom",
        test_id="t_custom",
        run_id="r_custom",
        model_id=refund_model.model_id,
        model_version=refund_model.version,
        customer_id=99,
        target_order_id=802,
    )

    custom_test_def = GeneratedTestDefinition(
        test_id="t_custom",
        project_id="p_custom",
        pinned_model_id=refund_model.model_id,
        pinned_model_version=refund_model.version,
        model_content_hash="",
        category=TestCategory.VALID,
        task="Refund latest paid order 802 for Customer 99",
        fixture_ref="fixture_custom_99",
        expected_outcome=ExpectedOutcomeType.PASS,
        readiness=TestReadinessStatus.TEST_READY,
    )

    engine = ConformanceEvaluationEngine()
    res = engine.evaluate(
        model=refund_model,
        test_def=custom_test_def,
        evidence=evidence,
        fixture_data=custom_fixture,
    )
    assert res.verdict == RuntimeVerdict.PASS
