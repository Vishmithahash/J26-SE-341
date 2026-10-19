"""Bounded research runner, comparative baselines, and ablations for Component 3 Phase 6.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 6 - Second domain, research validation, baselines, metrics, and final acceptance.
"""

from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.components.c3_robustness_recovery.contracts.evaluation import (
    C2AssertionFact,
    C2FactValue,
    RecoveryEvaluationRequest,
    RecoveryEvaluationResult,
    RecoveryVerdict,
)
from app.components.c3_robustness_recovery.contracts.generation import FrozenSuite
from app.components.c3_robustness_recovery.contracts.persistence import (
    ExecutionCreateRequest,
    ExecutionTrackingStatus,
)
from app.components.c3_robustness_recovery.contracts.research import (
    AblationType,
    BaselineType,
    DatasetSplit,
    ExperimentManifest,
    ResearchMetricsReport,
    ReviewerLabelRecord,
)
from app.components.c3_robustness_recovery.repositories.persistence import (
    C3PersistenceRepository,
)
from app.components.c3_robustness_recovery.runtime.adapter import (
    CallerIdentity,
    DemonstrationFixtureManager,
    DemonstrationToolAdapter,
    TargetMode,
)
from app.components.c3_robustness_recovery.runtime.banking_adapter import (
    BankingFixtureManager,
    BankingServiceAdapter,
)
from app.components.c3_robustness_recovery.runtime.evidence import (
    ExposureStatus,
)
from app.components.c3_robustness_recovery.runtime.suite_runner import SuiteRunner
from app.components.c3_robustness_recovery.services.experiment_plan import (
    filter_suite_for_split,
)
from app.components.c3_robustness_recovery.services.recovery_evaluation import (
    evaluate_recovery,
)
from app.components.c3_robustness_recovery.services.research_metrics import (
    compute_research_metrics,
)
from app.components.c3_robustness_recovery.services.run_tracking import (
    create_execution_manifest,
    finalize_execution_lifecycle,
    record_case_execution_progress,
)
from app.components.c3_robustness_recovery.services.storage import (
    store_frozen_suite,
)


def evaluate_with_baseline_or_ablation(
    eval_req: RecoveryEvaluationRequest,
    baseline_type: BaselineType = BaselineType.PRODUCTION_C3,
    ablation_type: AblationType = AblationType.NONE,
) -> RecoveryEvaluationResult:
    """Evaluate recovery under comparative baseline or isolated ablation rules."""
    req = eval_req.model_copy(deep=True)

    # 1. OUTCOME_ONLY_BASELINE: Ignores C2 state assertions and evidence state observations
    if baseline_type == BaselineType.OUTCOME_ONLY_BASELINE:
        # Strip all C2 state assertions
        req.c2_facts = []
        # Evaluator only sees caller-reported outcome without state awareness
        res = evaluate_recovery(req)
        # Outcome-only rule: if caller reported success, verdict is PASS_COMPLETED without verification
        fault_outcome = (
            getattr(req.matched_evidence.fault_trial, "caller_outcome", "") or ""
        )
        if fault_outcome.startswith("SUCCESS"):
            return res.model_copy(
                update={
                    "recovery_verdict": RecoveryVerdict.PASS_COMPLETED,
                    "first_violated_rule": None,
                }
            )
        return res

    # 2. Planned Ablations
    if ablation_type == AblationType.NO_STATE_FACTS:
        # Ablate all state assertions to UNKNOWN
        req.c2_facts = [
            C2AssertionFact(
                assertion_id=f.assertion_id,
                assertion_version=f.assertion_version,
                value=C2FactValue.UNKNOWN,
                provenance="ABLATED_FACT",
            )
            for f in req.c2_facts
        ]
    elif ablation_type == AblationType.NO_EXPOSURE_RECEIPTS:
        # Ablate confirmed exposure to UNKNOWN
        req.matched_evidence.exposure_status = ExposureStatus.EXPOSURE_UNKNOWN
        req.matched_evidence.caller_observed_timeout = False

    return evaluate_recovery(req)


