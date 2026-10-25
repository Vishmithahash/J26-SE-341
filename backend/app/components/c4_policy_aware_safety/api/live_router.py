"""C4 live NexaCart endpoints: readiness, domain/policy import and background execution.

The standard C4 workflow stays the same (policy artifact -> candidate rules -> accepted contract
-> generated and frozen cases -> runs). These endpoints add the live NexaCart pieces:

* ``GET  .../c4/live/nexacart/readiness``      harness, credentials and agent model
* ``POST .../c4/live/nexacart/import``         project-scoped NexaCart binding, policy document and
                                               reviewed reference candidate rules (to review/accept)
* ``POST .../c4/live/nexacart/executions``     run frozen NexaCart cases in the background
* ``GET  .../c4/live/nexacart/executions[/id]`` progress and per-case verdicts

Each case run is persisted as a normal C4 run record (adapter ``nexacart_live_c4_adapter``).
"""

import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.components.c4_policy_aware_safety.api.dependencies import (
    get_authorized_c4_project,
)
from app.components.c4_policy_aware_safety.contracts.artifacts import (
    ArtifactCreate,
    ArtifactVersionRecord,
)
from app.components.c4_policy_aware_safety.contracts.cases import CaseLifecycleState
from app.components.c4_policy_aware_safety.contracts.enums import (
    ArtifactKind,
    ContractLifecycleState,
)
from app.components.c4_policy_aware_safety.contracts.rules import CandidateRule
from app.components.c4_policy_aware_safety.derivation.intake import normalize_artifact
from app.components.c4_policy_aware_safety.domains.nexacart_live import (
    NEXACART_DOMAIN_ID,
    NEXACART_POLICY_ARTIFACT_ID,
    NEXACART_POLICY_MARKDOWN,
    NEXACART_REFERENCE_CONTRACT_ID,
    build_nexacart_binding,
    build_nexacart_reference_rules,
)
from app.components.c4_policy_aware_safety.execution.nexacart_live_adapter import (
    NexaCartLiveC4Adapter,
)
from app.components.c4_policy_aware_safety.execution.repetition_summary import (
    summarize_case_rates,
)
from app.components.c4_policy_aware_safety.execution.runner import C4ExecutionRunner
from app.components.c4_policy_aware_safety.persistence.repository import C4Repository
from app.database import SessionLocal, get_db

router = APIRouter(
    prefix="/projects/{project_id}/c4/live/nexacart",
    tags=["C4 Live NexaCart"],
    dependencies=[Depends(get_authorized_c4_project)],
)

# Background execution progress (process lifetime). Each finished case is a persisted run record.
_EXECUTIONS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()


def get_c4_live_adapter_factory() -> Callable[[], NexaCartLiveC4Adapter]:
    """Adapter factory (overridden in hermetic tests)."""
    return NexaCartLiveC4Adapter


def get_c4_session_factory() -> Callable[[], Session]:
    """Session factory for background executions (overridden in hermetic tests)."""
    return SessionLocal


class LiveImportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    binding_id: str
    binding_version: int
    artifact_id: str
    artifact_version: int
    candidate_rule_ids: list[str]
    candidate_rules: list[CandidateRule]
    artifact: ArtifactVersionRecord
    suggested_contract_id: str
    next_steps: list[str]


class LiveExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_id: str = Field(..., min_length=1)
    contract_version: int = Field(..., ge=1)
    case_ids: list[str] | None = Field(
        default=None,
        description="Frozen case IDs to run; default: every frozen NexaCart case of the contract",
    )
    repetitions: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Live runs per case (the proposal uses 3); results are reported as per-case rates",
    )


@router.get("/readiness", summary="Live NexaCart readiness for C4")
def live_readiness(
    project_id: str,
    adapter_factory: Annotated[
        Callable[[], NexaCartLiveC4Adapter], Depends(get_c4_live_adapter_factory)
    ],
) -> dict[str, Any]:
    adapter = adapter_factory()
    ready, blockers = adapter.client.check_readiness()
    agent: dict[str, Any] = {}
    tools: list[dict[str, Any]] = []
    if ready:
        capabilities = adapter.client.get_capabilities()
        agent = capabilities.get("agent", {})
        tools = [
            {"name": t["name"], "is_state_changing": bool(t.get("isStateChanging"))}
            for t in capabilities.get("tools", [])
        ]
    return {
        "domain_id": NEXACART_DOMAIN_ID,
        "is_ready": ready,
        "status": "READY" if ready else "BLOCKED",
        "blockers": blockers,
        "base_url": getattr(adapter.client, "base_url", None),
        "agent": agent,
        "tools": tools,
        "adapter_id": adapter.adapter_id,
        "adapter_version": adapter.adapter_version,
    }


