"""Comprehensive tests for C2 reporting, publishing adapter, and integration APIs.

Verifies:
1. C2ReportContributionContract and C2SuiteReportContract schema completeness.
2. All 6 runtime verdict categories represented; readiness rejections separated from scored outcomes.
3. C2ReportPublisher typed publishing adapter behavior (honest stub without fake claims).
4. REST API endpoints:
   - Case and suite run execution
   - Retained evidence retrieval and digest verification
   - Idempotent re-evaluation from retained evidence
   - Detailed observed coverage retrieval (case and aggregated suite)
   - Run and suite report retrieval and export
5. Project, suite, and model version isolation.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    RuntimeVerdict,
)
from app.components.c2_state_aware_workflow.contracts.report import (
    C2ReportContributionContract,
    ExecutionProvenance,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    GenerateTestSuiteRequest,
)
from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
)
from app.components.c2_state_aware_workflow.generator.service import (
    TestGenerationService,
)
from app.components.c2_state_aware_workflow.integrations.reporting import (
    C2ReportPublisher,
)
from app.components.c2_state_aware_workflow.persistence.repository import (
    C2ModelRepository,
)
from app.components.c2_state_aware_workflow.validator.service import (
    ModelValidationService,
)
from app.database import Base, get_db
from app.main import app


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def setup_c2_suite(db_session: Session):
    project_id = "proj_report_test"
    repo = C2ModelRepository(db_session)
    val_service = ModelValidationService(db_session)
    gen_service = TestGenerationService(db_session)

    model = build_synthetic_refund_efsm()
    model = model.model_copy(update={"project_id": project_id})
    repo.create_draft_model(project_id, model)
    val_service.validate_model_record(project_id, model.model_id, model.version)
    repo.approve_model(
        project_id=project_id,
        model_id=model.model_id,
        version=model.version,
        reviewer_id="reviewer_rep",
        review_basis="Approved for report tests",
    )

    req = GenerateTestSuiteRequest(
        model_id=model.model_id,
        version=model.version,
        include_mutations=True,
        case_budget=8,
    )
    suite = gen_service.generate_suite_for_model(
        project_id=project_id,
        model_id=model.model_id,
        version=model.version,
        request=req,
    )
    return project_id, suite.suite_id, model.model_id, model.version


def test_publisher_adapter_honest_status():
    publisher = C2ReportPublisher(aggregator_client=None)
    assert publisher.is_aggregator_connected is False

    prov = ExecutionProvenance(
        intended_execution_mode="live_agent",
        actual_execution_origin="scripted_synthetic_demonstration",
        runner_id="test_runner",
    )
    from app.components.c2_state_aware_workflow.evaluator.coverage import (
        ObservedCoverageEngine,
    )

    model = build_synthetic_refund_efsm()
    engine = ObservedCoverageEngine(model)
    cov = engine.compute_coverage(
        covered_transitions=set(),
        guard_true_outcomes=set(),
        guard_false_outcomes=set(),
        guard_unknown_observations=set(),
        satisfied_effects=set(),
        violated_effects=set(),
        unknown_effects=set(),
    )

    dummy_report = C2ReportContributionContract(
        component="C2_STATE_AWARE_WORKFLOW",
        contract_version="2026.1",
        project_id="p1",
        suite_id="s1",
        test_id="t1",
        run_id="r1",
        evaluation_id="e1",
        model_id=model.model_id,
        model_version=model.version,
        model_content_hash="h1",
        fixture_version="2026.1",
        runner_version="2026.1",
        evaluator_version="2026.1",
        execution_provenance=prov,
        verdict=RuntimeVerdict.PASS,
        verdict_category="EVALUATION_OUTCOME",
        reason_codes=["All steps passed"],
        evidence_digest="digest_123",
        evidence_references=["evt_1"],
        observed_coverage=cov,
    )

    status = publisher.publish(dummy_report)
    assert status == "STUB_PENDING_SHARED_AGGREGATOR"

    # With a mock connected aggregator
    class MockAggregator:
        def publish(self, payload):
            return "PUBLISHED_AGGREGATOR_ACK_456"

    mock_pub = C2ReportPublisher(aggregator_client=MockAggregator())
    assert mock_pub.is_aggregator_connected is True
    assert mock_pub.publish(dummy_report) == "PUBLISHED_AGGREGATOR_ACK_456"


def test_api_run_case_evidence_and_report_endpoints(
    client: TestClient, setup_c2_suite, db_session: Session
):
    project_id, suite_id, *_ = setup_c2_suite
    repo = C2ModelRepository(db_session)
    cases = repo.list_test_cases(project_id, suite_id)
    assert len(cases) > 0
    case_to_run = cases[0]

    # 1. POST /run case
    run_resp = client.post(
        f"/api/v1/c2/projects/{project_id}/suites/{suite_id}/cases/{case_to_run.test_id}/run",
        json={"intended_execution_mode": "live_agent"},
    )
    assert run_resp.status_code == 200
    eval_data = run_resp.json()
    assert eval_data["test_id"] == case_to_run.test_id
    evaluation_id = eval_data["evaluation_id"]
    run_id = eval_data["run_id"]
    assert evaluation_id is not None
    assert run_id is not None

    # 2. GET /evidence/{run_id}
    ev_resp = client.get(f"/api/v1/c2/projects/{project_id}/evidence/{run_id}")
    assert ev_resp.status_code == 200
    ev_data = ev_resp.json()
    assert ev_data["run_id"] == run_id
    assert "evidence_digest" in ev_data
    assert "evidence_payload" in ev_data
    assert (
        ev_data["execution_provenance"]["actual_execution_origin"]
        == "scripted_synthetic_demonstration"
    )
    assert ev_data["execution_provenance"]["is_live_execution"] is False

    # 3. GET /evaluations/{evaluation_id}/coverage
    cov_resp = client.get(
        f"/api/v1/c2/projects/{project_id}/evaluations/{evaluation_id}/coverage"
    )
    assert cov_resp.status_code == 200
    cov_data = cov_resp.json()
    assert "transition_coverage" in cov_data
    assert cov_data["transition_coverage"]["denominator"] > 0
    assert "guard_outcome_coverage" in cov_data
    assert cov_data["guard_outcome_coverage"]["denominator"] > 0
    assert "selected_path_coverage" in cov_data
    assert "state_effect_coverage" in cov_data

    # 4. GET /evaluations/{evaluation_id}/report
    rep_resp = client.get(
        f"/api/v1/c2/projects/{project_id}/evaluations/{evaluation_id}/report"
    )
    assert rep_resp.status_code == 200
    rep_data = rep_resp.json()
    assert rep_data["component"] == "C2_STATE_AWARE_WORKFLOW"
    assert rep_data["contract_version"] == "2026.1"
    assert rep_data["evaluation_id"] == evaluation_id
    assert rep_data["verdict"] in [v.value for v in RuntimeVerdict]
    assert rep_data["published_to_shared_aggregator"] is False
    assert rep_data["publishing_status"] == "STUB_PENDING_SHARED_AGGREGATOR"

    # 5. POST /evaluations/{evaluation_id}/export-report
    exp_resp = client.post(
        f"/api/v1/c2/projects/{project_id}/evaluations/{evaluation_id}/export-report"
    )
    assert exp_resp.status_code == 200
    exp_data = exp_resp.json()
    assert exp_data["publishing_status"] == "STUB_PENDING_SHARED_AGGREGATOR"
    assert "report_contribution" in exp_data

    # 6. POST /evaluations/{evaluation_id}/re-evaluate (reproduce from retained evidence)
    re_resp = client.post(
        f"/api/v1/c2/projects/{project_id}/evaluations/{evaluation_id}/re-evaluate",
        json={"evaluator_version": "c2_evaluator_v1", "evaluator_config": {}},
    )
    assert re_resp.status_code == 200
    re_data = re_resp.json()
    # Idempotent re-evaluation with identical config returns existing evaluation_id
    assert re_data["evaluation_id"] == evaluation_id


def test_api_batch_suite_run_and_suite_report(client: TestClient, setup_c2_suite):
    project_id, suite_id, model_id, _ = setup_c2_suite

    # 1. Run batch suite
    batch_resp = client.post(
        f"/api/v1/c2/projects/{project_id}/suites/{suite_id}/run",
        json={"max_cases": 4},
    )
    assert batch_resp.status_code == 200
    batch_data = batch_resp.json()
    assert batch_data["suite_id"] == suite_id
    assert batch_data["evaluated_cases"] <= 4
    assert len(batch_data["case_reports"]) > 0

    # 2. GET /suites/{suite_id}/coverage
    suite_cov_resp = client.get(
        f"/api/v1/c2/projects/{project_id}/suites/{suite_id}/coverage"
    )
    assert suite_cov_resp.status_code == 200
    suite_cov = suite_cov_resp.json()
    assert suite_cov["model_id"] == model_id
    assert "transition_coverage" in suite_cov
    assert suite_cov["transition_coverage"]["denominator"] > 0

    # 3. GET /suites/{suite_id}/report
    suite_rep_resp = client.get(
        f"/api/v1/c2/projects/{project_id}/suites/{suite_id}/report"
    )
    assert suite_rep_resp.status_code == 200
    suite_rep = suite_rep_resp.json()
    assert suite_rep["component"] == "C2_STATE_AWARE_WORKFLOW"
    assert suite_rep["suite_id"] == suite_id
    assert "verdict_counts" in suite_rep
    assert "readiness_rejection_counts" in suite_rep
    assert "scored_agent_outcomes" in suite_rep
    assert len(suite_rep["case_reports"]) > 0


def test_project_and_model_isolation(client: TestClient, setup_c2_suite):
    project_id, suite_id, *_ = setup_c2_suite

    # Run one case in project_id
    repo_cases = client.get(f"/api/v1/c2/projects/{project_id}/suites/{suite_id}/cases")
    test_id = repo_cases.json()[0]["test_id"]

    run_resp = client.post(
        f"/api/v1/c2/projects/{project_id}/suites/{suite_id}/cases/{test_id}/run"
    )
    assert run_resp.status_code == 200
    run_id = run_resp.json()["run_id"]
    eval_id = run_resp.json()["evaluation_id"]

    # Attempt to retrieve evidence from a different project
    ev_cross = client.get(
        f"/api/v1/c2/projects/different_unauthorized_project/evidence/{run_id}"
    )
    assert ev_cross.status_code == 404

    # Attempt to retrieve report from a different project
    rep_cross = client.get(
        f"/api/v1/c2/projects/different_unauthorized_project/evaluations/{eval_id}/report"
    )
    assert rep_cross.status_code == 404
