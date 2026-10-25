"""Live NexaCart execution service for C2: reference-model import, background runs, summaries.

Component: C2 - State-Aware Multi-Step Workflow Testing

The C2 workflow is unchanged: a NexaCart reference EFSM is imported as a DRAFT, validated and
approved by a reviewer on the C2 pages, a suite is generated automatically from the approved
model, and the selected cases run live. A live agent run takes about a minute with local Ollama,
so an execution is recorded as RUNNING and executed in the background; the C2 page polls it.
Every case's evidence and evaluation is persisted by the standard C2 evaluation service.
"""

import logging
import statistics
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    GeneratedTestDefinition,
)
from app.components.c2_state_aware_workflow.examples.nexacart_workflows import (
    NEXACART_WORKFLOWS,
)
from app.components.c2_state_aware_workflow.integrations.nexacart_live import (
    SCORED_PASS_VERDICTS,
    LiveC2CaseResult,
    NexaCartLiveWorkflowRunner,
)
from app.components.c2_state_aware_workflow.persistence.models import (
    C2LiveExecution,
    C2TestSuite,
)
from app.components.c2_state_aware_workflow.persistence.repository import (
    C2ModelRepository,
    ModelAlreadyExistsError,
)

logger = logging.getLogger(__name__)

RUNNING = "RUNNING"
COMPLETED = "COMPLETED"
ERROR = "ERROR"
CANCELLED = "CANCELLED"


def list_reference_workflows(db: Session, project_id: str) -> list[dict[str, Any]]:
    """NexaCart reference workflows with their import, approval and suite status in the project."""
    repo = C2ModelRepository(db)
    rows = []
    for workflow in NEXACART_WORKFLOWS.values():
        model = workflow.builder(project_id)
        record = repo.get_model(project_id, model.model_id, model.version)
        suites = (
            db.execute(
                select(C2TestSuite.suite_id).where(
                    C2TestSuite.project_id == project_id,
                    C2TestSuite.model_id == model.model_id,
                    C2TestSuite.model_version == model.version,
                )
            )
            .scalars()
            .all()
        )
        rows.append(
            {
                "model_id": model.model_id,
                "version": model.version,
                "name": model.name,
                "title": workflow.title,
                "kind": workflow.kind,
                "description": model.description,
                "fixture_id": workflow.fixture_id,
                "fixture_definition": workflow.fixture_definition,
                "tasks": sorted(
                    {o.task_prompt for o in model.final_outcomes if o.task_prompt}
                ),
                "business_rules": workflow.business_rules,
                "states_count": len(model.states),
                "transitions_count": len(model.transitions),
                "lifecycle_status": record.lifecycle_status if record else None,
                "suite_ids": list(suites),
            }
        )
    return rows


def import_reference_model(
    db: Session, project_id: str, model_id: str
) -> dict[str, Any]:
    """Create the NexaCart reference EFSM as a DRAFT in the project (idempotent)."""
    workflow = NEXACART_WORKFLOWS[model_id]
    model = workflow.builder(project_id)
    repo = C2ModelRepository(db)
    existing = repo.get_model(project_id, model.model_id, model.version)
    if existing is not None:
        return {
            "created": False,
            "lifecycle_status": existing.lifecycle_status,
            "version": model.version,
        }
    try:
        record = repo.create_draft_model(project_id, model)
    except ModelAlreadyExistsError:
        record = repo.get_model(project_id, model.model_id, model.version)
        return {
            "created": False,
            "lifecycle_status": record.lifecycle_status,
            "version": model.version,
        }
    db.commit()
    return {
        "created": True,
        "lifecycle_status": record.lifecycle_status,
        "version": model.version,
    }


def _ordered_selection(
    cases: list[GeneratedTestDefinition], test_ids: list[str] | None
) -> list[GeneratedTestDefinition]:
    if not test_ids:
        return list(cases)
    wanted = set(test_ids)
    return [c for c in cases if c.test_id in wanted]


