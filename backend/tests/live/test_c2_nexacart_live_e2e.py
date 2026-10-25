"""Opt-in live C2 check: NexaCart reference EFSMs -> generated suites -> NexaCart's Ollama agent.

Skipped unless NEXACART_LIVE_E2E=1 (same environment as test_nexacart_live_e2e.py). Optional:
  NEXACART_C2_MODEL_FILTER   comma-separated model ids (default: every NexaCart reference workflow)
  NEXACART_C2_CASE_BUDGET    generated path cases per model (default 2; each is one agent run)

Per model the C2 workflow runs exactly as on the C2 pages: import the reference EFSM as a draft,
validate it, approve it, generate a suite (paths + mutations), then run every generated case:
live cases with NexaCart's agent on fresh fixtures, mutants on their parent's live trace.
The QA side uses a throwaway SQLite database. NexaCart keeps the synthetic fixtures and agent
runs as evidence. Results are written to backend/evidence_output/live_nexacart/c2_suite_report.json.
The test asserts that cases ran on real evidence; it records, but does not assert, the verdicts.
"""

import json
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

pytestmark = pytest.mark.skipif(
    os.environ.get("NEXACART_LIVE_E2E") != "1",
    reason="Live NexaCart e2e is opt-in (set NEXACART_LIVE_E2E=1 and NexaCart credentials).",
)


def test_c2_live_generated_suites_on_nexacart():
    from app.components.c2_state_aware_workflow.contracts.test_definition import (
        GenerateTestSuiteRequest,
    )
    from app.components.c2_state_aware_workflow.examples.nexacart_workflows import (
        NEXACART_WORKFLOWS,
    )
    from app.components.c2_state_aware_workflow.generator.service import (
        TestGenerationService,
    )
    from app.components.c2_state_aware_workflow.integrations.live_execution import (
        execution_to_dict,
        import_reference_model,
        run_live_execution_job,
        start_live_execution,
    )
    from app.components.c2_state_aware_workflow.integrations.nexacart_live import (
        NexaCartLiveWorkflowRunner,
    )
    from app.components.c2_state_aware_workflow.persistence.models import (
        C2LiveExecution,
    )
    from app.components.c2_state_aware_workflow.persistence.repository import (
        C2ModelRepository,
    )
    from app.components.c2_state_aware_workflow.validator.service import (
        ModelValidationService,
    )
    from app.config import get_settings
    from app.database import Base
    from app.shared.integration.adapters import LiveNexaCartTargetAdapter

    get_settings.cache_clear()
    target = LiveNexaCartTargetAdapter()
    ready, reasons = target.client.check_readiness()
    assert ready, f"NexaCart harness not ready: {reasons}"
    capabilities = target.client.get_capabilities()

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    db = factory()
    project_id = "proj_live_c2_nexacart"
    repo = C2ModelRepository(db)

    model_filter = [
        m for m in os.environ.get("NEXACART_C2_MODEL_FILTER", "").split(",") if m
    ]
    case_budget = int(os.environ.get("NEXACART_C2_CASE_BUDGET", "2"))
    report: dict = {
        "base_url": target.base_url,
        "harness_version": capabilities.get("harnessVersion"),
        "agent": capabilities.get("agent"),
        "case_budget": case_budget,
        "executions": [],
    }
    out = Path(__file__).resolve().parents[2] / "evidence_output" / "live_nexacart"
    out.mkdir(parents=True, exist_ok=True)

    for model_id, workflow in NEXACART_WORKFLOWS.items():
        if model_filter and model_id not in model_filter:
            continue
        version = import_reference_model(db, project_id, model_id)["version"]
        ModelValidationService(db).validate_model_record(project_id, model_id, version)
        repo.approve_model(
            project_id=project_id,
            model_id=model_id,
            version=version,
            reviewer_id="live-e2e [SELF_REPORTED_DEVELOPMENT]",
            review_basis=f"NexaCart business rules {workflow.business_rules}",
        )
        suite = TestGenerationService(db).generate_suite_for_model(
            project_id=project_id,
            model_id=model_id,
            version=version,
            request=GenerateTestSuiteRequest(
                model_id=model_id,
                version=version,
                case_budget=case_budget,
                mutation_budget=8,
            ),
        )
        test_ids = [c.test_id for c in repo.list_test_cases(project_id, suite.suite_id)]
        execution = start_live_execution(
            db,
            project_id,
            suite,
            test_ids,
            user_id="live-e2e",
            capabilities=capabilities,
            base_url=target.base_url,
        )
        run_live_execution_job(
            project_id,
            execution.execution_id,
            factory,
            NexaCartLiveWorkflowRunner(adapter=target),
        )
        db.expire_all()
        record = db.get(C2LiveExecution, execution.execution_id)
        report["executions"].append(execution_to_dict(record))
        (out / "c2_suite_report.json").write_text(
            json.dumps(report, indent=2, default=str), encoding="utf-8"
        )

        assert record.status in ("COMPLETED", "ERROR"), record.halt_reason
        live = [
            r
            for r in record.case_results
            if r["category"] != "mutated" and r["status"] == "EXECUTED"
        ]
        assert live, f"{model_id}: no live case executed ({record.halt_reason})"
        for result in live:
            assert result["agent_run_id"], result
            assert result["verdict"] is not None, result
