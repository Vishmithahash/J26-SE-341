"""Integration tests for C2 experiment and baseline REST APIs.

Verifies:
1. Dataset manifest import, retrieval, listing, and freezing.
2. Immutability of frozen datasets.
3. Experiment execution across baselines (B1-B4) over frozen evidence.
4. Comparative baseline metrics retrieval and acceptance targets evaluation.
5. Case predictions retrieval.
6. JSON and CSV export endpoints.
7. Project isolation across datasets and experiments.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c2_state_aware_workflow.contracts.experiment import (
    DatasetPartition,
)
from app.components.c2_state_aware_workflow.experiments.benchmark import (
    BenchmarkSuiteBuilder,
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
def mini_manifest():
    """Build a compact 10-case benchmark manifest for fast API testing."""
    builder = BenchmarkSuiteBuilder(project_id="proj_exp_api_test")
    manifest, _, _ = builder.build_benchmark_manifest(
        dataset_id="test_mini_dataset",
        version="v1.0.0",
    )
    # Take first 10 cases for fast API integration tests and set is_frozen=False
    compact_manifest = manifest.model_copy(
        update={
            "cases": manifest.cases[:10],
            "case_count": 10,
            "development_count": len(
                [
                    c
                    for c in manifest.cases[:10]
                    if c.partition == DatasetPartition.DEVELOPMENT
                ]
            ),
            "held_out_count": len(
                [
                    c
                    for c in manifest.cases[:10]
                    if c.partition == DatasetPartition.HELD_OUT
                ]
            ),
            "is_frozen": False,
        }
    )
    return compact_manifest


def test_dataset_lifecycle_and_freeze(client: TestClient, mini_manifest):
    project_id = "proj_exp_api_test"

    # 1. Import dataset manifest
    manifest_dict = mini_manifest.model_dump(mode="json")
    res = client.post(f"/api/v1/c2/projects/{project_id}/datasets", json=manifest_dict)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["dataset_id"] == "test_mini_dataset"
    assert data["version"] == "v1.0.0"
    assert data["case_count"] == 10
    assert data["is_frozen"] is False

    # 2. List datasets
    res_list = client.get(f"/api/v1/c2/projects/{project_id}/datasets")
    assert res_list.status_code == 200
    datasets = res_list.json()
    assert len(datasets) == 1
    assert datasets[0]["dataset_id"] == "test_mini_dataset"

    # 3. Get single dataset
    res_get = client.get(
        f"/api/v1/c2/projects/{project_id}/datasets/test_mini_dataset/versions/v1.0.0"
    )
    assert res_get.status_code == 200
    get_data = res_get.json()
    assert get_data["dataset_id"] == "test_mini_dataset"
    assert len(get_data["cases"]) == 10

    # 4. Freeze dataset
    res_freeze = client.post(
        f"/api/v1/c2/projects/{project_id}/datasets/test_mini_dataset/versions/v1.0.0/freeze"
    )
    assert res_freeze.status_code == 200
    assert res_freeze.json()["is_frozen"] is True

    # 5. Attempt re-import/mutation on frozen dataset returns 409 Conflict
    res_reimport = client.post(
        f"/api/v1/c2/projects/{project_id}/datasets", json=manifest_dict
    )
    assert res_reimport.status_code == 409
    assert "frozen" in res_reimport.json()["detail"].lower()


def test_experiment_execution_and_baselines(client: TestClient, mini_manifest):
    project_id = "proj_exp_api_test"

    # Import and freeze dataset
    manifest_dict = mini_manifest.model_dump(mode="json")
    client.post(f"/api/v1/c2/projects/{project_id}/datasets", json=manifest_dict)
    client.post(
        f"/api/v1/c2/projects/{project_id}/datasets/test_mini_dataset/versions/v1.0.0/freeze"
    )

    # Run experiment
    run_req = {
        "experiment_id": "exp_api_01",
        "name": "API Experiment Run Test",
        "dataset_id": "test_mini_dataset",
        "dataset_version": "v1.0.0",
        "eval_methods": [
            "B1_FINAL_STATE_ONLY",
            "B2_TRACE_ONLY",
            "B3_MILESTONE_BASED",
            "B4_FULL_C2",
        ],
    }
    res_run = client.post(f"/api/v1/c2/projects/{project_id}/experiments", json=run_req)
    assert res_run.status_code == 201, res_run.text
    run_data = res_run.json()
    experiment_id = run_data["experiment_id"]
    assert run_data["status"] == "COMPLETED"
    assert run_data["total_cases_evaluated"] == 40  # 10 cases * 4 methods

    # Retrieve experiment comparative baselines report
    res_report = client.get(
        f"/api/v1/c2/projects/{project_id}/experiments/{experiment_id}/baselines"
    )
    assert res_report.status_code == 200
    report = res_report.json()
    assert report["experiment_id"] == experiment_id
    assert report["dataset_id"] == "test_mini_dataset"
    assert len(report["metrics_by_method"]) == 4

    # Verify B1-B4 presence and localization honesty
    methods = report["metrics_by_method"]
    assert "B1_FINAL_STATE_ONLY" in methods
    assert "B2_TRACE_ONLY" in methods
    assert "B3_MILESTONE_BASED" in methods
    assert "B4_FULL_C2" in methods

    # B1 and B3 must report localization unavailable
    assert methods["B1_FINAL_STATE_ONLY"]["localization_metrics"]["accuracy"] is None
    assert methods["B3_MILESTONE_BASED"]["localization_metrics"]["accuracy"] is None

    # Retrieve case predictions
    res_cases = client.get(
        f"/api/v1/c2/projects/{project_id}/experiments/{experiment_id}/cases"
    )
    assert res_cases.status_code == 200
    cases_data = res_cases.json()
    # 10 cases * 4 methods = 40 case predictions
    assert len(cases_data) == 40
    methods_found = {c["method_id"] for c in cases_data}
    assert methods_found == {
        "B1_FINAL_STATE_ONLY",
        "B2_TRACE_ONLY",
        "B3_MILESTONE_BASED",
        "B4_FULL_C2",
    }


def test_experiment_export_json_and_csv(client: TestClient, mini_manifest):
    project_id = "proj_exp_api_test"
    manifest_dict = mini_manifest.model_dump(mode="json")
    client.post(f"/api/v1/c2/projects/{project_id}/datasets", json=manifest_dict)

    run_req = {
        "experiment_id": "exp_export_01",
        "name": "Export Test",
        "dataset_id": "test_mini_dataset",
        "dataset_version": "v1.0.0",
        "eval_methods": ["B1_FINAL_STATE_ONLY", "B4_FULL_C2"],
    }
    res_run = client.post(f"/api/v1/c2/projects/{project_id}/experiments", json=run_req)
    assert res_run.status_code == 201, res_run.text
    experiment_id = res_run.json()["experiment_id"]

    # Export JSON
    res_json = client.get(
        f"/api/v1/c2/projects/{project_id}/experiments/{experiment_id}/export?format=json"
    )
    assert res_json.status_code == 200
    assert "application/json" in res_json.headers["content-type"]
    json_data = res_json.json()
    assert json_data["experiment_id"] == experiment_id

    # Export CSV
    res_csv = client.get(
        f"/api/v1/c2/projects/{project_id}/experiments/{experiment_id}/export?format=csv"
    )
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    csv_text = res_csv.text
    lines = (
        csv_text.strip().split("\r\n")
        if "\r\n" in csv_text
        else csv_text.strip().split("\n")
    )
    assert len(lines) >= 3  # Header + 2 methods
    header = lines[0].split(",")
    assert "method" in header
    assert "precision" in header
    assert "recall" in header
    assert "f1_score" in header


def test_project_isolation(client: TestClient, mini_manifest):
    project_a = "proj_alpha"
    project_b = "proj_beta"

    # Import dataset into Project A
    manifest_a = mini_manifest.model_copy(update={"project_id": project_a})
    manifest_dict = manifest_a.model_dump(mode="json")
    res_create = client.post(
        f"/api/v1/c2/projects/{project_a}/datasets", json=manifest_dict
    )
    assert res_create.status_code == 201

    # Project B cannot access Project A's dataset
    res_b = client.get(
        f"/api/v1/c2/projects/{project_b}/datasets/test_mini_dataset/versions/v1.0.0"
    )
    assert res_b.status_code == 404

    # Run experiment in Project A
    run_req = {
        "experiment_id": "exp_iso_01",
        "name": "Isolation Test",
        "dataset_id": "test_mini_dataset",
        "dataset_version": "v1.0.0",
        "eval_methods": ["B4_FULL_C2"],
    }
    res_run = client.post(f"/api/v1/c2/projects/{project_a}/experiments", json=run_req)
    assert res_run.status_code == 201
    exp_id = res_run.json()["experiment_id"]

    # Project B cannot access Project A's experiment
    res_exp_b = client.get(
        f"/api/v1/c2/projects/{project_b}/experiments/{exp_id}/baselines"
    )
    assert res_exp_b.status_code == 404