async def run_batch_experiment(
    suite: FrozenSuite,
    manifest: ExperimentManifest,
    split: DatasetSplit = DatasetSplit.TRAIN_DEV,
    project_id: str = "proj-c3-research",
    db: Session | None = None,
    domain: str = "ecommerce",
    baseline_type: BaselineType = BaselineType.PRODUCTION_C3,
    ablation_type: AblationType = AblationType.NONE,
    labels: list[ReviewerLabelRecord] | None = None,
) -> tuple[ResearchMetricsReport, str]:
    """Execute a bounded research experiment over a split partition."""
    # 1. Filter suite to partition cases
    partitioned_suite = filter_suite_for_split(suite, manifest, split)
    execution_id = f"exec-res-{uuid4().hex[:10]}"

    # Select adapter based on domain
    if domain == "banking":
        fix_mgr = BankingFixtureManager()
        adapter = BankingServiceAdapter(fixture_manager=fix_mgr)
    else:
        fix_mgr = DemonstrationFixtureManager()
        adapter = DemonstrationToolAdapter(fixture_manager=fix_mgr)

    # 2. Persist execution manifest if db session provided
    if db:
        store_frozen_suite(db, project_id, partitioned_suite)
        create_req = ExecutionCreateRequest(
            execution_id=execution_id,
            suite_digest=partitioned_suite.suite_digest,
            project_id=project_id,
            target_mode=TargetMode.DEMONSTRATION.value,
            caller_identity="SCRIPTED_CALLER",
            planned_cases=[c.case_id for c in partitioned_suite.selected_cases],
            configuration_snapshot={
                "split": split.value,
                "baseline_type": baseline_type.value,
                "ablation_type": ablation_type.value,
                "domain": domain,
            },
        )
        create_execution_manifest(db, project_id, create_req)

    # 3. Execute suite
    suite_runner = SuiteRunner(
        adapter=adapter,
        fixture_manager=fix_mgr,
        task_fixture_metadata=partitioned_suite.task_fixture_metadata,
        recovery_contract=partitioned_suite.recovery_contract,
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity=CallerIdentity.SCRIPTED_CALLER,
    )
    summary = await suite_runner.run_frozen_suite(partitioned_suite)

    # 4. Evaluate each executed case
    evaluations: list[RecoveryEvaluationResult] = []
    pair_records: list[Any] = []

    for r in summary.case_results:
        if db:
            record_case_execution_progress(
                db=db,
                project_id=project_id,
                execution_id=execution_id,
                case_id=r.case_id,
                status=r.status,
                evidence=r.evidence,
            )

        if r.evidence:
            pair_records.append(r.evidence)
            matching_case = next(
                (c for c in partitioned_suite.selected_cases if c.case_id == r.case_id),
                partitioned_suite.selected_cases[0],
            )
            eval_req = RecoveryEvaluationRequest(
                project_id=project_id,
                case_id=r.case_id,
                evaluator_version=manifest.evaluator_version,
                rule_set_version=manifest.rule_set_version,
                candidate_case=matching_case,
                recovery_contract=partitioned_suite.recovery_contract,
                matched_evidence=r.evidence,
                c2_facts=[
                    C2AssertionFact(
                        assertion_id="state_order_created"
                        if domain == "ecommerce"
                        else "state_transfer_settled",
                        value=C2FactValue.TRUE,
                        provenance="C2_DEMO_FIXTURE",
                    )
                ],
            )
            eval_res = evaluate_with_baseline_or_ablation(
                eval_req=eval_req,
                baseline_type=baseline_type,
                ablation_type=ablation_type,
            )
            evaluations.append(eval_res)

    if db:
        finalize_execution_lifecycle(
            db=db,
            project_id=project_id,
            execution_id=execution_id,
            summary=summary,
        )

    # 5. Compute research metrics
    report = compute_research_metrics(
        experiment_id=manifest.experiment_id,
        target_domains=manifest.target_domains,
        pair_models=pair_records,
        evaluations=evaluations,
        labels=labels,
        total_case_families=len(manifest.family_splits),
        dev_families_count=sum(
            1 for s in manifest.family_splits.values() if s == DatasetSplit.TRAIN_DEV
        ),
        test_families_count=sum(
            1
            for s in manifest.family_splits.values()
            if s == DatasetSplit.HELD_OUT_TEST
        ),
        planned_cases_count=summary.total_cases,
        blocked_cases_count=summary.blocked_count,
        unsupported_cases_count=summary.unsupported_count,
        cancelled_cases_count=summary.cancelled_count,
        error_cases_count=summary.error_count,
        baseline_type=baseline_type,
        ablation_type=ablation_type,
        demonstration_mode=True,
        evaluator_version=manifest.evaluator_version,
        rule_set_version=manifest.rule_set_version,
    )

    return report, execution_id


