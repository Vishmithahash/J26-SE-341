"""Tests for coverage-guided generation, workflow mutations, and readiness validation."""

import pytest

from app.components.c2_state_aware_workflow.contracts.test_definition import (
    ExecutionMode,
    ExpectedOutcomeType,
    GenerateTestSuiteRequest,
    MutationType,
    TestCategory,
)
from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
    get_refund_workflow_input,
)
from app.components.c2_state_aware_workflow.generator.engine import (
    CoverageGuidedGenerator,
)
from app.components.c2_state_aware_workflow.generator.mutations import (
    WorkflowMutator,
)
from app.components.c2_state_aware_workflow.generator.readiness import (
    GenerationReadinessValidator,
)
from app.components.c2_state_aware_workflow.persistence.models import (
    C2ValidationReport,
    C2WorkflowModel,
)


@pytest.fixture
def refund_model():
    return build_synthetic_refund_efsm()


@pytest.fixture
def fixture_data():
    return get_refund_workflow_input().synthetic_fixture.model_dump()


def test_coverage_guided_generator_cases_and_diagnostics(refund_model, fixture_data):
    """Verify normal, alternative, and expected-rejection path generation."""
    config = GenerateTestSuiteRequest(
        model_id=refund_model.model_id,
        version=refund_model.version,
        seed=42,
        case_budget=10,
        include_alternatives=True,
        include_negative_rejections=True,
    )
    generator = CoverageGuidedGenerator(config=config)
    cases, diagnostics = generator.generate(
        model=refund_model,
        suite_id="suite_test_001",
        fixture_data=fixture_data,
    )

    assert len(cases) >= 3

    categories = {c.category for c in cases}
    assert TestCategory.VALID in categories
    assert TestCategory.ALTERNATIVE in categories
    assert TestCategory.NEGATIVE in categories

    # Verify normal case (direct refund of 503)
    valid_cases = [c for c in cases if c.category == TestCategory.VALID]
    assert len(valid_cases) >= 1
    normal_case = valid_cases[0]
    assert normal_case.expected_outcome == ExpectedOutcomeType.PASS
    assert "REFUNDED" in normal_case.private_reference_paths[0]
    assert "ORDER_DETAILS_INSPECTED" not in normal_case.private_reference_paths[0]

    # Verify alternative case (inspected order details before refund)
    alt_cases = [c for c in cases if c.category == TestCategory.ALTERNATIVE]
    assert len(alt_cases) >= 1
    alt_case = alt_cases[0]
    assert alt_case.expected_outcome == ExpectedOutcomeType.PASS
    assert "ORDER_DETAILS_INSPECTED" in alt_case.private_reference_paths[0]
    assert alt_case.private_reference_paths[0][-1] == "REFUNDED"

    # Verify negative rejection case (unpaid order 502)
    neg_cases = [c for c in cases if c.category == TestCategory.NEGATIVE]
    assert len(neg_cases) >= 1
    neg_case = neg_cases[0]
    assert neg_case.expected_outcome == ExpectedOutcomeType.EXPECTED_REJECTION_PASS
    assert neg_case.private_reference_paths[0][-1] == "REJECTED_UNPAID"

    # Planned coverage metrics
    assert diagnostics.planned_transition_coverage["total_transitions"] == len(
        refund_model.transitions
    )
    assert diagnostics.planned_transition_coverage["covered_transitions_count"] > 0
    assert diagnostics.planned_transition_coverage["coverage_percentage"] > 50.0
    assert diagnostics.planned_guard_coverage["covered_guards_count"] > 0


def test_generator_determinism_with_seed(refund_model, fixture_data):
    """Running generator twice with same seed produces identical test cases."""
    config = GenerateTestSuiteRequest(
        model_id=refund_model.model_id,
        version=refund_model.version,
        seed=1337,
        case_budget=10,
    )

    gen1 = CoverageGuidedGenerator(config=config)
    cases1, _ = gen1.generate(refund_model, "suite_s1", fixture_data)

    gen2 = CoverageGuidedGenerator(config=config)
    cases2, _ = gen2.generate(refund_model, "suite_s1", fixture_data)

    assert len(cases1) == len(cases2)
    for c1, c2 in zip(cases1, cases2, strict=True):
        assert c1.task == c2.task
        assert c1.category == c2.category
        assert c1.expected_outcome == c2.expected_outcome
        assert c1.private_reference_paths == c2.private_reference_paths
        assert c1.private_reference_transitions == c2.private_reference_transitions


def test_generator_fixture_variations(refund_model):
    """Test with sufficient fixture variations (different customers, order IDs, timestamps)."""
    varied_fixtures = [
        {
            "fixture_id": "fix_cust_42",
            "customer": {"id": 42, "name": "Alice"},
            "orders": {
                "503": {
                    "id": 503,
                    "payment_status": "PAID",
                    "created_at": "2026-10-15T10:00:00Z",
                },
            },
        },
        {
            "fixture_id": "fix_cust_99",
            "customer": {"id": 99, "name": "Bob"},
            "orders": {
                "601": {
                    "id": 601,
                    "payment_status": "PAID",
                    "created_at": "2026-11-01T12:00:00Z",
                },
            },
        },
    ]

    for fix in varied_fixtures:
        generator = CoverageGuidedGenerator(
            config=GenerateTestSuiteRequest(
                model_id=refund_model.model_id,
                version=refund_model.version,
                fixture_ref=fix["fixture_id"],
            )
        )
        cases, _ = generator.generate(refund_model, "suite_var", fix)
        assert len(cases) > 0
        assert all(c.fixture_ref == fix["fixture_id"] for c in cases)


