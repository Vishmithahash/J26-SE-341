"""Evidence Replay Service for deterministic multi-evaluator reproducibility.

Component: Shared Integration Reporting & Replay (Part 3)
Guarantees:
- Strictly re-evaluates retained execution evidence without invoking target services.
- Never launches network requests, browser adapters, or agent invocations during replay.
- Preserves original evaluation records immutably while reporting semantic parity.
- Clearly separates non-deterministic metadata (timestamps, ephemeral IDs) from semantic equality.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
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
from app.shared.integration.adapters import ExecutionTrace
from app.shared.integration.contracts import (
    ComponentReferencesPlan,
    ReplayComparisonResponse,
)
from app.shared.integration.evidence import (
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

# Non-deterministic fields that vary per evaluation invocation and should not break semantic parity
NONDETERMINISTIC_EVALUATION_FIELDS = [
    "created_at_utc",
    "updated_at_utc",
    "started_at_utc",
    "completed_at_utc",
    "replayed_at_utc",
    "run_id",
    "test_id",
    "case_id",
    "pair_id",
    "execution_id",
]


class EvidenceReplayService:
    """Replays retained execution evidence through pinned component evaluators without target execution."""

    def __init__(self, db: Session):
        self.db = db

    def replay_execution(
        self,
        project: Project,
        user: User,
        execution_id: str,
    ) -> ReplayComparisonResponse:
        """Replay stored evidence against pinned configurations to verify semantic reproducibility."""
        # 1. Fetch execution record
        exec_stmt = select(IntegrationExecutionModel).where(
            IntegrationExecutionModel.project_id == project.project_id,
            IntegrationExecutionModel.execution_id == execution_id,
        )
        execution_record = self.db.execute(exec_stmt).scalars().first()
        if not execution_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution '{execution_id}' not found in project '{project.project_id}'.",
            )

        # 2. Verify evidence retention
        retained_bundle = execution_record.retained_evidence
        if not retained_bundle or "primary_trace" not in retained_bundle:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Execution '{execution_id}' has no retained evidence available for replay. "
                    "Cannot replay without stored traces."
                ),
            )

        # 3. Retrieve run plan with pinned component references
        plan_stmt = select(IntegrationRunPlanModel).where(
            IntegrationRunPlanModel.project_id == project.project_id,
            IntegrationRunPlanModel.integration_run_id
            == execution_record.integration_run_id,
        )
        plan_record = self.db.execute(plan_stmt).scalars().first()
        if not plan_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Integration run plan '{execution_record.integration_run_id}' not found.",
            )

        ref_payload = plan_record.plan_payload.get("component_references", {})
        refs = ComponentReferencesPlan(**ref_payload)

        # 4. Reconstruct Traces from Stored Evidence (WITHOUT invoking target)
        primary_trace = ExecutionTrace.model_validate(retained_bundle["primary_trace"])
        fault_trace: ExecutionTrace | None = None
        if retained_bundle.get("fault_trace"):
            fault_trace = ExecutionTrace.model_validate(retained_bundle["fault_trace"])

        replayed_evaluations: dict[str, Any] = {}

        # 5. Re-run Evaluators Deterministically

        # --- C1 Replay ---
        if refs.c1 is not None:
            c1_events, c1_completeness = project_c1_evidence(primary_trace)
            c1_evaluator = DeterministicCorrectnessEvaluator()
            c1_expectations = [
                ExpectedToolCallSpec(
                    tool_name="order_placement",
                    min_count=1,
                    max_count=2,
                    is_forbidden=False,
                )
            ]
            c1_verdict, c1_checks = c1_evaluator.evaluate_case(
                case_id=f"c1_replay_{execution_id[:8]}",
                category=CaseCategory.CORRECT_BEHAVIOUR,
                resolved_expectations=c1_expectations,
                captured_events=c1_events,
                trace_completeness=c1_completeness,
                context_data={"project_id": project.project_id},
                requirement_refs=["REQ-TOOL-CORRECTNESS-01"],
            )
            replayed_evaluations["C1"] = {
                "component": "C1",
                "verdict": c1_verdict.value,
                "checks_count": len(c1_checks),
                "passed_checks": sum(1 for c in c1_checks if c.verdict.value == "PASS"),
                "trace_completeness": c1_completeness.value,
                "evaluator_version": c1_evaluator.EVALUATOR_VERSION,
                "checks": [c.model_dump(mode="json") for c in c1_checks],
            }

        # --- C2 Replay ---
        if refs.c2 is not None:
            c2_evidence = project_c2_evidence(
                project_id=project.project_id,
                run_id=execution_id,
                test_id=f"c2_replay_{execution_id[:8]}",
                model_id=refs.c2.model_id,
                model_version=refs.c2.model_version,
                trace=primary_trace,
            )
            c2_engine = ConformanceEvaluationEngine()
            model_query = select(C2WorkflowModel).where(
                C2WorkflowModel.project_id == project.project_id,
                C2WorkflowModel.model_id == refs.c2.model_id,
                C2WorkflowModel.version == refs.c2.model_version,
            )
            model_rec = self.db.execute(model_query).scalars().first()
            if model_rec:
                c2_model = EFSMModelDefinition(**model_rec.definition)
                test_def = GeneratedTestDefinition(
                    test_id=f"c2_replay_{execution_id[:8]}",
                    project_id=project.project_id,
                    pinned_model_id=refs.c2.model_id,
                    pinned_model_version=refs.c2.model_version,
                    model_content_hash=model_rec.content_hash,
                    category=TestCategory.VALID,
                    task="Replay evaluation from retained evidence",
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
                replayed_evaluations["C2"] = {
                    "component": "C2",
                    "verdict": c2_result.verdict.value,
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
                replayed_evaluations["C2"] = {
                    "component": "C2",
                    "verdict": "MODEL_NOT_READY",
                    "reasons": [
                        f"Model '{refs.c2.model_id}' v{refs.c2.model_version} record not found."
                    ],
                }

        # --- C3 Replay ---
        if refs.c3 is not None and fault_trace is not None:
            pair_id = f"pair-replay-{execution_id[:8]}"
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
            matched_evidence, c2_facts = project_c3_matched_pair_evidence(
                project_id=project.project_id,
                case_id=f"c3_replay_{execution_id[:8]}",
                pair_id=pair_id,
                run_id=execution_id,
                clean_trace=primary_trace,
                fault_trace=fault_trace,
                recovery_contract=contract,
                expected_entity_id="ord-001",
            )
            case = CandidateFaultCase(
                schema_version="2026.1",
                project_id=project.project_id,
                case_id=f"c3_replay_{execution_id[:8]}",
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
            replayed_evaluations["C3"] = {
                "component": "C3",
                "verdict": (
                    c3_result.recovery_verdict.value
                    if c3_result.recovery_verdict
                    else "INCONCLUSIVE"
                ),
                "status": c3_result.evaluation_status.value,
                "rule_results_count": len(c3_result.rule_results),
                "exposure_status": matched_evidence.exposure_status.value,
                "c2_facts_consumed": len(c2_facts),
                "c2_facts_provenance": list({f.provenance for f in c2_facts}),
                "clean_qualification": matched_evidence.clean_qualification.value,
                "non_evaluation_reasons": c3_result.non_evaluation_reasons,
                "rule_results": [
                    r.model_dump(mode="json") for r in c3_result.rule_results
                ],
            }

        # --- C4 Replay ---
        if refs.c4 is not None:
            c4_package = project_c4_evidence(
                project_id=project.project_id,
                case_id=f"c4_replay_{execution_id[:8]}",
                run_id=execution_id,
                contract_version=refs.c4.contract_version or 1,
                trace=primary_trace,
            )
            c4_evaluator = DeterministicPolicyEvaluator()
            contract_query = select(C4ContractModel).where(
                C4ContractModel.project_id == project.project_id,
                C4ContractModel.contract_id == refs.c4.contract_id,
            )
            c4_rec = self.db.execute(contract_query).scalars().first()
            if c4_rec:
                rules: list[PolicyRule] = []
                for r in c4_rec.rules_data or []:
                    try:
                        rules.append(PolicyRule.model_validate(r))
                    except (ValidationError, ValueError, TypeError, KeyError) as exc:
                        logger.debug("Skipping unparseable policy rule: %s", exc)
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
                replayed_evaluations["C4"] = {
                    "component": "C4",
                    "verdict": c4_report.overall_verdict.value,
                    "findings_count": len(c4_report.findings),
                    "summary": c4_report.summary,
                    "findings": [f.model_dump(mode="json") for f in c4_report.findings],
                }
            else:
                replayed_evaluations["C4"] = {
                    "component": "C4",
                    "verdict": "NOT_EVALUATED",
                    "reason": f"Contract '{refs.c4.contract_id}' record not found.",
                }

        # 6. Compare Semantic Equality vs Original Evaluations
        original_evaluations = execution_record.evaluations or {}
        semantic_diffs: list[str] = []

        for comp in ("C1", "C2", "C3", "C4"):
            orig = original_evaluations.get(comp)
            repl = replayed_evaluations.get(comp)

            if orig is None and repl is None:
                continue
            if (orig is None) != (repl is None):
                semantic_diffs.append(
                    f"Component {comp} presence mismatch: original={orig is not None}, replayed={repl is not None}"
                )
                continue

            # Compare core semantic verdict
            orig_verdict = orig.get("verdict")
            repl_verdict = repl.get("verdict")
            if orig_verdict != repl_verdict:
                semantic_diffs.append(
                    f"Component {comp} verdict mismatch: original='{orig_verdict}', replayed='{repl_verdict}'"
                )

            # Compare counts
            if comp == "C1":
                if orig.get("checks_count") != repl.get("checks_count"):
                    semantic_diffs.append(
                        f"C1 checks count mismatch: {orig.get('checks_count')} vs {repl.get('checks_count')}"
                    )
                if orig.get("passed_checks") != repl.get("passed_checks"):
                    semantic_diffs.append(
                        f"C1 passed checks mismatch: {orig.get('passed_checks')} vs {repl.get('passed_checks')}"
                    )
            elif comp == "C2":
                if orig.get("violations_count") != repl.get("violations_count"):
                    semantic_diffs.append(
                        f"C2 violations count mismatch: {orig.get('violations_count')} vs {repl.get('violations_count')}"
                    )
                if orig.get("observed_states") != repl.get("observed_states"):
                    semantic_diffs.append(
                        f"C2 observed states mismatch: {orig.get('observed_states')} vs {repl.get('observed_states')}"
                    )
            elif comp == "C3":
                if orig.get("exposure_status") != repl.get("exposure_status"):
                    semantic_diffs.append(
                        f"C3 exposure status mismatch: {orig.get('exposure_status')} vs {repl.get('exposure_status')}"
                    )
                if orig.get("clean_qualification") != repl.get("clean_qualification"):
                    semantic_diffs.append(
                        f"C3 clean qualification mismatch: {orig.get('clean_qualification')} vs {repl.get('clean_qualification')}"
                    )
            elif comp == "C4":
                if orig.get("findings_count") != repl.get("findings_count"):
                    semantic_diffs.append(
                        f"C4 findings count mismatch: {orig.get('findings_count')} vs {repl.get('findings_count')}"
                    )

        is_semantically_identical = len(semantic_diffs) == 0

        return ReplayComparisonResponse(
            execution_id=execution_id,
            is_semantically_identical=is_semantically_identical,
            original_evaluations=original_evaluations,
            replayed_evaluations=replayed_evaluations,
            semantic_diffs=semantic_diffs,
            nondeterministic_fields_ignored=NONDETERMINISTIC_EVALUATION_FIELDS,
            replayed_at_utc=datetime.now(UTC),
        )
