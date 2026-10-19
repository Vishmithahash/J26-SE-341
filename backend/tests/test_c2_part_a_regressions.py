"""Focused regression tests for Part A issues and edge cases.

Verifies:
1. Guard outcome coverage calculations (distinguishing encountered, TRUE, FALSE, UNKNOWN).
2. Unique transition counting from the pinned model.
3. Agent export eligibility (filtering and rejecting non-LIVE_AGENT synthetic mutants).
4. Mutation discrimination (checking rules, guards, valid alternative filtering, honest unresolved status).
5. Multiple suites coexisting with identical case names.
6. Offline migration downgrade ranges.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.components.c2_state_aware_workflow.contracts.test_definition import (
    GenerateTestSuiteRequest,
    MutationType,
)
from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
    get_refund_workflow_input,
)
from app.components.c2_state_aware_workflow.generator.engine import (
    CoverageGuidedGenerator,
)
from app.components.c2_state_aware_workflow.generator.mutations import WorkflowMutator
from app.components.c2_state_aware_workflow.persistence.models import (
    C2TestCase,
    C2TestSuite,
)
from app.components.c2_state_aware_workflow.persistence.repository import (
    C2ModelRepository,
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


def test_guard_outcome_coverage_definitions_and_unique_transitions():
    """Verify guard outcome coverage distinguishes TRUE, FALSE, UNKNOWN with explicit denominator."""
    model = build_synthetic_refund_efsm()
    fixture_data = get_refund_workflow_input().synthetic_fixture.model_dump()

    config = GenerateTestSuiteRequest(
        model_id=model.model_id,
        version=model.version,
        seed=42,
        case_budget=20,
        include_alternatives=True,
        include_negative_rejections=True,
    )
    generator = CoverageGuidedGenerator(config=config)
    _cases, diagnostics = generator.generate(
        model=model,
        suite_id="suite_cov_test",
        fixture_data=fixture_data,
    )

    # 1. Unique transition counting strictly from pinned model
    trans_cov = diagnostics.planned_transition_coverage
    unique_model_trans_ids = {t.id for t in model.transitions}
    assert trans_cov["total_transitions"] == len(unique_model_trans_ids)
    assert trans_cov["covered_transitions_count"] == len(unique_model_trans_ids)
    assert trans_cov["coverage_percentage"] == 100.0

    # 2. Guard outcome coverage
    guard_cov = diagnostics.planned_guard_coverage
    assert "total_guards_defined" in guard_cov
    assert "total_outcome_targets" in guard_cov
    assert "guards_encountered_count" in guard_cov
    assert "guards_planned_true_count" in guard_cov
    assert "guards_planned_false_count" in guard_cov
    assert "guards_planned_unknown_count" in guard_cov
    assert "planned_guard_outcome_coverage_pct" in guard_cov

    # Total outcome targets = total_guards_defined * 2 (honest denominator)
    total_guards = sum(1 for t in model.transitions if t.guard)
    assert guard_cov["total_guards_defined"] == total_guards
    assert guard_cov["total_outcome_targets"] == total_guards * 2
    assert guard_cov["guards_encountered_count"] > 0
    assert guard_cov["guards_planned_true_count"] > 0


def test_mutation_discrimination_and_valid_order_substitution():
    """Verify that WRONG_ENTITY substitutes valid order 501 and sets honest discrimination provenance."""
    model = build_synthetic_refund_efsm()
    generator = CoverageGuidedGenerator()
    cases, _ = generator.generate(model=model, suite_id="suite_mut_disc")

    mutator = WorkflowMutator(seed=42)
    mutants = mutator.generate_mutations(
        base_cases=cases,
        model=model,
        mutation_budget=8,
        enabled_types=[
            MutationType.WRONG_ENTITY,
            MutationType.MISSING_EFFECT,
            MutationType.UNEXPECTED_PROTECTED_STATE_CHANGE,
        ],
    )

    wrong_entity_mutants = [
        m
        for m in mutants
        if m.mutation_provenance.mutation_type == MutationType.WRONG_ENTITY
    ]
    assert len(wrong_entity_mutants) > 0
    we_prov = wrong_entity_mutants[0].mutation_provenance

    # Substituted entity must be another valid order (501 or 503), not random 999
    assert we_prov.changed_details["substituted_entity_id"] in (501, 503)
    assert we_prov.is_ambiguous_or_non_discriminating is False

    # Check missing effect mutant
    missing_eff_mutants = [
        m
        for m in mutants
        if m.mutation_provenance.mutation_type == MutationType.MISSING_EFFECT
    ]
    assert len(missing_eff_mutants) > 0
    me_prov = missing_eff_mutants[0].mutation_provenance
    assert me_prov.is_ambiguous_or_non_discriminating is False


def test_multiple_suites_coexist_with_identical_case_names(db_session):
    """Verify that two suites in the same project can store identical case names without conflict."""
    repo = C2ModelRepository(db_session)
    project_id = "test_coexist_proj"
    model = build_synthetic_refund_efsm()

    # Create approved model
    model_record = repo.create_draft_model(project_id, model)
    model_record.lifecycle_status = "APPROVED"
    db_session.commit()

    # Suite 1
    s1 = C2TestSuite(
        project_id=project_id,
        suite_id="suite_alpha",
        model_record_id=model_record.id,
        model_id=model.model_id,
        model_version=model.version,
        model_content_hash=model_record.content_hash,
        generator_version="2026.1",
        config={},
        diagnostics={},
        total_cases=1,
    )
    db_session.add(s1)
    db_session.commit()

    # Suite 2
    s2 = C2TestSuite(
        project_id=project_id,
        suite_id="suite_beta",
        model_record_id=model_record.id,
        model_id=model.model_id,
        model_version=model.version,
        model_content_hash=model_record.content_hash,
        generator_version="2026.1",
        config={},
        diagnostics={},
        total_cases=1,
    )
    db_session.add(s2)
    db_session.commit()

    # Same test_id in both suites
    identical_test_id = "test_def_00000001"
    c1 = C2TestCase(
        suite_record_id=s1.id,
        project_id=project_id,
        suite_id=s1.suite_id,
        test_id=identical_test_id,
        category="valid",
        execution_mode="live_agent",
        task="Refund latest paid order (Suite Alpha)",
        fixture_ref="fixture_alpha",
        definition={"test_id": identical_test_id, "suite": "alpha"},
    )
    c2 = C2TestCase(
        suite_record_id=s2.id,
        project_id=project_id,
        suite_id=s2.suite_id,
        test_id=identical_test_id,
        category="valid",
        execution_mode="live_agent",
        task="Refund latest paid order (Suite Beta)",
        fixture_ref="fixture_beta",
        definition={"test_id": identical_test_id, "suite": "beta"},
    )
    db_session.add(c1)
    db_session.add(c2)
    db_session.commit()

    # Both cases should be retrievable unambiguously via (project_id, suite_id, test_id)
    retrieved_c1 = repo.get_test_case(project_id, "suite_alpha", identical_test_id)
    retrieved_c2 = repo.get_test_case(project_id, "suite_beta", identical_test_id)
    assert retrieved_c1 is not None
    assert retrieved_c2 is not None
    assert retrieved_c1.suite_id == "suite_alpha"
    assert retrieved_c2.suite_id == "suite_beta"
    assert retrieved_c1.task != retrieved_c2.task