def start_live_execution(
    db: Session,
    project_id: str,
    suite: C2TestSuite,
    test_ids: list[str],
    user_id: str | None,
    capabilities: dict[str, Any] | None,
    base_url: str | None,
) -> C2LiveExecution:
    """Persist a RUNNING execution record before any NexaCart activity."""
    workflow = NEXACART_WORKFLOWS.get(suite.model_id)
    record = C2LiveExecution(
        execution_id=f"c2x-{uuid.uuid4().hex[:12]}",
        project_id=project_id,
        suite_id=suite.suite_id,
        model_id=suite.model_id,
        model_version=suite.model_version,
        target="NEXACART",
        status=RUNNING,
        planned_test_ids=list(test_ids),
        case_results=[],
        summary={},
        configuration_snapshot={
            "target": "NexaCart QA harness",
            "base_url": base_url,
            "harness_version": (capabilities or {}).get("harnessVersion"),
            "agent": (capabilities or {}).get("agent"),
            "model_content_hash": suite.model_content_hash,
            "fixture_definition_id": workflow.fixture_id if workflow else None,
            "fixture_definition": workflow.fixture_definition if workflow else None,
            "runner": "c2_nexacart_live_runner",
        },
        created_by=user_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(pct / 100.0 * (len(ordered) - 1))))
    return round(ordered[index], 1)


def build_summary(
    case_results: list[dict[str, Any]], model: EFSMModelDefinition | None
) -> dict[str, Any]:
    """Suite-level C2 results: live verdicts, mutation detection, first divergences, coverage."""
    live = [
        r
        for r in case_results
        if r.get("category") != "mutated" and r.get("status") == "EXECUTED"
    ]
    mutants = [r for r in case_results if r.get("category") == "mutated"]
    verdicts: dict[str, int] = {}
    for r in live:
        verdicts[r.get("verdict") or "NONE"] = (
            verdicts.get(r.get("verdict") or "NONE", 0) + 1
        )
    statuses: dict[str, int] = {}
    for r in case_results:
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1

    conforming = sum(1 for r in live if r.get("verdict") in SCORED_PASS_VERDICTS)
    applied = [m for m in mutants if m.get("status") == "EXECUTED"]
    detected = sum(1 for m in applied if m.get("mutation_detected"))

    covered_transitions: set[str] = set()
    covered_guards: set[str] = set()
    for r in live:
        covered_transitions.update(r.get("covered_transitions") or [])
        covered_guards.update(r.get("covered_guard_outcomes") or [])

    coverage: dict[str, Any] = {}
    if model is not None:
        all_ids = [t.id for t in model.transitions]
        workflow_ids = [t for t in all_ids if not t.startswith("T_READ_")]
        guard_targets = [
            f"{t.id}_outcome_{o}"
            for t in model.transitions
            if t.guard
            for o in ("TRUE", "FALSE")
        ]
        coverage = {
            "transitions_covered": len(covered_transitions & set(all_ids)),
            "transitions_total": len(all_ids),
            "workflow_transitions_covered": len(
                covered_transitions & set(workflow_ids)
            ),
            "workflow_transitions_total": len(workflow_ids),
            "workflow_transition_ratio": round(
                len(covered_transitions & set(workflow_ids))
                / max(1, len(workflow_ids)),
                3,
            ),
            "covered_transition_ids": sorted(covered_transitions),
            "guard_outcomes_covered": len(covered_guards),
            "guard_outcome_targets": len(guard_targets),
            "basis": (
                "Union over live (non-mutant) runs. Workflow transitions exclude neutral "
                "catalogue/cart/address read loops (T_READ_*)."
            ),
        }

    durations = [float(r.get("duration_ms") or 0.0) for r in live]
    return {
        "planned_cases": len(case_results),
        "status_counts": statuses,
        "live": {
            "executed": len(live),
            "verdict_counts": verdicts,
            "conforming": conforming,
            "conformance_rate": round(conforming / len(live), 3) if live else None,
            "inconclusive_rate": round(verdicts.get("INCONCLUSIVE", 0) / len(live), 3)
            if live
            else None,
            "agent_run_ids": [
                r.get("agent_run_id") for r in live if r.get("agent_run_id")
            ],
        },
        "mutation": {
            "total": len(mutants),
            "applied": len(applied),
            "detected": detected,
            "not_applicable": sum(
                1 for m in mutants if m.get("status") == "NOT_APPLICABLE"
            ),
            "detection_score": round(detected / len(applied), 3) if applied else None,
            "basis": "Controlled mutants of conforming live traces (oracle sensitivity).",
        },
        "first_divergences": [
            {
                "test_id": r["test_id"],
                "category": r.get("category"),
                "event_index": (r.get("first_divergence") or {}).get("event_index"),
                "attempted_event": (r.get("first_divergence") or {}).get(
                    "attempted_event"
                ),
                "violation_type": (r.get("first_divergence") or {}).get(
                    "violation_type"
                ),
                "state_at_divergence": (r.get("first_divergence") or {}).get(
                    "state_at_divergence"
                ),
            }
            for r in case_results
            if r.get("first_divergence")
        ],
        "coverage": coverage,
        "overhead": {
            "live_case_duration_ms_median": round(statistics.median(durations), 1)
            if durations
            else None,
            "live_case_duration_ms_p95": _percentile(durations, 95),
        },
    }


