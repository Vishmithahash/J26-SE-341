"""Orchestration service for Phase 5 Policy Change Tracking and Selective Regression."""

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from app.components.c4_policy_aware_safety.contracts.cases import (
    PolicyTestCase,
)
from app.components.c4_policy_aware_safety.contracts.evidence import (
    EvaluationEvidencePackage,
)
from app.components.c4_policy_aware_safety.contracts.execution import (
    IdempotencyConflictError,
)
from app.components.c4_policy_aware_safety.contracts.regression import (
    CaseDecisionAction,
    ExecutionModeType,
    HistoricalReEvaluationRecord,
    PlanLifecycleState,
    PolicyComparisonRecord,
    PolicyComparisonRequest,
    RegressionBatchRecord,
    RegressionPlanRecord,
    RegressionReport,
    VerdictTransition,
    VerdictTransitionType,
)
from app.components.c4_policy_aware_safety.evaluator.engine import (
    DeterministicPolicyEvaluator,
)
from app.components.c4_policy_aware_safety.execution.adapters import (
    C4TargetAdapter,
    SimulatedC4ApplicationAdapter,
)
from app.components.c4_policy_aware_safety.execution.runner import (
    C4ExecutionRunner,
)
from app.components.c4_policy_aware_safety.persistence.repository import (
    C4Repository,
)
from app.components.c4_policy_aware_safety.regression.diff import PolicyDiffEngine
from app.components.c4_policy_aware_safety.regression.impact import (
    PolicyImpactAnalyzer,
)
from app.components.c4_policy_aware_safety.regression.regeneration import (
    RegressionRegenerationService,
)