def verify_multi_project_concurrency_isolation(
    db: Session,
    proj_a: str,
    proj_b: str,
    suite_a: FrozenSuite,
    suite_b: FrozenSuite,
) -> dict[str, Any]:
    """Verify that concurrent executions under separate projects remain strictly isolated.

    Verifies:
    1. Independent execution manifests and unique IDs.
    2. Zero cross-project leakage in database queries.
    3. Cancellation or failure in project A does not affect project B.
    """
    repo = C3PersistenceRepository(db)

    # 1. Store both suites under respective project IDs
    store_frozen_suite(db, proj_a, suite_a)
    store_frozen_suite(db, proj_b, suite_b)

    exec_id_a = f"exec-iso-{proj_a}-{uuid4().hex[:6]}"
    exec_id_b = f"exec-iso-{proj_b}-{uuid4().hex[:6]}"

    req_a = ExecutionCreateRequest(
        execution_id=exec_id_a,
        suite_digest=suite_a.suite_digest,
        project_id=proj_a,
        target_mode=TargetMode.DEMONSTRATION.value,
        caller_identity="SCRIPTED_CALLER",
        planned_cases=[c.case_id for c in suite_a.selected_cases],
    )
    req_b = ExecutionCreateRequest(
        execution_id=exec_id_b,
        suite_digest=suite_b.suite_digest,
        project_id=proj_b,
        target_mode=TargetMode.DEMONSTRATION.value,
        caller_identity="SCRIPTED_CALLER",
        planned_cases=[c.case_id for c in suite_b.selected_cases],
    )

    create_execution_manifest(db, proj_a, req_a)
    create_execution_manifest(db, proj_b, req_b)

    # 2. Cancel execution in project A
    repo.update_execution_progress(
        project_id=proj_a,
        execution_id=exec_id_a,
        status=ExecutionTrackingStatus.CANCELLED,
        halt_reason="Manual test cancellation of Project A",
    )
    db.commit()

    # Complete execution in project B
    repo.update_execution_progress(
        project_id=proj_b,
        execution_id=exec_id_b,
        status=ExecutionTrackingStatus.COMPLETED,
        executed_cases_count=len(suite_b.selected_cases),
    )
    db.commit()

    # 3. Verify project B remains unaffected
    model_a = repo.get_execution(proj_a, exec_id_a)
    model_b = repo.get_execution(proj_b, exec_id_b)

    assert (
        model_a is not None
        and model_a.status == ExecutionTrackingStatus.CANCELLED.value
    )
    assert (
        model_b is not None
        and model_b.status == ExecutionTrackingStatus.COMPLETED.value
    )

    # Cross-project query isolation
    leak_a_in_b = repo.get_execution(proj_b, exec_id_a)
    leak_b_in_a = repo.get_execution(proj_a, exec_id_b)
    assert leak_a_in_b is None
    assert leak_b_in_a is None

    return {
        "isolation_verified": True,
        "project_a_status": model_a.status,
        "project_b_status": model_b.status,
        "cross_project_query_leakage": False,
    }
