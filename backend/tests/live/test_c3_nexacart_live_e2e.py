"""Opt-in live C3 check: automatic NexaCart fault suite, matched trials with NexaCart's Ollama agent.

Skipped unless NEXACART_LIVE_E2E=1 (same environment as test_nexacart_live_e2e.py). Optional:
  NEXACART_C3_CASE_FILTER   comma-separated FAMILY:PHASE cells to run, e.g.
                            TIMEOUT_DISCONNECTION:AFTER_COMMIT,TOOL_UNAVAILABILITY:BEFORE_EFFECT
                            (default: every generated case)

The QA side uses a throwaway SQLite database. NexaCart keeps the synthetic fixtures and agent runs
as evidence. Per-case results are written to
backend/evidence_output/live_nexacart/c3_suite_report.json. The test asserts that the cases ran on
real evidence; it records, but does not assert, the agent's recovery verdicts.
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


def test_c3_live_suite_generation_and_matched_trials():
    from app.components.c3_robustness_recovery.models.persistence import (
        C3EvaluationModel,
        C3MatchedPairModel,
    )
    from app.components.c3_robustness_recovery.runtime.nexacart_live import (
        NexaCartLiveSuiteRunner,
    )
    from app.components.c3_robustness_recovery.services.live_execution import (
        generate_and_store_nexacart_suite,
        run_live_execution_job,
        start_live_execution,
    )
    from app.components.c3_robustness_recovery.services.run_tracking import (
        get_execution,
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
    project_id = "proj_live_c3_nexacart"

    generation, stored = generate_and_store_nexacart_suite(db, project_id, capabilities)
    assert stored is not None, generation.reasons
    suite = generation.frozen_suite

    cell_filter = {
        tuple(cell.split(":"))
        for cell in os.environ.get("NEXACART_C3_CASE_FILTER", "").split(",")
        if cell
    }
    case_ids = [
        c.case_id
        for c in suite.selected_cases
        if not cell_filter or (c.fault_family.value, c.effect_phase.value) in cell_filter
    ]
    assert case_ids

    execution = start_live_execution(
        db, project_id, suite, stored.suite_digest, case_ids, capabilities.get("agent")
    )
    run_live_execution_job(
        project_id,
        execution.execution_id,
        suite,
        case_ids,
        factory,
        NexaCartLiveSuiteRunner(adapter=target),
    )

    db.expire_all()
    record = get_execution(db, project_id, execution.execution_id)
    pairs = db.query(C3MatchedPairModel).filter_by(execution_id=record.execution_id).all()
    evaluations = {e.pair_id: e for e in db.query(C3EvaluationModel).all()}
    cases = {c.case_id: c for c in suite.selected_cases}
    report = {
        "execution_id": record.execution_id,
        "status": record.status.value,
        "halt_reason": record.halt_reason,
        "agent": capabilities.get("agent"),
        "suite_id": suite.suite_id,
        "suite_digest": suite.suite_digest,
        "generation_counters": generation.counters.model_dump(),
        "cases": [],
    }
    for pair in pairs:
        ev = pair.evidence_snapshot
        case = cases[pair.case_id]
        evaluation = evaluations.get(pair.pair_id)
        aut = ev["configuration_snapshot"].get("aut_trials", {})
        report["cases"].append(
            {
                "case_id": pair.case_id,
                "fault_family": case.fault_family.value,
                "effect_phase": case.effect_phase.value,
                "pair_id": pair.pair_id,
                "exposure_status": pair.exposure_status,
                "exposure_reasons": ev.get("exposure_reasons"),
                "clean_qualification": pair.clean_qualification,
                "recovery_verdict": evaluation.recovery_verdict if evaluation else None,
                "first_violated_rule": evaluation.first_violated_rule
                if evaluation
                else None,
                "rules": [
                    (r["rule_id"], r["status"], r.get("reason_code"))
                    for r in (evaluation.rule_results_snapshot if evaluation else [])
                ],
                "clean": {
                    k: aut.get("clean", {}).get(k)
                    for k in ("agent_run_id", "caller_outcome", "final_answer", "tool_calls")
                },
                "fault": {
                    k: aut.get("fault", {}).get(k)
                    for k in (
                        "agent_run_id",
                        "caller_outcome",
                        "outcome_classification",
                        "final_answer",
                        "tool_calls",
                        "final_state",
                    )
                },
            }
        )
    report["case_results"] = record.manifest_snapshot.get("case_results")
    out = Path(__file__).resolve().parents[2] / "evidence_output" / "live_nexacart"
    out.mkdir(parents=True, exist_ok=True)
    (out / "c3_suite_report.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )

    assert record.target_mode == "LIVE_AUT"
    assert record.status.value in ("COMPLETED", "ERROR"), record.halt_reason
    assert len(pairs) == record.executed_cases_count > 0
    for pair in pairs:
        aut = pair.evidence_snapshot["configuration_snapshot"]["aut_trials"]
        assert aut["clean"]["agent_run_id"] and aut["fault"]["agent_run_id"]
        assert pair.evidence_snapshot["caller_identity"] == "ACTUAL_AGENT"
