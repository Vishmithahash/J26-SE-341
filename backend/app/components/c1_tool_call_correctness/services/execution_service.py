import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.components.c1_tool_call_correctness.contracts.execution import (
    CapturedToolEvent,
    CaseExecutionDetail,
    ExecutionReasonCode,
    ExecutionRequest,
    RunDetailResponse,
    RunSummary,
    TraceCompleteness,
)
from app.components.c1_tool_call_correctness.contracts.generation import (
    AgentFacingTask,
    ExpectedToolCallSpec,
    FixturePreparationPlan,
)
from app.components.c1_tool_call_correctness.contracts.lifecycle import (
    EvidenceRef,
    RunStatus,
)
from app.components.c1_tool_call_correctness.contracts.results import (
    CaseExecutionStatus,
    CaseReadinessStatus,
    CheckLevelResult,
    CorrectnessVerdict,
)
from app.components.c1_tool_call_correctness.models.persistence import (
    C1CaseExecutionModel,
    C1ExecutionRunModel,
    C1ProjectConfigModel,
    C1SuiteVersionModel,
)
from app.components.c1_tool_call_correctness.services.agent_adapter import (
    AgentExecutionAdapter,
    FakeAgentAdapter,
    LiveAgentAdapter,
)
from app.components.c1_tool_call_correctness.services.correctness_evaluator import (
    DeterministicCorrectnessEvaluator,
)
from app.components.c1_tool_call_correctness.services.fixture_service import (
    SyntheticFixtureService,
)


