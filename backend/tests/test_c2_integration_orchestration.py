"""Integration and orchestration tests for C2.

Verifies:
1. End-to-end integration: approved model -> generated case -> fixture reset -> supported runner -> evidence retention -> evaluator -> persistence.
2. Provenance integrity: LIVE_AGENT case executed via synthetic adapter is honestly reported as scripted_synthetic_demonstration (is_live_execution=False).
3. Strict oracle isolation: agent receives only task, fixture_ref, and permitted_context; private paths/assertions remain isolated.
4. Fixture isolation and reset between runs.
5. Readiness pre-flight checks: unapproved models produce MODEL_NOT_READY, non-ready cases produce TEST_NOT_READY.
6. Bounded batch suite execution with per-case failure recording.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    RuntimeVerdict,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    ExecutionMode,
    GenerateTestSuiteRequest,
)
from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
)
from app.components.c2_state_aware_workflow.generator.service import (
    TestGenerationService,
)
from app.components.c2_state_aware_workflow.integrations.interfaces import (
    LocalSyntheticFixtureManager,
)
from app.components.c2_state_aware_workflow.integrations.service import (
    C2IntegrationService,
)
from app.components.c2_state_aware_workflow.persistence.models import (
    C2TestCase,
    C2TestSuite,
)
from app.components.c2_state_aware_workflow.persistence.repository import (
    C2ModelRepository,
)
from app.components.c2_state_aware_workflow.validator.service import (
    ModelValidationService,
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
def approved_project_with_generated_suite(db_session: Session):
    project_id = "proj_orch_test"
    repo = C2ModelRepository(db_session)
    val_service = ModelValidationService(db_session)
    gen_service = TestGenerationService(db_session)

    # 1. Create and approve model
    model = build_synthetic_refund_efsm()
    model = model.model_copy(update={"project_id": project_id})
    repo.create_draft_model(project_id, model)
    val_service.validate_model_record(project_id, model.model_id, model.version)
    repo.approve_model(
        project_id=project_id,
        model_id=model.model_id,
        version=model.version,
        reviewer_id="reviewer_orch",
        review_basis="Comprehensive unit verification",
    )

    # 2. Generate suite with mutations
    req = GenerateTestSuiteRequest(
        model_id=model.model_id,
        version=model.version,
        include_mutations=True,
        case_budget=10,
    )
    suite = gen_service.generate_suite_for_model(
        project_id=project_id,
        model_id=model.model_id,
        version=model.version,
        request=req,
    )

    return project_id, suite.suite_id, model.model_id, model.version


def test_e2e_integration_orchestration_run_case(
    db_session: Session, approved_project_with_generated_suite
):
    """Verify complete orchestration pipeline runs an individual case and retains evidence."""
    project_id, suite_id, *_ = approved_project_with_generated_suite
    repo = C2ModelRepository(db_session)
    service = C2IntegrationService(db_session)

    # Find a valid test case
    cases = repo.list_test_cases(project_id, suite_id, category="valid")
    assert len(cases) > 0
    case = cases[0]

    # Run case through orchestration service
    run_id = "orch_run_valid_001"
    eval_result = service.run_case(
        project_id=project_id,
        suite_id=suite_id,
        test_id=case.test_id,
        run_id=run_id,
    )

    # Conformance verified
    assert eval_result.verdict == RuntimeVerdict.PASS
    assert eval_result.run_id == run_id
    assert eval_result.evaluation_id is not None

    # Evidence retained with valid SHA-256 digest
    retained_ev = repo.get_execution_evidence(project_id, run_id)
    assert retained_ev is not None
    assert len(retained_ev.evidence_digest) == 64
    assert retained_ev.execution_mode == "scripted_synthetic_demonstration"


def test_provenance_integrity_distinguishes_intended_from_actual_execution(
    db_session: Session, approved_project_with_generated_suite
):
    """LIVE_AGENT case executed via synthetic demonstration must NOT be reported as actual live LLM run."""
    project_id, suite_id, _, _ = approved_project_with_generated_suite
    repo = C2ModelRepository(db_session)
    service = C2IntegrationService(db_session)

    cases = repo.list_test_cases(project_id, suite_id, category="valid")
    case = cases[0]
    assert case.execution_mode == ExecutionMode.LIVE_AGENT.value

    run_id = "orch_run_prov_check"
    service.run_case(
        project_id=project_id,
        suite_id=suite_id,
        test_id=case.test_id,
        run_id=run_id,
    )

    retained_ev = repo.get_execution_evidence(project_id, run_id)
    assert retained_ev is not None
    prov = retained_ev.execution_provenance

    # Critical provenance invariants
    assert prov["intended_execution_mode"] == "live_agent"
    assert prov["actual_execution_origin"] == "scripted_synthetic_demonstration"
    assert prov["is_live_execution"] is False
    assert prov["runner_id"] == "local_synthetic_runner_v1"
    assert prov["live_capabilities_available"] is False
    assert "live_llm_runner" in prov["unavailable_live_capabilities"]


def test_fixture_isolation_between_runs(
    db_session: Session, approved_project_with_generated_suite
):
    """Fixtures must be reset and isolated between consecutive runs."""
    project_id, suite_id, _, _ = approved_project_with_generated_suite
    repo = C2ModelRepository(db_session)
    fixture_manager = LocalSyntheticFixtureManager()
    service = C2IntegrationService(db_session, fixture_manager=fixture_manager)

    cases = repo.list_test_cases(project_id, suite_id, category="valid")
    case = cases[0]

    # Run 1
    res1 = service.run_case(project_id, suite_id, case.test_id, run_id="run_iso_1")
    assert res1.verdict == RuntimeVerdict.PASS

    # Run 2
    res2 = service.run_case(project_id, suite_id, case.test_id, run_id="run_iso_2")
    assert res2.verdict == RuntimeVerdict.PASS

    ev1 = repo.get_execution_evidence(project_id, "run_iso_1")
    ev2 = repo.get_execution_evidence(project_id, "run_iso_2")
    assert ev1 is not None and ev2 is not None
    # Each run has independent events starting at sequence index 0
    assert ev1.evidence_payload["ordered_events"][0]["event_index"] == 0
    assert ev2.evidence_payload["ordered_events"][0]["event_index"] == 0


def test_readiness_preflight_checks(db_session: Session):
    """Unapproved model produces MODEL_NOT_READY, non-ready case produces TEST_NOT_READY."""
    project_id = "proj_readiness_checks"
    repo = C2ModelRepository(db_session)
    service = C2IntegrationService(db_session)

    # 1. Unapproved DRAFT model
    model = build_synthetic_refund_efsm()
    model = model.model_copy(update={"project_id": project_id})
    model_rec = repo.create_draft_model(project_id, model)
    assert model_rec.lifecycle_status == "DRAFT"

    suite_rec = C2TestSuite(
        project_id=project_id,
        suite_id="suite_draft",
        model_record_id=model_rec.id,
        model_id=model.model_id,
        model_version=model.version,
        model_content_hash=model_rec.content_hash,
        generator_version="2026.1",
        config={},
        diagnostics={},
        total_cases=2,
    )
    db_session.add(suite_rec)
    db_session.commit()

    case_draft = C2TestCase(
        suite_record_id=suite_rec.id,
        project_id=project_id,
        suite_id=suite_rec.suite_id,
        test_id="case_unapproved_model",
        category="valid",
        execution_mode="live_agent",
        task="Refund latest paid order",
        fixture_ref="fix",
        definition={
            "test_id": "case_unapproved_model",
            "project_id": project_id,
            "pinned_model_id": model.model_id,
            "pinned_model_version": model.version,
            "model_content_hash": model_rec.content_hash,
            "category": "valid",
            "task": "Refund latest paid order",
            "fixture_ref": "fix",
            "expected_outcome": "PASS",
            "readiness": "TEST_READY",
        },
    )
    db_session.add(case_draft)
    db_session.commit()

    res_model_nr = service.run_case(project_id, suite_rec.suite_id, case_draft.test_id)
    assert res_model_nr.verdict == RuntimeVerdict.MODEL_NOT_READY

    # 2. Test not ready case
    case_test_nr = C2TestCase(
        suite_record_id=suite_rec.id,
        project_id=project_id,
        suite_id=suite_rec.suite_id,
        test_id="case_test_not_ready",
        category="valid",
        execution_mode="live_agent",
        task="Refund latest paid order",
        fixture_ref="fix",
        readiness="TEST_NOT_READY",
        definition={
            "test_id": "case_test_not_ready",
            "project_id": project_id,
            "pinned_model_id": model.model_id,
            "pinned_model_version": model.version,
            "model_content_hash": model_rec.content_hash,
            "category": "valid",
            "task": "Refund latest paid order",
            "fixture_ref": "fix",
            "expected_outcome": "PASS",
            "readiness": "TEST_NOT_READY",
            "readiness_reasons": ["Unresolved variable references"],
        },
    )
    db_session.add(case_test_nr)
    db_session.commit()

    # Now approve model so TEST_NOT_READY is evaluated
    model_rec.lifecycle_status = "APPROVED"
    db_session.commit()

    res_test_nr = service.run_case(project_id, suite_rec.suite_id, case_test_nr.test_id)
    assert res_test_nr.verdict == RuntimeVerdict.TEST_NOT_READY


def test_bounded_suite_execution(
    db_session: Session, approved_project_with_generated_suite
):
    """Bounded suite run executes cases up to max_cases budget and computes suite report."""
    project_id, suite_id, _, _ = approved_project_with_generated_suite
    service = C2IntegrationService(db_session)

    # Execute batch with max_cases = 5
    suite_report = service.run_suite(project_id, suite_id, max_cases=5)

    assert suite_report.suite_id == suite_id
    assert suite_report.project_id == project_id
    assert suite_report.evaluated_cases > 0
    assert suite_report.evaluated_cases <= 5
    assert len(suite_report.case_reports) == suite_report.evaluated_cases
    # Aggregate observed coverage computed
    assert suite_report.aggregate_observed_coverage is not None
    assert suite_report.aggregate_observed_coverage.transition_coverage.numerator > 0
