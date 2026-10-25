import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.components.c1_tool_call_correctness.contracts.execution import (
    AdapterExecutionResult,
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
from app.components.c1_tool_call_correctness.examples.nexacart_live import (
    is_nexacart_connection,
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

logger = logging.getLogger(__name__)


def run_execution_provenance(raw_traces: list[dict[str, Any] | None]) -> str | None:
    """Run provenance corroborated by recorded case traces (never by the requested mode alone).

    LIVE_EXECUTION needs a NexaCart agent run id on a non-simulated live trace; a simulated or
    fake-adapter trace makes the run SYNTHETIC_DEMO. ``None`` when no trace corroborates either.
    """
    provenance = None
    for trace in raw_traces:
        trace = trace or {}
        adapter = str(trace.get("adapter") or "").upper()
        if trace.get("simulated") is True or "FAKE" in adapter or "SIMULATED" in adapter:
            return "SYNTHETIC_DEMO"
        if (
            adapter == "NEXACART_LIVE_AGENT_ADAPTER"
            and trace.get("is_live_execution") is True
            and trace.get("agent_run_id")
        ):
            provenance = "LIVE_EXECUTION"
    return provenance


def nexacart_adapter_for_connection(
    conn_ref: str, live_adapter_factory: Any | None = None
) -> AgentExecutionAdapter:
    """Live adapter for the NexaCart instance a configuration names (local instances only).

    ``live_adapter_factory(base_url | None)`` builds the adapter (overridden in hermetic tests);
    ``None`` means the configured default NexaCart instance.
    """
    from app.components.c1_tool_call_correctness.examples.nexacart_live import (
        base_url_from_connection_ref,
    )
    from app.components.c1_tool_call_correctness.services.nexacart_correction import (
        host_is_local,
    )
    from app.components.c1_tool_call_correctness.services.nexacart_live_adapter import (
        NexaCartLiveAgentAdapter,
    )
    from app.config import get_settings

    base_url = base_url_from_connection_ref(conn_ref)
    default = get_settings().nexacart_base_url.rstrip("/")
    if base_url.rstrip("/") == default:
        return (
            live_adapter_factory(None)
            if live_adapter_factory
            else NexaCartLiveAgentAdapter()
        )
    if not host_is_local(base_url):
        # Other hosts are never contacted with the QA admin credentials (stays not ready).
        return LiveAgentAdapter(connection_ref=conn_ref)
    if live_adapter_factory:
        return live_adapter_factory(base_url)
    return NexaCartLiveAgentAdapter.for_base_url(base_url)


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
        live_adapter_factory: Any | None = None,
    ) -> AgentExecutionAdapter:
        """Resolves the appropriate adapter based on request override and configuration."""
        if request.adapter_override:
            # Format: e.g. "SIMULATED:WRONG_TOOL" or "WRONG_TOOL"
            mode = request.adapter_override.replace("SIMULATED:", "").strip()
            return FakeAgentAdapter(mode=mode)

        conn_ref = config.agent_connection_ref
        if conn_ref.startswith(("urn:conn:mock", "simulated:")):
            # Default mock or simulated connection uses clean AUTO simulated fake adapter
            return FakeAgentAdapter(mode="AUTO")

        if is_nexacart_connection(conn_ref):
            return nexacart_adapter_for_connection(conn_ref, live_adapter_factory)

        return LiveAgentAdapter(connection_ref=conn_ref)

    @staticmethod
    def is_live_adapter(adapter: AgentExecutionAdapter) -> bool:
        """Live adapters run real agent sessions (minutes per case) and are run in the background."""
        return hasattr(adapter, "fixture_service")

    def create_and_start_run(
        self,
        db: Session,
        project_id: str,
        request: ExecutionRequest,
        adapter: AgentExecutionAdapter | None = None,
    ) -> C1ExecutionRunModel:
        """Prepares and executes a test suite run, recording attempts and case evaluations."""
        run_model, adapter, is_ready = self.prepare_run(
            db, project_id, request, adapter
        )
        if is_ready and run_model.status == RunStatus.RUNNING.value:
            self.execute_prepared_run(db, run_model.id, adapter)
            db.refresh(run_model)
        return run_model

    def prepare_run(
        self,
        db: Session,
        project_id: str,
        request: ExecutionRequest,
        adapter: AgentExecutionAdapter | None = None,
        live_adapter_factory: Any | None = None,
    ) -> tuple[C1ExecutionRunModel, AgentExecutionAdapter, bool]:
        """Freezes the suite and configuration and records the run (RUNNING when ready).

        Returns (run, adapter, is_ready). A run that already existed for the idempotency key is
        returned with is_ready False so it is never executed twice.
        """
        # 1. Idempotency Check: prevent duplicate submissions from triggering duplicate executions
        if request.idempotency_key:
            stmt = select(C1ExecutionRunModel).where(
                C1ExecutionRunModel.project_id == project_id,
                C1ExecutionRunModel.idempotency_key == request.idempotency_key,
            )
            existing_run = db.execute(stmt).scalars().first()
            if existing_run:
                return existing_run, adapter or FakeAgentAdapter(mode="AUTO"), False

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
            adapter = self.get_adapter(config, request, live_adapter_factory)

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
            "adapter_override": request.adapter_override,
            "agent_connection_ref": config.agent_connection_ref,
            "suite_content_hash": suite_version_model.content_hash,
            "repetitions": request.repetitions,
        }
        if is_ready and hasattr(adapter, "describe"):
            effective_config["execution_target"] = adapter.describe()

        # 6. Initialize Execution Run Record
        run_id = f"run_{uuid.uuid4().hex}"  # 36 chars: fits the varchar(36) key
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
                "total_cases": len(suite_version_model.cases) * request.repetitions,
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
        return run_model, adapter, is_ready

    def execute_prepared_run(
        self,
        db: Session,
        run_id: str,
        adapter: AgentExecutionAdapter,
        attempt_number: int = 1,
    ) -> None:
        """Executes the accepted cases of a prepared run (synchronously or as a background job)."""
        run_model = db.get(C1ExecutionRunModel, run_id)
        if run_model is None:
            return
        suite_version_model = db.get(C1SuiteVersionModel, run_model.suite_version_id)
        config = db.get(C1ProjectConfigModel, run_model.config_id)
        if suite_version_model is None or config is None:
            run_model.status = RunStatus.FAILED.value
            run_model.error_message = "Referenced suite or configuration not found."
            run_model.completed_at = datetime.now(UTC)
            db.commit()
            return
        try:
            self._execute_cases(
                db=db,
                run_model=run_model,
                cases=suite_version_model.cases,
                adapter=adapter,
                deadline_seconds=run_model.effective_config.get("deadline_seconds", 60),
                attempt_number=attempt_number,
                tools=config.tools,
                tool_constraints=config.tool_constraints,
                repetitions=int(run_model.effective_config.get("repetitions", 1) or 1),
            )
        except Exception as exc:  # noqa: BLE001
            # A crashed run must never look completed or successful.
            db.rollback()
            run_model = db.get(C1ExecutionRunModel, run_id)
            if run_model is not None:
                run_model.status = RunStatus.FAILED.value
                run_model.error_message = (
                    f"Execution stopped by an internal error: {exc}"
                )
                run_model.completed_at = datetime.now(UTC)
                db.commit()

    def run_prepared_in_background(
        self,
        session_factory: Any,
        run_id: str,
        adapter: AgentExecutionAdapter,
        attempt_number: int = 1,
    ) -> None:
        """Background job entry point with its own database session."""
        db = session_factory()
        try:
            self.execute_prepared_run(db, run_id, adapter, attempt_number)
        finally:
            db.close()

    def rerun_execution(
        self,
        db: Session,
        project_id: str,
        run_id: str,
        adapter: AgentExecutionAdapter | None = None,
    ) -> C1ExecutionRunModel:
        """Creates a new execution attempt for a run without overwriting previous attempt history."""
        run_model, adapter, is_ready = self.prepare_rerun(
            db, project_id, run_id, adapter
        )
        if is_ready:
            self.execute_prepared_run(
                db, run_model.id, adapter, self.next_attempt_number(db, run_model.id)
            )
            db.refresh(run_model)
        return run_model

    @staticmethod
    def next_attempt_number(db: Session, run_id: str) -> int:
        attempts = (
            db.execute(
                select(C1CaseExecutionModel.attempt_number).where(
                    C1CaseExecutionModel.run_id == run_id
                )
            )
            .scalars()
            .all()
        )
        return (max(attempts) + 1) if attempts else 1

    def prepare_rerun(
        self,
        db: Session,
        project_id: str,
        run_id: str,
        adapter: AgentExecutionAdapter | None = None,
        live_adapter_factory: Any | None = None,
    ) -> tuple[C1ExecutionRunModel, AgentExecutionAdapter, bool]:
        """Marks a run RUNNING for a new attempt with the SAME kind of adapter it was started with.

        A live run is never silently re-executed with the simulated adapter.
        """
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
        config = db.get(C1ProjectConfigModel, run_model.config_id)
        if (
            config is None
            or db.get(C1SuiteVersionModel, run_model.suite_version_id) is None
        ):
            raise ValueError("Referenced suite or config not found for rerun.")

        if adapter is None:
            adapter = self.get_adapter(
                config,
                ExecutionRequest(
                    suite_id=run_model.suite_id,
                    adapter_override=(run_model.effective_config or {}).get(
                        "adapter_override"
                    ),
                ),
                live_adapter_factory,
            )
        is_ready, not_ready_reason = adapter.check_readiness()
        if not is_ready:
            run_model.error_message = f"Rerun not started: {not_ready_reason}"
            db.commit()
            db.refresh(run_model)
            return run_model, adapter, False

        run_model.status = RunStatus.RUNNING.value
        run_model.error_message = None
        run_model.completed_at = None
        db.commit()
        db.refresh(run_model)
        return run_model, adapter, True

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
        repetitions: int = 1,
    ) -> None:
        """Executes test cases with fixture reset and fresh agent sessions per case.

        With repetitions > 1 every case runs that many times, round-robin (all cases once, then
        again), each on a fresh fixture; executions are stored as ``<case_id>::r<n>``.
        """
        passed_cases = 0
        failed_cases = 0
        inconclusive_cases = 0
        error_cases = 0

        all_tool_names = [t.get("name") for t in tools if t.get("name")]
        # Live adapters prepare real application fixtures; others use the synthetic store.
        fixture_service = (
            getattr(adapter, "fixture_service", None) or self.fixture_service
        )

        def record_progress() -> None:
            run_model.summary = {
                "total_cases": len(cases) * repetitions,
                "passed_cases": passed_cases,
                "failed_cases": failed_cases,
                "inconclusive_cases": inconclusive_cases,
                "error_cases": error_cases,
            }
            db.commit()

        schedule = [(rep, c) for rep in range(1, repetitions + 1) for c in cases]
        for repetition, case_dict in schedule:
            # Check for cancellation between cases
            db.refresh(run_model)
            if run_model.status == RunStatus.ABORTED.value:
                break

            case_id = case_dict.get("case_id", f"case_{str(uuid.uuid4())[:8]}")
            if repetitions > 1:
                case_id = f"{case_id}::r{repetition}"
            category = case_dict.get("category", "CORRECT_BEHAVIOUR")
            is_valid = case_dict.get("is_valid", True)
            rejection_reason = case_dict.get("rejection_reason")

            # 1. Candidate readiness check
            if not is_valid or rejection_reason:
                # Do not score rejected, ambiguous, or unresolved candidate cases!
                case_exec = C1CaseExecutionModel(
                    id=f"cexec_{uuid.uuid4().hex[:30]}",
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
                fix_ok, session_data, fix_evidence = fixture_service.prepare_fixture(
                    session_id, fixture_plan
                )
            except (ValueError, KeyError, TypeError, AttributeError):
                fix_ok, session_data, fix_evidence = (
                    False,
                    {},
                    [],
                )

            if not fix_ok:
                case_exec = C1CaseExecutionModel(
                    id=f"cexec_{uuid.uuid4().hex[:30]}",
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
                    error_message=getattr(fixture_service, "last_error", None)
                    or "Fixture preparation failed.",
                    completed_at=datetime.now(UTC),
                )
                db.add(case_exec)
                db.commit()
                error_cases += 1
                record_progress()
                continue

            # 3. Prepare Agent-Facing Task (Strictly isolated from QA expectations)
            raw_specs = case_dict.get("expected_tool_calls", [])
            expectations = [ExpectedToolCallSpec.model_validate(s) for s in raw_specs]
            permitted_tools = [
                s.tool_name for s in expectations if not s.is_forbidden
            ] or all_tool_names

            agent_task = AgentFacingTask(
                case_id=case_id,
                task_prompt=case_dict.get("agent_task_prompt", ""),
                context_inputs=case_dict.get("task_context_inputs", {}),
                permitted_tools=permitted_tools,
            )
            task_error = None
            if hasattr(adapter, "prepare_task"):
                # Live targets fill customer-visible fixture values into the task text.
                agent_task, task_error = adapter.prepare_task(agent_task, session_data)

            # 4. Resolve Fixture-Dependent Expected Values (frozen before the agent runs)
            resolved_expectations = fixture_service.resolve_expectation_values(
                expectations, session_data
            )

            # 5. Invoke Agent through Adapter
            if task_error:
                adapter_res = AdapterExecutionResult(
                    session_id=session_id,
                    execution_status=CaseExecutionStatus.EXECUTION_ERROR,
                    trace_completeness=TraceCompleteness.MISSING,
                    raw_trace={
                        "adapter": getattr(adapter, "ADAPTER_TYPE", "UNKNOWN"),
                        "error": task_error,
                    },
                    error_message=task_error,
                )
            else:
                adapter_res = adapter.execute_task(
                    session_id=session_id,
                    task=agent_task,
                    deadline_seconds=deadline_seconds,
                )

            # 5b. One automatic retry when the agent's LLM provider failed (infrastructure, e.g. an
            # Ollama timeout): fresh fixture, same frozen case. The first attempt stays in evidence.
            if (
                not task_error
                and adapter_res.execution_status == CaseExecutionStatus.EXECUTION_ERROR
                and adapter_res.raw_trace.get("caller_outcome")
                in getattr(adapter, "RETRYABLE_OUTCOMES", ())
            ):
                first_attempt = {
                    k: adapter_res.raw_trace.get(k)
                    for k in (
                        "agent_run_id",
                        "caller_outcome",
                        "agent_error",
                        "nexacart_fixture_id",
                    )
                } | {"error": adapter_res.error_message}
                fixture_service.reset_session(session_id)
                session_id = f"{session_id}_retry"
                retry_ok, retry_data, retry_evidence = fixture_service.prepare_fixture(
                    session_id, fixture_plan
                )
                if retry_ok:
                    retry_task, retry_error = adapter.prepare_task(
                        AgentFacingTask(
                            case_id=case_id,
                            task_prompt=case_dict.get("agent_task_prompt", ""),
                            context_inputs=case_dict.get("task_context_inputs", {}),
                            permitted_tools=permitted_tools,
                        ),
                        retry_data,
                    )
                    if not retry_error:
                        session_data, agent_task = retry_data, retry_task
                        fix_evidence = fix_evidence + retry_evidence
                        resolved_expectations = (
                            fixture_service.resolve_expectation_values(
                                expectations, session_data
                            )
                        )
                        adapter_res = adapter.execute_task(
                            session_id=session_id,
                            task=agent_task,
                            deadline_seconds=deadline_seconds,
                        )
                adapter_res.raw_trace["infrastructure_retries"] = [first_attempt]

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
                id=f"cexec_{uuid.uuid4().hex[:30]}",
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

            # 8. Reset Fixture Session
            try:
                fixture_service.reset_session(session_id)
            except Exception as exc:  # noqa: BLE001
                # A failed release does not change the recorded evidence.
                logger.warning("Fixture release failed for %s: %s", session_id, exc)
            record_progress()

        # 9. Update Run Model Summary
        db.refresh(run_model)
        run_model.summary = {
            "total_cases": len(cases) * repetitions,
            "passed_cases": passed_cases,
            "failed_cases": failed_cases,
            "inconclusive_cases": inconclusive_cases,
            "error_cases": error_cases,
        }
        if repetitions > 1:
            run_model.summary = {
                **run_model.summary,
                "repetitions": repetitions,
                "repetition_summary": self.repetition_summary(
                    db, run_model.id, attempt_number
                ),
            }
        if run_model.status != RunStatus.ABORTED.value:
            run_model.status = RunStatus.COMPLETED.value
        run_model.completed_at = datetime.now(UTC)
        db.commit()

    @staticmethod
    def repetition_summary(
        db: Session, run_id: str, attempt_number: int
    ) -> dict[str, dict[str, Any]]:
        """Per-case outcome counts and pass rate over the repetitions of one attempt."""
        rows = (
            db.execute(
                select(C1CaseExecutionModel).where(
                    C1CaseExecutionModel.run_id == run_id,
                    C1CaseExecutionModel.attempt_number == attempt_number,
                )
            )
            .scalars()
            .all()
        )
        summary: dict[str, dict[str, Any]] = {}
        for row in rows:
            base = row.case_id.split("::r")[0]
            entry = summary.setdefault(
                base,
                {"runs": 0, "PASS": 0, "FAIL": 0, "INCONCLUSIVE": 0, "ERROR": 0},
            )
            entry["runs"] += 1
            if row.execution_status == CaseExecutionStatus.EXECUTION_ERROR.value:
                entry["ERROR"] += 1
            elif row.verdict in ("PASS", "FAIL", "INCONCLUSIVE"):
                entry[row.verdict] += 1
        for entry in summary.values():
            judged = entry["PASS"] + entry["FAIL"]
            # Pass rate over runs with a definite verdict; errors/inconclusive are reported apart.
            entry["pass_rate"] = round(entry["PASS"] / judged, 3) if judged else None
        return dict(sorted(summary.items()))

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
            repetitions=run_model.summary.get("repetitions", 1),
            repetition_summary=run_model.summary.get("repetition_summary", {}),
            execution_provenance=run_execution_provenance([c.raw_trace for c in case_details]),
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

        traces_by_run: dict[str, list[dict[str, Any] | None]] = {}
        if runs:
            trace_rows = db.execute(
                select(C1CaseExecutionModel.run_id, C1CaseExecutionModel.raw_trace).where(
                    C1CaseExecutionModel.run_id.in_([r.id for r in runs])
                )
            ).all()
            for run_id, raw_trace in trace_rows:
                traces_by_run.setdefault(run_id, []).append(raw_trace)

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
                    repetitions=r.summary.get("repetitions", 1),
                    repetition_summary=r.summary.get("repetition_summary", {}),
                    execution_provenance=run_execution_provenance(traces_by_run.get(r.id, [])),
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
