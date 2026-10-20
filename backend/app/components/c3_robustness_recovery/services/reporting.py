"""Backend reporting service for Component 3 Phase 5.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 5 - Shared persistence, execution tracking, results and reporting.
"""

import csv
import io
from collections import Counter
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.components.c3_robustness_recovery.contracts.evaluation import RecoveryVerdict
from app.components.c3_robustness_recovery.contracts.persistence import (
    ExecutionReportResponse,
    RecoveryVerdictCounts,
)
from app.components.c3_robustness_recovery.models.persistence import (
    C3EvaluationModel,
    C3MatchedPairModel,
)
from app.components.c3_robustness_recovery.repositories.persistence import (
    C3PersistenceRepository,
    EntityNotFoundError,
)


def build_execution_report(
    db: Session, project_id: str, execution_id: str
) -> ExecutionReportResponse:
    """Assemble a comprehensive structured report from persisted records and evaluator outputs.

    Does not compute independent or contradictory verdict logic inside reporting.
    Distinguishes demonstration from live execution.
    Specifies explicit denominators for all counts.
    """
    repo = C3PersistenceRepository(db)

    # 1. Fetch execution record
    exec_model = repo.get_execution(project_id, execution_id)
    if not exec_model:
        raise EntityNotFoundError(
            f"Execution '{execution_id}' does not exist in project '{project_id}'."
        )

    # 2. Fetch enclosing suite
    suite_model = repo.get_suite_by_digest(project_id, exec_model.suite_digest)
    suite_id = suite_model.suite_id if suite_model else exec_model.suite_id

    # 3. Fetch all matched pairs linked to this execution
    pairs_query = (
        select(C3MatchedPairModel)
        .where(
            C3MatchedPairModel.project_id == project_id,
            C3MatchedPairModel.execution_id == execution_id,
        )
        .order_by(C3MatchedPairModel.created_at_utc.asc(), C3MatchedPairModel.id.asc())
    )
    pair_models = list(db.scalars(pairs_query).all())

    # 4. Fetch all evaluations for these pairs
    pair_ids = [p.pair_id for p in pair_models]
    eval_models: list[C3EvaluationModel] = []
    if pair_ids:
        evals_query = select(C3EvaluationModel).where(
            C3EvaluationModel.project_id == project_id,
            C3EvaluationModel.pair_id.in_(pair_ids),
        )
        eval_models = list(db.scalars(evals_query).all())

    # Map pair_id -> latest evaluation
    latest_eval_by_pair: dict[str, C3EvaluationModel] = {}
    for ev in eval_models:
        if (
            ev.pair_id not in latest_eval_by_pair
            or ev.created_at_utc > latest_eval_by_pair[ev.pair_id].created_at_utc
        ):
            latest_eval_by_pair[ev.pair_id] = ev

    # 5. Aggregate metrics
    clean_counts = Counter(p.clean_qualification for p in pair_models)
    exposure_counts = Counter(p.exposure_status for p in pair_models)
    cleanup_counts = Counter(p.cleanup_status for p in pair_models)

    verdict_counter: Counter[str] = Counter()
    not_evaluated_count = 0
    rule_violations: Counter[str] = Counter()
    fact_provenances: set[str] = set()
    demo_notes: list[str] = []
    clean_notes: list[str] = []

    case_reports: list[dict[str, Any]] = []

    for pair in pair_models:
        ev = latest_eval_by_pair.get(pair.pair_id)
        verdict_str: str | None = None
        first_violation: str | None = None

        if ev:
            if ev.recovery_verdict:
                verdict_counter[ev.recovery_verdict] += 1
                verdict_str = ev.recovery_verdict
            else:
                not_evaluated_count += 1

            if ev.first_violated_rule:
                rule_violations[ev.first_violated_rule] += 1
                first_violation = ev.first_violated_rule

            # Extract fact provenances
            if ev.c2_facts_provenance_snapshot:
                for f in ev.c2_facts_provenance_snapshot:
                    prov = f.get("provenance")
                    if prov:
                        fact_provenances.add(prov)

            eval_dict = ev.evaluation_snapshot
            if eval_dict.get("demonstration_limitations"):
                for note in eval_dict["demonstration_limitations"]:
                    if note not in demo_notes:
                        demo_notes.append(note)
            if eval_dict.get("clean_control_limitations"):
                for note in eval_dict["clean_control_limitations"]:
                    if note not in clean_notes:
                        clean_notes.append(note)
        else:
            # Pair executed but not yet evaluated
            not_evaluated_count += 1

        case_reports.append(
            {
                "case_id": pair.case_id,
                "pair_id": pair.pair_id,
                "run_id": pair.run_id,
                "exposure_status": pair.exposure_status,
                "clean_qualification": pair.clean_qualification,
                "cleanup_status": pair.cleanup_status,
                "fault_execution_status": pair.fault_execution_status,
                "recovery_verdict": verdict_str,
                "first_violated_rule": first_violation,
            }
        )

    verdict_breakdown = RecoveryVerdictCounts(
        pass_completed_count=verdict_counter.get(
            RecoveryVerdict.PASS_COMPLETED.value, 0
        ),
        pass_graceful_count=verdict_counter.get(RecoveryVerdict.PASS_GRACEFUL.value, 0),
        fail_count=verdict_counter.get(RecoveryVerdict.FAIL.value, 0),
        inconclusive_count=verdict_counter.get(RecoveryVerdict.INCONCLUSIVE.value, 0),
        not_evaluated_count=not_evaluated_count,
    )

    is_demo = exec_model.target_mode == "DEMONSTRATION"
    if is_demo and not demo_notes:
        demo_notes.append(
            "Evaluation performed in DEMONSTRATION mode against in-memory double. "
            "Does not represent live application accuracy."
        )

    evaluator_ver = eval_models[0].evaluator_version if eval_models else "1.1.0"
    rule_set_ver = eval_models[0].rule_set_version if eval_models else "1.1.0"

    report_id = f"rep-{uuid4().hex[:12]}"

    return ExecutionReportResponse(
        report_id=report_id,
        execution_id=exec_model.execution_id,
        suite_id=suite_id,
        suite_digest=exec_model.suite_digest,
        project_id=project_id,
        target_mode=exec_model.target_mode,
        caller_identity=exec_model.caller_identity,
        status=exec_model.status,
        evaluator_version=evaluator_ver,
        rule_set_version=rule_set_ver,
        generated_at_utc=datetime.now(UTC).isoformat(),
        planned_cases_count=exec_model.planned_cases_count,
        executed_cases_count=exec_model.executed_cases_count,
        blocked_cases_count=exec_model.blocked_cases_count,
        unsupported_cases_count=exec_model.unsupported_cases_count,
        cancelled_cases_count=exec_model.cancelled_cases_count,
        error_cases_count=exec_model.error_cases_count,
        clean_qualified_count=clean_counts.get("QUALIFIED", 0),
        clean_disqualified_count=clean_counts.get("DISQUALIFIED", 0),
        clean_indeterminate_count=clean_counts.get("INDETERMINATE", 0),
        confirmed_exposure_count=exposure_counts.get("CONFIRMED", 0),
        not_triggered_exposure_count=exposure_counts.get("NOT_TRIGGERED", 0),
        unknown_exposure_count=exposure_counts.get("EXPOSURE_UNKNOWN", 0),
        verdict_counts=verdict_breakdown,
        cleanup_verified_count=cleanup_counts.get("CLEANED_AND_VERIFIED", 0),
        cleanup_uncertain_count=cleanup_counts.get("UNCERTAIN", 0),
        rule_violation_counts=dict(rule_violations),
        demonstration_mode=is_demo,
        demonstration_notes=demo_notes,
        clean_control_notes=clean_notes,
        fact_provenances=sorted(fact_provenances),
        case_reports=case_reports,
    )