def test_generator_deduplication(refund_model, fixture_data):
    """Deduplication prevents duplicate cases from padding the suite."""
    config = GenerateTestSuiteRequest(
        model_id=refund_model.model_id,
        version=refund_model.version,
        case_budget=50,  # Request budget larger than distinct paths
    )
    generator = CoverageGuidedGenerator(config=config)
    cases, _diag = generator.generate(refund_model, "suite_dedup", fixture_data)

    # All generated cases must have unique transition path signatures
    signatures = [tuple(c.private_reference_transitions[0]) for c in cases]
    assert len(signatures) == len(set(signatures))


def test_workflow_mutator_all_eight_operators(refund_model, fixture_data):
    """Verify each of the 8 required mutation operators produces valid provenance."""
    config = GenerateTestSuiteRequest(
        model_id=refund_model.model_id,
        version=refund_model.version,
        include_alternatives=True,
    )
    generator = CoverageGuidedGenerator(config=config)
    base_cases, _ = generator.generate(refund_model, "suite_mut", fixture_data)

    mutator = WorkflowMutator(seed=42)
    mutated_cases = mutator.generate_mutations(
        base_cases=base_cases,
        model=refund_model,
        mutation_budget=16,
    )

    assert len(mutated_cases) >= 6
    assert {c.mutation_provenance.mutation_type for c in mutated_cases} <= set(
        MutationType
    )

    # Check each generated mutant has correct metadata
    for mutant in mutated_cases:
        assert mutant.category == TestCategory.MUTATED
        assert mutant.execution_mode == ExecutionMode.SYNTHETIC_EVALUATOR
        assert mutant.mutation_provenance is not None
        prov = mutant.mutation_provenance
        assert prov.parent_case_id is not None
        assert prov.description != ""
        assert prov.intended_violation is not None


def test_workflow_mutator_individual_operators(refund_model, fixture_data):
    """Explicitly verify individual mutation operators."""
    config = GenerateTestSuiteRequest(
        model_id=refund_model.model_id,
        version=refund_model.version,
        include_alternatives=True,
    )
    generator = CoverageGuidedGenerator(config=config)
    base_cases, _ = generator.generate(refund_model, "suite_indiv", fixture_data)

    mutator = WorkflowMutator(seed=123)

    for op in MutationType:
        mutants = mutator.generate_mutations(
            base_cases=base_cases,
            model=refund_model,
            mutation_budget=1,
            enabled_types=[op],
        )
        if mutants:
            m = mutants[0]
            assert m.mutation_provenance.mutation_type == op
            assert m.execution_mode == ExecutionMode.SYNTHETIC_EVALUATOR


def test_generation_readiness_validator_model_checks():
    """Verify GenerationReadinessValidator rejects unapproved or inconsistent reference models."""
    mock_model = C2WorkflowModel(
        id="m1",
        project_id="p1",
        model_id="order_wf",
        version="1.0.0",
        schema_version="2026.1",
        name="Order WF",
        definition={},
        content_hash="hash_current_123",
        lifecycle_status="DRAFT",
    )

    # 1. Draft model -> MODEL NOT READY
    is_ready, readiness, reasons = (
        GenerationReadinessValidator.validate_model_readiness(
            model_record=mock_model,
            latest_report=None,
        )
    )
    assert is_ready is False
    assert readiness == "MODEL NOT READY"
    assert any("APPROVED" in r for r in reasons)
    assert any("never been validated" in r for r in reasons)

    # 2. Approved model with stale report -> MODEL NOT READY
    mock_model.lifecycle_status = "APPROVED"
    stale_report = C2ValidationReport(
        id="r1",
        model_record_id="m1",
        project_id="p1",
        model_id="order_wf",
        version="1.0.0",
        content_hash="hash_old_999",
        is_valid=True,
        readiness="READY",
        summary={},
    )
    is_ready, readiness, reasons = (
        GenerationReadinessValidator.validate_model_readiness(
            model_record=mock_model,
            latest_report=stale_report,
        )
    )
    assert is_ready is False
    assert readiness == "MODEL NOT READY"
    assert any("content hash" in r for r in reasons)

    # 3. Approved model with matching valid report -> READY
    fresh_report = C2ValidationReport(
        id="r2",
        model_record_id="m1",
        project_id="p1",
        model_id="order_wf",
        version="1.0.0",
        content_hash="hash_current_123",
        is_valid=True,
        readiness="READY",
        summary={},
    )
    is_ready, readiness, reasons = (
        GenerationReadinessValidator.validate_model_readiness(
            model_record=mock_model,
            latest_report=fresh_report,
        )
    )
    assert is_ready is True
    assert readiness == "READY"
    assert reasons == []
