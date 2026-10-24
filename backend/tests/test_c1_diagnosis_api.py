import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CauseCategory,
    DiagnosisStatus,
)
from app.components.c1_tool_call_correctness.examples import (
    get_nexacart_refund_example_config,
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
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


from tests.auth_test_fixtures import AutoSeedingTestClient, seed_test_admin
from app.shared.auth.dependencies import require_active_user


@pytest.fixture
def client(db_session):
    admin_user = seed_test_admin(db_session)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_active_user] = lambda: admin_user
    with AutoSeedingTestClient(db_session, admin_user) as test_client:
        yield test_client
    app.dependency_overrides.clear()



def _setup_run_with_failures(client: TestClient, project_id: str) -> str:
    """Configures project, generates and promotes suite, then executes run with simulated failing adapter."""
    # 1. Config
    cfg_payload = get_nexacart_refund_example_config().model_dump()
    cfg_resp = client.post(
        f"/api/v1/projects/{project_id}/c1/configs", json=cfg_payload
    )
    assert cfg_resp.status_code == 201

    # 2. Generation & Promotion
    gen_payload = {
        "config_version": 1,
        "max_candidates": 6,
        "max_accepted_cases": 4,
        "seed": 42,
        "auto_promote_suite": True,
    }
    gen_resp = client.post(
        f"/api/v1/projects/{project_id}/c1/generation/jobs",
        json=gen_payload,
    )
    assert gen_resp.status_code == 201
    job_id = gen_resp.json()["job_id"]

    promote_payload = {
        "suite_id": "suite_diag_test",
        "name": "Diagnosis Test Suite",
    }
    promote_resp = client.post(
        f"/api/v1/projects/{project_id}/c1/generation/jobs/{job_id}/promote-suite",
        json=promote_payload,
    )
    assert promote_resp.status_code == 201

    # 3. Execute run with adapter_override='failing' to generate deliberate failures
    run_payload = {
        "suite_id": "suite_diag_test",
        "adapter_override": "failing",
    }
    run_resp = client.post(
        f"/api/v1/projects/{project_id}/c1/runs",
        json=run_payload,
    )
    assert run_resp.status_code == 201
    run_id = run_resp.json()["summary"]["run_id"]
    return run_id


def test_diagnosis_apis_full_lifecycle(client):
    """Test full API lifecycle for requesting, retrieving, and inspecting diagnoses."""
    project_id = "proj_diag_api"
    run_id = _setup_run_with_failures(client, project_id)

    # 1. Request batch diagnosis for the failing run
    diag_req_payload = {
        "idempotency_key": "diag_key_001",
        "use_model_assisted": False,
    }
    resp = client.post(
        f"/api/v1/projects/{project_id}/c1/runs/{run_id}/diagnose",
        json=diag_req_payload,
    )
    assert resp.status_code == 200
    diagnoses = resp.json()
    assert len(diagnoses) > 0

    first_diag = diagnoses[0]
    diag_id = first_diag["diagnosis_id"]
    case_id = first_diag["case_id"]

    assert first_diag["project_id"] == project_id
    assert first_diag["run_id"] == run_id
    assert first_diag["status"] in (
        DiagnosisStatus.COMPLETED.value,
        DiagnosisStatus.INSUFFICIENT_EVIDENCE.value,
    )
    assert first_diag["cause_category"] in [c.value for c in CauseCategory]
    assert len(first_diag["explanation_summary"]) > 0
    assert "retrieval_ms" in first_diag["metrics"]

    # 2. Idempotency test: repeated request with same key returns identical results
    resp_idempotent = client.post(
        f"/api/v1/projects/{project_id}/c1/runs/{run_id}/diagnose",
        json=diag_req_payload,
    )
    assert resp_idempotent.status_code == 200
    second_diagnoses = resp_idempotent.json()
    assert len(second_diagnoses) == len(diagnoses)
    assert second_diagnoses[0]["diagnosis_id"] == diag_id

    # 3. GET /diagnoses/{diagnosis_id}
    get_diag_resp = client.get(f"/api/v1/projects/{project_id}/c1/diagnoses/{diag_id}")
    assert get_diag_resp.status_code == 200
    fetched_diag = get_diag_resp.json()
    assert fetched_diag["diagnosis_id"] == diag_id
    assert fetched_diag["case_id"] == case_id

    # 4. GET /runs/{run_id}/cases/{case_id}/diagnosis
    get_case_diag_resp = client.get(
        f"/api/v1/projects/{project_id}/c1/runs/{run_id}/cases/{case_id}/diagnosis"
    )
    assert get_case_diag_resp.status_code == 200
    assert get_case_diag_resp.json()["diagnosis_id"] == diag_id

    # 5. GET /diagnoses/{diagnosis_id}/code-locations
    locs_resp = client.get(
        f"/api/v1/projects/{project_id}/c1/diagnoses/{diag_id}/code-locations"
    )
    assert locs_resp.status_code == 200
    locations = locs_resp.json()
    assert isinstance(locations, list)

    # 6. GET /diagnoses (list history)
    list_resp = client.get(f"/api/v1/projects/{project_id}/c1/diagnoses")
    assert list_resp.status_code == 200
    history = list_resp.json()
    assert len(history) >= len(diagnoses)
    diag_summary = next(h for h in history if h["diagnosis_id"] == diag_id)
    assert diag_summary["case_id"] == case_id
    assert diag_summary["run_id"] == run_id

    # 7. Non-existent ID errors
    assert (
        client.get(
            f"/api/v1/projects/{project_id}/c1/diagnoses/non_existent_id"
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/projects/{project_id}/c1/runs/{run_id}/cases/unknown_case/diagnosis"
        ).status_code
        == 404
    )