def run_live_execution_job(
    project_id: str,
    execution_id: str,
    session_factory: Callable[[], Session],
    runner: NexaCartLiveWorkflowRunner | None = None,
) -> None:
    """Background job: run the selected cases live and persist progress after every case."""
    db = session_factory()
    try:
        record = db.get(C2LiveExecution, execution_id)
        if record is None:
            return
        repo = C2ModelRepository(db)
        model_record = repo.get_model(project_id, record.model_id, record.model_version)
        model = EFSMModelDefinition(**model_record.definition) if model_record else None
        runner = runner or NexaCartLiveWorkflowRunner()

        not_ready = (
            ["Pinned model not found."]
            if model is None
            else runner.check_readiness(model)
        )
        if not_ready:
            record.status = ERROR
            record.halt_reason = "Live NexaCart execution BLOCKED: " + " | ".join(
                not_ready
            )
            record.completed_at = datetime.now(UTC)
            db.commit()
            return

        suite_cases = {
            c.test_id: GeneratedTestDefinition(**c.definition)
            for c in repo.list_test_cases(project_id, record.suite_id)
        }
        selected = _ordered_selection(
            list(suite_cases.values()), record.planned_test_ids
        )

        def on_case_done(result: LiveC2CaseResult) -> None:
            record.case_results = [*record.case_results, result.to_record()]
            record.summary = build_summary(record.case_results, model)
            db.commit()

        _, halt_reason = runner.run_cases(
            db,
            project_id,
            record.suite_id,
            selected,
            model,
            model_is_approved=model_record.lifecycle_status == "APPROVED",
            execution_id=execution_id,
            all_cases=suite_cases,
            on_case_done=on_case_done,
        )
        errors = sum(1 for r in record.case_results if r["status"] == "ERROR")
        record.status = ERROR if errors else CANCELLED if halt_reason else COMPLETED
        record.halt_reason = halt_reason or (
            f"{errors} case(s) could not be executed live." if errors else None
        )
        record.summary = build_summary(record.case_results, model)
        record.completed_at = datetime.now(UTC)
        db.commit()
    except Exception as exc:
        logger.exception("Live C2 execution %s failed", execution_id)
        db.rollback()
        try:
            record = db.get(C2LiveExecution, execution_id)
            if record is not None:
                record.status = ERROR
                record.halt_reason = (
                    f"Live execution failed: {type(exc).__name__}: {exc}"
                )
                record.completed_at = datetime.now(UTC)
                db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
    finally:
        db.close()


def execution_to_dict(record: C2LiveExecution) -> dict[str, Any]:
    return {
        "execution_id": record.execution_id,
        "project_id": record.project_id,
        "suite_id": record.suite_id,
        "model_id": record.model_id,
        "model_version": record.model_version,
        "target": record.target,
        "status": record.status,
        "planned_test_ids": record.planned_test_ids,
        "case_results": record.case_results,
        "summary": record.summary,
        "configuration_snapshot": record.configuration_snapshot,
        "halt_reason": record.halt_reason,
        "created_by": record.created_by,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "completed_at": record.completed_at,
    }
