import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c1_tool_call_correctness.examples import (
    get_nexacart_refund_example_config,
)
from app.database import Base, get_db
from app.main import app


@pytest.fixture
def db_session():
    """Create an isolated in-memory SQLite database for testing persistence and API behavior."""
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


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_create_and_retrieve_project_config(client):
    project_id = "proj_nexacart_test"
    payload = get_nexacart_refund_example_config().model_dump()

    # 1. Create config
    resp = client.post(f"/api/v1/projects/{project_id}/c1/configs", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    config_id = data["id"]
    assert data["project_id"] == project_id
    assert data["version"] == 1
    assert data["is_immutable"] is False
    assert len(data["tools"]) == 3
    assert len(data["requirements"]) == 4

    # 2. Retrieve config
    get_resp = client.get(f"/api/v1/projects/{project_id}/c1/configs/{config_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == config_id


def test_list_project_configs_scoped_to_project(client):
    proj_a = "proj_alpha"
    proj_b = "proj_beta"

    payload_a = get_nexacart_refund_example_config().model_dump()
    payload_b = get_nexacart_refund_example_config().model_dump()

    # Create config in Alpha
    resp_a = client.post(f"/api/v1/projects/{proj_a}/c1/configs", json=payload_a)
    assert resp_a.status_code == 201

    # Create config in Beta
    resp_b = client.post(f"/api/v1/projects/{proj_b}/c1/configs", json=payload_b)
    assert resp_b.status_code == 201

    # Listing Alpha only returns Alpha
    list_a = client.get(f"/api/v1/projects/{proj_a}/c1/configs").json()
    assert len(list_a) == 1
    assert list_a[0]["project_id"] == proj_a

    # Listing Beta only returns Beta
    list_b = client.get(f"/api/v1/projects/{proj_b}/c1/configs").json()
    assert len(list_b) == 1
    assert list_b[0]["project_id"] == proj_b


def test_project_boundary_security_and_isolation(client):
    proj_a = "proj_authorized"
    proj_b = "proj_foreign"

    # 1. Request with mismatched X-Project-ID header is rejected with 403 Forbidden
    resp = client.get(
        f"/api/v1/projects/{proj_a}/c1/configs",
        headers={"X-Project-ID": proj_b},
    )
    assert resp.status_code == 403
    assert "Cross-project access denied" in resp.json()["detail"]

    # 2. Cross-project config retrieval returns 404
    payload_a = get_nexacart_refund_example_config().model_dump()
    create_resp = client.post(f"/api/v1/projects/{proj_a}/c1/configs", json=payload_a)
    config_a_id = create_resp.json()["id"]

    # Querying proj_b for proj_a's config ID
    cross_resp = client.get(f"/api/v1/projects/{proj_b}/c1/configs/{config_a_id}")
    assert cross_resp.status_code == 404


def test_update_config_and_immutability_locking(client):
    project_id = "proj_immutability_test"
    payload = get_nexacart_refund_example_config().model_dump()

    # Create config
    resp = client.post(f"/api/v1/projects/{project_id}/c1/configs", json=payload)
    config_id = resp.json()["id"]

    # Update mutable config succeeds
    update_payload = {"agent_connection_ref": "conn_updated_ref"}
    put_resp = client.put(
        f"/api/v1/projects/{project_id}/c1/configs/{config_id}",
        json=update_payload,
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["agent_connection_ref"] == "conn_updated_ref"

    # Accept into suite version -> locks config
    suite_payload = {
        "suite_id": "suite_regression_01",
        "name": "NexaCart Baseline Suite",
        "config_id": config_id,
        "cases": [{"case_id": "case_refund_101", "name": "Standard Refund"}],
    }
    suite_resp = client.post(
        f"/api/v1/projects/{project_id}/c1/suites", json=suite_payload
    )
    assert suite_resp.status_code == 201
    assert suite_resp.json()["is_immutable"] is True

    # Check config is now immutable
    get_resp = client.get(f"/api/v1/projects/{project_id}/c1/configs/{config_id}")
    assert get_resp.json()["is_immutable"] is True

    # Attempting to mutate locked config must return 409 Conflict
    forbidden_put = client.put(
        f"/api/v1/projects/{project_id}/c1/configs/{config_id}",
        json={"agent_connection_ref": "conn_attempt_illegal_mutation"},
    )
    assert forbidden_put.status_code == 409
    assert "immutable" in forbidden_put.json()["detail"].lower()


def test_validate_spec_transient_endpoint(client):
    project_id = "proj_validate_test"
    payload = get_nexacart_refund_example_config().model_dump()

    # Valid transient spec
    resp = client.post(
        f"/api/v1/projects/{project_id}/c1/configs/validate-spec", json=payload
    )
    assert resp.status_code == 200
    assert resp.json()["is_valid"] is True
    assert resp.json()["error_count"] == 0

    # Invalid transient spec (e.g. unknown tool in constraints)
    payload["tool_constraints"]["required_tools"].append("ghost_tool")
    invalid_resp = client.post(
        f"/api/v1/projects/{project_id}/c1/configs/validate-spec", json=payload
    )
    assert invalid_resp.status_code == 200
    assert invalid_resp.json()["is_valid"] is False
    assert invalid_resp.json()["error_count"] >= 1


def test_get_nexacart_example_endpoint(client):
    project_id = "proj_demo"
    resp = client.get(f"/api/v1/projects/{project_id}/c1/examples/nexacart")
    assert resp.status_code == 200
    data = resp.json()
    assert "user_request" in data
    assert "config" in data
    assert "fixture_context" in data
    assert data["config"]["agent_connection_ref"] == "conn_nexacart_staging_agent"
