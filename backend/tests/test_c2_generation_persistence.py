"""Tests for C2 test suite and case database persistence."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.components.c2_state_aware_workflow.contracts.test_definition import (
    GenerateTestSuiteRequest,
    TestCategory,
    TestReadinessStatus,
)
from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
)
from app.components.c2_state_aware_workflow.generator.service import (
    TestGenerationService,
)
from app.components.c2_state_aware_workflow.persistence import (
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
def approved_model_record(db_session: Session):
    efsm = build_synthetic_refund_efsm()
    repo = C2ModelRepository(db_session)
    repo.create_draft_model(efsm.project_id, efsm)

    val_service = ModelValidationService(db_session)
    val_service.validate_model_record(efsm.project_id, efsm.model_id, efsm.version)

    approved = repo.approve_model(
        project_id=efsm.project_id,
        model_id=efsm.model_id,
        version=efsm.version,
        reviewer_id="reviewer_test [SELF_REPORTED_DEVELOPMENT]",
        review_basis="Test basis",
    )
    return approved


def test_persist_and_retrieve_test_suite_and_cases(
    db_session: Session, approved_model_record
):
    """Test generating, persisting, and querying test suites and cases."""
    service = TestGenerationService(db_session)
    request = GenerateTestSuiteRequest(
        model_id=approved_model_record.model_id,
        version=approved_model_record.version,
        seed=42,
        case_budget=10,
        include_mutations=True,
        mutation_budget=4,
    )

    persisted_suite = service.generate_suite_for_model(
        project_id=approved_model_record.project_id,
        model_id=approved_model_record.model_id,
        version=approved_model_record.version,
        request=request,
    )

    assert persisted_suite.id is not None
    assert persisted_suite.suite_id.startswith("suite_")
    assert persisted_suite.total_cases > 0
    assert persisted_suite.ready_cases_count > 0

    repo = C2ModelRepository(db_session)

    # Retrieve suite by (project_id, suite_id)
    retrieved = repo.get_test_suite(
        approved_model_record.project_id, persisted_suite.suite_id
    )
    assert retrieved is not None
    assert retrieved.model_content_hash == approved_model_record.content_hash
    assert retrieved.generator_version == "c2_generator_v1"

    # List suites for project
    suites = repo.list_test_suites(approved_model_record.project_id)
    assert len(suites) == 1
    assert suites[0].suite_id == persisted_suite.suite_id

    # List cases for suite
    cases = repo.list_test_cases(
        approved_model_record.project_id, persisted_suite.suite_id
    )
    assert len(cases) == persisted_suite.total_cases

    # Filter cases by category
    valid_cases = repo.list_test_cases(
        approved_model_record.project_id,
        persisted_suite.suite_id,
        category=TestCategory.VALID.value,
    )
    assert len(valid_cases) >= 1
    for vc in valid_cases:
        assert vc.category == TestCategory.VALID.value

    # Filter cases by readiness
    ready_cases = repo.list_test_cases(
        approved_model_record.project_id,
        persisted_suite.suite_id,
        readiness=TestReadinessStatus.TEST_READY.value,
    )
    assert len(ready_cases) == persisted_suite.ready_cases_count

    # Retrieve individual case
    single_case = repo.get_test_case(
        approved_model_record.project_id,
        persisted_suite.suite_id,
        cases[0].test_id,
    )
    assert single_case is not None
    assert single_case.test_id == cases[0].test_id
    assert "private_reference_paths" in single_case.definition


def test_cascade_deletion_on_model_or_suite(db_session: Session, approved_model_record):
    """Deleting a suite deletes constituent cases cleanly."""
    service = TestGenerationService(db_session)
    request = GenerateTestSuiteRequest(
        model_id=approved_model_record.model_id,
        version=approved_model_record.version,
        seed=100,
        case_budget=5,
        include_mutations=False,
    )

    persisted_suite = service.generate_suite_for_model(
        project_id=approved_model_record.project_id,
        model_id=approved_model_record.model_id,
        version=approved_model_record.version,
        request=request,
    )

    repo = C2ModelRepository(db_session)
    cases_before = repo.list_test_cases(
        approved_model_record.project_id, persisted_suite.suite_id
    )
    assert len(cases_before) > 0

    # Delete suite record
    db_session.delete(persisted_suite)
    db_session.commit()

    # Cases must be deleted via cascade
    cases_after = repo.list_test_cases(
        approved_model_record.project_id, persisted_suite.suite_id
    )
    assert len(cases_after) == 0