class C4RegressionService:
    """Orchestrates policy diffing, impact analysis, selective test regeneration, and regression reporting."""

    def __init__(
        self,
        repository: C4Repository | None = None,
        diff_engine: PolicyDiffEngine | None = None,
        impact_analyzer: PolicyImpactAnalyzer | None = None,
        regeneration_service: RegressionRegenerationService | None = None,
        runner: C4ExecutionRunner | None = None,
        evaluator: DeterministicPolicyEvaluator | None = None,
    ) -> None:
        self.repository = repository
        self.diff_engine = diff_engine or PolicyDiffEngine()
        self.impact_analyzer = impact_analyzer or PolicyImpactAnalyzer()
        self.regeneration_service = (
            regeneration_service or RegressionRegenerationService()
        )
        self.runner = runner or C4ExecutionRunner(repository=repository)
        self.evaluator = evaluator or DeterministicPolicyEvaluator()

    # 1. Comparison
    def compare_contracts(
        self, request: PolicyComparisonRequest
    ) -> PolicyComparisonRecord:
        """Compare two accepted policy contracts and persist comparison record."""
        if not self.repository:
            raise RuntimeError("Repository required to compare contracts.")

        baseline = self.repository.get_contract(
            request.project_id,
            request.baseline_contract_id,
            request.baseline_contract_version,
        )
        if not baseline:
            raise ValueError(
                f"Baseline contract '{request.baseline_contract_id}' v{request.baseline_contract_version} not found in project '{request.project_id}'."
            )

        candidate = self.repository.get_contract(
            request.project_id,
            request.candidate_contract_id,
            request.candidate_contract_version,
        )
        if not candidate:
            raise ValueError(
                f"Candidate contract '{request.candidate_contract_id}' v{request.candidate_contract_version} not found in project '{request.project_id}'."
            )

        comparison = self.diff_engine.compare_contracts(
            request, baseline, candidate
        )
        self.repository.save_policy_comparison(comparison)
        return comparison

    # 2. Impact Planning
    def create_regression_plan(
        self,
        project_id: str,
        comparison_id: str,
        binding_id: str,
        binding_version: int,
    ) -> RegressionPlanRecord:
        """Build a typed regression plan with impact decisions for all baseline cases."""
        if not self.repository:
            raise RuntimeError("Repository required for regression planning.")

        comparison = self.repository.get_policy_comparison(
            project_id, comparison_id
        )
        if not comparison:
            raise ValueError(
                f"Comparison '{comparison_id}' not found in project '{project_id}'."
            )

        candidate = self.repository.get_contract(
            project_id,
            comparison.candidate_contract_id,
            comparison.candidate_contract_version,
        )
        if not candidate:
            raise ValueError(
                f"Candidate contract '{comparison.candidate_contract_id}' v{comparison.candidate_contract_version} not found."
            )

        binding = self.repository.get_domain_binding(
            project_id, binding_id, binding_version
        )
        if not binding:
            raise ValueError(
                f"Domain binding '{binding_id}' v{binding_version} not found."
            )

        # Only the baseline contract's cases (a project can hold cases of several contracts).
        baseline_cases = [
            c
            for c in self.repository.list_test_cases(project_id)
            if c.contract_id == comparison.baseline_contract_id
            and c.contract_version == comparison.baseline_contract_version
        ]

        decisions = self.impact_analyzer.analyze_impact(
            comparison, candidate, baseline_cases, binding
        )

        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        raw_plan_input = f"{project_id}:{comparison_id}:{candidate.content_hash}:{binding.content_hash}:{len(decisions)}"
        plan_digest = hashlib.sha256(raw_plan_input.encode("utf-8")).hexdigest()

        plan = RegressionPlanRecord(
            plan_id=plan_id,
            project_id=project_id,
            comparison_id=comparison_id,
            baseline_contract_id=comparison.baseline_contract_id,
            baseline_contract_version=comparison.baseline_contract_version,
            candidate_contract_id=comparison.candidate_contract_id,
            candidate_contract_version=comparison.candidate_contract_version,
            binding_id=binding_id,
            binding_version=binding_version,
            status=PlanLifecycleState.DRAFT,
            case_decisions=decisions,
            proposed_replacement_cases=[],
            retained_cases=[
                d.case_id
                for d in decisions
                if d.action == CaseDecisionAction.RETAIN
            ],
            retired_cases=[
                d.case_id
                for d in decisions
                if d.action == CaseDecisionAction.RETIRE
            ],
            readiness_gaps=[],
            dependency_hashes={
                "candidate_contract": candidate.content_hash,
                "binding": binding.content_hash,
            },
            plan_digest=plan_digest,
            created_at=datetime.now(UTC),
        )

        self.repository.save_regression_plan(plan)
        return plan

    # 3. Selective Regeneration & Validation
    def regenerate_plan(
        self,
        project_id: str,
        plan_id: str,
    ) -> tuple[RegressionPlanRecord, list[PolicyTestCase]]:
        """Regenerate and validate affected cases according to the plan."""
        if not self.repository:
            raise RuntimeError("Repository required for regeneration.")

        plan = self.repository.get_regression_plan(project_id, plan_id)
        if not plan:
            raise ValueError(
                f"Regression plan '{plan_id}' not found in project '{project_id}'."
            )

        candidate = self.repository.get_contract(
            project_id,
            plan.candidate_contract_id,
            plan.candidate_contract_version,
        )
        if not candidate:
            raise ValueError(
                f"Candidate contract '{plan.candidate_contract_id}' v{plan.candidate_contract_version} not found."
            )

        binding = self.repository.get_domain_binding(
            project_id, plan.binding_id, plan.binding_version
        )
        if not binding:
            raise ValueError(
                f"Domain binding '{plan.binding_id}' v{plan.binding_version} not found."
            )

        baseline_cases = self.repository.list_test_cases(project_id)

        updated_plan, replacement_cases = (
            self.regeneration_service.regenerate_and_revalidate(
                plan, candidate, binding, baseline_cases
            )
        )

        for case in replacement_cases:
            existing = self.repository.get_test_case(project_id, case.case_id, case.case_version)
            # A later plan for the same contract change yields the same frozen replacement; reuse it.
            if existing is not None and existing.content_hash == case.content_hash:
                continue
            self.repository.save_test_case(case)

        self.repository.save_regression_plan(updated_plan)
        return updated_plan, replacement_cases

    # 4. Freeze Plan
    def freeze_plan(self, project_id: str, plan_id: str) -> RegressionPlanRecord:
        """Freeze a validated regression plan into an immutable execution snapshot."""
        if not self.repository:
            raise RuntimeError("Repository required for plan freezing.")

        plan = self.repository.get_regression_plan(project_id, plan_id)
        if not plan:
            raise ValueError(
                f"Regression plan '{plan_id}' not found in project '{project_id}'."
            )

        if plan.status == PlanLifecycleState.FROZEN:
            return plan

        if plan.readiness_gaps:
            raise ValueError(
                f"Cannot freeze regression plan with active readiness gaps: {'; '.join(plan.readiness_gaps)}"
            )

        plan.status = PlanLifecycleState.FROZEN
        plan.frozen_at = datetime.now(UTC)
        self.repository.save_regression_plan(plan)
        return plan

    # 5. Selective Execution
    def execute_plan(
        self,
        project_id: str,
        plan_id: str,
        adapter: C4TargetAdapter | None = None,
        execution_mode: ExecutionModeType = ExecutionModeType.FRESH_EXECUTION,
        idempotency_key: str | None = None,
    ) -> tuple[RegressionBatchRecord, RegressionReport]:
        """Selectively execute only affected replacement cases in the frozen plan."""
        if not self.repository:
            raise RuntimeError("Repository required for plan execution.")

        plan = self.repository.get_regression_plan(project_id, plan_id)
        if not plan:
            raise ValueError(
                f"Regression plan '{plan_id}' not found in project '{project_id}'."
            )

        if plan.status != PlanLifecycleState.FROZEN:
            raise ValueError(
                f"Cannot execute plan in state '{plan.status.value}'. Only FROZEN plans can be executed."
            )

        candidate = self.repository.get_contract(
            project_id,
            plan.candidate_contract_id,
            plan.candidate_contract_version,
        )
        if not candidate:
            raise ValueError("Candidate contract not found.")

        binding = self.repository.get_domain_binding(
            project_id, plan.binding_id, plan.binding_version
        )
        if not binding:
            raise ValueError("Domain binding not found.")

        if adapter is None:
            adapter = SimulatedC4ApplicationAdapter()

        # Idempotency check for batch execution
        request_digest = hashlib.sha256(
            f"{project_id}:{plan_id}:{adapter.adapter_id}:{execution_mode.value}:{','.join(sorted(plan.proposed_replacement_cases))}".encode()
        ).hexdigest()

        if idempotency_key:
            existing_batch = self.repository.get_regression_batch_by_idempotency(
                project_id, idempotency_key
            )
            if existing_batch:
                if (
                    existing_batch.request_digest
                    and existing_batch.request_digest != request_digest
                ):
                    raise IdempotencyConflictError(
                        f"Idempotency key '{idempotency_key}' previously used with different batch parameters."
                    )
                report = existing_batch.report or self.get_regression_report(
                    project_id, plan_id
                )
                return existing_batch, report

        batch_id = f"batch-{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)

        executed_run_ids: list[str] = []
        reused_run_ids: list[str] = []
        historical_re_eval_ids: list[str] = []
        verdict_transitions: list[VerdictTransition] = []
        all_findings: list[dict[str, Any]] = []
        inj_target_findings: list[dict[str, Any]] = []
        attempt_goals: dict[str, int] = {}
        commit_goals: dict[str, int] = {}
        benign_utils: dict[str, int] = {}
        readiness_failures: list[str] = []

        # Find replacement cases to execute
        replacement_cases = [
            self.repository.get_test_case(project_id, case_id)
            for case_id in plan.proposed_replacement_cases
        ]
        valid_replacements = [c for c in replacement_cases if c is not None]

        # 1. Fresh execution of replaced cases
        if execution_mode == ExecutionModeType.FRESH_EXECUTION:
            for rep_case in valid_replacements:
                try:
                    case_idem = (
                        f"{idempotency_key}-{rep_case.case_id}"
                        if idempotency_key
                        else None
                    )
                    run_record = self.runner.execute_case(
                        case=rep_case,
                        contract=candidate,
                        binding=binding,
                        adapter=adapter,
                        idempotency_key=case_idem,
                    )
                    executed_run_ids.append(run_record.run_id)

                    # Gather outcomes
                    att_goal = getattr(
                        run_record.attempt_goal_outcome, "value", "NOT_APPLICABLE"
                    )
                    attempt_goals[att_goal] = attempt_goals.get(att_goal, 0) + 1

                    com_goal = getattr(
                        run_record.commit_goal_outcome, "value", "NOT_APPLICABLE"
                    )
                    commit_goals[com_goal] = commit_goals.get(com_goal, 0) + 1

                    b_util = getattr(
                        run_record.task_utility_outcome, "value", "UNKNOWN"
                    )
                    benign_utils[b_util] = benign_utils.get(b_util, 0) + 1

                    if run_record.injection_target_verdict:
                        inj_target_findings.append(
                            {
                                "case_id": rep_case.case_id,
                                "injection_target_verdict": run_record.injection_target_verdict,
                            }
                        )

                    all_findings.extend(run_record.findings)

                    # Determine baseline verdict for predecessor
                    pred_verdict = None
                    if getattr(rep_case, "predecessor_case_id", None):
                        pred_runs = self.repository.get_execution_runs_by_case(
                            project_id, rep_case.predecessor_case_id
                        )
                        if pred_runs:
                            pred_verdict = pred_runs[0].policy_verdict  # newest first

                    trans_type = self._classify_verdict_transition(
                        pred_verdict, run_record.policy_verdict
                    )
                    rep_rule_id = getattr(
                        rep_case, "target_rule_id", getattr(rep_case, "rule_id", "")
                    )
                    rep_desc = getattr(
                        rep_case, "legitimate_task", getattr(rep_case, "description", "")
                    )
                    is_req_change = (
                        trans_type == VerdictTransitionType.PASS_TO_FAIL
                        and "threshold" in rep_desc.lower()
                    )
                    verdict_transitions.append(
                        VerdictTransition(
                            case_id=rep_case.case_id,
                            rule_id=rep_rule_id,
                            baseline_verdict=pred_verdict,
                            candidate_verdict=run_record.policy_verdict,
                            transition_type=trans_type,
                            explanation=(
                                f"Transition {trans_type.value}: baseline verdict {pred_verdict}, candidate verdict {run_record.policy_verdict}."
                                if not is_req_change
                                else f"Verdict transition caused by stricter candidate policy requirement ({rep_rule_id}), not necessarily agent behavioral regression."
                            ),
                            is_requirement_change=is_req_change,
                        )
                    )

                except Exception as e:  # noqa: BLE001
                    readiness_failures.append(
                        f"Execution failed for case '{rep_case.case_id}': {e}"
                    )

        # 2. Re-evaluating historical evidence if requested
        elif execution_mode == ExecutionModeType.HISTORICAL_RE_EVALUATION:
            for rep_case in valid_replacements:
                pred_id = getattr(rep_case, "predecessor_case_id", None) or rep_case.case_id
                pred_runs = self.repository.get_execution_runs_by_case(
                    project_id, pred_id
                )
                if pred_runs:
                    last_run = pred_runs[0]  # newest first
                    rep_rule_id = getattr(
                        rep_case, "target_rule_id", getattr(rep_case, "rule_id", "")
                    )
                    # Re-score the retained evidence under the candidate contract. Runs recorded
                    # before evidence packages were retained cannot be re-scored: INCONCLUSIVE.
                    package = (last_run.evaluation_report_summary or {}).get("evidence_package")
                    if package:
                        target_ids = rep_case.target_rule_ids or (
                            [rep_case.target_rule_id] if rep_case.target_rule_id else None
                        )
                        re_report = self.runner.evaluator.evaluate_contract(
                            candidate,
                            EvaluationEvidencePackage.model_validate(package),
                            target_rule_ids=target_ids,
                        )
                        derived_verdict = re_report.overall_verdict.value
                        derived_findings = [f.model_dump(mode="json") for f in re_report.findings]
                        re_eval_note = (
                            f"Re-scored retained evidence of run {last_run.run_id} under candidate contract "
                            f"v{plan.candidate_contract_version} without fresh agent execution."
                        )
                    else:
                        derived_verdict = "INCONCLUSIVE"
                        derived_findings = []
                        re_eval_note = (
                            f"Run {last_run.run_id} has no retained evidence package; it cannot be re-scored "
                            "under the candidate contract (run the case fresh instead)."
                        )
                    # Create immutable HistoricalReEvaluationRecord
                    re_eval_record = HistoricalReEvaluationRecord(
                        re_eval_id=f"reeval-{uuid.uuid4().hex[:12]}",
                        project_id=project_id,
                        source_run_id=last_run.run_id,
                        source_evidence_references=[last_run.run_id],
                        original_contract_id=plan.baseline_contract_id,
                        original_contract_version=plan.baseline_contract_version,
                        candidate_contract_id=plan.candidate_contract_id,
                        candidate_contract_version=plan.candidate_contract_version,
                        evaluator_version="3-valued-kleene-v1",
                        evaluator_config_digest=getattr(candidate, "content_hash", "default"),
                        derived_policy_verdict=derived_verdict,
                        derived_findings=derived_findings,
                        analysis_mode="HISTORICAL_RE_EVALUATION",
                        explanation=re_eval_note,
                        created_at=datetime.now(UTC),
                    )
                    self.repository.save_historical_re_evaluation(re_eval_record)
                    historical_re_eval_ids.append(re_eval_record.re_eval_id)
                    verdict_transitions.append(
                        VerdictTransition(
                            case_id=rep_case.case_id,
                            rule_id=rep_rule_id,
                            baseline_verdict=last_run.policy_verdict,
                            candidate_verdict=derived_verdict,
                            transition_type=self._classify_verdict_transition(
                                last_run.policy_verdict, derived_verdict
                            ),
                            explanation=re_eval_record.explanation,
                            is_requirement_change=False,
                        )
                    )

        # For unaffected retained cases, record as reused
        for ret_id in plan.retained_cases:
            runs = self.repository.get_execution_runs_by_case(project_id, ret_id)
            if runs:
                reused_run_ids.append(runs[0].run_id)  # newest first

        # Build Regression Report
        comparison = self.repository.get_policy_comparison(
            project_id, plan.comparison_id
        )
        diff_summary = comparison.summary if comparison else {}

        impact_summary = {
            "definitely_affected": sum(
                1
                for d in plan.case_decisions
                if d.impact_level.value == "DEFINITELY_AFFECTED"
            ),
            "possibly_affected": sum(
                1
                for d in plan.case_decisions
                if d.impact_level.value == "POSSIBLY_AFFECTED"
            ),
            "unaffected": sum(
                1
                for d in plan.case_decisions
                if d.impact_level.value == "UNAFFECTED"
            ),
            "regenerate_count": sum(
                1 for d in plan.case_decisions if d.action.value == "REGENERATE"
            ),
            "revalidate_count": sum(
                1 for d in plan.case_decisions if d.action.value == "REVALIDATE"
            ),
            "revise_count": sum(
                1 for d in plan.case_decisions if d.action.value == "REVISE"
            ),
            "retire_count": len(plan.retired_cases),
            "retain_count": len(plan.retained_cases),
            "replacement_count": len(plan.proposed_replacement_cases),
            "blocked_count": sum(
                1 for d in plan.case_decisions if d.action.value == "BLOCKED"
            ),
            "needs_review_count": sum(
                1 for d in plan.case_decisions if d.action.value == "NEEDS_REVIEW"
            ),
        }

        exec_summary = {
            "executed_cases_count": len(executed_run_ids),
            "reused_historical_count": len(reused_run_ids),
            "historical_re_eval_count": len(historical_re_eval_ids),
            "readiness_failures_count": len(readiness_failures),
        }

        # Calculate explicit denominators
        baseline_cases_count = len(plan.case_decisions)
        candidate_cases_count = len(plan.retained_cases) + len(
            plan.proposed_replacement_cases
        )

        report = RegressionReport(
            report_id=f"rep-{uuid.uuid4().hex[:12]}",
            project_id=project_id,
            plan_id=plan_id,
            comparison_id=plan.comparison_id,
            baseline_contract_id=plan.baseline_contract_id,
            baseline_contract_version=plan.baseline_contract_version,
            candidate_contract_id=plan.candidate_contract_id,
            candidate_contract_version=plan.candidate_contract_version,
            diff_summary=diff_summary,
            impact_summary=impact_summary,
            execution_summary=exec_summary,
            verdict_transitions=verdict_transitions,
            per_rule_findings=all_findings,
            injection_target_findings=inj_target_findings,
            attempt_goal_outcomes=attempt_goals,
            commit_goal_outcomes=commit_goals,
            benign_utility_summary=benign_utils,
            readiness_failures=readiness_failures,
            baseline_denominator=baseline_cases_count,
            candidate_denominator=candidate_cases_count,
            created_at=datetime.now(UTC),
        )

        batch = RegressionBatchRecord(
            batch_id=batch_id,
            project_id=project_id,
            plan_id=plan_id,
            candidate_contract_id=plan.candidate_contract_id,
            candidate_contract_version=plan.candidate_contract_version,
            adapter_id=adapter.adapter_id,
            execution_mode=execution_mode,
            executed_run_ids=executed_run_ids,
            reused_run_ids=reused_run_ids,
            historical_re_eval_ids=historical_re_eval_ids,
            status="COMPLETED" if not readiness_failures else "PARTIAL",
            report=report,
            idempotency_key=idempotency_key,
            request_digest=request_digest,
            created_at=now,
            completed_at=datetime.now(UTC),
        )

        self.repository.save_regression_batch(batch)
        return batch, report

    def get_regression_report(
        self, project_id: str, plan_id: str
    ) -> RegressionReport | None:
        """Retrieve existing regression report for plan."""
        if not self.repository:
            return None
        batch = self.repository.get_latest_regression_batch(project_id, plan_id)
        if batch and batch.report:
            return batch.report
        return None

    def _classify_verdict_transition(
        self, baseline_verdict: str | None, candidate_verdict: str
    ) -> VerdictTransitionType:
        if baseline_verdict is None:
            return VerdictTransitionType.NEW_COVERAGE
        # NOT_EXERCISED / ERROR / unknown are not passes: they count as INCONCLUSIVE here
        # (previously every unmatched pair, e.g. NOT_EXERCISED -> FAIL, was labelled PASS_TO_PASS).
        definite = ("PASS", "FAIL")
        b = baseline_verdict.upper() if baseline_verdict.upper() in definite else "INCONCLUSIVE"
        c = candidate_verdict.upper() if candidate_verdict.upper() in definite else "INCONCLUSIVE"
        if b == "PASS" and c == "PASS":
            return VerdictTransitionType.PASS_TO_PASS
        if b == "PASS" and c == "FAIL":
            return VerdictTransitionType.PASS_TO_FAIL
        if b == "FAIL" and c == "PASS":
            return VerdictTransitionType.FAIL_TO_PASS
        if b == "FAIL" and c == "FAIL":
            return VerdictTransitionType.FAIL_TO_FAIL
        if b == "PASS" and c == "INCONCLUSIVE":
            return VerdictTransitionType.PASS_TO_INCONCLUSIVE
        if b == "FAIL" and c == "INCONCLUSIVE":
            return VerdictTransitionType.FAIL_TO_INCONCLUSIVE
        if b == "INCONCLUSIVE" and c == "PASS":
            return VerdictTransitionType.INCONCLUSIVE_TO_PASS
        if b == "INCONCLUSIVE" and c == "FAIL":
            return VerdictTransitionType.INCONCLUSIVE_TO_FAIL
        return VerdictTransitionType.INCONCLUSIVE_TO_INCONCLUSIVE
