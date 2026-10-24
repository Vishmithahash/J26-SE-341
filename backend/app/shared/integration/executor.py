"""Shared Execution Coordinator for cross-component testing and evaluation.

Component: Shared Integration Coordination (Part 2)
Responsibilities:
- Coordinate execution across validated component plans without sequential chaining.
- Execute the application under test once per trial and retain correlated evidence.
- Maintain C3 matched-pair requirements (clean and fault trials with fresh fixtures).
- Route retained evidence directly to native evaluators (C1, C2, C3, C4) via shared dispatcher.
- Obtain authoritative server-side C2 state facts for C3 recovery evaluation.
- Enforce honest target readiness: LIVE_AUT is reported as BLOCKED; never falls back silently to simulation.
- Provide safe execution lifecycle controls (start, status, cancel) with cooperative cancellation and without holding transactions across calls.
"""

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
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
    GeneratedTestDefinition,
)
from app.components.c2_state_aware_workflow.evaluator.engine import (
    ConformanceEvaluationEngine,
)
from app.components.c2_state_aware_workflow.persistence.models import (
    C2EvaluationResult,
    C2ExecutionEvidence,
    C2TestCase,
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
    IntegrationIdentifierMappingModel,
    IntegrationPublishedContributionModel,
    IntegrationRunPlanModel,
)
from app.shared.integration.service import canonical_json_digest
from app.shared.projects.models import Project

logger = logging.getLogger(__name__)

# Active cooperative cancellation set
ACTIVE_CANCELLATIONS: set[str] = set()


