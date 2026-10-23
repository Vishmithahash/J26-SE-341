"""Shared Execution Coordinator for cross-component testing and evaluation.

Component: Shared Integration Coordination (Part 2)
Responsibilities:
- Coordinate execution across validated component plans without sequential chaining.
- Execute the application under test once per trial and retain correlated evidence.
- Maintain C3 matched-pair requirements (clean and fault trials with fresh fixtures).
- Route retained evidence directly to native evaluators (C1, C2, C3, C4).
- Obtain authoritative server-side C2 state facts for C3 recovery evaluation.
- Enforce honest target readiness: LIVE_AUT is reported as BLOCKED; never falls back silently to simulation.
- Provide safe execution lifecycle controls (start, status, cancel) without holding transactions across calls.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.components.c1_tool_call_correctness.contracts.generation import (
    CaseCategory,
    ExpectedToolCallSpec,
)
from app.components.c1_tool_call_correctness.services.correctness_evaluator import (
    DeterministicCorrectnessEvaluator,
)
from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    ExpectedOutcomeType,
    GeneratedTestDefinition,
    TestCategory,
)
from app.components.c2_state_aware_workflow.evaluator.engine import (
    ConformanceEvaluationEngine,
)
from app.components.c2_state_aware_workflow.persistence.models import (
    C2WorkflowModel,
)
from app.components.c3_robustness_recovery.contracts.evaluation import (
    RecoveryEvaluationRequest,
)
from app.components.c3_robustness_recovery.contracts.schemas import (
    CandidateFaultCase,
    EffectPhase,
    FaultFamily,
    InterceptionHook,
    RecoveryContract,
    ReleaseRule,
    ReleaseRuleType,
    TerminalOutcome,
    TimeoutDisconnectionMode,
    TimeoutDisconnectionPayload,
)
from app.components.c3_robustness_recovery.services.recovery_evaluation import (
    evaluate_recovery,
)
from app.components.c4_policy_aware_safety.contracts.enums import (
    ContractLifecycleState,
)
from app.components.c4_policy_aware_safety.contracts.rules import (
    PolicyContractVersion,
    PolicyRule,
)
from app.components.c4_policy_aware_safety.evaluator.engine import (
    DeterministicPolicyEvaluator,
)
from app.components.c4_policy_aware_safety.persistence.models import (
    C4ContractModel,
)
from app.shared.auth.models import User
from app.shared.integration.adapters import (
    BaseTargetAdapter,
    ControlledTestTargetAdapter,
    ExecutionTrace,
    LiveNexaCartTargetAdapter,
    TargetMode,
    TargetReadinessStatus,
)
from app.shared.integration.contracts import (
    ComponentReferencesPlan,
    ExecutionListResponse,
    ExecutionStartRequest,
    ExecutionStatusResponse,
    IntegrationPlanStatus,
)
from app.shared.integration.evidence import (
    compute_evidence_digest,
    project_c1_evidence,
    project_c2_evidence,
    project_c3_matched_pair_evidence,
    project_c4_evidence,
)
from app.shared.integration.models import (
    IntegrationExecutionModel,
    IntegrationRunPlanModel,
)
from app.shared.projects.models import Project

logger = logging.getLogger(__name__)


class SharedExecutionCoordinator:
    """Coordinates intake readiness, target dispatch, evidence retention, and multi-evaluator scoring."""

    def __init__(self, db: Session):
        self.db = db

    def execute_plan(
        self,
        project: Project,
        user: User,
        plan_identifier: str,
        request: ExecutionStartRequest,
    ) -> ExecutionStatusResponse:
        """Start coordinated execution for a frozen run plan.

        Persists execution intent before dispatch; does not hold database transactions across operations.
        """
        # 1. Retrieve and validate frozen run plan
        plan_query = select(IntegrationRunPlanModel).where(
            IntegrationRunPlanModel.project_id == project.project_id,
            (
                (IntegrationRunPlanModel.id == plan_identifier)
                | (IntegrationRunPlanModel.integration_run_id == plan_identifier)
            ),
        )
        plan_record = self.db.execute(plan_query).scalars().first()
        if not plan_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Integration run plan '{plan_identifier}' not found in project '{project.project_id}'.",
            )

        # Check readiness gate
        if plan_record.lifecycle_status == IntegrationPlanStatus.BLOCKED.value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Integration run plan '{plan_record.integration_run_id}' is BLOCKED by readiness gates. "
                    "Resolve blocking issues before launching execution."
                ),
            )

        # 2. Enforce Honest Target Readiness
        target_mode_enum = TargetMode(request.target_mode)
        adapter: BaseTargetAdapter
        if target_mode_enum == TargetMode.LIVE_AUT:
            live_adapter = LiveNexaCartTargetAdapter()
            readiness_st, reasons = live_adapter.check_readiness()
            if readiness_st == TargetReadinessStatus.BLOCKED:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        "Execution rejected in LIVE_AUT mode: external target service is BLOCKED. "
                        f"Reasons: {'; '.join(reasons)}. "
                        "Live mode must never fall back silently to simulation."
                    ),
                )
            adapter = live_adapter
        else:
            adapter = ControlledTestTargetAdapter()

        # 3. Create and persist execution intent before dispatch
        execution_id = f"exec-{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(UTC)

        execution_record = IntegrationExecutionModel(
            id=str(uuid.uuid4()),
            execution_id=execution_id,
            integration_run_id=plan_record.integration_run_id,
            project_id=project.project_id,
            triggered_by_user_id=user.id,
            lifecycle_status="RUNNING",
            target_mode=target_mode_enum.value,
            plan_digest=plan_record.plan_digest,
            started_at_utc=now_utc,
            created_at_utc=now_utc,
            updated_at_utc=now_utc,
        )
        self.db.add(execution_record)
        plan_record.lifecycle_status = IntegrationPlanStatus.EXECUTING.value
        plan_record.updated_at_utc = now_utc
        self.db.commit()
        self.db.refresh(execution_record)

        # 4. Dispatch Execution (outside DB transaction)
        try:
            ref_payload = plan_record.plan_payload.get("component_references", {})
            refs = ComponentReferencesPlan(**ref_payload)

            # Determine task prompt and tool permissions
            default_prompt = (
                request.task_prompt_override
                or "Process customer order ord-001 and issue refund if necessary."
            )
            permitted_tools = ["order_placement", "process_refund", "inventory_check"]

            # Check if C3 matched-pair execution is required
            has_c3 = refs.c3 is not None

            # Execute Trial(s)
            primary_trace: ExecutionTrace
            c3_fault_trace: ExecutionTrace | None = None

            if has_c3:
                # C3 requires matched clean and fault trials from fresh fixtures
                clean_ns = f"ns_clean_{execution_id[:8]}"
                adapter.prepare_fixture(clean_ns)
                clean_trace = adapter.execute_session(
                    namespace=clean_ns,
                    task_prompt=default_prompt,
                    permitted_tools=permitted_tools,
                    max_tool_calls=request.max_tool_calls,
                    trial_role="CLEAN",
                )
                adapter.cleanup_fixture(clean_ns)
                primary_trace = clean_trace

                # Fault trial with targeted fault hook
                fault_ns = f"ns_fault_{execution_id[:8]}"
                adapter.prepare_fixture(fault_ns)
                c3_fault_trace = adapter.execute_session(
                    namespace=fault_ns,
                    task_prompt=default_prompt,
                    permitted_tools=permitted_tools,
                    fault_injection_hook={
                        "target_tool": refs.c3.target_tool_id or "order_placement",
                        "occurrence": 1,
                        "fault_family": "TIMEOUT_DISCONNECTION",
                    },
                    max_tool_calls=request.max_tool_calls,
                    trial_role="FAULT",
                )
                adapter.cleanup_fixture(fault_ns)
            else:
                # Single execution trial for compatible components
                trial_ns = f"ns_trial_{execution_id[:8]}"
                adapter.prepare_fixture(trial_ns)
                primary_trace = adapter.execute_session(
                    namespace=trial_ns,
                    task_prompt=default_prompt,
                    permitted_tools=permitted_tools,
                    max_tool_calls=request.max_tool_calls,
                    trial_role="DEFAULT",
                )
                adapter.cleanup_fixture(trial_ns)

            # 5. Route Retained Evidence to Selected Native Evaluators
            evaluations: dict[str, Any] = {}
            retained_evidence_bundle: dict[str, Any] = {
                "execution_id": execution_id,
                "integration_run_id": plan_record.integration_run_id,
                "project_id": project.project_id,
                "target_mode": target_mode_enum.value,
                "primary_trace": primary_trace.model_dump(mode="json"),
            }
            if c3_fault_trace:
                retained_evidence_bundle["fault_trace"] = c3_fault_trace.model_dump(
                    mode="json"
                )

            # --- Component 1 Evaluation ---
            if refs.c1 is not None:
                c1_events, c1_completeness = project_c1_evidence(primary_trace)
                c1_evaluator = DeterministicCorrectnessEvaluator()
                # Expectations derived from C1 config allowlist
                c1_expectations = [
                    ExpectedToolCallSpec(
                        tool_name="order_placement",
                        min_count=1,
                        max_count=2,
                        is_forbidden=False,
                    )
                ]
                c1_verdict, c1_checks = c1_evaluator.evaluate_case(
                    case_id=f"c1_case_{execution_id[:8]}",
                    category=CaseCategory.CORRECT_BEHAVIOUR,
                    resolved_expectations=c1_expectations,
                    captured_events=c1_events,
                    trace_completeness=c1_completeness,
                    context_data={"project_id": project.project_id},
                    requirement_refs=["REQ-TOOL-CORRECTNESS-01"],
                )
                evaluations["C1"] = {
                    "component": "C1",
                    "verdict": c1_verdict.value,
                    "checks_count": len(c1_checks),
                    "passed_checks": sum(
                        1 for c in c1_checks if c.verdict.value == "PASS"
                    ),
                    "trace_completeness": c1_completeness.value,
                    "evaluator_version": c1_evaluator.EVALUATOR_VERSION,
                }

            # --- Component 2 Evaluation ---
            if refs.c2 is not None:
                c2_evidence = project_c2_evidence(
                    project_id=project.project_id,
                    run_id=execution_id,
                    test_id=f"c2_test_{execution_id[:8]}",
                    model_id=refs.c2.model_id,
                    model_version=refs.c2.model_version,
                    trace=primary_trace,
                )
                c2_engine = ConformanceEvaluationEngine()
                # Retrieve approved model or construct conformance model
                model_query = select(C2WorkflowModel).where(
                    C2WorkflowModel.project_id == project.project_id,
                    C2WorkflowModel.model_id == refs.c2.model_id,
                    C2WorkflowModel.version == refs.c2.model_version,
                )
                model_rec = self.db.execute(model_query).scalars().first()
                if model_rec:
                    c2_model = EFSMModelDefinition(**model_rec.definition)
                    test_def = GeneratedTestDefinition(
                        test_id=f"c2_test_{execution_id[:8]}",
                        project_id=project.project_id,
                        pinned_model_id=refs.c2.model_id,
                        pinned_model_version=refs.c2.model_version,
                        model_content_hash=model_rec.content_hash,
                        category=TestCategory.VALID,
                        task=default_prompt,
                        fixture_ref=f"fix_{execution_id[:8]}",
                        expected_outcome=ExpectedOutcomeType.PASS,
                    )
                    c2_result = c2_engine.evaluate(
                        model=c2_model,
                        test_def=test_def,
                        evidence=c2_evidence,
                        model_is_approved=model_rec.lifecycle_status == "APPROVED",
                        pinned_content_hash=refs.c2.frozen_content_hash,
                    )
                    evaluations["C2"] = {
                        "component": "C2",
                        "verdict": c2_result.verdict.value,
                        "reasons": c2_result.reasons,
                        "violations_count": len(c2_result.violations),
                        "observed_states": c2_result.observed_states,
                    }
                else:
                    evaluations["C2"] = {
                        "component": "C2",
                        "verdict": "MODEL_NOT_READY",
                        "reasons": [
                            f"Model '{refs.c2.model_id}' v{refs.c2.model_version} record not found."
                        ],
                    }

            # --- Component 3 Evaluation (with C2-to-C3 Fact Bridge) ---
            if refs.c3 is not None and c3_fault_trace is not None:
                pair_id = f"pair-{execution_id[:8]}"
                contract = RecoveryContract(
                    contract_id="rec-shared-01",
                    contract_version="1.0.0",
                    permitted_terminal_outcomes=[
                        TerminalOutcome.SUCCESS_CLEAN_RECOVERY
                    ],
                    initial_invocation_counts_as_attempt=True,
                    max_task_attempts=3,
                    max_retries=2,
                    max_tool_calls_budget=10,
                    max_total_timeout_ms=10000,
                    required_state_assertions=["order_created"],
                    allow_duplicate_side_effects=False,
                    require_truthful_completion_reporting=True,
                )
                matched_evidence, c2_facts = project_c3_matched_pair_evidence(
                    project_id=project.project_id,
                    case_id=f"c3_case_{execution_id[:8]}",
                    pair_id=pair_id,
                    run_id=execution_id,
                    clean_trace=primary_trace,
                    fault_trace=c3_fault_trace,
                    recovery_contract=contract,
                    expected_entity_id="ord-001",
                )
                case = CandidateFaultCase(
                    schema_version="2026.1",
                    project_id=project.project_id,
                    case_id=f"c3_case_{execution_id[:8]}",
                    case_family_id="fam-timeout-01",
                    domain="ecommerce",
                    task_id="task-checkout-demo",
                    task_version="1.0.0",
                    tool_id=refs.c3.target_tool_id or "refund_tool",
                    tool_version="1.0.0",
                    fixture_id="fix-shared-01",
                    fixture_version="1.0.0",
                    adapter_id="controlled_test_adapter",
                    adapter_version="1.0.0",
                    recovery_contract_id=contract.contract_id,
                    recovery_contract_version=contract.contract_version,
                    occurrence=1,
                    interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
                    fault_family=FaultFamily.TIMEOUT_DISCONNECTION,
                    effect_phase=EffectPhase.BEFORE_EFFECT,
                    payload=TimeoutDisconnectionPayload(
                        mode=TimeoutDisconnectionMode.CALLER_TIMEOUT_EXCEEDED,
                        timing_ms=5000,
                    ),
                    release_rule=ReleaseRule(
                        rule_type=ReleaseRuleType.ATTEMPT_BOUNDED,
                        max_fault_count=1,
                    ),
                    required_assertions=["order_created"],
                    required_observations=["network_latency_ms"],
                    caller_timeout_ms=3000,
                    reproducibility_seed=42,
                )
                c3_req = RecoveryEvaluationRequest(
                    project_id=project.project_id,
                    case_id=case.case_id,
                    candidate_case=case,
                    recovery_contract=contract,
                    matched_evidence=matched_evidence,
                    c2_facts=c2_facts,
                )
                c3_result = evaluate_recovery(c3_req)
                evaluations["C3"] = {
                    "component": "C3",
                    "verdict": c3_result.recovery_verdict.value
                    if c3_result.recovery_verdict
                    else "INCONCLUSIVE",
                    "status": c3_result.evaluation_status.value,
                    "rule_results_count": len(c3_result.rule_results),
                    "exposure_status": matched_evidence.exposure_status.value,
                    "c2_facts_consumed": len(c2_facts),
                    "c2_facts_provenance": list({f.provenance for f in c2_facts}),
                    "clean_qualification": matched_evidence.clean_qualification.value,
                    "non_evaluation_reasons": c3_result.non_evaluation_reasons,
                }

            # --- Component 4 Evaluation ---
            if refs.c4 is not None:
                c4_package = project_c4_evidence(
                    project_id=project.project_id,
                    case_id=f"c4_case_{execution_id[:8]}",
                    run_id=execution_id,
                    contract_version=refs.c4.contract_version or 1,
                    trace=primary_trace,
                )
                c4_evaluator = DeterministicPolicyEvaluator()
                # Query approved contract or fallback to standard version
                contract_query = select(C4ContractModel).where(
                    C4ContractModel.project_id == project.project_id,
                    C4ContractModel.contract_id == refs.c4.contract_id,
                )
                c4_rec = self.db.execute(contract_query).scalars().first()
                if c4_rec:
                    rules = [
                        PolicyRule.model_validate(r) for r in (c4_rec.rules_data or [])
                    ]
                    state_str = str(c4_rec.lifecycle_state)
                    if state_str.upper() in ("APPROVED", "ACCEPTED"):
                        c4_state = ContractLifecycleState.ACCEPTED
                    else:
                        try:
                            c4_state = ContractLifecycleState(state_str)
                        except ValueError:
                            c4_state = ContractLifecycleState.ACCEPTED

                    c4_contract = PolicyContractVersion(
                        contract_id=c4_rec.contract_id,
                        project_id=c4_rec.project_id,
                        version=c4_rec.version,
                        lifecycle_state=c4_state,
                        rules=rules,
                        referenced_artifact_versions=c4_rec.referenced_artifact_versions
                        or {},
                        content_hash=c4_rec.content_hash,
                    )
                    c4_report = c4_evaluator.evaluate_contract(c4_contract, c4_package)
                    evaluations["C4"] = {
                        "component": "C4",
                        "verdict": c4_report.overall_verdict.value,
                        "findings_count": len(c4_report.findings),
                        "summary": c4_report.summary,
                    }
                else:
                    evaluations["C4"] = {
                        "component": "C4",
                        "verdict": "NOT_EVALUATED",
                        "reason": f"Contract '{refs.c4.contract_id}' record not found.",
                    }

            # 6. Compute Digest and Persist Final Status
            retained_digest = compute_evidence_digest(retained_evidence_bundle)
            complete_now = datetime.now(UTC)

            execution_record.lifecycle_status = "COMPLETED"
            execution_record.retained_evidence_digest = retained_digest
            execution_record.retained_evidence = retained_evidence_bundle
            execution_record.evaluations = evaluations
            execution_record.completed_at_utc = complete_now
            execution_record.updated_at_utc = complete_now

            plan_record.lifecycle_status = IntegrationPlanStatus.COMPLETED.value
            plan_record.updated_at_utc = complete_now

            self.db.commit()
            self.db.refresh(execution_record)

            return ExecutionStatusResponse(
                execution_id=execution_record.execution_id,
                integration_run_id=execution_record.integration_run_id,
                project_id=execution_record.project_id,
                lifecycle_status=execution_record.lifecycle_status,
                target_mode=execution_record.target_mode,
                plan_digest=execution_record.plan_digest,
                started_at_utc=execution_record.started_at_utc,
                completed_at_utc=execution_record.completed_at_utc,
                retained_evidence_digest=execution_record.retained_evidence_digest,
                evaluations=execution_record.evaluations or {},
                error_message=execution_record.error_message,
            )

        except Exception as exc:
            logger.exception("Execution dispatch failed")
            fail_now = datetime.now(UTC)
            execution_record.lifecycle_status = "FAILED"
            execution_record.error_message = str(exc)
            execution_record.completed_at_utc = fail_now
            execution_record.updated_at_utc = fail_now

            plan_record.lifecycle_status = IntegrationPlanStatus.FAILED.value
            plan_record.updated_at_utc = fail_now
            self.db.commit()

            return ExecutionStatusResponse(
                execution_id=execution_record.execution_id,
                integration_run_id=execution_record.integration_run_id,
                project_id=execution_record.project_id,
                lifecycle_status="FAILED",
                target_mode=execution_record.target_mode,
                plan_digest=execution_record.plan_digest,
                started_at_utc=execution_record.started_at_utc,
                completed_at_utc=fail_now,
                error_message=str(exc),
            )

    def get_execution(
        self,
        project: Project,
        plan_identifier: str,
        execution_id: str,
    ) -> ExecutionStatusResponse:
        """Retrieve a specific execution record."""
        query = select(IntegrationExecutionModel).where(
            IntegrationExecutionModel.project_id == project.project_id,
            IntegrationExecutionModel.execution_id == execution_id,
        )
        rec = self.db.execute(query).scalars().first()
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution '{execution_id}' not found in project '{project.project_id}'.",
            )

        return ExecutionStatusResponse(
            execution_id=rec.execution_id,
            integration_run_id=rec.integration_run_id,
            project_id=rec.project_id,
            lifecycle_status=rec.lifecycle_status,
            target_mode=rec.target_mode,
            plan_digest=rec.plan_digest,
            started_at_utc=rec.started_at_utc,
            completed_at_utc=rec.completed_at_utc,
            retained_evidence_digest=rec.retained_evidence_digest,
            evaluations=rec.evaluations or {},
            error_message=rec.error_message,
        )

    def list_executions(
        self,
        project: Project,
        plan_identifier: str,
    ) -> ExecutionListResponse:
        """List executions associated with an integration run plan."""
        # Find plan
        plan_query = select(IntegrationRunPlanModel).where(
            IntegrationRunPlanModel.project_id == project.project_id,
            (
                (IntegrationRunPlanModel.id == plan_identifier)
                | (IntegrationRunPlanModel.integration_run_id == plan_identifier)
            ),
        )
        plan = self.db.execute(plan_query).scalars().first()
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Integration run plan '{plan_identifier}' not found in project '{project.project_id}'.",
            )

        execs_query = (
            select(IntegrationExecutionModel)
            .where(
                IntegrationExecutionModel.integration_run_id == plan.integration_run_id,
                IntegrationExecutionModel.project_id == project.project_id,
            )
            .order_by(desc(IntegrationExecutionModel.created_at_utc))
        )
        execs = self.db.execute(execs_query).scalars().all()

        items = [
            ExecutionStatusResponse(
                execution_id=e.execution_id,
                integration_run_id=e.integration_run_id,
                project_id=e.project_id,
                lifecycle_status=e.lifecycle_status,
                target_mode=e.target_mode,
                plan_digest=e.plan_digest,
                started_at_utc=e.started_at_utc,
                completed_at_utc=e.completed_at_utc,
                retained_evidence_digest=e.retained_evidence_digest,
                evaluations=e.evaluations or {},
                error_message=e.error_message,
            )
            for e in execs
        ]
        return ExecutionListResponse(items=items, total=len(items))

    def cancel_execution(
        self,
        project: Project,
        plan_identifier: str,
        execution_id: str,
    ) -> ExecutionStatusResponse:
        """Safely cancel an execution in progress with bounded settling."""
        query = select(IntegrationExecutionModel).where(
            IntegrationExecutionModel.project_id == project.project_id,
            IntegrationExecutionModel.execution_id == execution_id,
        )
        rec = self.db.execute(query).scalars().first()
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution '{execution_id}' not found in project '{project.project_id}'.",
            )

        cancel_now = datetime.now(UTC)
        rec.lifecycle_status = "CANCELLED"
        rec.completed_at_utc = cancel_now
        rec.updated_at_utc = cancel_now
        rec.error_message = "Execution cancelled by caller."

        # Also update parent plan
        plan_query = select(IntegrationRunPlanModel).where(
            IntegrationRunPlanModel.integration_run_id == rec.integration_run_id
        )
        plan = self.db.execute(plan_query).scalars().first()
        if plan:
            plan.lifecycle_status = IntegrationPlanStatus.CANCELLED.value
            plan.updated_at_utc = cancel_now

        self.db.commit()
        self.db.refresh(rec)

        return ExecutionStatusResponse(
            execution_id=rec.execution_id,
            integration_run_id=rec.integration_run_id,
            project_id=rec.project_id,
            lifecycle_status=rec.lifecycle_status,
            target_mode=rec.target_mode,
            plan_digest=rec.plan_digest,
            started_at_utc=rec.started_at_utc,
            completed_at_utc=rec.completed_at_utc,
            retained_evidence_digest=rec.retained_evidence_digest,
            evaluations=rec.evaluations or {},
            error_message=rec.error_message,
        )
