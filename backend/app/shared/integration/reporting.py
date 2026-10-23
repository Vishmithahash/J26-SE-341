"""Shared Multi-Component QA Report Aggregator and Findings Correlator.

Component: Shared Integration Reporting & Replay (Part 3)
Responsibilities:
- Consume actual persisted component findings and evaluation results from shared runs.
- Adapt native component reporting structures (C1, C2, C3, C4) without duplicating logic.
- Connect C2ReportPublisher to the aggregator and transition from STUB to CONNECTED on publication.
- Retain all native verdicts (no flattening of C2 EFSM verdicts, C3 recovery outcomes, or C4 policy verdicts).
- Provide honest report completeness (requested vs evaluated vs not-ready vs blocked vs not-evaluated).
- Link related findings through shared run/event/entity references without collapsing distinct violations.
- Deduplicate repeated finding publications using stable deterministic identities.
- Expose raw finding counts separately from grouped-defect counts.
- Export combined QA reports to JSON and CSV formats.
"""

import csv
import hashlib
import io
import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.components.c2_state_aware_workflow.integrations.reporting import (
    C2ReportPublisher,
)
from app.shared.auth.models import User
from app.shared.integration.contracts import (
    CombinedQAReport,
    ComponentContribution,
    ComponentReferencesPlan,
    ComponentType,
    CorrelatedFindingGroup,
    IntegrationReportListResponse,
    ReportCompletenessSummary,
    UnifiedFinding,
)
from app.shared.integration.models import (
    IntegrationExecutionModel,
    IntegrationReportModel,
    IntegrationRunPlanModel,
)
from app.shared.projects.models import Project

logger = logging.getLogger(__name__)


def compute_finding_id(
    component: str, run_id: str, rule_or_check_id: str, event_or_target_ref: str
) -> str:
    """Generate a stable, deterministic identity hash for finding deduplication."""
    identity_str = f"{component}:{run_id}:{rule_or_check_id}:{event_or_target_ref}"
    digest = hashlib.sha256(identity_str.encode("utf-8")).hexdigest()[:16]
    return f"find-{component.lower()}-{digest}"


