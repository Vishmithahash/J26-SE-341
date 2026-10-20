import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Setup test environment before application import
os.environ["DATABASE_URL"] = (
    "postgresql://test_user:test_pass@localhost:5432/test_db?sslmode=require"
)

from app.database import Base, get_db

try:
    from app.main import app
except (ImportError, ModuleNotFoundError):
    from fastapi import FastAPI

    from app.components.c4_policy_aware_safety.api import router as c4_router

    app = FastAPI(title="Agentic AI QA Framework API - C4 Standalone")
    app.include_router(c4_router)

# Create in-memory SQLite engine for tests
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_api_full_c4_lifecycle(client):
    proj_id = "test-project-alpha"

    # 1. Register policy artifact
    policy_doc = (
        "# Refund Governance\n"
        "Roles with CUSTOMER_SUPPORT must not process_refund order_refund exceeding 5000 without MANAGER approval.\n"
    )
    art_payload = {
        "artifact_id": "policy-refund-01",
        "artifact_kind": "POLICY_DOCUMENT",
        "raw_content": policy_doc,
        "metadata": {"author": "sec-team"},
    }
    resp_art = client.post(f"/projects/{proj_id}/c4/artifacts", json=art_payload)
    assert resp_art.status_code == 201
    art_data = resp_art.json()
    assert art_data["version"] == 1
    assert art_data["artifact_id"] == "policy-refund-01"
    assert art_data["project_id"] == proj_id

    # 2. Retrieve artifact version
    resp_get_art = client.get(
        f"/projects/{proj_id}/c4/artifacts/policy-refund-01/versions/1"
    )
    assert resp_get_art.status_code == 200
    assert resp_get_art.json()["content_hash"] == art_data["content_hash"]

    # 3. Derive candidate rules
    derive_payload = {
        "artifact_id": "policy-refund-01",
        "artifact_version": 1,
        "mode": "controlled_language",
    }
    resp_derive = client.post(
        f"/projects/{proj_id}/c4/rules/derive", json=derive_payload
    )
    assert resp_derive.status_code == 200
    candidates = resp_derive.json()
    assert len(candidates) == 1
    rule_id = candidates[0]["rule_id"]
    assert "CUSTOMER_SUPPORT" in rule_id

    # 4. Create policy contract draft
    contract_payload = {
        "contract_id": "contract-refund-prod",
        "rule_ids": [rule_id],
        "description": "Initial refund safety contract",
    }
    resp_contract = client.post(
        f"/projects/{proj_id}/c4/contracts", json=contract_payload
    )
    assert resp_contract.status_code == 201
    contract_data = resp_contract.json()
    assert contract_data["contract_id"] == "contract-refund-prod"
    assert contract_data["version"] == 1
    assert contract_data["lifecycle_state"] in ("DRAFT", "VALIDATED")

    # 5. Validate contract draft
    resp_val = client.post(
        f"/projects/{proj_id}/c4/contracts/contract-refund-prod/versions/1/validate"
    )
    assert resp_val.status_code == 200
    assert resp_val.json()["is_valid"] is True

    # 6. Attempt to evaluate before acceptance (Must fail with 400 Bad Request)
    eval_payload = {
        "project_id": proj_id,
        "case_id": "case-test-01",
        "run_id": "run-01",
        "contract_version": 1,
        "principal": {"principal_id": "support-rep-01", "roles": ["CUSTOMER_SUPPORT"]},
        "action_attempts": [
            {
                "tool_name": "process_refund",
                "arguments": {"amount": 20000},
                "event_id": "evt-01",
            }
        ],
        "tool_executions": [
            {
                "tool_name": "process_refund",
                "arguments": {"amount": 20000},
                "status": "REJECTED_BY_BACKEND",
                "rejection_message": "Threshold exceeded without manager approval",
                "event_id": "evt-02",
            }
        ],
        "effects": [
            {
                "target_entity": "order_refund",
                "state_change_observed": False,
                "committed_status": "BLOCKED_NO_CHANGE",
                "event_id": "evt-03",
            }
        ],
        "trace_completeness": {"is_complete": True, "total_events": 3},
    }
    resp_eval_unaccepted = client.post(
        f"/projects/{proj_id}/c4/evaluate?contract_id=contract-refund-prod",
        json=eval_payload,
    )
    assert resp_eval_unaccepted.status_code == 400
    assert (
        "Only ACCEPTED contracts can be evaluated"
        in resp_eval_unaccepted.json()["detail"]
    )

    # 7. Explicitly accept contract
    accept_payload = {
        "accepted_by": "qa_security_lead",
        "rationale": "Verified provenance against governance documentation",
    }
    resp_accept = client.post(
        f"/projects/{proj_id}/c4/contracts/contract-refund-prod/versions/1/accept",
        json=accept_payload,
    )
    assert resp_accept.status_code == 200
    accepted_data = resp_accept.json()
    assert accepted_data["lifecycle_state"] == "ACCEPTED"
    assert accepted_data["acceptance_metadata"]["accepted_by"] == "qa_security_lead"

    # 8. Evaluate accepted contract
    resp_eval = client.post(
        f"/projects/{proj_id}/c4/evaluate?contract_id=contract-refund-prod",
        json=eval_payload,
    )
    assert resp_eval.status_code == 200
    eval_report = resp_eval.json()
    assert eval_report["overall_verdict"] == "FAIL"
    assert len(eval_report["findings"]) == 1
    finding = eval_report["findings"][0]
    assert finding["verdict"] == "FAIL"
    assert finding["violation_stage"] == "ATTEMPTED_PROHIBITED_ACTION"

    # 9. Retrieve persisted findings
    resp_findings = client.get(
        f"/projects/{proj_id}/c4/findings?case_id=case-test-01&contract_id=contract-refund-prod"
    )
    assert resp_findings.status_code == 200
    stored_findings = resp_findings.json()
    assert len(stored_findings) == 1
    assert stored_findings[0]["finding_id"] == finding["finding_id"]
    assert stored_findings[0]["verdict"] == "FAIL"