def export_report_to_csv(report: ExecutionReportResponse) -> str:
    """Format report case results and summary counts as downloadable CSV text."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Metadata Header
    writer.writerow(["# C3 Execution and Recovery Evaluation Report"])
    writer.writerow(["# Report ID", report.report_id])
    writer.writerow(["# Execution ID", report.execution_id])
    writer.writerow(["# Suite ID", report.suite_id])
    writer.writerow(["# Suite Digest", report.suite_digest])
    writer.writerow(["# Project ID", report.project_id])
    writer.writerow(["# Target Mode", report.target_mode])
    writer.writerow(["# Status", report.status])
    writer.writerow(["# Evaluator Version", report.evaluator_version])
    writer.writerow(["# Rule-Set Version", report.rule_set_version])
    writer.writerow(["# Generated At (UTC)", report.generated_at_utc])
    writer.writerow([])

    # Metric Breakdown Summary
    writer.writerow(["Metric", "Count", "Denominator / Context"])
    writer.writerow(
        [
            "Planned Cases",
            report.planned_cases_count,
            report.denominators["planned_cases"],
        ]
    )
    writer.writerow(
        [
            "Executed Cases",
            report.executed_cases_count,
            report.denominators["executed_pairs"],
        ]
    )
    writer.writerow(["Blocked Cases", report.blocked_cases_count, "Readiness blocked"])
    writer.writerow(
        ["Unsupported Cases", report.unsupported_cases_count, "Readiness unsupported"]
    )
    writer.writerow(
        ["Cancelled Cases", report.cancelled_cases_count, "Timed out or halted"]
    )
    writer.writerow(
        ["Error Cases", report.error_cases_count, "Harness execution errors"]
    )
    writer.writerow(
        ["Confirmed Exposures", report.confirmed_exposure_count, "Eligible for verdict"]
    )
    writer.writerow(
        ["Clean Qualified", report.clean_qualified_count, "Baseline clean success"]
    )
    writer.writerow(
        [
            "PASS_COMPLETED",
            report.verdict_counts.pass_completed_count,
            "Task completed under fault",
        ]
    )
    writer.writerow(
        [
            "PASS_GRACEFUL",
            report.verdict_counts.pass_graceful_count,
            "Stopped safely under fault",
        ]
    )
    writer.writerow(
        ["FAIL", report.verdict_counts.fail_count, "Violated recovery rule"]
    )
    writer.writerow(
        [
            "INCONCLUSIVE",
            report.verdict_counts.inconclusive_count,
            "Unknown facts or uncertain settling",
        ]
    )
    writer.writerow(
        [
            "Not Evaluated",
            report.verdict_counts.not_evaluated_count,
            "Ineligible or unscored",
        ]
    )
    writer.writerow([])

    # Case Details Table
    writer.writerow(
        [
            "Case ID",
            "Pair ID",
            "Run ID",
            "Exposure Status",
            "Clean Qualification",
            "Cleanup Status",
            "Fault Execution",
            "Recovery Verdict",
            "First Violated Rule",
        ]
    )

    for c in report.case_reports:
        writer.writerow(
            [
                c.get("case_id", ""),
                c.get("pair_id", ""),
                c.get("run_id", ""),
                c.get("exposure_status", ""),
                c.get("clean_qualification", ""),
                c.get("cleanup_status", ""),
                c.get("fault_execution_status", ""),
                c.get("recovery_verdict") or "None (not evaluated)",
                c.get("first_violated_rule") or "None",
            ]
        )

    return output.getvalue()