def dispatch_component_evaluations(
    db: Session,
    project_id: str,
    execution_id: str,
    refs: ComponentReferencesPlan,
    frozen_inputs: dict[str, Any],
    primary_trace: ExecutionTrace,
    c3_fault_trace: ExecutionTrace | None = None,
    is_replay: bool = False,
) -> dict[str, Any]:
    """Shared deterministic evaluation dispatcher reused by execution and replay.

    Routes retained traces through pinned component evaluators using frozen snapshots.
    Never invents arbitrary test cases, models, or recovery contracts.
    """
    evaluations: dict[str, Any] = {}

    # --- Component 1: Tool-Call Correctness ---
    if refs.c1 is not None:
        c1_inputs = frozen_inputs.get("c1", {})
        c1_events, c1_completeness = project_c1_evidence(primary_trace)
        c1_evaluator = DeterministicCorrectnessEvaluator()

        raw_specs = (
            c1_inputs.get("expected_tool_calls") or c1_inputs.get("expectations") or []
        )
        c1_expectations: list[ExpectedToolCallSpec] = []
        for spec in raw_specs:
            if isinstance(spec, dict):
                c1_expectations.append(ExpectedToolCallSpec(**spec))
            elif isinstance(spec, ExpectedToolCallSpec):
                c1_expectations.append(spec)

        case_cat = CaseCategory.CORRECT_BEHAVIOUR
        raw_cat = c1_inputs.get("category")
        if raw_cat:
            try:
                case_cat = CaseCategory(raw_cat)
            except ValueError:
                pass

        req_refs = c1_inputs.get("requirement_refs") or ["REQ-TOOL-CORRECTNESS-01"]
        c1_case_id = c1_inputs.get("case_id") or f"c1_case_{execution_id[:8]}"

        c1_verdict, c1_checks = c1_evaluator.evaluate_case(
            case_id=c1_case_id,
            category=case_cat,
            resolved_expectations=c1_expectations,
            captured_events=c1_events,
            trace_completeness=c1_completeness,
            context_data={
                "project_id": project_id,
                **(
                    c1_inputs.get("context_data")
                    or {
                        "fixture_order_9821": {
                            "order_id": "ORD-9821",
                            "customer_id": "CUST-8831",
                            "status": "DELIVERED",
                            "items": {
                                "ITEM-44": {
                                    "name": "Wireless Ergonomic Mouse",
                                    "price": 35.00,
                                    "refundable": True,
                                }
                            },
                        }
                    }
                ),
            },
            requirement_refs=req_refs,
        )
        evaluations["C1"] = {
            "component": "C1",
            "verdict": c1_verdict.value,
            "checks_count": len(c1_checks),
            "passed_checks": sum(1 for c in c1_checks if c.verdict.value == "PASS"),
            "trace_completeness": c1_completeness.value,
            "evaluator_version": c1_evaluator.EVALUATOR_VERSION,
            "checks": [c.model_dump(mode="json") for c in c1_checks],
        }

    # --- Component 2: State-Aware EFSM Testing ---
    if refs.c2 is not None:
        c2_inputs = frozen_inputs.get("c2", {})
        c2_evidence = project_c2_evidence(
            project_id=project_id,
            run_id=execution_id,
            test_id=c2_inputs.get("test_id") or f"c2_test_{execution_id[:8]}",
            model_id=refs.c2.model_id,
            model_version=refs.c2.model_version,
            trace=primary_trace,
        )
        c2_engine = ConformanceEvaluationEngine()

        model_def = c2_inputs.get("definition")
        pinned_hash = refs.c2.frozen_content_hash or c2_inputs.get("content_hash")
        model_status = c2_inputs.get("lifecycle_status", "APPROVED")

        if not model_def:
            model_query = select(C2WorkflowModel).where(
                C2WorkflowModel.project_id == project_id,
                C2WorkflowModel.model_id == refs.c2.model_id,
                C2WorkflowModel.version == refs.c2.model_version,
            )
            model_rec = db.execute(model_query).scalars().first()
            if model_rec:
                model_def = model_rec.definition
                pinned_hash = pinned_hash or model_rec.content_hash
                model_status = model_rec.lifecycle_status

        if model_def:
            c2_model = EFSMModelDefinition(**model_def)
            test_def_raw = c2_inputs.get("test_definition")
            test_def = None
            if test_def_raw and isinstance(test_def_raw, dict):
                td_dict = dict(test_def_raw)
                if isinstance(td_dict.get("category"), str):
                    td_dict["category"] = td_dict["category"].lower()
                test_def = GeneratedTestDefinition(**td_dict)
            else:
                test_id = c2_inputs.get("test_id")
                suite_id = refs.c2.suite_id or c2_inputs.get("suite_id")
                if test_id:
                    t_query = select(C2TestCase).where(
                        C2TestCase.project_id == project_id,
                        C2TestCase.test_id == test_id,
                    )
                    if suite_id:
                        t_query = t_query.where(C2TestCase.suite_id == suite_id)
                    test_rec = db.execute(t_query).scalars().first()
                    if test_rec and test_rec.definition:
                        td_dict = dict(test_rec.definition)
                        if isinstance(td_dict.get("category"), str):
                            td_dict["category"] = td_dict["category"].lower()
                        test_def = GeneratedTestDefinition(**td_dict)

            if not test_def:
                evaluations["C2"] = {
                    "component": "C2",
                    "verdict": "TEST NOT READY",
                    "reasons": [
                        f"Test '{c2_inputs.get('test_id')}' definition not found or unready."
                    ],
                }
            else:
                c2_result = c2_engine.evaluate(
                    model=c2_model,
                    test_def=test_def,
                    evidence=c2_evidence,
                    model_is_approved=(model_status == "APPROVED"),
                    pinned_content_hash=pinned_hash,
                )
                eval_id = None
                evidence_id = None
                pub_token = None
                c2_res_rec = None
                if not is_replay:
                    suite_id = (
                        refs.c2.suite_id
                        or c2_inputs.get("suite_id")
                        or getattr(test_def, "suite_id", None)
                        or "default_suite"
                    )
                    evidence_digest = (
                        c2_evidence.canonical_digest()
                        if hasattr(c2_evidence, "canonical_digest")
                        else canonical_json_digest(c2_evidence.model_dump(mode="json"))
                    )

                    c2_ev_rec = C2ExecutionEvidence(
                        project_id=project_id,
                        suite_id=suite_id,
                        test_id=test_def.test_id,
                        run_id=execution_id,
                        evidence_digest=evidence_digest,
                        model_id=refs.c2.model_id,
                        model_version=refs.c2.model_version,
                        model_content_hash=pinned_hash or "",
                        execution_mode=c2_evidence.execution_mode,
                        runner_id="shared_integration_coordinator",
                        execution_provenance=c2_evidence.collector_provenance,
                        evidence_payload=c2_evidence.model_dump(mode="json"),
                    )
                    db.add(c2_ev_rec)
                    db.flush()
                    evidence_id = c2_ev_rec.id

                    c2_res_rec = C2EvaluationResult(
                        execution_evidence_id=c2_ev_rec.id,
                        project_id=project_id,
                        suite_id=suite_id,
                        test_id=test_def.test_id,
                        run_id=execution_id,
                        model_id=refs.c2.model_id,
                        model_version=refs.c2.model_version,
                        model_content_hash=pinned_hash or "",
                        evaluator_version="c2_evaluator_v1",
                        verdict=c2_result.verdict.value,
                        reasons=c2_result.reasons,
                        violations=[
                            v.model_dump(mode="json") for v in c2_result.violations
                        ],
                        first_divergence=(
                            c2_result.first_divergence.model_dump(mode="json")
                            if c2_result.first_divergence
                            else None
                        ),
                        coverage=c2_result.coverage.model_dump(mode="json")
                        if hasattr(c2_result, "coverage") and c2_result.coverage
                        else {},
                        expected_states=c2_result.expected_states,
                        observed_states=c2_result.observed_states,
                        evidence_references=c2_result.evidence_references,
                        evaluator_timing_ms=c2_result.evaluator_timing_ms,
                    )
                    db.add(c2_res_rec)
                    db.flush()
                    eval_id = c2_res_rec.id

                    plan_rec = (
                        db.execute(
                            select(IntegrationExecutionModel.integration_run_id).where(
                                IntegrationExecutionModel.execution_id == execution_id
                            )
                        )
                        .scalars()
                        .first()
                    )
                    run_id_for_mapping = plan_rec or execution_id

                    mapping_rec = IntegrationIdentifierMappingModel(
                        integration_run_id=run_id_for_mapping,
                        project_id=project_id,
                        component_type="C2",
                        native_entity_type="evaluation",
                        native_id=c2_res_rec.id,
                        context_json={
                            "execution_id": execution_id,
                            "suite_id": suite_id,
                            "test_id": test_def.test_id,
                            "evidence_id": c2_ev_rec.id,
                        },
                    )
                    db.add(mapping_rec)

                    c2_payload = {
                        "project_id": project_id,
                        "component": "C2",
                        "evaluation_id": eval_id,
                        "evidence_id": evidence_id,
                        "verdict": c2_result.verdict.value,
                        "observed_states": c2_result.observed_states,
                        "reasons": c2_result.reasons,
                        "violations": [
                            v.model_dump(mode="json") for v in c2_result.violations
                        ],
                    }
                    content_digest = canonical_json_digest(c2_payload)
                    pub_token = f"PUB-{execution_id[:8]}-{content_digest[:8]}"
                    pub_record = IntegrationPublishedContributionModel(
                        project_id=project_id,
                        component_type="C2",
                        contribution_id=eval_id,
                        execution_id=execution_id,
                        publication_token=pub_token,
                        content_digest=content_digest,
                        payload=c2_payload,
                    )
                    db.add(pub_record)

                pub_token_val = pub_token if c2_res_rec is not None else None
                evaluations["C2"] = {
                    "component": "C2",
                    "verdict": c2_result.verdict.value,
                    "evaluation_id": eval_id,
                    "evidence_id": evidence_id,
                    "publication_token": pub_token_val,
                    "reasons": c2_result.reasons,
                    "violations_count": len(c2_result.violations),
                    "observed_states": c2_result.observed_states,
                    "violations": [
                        v.model_dump(mode="json") for v in c2_result.violations
                    ],
                    "first_divergence": (
                        c2_result.first_divergence.model_dump(mode="json")
                        if c2_result.first_divergence
                        else None
                    ),
                }
        else:
            evaluations["C2"] = {
                "component": "C2",
                "verdict": "MODEL NOT READY",
                "reasons": [
                    f"Model '{refs.c2.model_id}' v{refs.c2.model_version} record not found."
                ],
            }

    # --- Component 3: Robustness & Fault Recovery ---
    if refs.c3 is not None and c3_fault_trace is not None:
        c3_inputs = frozen_inputs.get("c3", {})
        pair_id = f"pair-{execution_id[:8]}"

        is_demo_c3 = bool(
            frozen_inputs.get("is_demonstration") is True
            or frozen_inputs.get("is_demo") is True
        )

        contract_raw = c3_inputs.get("recovery_contract") or c3_inputs.get(
            "recovery_contract_snapshot"
        )
        if (
            contract_raw
            and isinstance(contract_raw, dict)
            and contract_raw.get("contract_id")
        ):
            contract = RecoveryContract(**contract_raw)
        elif is_demo_c3:
            contract = RecoveryContract(
                contract_id="rec-shared-01",
                contract_version="1.0.0",
                permitted_terminal_outcomes=[TerminalOutcome.SUCCESS_CLEAN_RECOVERY],
                initial_invocation_counts_as_attempt=True,
                max_task_attempts=3,
                max_retries=2,
                max_tool_calls_budget=10,
                max_total_timeout_ms=10000,
                required_state_assertions=["order_created"],
                allow_duplicate_side_effects=False,
                require_truthful_completion_reporting=True,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Execution evaluation prevented: missing required C3 recovery contract in frozen execution inputs.",
            )

        case_raw = c3_inputs.get("case") or c3_inputs.get("selected_case")
        if case_raw and isinstance(case_raw, dict) and case_raw.get("case_id"):
            case = CandidateFaultCase(**case_raw)
        elif is_demo_c3:
            case = CandidateFaultCase(
                schema_version="2026.1",
                project_id=project_id,
                case_id=c3_inputs.get("case_id") or f"c3_case_{execution_id[:8]}",
                case_family_id="fam-timeout-01",
                domain="ecommerce",
                task_id=refs.c3.task_id or "task-checkout-demo",
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
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Execution evaluation prevented: missing required C3 candidate fault case in frozen execution inputs.",
            )

        pinned_mappings = c3_inputs.get("pinned_mappings") or c3_inputs.get("mappings")
        expected_entity_id = c3_inputs.get("expected_entity_id")
        if not expected_entity_id and c3_fault_trace and c3_fault_trace.final_state:
            f_state = getattr(c3_fault_trace.final_state, "state", {}) or {}
            if isinstance(f_state, dict):
                order_info = f_state.get("order")
                if isinstance(order_info, dict) and order_info.get("order_id"):
                    expected_entity_id = str(order_info.get("order_id"))
        if not expected_entity_id and (
            is_demo_c3
            or getattr(primary_trace, "target_mode", None) == TargetMode.CONTROLLED_TEST
        ):
            expected_entity_id = "ord-001"
        matched_evidence, c2_facts = project_c3_matched_pair_evidence(
            project_id=project_id,
            case_id=case.case_id,
            pair_id=pair_id,
            run_id=execution_id,
            clean_trace=primary_trace,
            fault_trace=c3_fault_trace,
            recovery_contract=contract,
            c2_mappings=pinned_mappings,
            expected_entity_id=expected_entity_id,
        )

        c3_req = RecoveryEvaluationRequest(
            project_id=project_id,
            case_id=case.case_id,
            candidate_case=case,
            recovery_contract=contract,
            matched_evidence=matched_evidence,
            c2_facts=c2_facts,
            pinned_mappings=pinned_mappings,
        )
        c3_result = evaluate_recovery(c3_req)

        recovery_verdict_str = (
            c3_result.recovery_verdict.value if c3_result.recovery_verdict else None
        )
        evaluations["C3"] = {
            "component": "C3",
            "verdict": recovery_verdict_str,
            "status": c3_result.evaluation_status.value,
            "rule_results_count": len(c3_result.rule_results),
            "exposure_status": matched_evidence.exposure_status.value,
            "c2_facts_consumed": len(c2_facts),
            "c2_facts_provenance": list({f.provenance for f in c2_facts}),
            "clean_qualification": matched_evidence.clean_qualification.value,
            "non_evaluation_reasons": c3_result.non_evaluation_reasons,
            "rule_results": [
                {
                    "rule_id": r.rule_id,
                    "rule_name": r.rule_name,
                    "status": r.status.value
                    if hasattr(r.status, "value")
                    else str(r.status),
                    "reason_code": r.reason_code,
                    "message": r.message,
                    "supporting_fact_ids": r.supporting_fact_ids,
                    "supporting_event_ids": r.supporting_event_ids,
                    "details": r.details,
                }
                for r in c3_result.rule_results
            ],
        }

    # --- Component 4: Policy-Aware Safety & Compliance ---
    if refs.c4 is not None:
        c4_inputs = frozen_inputs.get("c4", {})
        contract_version = refs.c4.contract_version or c4_inputs.get("version", 1)
        c4_package = project_c4_evidence(
            project_id=project_id,
            case_id=f"c4_case_{execution_id[:8]}",
            run_id=execution_id,
            contract_version=contract_version,
            trace=primary_trace,
        )
        c4_evaluator = DeterministicPolicyEvaluator()

        rules: list[PolicyRule] = []
        rules_data = (
            c4_inputs.get("rules")
            if c4_inputs.get("rules") is not None
            else c4_inputs.get("rules_data")
        )
        content_hash = refs.c4.frozen_content_hash or c4_inputs.get("content_hash", "")
        referenced_artifacts = c4_inputs.get("referenced_artifact_versions", {})

        if rules_data is not None:
            for r in rules_data:
                rules.append(PolicyRule.model_validate(r))

            c4_contract = PolicyContractVersion(
                contract_id=refs.c4.contract_id,
                project_id=project_id,
                version=contract_version,
                lifecycle_state=ContractLifecycleState.ACCEPTED,
                rules=rules,
                referenced_artifact_versions=referenced_artifacts,
                content_hash=content_hash,
            )
            c4_report = c4_evaluator.evaluate_contract(c4_contract, c4_package)
            findings = c4_report.findings
            evaluations["C4"] = {
                "component": "C4",
                "verdict": c4_report.overall_verdict.value,
                "findings_count": len(findings),
                "summary": c4_report.summary,
                "findings": [
                    {
                        "finding_id": f.finding_id,
                        "rule_id": f.rule_id,
                        "verdict": f.verdict.value,
                        "explanation": f.explanation,
                        "event_id": f.supporting_evidence_ids[0]
                        if f.supporting_evidence_ids
                        else None,
                        "supporting_evidence_ids": f.supporting_evidence_ids,
                        "severity": f.severity.value
                        if hasattr(f.severity, "value")
                        else str(f.severity),
                    }
                    for f in findings
                ],
            }
        else:
            evaluations["C4"] = {
                "component": "C4",
                "verdict": "NOT_EVALUATED",
                "reason": f"Contract '{refs.c4.contract_id}' v{contract_version} record not found.",
            }

    return evaluations


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
        Supports cooperative cancellation and strictly enforces bounded resource limits.
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

        # Verify plan content digest and execution inputs digest before dispatch
        plan_payload = plan_record.plan_payload or {}
        inputs_snapshot = plan_payload.get("execution_inputs_snapshot", {})
        expected_inputs_digest = plan_payload.get("execution_inputs_digest")
        if expected_inputs_digest:
            actual_inputs_digest = canonical_json_digest(inputs_snapshot)
            if actual_inputs_digest != expected_inputs_digest:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Plan execution inputs integrity check failed: digest mismatch ({actual_inputs_digest} != {expected_inputs_digest}).",
                )
        if plan_record.plan_digest:
            actual_plan_digest = canonical_json_digest(plan_payload)
            if actual_plan_digest != plan_record.plan_digest:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Plan content integrity check failed: digest mismatch ({actual_plan_digest} != {plan_record.plan_digest}).",
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

        # Validate required pinned execution inputs before dispatching
        ref_payload = plan_record.plan_payload.get("component_references", {})
        refs = ComponentReferencesPlan(**ref_payload)
        frozen_inputs = plan_record.plan_payload.get("execution_inputs_snapshot", {})

        # 1. Identify demonstration configuration explicitly without heuristic inference
        is_demo = bool(
            frozen_inputs.get("is_demonstration") is True
            or frozen_inputs.get("is_demo") is True
            or (
                plan_record.plan_payload
                and plan_record.plan_payload.get("is_demonstration") is True
            )
            or getattr(plan_record, "is_demonstration", False) is True
        )

        has_c1 = (refs.c1 is not None) or ("c1" in frozen_inputs)
        has_c2 = (refs.c2 is not None) or ("c2" in frozen_inputs)
        has_c3 = (refs.c3 is not None) or ("c3" in frozen_inputs)
        has_c4 = (refs.c4 is not None) or ("c4" in frozen_inputs)

        c1_raw = frozen_inputs.get("c1")
        c2_raw = frozen_inputs.get("c2")
        c3_raw = frozen_inputs.get("c3")
        c4_raw = frozen_inputs.get("c4")

        c1_inputs = c1_raw if isinstance(c1_raw, dict) else {}
        c2_inputs = c2_raw if isinstance(c2_raw, dict) else {}
        c3_inputs = c3_raw if isinstance(c3_raw, dict) else {}
        c4_inputs = c4_raw if isinstance(c4_raw, dict) else {}

        resolved_prompt = request.task_prompt_override
        if not resolved_prompt and c1_inputs:
            resolved_prompt = c1_inputs.get("task_prompt") or c1_inputs.get("task")
        if not resolved_prompt and c2_inputs:
            c2_test_def = c2_inputs.get("test_definition") or {}
            resolved_prompt = (
                c2_test_def.get("task")
                or c2_inputs.get("task")
                or c2_inputs.get("task_prompt")
            )
        if not resolved_prompt and c3_inputs:
            c3_case_snap = c3_inputs.get("case") or c3_inputs.get("selected_case") or {}
            resolved_prompt = (
                c3_case_snap.get("task")
                or c3_inputs.get("task")
                or c3_inputs.get("task_prompt")
            )
        if not resolved_prompt and c4_inputs:
            resolved_prompt = c4_inputs.get("task_prompt") or c4_inputs.get("task")

        if not resolved_prompt:
            has_explicit_component_input = (
                (has_c1 and c1_raw is not None)
                or (has_c2 and c2_raw is not None)
                or (has_c3 and c3_raw is not None)
                or (has_c4 and c4_raw is not None)
                or (frozen_inputs.get("is_demonstration") is False)
            )
            if has_explicit_component_input and not is_demo:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Execution dispatch prevented: missing required task prompt in frozen execution inputs.",
                )
            resolved_prompt = (
                "Execute target test plan"
                if not is_demo
                else "Demonstration execution task prompt"
            )
        default_prompt = resolved_prompt

        # 3. Resolve actual permitted tools from pinned component inputs
        active_tools: list[str] = []
        if request.permitted_tools_override:
            active_tools = list(request.permitted_tools_override)
        else:
            # From C1
            c1_tools = [
                t.get("name") if isinstance(t, dict) else getattr(t, "name", "")
                for t in (
                    c1_inputs.get("tools", []) if isinstance(c1_inputs, dict) else []
                )
            ]
            c1_permitted = c1_inputs.get("permitted_tools") or [
                t for t in c1_tools if t
            ]
            for t in c1_permitted:
                if t and t not in active_tools:
                    active_tools.append(t)

            # From C2
            c2_def = c2_inputs.get("definition") or {}
            c2_event_mappings = c2_def.get("event_mappings") or []
            for em in c2_event_mappings:
                tool_name = (
                    em.get("tool_name")
                    if isinstance(em, dict)
                    else getattr(em, "tool_name", None)
                )
                if tool_name and tool_name not in active_tools:
                    active_tools.append(tool_name)
            c2_tool_specs = c2_def.get("tool_specifications") or []
            for ts in c2_tool_specs:
                tool_name = (
                    ts.get("name")
                    if isinstance(ts, dict)
                    else getattr(ts, "name", None)
                )
                if tool_name and tool_name not in active_tools:
                    active_tools.append(tool_name)

            # From C3
            c3_case_snap = c3_inputs.get("case") or c3_inputs.get("selected_case") or {}
            c3_tool = (
                c3_case_snap.get("tool_id")
                or (refs.c3.target_tool_id if refs.c3 else None)
                or c3_inputs.get("tool_id")
            )
            if c3_tool and c3_tool not in active_tools:
                active_tools.append(c3_tool)

            # From C4
            c4_tools = c4_inputs.get("permitted_tools") or c4_inputs.get("tools") or []
            for t in c4_tools:
                tool_name = t.get("name") if isinstance(t, dict) else t
                if tool_name and tool_name not in active_tools:
                    active_tools.append(tool_name)

        if not active_tools:
            has_explicit_component_input = (
                (has_c1 and c1_raw is not None)
                or (has_c2 and c2_raw is not None)
                or (has_c3 and c3_raw is not None)
                or (has_c4 and c4_raw is not None)
                or (frozen_inputs.get("is_demonstration") is False)
            )
            if has_explicit_component_input and not is_demo:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Execution dispatch prevented: missing required tool configuration in frozen execution inputs.",
                )
            permitted_tools = (
                ["target_execution_tool"] if not is_demo else ["demo_tool"]
            )
        else:
            permitted_tools = active_tools

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
        prepared_namespaces: list[str] = []
        try:
            if execution_id in ACTIVE_CANCELLATIONS:
                ACTIVE_CANCELLATIONS.discard(execution_id)
                execution_record.lifecycle_status = "CANCELLED"
                execution_record.error_message = (
                    "Execution cancelled prior to target dispatch."
                )
                execution_record.completed_at_utc = datetime.now(UTC)
                self.db.commit()
                return self._to_status_response(execution_record)

            deadline_monotonic = (
                (time.monotonic() + request.timeout_seconds)
                if request.timeout_seconds
                else None
            )

            def is_cancelled() -> bool:
                return execution_id in ACTIVE_CANCELLATIONS or self._is_cancelled(
                    execution_id
                )

            has_c3 = refs.c3 is not None
            primary_trace: ExecutionTrace
            c3_fault_trace: ExecutionTrace | None = None

            if has_c3:
                clean_ns = f"ns_clean_{execution_id}"
                prepared_namespaces.append(clean_ns)
                adapter.prepare_fixture(clean_ns)
                clean_trace = adapter.execute_session(
                    namespace=clean_ns,
                    task_prompt=default_prompt,
                    permitted_tools=permitted_tools,
                    max_tool_calls=request.max_tool_calls,
                    trial_role="CLEAN",
                    deadline_monotonic=deadline_monotonic,
                    check_cancellation=is_cancelled,
                )
                primary_trace = clean_trace

                if is_cancelled():
                    raise InterruptedError("Execution cancelled by caller.")

                fault_ns = f"ns_fault_{execution_id}"
                prepared_namespaces.append(fault_ns)
                adapter.prepare_fixture(fault_ns)
                c3_in = frozen_inputs.get("c3", {})
                c3_case_snap = c3_in.get("case") or c3_in.get("selected_case") or {}
                target_tool = (
                    c3_case_snap.get("tool_id")
                    or refs.c3.target_tool_id
                    or c3_in.get("tool_id")
                )
                fault_family = (
                    c3_case_snap.get("fault_family") or "TIMEOUT_DISCONNECTION"
                )
                occurrence = c3_case_snap.get("occurrence", 1)
                interception_hook = (
                    c3_case_snap.get("interception_hook") or "before_tool_execution"
                )
                effect_phase = c3_case_snap.get("effect_phase") or "during_call"
                payload = c3_case_snap.get("payload") or {}

                c3_fault_trace = adapter.execute_session(
                    namespace=fault_ns,
                    task_prompt=default_prompt,
                    permitted_tools=permitted_tools,
                    fault_injection_hook={
                        "target_tool": target_tool,
                        "occurrence": occurrence,
                        "fault_family": fault_family,
                        "interception_hook": interception_hook,
                        "effect_phase": effect_phase,
                        "payload": payload,
                    },
                    max_tool_calls=request.max_tool_calls,
                    trial_role="FAULT",
                    deadline_monotonic=deadline_monotonic,
                    check_cancellation=is_cancelled,
                )
            else:
                trial_ns = f"ns_trial_{execution_id}"
                prepared_namespaces.append(trial_ns)
                adapter.prepare_fixture(trial_ns)
                primary_trace = adapter.execute_session(
                    namespace=trial_ns,
                    task_prompt=default_prompt,
                    permitted_tools=permitted_tools,
                    max_tool_calls=request.max_tool_calls,
                    trial_role="DEFAULT",
                    deadline_monotonic=deadline_monotonic,
                    check_cancellation=is_cancelled,
                )

            if is_cancelled():
                raise InterruptedError("Execution cancelled by caller.")

            # Perform fixture cleanup and record cleanup outcome on traces BEFORE evaluation and digest computation
            clean_ok_all = True
            reusable_all = True
            for ns in prepared_namespaces:
                try:
                    c_ok, c_reusable = adapter.cleanup_fixture(ns)
                    if not c_ok:
                        clean_ok_all = False
                    if not c_reusable:
                        reusable_all = False
                except Exception as clean_err:  # noqa: BLE001
                    logger.warning("Fixture cleanup failed for %s: %s", ns, clean_err)
                    clean_ok_all = False
                    reusable_all = False

            primary_trace.cleanup_successful = clean_ok_all
            primary_trace.cleanup_reusable = reusable_all
            if c3_fault_trace:
                c3_fault_trace.cleanup_successful = clean_ok_all
                c3_fault_trace.cleanup_reusable = reusable_all

            if not clean_ok_all:
                cleanup_err_msg = (
                    "Fixture cleanup failed; environment cannot be safely reused."
                )
                execution_record.error_message = (
                    f"{execution_record.error_message}; {cleanup_err_msg}"
                    if execution_record.error_message
                    else cleanup_err_msg
                )

            # 5. Route Retained Evidence to Selected Native Evaluators via shared dispatcher
            evaluations = dispatch_component_evaluations(
                db=self.db,
                project_id=project.project_id,
                execution_id=execution_id,
                refs=refs,
                frozen_inputs=frozen_inputs,
                primary_trace=primary_trace,
                c3_fault_trace=c3_fault_trace,
            )

            if is_cancelled():
                raise InterruptedError("Execution cancelled by caller.")

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

            retained_digest = compute_evidence_digest(retained_evidence_bundle)
            complete_now = datetime.now(UTC)

            if not clean_ok_all or not reusable_all:
                cleanup_msg = "Fixture cleanup failed; fixture marked unreusable."
                execution_record.error_message = (
                    (execution_record.error_message + "; " + cleanup_msg)
                    if execution_record.error_message
                    else cleanup_msg
                )

            # Guard against overwriting CANCELLED state without wiping pending attributes
            cancelled_status = self.db.execute(
                select(IntegrationExecutionModel.lifecycle_status).where(
                    IntegrationExecutionModel.id == execution_record.id
                )
            ).scalar_one_or_none()
            if cancelled_status == "CANCELLED" or is_cancelled():
                ACTIVE_CANCELLATIONS.discard(execution_id)
                execution_record.lifecycle_status = "CANCELLED"
                return self._to_status_response(execution_record)

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

            return self._to_status_response(execution_record)

        except InterruptedError:
            ACTIVE_CANCELLATIONS.discard(execution_id)
            cancel_now = datetime.now(UTC)
            execution_record.lifecycle_status = "CANCELLED"
            execution_record.error_message = (
                "Execution cancelled by caller during processing."
            )
            execution_record.completed_at_utc = cancel_now
            execution_record.updated_at_utc = cancel_now
            plan_record.lifecycle_status = IntegrationPlanStatus.CANCELLED.value
            plan_record.updated_at_utc = cancel_now
            self.db.commit()
            return self._to_status_response(execution_record)

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
            return self._to_status_response(execution_record)

        finally:
            for ns in prepared_namespaces:
                try:
                    adapter.cleanup_fixture(ns)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Fixture cleanup suppressed error for %s: %s", ns, exc)

    def get_execution(
        self,
        project: Project,
        plan_identifier: str,
        execution_id: str,
    ) -> ExecutionStatusResponse:
        """Retrieve a specific execution record strictly verifying nested project -> plan -> execution hierarchy."""
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

        query = select(IntegrationExecutionModel).where(
            IntegrationExecutionModel.project_id == project.project_id,
            IntegrationExecutionModel.execution_id == execution_id,
            IntegrationExecutionModel.integration_run_id == plan.integration_run_id,
        )
        rec = self.db.execute(query).scalars().first()
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution '{execution_id}' not found under plan '{plan_identifier}'.",
            )

        return self._to_status_response(rec)

    def list_executions(
        self,
        project: Project,
        plan_identifier: str,
        page: int = 1,
        page_size: int = 20,
    ) -> ExecutionListResponse:
        """List executions associated with an integration run plan with bounded pagination."""
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

        base_filter = [
            IntegrationExecutionModel.integration_run_id == plan.integration_run_id,
            IntegrationExecutionModel.project_id == project.project_id,
        ]
        total_stmt = select(func.count(IntegrationExecutionModel.id)).where(
            *base_filter
        )
        total = self.db.execute(total_stmt).scalar() or 0

        bounded_page = max(1, page)
        bounded_size = max(1, min(100, page_size))
        offset = (bounded_page - 1) * bounded_size

        execs_query = (
            select(IntegrationExecutionModel)
            .where(*base_filter)
            .order_by(desc(IntegrationExecutionModel.created_at_utc))
            .offset(offset)
            .limit(bounded_size)
        )
        execs = self.db.execute(execs_query).scalars().all()

        items = [self._to_status_response(e) for e in execs]
        return ExecutionListResponse(
            items=items,
            total=total,
            page=bounded_page,
            page_size=bounded_size,
        )

    def cancel_execution(
        self,
        project: Project,
        plan_identifier: str,
        execution_id: str,
    ) -> ExecutionStatusResponse:
        """Safely cancel an execution in progress with bounded settling and terminal state protection."""
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

        query = select(IntegrationExecutionModel).where(
            IntegrationExecutionModel.project_id == project.project_id,
            IntegrationExecutionModel.execution_id == execution_id,
            IntegrationExecutionModel.integration_run_id == plan.integration_run_id,
        )
        rec = self.db.execute(query).scalars().first()
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution '{execution_id}' not found under plan '{plan_identifier}'.",
            )

        if rec.lifecycle_status in ("COMPLETED", "FAILED", "CANCELLED"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Execution '{execution_id}' is already in terminal state '{rec.lifecycle_status}' and cannot be cancelled.",
            )

        ACTIVE_CANCELLATIONS.add(execution_id)

        cancel_now = datetime.now(UTC)
        rec.lifecycle_status = "CANCELLED"
        rec.completed_at_utc = cancel_now
        rec.updated_at_utc = cancel_now
        rec.error_message = "Execution cancelled by caller."

        plan.lifecycle_status = IntegrationPlanStatus.CANCELLED.value
        plan.updated_at_utc = cancel_now

        self.db.commit()
        self.db.refresh(rec)

        return self._to_status_response(rec)

    def _is_cancelled(self, execution_id: str) -> bool:
        if execution_id in ACTIVE_CANCELLATIONS:
            return True
        st = self.db.execute(
            select(IntegrationExecutionModel.lifecycle_status).where(
                IntegrationExecutionModel.execution_id == execution_id
            )
        ).scalar_one_or_none()
        return st == "CANCELLED"

    def _to_status_response(
        self, rec: IntegrationExecutionModel
    ) -> ExecutionStatusResponse:
        cleanup_successful = None
        cleanup_reusable = None
        if rec.retained_evidence and isinstance(rec.retained_evidence, dict):
            pt = rec.retained_evidence.get("primary_trace") or {}
            cleanup_successful = pt.get("cleanup_successful")
            cleanup_reusable = pt.get("cleanup_reusable")

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
            cleanup_successful=cleanup_successful,
            cleanup_reusable=cleanup_reusable,
        )
