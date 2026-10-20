import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.components.c1_tool_call_correctness.contracts.generation import (
    AgentFacingTask,
    GeneratedCandidateCase,
    GenerationRequest,
)
from app.components.c1_tool_call_correctness.contracts.validation import (
    ValidationSeverity,
)
from app.components.c1_tool_call_correctness.models.persistence import (
    C1GenerationRunModel,
    C1ProjectConfigModel,
    C1SuiteVersionModel,
)
from app.components.c1_tool_call_correctness.services.candidate_validator import (
    validate_candidate_case,
)
from app.components.c1_tool_call_correctness.services.config_service import (
    ConfigNotFoundError,
)
from app.components.c1_tool_call_correctness.services.generator_engine import (
    DeterministicCandidateGenerator,
)
from app.components.c1_tool_call_correctness.services.suite_selector import (
    SuiteSelector,
    extract_agent_facing_task,
)


def get_generation_run(
    db: Session, project_id: str, run_id: str
) -> C1GenerationRunModel | None:
    """Retrieves a single generation run scoped strictly by project_id and run_id."""
    stmt = select(C1GenerationRunModel).where(
        C1GenerationRunModel.id == run_id, C1GenerationRunModel.project_id == project_id
    )
    return db.execute(stmt).scalar_one_or_none()


def list_generation_runs(db: Session, project_id: str) -> list[C1GenerationRunModel]:
    """Lists all generation runs scoped strictly to the specified project."""
    stmt = (
        select(C1GenerationRunModel)
        .where(C1GenerationRunModel.project_id == project_id)
        .order_by(C1GenerationRunModel.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def execute_generation_job(
    db: Session, project_id: str, request: GenerationRequest
) -> tuple[
    C1GenerationRunModel,
    list[GeneratedCandidateCase],
    list[AgentFacingTask],
    C1SuiteVersionModel | None,
]:
    """Orchestrates candidate generation, validation, deduplication, selection, and persistence.
    Verifies input limits and references, validates candidates, and excludes invalid/ambiguous cases.
    """
    # 1. Fetch targeted project configuration
    stmt = select(C1ProjectConfigModel).where(
        C1ProjectConfigModel.project_id == project_id,
        C1ProjectConfigModel.version == request.config_version,
    )
    config = db.execute(stmt).scalar_one_or_none()
    if not config:
        raise ConfigNotFoundError(
            f"Configuration version {request.config_version} not found for project '{project_id}'."
        )

    # 2. Validate request limits and reject unresolved references
    if request.max_accepted_cases > request.max_candidates:
        raise ValueError(
            f"max_accepted_cases ({request.max_accepted_cases}) cannot exceed "
            f"max_candidates ({request.max_candidates})."
        )

    declared_req_ids = {
        r.get("req_id") for r in (config.requirements or []) if isinstance(r, dict)
    }
    if request.requirement_ids:
        unresolved_reqs = set(request.requirement_ids) - declared_req_ids
        if unresolved_reqs:
            raise ValueError(
                f"Unresolved requirement references in generation request: {sorted(unresolved_reqs)}"
            )

    declared_tool_names = {
        t.get("name") for t in (config.tools or []) if isinstance(t, dict)
    }
    if request.tool_names:
        unresolved_tools = set(request.tool_names) - declared_tool_names
        if unresolved_tools:
            raise ValueError(
                f"Unresolved tool references in generation request: {sorted(unresolved_tools)}"
            )

    # 3. Generate raw candidates
    generator = DeterministicCandidateGenerator(config, request)
    raw_candidates = generator.generate_all_candidates()

    # 4. Perform deep candidate validation
    for candidate in raw_candidates:
        issues = validate_candidate_case(candidate, config)
        candidate.validation_issues = issues
        has_errors = any(i.severity == ValidationSeverity.ERROR for i in issues)
        candidate.is_valid = not has_errors
        if has_errors and not candidate.rejection_reason:
            err_msg = issues[0].message if issues else "Validation error"
            candidate.rejection_reason = f"Candidate validation failed: {err_msg}"

    # 5. Deduplicate and select bounded reproducible suite
    selector = SuiteSelector(max_accepted_cases=request.max_accepted_cases)
    selected_cases, processed_all, summary, content_hash = selector.process_and_select(
        raw_candidates
    )

    run_id = str(uuid.uuid4())
    suite_model: C1SuiteVersionModel | None = None

    # 6. Optional auto-promotion to accepted suite
    if request.auto_promote_suite and selected_cases:
        suite_id = (
            request.suite_id or f"suite_{project_id}_auto_{request.config_version}"
        )
        suite_name = (
            request.suite_name
            or f"Auto-Generated Suite for Config v{request.config_version}"
        )

        # Fetch latest version for this suite_id
        suite_stmt = (
            select(C1SuiteVersionModel)
            .where(
                C1SuiteVersionModel.project_id == project_id,
                C1SuiteVersionModel.suite_id == suite_id,
            )
            .order_by(C1SuiteVersionModel.version.desc())
        )
        latest_suite = db.execute(suite_stmt).scalars().first()
        next_ver = (latest_suite.version + 1) if latest_suite else 1

        suite_model = C1SuiteVersionModel(
            id=str(uuid.uuid4()),
            project_id=project_id,
            suite_id=suite_id,
            version=next_ver,
            name=suite_name,
            config_id=config.id,
            is_immutable=True,
            cases=[c.model_dump(mode="json") for c in selected_cases],
            content_hash=content_hash,
            generation_run_id=run_id,
            created_at=datetime.now(UTC),
        )
        db.add(suite_model)

        # Freeze config
        config.is_immutable = True
        config.updated_at = datetime.now(UTC)

    # 7. Persist generation run record
    run_record = C1GenerationRunModel(
        id=run_id,
        project_id=project_id,
        config_id=config.id,
        status="COMPLETED",
        request_payload=request.model_dump(mode="json"),
        summary=summary.model_dump(mode="json"),
        candidates=[c.model_dump(mode="json") for c in processed_all],
        content_hash=content_hash,
        suite_id=request.suite_id if request.auto_promote_suite else None,
        suite_version_id=suite_model.id if suite_model else None,
        error_message=None,
        created_at=datetime.now(UTC),
    )
    db.add(run_record)
    db.commit()
    db.refresh(run_record)

    # 8. Extract isolated agent-facing tasks
    agent_tasks = [extract_agent_facing_task(c) for c in selected_cases]

    return run_record, selected_cases, agent_tasks, suite_model
