"""Tests for C2 evaluation and demonstration REST API endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c2_state_aware_workflow.evaluator.fixtures import (
    ScriptedDemonstrationAgent,
)
from app.components.c2_state_aware_workflow.evaluator.observer import (
    IndependentStateObserver,
)
from app.components.c2_state_aware_workflow.evaluator.sut import SyntheticRefundSUT
from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
)
from app.components.c2_state_aware_workflow.persistence.repository import (
    C2ModelRepository,
)
from app.database import Base, get_db
from app.main import app


@pytest.fixture
def client_with_approved_suite():
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

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    db = testing_session_local()
    repo = C2ModelRepository(db)
    project_id = "eval_api_proj"
    model = build_synthetic_refund_efsm()

    # 1. Create model in DRAFT
    repo.create_draft_model(project_id, model)
    from app.components.c2_state_aware_workflow.validator.service import (
        ModelValidationService,
    )

    val_service = ModelValidationService(db)
    val_service.validate_model_record(project_id, model.model_id, model.version)
    # 2. Approve model
    repo.approve_model(
        project_id=project_id,
        model_id=model.model_id,
        version=model.version,
        reviewer_id="eval_reviewer [SELF_REPORTED_DEVELOPMENT]",
        review_basis="Synthetic refund specifications",
    )

    # 3. Generate suite via API
    res_gen = client.post(
        f"/api/v1/c2/projects/{project_id}/suites/generate",
        json={
            "model_id": model.model_id,
            "version": model.version,
            "case_budget": 5,
        },
    )
    assert res_gen.status_code == 201
    suite_id = res_gen.json()["suite_id"]

    # 4. Get first valid test case ID
    res_cases = client.get(
        f"/api/v1/c2/projects/{project_id}/suites/{suite_id}/cases?category=valid"
    )
    test_id = res_cases.json()[0]["test_id"]

    try:
        yield client, project_id, suite_id, test_id, model
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_api_evaluate_test_run_and_retrieval(client_with_approved_suite):
    """Test full evaluation pipeline via API: evaluate evidence, retrieve report, and filter."""
    client, project_id, suite_id, test_id, model = client_with_approved_suite

    # Execute valid happy path evidence
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)
    run_id = "eval_api_run_01"

    evidence = agent.run_happy_path(
        project_id=project_id,
        test_id=test_id,
        run_id=run_id,
        model_id=model.model_id,
        model_version=model.version,
    )

    # 1. Post evaluation
    res_eval = client.post(
        f"/api/v1/c2/projects/{project_id}/suites/{suite_id}/cases/{test_id}/evaluate",
        json=evidence.model_dump(mode="json"),
    )
    assert res_eval.status_code == 200
    eval_data = res_eval.json()
    assert eval_data["verdict"] == "PASS"
    evaluation_id = eval_data["evaluation_id"]
    assert evaluation_id is not None

    # 2. Retrieve evaluation by ID
    res_get = client.get(
        f"/api/v1/c2/projects/{project_id}/evaluations/{evaluation_id}"
    )
    assert res_get.status_code == 200
    get_data = res_get.json()
    assert get_data["verdict"] == "PASS"
    assert get_data["run_id"] == run_id

    # 3. List evaluations with verdict filter
    res_list = client.get(f"/api/v1/c2/projects/{project_id}/evaluations?verdict=PASS")
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert len(list_data) >= 1
    assert any(e["evaluation_id"] == evaluation_id for e in list_data)


def test_api_evaluate_rejects_mismatched_route_parameters(client_with_approved_suite):
    """Test evaluation rejects evidence when route project_id or test_id do not match."""
    client, project_id, suite_id, test_id, model = client_with_approved_suite

    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)

    evidence = agent.run_happy_path(
        project_id="wrong_proj",
        test_id=test_id,
        run_id="run_mismatch",
        model_id=model.model_id,
        model_version=model.version,
    )

    res = client.post(
        f"/api/v1/c2/projects/{project_id}/suites/{suite_id}/cases/{test_id}/evaluate",
        json=evidence.model_dump(mode="json"),
    )
    assert res.status_code == 400
    assert "project_id" in res.json()["detail"]


def test_api_synthetic_demonstrations_endpoint(client_with_approved_suite):
    """Test clearly labelled synthetic demonstration endpoint across key scenarios."""
    client, project_id, _, _, model = client_with_approved_suite

    scenarios = [
        ("happy_path", "PASS"),
        ("inspection_alternative", "PASS"),
        ("unpaid_order_rejection", "EXPECTED REJECTION PASS"),
        ("skipped_step", "FAIL"),
        ("reordered_step", "FAIL"),
        ("wrong_entity", "FAIL"),
        ("missing_effect", "FAIL"),
        ("protected_state_change", "FAIL"),
        ("truncated_trace", "INCONCLUSIVE"),
    ]

    for scenario, expected_verdict in scenarios:
        res = client.post(
            f"/api/v1/c2/projects/{project_id}/demonstrations/run",
            json={
                "scenario": scenario,
                "model_id": model.model_id,
                "model_version": model.version,
            },
        )
        assert res.status_code == 200, f"Scenario '{scenario}' failed with {res.text}"
        data = res.json()
        assert data["verdict"] == expected_verdict, (
            f"Scenario '{scenario}' expected {expected_verdict}, got {data['verdict']}"
        )
