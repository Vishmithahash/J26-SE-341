"""Opt-in live C1 check: generated tool-call suite -> NexaCart's own Ollama agent.

Skipped unless NEXACART_LIVE_E2E=1 (same environment as test_nexacart_live_e2e.py). Optional:
  NEXACART_C1_SEED          generation seed (default 7)
  NEXACART_C1_CASE_FILTER   comma-separated substrings of case ids to run (default: all accepted)

The C1 workflow runs exactly as on the C1 page: import the configuration from the harness
capabilities, generate and validate cases, freeze an accepted suite, then execute every case with
NexaCart's agent on a fresh fixture and evaluate the persisted tool calls. The QA side uses a
throwaway SQLite database; NexaCart keeps fixtures and agent runs as evidence. Results are written to
backend/evidence_output/live_nexacart/c1_suite_report.json. The test asserts that cases ran on real
evidence and that the suite is valid; it records, but does not assert, the agent's verdicts.
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


def test_c1_live_generated_suite_on_nexacart():
    from app.components.c1_tool_call_correctness.contracts.execution import (
        ExecutionRequest,
    )
    from app.components.c1_tool_call_correctness.contracts.generation import (
        GenerationRequest,
    )
    from app.components.c1_tool_call_correctness.examples.nexacart_live import (
        build_nexacart_live_config,
    )
    from app.components.c1_tool_call_correctness.services.config_service import (
        create_project_config,
        create_suite_version,
    )
    from app.components.c1_tool_call_correctness.services.execution_service import (
        ExecutionService,
    )
    from app.components.c1_tool_call_correctness.services.generation_service import (
        execute_generation_job,
    )
    from app.components.c1_tool_call_correctness.services.nexacart_live_adapter import (
        NexaCartLiveAgentAdapter,
    )
    from app.database import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    project = "c1-live-e2e"

    adapter = NexaCartLiveAgentAdapter()
    ready, reason = adapter.check_readiness()
    assert ready, f"Live NexaCart BLOCKED: {reason}"

    config = create_project_config(
        db,
        project,
        build_nexacart_live_config(adapter.capabilities, adapter.target.base_url),
    )
    job, selected, _, _ = execute_generation_job(
        db,
        project,
        GenerationRequest(
            config_version=1,
            seed=int(os.environ.get("NEXACART_C1_SEED", "7")),
            max_candidates=30,
            max_accepted_cases=30,
        ),
    )
    assert job.summary["invalid_candidates"] == 0
    filters = [f for f in os.environ.get("NEXACART_C1_CASE_FILTER", "").split(",") if f]
    cases = [
        c.model_dump(mode="json")
        for c in selected
        if not filters or any(f in c.case_id for f in filters)
    ]
    assert cases
    suite = create_suite_version(
        db, project, "c1_live_suite", "C1 live", config.id, cases
    )
    suite.content_hash = job.content_hash
    db.commit()

    service = ExecutionService()
    run = service.create_and_start_run(
        db, project, ExecutionRequest(suite_id="c1_live_suite"), adapter=adapter
    )
    detail = service.get_run_detail(db, project, run.id)
    assert detail.summary.status.value == "COMPLETED"

    report_cases = []
    for case in detail.case_executions:
        trace = case.raw_trace
        report_cases.append(
            {
                "case_id": case.case_id,
                "category": next(
                    c["category"] for c in cases if c["case_id"] == case.case_id
                ),
                "verdict": case.verdict.value if case.verdict else None,
                "execution_status": case.execution_status.value,
                "trace_completeness": case.trace_completeness.value,
                "task_sent": case.agent_task_sent.task_prompt
                if case.agent_task_sent
                else None,
                "agent_run_id": trace.get("agent_run_id"),
                "agent_model": trace.get("agent_model"),
                "caller_outcome": trace.get("caller_outcome"),
                "duration_ms": trace.get("duration_ms"),
                "tool_calls": [
                    {
                        "index": e.call_index,
                        "tool": e.tool_name,
                        "arguments": e.arguments,
                        "status": e.status.value,
                        "error": e.tool_error,
                    }
                    for e in case.captured_events
                ],
                "failed_checks": [
                    {
                        "rule": c.rule_name,
                        "tool": c.target_tool,
                        "argument": c.target_argument,
                        "reason": c.reason_code,
                        "expected": c.expected_value,
                        "actual": c.actual_value,
                    }
                    for c in case.check_results
                    if c.verdict.value != "PASS"
                ],
                "final_answer": trace.get("final_answer"),
                "error": case.error_message,
            }
        )
        if case.execution_status.value == "EXECUTED":
            assert trace.get("agent_run_id"), case.case_id  # real NexaCart agent run
            assert "{{" not in case.agent_task_sent.task_prompt

    out = Path(__file__).resolve().parents[2] / "evidence_output" / "live_nexacart"
    out.mkdir(parents=True, exist_ok=True)
    (out / "c1_suite_report.json").write_text(
        json.dumps(
            {
                "run_id": detail.summary.run_id,
                "summary": detail.summary.model_dump(mode="json"),
                "generation": job.summary,
                "execution_target": detail.effective_config.get("execution_target"),
                "cases": report_cases,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
