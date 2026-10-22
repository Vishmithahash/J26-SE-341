"""Tests for C2 test generation, suite persistence, and export REST APIs."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
)
from app.components.c2_state_aware_workflow.persistence import C2ModelRepository
from app.components.c2_state_aware_workflow.validator.service import (
    ModelValidationService,
)
from app.database import Base, get_db
from app.main import app


from tests.auth_test_fixtures import AutoSeedingTestClient, seed_test_admin, seed_test_projects
from app.shared.auth.dependencies import require_active_user


@pytest.fixture
def client_with_approved_model():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    # Pre-seed approved refund model in database
    db = testing_session_local()
    admin_user = seed_test_admin(db)
    efsm = build_synthetic_refund_efsm()
    seed_test_projects(db, [efsm.project_id], owner_id=admin_user.id)
    repo = C2ModelRepository(db)
    repo.create_draft_model(efsm.project_id, efsm)
    val_service = ModelValidationService(db)
    val_service.validate_model_record(efsm.project_id, efsm.model_id, efsm.version)
    repo.approve_model(
        project_id=efsm.project_id,
        model_id=efsm.model_id,
        version=efsm.version,
        reviewer_id="lead_qa [SELF_REPORTED_DEVELOPMENT]",
        review_basis="Synthetic refund specifications",
    )
    db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_active_user] = lambda: admin_user
    with AutoSeedingTestClient(testing_session_local(), admin_user) as test_client:
        yield test_client
    app.dependency_overrides.clear()



def test_api_generate_suite_and_query_endpoints(
    client_with_approved_model: TestClient,
):
    project_id = "research_project_nexacart"
    model_id = "refund_efsm"
    version = "1.0.0"

    # 1. Generate test suite
    gen_payload = {
        "model_id": model_id,
        "version": version,
        "seed": 42,
        "case_budget": 10,
        "include_alternatives": True,
        "include_negative_rejections": True,
        "include_mutations": True,
        "mutation_budget": 4,
    }
    res_gen = client_with_approved_model.post(
        f"/api/v1/c2/projects/{project_id}/suites/generate",
        json=gen_payload,
    )
    assert res_gen.status_code == 201
    suite_data = res_gen.json()
    assert "suite_id" in suite_data
    suite_id = suite_data["suite_id"]
    assert suite_data["total_cases"] > 0
    assert suite_data["ready_cases_count"] > 0

    # 2. List suites
    res_list = client_with_approved_model.get(
        f"/api/v1/c2/projects/{project_id}/suites"
    )
    assert res_list.status_code == 200
    suites = res_list.json()
    assert len(suites) == 1
    assert suites[0]["suite_id"] == suite_id

    # 3. Get specific suite
    res_get_suite = client_with_approved_model.get(
        f"/api/v1/c2/projects/{project_id}/suites/{suite_id}"
    )
    assert res_get_suite.status_code == 200
    assert res_get_suite.json()["suite_id"] == suite_id

    # 4. List cases in suite
    res_cases = client_with_approved_model.get(
        f"/api/v1/c2/projects/{project_id}/suites/{suite_id}/cases"
    )
    assert res_cases.status_code == 200
    cases = res_cases.json()
    assert len(cases) == suite_data["total_cases"]
    test_id = cases[0]["test_id"]

    # 5. Filter cases by category
    res_filter = client_with_approved_model.get(
        f"/api/v1/c2/projects/{project_id}/suites/{suite_id}/cases?category=valid"
    )
    assert res_filter.status_code == 200
    valid_cases = res_filter.json()
    assert len(valid_cases) >= 1
    assert all(c["category"] == "valid" for c in valid_cases)

    # 6. Get case detail
    res_case_detail = client_with_approved_model.get(
        f"/api/v1/c2/projects/{project_id}/suites/{suite_id}/cases/{test_id}"
    )
    assert res_case_detail.status_code == 200
    detail = res_case_detail.json()
    assert detail["test_id"] == test_id
    assert "definition" in detail
    assert "private_reference_paths" in detail["definition"]

    # 7. Suite readiness
    res_readiness = client_with_approved_model.get(
        f"/api/v1/c2/projects/{project_id}/suites/{suite_id}/readiness"
    )
    assert res_readiness.status_code == 200
    r_data = res_readiness.json()
    assert r_data["suite_id"] == suite_id
    assert r_data["ready_cases_count"] > 0

    # 8. Export QA Suite
    res_qa_export = client_with_approved_model.get(
        f"/api/v1/c2/projects/{project_id}/suites/{suite_id}/export/qa"
    )
    assert res_qa_export.status_code == 200
    qa_export = res_qa_export.json()
    assert qa_export["suite_id"] == suite_id
    assert len(qa_export["cases"]) == suite_data["total_cases"]
    assert "private_reference_paths" in qa_export["cases"][0]


def test_api_oracle_isolation_agent_exports(
    client_with_approved_model: TestClient,
):
    """Verify strict allowlist isolation: agent exports NEVER leak reference paths, assertions, or outcomes."""
    project_id = "research_project_nexacart"
    model_id = "refund_efsm"
    version = "1.0.0"

    res_gen = client_with_approved_model.post(
        f"/api/v1/c2/projects/{project_id}/suites/generate",
        json={
            "model_id": model_id,
            "version": version,
            "include_mutations": True,
            "mutation_budget": 2,
        },
    )
    suite_id = res_gen.json()["suite_id"]

    # 1. Batch agent payload export
    res_agent_export = client_with_approved_model.get(
        f"/api/v1/c2/projects/{project_id}/suites/{suite_id}/export/agent"
    )
    assert res_agent_export.status_code == 200
    agent_tasks = res_agent_export.json()
    assert len(agent_tasks) > 0

    prohibited_keys = {
        "private_reference_paths",
        "private_reference_transitions",
        "private_reference_assertions",
        "expected_outcome",
        "mutation_provenance",
        "intended_violation",
        "injected_fault_code",
    }

    for task in agent_tasks:
        # Check that only allowed keys exist
        assert set(task.keys()) <= {
            "test_id",
            "project_id",
            "task",
            "fixture_ref",
            "permitted_context",
        }
        for bad_key in prohibited_keys:
            assert bad_key not in task

    # 2. Individual case agent payload
    test_id = agent_tasks[0]["test_id"]
    res_single_agent = client_with_approved_model.get(
        f"/api/v1/c2/projects/{project_id}/suites/{suite_id}/cases/{test_id}/agent-payload"
    )
    assert res_single_agent.status_code == 200
    single_payload = res_single_agent.json()
    assert set(single_payload.keys()) <= {
        "test_id",
        "project_id",
        "task",
        "fixture_ref",
        "permitted_context",
    }
    for bad_key in prohibited_keys:
        assert bad_key not in single_payload


def test_api_generate_suite_rejects_unapproved_model(
    client_with_approved_model: TestClient,
):
    """Attempting to generate a suite for an unapproved draft model yields 422 with MODEL NOT READY."""
    project_id = "research_project_nexacart"
    model_id = "refund_efsm"

    # Spawn an unapproved draft version 2.0.0 from existing 1.0.0
    res_draft = client_with_approved_model.post(
        f"/api/v1/c2/projects/{project_id}/models/{model_id}/versions/1.0.0/new-draft",
        json={"new_version": "2.0.0", "description": "Unapproved draft v2"},
    )
    assert res_draft.status_code == 201
    assert res_draft.json()["lifecycle_status"] == "DRAFT"

    # Attempt to generate suite for draft version 2.0.0
    res_gen = client_with_approved_model.post(
        f"/api/v1/c2/projects/{project_id}/suites/generate",
        json={
            "model_id": model_id,
            "version": "2.0.0",
        },
    )
    assert res_gen.status_code == 422
    data = res_gen.json()
    assert data["detail"]["readiness"] == "MODEL NOT READY"
