import csv
import io
import json

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.components.c1_tool_call_correctness.contracts.correction import (
    CandidatePatch,
    ReviewRecord,
    VerificationCheckResult,
)
from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CandidateCodeLocation,
    CauseCategory,
)
from app.components.c1_tool_call_correctness.contracts.execution import (
    TraceCompleteness,
)
from app.components.c1_tool_call_correctness.contracts.reporting import (
    WorkflowCaseReportItem,
    WorkflowReportFilter,
    WorkflowRunReport,
    redact_sensitive_fields,
)
from app.components.c1_tool_call_correctness.contracts.results import (
    CaseExecutionStatus,
    CheckLevelResult,
    CorrectnessVerdict,
)
from app.components.c1_tool_call_correctness.models.persistence import (
    C1CaseDiagnosisModel,
    C1CaseExecutionModel,
    C1CorrectionModel,
    C1ExecutionRunModel,
)


class ReportingService:
    """Aggregates end-to-end audit records across configuration, execution, evaluation,
    diagnosis, correction, and review with redaction and pagination."""

    def generate_workflow_report(
        self,
        db: Session,
        report_filter: WorkflowReportFilter,
    ) -> WorkflowRunReport:
        """Builds a paginated, redacted workflow report across all pipeline stages."""
        # 1. Base query for case executions
        query = (
            select(C1CaseExecutionModel)
            .join(
                C1ExecutionRunModel,
                C1CaseExecutionModel.run_id == C1ExecutionRunModel.id,
            )
            .where(C1ExecutionRunModel.project_id == report_filter.project_id)
        )

        if report_filter.run_id:
            query = query.where(C1CaseExecutionModel.run_id == report_filter.run_id)

        if report_filter.suite_id:
            query = query.where(C1ExecutionRunModel.suite_id == report_filter.suite_id)

        if report_filter.verdict:
            query = query.where(
                C1CaseExecutionModel.verdict == report_filter.verdict.value
            )

        # Order by run_id, case_id, attempt_number
        query = query.order_by(
            C1CaseExecutionModel.run_id,
            C1CaseExecutionModel.case_id,
            C1CaseExecutionModel.attempt_number,
        )

        all_matched = db.scalars(query).all()

        # Fetch associated run record if run_id provided
        run_record = None
        if report_filter.run_id:
            run_record = db.get(C1ExecutionRunModel, report_filter.run_id)

        # Pre-fetch explanations, diagnoses, corrections for fast lookup
        run_ids = list({c.run_id for c in all_matched})
        case_ids = list({c.case_id for c in all_matched})

        diagnoses_map: dict[tuple[str, str], C1CaseDiagnosisModel] = {}
        corrections_map: dict[tuple[str, str], C1CorrectionModel] = {}

        if run_ids and case_ids:
            diag_stmt = select(C1CaseDiagnosisModel).where(
                C1CaseDiagnosisModel.run_id.in_(run_ids),
                C1CaseDiagnosisModel.case_id.in_(case_ids),
            )
            for diag in db.scalars(diag_stmt).all():
                diagnoses_map[(diag.run_id, diag.case_id)] = diag

            corr_stmt = select(C1CorrectionModel).where(
                C1CorrectionModel.run_id.in_(run_ids),
                C1CorrectionModel.case_id.in_(case_ids),
            )
            for corr in db.scalars(corr_stmt).all():
                corrections_map[(corr.run_id, corr.case_id)] = corr

        # Build items and apply secondary filters (cause_category, is_verified)
        filtered_items: list[WorkflowCaseReportItem] = []

        total_pass = 0
        total_fail = 0
        total_inconclusive = 0

        code_defects = 0
        agent_defects = 0
        spec_problems = 0
        unknown_causes = 0

        corrections_attempted = 0
        verified_corrections = 0
        accepted_corrections = 0
        rejected_corrections = 0

        for c_model in all_matched:
            # Tally verdict
            v_val = c_model.verdict
            if v_val == CorrectnessVerdict.PASS.value:
                total_pass += 1
            elif v_val == CorrectnessVerdict.FAIL.value:
                total_fail += 1
            elif v_val == CorrectnessVerdict.INCONCLUSIVE.value:
                total_inconclusive += 1

            diag_model = diagnoses_map.get((c_model.run_id, c_model.case_id))
            corr_model = corrections_map.get((c_model.run_id, c_model.case_id))

            # Diagnostic stats
            cause_enum: CauseCategory | None = None
            if diag_model:
                try:
                    cause_enum = CauseCategory(diag_model.cause_category)
                except ValueError:
                    cause_enum = CauseCategory.UNKNOWN

                if cause_enum == CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT:
                    code_defects += 1
                elif cause_enum == CauseCategory.AGENT_BEHAVIOUR:
                    agent_defects += 1
                elif cause_enum == CauseCategory.SPECIFICATION_OR_EXPECTATION_PROBLEM:
                    spec_problems += 1
                else:
                    unknown_causes += 1

            # Correction stats
            if corr_model:
                corrections_attempted += 1
                if corr_model.is_verified:
                    verified_corrections += 1
                rev = corr_model.review or {}
                dec = rev.get("decision")
                if dec == "ACCEPTED":
                    accepted_corrections += 1
                elif dec == "REJECTED":
                    rejected_corrections += 1

            # Secondary filter: cause_category
            if report_filter.cause_category is not None and (
                not cause_enum or cause_enum != report_filter.cause_category
            ):
                continue

            # Secondary filter: is_verified
            if report_filter.is_verified is not None:
                corr_is_ver = corr_model.is_verified if corr_model else False
                if corr_is_ver != report_filter.is_verified:
                    continue

            # Build CheckLevelResult objects
            parsed_checks = []
            for chk in c_model.check_results or []:
                try:
                    parsed_checks.append(CheckLevelResult.model_validate(chk))
                except (ValidationError, ValueError, TypeError, KeyError):
                    pass

            # Build CandidateCodeLocations
            parsed_locs = []
            if diag_model and diag_model.candidate_code_locations:
                for loc in diag_model.candidate_code_locations:
                    try:
                        parsed_locs.append(CandidateCodeLocation.model_validate(loc))
                    except (ValidationError, ValueError, TypeError, KeyError):
                        pass

            # Build VerificationCheckResults
            parsed_ver_checks = []
            if corr_model and corr_model.verification_results:
                for v_chk in corr_model.verification_results:
                    try:
                        parsed_ver_checks.append(
                            VerificationCheckResult.model_validate(v_chk)
                        )
                    except (ValidationError, ValueError, TypeError, KeyError):
                        pass

            candidate_patch = None
            if corr_model and corr_model.candidate_patch:
                try:
                    candidate_patch = CandidatePatch.model_validate(
                        corr_model.candidate_patch
                    )
                except (ValidationError, ValueError, TypeError, KeyError):
                    pass

            review_record = None
            if corr_model and corr_model.review and "decision" in corr_model.review:
                try:
                    review_record = ReviewRecord.model_validate(corr_model.review)
                except (ValidationError, ValueError, TypeError, KeyError):
                    pass

            item = WorkflowCaseReportItem(
                case_id=c_model.case_id,
                suite_id=run_record.suite_id if run_record else None,
                run_id=c_model.run_id,
                attempt_number=c_model.attempt_number,
                session_id=c_model.session_id,
                execution_status=CaseExecutionStatus(c_model.execution_status),
                verdict=CorrectnessVerdict(c_model.verdict),
                trace_completeness=TraceCompleteness(c_model.trace_completeness),
                error_message=c_model.error_message,
                check_results=parsed_checks,
                explanation_summary=diag_model.explanation_summary
                if diag_model
                else None,
                evidence_refs=diag_model.evidence_refs if diag_model else [],
                source_relationship=diag_model.explanation_method
                if diag_model
                else None,
                cause_category=cause_enum,
                diagnosis_confidence=(diag_model.metrics or {}).get("confidence_score")
                if diag_model
                else None,
                candidate_code_locations=parsed_locs,
                diagnosis_evidence_refs=diag_model.evidence_refs if diag_model else [],
                correction_attempted=corr_model is not None,
                candidate_patch=candidate_patch,
                is_verified=corr_model.is_verified if corr_model else False,
                verification_checks=parsed_ver_checks,
                review=review_record,
            )
            filtered_items.append(item)

        total_count = len(filtered_items)
        paginated_items = filtered_items[
            report_filter.offset : report_filter.offset + report_filter.limit
        ]
        has_next = (report_filter.offset + report_filter.limit) < total_count

        return WorkflowRunReport(
            project_id=report_filter.project_id,
            run_id=report_filter.run_id,
            suite_id=run_record.suite_id if run_record else report_filter.suite_id,
            suite_version=run_record.suite_version if run_record else None,
            config_version=None,
            total_cases=len(all_matched),
            passed_cases=total_pass,
            failed_cases=total_fail,
            inconclusive_cases=total_inconclusive,
            total_diagnosed=len(diagnoses_map),
            application_code_defects_count=code_defects,
            agent_behaviour_defects_count=agent_defects,
            specification_problem_count=spec_problems,
            unknown_cause_count=unknown_causes,
            total_corrections_attempted=corrections_attempted,
            verified_corrections_count=verified_corrections,
            accepted_corrections_count=accepted_corrections,
            rejected_corrections_count=rejected_corrections,
            items=paginated_items,
            total_count=total_count,
            limit=report_filter.limit,
            offset=report_filter.offset,
            has_next=has_next,
        )

    def export_report_json(self, report: WorkflowRunReport) -> str:
        """Serializes and redacts workflow report to JSON string."""
        raw_dict = report.model_dump(mode="json")
        redacted_dict = redact_sensitive_fields(raw_dict)
        return json.dumps(redacted_dict, indent=2)

    def export_report_csv(self, report: WorkflowRunReport) -> str:
        """Serializes workflow case records to tabular CSV string."""
        output = io.StringIO()
        fieldnames = [
            "case_id",
            "run_id",
            "verdict",
            "execution_status",
            "error_message",
            "cause_category",
            "diagnosis_confidence",
            "correction_attempted",
            "is_verified",
            "review_decision",
            "reviewer_id",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for item in report.items:
            rev_dec = item.review.decision.value if item.review else "NONE"
            rev_user = (
                (
                    getattr(item.review, "reviewer", None)
                    or getattr(item.review, "reviewer_id", None)
                    or ""
                )
                if item.review
                else ""
            )
            writer.writerow(
                {
                    "case_id": item.case_id,
                    "run_id": item.run_id,
                    "verdict": item.verdict.value,
                    "execution_status": item.execution_status.value,
                    "error_message": item.error_message or "",
                    "cause_category": item.cause_category.value
                    if item.cause_category
                    else "UNLABELLED",
                    "diagnosis_confidence": item.diagnosis_confidence or 0.0,
                    "correction_attempted": str(item.correction_attempted),
                    "is_verified": str(item.is_verified),
                    "review_decision": rev_dec,
                    "reviewer_id": rev_user,
                }
            )

        return output.getvalue()


reporting_service = ReportingService()
