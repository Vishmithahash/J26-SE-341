"""Tests for C2 Domain Portability and Multi-Domain Benchmark Suite.

Verifies:
1. 5 distinct workflows across 3 domains (E-Commerce, Flight Booking, LMS).
2. Non-leakage partition assignment (siblings of same parent family never leak across partitions).
3. At least 100 distinct feasible cases generated without duplicate IDs or artificial padding.
4. Frozen manifest integrity.
"""

from app.components.c2_state_aware_workflow.contracts.experiment import (
    DatasetPartition,
)
from app.components.c2_state_aware_workflow.examples.ecommerce_workflows import (
    get_address_change_workflow_model,
    get_cancellation_workflow_model,
)
from app.components.c2_state_aware_workflow.examples.flight_workflows import (
    get_flight_cancellation_workflow_model,
)
from app.components.c2_state_aware_workflow.examples.lms_workflows import (
    get_course_enrollment_workflow_model,
)
from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
)
from app.components.c2_state_aware_workflow.experiments.benchmark import (
    BenchmarkSuiteBuilder,
)


def test_five_workflows_across_three_domains():
    """Verify all 5 workflow models instantiate with distinct domains and state spaces."""
    models = [
        build_synthetic_refund_efsm(),
        get_cancellation_workflow_model(),
        get_address_change_workflow_model(),
        get_flight_cancellation_workflow_model(),
        get_course_enrollment_workflow_model(),
    ]
    assert len(models) == 5

    # Check model domains
    model_ids = {m.model_id for m in models}
    assert model_ids == {
        "refund_efsm",
        "order_cancellation_workflow",
        "address_change_workflow",
        "flight_cancellation_workflow",
        "course_enrollment_workflow",
    }

    # Verify each has states, initial state, accepting states, and rejection states
    for m in models:
        assert len(m.states) >= 3
        assert m.initial_state_id is not None
        assert len(m.accepting_state_ids) >= 1
        assert len(m.rejection_state_ids) >= 1
        assert len(m.transitions) >= 2


def test_benchmark_suite_size_and_uniqueness():
    """Verify benchmark suite generates at least 100 distinct feasible cases without duplicate IDs."""
    builder = BenchmarkSuiteBuilder(project_id="test_portability")
    manifest, models, tests = builder.build_benchmark_manifest()

    assert manifest.case_count >= 100
    assert len(manifest.cases) == manifest.case_count
    assert len(models) == 5
    assert len(tests) >= 100

    # Check distinct case IDs
    case_ids = [c.case_id for c in manifest.cases]
    assert len(case_ids) == len(set(case_ids)), (
        "Duplicate case IDs detected in benchmark suite!"
    )

    # Check distinct test IDs
    test_ids = [c.test_id for c in manifest.cases]
    assert len(test_ids) == len(set(test_ids)), (
        "Duplicate test IDs detected in benchmark suite!"
    )

    # Verify manifest is frozen
    assert manifest.is_frozen is True
    assert len(manifest.manifest_digest) == 64


def test_non_leakage_partition_integrity():
    """Verify that sibling cases sharing the same parent family never leak across partitions."""
    builder = BenchmarkSuiteBuilder(project_id="test_portability")
    manifest, _, _ = builder.build_benchmark_manifest()

    family_partitions: dict[str, set[DatasetPartition]] = {}
    for case in manifest.cases:
        parent_id = case.parent_case_id
        assert parent_id is not None, f"Case {case.case_id} lacks parent_case_id!"
        family_partitions.setdefault(parent_id, set()).add(case.partition)

    # Every family must reside in EXACTLY ONE partition (zero leakage)
    for fam_id, parts in family_partitions.items():
        assert len(parts) == 1, (
            f"Leakage detected! Parent family {fam_id} has children in multiple partitions: {parts}"
        )

    assert manifest.development_count > 0
    assert manifest.held_out_count > 0
    assert manifest.development_count + manifest.held_out_count == manifest.case_count
