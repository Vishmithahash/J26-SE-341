"""Opt-in live C4 check: the full policy workflow over HTTP against NexaCart's Ollama agent.

import NexaCart policy -> contract -> accept -> generate + validate + freeze -> live executions.

Skipped unless NEXACART_LIVE_E2E=1 (same environment as test_nexacart_live_e2e.py). Optional:
  NEXACART_C4_CASE_FILTER   comma-separated case keys, e.g. shop-purchase-injection,refund-over-limit
  NEXACART_C4_REPETITIONS   live runs per case (default 3, as in the proposal); results include per-case rates
                            (default: every generated case)

The QA side uses a throwaway SQLite database. NexaCart keeps the synthetic fixtures and agent runs
as evidence. Per-case results are written to
backend/evidence_output/live_nexacart/c4_suite_report.json. The test asserts that every case ran on
real agent evidence; it records, but does not assert, the agent's policy verdicts.
"""

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

pytestmark = pytest.mark.skipif(
    os.environ.get("NEXACART_LIVE_E2E") != "1",
    reason="Live NexaCart e2e is opt-in (set NEXACART_LIVE_E2E=1 and NexaCart credentials).",
)

PROJECT_ID = "proj_live_c4_nexacart"


def test_c4_live_policy_workflow_over_http():
    from app.components.c4_policy_aware_safety.api.live_router import (
        get_c4_session_factory,
    )
    from app.components.c4_policy_aware_safety.generation.nexacart_live_generator import (
        nexacart_case_id,
    )
    from app.config import get_settings
    from app.database import Base, get_db
    from app.main import app
    from app.shared.auth.dependencies import require_active_user
    from app.shared.auth.models import User, UserRole
    from app.shared.projects.models import (
        Project,
        ProjectConnectionState,
        ProjectLifecycle,
    )

    get_settings.cache_clear()
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = factory()
    user = User(
        id=4101,
        name="C4 Live E2E",
        email="c4-live-e2e@example.com",
        canonical_email="c4-live-e2e@example.com",
        password_hash="x",
        role=UserRole.USER,
        is_active=True,
    )
    db.add(user)
    db.add(
        Project(
            project_id=PROJECT_ID,
            owner_user_id=user.id,
            name="C4 NexaCart Live E2E",
            domain="ecommerce",
            environment="TEST",
            backend_base_url=os.environ.get("NEXACART_BASE_URL", ""),
            backend_health_url=os.environ.get("NEXACART_BASE_URL", "") + "/health",
            configuration_version=1,
            lifecycle=ProjectLifecycle.ACTIVE.value,
            connection_state=ProjectConnectionState.CONNECTED.value,
        )
    )
    db.commit()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_active_user] = lambda: user
    app.dependency_overrides[get_c4_session_factory] = lambda: factory
    base = f"/projects/{PROJECT_ID}/c4"
    try:
        with TestClient(app) as client:
            readiness = client.get(f"{base}/live/nexacart/readiness").json()
            assert readiness["is_ready"], readiness["blockers"]

            imported = client.post(f"{base}/live/nexacart/import")
            assert imported.status_code == 201, imported.text
            body = imported.json()
            contract_id = body["suggested_contract_id"]

            created = client.post(
                f"{base}/contracts",
                json={
                    "contract_id": contract_id,
                    "rule_ids": body["candidate_rule_ids"],
                },
            )
            assert created.status_code == 201, created.text
            accepted = client.post(
                f"{base}/contracts/{contract_id}/versions/1/accept",
                json={
                    "accepted_by": "c4-live-e2e",
                    "rationale": "NexaCart reference rules",
                },
            )
            assert accepted.status_code == 200, accepted.text

            generated = client.post(
                f"{base}/generate",
                json={
                    "contract_id": contract_id,
                    "contract_version": 1,
                    "binding_id": body["binding_id"],
                    "binding_version": body["binding_version"],
                    "auto_validate": True,
                    "auto_freeze": True,
                },
            )
            assert generated.status_code == 200, generated.text
            report = generated.json()

            wanted = [
                k for k in os.environ.get("NEXACART_C4_CASE_FILTER", "").split(",") if k
            ]
            case_ids = [nexacart_case_id(contract_id, 1, k) for k in wanted] or None
            # Starlette runs the background job before the TestClient call returns.
            started = client.post(
                f"{base}/live/nexacart/executions",
                json={
                    "contract_id": contract_id,
                    "contract_version": 1,
                    "case_ids": case_ids,
                    "repetitions": int(os.environ.get("NEXACART_C4_REPETITIONS", "3")),
                },
            )
            assert started.status_code == 202, started.text
            execution = client.get(
                f"{base}/live/nexacart/executions/{started.json()['execution_id']}"
            ).json()
            runs = {
                f"{r['case_id']}#{r['repetition']}": client.get(f"{base}/runs/{r['run_id']}").json()
                for r in execution["case_results"]
                if r.get("run_id")
            }
    finally:
        app.dependency_overrides.clear()
        db.close()

    out = Path(__file__).resolve().parents[2] / "evidence_output" / "live_nexacart"
    out.mkdir(parents=True, exist_ok=True)
    (out / "c4_suite_report.json").write_text(
        json.dumps(
            {
                "agent": readiness["agent"],
                "generation": {
                    "generated_count": report.get("generated_count"),
                    "frozen_count": report.get("frozen_count"),
                    "metadata": report.get("metadata"),
                },
                "execution": execution,
                "runs": {
                    run_key: {
                        "policy_verdict": run["policy_verdict"],
                        "findings": [
                            (f["rule_id"], f["verdict"], f["reason_codes"])
                            for f in run["findings"]
                        ],
                        "live_nexacart": run["evaluation_report_summary"].get(
                            "live_nexacart"
                        ),
                        "evidence": run["evaluation_report_summary"].get("evidence"),
                    }
                    for run_key, run in runs.items()
                },
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    assert execution["status"] == "COMPLETED", execution.get("error_message")
    assert execution["case_results"] and len(runs) == len(execution["case_results"])
    for run in runs.values():
        assert run["execution_mode"] == "LIVE_AUT"
        assert run["adapter_id"] == "nexacart_live_c4_adapter"
        assert run["evaluation_report_summary"]["live_nexacart"][
            "nexacart_agent_run_id"
        ]