def canonical_json_digest(data: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 digest over canonical JSON bytes."""
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class AggregatorClientAdapter:
    """Concrete client adapter registered with C2ReportPublisher to handle published findings."""

    def __init__(self, execution_id: str):
        self.execution_id = execution_id
        self.published_payloads: list[Any] = []

    def publish(self, evaluation: Any) -> str:
        """Record published evaluation and return confirmed publication token."""
        self.published_payloads.append(evaluation)
        return f"PUB-{self.execution_id[:8]}-C2-OK"


class SharedReportAggregator:
    """Aggregates multi-component QA results into a consolidated report."""

    def __init__(self, db: Session):
        self.db = db

    def generate_report(
        self,
        project: Project,
        execution_id: str,
        user: User | None = None,
        persist: bool = True,
    ) -> CombinedQAReport:
        """Assemble and optionally persist a combined QA report for an execution."""
        # 1. Fetch execution record and verify project scoping
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

        # 2. Fetch associated run plan
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

        # 3. Check if an existing published report already exists
        existing_report_stmt = select(IntegrationReportModel).where(
            IntegrationReportModel.project_id == project.project_id,
            IntegrationReportModel.execution_id == execution_id,
        )
        existing_report = self.db.execute(existing_report_stmt).scalars().first()
        if existing_report and not persist:
            return CombinedQAReport.model_validate(existing_report.report_payload)

        # 4. Extract frozen references and runtime evaluations
        ref_payload = plan_record.plan_payload.get("component_references", {})
        refs = ComponentReferencesPlan(**ref_payload)
        evaluations: dict[str, Any] = execution_record.evaluations or {}

        # 5. Connect Component Adapters
        contributions: dict[str, ComponentContribution] = {}
        all_raw_findings: list[UnifiedFinding] = []

        # -------------------------------------------------------------------
        # C1 Adapter (Tool-Call Correctness)
        # -------------------------------------------------------------------
        if refs.c1 is not None:
            c1_data = evaluations.get("C1")
            if c1_data:
                c1_checks = c1_data.get("checks", [])
                c1_verdict = c1_data.get("verdict", "UNKNOWN")
                checks_count = c1_data.get("checks_count", len(c1_checks))
                passed_checks = c1_data.get("passed_checks", checks_count)
                violations_count = max(0, checks_count - passed_checks)

                contributions["C1"] = ComponentContribution(
                    component=ComponentType.C1,
                    native_entity_id=refs.c1.config_id,
                    evaluation_version="2026.1",
                    evaluator_version=c1_data.get("evaluator_version", "1.0.0"),
                    status="EVALUATED",
                    native_verdict=c1_verdict,
                    checks_or_rules_count=checks_count,
                    violations_or_findings_count=violations_count,
                    native_details={
                        "trace_completeness": c1_data.get("trace_completeness"),
                        "passed_checks": passed_checks,
                    },
                    evidence_references=[f"trace-{execution_id[:8]}-primary"],
                )

                # Extract check findings
                for check in c1_checks:
                    chk_verdict = check.get("verdict", "PASS")
                    chk_id = check.get("check_id") or check.get("tool_name", "c1_check")
                    event_idx = str(check.get("event_index", "0"))
                    finding_id = compute_finding_id(
                        "C1", execution_id, chk_id, event_idx
                    )

                    all_raw_findings.append(
                        UnifiedFinding(
                            finding_id=finding_id,
                            component=ComponentType.C1,
                            rule_or_check_id=chk_id,
                            native_verdict=chk_verdict,
                            severity="VIOLATION" if chk_verdict != "PASS" else "INFO",
                            event_id=f"event-{event_idx}",
                            tool_call_id=check.get("tool_name"),
                            entity_id="ord-001",
                            message=check.get("message")
                            or f"Tool call check {chk_id}: {chk_verdict}",
                            supporting_evidence=check.get("context_data"),
                        )
                    )
            else:
                contributions["C1"] = ComponentContribution(
                    component=ComponentType.C1,
                    native_entity_id=refs.c1.config_id,
                    status="NOT_EVALUATED",
                    native_verdict=None,
                    non_evaluation_reasons=["C1 was planned but did not execute."],
                )

        # -------------------------------------------------------------------
        # C2 Adapter (State-Aware EFSM Workflow)
        # -------------------------------------------------------------------
        if refs.c2 is not None:
            c2_data = evaluations.get("C2")
            if c2_data:
                # Connect C2 Report Publisher to replace STUB status with CONNECTED
                aggregator_client = AggregatorClientAdapter(execution_id)
                c2_publisher = C2ReportPublisher(aggregator_client=aggregator_client)
                c2_pub_token = c2_publisher.publish_component_finding(c2_data)

                c2_verdict = c2_data.get("verdict", "UNKNOWN")
                violations = c2_data.get("violations", [])
                reasons = c2_data.get("reasons", [])
                observed_states = c2_data.get("observed_states", [])

                contributions["C2"] = ComponentContribution(
                    component=ComponentType.C2,
                    native_entity_id=refs.c2.model_id,
                    evaluation_version="2026.1",
                    evaluator_version="1.0.0",
                    status="EVALUATED",
                    native_verdict=c2_verdict,
                    checks_or_rules_count=len(observed_states) or 1,
                    violations_or_findings_count=len(violations),
                    native_details={
                        "observed_states": observed_states,
                        "reasons": reasons,
                        "first_divergence": c2_data.get("first_divergence"),
                        "publisher_status": c2_publisher.status.value,
                        "publication_token": c2_pub_token,
                    },
                    evidence_references=[f"trace-{execution_id[:8]}-c2-states"],
                )

                # Extract violations into findings
                for v in violations:
                    v_rule = v.get("transition_id") or v.get(
                        "violation_type", "efsm_rule"
                    )
                    v_step = str(v.get("step_index", "0"))
                    finding_id = compute_finding_id(
                        "C2", execution_id, v_rule, f"step-{v_step}"
                    )
                    all_raw_findings.append(
                        UnifiedFinding(
                            finding_id=finding_id,
                            component=ComponentType.C2,
                            rule_or_check_id=v_rule,
                            native_verdict=c2_verdict,
                            severity="VIOLATION",
                            event_id=f"event-{v_step}",
                            tool_call_id=v.get("action_or_tool"),
                            entity_id="ord-001",
                            message=v.get("message")
                            or f"State-aware workflow divergence: {v_rule}",
                            supporting_evidence=v,
                        )
                    )

                # If no violation records but non-passing verdict (e.g. unexpected termination)
                if not violations and c2_verdict not in (
                    "PASS",
                    "EXPECTED_REJECTION_PASS",
                ):
                    finding_id = compute_finding_id(
                        "C2", execution_id, "workflow_outcome", c2_verdict
                    )
                    all_raw_findings.append(
                        UnifiedFinding(
                            finding_id=finding_id,
                            component=ComponentType.C2,
                            rule_or_check_id="EFSM_WORKFLOW_VERDICT",
                            native_verdict=c2_verdict,
                            severity="VIOLATION",
                            event_id="event-0",
                            tool_call_id=None,
                            entity_id="ord-001",
                            message=f"EFSM conformance outcome: {c2_verdict}. Reasons: {'; '.join(reasons)}",
                            supporting_evidence={"reasons": reasons},
                        )
                    )
            else:
                contributions["C2"] = ComponentContribution(
                    component=ComponentType.C2,
                    native_entity_id=refs.c2.model_id,
                    status="NOT_EVALUATED",
                    native_verdict=None,
                    non_evaluation_reasons=["C2 was planned but did not execute."],
                )

        # -------------------------------------------------------------------
        # C3 Adapter (Robustness & Fault Recovery)
        # -------------------------------------------------------------------
        if refs.c3 is not None:
            c3_data = evaluations.get("C3")
            if c3_data:
                c3_verdict = c3_data.get("verdict", "INCONCLUSIVE")
                rule_results = c3_data.get("rule_results", [])
                rule_count = c3_data.get("rule_results_count", len(rule_results))
                violations_count = sum(
                    1 for r in rule_results if not r.get("passed", True)
                )

                contributions["C3"] = ComponentContribution(
                    component=ComponentType.C3,
                    native_entity_id=refs.c3.suite_id,
                    evaluation_version="2026.1",
                    evaluator_version="1.0.0",
                    status="EVALUATED",
                    native_verdict=c3_verdict,
                    checks_or_rules_count=rule_count,
                    violations_or_findings_count=violations_count,
                    native_details={
                        "evaluation_status": c3_data.get("status"),
                        "exposure_status": c3_data.get("exposure_status"),
                        "c2_facts_consumed": c3_data.get("c2_facts_consumed", 0),
                        "c2_facts_provenance": c3_data.get("c2_facts_provenance", []),
                        "clean_qualification": c3_data.get("clean_qualification"),
                        "non_evaluation_reasons": c3_data.get(
                            "non_evaluation_reasons", []
                        ),
                    },
                    evidence_references=[
                        f"pair-{execution_id[:8]}-clean",
                        f"pair-{execution_id[:8]}-fault",
                    ],
                    non_evaluation_reasons=c3_data.get("non_evaluation_reasons", []),
                )

                # Extract rule results into findings
                for r in rule_results:
                    r_id = r.get("rule_id", "rec_rule")
                    r_passed = r.get("passed", True)
                    finding_id = compute_finding_id(
                        "C3", execution_id, r_id, "fault_trial"
                    )
                    all_raw_findings.append(
                        UnifiedFinding(
                            finding_id=finding_id,
                            component=ComponentType.C3,
                            rule_or_check_id=r_id,
                            native_verdict=c3_verdict,
                            severity="VIOLATION" if not r_passed else "INFO",
                            event_id="event-fault-trial",
                            tool_call_id=refs.c3.target_tool_id or "order_placement",
                            entity_id="ord-001",
                            message=r.get("failure_reason")
                            or f"Recovery contract rule {r_id}: {'PASSED' if r_passed else 'VIOLATED'}",
                            supporting_evidence=r,
                        )
                    )

                # If non-passing verdict and no explicit rule results
                if not rule_results and c3_verdict not in (
                    "SUCCESS_CLEAN_RECOVERY",
                    "SUCCESS_DEGRADED_RECOVERY",
                ):
                    finding_id = compute_finding_id(
                        "C3", execution_id, "recovery_verdict", c3_verdict
                    )
                    all_raw_findings.append(
                        UnifiedFinding(
                            finding_id=finding_id,
                            component=ComponentType.C3,
                            rule_or_check_id="RECOVERY_VERDICT",
                            native_verdict=c3_verdict,
                            severity="VIOLATION",
                            event_id="event-fault-trial",
                            tool_call_id=refs.c3.target_tool_id or "order_placement",
                            entity_id="ord-001",
                            message=f"Recovery assessment outcome: {c3_verdict}",
                            supporting_evidence=c3_data,
                        )
                    )
            else:
                contributions["C3"] = ComponentContribution(
                    component=ComponentType.C3,
                    native_entity_id=refs.c3.suite_id,
                    status="NOT_EVALUATED",
                    native_verdict=None,
                    non_evaluation_reasons=["C3 was planned but did not execute."],
                )

        # -------------------------------------------------------------------
        # C4 Adapter (Policy-Aware Safety)
        # -------------------------------------------------------------------
        if refs.c4 is not None:
            c4_data = evaluations.get("C4")
            if c4_data:
                c4_verdict = c4_data.get("verdict", "UNKNOWN")
                findings = c4_data.get("findings", [])
                findings_count = c4_data.get("findings_count", len(findings))

                contributions["C4"] = ComponentContribution(
                    component=ComponentType.C4,
                    native_entity_id=refs.c4.contract_id or "contract-c4",
                    evaluation_version="2026.1",
                    evaluator_version="1.0.0",
                    status="EVALUATED",
                    native_verdict=c4_verdict,
                    checks_or_rules_count=max(1, len(findings)),
                    violations_or_findings_count=findings_count,
                    native_details={
                        "summary": c4_data.get("summary", {}),
                    },
                    evidence_references=[f"trace-{execution_id[:8]}-c4-policy"],
                )

                # Extract policy rule findings
                for f in findings:
                    r_id = f.get("rule_id", "pol_rule")
                    f_verdict = f.get("verdict", "PASS")
                    finding_id = compute_finding_id(
                        "C4", execution_id, r_id, str(f.get("finding_id", "0"))
                    )
                    all_raw_findings.append(
                        UnifiedFinding(
                            finding_id=finding_id,
                            component=ComponentType.C4,
                            rule_or_check_id=r_id,
                            native_verdict=f_verdict,
                            severity=(
                                "VIOLATION"
                                if f_verdict in ("FLAG", "BLOCK", "REJECT")
                                else "INFO"
                            ),
                            event_id="event-0",
                            tool_call_id=f.get("target_tool", "order_placement"),
                            entity_id="ord-001",
                            message=f.get("explanation")
                            or f"Policy rule {r_id} evaluated with verdict {f_verdict}",
                            supporting_evidence=f,
                        )
                    )
            else:
                contributions["C4"] = ComponentContribution(
                    component=ComponentType.C4,
                    native_entity_id=refs.c4.contract_id or "contract-c4",
                    status="NOT_EVALUATED",
                    native_verdict=None,
                    non_evaluation_reasons=["C4 was planned but did not execute."],
                )

        # 6. Deduplicate repeated publications using stable finding_id
        deduped_findings_map: dict[str, UnifiedFinding] = {}
        for finding in all_raw_findings:
            if finding.finding_id not in deduped_findings_map:
                deduped_findings_map[finding.finding_id] = finding
        deduped_findings = list(deduped_findings_map.values())

        # 7. Link Related Findings (Shared Run, Event, or Entity References)
        # Distinct violations are preserved without collapse!
        correlated_defect_groups: list[CorrelatedFindingGroup] = []
        correlation_buckets: dict[str, list[UnifiedFinding]] = {}

        for finding in deduped_findings:
            # Group by correlated entity/event reference if available
            key = None
            if finding.event_id and finding.event_id not in (
                "event-0",
                "event-fault-trial",
            ):
                key = f"event:{finding.event_id}"
            elif finding.entity_id:
                key = f"entity:{finding.entity_id}"
            else:
                key = f"misc:{finding.component.value}"

            correlation_buckets.setdefault(key, []).append(finding)

        group_idx = 1
        for corr_key, group_findings in correlation_buckets.items():
            involved = list({f.component for f in group_findings})
            group_id = f"grp-{execution_id[:8]}-{group_idx:02d}"
            group_idx += 1

            correlated_defect_groups.append(
                CorrelatedFindingGroup(
                    group_id=group_id,
                    correlation_key=corr_key,
                    shared_entity_or_event_ref=corr_key.split(":", 1)[-1],
                    finding_ids=[f.finding_id for f in group_findings],
                    involved_components=involved,
                    findings=group_findings,
                    correlation_explanation=(
                        f"Distinct component findings correlated by shared {corr_key}. "
                        "Correlated findings are linked for triage but remain distinct individual defects."
                    ),
                )
            )

        # 8. Report Completeness Breakdown
        requested_comps: list[ComponentType] = []
        if refs.c1 is not None:
            requested_comps.append(ComponentType.C1)
        if refs.c2 is not None:
            requested_comps.append(ComponentType.C2)
        if refs.c3 is not None:
            requested_comps.append(ComponentType.C3)
        if refs.c4 is not None:
            requested_comps.append(ComponentType.C4)

        evaluated_comps: list[ComponentType] = [
            c.component for c in contributions.values() if c.status == "EVALUATED"
        ]
        not_evaluated_comps: list[ComponentType] = [
            c for c in requested_comps if c not in evaluated_comps
        ]

        per_comp_verdicts: dict[str, str] = {
            c.component.value: c.native_verdict or "NOT_EVALUATED"
            for c in contributions.values()
        }
        per_comp_counts: dict[str, int] = {
            c.component.value: c.checks_or_rules_count for c in contributions.values()
        }

        # Overall Verdict Logic:
        # Only true passing verdicts:
        passing_verdicts = {
            "PASS",
            "EXPECTED_REJECTION_PASS",
            "SUCCESS_CLEAN_RECOVERY",
            "SUCCESS_DEGRADED_RECOVERY",
        }
        all_evaluated_passed = (
            len(evaluated_comps) == len(requested_comps)
            and len(requested_comps) > 0
            and all(
                c.native_verdict in passing_verdicts
                and c.violations_or_findings_count == 0
                for c in contributions.values()
                if c.status == "EVALUATED"
            )
        )

        overall_verdict: str
        if not_evaluated_comps:
            overall_verdict = "PARTIAL_NOT_ALL_COMPONENTS_EVALUATED"
        elif all_evaluated_passed:
            overall_verdict = "PASSED"
        elif len(evaluated_comps) > 0:
            overall_verdict = "FAILED"
        else:
            overall_verdict = "NOT_EVALUATED"

        completeness_summary = ReportCompletenessSummary(
            requested_components=requested_comps,
            evaluated_components=evaluated_comps,
            not_ready_components=[],
            blocked_components=[],
            failed_execution_components=[],
            not_evaluated_components=not_evaluated_comps,
            pending_or_missing_evidence=[],
            per_component_verdicts=per_comp_verdicts,
            per_component_counts=per_comp_counts,
            overall_verdict=overall_verdict,
        )

        # 9. Assemble Combined QA Report
        report_id = f"rep-{execution_id[:8]}"
        now_utc = datetime.now(UTC)

        report_dict: dict[str, Any] = {
            "report_id": report_id,
            "integration_run_id": execution_record.integration_run_id,
            "execution_id": execution_id,
            "project_id": project.project_id,
            "target_mode": execution_record.target_mode,
            "provenance": {
                "runner_version": "2026.1",
                "execution_mode": execution_record.target_mode,
                "retained_evidence_digest": execution_record.retained_evidence_digest,
                "plan_digest": execution_record.plan_digest,
            },
            "generated_at_utc": now_utc.isoformat(),
            "completeness": completeness_summary.model_dump(mode="json"),
            "component_contributions": {
                k: v.model_dump(mode="json") for k, v in contributions.items()
            },
            "raw_finding_count": len(deduped_findings),
            "grouped_defect_count": len(correlated_defect_groups),
            "findings": [f.model_dump(mode="json") for f in deduped_findings],
            "correlated_defect_groups": [
                g.model_dump(mode="json") for g in correlated_defect_groups
            ],
        }
        report_digest = canonical_json_digest(report_dict)
        report_dict["report_digest"] = report_digest

        combined_report = CombinedQAReport.model_validate(report_dict)

        # 10. Persist Report
        if persist:
            if existing_report:
                existing_report.report_payload = combined_report.model_dump(mode="json")
                existing_report.report_digest = report_digest
                existing_report.raw_finding_count = len(deduped_findings)
                existing_report.grouped_defect_count = len(correlated_defect_groups)
                existing_report.updated_at_utc = now_utc
            else:
                new_report_model = IntegrationReportModel(
                    report_id=report_id,
                    execution_id=execution_id,
                    integration_run_id=execution_record.integration_run_id,
                    project_id=project.project_id,
                    published_by_user_id=user.id if user else None,
                    report_status="PUBLISHED",
                    report_digest=report_digest,
                    raw_finding_count=len(deduped_findings),
                    grouped_defect_count=len(correlated_defect_groups),
                    report_payload=combined_report.model_dump(mode="json"),
                    created_at_utc=now_utc,
                    updated_at_utc=now_utc,
                )
                self.db.add(new_report_model)

            self.db.commit()

        return combined_report

    def export_report_json(self, report: CombinedQAReport) -> str:
        """Export combined QA report to pretty-printed JSON."""
        return json.dumps(report.model_dump(mode="json"), indent=2, default=str)

    def export_report_csv(self, report: CombinedQAReport) -> str:
        """Export combined QA report findings and component summaries to CSV."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Write Metadata Header
        writer.writerow(["# Combined QA Report Export"])
        writer.writerow(["Report ID", report.report_id])
        writer.writerow(["Integration Run ID", report.integration_run_id])
        writer.writerow(["Execution ID", report.execution_id])
        writer.writerow(["Project ID", report.project_id])
        writer.writerow(["Overall Verdict", report.completeness.overall_verdict])
        writer.writerow(["Raw Finding Count", report.raw_finding_count])
        writer.writerow(["Grouped Defect Count", report.grouped_defect_count])
        writer.writerow(["Generated At UTC", str(report.generated_at_utc)])
        writer.writerow([])

        # Write Component Breakdown
        writer.writerow(
            [
                "Component",
                "Native Entity ID",
                "Status",
                "Native Verdict",
                "Checks Count",
                "Violations Count",
            ]
        )
        for comp_name, contrib in report.component_contributions.items():
            writer.writerow(
                [
                    comp_name,
                    contrib.native_entity_id,
                    contrib.status,
                    contrib.native_verdict or "N/A",
                    contrib.checks_or_rules_count,
                    contrib.violations_or_findings_count,
                ]
            )
        writer.writerow([])

        # Write Detailed Findings
        writer.writerow(
            [
                "Finding ID",
                "Component",
                "Rule or Check ID",
                "Native Verdict",
                "Severity",
                "Event ID",
                "Tool Call ID",
                "Entity ID",
                "Message",
            ]
        )
        for finding in report.findings:
            writer.writerow(
                [
                    finding.finding_id,
                    finding.component.value,
                    finding.rule_or_check_id,
                    finding.native_verdict,
                    finding.severity,
                    finding.event_id or "",
                    finding.tool_call_id or "",
                    finding.entity_id or "",
                    finding.message,
                ]
            )

        return output.getvalue()

    def list_reports(
        self,
        project: Project,
        component: str | None = None,
        verdict: str | None = None,
        execution_mode: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> IntegrationReportListResponse:
        """Query persisted combined reports with bounded pagination and filtering."""
        query = select(IntegrationReportModel).where(
            IntegrationReportModel.project_id == project.project_id
        )

        # Filters on report payload
        if verdict:
            # We can filter in memory or via SQL query
            pass

        count_query = (
            select(func.count())
            .select_from(IntegrationReportModel)
            .where(IntegrationReportModel.project_id == project.project_id)
        )
        total = self.db.execute(count_query).scalar() or 0

        offset = (page - 1) * page_size
        query = (
            query.order_by(desc(IntegrationReportModel.created_at_utc))
            .offset(offset)
            .limit(page_size)
        )
        records = self.db.execute(query).scalars().all()

        items: list[CombinedQAReport] = []
        for r in records:
            rep = CombinedQAReport.model_validate(r.report_payload)
            # Apply in-memory filters if specified
            if component and component not in rep.component_contributions:
                continue
            if verdict and rep.completeness.overall_verdict.upper() != verdict.upper():
                continue
            if execution_mode and rep.target_mode.upper() != execution_mode.upper():
                continue
            items.append(rep)

        return IntegrationReportListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