class ExecutionService:
    """Orchestrates test run preparation, fixture isolation, agent execution,
    trace capture, correctness evaluation, and persistent reporting.
    """

    def __init__(self) -> None:
        self.fixture_service = SyntheticFixtureService()
        self.evaluator = DeterministicCorrectnessEvaluator()

    def get_adapter(
        self,
        config: C1ProjectConfigModel,
        request: ExecutionRequest,
    ) -> AgentExecutionAdapter:
        """Resolves the appropriate adapter based on request override and configuration."""
        if request.adapter_override:
            # Format: e.g. "SIMULATED:WRONG_TOOL" or "WRONG_TOOL"
            mode = request.adapter_override.replace("SIMULATED:", "").strip()
            return FakeAgentAdapter(mode=mode)

        conn_ref = config.agent_connection_ref
        if conn_ref.startswith("urn:conn:mock"):
            # Default mock connection uses clean AUTO simulated fake adapter
            return FakeAgentAdapter(mode="AUTO")

        return LiveAgentAdapter(connection_ref=conn_ref)

    def create_and_start_run(
        self,
        db: Session,
        project_id: str,
        request: ExecutionRequest,
        adapter: AgentExecutionAdapter | None = None,
    ) -> C1ExecutionRunModel:
        """Prepares and executes a test suite run, recording attempts and case evaluations."""
        # 1. Idempotency Check: prevent duplicate submissions from triggering duplicate executions
        if request.idempotency_key:
            stmt = select(C1ExecutionRunModel).where(
                C1ExecutionRunModel.project_id == project_id,
                C1ExecutionRunModel.idempotency_key == request.idempotency_key,
            )
            existing_run = db.execute(stmt).scalars().first()
            if existing_run:
                return existing_run

        # 2. Retrieve Suite Version
        suite_stmt = select(C1SuiteVersionModel).where(
            C1SuiteVersionModel.project_id == project_id,
            C1SuiteVersionModel.suite_id == request.suite_id,
        )
        if request.suite_version is not None:
            suite_stmt = suite_stmt.where(
                C1SuiteVersionModel.version == request.suite_version
            )
        else:
            suite_stmt = suite_stmt.order_by(desc(C1SuiteVersionModel.version))

        suite_version_model = db.execute(suite_stmt).scalars().first()
        if not suite_version_model:
            raise ValueError(
                f"Suite '{request.suite_id}' (version {request.suite_version}) not found for project '{project_id}'."
            )

        # 3. Retrieve Config Snapshot
        config = (
            db.execute(
                select(C1ProjectConfigModel).where(
                    C1ProjectConfigModel.id == suite_version_model.config_id
                )
            )
            .scalars()
            .first()
        )
        if not config:
            raise ValueError(
                f"Referenced configuration '{suite_version_model.config_id}' not found."
            )

        # 4. Resolve Adapter & Validate Readiness
        if adapter is None:
            adapter = self.get_adapter(config, request)

        is_ready, not_ready_reason = adapter.check_readiness()

        # 5. Freeze Effective Configuration
        effective_config = {
            "requirement_version": f"cfg_v{config.version}",
            "fixture_capabilities": config.synthetic_fixture_refs,
            "tool_schemas": [t.get("name") for t in config.tools],
            "evaluator_version": request.evaluator_version,
            "code_version": request.code_version,
            "deadline_seconds": request.deadline_seconds,
            "adapter_type": getattr(adapter, "ADAPTER_TYPE", "UNKNOWN"),
            "suite_content_hash": suite_version_model.content_hash,
        }

        # 6. Initialize Execution Run Record
        run_id = f"run_{uuid.uuid4()}"
        initial_status = RunStatus.RUNNING.value if is_ready else RunStatus.FAILED.value
        run_model = C1ExecutionRunModel(
            id=run_id,
            project_id=project_id,
            suite_id=suite_version_model.suite_id,
            suite_version=suite_version_model.version,
            suite_version_id=suite_version_model.id,
            config_id=config.id,
            status=initial_status,
            idempotency_key=request.idempotency_key,
            effective_config=effective_config,
            summary={
                "total_cases": len(suite_version_model.cases),
                "passed_cases": 0,
                "failed_cases": 0,
                "inconclusive_cases": 0,
                "error_cases": 0,
            },
            error_message=not_ready_reason if not is_ready else None,
            started_at=datetime.now(UTC),
        )
        db.add(run_model)
        db.commit()
        db.refresh(run_model)

        if not is_ready:
            return run_model

        # 7. Execute Accepted Cases
        self._execute_cases(
            db=db,
            run_model=run_model,
            cases=suite_version_model.cases,
            adapter=adapter,
            deadline_seconds=request.deadline_seconds,
            attempt_number=1,
            tools=config.tools,
            tool_constraints=config.tool_constraints,
        )

        db.refresh(run_model)
        return run_model

    def rerun_execution(
        self,
        db: Session,
        project_id: str,
        run_id: str,
        adapter: AgentExecutionAdapter | None = None,
    ) -> C1ExecutionRunModel:
        """Creates a new execution attempt for a run without overwriting previous attempt history."""
        run_model = (
            db.execute(
                select(C1ExecutionRunModel).where(
                    C1ExecutionRunModel.project_id == project_id,
                    C1ExecutionRunModel.id == run_id,
                )
            )
            .scalars()
            .first()
        )
        if not run_model:
            raise ValueError(
                f"Execution run '{run_id}' not found for project '{project_id}'."
            )

        # Get current highest attempt number
        attempt_stmt = select(C1CaseExecutionModel.attempt_number).where(
            C1CaseExecutionModel.run_id == run_id
        )
        existing_attempts = db.execute(attempt_stmt).scalars().all()
        next_attempt = (max(existing_attempts) + 1) if existing_attempts else 1

        suite_version_model = (
            db.execute(
                select(C1SuiteVersionModel).where(
                    C1SuiteVersionModel.id == run_model.suite_version_id
                )
            )
            .scalars()
            .first()
        )
        config = (
            db.execute(
                select(C1ProjectConfigModel).where(
                    C1ProjectConfigModel.id == run_model.config_id
                )
            )
            .scalars()
            .first()
        )
        if not suite_version_model or not config:
            raise ValueError("Referenced suite or config not found for rerun.")

        if adapter is None:
            adapter = FakeAgentAdapter(mode="AUTO")

        run_model.status = RunStatus.RUNNING.value
        db.commit()

        self._execute_cases(
            db=db,
            run_model=run_model,
            cases=suite_version_model.cases,
            adapter=adapter,
            deadline_seconds=run_model.effective_config.get("deadline_seconds", 60),
            attempt_number=next_attempt,
            tools=config.tools,
            tool_constraints=config.tool_constraints,
        )

        db.refresh(run_model)
        return run_model

    def cancel_run(
        self, db: Session, project_id: str, run_id: str
    ) -> C1ExecutionRunModel:
        """Cancels an active execution run."""
        run_model = (
            db.execute(
                select(C1ExecutionRunModel).where(
                    C1ExecutionRunModel.project_id == project_id,
                    C1ExecutionRunModel.id == run_id,
                )
            )
            .scalars()
            .first()
        )
        if not run_model:
            raise ValueError(
                f"Execution run '{run_id}' not found for project '{project_id}'."
            )
        if run_model.status in (RunStatus.RUNNING.value, RunStatus.PENDING.value):
            run_model.status = RunStatus.ABORTED.value
            run_model.completed_at = datetime.now(UTC)
            run_model.error_message = "Execution cancelled by user request."
            db.commit()
            db.refresh(run_model)
        return run_model

    def _execute_cases(
        self,
        db: Session,
        run_model: C1ExecutionRunModel,
        cases: list[dict[str, Any]],
        adapter: AgentExecutionAdapter,
        deadline_seconds: int,
        attempt_number: int,
        tools: list[dict[str, Any]],
        tool_constraints: dict[str, Any],
    ) -> None:
        """Executes test cases with fixture reset and fresh agent sessions per case."""
        passed_cases = 0
        failed_cases = 0
        inconclusive_cases = 0
        error_cases = 0

        all_tool_names = [t.get("name") for t in tools if t.get("name")]

        for case_dict in cases:
            # Check for cancellation between cases
            db.refresh(run_model)
            if run_model.status == RunStatus.ABORTED.value:
                break

            case_id = case_dict.get("case_id", f"case_{str(uuid.uuid4())[:8]}")
            category = case_dict.get("category", "CORRECT_BEHAVIOUR")
            is_valid = case_dict.get("is_valid", True)
            rejection_reason = case_dict.get("rejection_reason")

            # 1. Candidate readiness check
            if not is_valid or rejection_reason:
                # Do not score rejected, ambiguous, or unresolved candidate cases!
                case_exec = C1CaseExecutionModel(
                    id=f"cexec_{uuid.uuid4()}",
                    run_id=run_model.id,
                    case_id=case_id,
                    attempt_number=attempt_number,
                    session_id=f"sess_unconfigured_{str(uuid.uuid4())[:8]}",
                    readiness_status=CaseReadinessStatus.INVALID_SPEC.value,
                    execution_status=CaseExecutionStatus.NOT_EXECUTED.value,
                    verdict=None,
                    trace_completeness=TraceCompleteness.MISSING.value,
                    resolved_expectations=[],
                    agent_task_sent=None,
                    captured_events=[],
                    evidence_records=[],
                    raw_trace={},
                    check_results=[],
                    error_message=f"Case excluded from scoring: {rejection_reason or 'Validation error'}",
                    completed_at=datetime.now(UTC),
                )
                db.add(case_exec)
                db.commit()
                continue

            session_id = f"sess_{str(uuid.uuid4())[:8]}_{case_id[:8]}"

            # 2. Parse Fixture Plan and prepare isolated synthetic fixture
            fixture_plan_dict = case_dict.get("fixture_plan", {})
            try:
                fixture_plan = FixturePreparationPlan.model_validate(fixture_plan_dict)
                fix_ok, session_data, fix_evidence = (
                    self.fixture_service.prepare_fixture(session_id, fixture_plan)
                )
            except (ValueError, KeyError, TypeError, AttributeError):
                fix_ok, session_data, fix_evidence = (
                    False,
                    {},
                    [],
                )

            if not fix_ok:
                case_exec = C1CaseExecutionModel(
                    id=f"cexec_{uuid.uuid4()}",
                    run_id=run_model.id,
                    case_id=case_id,
                    attempt_number=attempt_number,
                    session_id=session_id,
                    readiness_status=CaseReadinessStatus.CONFIGURED.value,
                    execution_status=CaseExecutionStatus.EXECUTION_ERROR.value,
                    verdict=None,
                    trace_completeness=TraceCompleteness.MISSING.value,
                    resolved_expectations=[],
                    agent_task_sent=None,
                    captured_events=[],
                    evidence_records=[],
                    raw_trace={},
                    check_results=[],
                    error_message="Fixture preparation failed.",
                    completed_at=datetime.now(UTC),
                )
                db.add(case_exec)
                db.commit()
                error_cases += 1
                continue

            # 3. Resolve Fixture-Dependent Expected Values
            raw_specs = case_dict.get("expected_tool_calls", [])
            expectations = [ExpectedToolCallSpec.model_validate(s) for s in raw_specs]
            resolved_expectations = self.fixture_service.resolve_expectation_values(
                expectations, session_data
            )

            # 4. Prepare Agent-Facing Task (Strictly isolated from QA expectations)
            permitted_tools = [
                s.tool_name for s in resolved_expectations if not s.is_forbidden
            ] or all_tool_names

            agent_task = AgentFacingTask(
                case_id=case_id,
                task_prompt=case_dict.get("agent_task_prompt", ""),
                context_inputs=case_dict.get("task_context_inputs", {}),
                permitted_tools=permitted_tools,
            )

            # 5. Invoke Agent through Adapter
            adapter_res = adapter.execute_task(
                session_id=session_id,
                task=agent_task,
                deadline_seconds=deadline_seconds,
            )

            # 6. Evaluate Correctness
            evidence_records = fix_evidence + [
                ref for ev in adapter_res.events for ref in ev.evidence_refs
            ]

            if adapter_res.execution_status == CaseExecutionStatus.EXECUTION_ERROR:
                # Infrastructure errors must not be reported as agent mistakes
                verdict = CorrectnessVerdict.INCONCLUSIVE
                check = CheckLevelResult(
                    check_id=f"chk_infra_error_{case_id[:8]}",
                    rule_name="EXECUTION_INFRASTRUCTURE_HEALTH",
                    verdict=CorrectnessVerdict.INCONCLUSIVE,
                    reason_code=ExecutionReasonCode.ADAPTER_ERROR.value,
                    explanation=(
                        f"Execution failed due to adapter/system error: {adapter_res.error_message}. "
                        "Infrastructure error kept distinct from agent correctness."
                    ),
                )
                check_results = [check]
                error_cases += 1
            else:
                verdict, check_results = self.evaluator.evaluate_case(
                    case_id=case_id,
                    category=category,
                    resolved_expectations=resolved_expectations,
                    captured_events=adapter_res.events,
                    trace_completeness=adapter_res.trace_completeness,
                    context_data=session_data,
                    requirement_refs=case_dict.get("requirement_refs", []),
                    tool_constraints=tool_constraints,
                )
                if verdict == CorrectnessVerdict.PASS:
                    passed_cases += 1
                elif verdict == CorrectnessVerdict.FAIL:
                    failed_cases += 1
                else:
                    inconclusive_cases += 1

            # 7. Persist Case Execution Record
            case_exec = C1CaseExecutionModel(
                id=f"cexec_{uuid.uuid4()}",
                run_id=run_model.id,
                case_id=case_id,
                attempt_number=attempt_number,
                session_id=session_id,
                readiness_status=CaseReadinessStatus.CONFIGURED.value,
                execution_status=adapter_res.execution_status.value,
                verdict=verdict.value,
                trace_completeness=adapter_res.trace_completeness.value,
                resolved_expectations=[
                    s.model_dump(mode="json") for s in resolved_expectations
                ],
                agent_task_sent=agent_task.model_dump(mode="json"),
                captured_events=[e.model_dump(mode="json") for e in adapter_res.events],
                evidence_records=[r.model_dump(mode="json") for r in evidence_records],
                raw_trace=adapter_res.raw_trace,
                check_results=[c.model_dump(mode="json") for c in check_results],
                error_message=adapter_res.error_message,
                completed_at=datetime.now(UTC),
            )
            db.add(case_exec)
            db.commit()

            # 8. Reset Synthetic Fixture Session
            self.fixture_service.reset_session(session_id)

        # 9. Update Run Model Summary
        run_model.summary = {
            "total_cases": len(cases),
            "passed_cases": passed_cases,
            "failed_cases": failed_cases,
            "inconclusive_cases": inconclusive_cases,
            "error_cases": error_cases,
        }
        if run_model.status != RunStatus.ABORTED.value:
            run_model.status = RunStatus.COMPLETED.value
        run_model.completed_at = datetime.now(UTC)
        db.commit()

    def get_run_detail(
        self,
        db: Session,
        project_id: str,
        run_id: str,
    ) -> RunDetailResponse | None:
        """Retrieves full execution run details and case executions."""
        run_model = (
            db.execute(
                select(C1ExecutionRunModel).where(
                    C1ExecutionRunModel.project_id == project_id,
                    C1ExecutionRunModel.id == run_id,
                )
            )
            .scalars()
            .first()
        )
        if not run_model:
            return None

        # Fetch case executions (latest attempt for each case)
        case_models = (
            db.execute(
                select(C1CaseExecutionModel)
                .where(C1CaseExecutionModel.run_id == run_id)
                .order_by(
                    C1CaseExecutionModel.case_id,
                    desc(C1CaseExecutionModel.attempt_number),
                )
            )
            .scalars()
            .all()
        )

        # Keep only the latest attempt for each case_id
        seen_cases: set[str] = set()
        case_details: list[CaseExecutionDetail] = []
        for cm in case_models:
            if cm.case_id in seen_cases:
                continue
            seen_cases.add(cm.case_id)

            resolved_specs = [
                ExpectedToolCallSpec.model_validate(s)
                for s in (cm.resolved_expectations or [])
            ]
            agent_task = (
                AgentFacingTask.model_validate(cm.agent_task_sent)
                if cm.agent_task_sent
                else None
            )
            captured_events = [
                CapturedToolEvent.model_validate(e) for e in (cm.captured_events or [])
            ]
            evidence_records = [
                cm.evidence_records and r for r in (cm.evidence_records or [])
            ]
            check_results = [
                CheckLevelResult.model_validate(c) for c in (cm.check_results or [])
            ]

            case_details.append(
                CaseExecutionDetail(
                    execution_id=cm.id,
                    case_id=cm.case_id,
                    attempt_number=cm.attempt_number,
                    session_id=cm.session_id,
                    readiness_status=CaseReadinessStatus(cm.readiness_status),
                    execution_status=CaseExecutionStatus(cm.execution_status),
                    verdict=CorrectnessVerdict(cm.verdict) if cm.verdict else None,
                    trace_completeness=TraceCompleteness(cm.trace_completeness),
                    resolved_expectations=resolved_specs,
                    agent_task_sent=agent_task,
                    captured_events=captured_events,
                    evidence_records=[
                        r for r in evidence_records if isinstance(r, dict)
                    ],
                    raw_trace=cm.raw_trace or {},
                    check_results=check_results,
                    error_message=cm.error_message,
                    created_at=cm.created_at,
                    completed_at=cm.completed_at,
                )
            )

        summary = RunSummary(
            run_id=run_model.id,
            project_id=run_model.project_id,
            suite_id=run_model.suite_id,
            suite_version=run_model.suite_version,
            status=RunStatus(run_model.status),
            total_cases=run_model.summary.get("total_cases", 0),
            passed_cases=run_model.summary.get("passed_cases", 0),
            failed_cases=run_model.summary.get("failed_cases", 0),
            inconclusive_cases=run_model.summary.get("inconclusive_cases", 0),
            error_cases=run_model.summary.get("error_cases", 0),
            created_at=run_model.created_at,
            started_at=run_model.started_at,
            completed_at=run_model.completed_at,
        )

        return RunDetailResponse(
            summary=summary,
            effective_config=run_model.effective_config,
            case_executions=case_details,
        )

    def list_runs(
        self,
        db: Session,
        project_id: str,
        verdict: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RunSummary]:
        """Lists runs for a project, optionally filtering by verdict."""
        stmt = (
            select(C1ExecutionRunModel)
            .where(C1ExecutionRunModel.project_id == project_id)
            .order_by(desc(C1ExecutionRunModel.created_at))
            .limit(limit)
            .offset(offset)
        )
        runs = db.execute(stmt).scalars().all()

        results = []
        for r in runs:
            # If verdict filter provided, check if run has cases matching verdict
            if verdict:
                v_key = f"{verdict.lower()}_cases"
                if r.summary.get(v_key, 0) == 0:
                    continue

            results.append(
                RunSummary(
                    run_id=r.id,
                    project_id=r.project_id,
                    suite_id=r.suite_id,
                    suite_version=r.suite_version,
                    status=RunStatus(r.status),
                    total_cases=r.summary.get("total_cases", 0),
                    passed_cases=r.summary.get("passed_cases", 0),
                    failed_cases=r.summary.get("failed_cases", 0),
                    inconclusive_cases=r.summary.get("inconclusive_cases", 0),
                    error_cases=r.summary.get("error_cases", 0),
                    created_at=r.created_at,
                    started_at=r.started_at,
                    completed_at=r.completed_at,
                )
            )
        return results

    def get_case_execution_detail(
        self,
        db: Session,
        project_id: str,
        run_id: str,
        case_id: str,
    ) -> CaseExecutionDetail | None:
        """Retrieves detailed case execution record including check-level results and raw trace."""
        # Ensure run belongs to project
        run_model = (
            db.execute(
                select(C1ExecutionRunModel).where(
                    C1ExecutionRunModel.project_id == project_id,
                    C1ExecutionRunModel.id == run_id,
                )
            )
            .scalars()
            .first()
        )
        if not run_model:
            return None

        cm = (
            db.execute(
                select(C1CaseExecutionModel)
                .where(
                    C1CaseExecutionModel.run_id == run_id,
                    C1CaseExecutionModel.case_id == case_id,
                )
                .order_by(desc(C1CaseExecutionModel.attempt_number))
            )
            .scalars()
            .first()
        )
        if not cm:
            return None

        resolved_specs = [
            ExpectedToolCallSpec.model_validate(s)
            for s in (cm.resolved_expectations or [])
        ]
        agent_task = (
            AgentFacingTask.model_validate(cm.agent_task_sent)
            if cm.agent_task_sent
            else None
        )
        captured_events = [
            CapturedToolEvent.model_validate(e) for e in (cm.captured_events or [])
        ]
        check_results = [
            CheckLevelResult.model_validate(c) for c in (cm.check_results or [])
        ]

        return CaseExecutionDetail(
            execution_id=cm.id,
            case_id=cm.case_id,
            attempt_number=cm.attempt_number,
            session_id=cm.session_id,
            readiness_status=CaseReadinessStatus(cm.readiness_status),
            execution_status=CaseExecutionStatus(cm.execution_status),
            verdict=CorrectnessVerdict(cm.verdict) if cm.verdict else None,
            trace_completeness=TraceCompleteness(cm.trace_completeness),
            resolved_expectations=resolved_specs,
            agent_task_sent=agent_task,
            captured_events=captured_events,
            evidence_records=[
                EvidenceRef.model_validate(r) for r in (cm.evidence_records or [])
            ],
            raw_trace=cm.raw_trace or {},
            check_results=check_results,
            error_message=cm.error_message,
            created_at=cm.created_at,
            completed_at=cm.completed_at,
        )
