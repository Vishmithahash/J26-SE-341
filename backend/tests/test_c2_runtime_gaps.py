"""Focused regression tests verifying Day 3 Part A runtime gap fixes.

Verifies:
1. Original evidence retention & reproduction from digests, pinned models, and fixture snapshots.
2. Execution identity separate from evaluation identity (additive attempts, idempotent return, conflicting evidence integrity error).
3. Alternative branches & search limits (one branch fails while another remains valid, UNKNOWN preserves alternatives, later evidence resolves uncertainty, config limits produce INCONCLUSIVE).
4. Deferred effects permitted at later checkpoints (not failed prematurely, distinguished from missing observations).
5. Incomplete evidence with independently proven violations establishes FAIL with localization uncertainty.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    DeferredEffect,
    EFSMModelDefinition,
    FinalOutcome,
    StateDefinition,
    StateType,
    TransitionDefinition,
)
from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    RuntimeVerdict,
    ViolationType,
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
from app.components.c2_state_aware_workflow.evaluator.engine import (
    ConformanceEvaluationEngine,
)
from app.components.c2_state_aware_workflow.evaluator.fixtures import (
    ScriptedDemonstrationAgent,
)
from app.components.c2_state_aware_workflow.evaluator.observer import (
    IndependentStateObserver,
)
from app.components.c2_state_aware_workflow.evaluator.service import (
    WorkflowEvaluationService,
)
from app.components.c2_state_aware_workflow.evaluator.sut import SyntheticRefundSUT
from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
)
from app.components.c2_state_aware_workflow.persistence.models import (
    C2TestCase,
    C2TestSuite,
)
from app.components.c2_state_aware_workflow.persistence.repository import (
    C2ModelRepository,
    ConflictingEvidenceIntegrityError,
)
from app.components.c2_state_aware_workflow.predicates.expressions import (
    ComparisonOperator,
    ComparisonPredicate,
    FieldRef,
    ScopeEnum,
)
from app.database import Base


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def approved_model_and_test(db_session: Session):
    repo = C2ModelRepository(db_session)
    project_id = "proj_gap_test"
    model = build_synthetic_refund_efsm()
    model = model.model_copy(update={"project_id": project_id})

    model_rec = repo.create_draft_model(project_id, model)
    model_rec.lifecycle_status = "APPROVED"
    db_session.commit()

    suite_rec = C2TestSuite(
        project_id=project_id,
        suite_id="suite_gap_test",
        model_record_id=model_rec.id,
        model_id=model.model_id,
        model_version=model.version,
        model_content_hash=model_rec.content_hash,
        generator_version="2026.1",
        config={},
        diagnostics={},
        total_cases=1,
    )
    db_session.add(suite_rec)
    db_session.commit()

    test_def = GeneratedTestDefinition(
        test_id="test_case_refund_503",
        project_id=project_id,
        suite_id=suite_rec.suite_id,
        pinned_model_id=model.model_id,
        pinned_model_version=model.version,
        model_content_hash=model_rec.content_hash,
        category=TestCategory.VALID,
        task="Refund my latest paid order (Customer 42)",
        fixture_ref="fixture_refund_default",
        expected_outcome=ExpectedOutcomeType.PASS,
        readiness=TestReadinessStatus.TEST_READY,
    )

    case_rec = C2TestCase(
        suite_record_id=suite_rec.id,
        project_id=project_id,
        suite_id=suite_rec.suite_id,
        test_id=test_def.test_id,
        category="valid",
        execution_mode="live_agent",
        task=test_def.task,
        fixture_ref=test_def.fixture_ref,
        definition=test_def.model_dump(mode="json"),
    )
    db_session.add(case_rec)
    db_session.commit()

    return project_id, suite_rec.suite_id, test_def.test_id, model


# ---------------------------------------------------------------------------
# 1. Execution Identity vs Evaluation Identity
# ---------------------------------------------------------------------------


def test_execution_identity_separate_from_evaluation_identity(
    db_session: Session, approved_model_and_test
):
    """Verify additive evaluation attempts and consistent returns on identical requests."""
    project_id, suite_id, test_id, model = approved_model_and_test
    service = WorkflowEvaluationService(db_session)
    repo = C2ModelRepository(db_session)

    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)
    run_id = "run_identity_001"

    evidence = agent.run_happy_path(
        project_id=project_id,
        test_id=test_id,
        run_id=run_id,
        model_id=model.model_id,
        model_version=model.version,
    )

    # First evaluation: creates attempt 1
    eval_1 = service.evaluate_test_run(
        project_id=project_id,
        suite_id=suite_id,
        test_id=test_id,
        evidence=evidence,
        evaluator_version="c2_evaluator_v1",
        evaluator_config={"max_configurations": 100},
    )
    assert eval_1.verdict == RuntimeVerdict.PASS
    assert eval_1.evaluation_id is not None

    # Verify retained execution evidence exists
    retained = repo.get_execution_evidence(project_id, run_id)
    assert retained is not None
    assert retained.run_id == run_id
    assert len(retained.evidence_digest) == 64
    assert len(retained.evidence_payload["ordered_events"]) == 4

    # Identical request: returns existing evaluation result consistently
    eval_identical = service.evaluate_test_run(
        project_id=project_id,
        suite_id=suite_id,
        test_id=test_id,
        evidence=evidence,
        evaluator_version="c2_evaluator_v1",
        evaluator_config={"max_configurations": 100},
    )
    assert eval_identical.evaluation_id == eval_1.evaluation_id

    # Additive evaluation: evaluate same recorded execution with different config / version
    eval_2 = service.evaluate_test_run(
        project_id=project_id,
        suite_id=suite_id,
        test_id=test_id,
        evidence=evidence,
        evaluator_version="c2_evaluator_v2_experimental",
        evaluator_config={"max_configurations": 50},
    )
    assert eval_2.evaluation_id != eval_1.evaluation_id
    assert eval_2.evaluator_version == "c2_evaluator_v2_experimental"

    # Both evaluations coexist in database linked to the same run_id
    eval_records = repo.list_evaluation_results(
        project_id, suite_id=suite_id, test_id=test_id
    )
    assert len(eval_records) == 2
    attempts = [e.evaluation_attempt for e in eval_records]
    assert 1 in attempts
    assert 2 in attempts


def test_conflicting_evidence_raises_integrity_error(
    db_session: Session, approved_model_and_test
):
    """Conflicting evidence under the same claimed execution identity must raise ConflictingEvidenceIntegrityError."""
    project_id, suite_id, test_id, model = approved_model_and_test
    service = WorkflowEvaluationService(db_session)

    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)
    shared_run_id = "run_conflicting_evidence_test"

    # 1. Run legitimate happy path
    ev1 = agent.run_happy_path(
        project_id=project_id,
        test_id=test_id,
        run_id=shared_run_id,
        model_id=model.model_id,
        model_version=model.version,
    )
    service.evaluate_test_run(
        project_id=project_id,
        suite_id=suite_id,
        test_id=test_id,
        evidence=ev1,
    )

    # 2. Fabricate conflicting evidence under the exact same run_id
    ev2 = agent.run_inspection_alternative(
        project_id=project_id,
        test_id=test_id,
        run_id=shared_run_id,
        model_id=model.model_id,
        model_version=model.version,
    )

    with pytest.raises(ConflictingEvidenceIntegrityError) as exc_info:
        service.evaluate_test_run(
            project_id=project_id,
            suite_id=suite_id,
            test_id=test_id,
            evidence=ev2,
        )

    assert "Conflicting evidence detected under claimed run_id" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 2. Reproduction from Retained Evidence
# ---------------------------------------------------------------------------


def test_reproducible_re_evaluation(db_session: Session, approved_model_and_test):
    """Verify an evaluation can be reproduced from retained evidence, pinned model, and test definition."""
    project_id, suite_id, test_id, model = approved_model_and_test
    service = WorkflowEvaluationService(db_session)

    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)
    run_id = "run_reproduce_001"

    ev = agent.run_happy_path(
        project_id=project_id,
        test_id=test_id,
        run_id=run_id,
        model_id=model.model_id,
        model_version=model.version,
    )
    initial_eval = service.evaluate_test_run(
        project_id=project_id,
        suite_id=suite_id,
        test_id=test_id,
        evidence=ev,
    )

    # Re-evaluate execution from stored identity
    re_eval = service.re_evaluate_execution(
        project_id=project_id,
        evaluation_id=initial_eval.evaluation_id,
        evaluator_version="c2_evaluator_audit_v2",
        evaluator_config={"audit_mode": True},
    )

    assert re_eval.verdict == initial_eval.verdict
    assert re_eval.run_id == run_id
    assert re_eval.evaluator_version == "c2_evaluator_audit_v2"


# ---------------------------------------------------------------------------
# 3. Alternative Branches and Configuration Limits
# ---------------------------------------------------------------------------


def test_alternative_branch_survives_when_another_branch_fails():
    """Verify non-deterministic alignment considers all candidate branches before declaring divergence."""
    # Build a model with two branches from state S0 on event 'search':
    # Branch A: guard requires category == 'books'
    # Branch B: guard requires category == 'electronics'
    states = [
        StateDefinition(id="S0", name="Start", type=StateType.INITIAL),
        StateDefinition(id="S_BOOKS", name="Books", type=StateType.INTERMEDIATE),
        StateDefinition(id="S_ELEC", name="Electronics", type=StateType.INTERMEDIATE),
        StateDefinition(id="S_DONE", name="Done", type=StateType.TERMINAL_ACCEPTING),
    ]
    guard_books = ComparisonPredicate(
        left=FieldRef(scope=ScopeEnum.EVENT, path="arguments.category"),
        op=ComparisonOperator.EQUALS,
        right="books",
    )
    guard_elec = ComparisonPredicate(
        left=FieldRef(scope=ScopeEnum.EVENT, path="arguments.category"),
        op=ComparisonOperator.EQUALS,
        right="electronics",
    )
    transitions = [
        TransitionDefinition(
            id="T_BOOKS",
            source_state="S0",
            target_state="S_BOOKS",
            trigger_event="search",
            guard=guard_books,
        ),
        TransitionDefinition(
            id="T_ELEC",
            source_state="S0",
            target_state="S_ELEC",
            trigger_event="search",
            guard=guard_elec,
        ),
        TransitionDefinition(
            id="T_CHECKOUT",
            source_state="S_ELEC",
            target_state="S_DONE",
            trigger_event="checkout",
        ),
    ]
    model = EFSMModelDefinition(
        project_id="p1",
        model_id="branch_model",
        version="1.0.0",
        name="Branching EFSM",
        states=states,
        initial_state_id="S0",
        accepting_state_ids=["S_DONE"],
        transitions=transitions,
        final_outcomes=[
            FinalOutcome(
                outcome_id="O1",
                type="ACCEPTING",
                terminal_state_id="S_DONE",
                description="Done",
            )
        ],
    )

    # Event trace with category == 'electronics': Branch A fails, Branch B survives!
    events = [
        RuntimeEvent(
            event_index=0,
            event_id="evt_0",
            tool_name="search",
            arguments={"category": "electronics"},
        ),
        RuntimeEvent(
            event_index=1,
            event_id="evt_1",
            tool_name="checkout",
            arguments={},
        ),
    ]
    observations = [
        StateObservation(event_index=0, before_state={}, after_state={}),
        StateObservation(event_index=1, before_state={}, after_state={}),
    ]
    evidence = RuntimeEvidenceContract(
        project_id="p1",
        run_id="run_b1",
        test_id="t1",
        model_id=model.model_id,
        model_version=model.version,
        ordered_events=events,
        state_observations=observations,
        completeness=EvidenceCompleteness(
            is_complete=True, confirmed_agent_termination=True
        ),
    )

    test_def = GeneratedTestDefinition(
        test_id="t1",
        project_id="p1",
        pinned_model_id=model.model_id,
        pinned_model_version=model.version,
        model_content_hash="",
        category=TestCategory.VALID,
        task="Search and checkout electronics",
        fixture_ref="fix",
        expected_outcome=ExpectedOutcomeType.PASS,
        readiness=TestReadinessStatus.TEST_READY,
    )

    engine = ConformanceEvaluationEngine()
    result = engine.evaluate(model=model, test_def=test_def, evidence=evidence)
    assert result.verdict == RuntimeVerdict.PASS
    assert "S_ELEC" in result.observed_states


def test_configuration_limit_produces_inconclusive_not_fail():
    """Verify that exceeding max_configurations returns INCONCLUSIVE rather than false FAIL."""
    refund_model = build_synthetic_refund_efsm()
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)

    evidence = agent.run_happy_path(
        project_id="p_limit",
        test_id="t_limit",
        run_id="run_limit",
        model_id=refund_model.model_id,
        model_version=refund_model.version,
    )
    test_def = GeneratedTestDefinition(
        test_id="t_limit",
        project_id="p_limit",
        pinned_model_id=refund_model.model_id,
        pinned_model_version=refund_model.version,
        model_content_hash="",
        category=TestCategory.VALID,
        task="Refund latest paid order",
        fixture_ref="fix",
        expected_outcome=ExpectedOutcomeType.PASS,
        readiness=TestReadinessStatus.TEST_READY,
    )

    # Set extreme max_configurations limit = 0 to trigger configuration exhaustion limit immediately
    engine = ConformanceEvaluationEngine(max_configurations=0)
    result = engine.evaluate(model=refund_model, test_def=test_def, evidence=evidence)

    assert result.verdict == RuntimeVerdict.INCONCLUSIVE
    assert any("limit exceeded" in r.lower() for r in result.reasons)


# ---------------------------------------------------------------------------
# 4. Deferred Effects at Declared Checkpoints
# ---------------------------------------------------------------------------


def test_deferred_effects_verified_at_checkpoint_not_failed_prematurely():
    """Deferred effect must not fail prematurely on intermediate steps, and succeeds at designated checkpoint."""
    states = [
        StateDefinition(id="S0", name="Start", type=StateType.INITIAL),
        StateDefinition(id="S_PLACED", name="Placed", type=StateType.INTERMEDIATE),
        StateDefinition(
            id="S_CONFIRMED", name="Confirmed", type=StateType.TERMINAL_ACCEPTING
        ),
    ]

    # Deferred effect: warehouse_reserved == True must hold at checkpoint S_CONFIRMED
    deferred_warehouse_check = DeferredEffect(
        id="deff_warehouse",
        predicate=ComparisonPredicate(
            left=FieldRef(scope=ScopeEnum.AFTER, path="warehouse_reserved"),
            op=ComparisonOperator.EQUALS,
            right=True,
        ),
        checkpoint_state_id="S_CONFIRMED",
        description="Warehouse must be reserved at confirmation checkpoint",
    )

    transitions = [
        TransitionDefinition(
            id="T_PLACE",
            source_state="S0",
            target_state="S_PLACED",
            trigger_event="place_order",
            deferred_effects=[deferred_warehouse_check],
        ),
        TransitionDefinition(
            id="T_CONFIRM",
            source_state="S_PLACED",
            target_state="S_CONFIRMED",
            trigger_event="confirm_order",
        ),
    ]

    model = EFSMModelDefinition(
        project_id="p_deff",
        model_id="model_deff",
        version="1.0.0",
        name="Deferred EFSM",
        states=states,
        initial_state_id="S0",
        accepting_state_ids=["S_CONFIRMED"],
        transitions=transitions,
        final_outcomes=[
            FinalOutcome(
                outcome_id="O1",
                type="ACCEPTING",
                terminal_state_id="S_CONFIRMED",
                description="Done",
            )
        ],
    )

    # Step 0: place_order -> warehouse_reserved is NOT yet set in state
    # Intermediate step must NOT fail prematurely!
    obs0 = StateObservation(
        event_index=0,
        before_state={"warehouse_reserved": False},
        after_state={"warehouse_reserved": False},
    )
    # Step 1: confirm_order -> warehouse_reserved is now True at checkpoint S_CONFIRMED
    obs1 = StateObservation(
        event_index=1,
        before_state={"warehouse_reserved": False},
        after_state={"warehouse_reserved": True},
    )

    evidence = RuntimeEvidenceContract(
        project_id="p_deff",
        run_id="run_deff_pass",
        test_id="t_deff",
        model_id=model.model_id,
        model_version=model.version,
        ordered_events=[
            RuntimeEvent(event_index=0, event_id="e0", tool_name="place_order"),
            RuntimeEvent(event_index=1, event_id="e1", tool_name="confirm_order"),
        ],
        state_observations=[obs0, obs1],
        completeness=EvidenceCompleteness(
            is_complete=True, confirmed_agent_termination=True
        ),
    )

    test_def = GeneratedTestDefinition(
        test_id="t_deff",
        project_id="p_deff",
        pinned_model_id=model.model_id,
        pinned_model_version=model.version,
        model_content_hash="",
        category=TestCategory.VALID,
        task="Place and confirm order",
        fixture_ref="fix",
        expected_outcome=ExpectedOutcomeType.PASS,
        readiness=TestReadinessStatus.TEST_READY,
    )

    engine = ConformanceEvaluationEngine()
    result = engine.evaluate(model=model, test_def=test_def, evidence=evidence)
    assert result.verdict == RuntimeVerdict.PASS


def test_deferred_effects_proven_missing_at_checkpoint_fails():
    """At checkpoint, an effect that is evaluated to FALSE establishes FAIL for MISSING_EFFECT."""
    states = [
        StateDefinition(id="S0", name="Start", type=StateType.INITIAL),
        StateDefinition(id="S_PLACED", name="Placed", type=StateType.INTERMEDIATE),
        StateDefinition(
            id="S_CONFIRMED", name="Confirmed", type=StateType.TERMINAL_ACCEPTING
        ),
    ]

    deferred_warehouse_check = DeferredEffect(
        id="deff_warehouse",
        predicate=ComparisonPredicate(
            left=FieldRef(scope=ScopeEnum.AFTER, path="warehouse_reserved"),
            op=ComparisonOperator.EQUALS,
            right=True,
        ),
        checkpoint_state_id="S_CONFIRMED",
    )

    transitions = [
        TransitionDefinition(
            id="T_PLACE",
            source_state="S0",
            target_state="S_PLACED",
            trigger_event="place_order",
            deferred_effects=[deferred_warehouse_check],
        ),
        TransitionDefinition(
            id="T_CONFIRM",
            source_state="S_PLACED",
            target_state="S_CONFIRMED",
            trigger_event="confirm_order",
        ),
    ]

    model = EFSMModelDefinition(
        project_id="p_deff",
        model_id="model_deff",
        version="1.0.0",
        name="Deferred EFSM",
        states=states,
        initial_state_id="S0",
        accepting_state_ids=["S_CONFIRMED"],
        transitions=transitions,
        final_outcomes=[
            FinalOutcome(
                outcome_id="O1",
                type="ACCEPTING",
                terminal_state_id="S_CONFIRMED",
                description="Done",
            )
        ],
    )

    # Step 0: place_order
    obs0 = StateObservation(
        event_index=0,
        before_state={"warehouse_reserved": False},
        after_state={"warehouse_reserved": False},
    )
    # Step 1: confirm_order -> warehouse_reserved is still FALSE at checkpoint S_CONFIRMED!
    obs1 = StateObservation(
        event_index=1,
        before_state={"warehouse_reserved": False},
        after_state={"warehouse_reserved": False},
    )

    evidence = RuntimeEvidenceContract(
        project_id="p_deff",
        run_id="run_deff_fail",
        test_id="t_deff",
        model_id=model.model_id,
        model_version=model.version,
        ordered_events=[
            RuntimeEvent(event_index=0, event_id="e0", tool_name="place_order"),
            RuntimeEvent(event_index=1, event_id="e1", tool_name="confirm_order"),
        ],
        state_observations=[obs0, obs1],
        completeness=EvidenceCompleteness(
            is_complete=True, confirmed_agent_termination=True
        ),
    )

    test_def = GeneratedTestDefinition(
        test_id="t_deff",
        project_id="p_deff",
        pinned_model_id=model.model_id,
        pinned_model_version=model.version,
        model_content_hash="",
        category=TestCategory.VALID,
        task="Place and confirm order",
        fixture_ref="fix",
        expected_outcome=ExpectedOutcomeType.PASS,
        readiness=TestReadinessStatus.TEST_READY,
    )

    engine = ConformanceEvaluationEngine()
    result = engine.evaluate(model=model, test_def=test_def, evidence=evidence)
    assert result.verdict == RuntimeVerdict.FAIL


# ---------------------------------------------------------------------------
# 5. Incomplete Evidence with Independently Proven Violations
# ---------------------------------------------------------------------------


def test_proven_violation_in_truncated_trace_establishes_fail_with_uncertainty():
    """An independently proven violation in an incomplete or truncated trace establishes FAIL, explaining uncertainty."""
    refund_model = build_synthetic_refund_efsm()
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)

    # Agent performs wrong entity at step 1: calling select_order with 501 instead of 503
    flawed_evidence = agent.run_flawed_demonstration(
        flaw_type="wrong_entity",
        project_id="p_inc",
        test_id="t_inc",
        run_id="run_inc_viol",
        model_id=refund_model.model_id,
        model_version=refund_model.version,
    )

    # Mark trace as truncated with audit anomalies
    truncated_evidence = flawed_evidence.model_copy(
        update={
            "completeness": EvidenceCompleteness(
                is_truncated=True,
                confirmed_agent_termination=False,
                anomalies=["Trace buffer prematurely ended"],
            )
        }
    )

    test_def = GeneratedTestDefinition(
        test_id="t_inc",
        project_id="p_inc",
        pinned_model_id=refund_model.model_id,
        pinned_model_version=refund_model.version,
        model_content_hash="",
        category=TestCategory.VALID,
        task="Refund my latest paid order",
        fixture_ref="fix",
        expected_outcome=ExpectedOutcomeType.PASS,
        readiness=TestReadinessStatus.TEST_READY,
    )

    engine = ConformanceEvaluationEngine()
    result = engine.evaluate(
        model=refund_model, test_def=test_def, evidence=truncated_evidence
    )

    # Must NOT produce blanket INCONCLUSIVE because wrong entity violation was independently proven!
    assert result.verdict == RuntimeVerdict.FAIL
    assert any(
        v.violation_type == ViolationType.ENTITY_MISMATCH for v in result.violations
    )
    # Must record uncertainty regarding earliest point due to truncation
    assert result.divergence_localisation_uncertainty is not None
    assert (
        "incomplete" in result.divergence_localisation_uncertainty.lower()
        or "gaps" in result.divergence_localisation_uncertainty.lower()
    )


def test_incomplete_evidence_without_proven_violations_produces_inconclusive():
    """Incomplete evidence where no violations were proven produces INCONCLUSIVE, not PASS or false FAIL."""
    refund_model = build_synthetic_refund_efsm()
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)

    # Happy path trace but truncated after 2 steps (before reaching accepting state)
    happy_ev = agent.run_happy_path(
        project_id="p_inc",
        test_id="t_inc_clean",
        run_id="run_inc_clean",
        model_id=refund_model.model_id,
        model_version=refund_model.version,
    )

    # Truncate to first 2 events without termination confirmation
    truncated_ev = happy_ev.model_copy(
        update={
            "ordered_events": happy_ev.ordered_events[:2],
            "completeness": EvidenceCompleteness(
                is_truncated=True,
                confirmed_agent_termination=False,
            ),
        }
    )

    test_def = GeneratedTestDefinition(
        test_id="t_inc_clean",
        project_id="p_inc",
        pinned_model_id=refund_model.model_id,
        pinned_model_version=refund_model.version,
        model_content_hash="",
        category=TestCategory.VALID,
        task="Refund my latest paid order",
        fixture_ref="fix",
        expected_outcome=ExpectedOutcomeType.PASS,
        readiness=TestReadinessStatus.TEST_READY,
    )

    engine = ConformanceEvaluationEngine()
    result = engine.evaluate(
        model=refund_model, test_def=test_def, evidence=truncated_ev
    )

    assert result.verdict == RuntimeVerdict.INCONCLUSIVE
    assert any(
        "incomplete" in r.lower() or "truncated" in r.lower() for r in result.reasons
    )