@router.post(
    "/import",
    response_model=LiveImportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import the NexaCart domain binding, policy document and reference candidate rules",
)
def import_nexacart_domain(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> LiveImportResponse:
    repo = C4Repository(db)

    binding = build_nexacart_binding(project_id)
    existing = repo.get_domain_binding(project_id, binding.binding_id, binding.version)
    if existing is None:
        repo.save_domain_binding(binding)

    artifact_version = 1
    artifact = repo.get_artifact_version(
        project_id, NEXACART_POLICY_ARTIFACT_ID, artifact_version
    )
    if artifact is None:
        artifact = normalize_artifact(
            project_id,
            ArtifactCreate(
                artifact_id=NEXACART_POLICY_ARTIFACT_ID,
                artifact_kind=ArtifactKind.POLICY_DOCUMENT,
                raw_content=NEXACART_POLICY_MARKDOWN,
                metadata={
                    "source": "nexacart_live_domain",
                    "grounding": "NexaCart agent system prompt, refunds.service.ts, order ownership checks",
                },
            ),
            artifact_version,
        )
        repo.save_artifact_version(artifact)

    rules = build_nexacart_reference_rules(project_id, artifact.version)
    existing_ids = {
        r.rule_id
        for r in repo.list_candidate_rules(project_id, [r.rule_id for r in rules])
    }
    for rule in rules:
        if rule.rule_id not in existing_ids:
            repo.save_candidate_rule(rule)

    return LiveImportResponse(
        binding_id=binding.binding_id,
        binding_version=binding.version,
        artifact_id=artifact.artifact_id,
        artifact_version=artifact.version,
        candidate_rule_ids=[r.rule_id for r in rules],
        candidate_rules=repo.list_candidate_rules(
            project_id, [r.rule_id for r in rules]
        ),
        artifact=artifact,
        suggested_contract_id=NEXACART_REFERENCE_CONTRACT_ID,
        next_steps=[
            "Policy Preparation: optionally run extraction on the NexaCart policy with the selected Ollama model and compare with the reference rules",
            "Contracts: create a contract from the candidate rules, validate and accept it",
            f"Test Cases: generate with binding '{binding.binding_id}' v{binding.version} (auto validate + freeze)",
            "Runs & Findings: run the frozen cases live on NexaCart",
        ],
    )


def _summary(execution: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in execution.items() if not k.startswith("_")}


@router.post(
    "/executions",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Run frozen NexaCart policy cases live in the background",
)
def start_live_execution(
    project_id: str,
    request: LiveExecutionRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    adapter_factory: Annotated[
        Callable[[], NexaCartLiveC4Adapter], Depends(get_c4_live_adapter_factory)
    ],
    session_factory: Annotated[Callable[[], Session], Depends(get_c4_session_factory)],
) -> dict[str, Any]:
    repo = C4Repository(db)
    contract = repo.get_contract_version(
        project_id, request.contract_id, request.contract_version
    )
    if contract is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Contract '{request.contract_id}' v{request.contract_version} not found.",
        )
    if contract.lifecycle_state != ContractLifecycleState.ACCEPTED:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Only ACCEPTED contracts can be executed."
        )

    frozen = [
        c
        for c in repo.list_test_cases(
            project_id, lifecycle_state=CaseLifecycleState.FROZEN.value
        )
        if c.contract_id == contract.contract_id
        and c.contract_version == contract.version
        and c.domain_id == NEXACART_DOMAIN_ID
        and not c.is_obsolete
    ]
    if request.case_ids is not None:
        wanted = set(request.case_ids)
        frozen = [c for c in frozen if c.case_id in wanted]
        missing = wanted - {c.case_id for c in frozen}
        if missing:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Frozen NexaCart cases not found: {sorted(missing)}",
            )
    if not frozen:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No frozen NexaCart cases for this contract. Generate and freeze cases first.",
        )

    adapter = adapter_factory()
    ready, blockers = adapter.client.check_readiness()
    if not ready:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"NexaCart is not ready: {'; '.join(blockers)}"
        )

    execution_id = f"c4x-{uuid.uuid4().hex[:12]}"
    execution = {
        "execution_id": execution_id,
        "project_id": project_id,
        "contract_id": contract.contract_id,
        "contract_version": contract.version,
        "binding_id": NEXACART_DOMAIN_ID,
        "status": "RUNNING",
        "total_cases": len(frozen),
        "repetitions": request.repetitions,
        "total_runs": len(frozen) * request.repetitions,
        "completed_runs": 0,
        "current_case_id": None,
        "current_repetition": None,
        "case_results": [],
        "case_rates": summarize_case_rates([]),
        "error_message": None,
        "started_at": datetime.now(UTC).isoformat(),
        "completed_at": None,
    }
    with _LOCK:
        _EXECUTIONS[execution_id] = execution
    background_tasks.add_task(
        run_live_execution,
        execution_id,
        project_id,
        [(c.case_id, c.case_version) for c in frozen],
        request.repetitions,
        adapter_factory,
        session_factory,
    )
    return _summary(execution)


def run_live_execution(
    execution_id: str,
    project_id: str,
    case_refs: list[tuple[str, int]],
    repetitions: int,
    adapter_factory: Callable[[], NexaCartLiveC4Adapter],
    session_factory: Callable[[], Session],
) -> None:
    """Run each case `repetitions` times, each run on a fresh NexaCart fixture; persist a run record per run.

    Round-robin order (all cases, then the next repetition) so the repetitions of one case are spread
    over the execution instead of sharing one period of model/server load.
    """
    execution = _EXECUTIONS[execution_id]
    db = session_factory()
    try:
        repo = C4Repository(db)
        runner = C4ExecutionRunner(repo)
        planned = [(r, ref) for r in range(1, repetitions + 1) for ref in case_refs]
        for repetition, (case_id, case_version) in planned:
            execution["current_case_id"] = case_id
            execution["current_repetition"] = repetition
            case = repo.get_test_case(project_id, case_id, case_version)
            contract = repo.get_contract_version(
                project_id, case.contract_id, case.contract_version
            )
            binding = repo.get_domain_binding(
                project_id, case.domain_id, case.binding_version
            )
            adapter = adapter_factory()
            try:
                record = runner.execute_case(case, contract, binding, adapter=adapter)
                record.evaluation_report_summary["live_execution_id"] = execution_id
                record.evaluation_report_summary["repetition"] = repetition
                repo.save_execution_run(record)
                result = {
                    "case_id": case_id,
                    "repetition": repetition,
                    "test_kind": case.test_kind.value,
                    "run_id": record.run_id,
                    "status": record.status.value,
                    "policy_verdict": record.policy_verdict,
                    "exposure_status": record.exposure_status.value,
                    "attacker_objective_outcome": record.attacker_objective_outcome.value,
                    "task_utility_outcome": record.task_utility_outcome.value,
                    "agent_run_id": (
                        record.evaluation_report_summary.get("live_nexacart") or {}
                    ).get("nexacart_agent_run_id"),
                    "rule_verdicts": {
                        f["rule_id"]: f["verdict"] for f in record.findings
                    },
                    "error_message": record.error_message,
                }
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                result = {
                    "case_id": case_id,
                    "repetition": repetition,
                    "test_kind": case.test_kind.value if case else None,
                    "status": "ERROR",
                    "policy_verdict": None,
                    "error_message": str(exc),
                }
            execution["case_results"].append(result)
            execution["completed_runs"] += 1
            execution["case_rates"] = summarize_case_rates(execution["case_results"])
        execution["status"] = "COMPLETED"
    except Exception as exc:  # noqa: BLE001
        execution["status"] = "FAILED"
        execution["error_message"] = str(exc)
    finally:
        execution["current_case_id"] = None
        execution["current_repetition"] = None
        execution["completed_at"] = datetime.now(UTC).isoformat()
        db.close()


@router.get("/executions", summary="List live NexaCart executions of this project")
def list_live_executions(project_id: str) -> list[dict[str, Any]]:
    with _LOCK:
        items = [
            _summary(e) for e in _EXECUTIONS.values() if e["project_id"] == project_id
        ]
    return sorted(items, key=lambda e: e["started_at"], reverse=True)


@router.get(
    "/executions/{execution_id}", summary="Live NexaCart execution progress and results"
)
def get_live_execution(project_id: str, execution_id: str) -> dict[str, Any]:
    execution = _EXECUTIONS.get(execution_id)
    if execution is None or execution["project_id"] != project_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Live execution '{execution_id}' not found."
        )
    return _summary(execution)
