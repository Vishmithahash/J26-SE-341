"""Evidence Replay Service for deterministic multi-evaluator reproducibility.

Component: Shared Integration Reporting & Replay (Part 3)
Guarantees:
- Strictly re-evaluates retained execution evidence without invoking target services.
- Never launches network requests, browser adapters, or agent invocations during replay.
- Verifies evidence digest before dispatch; rejects tampered evidence with HTTP 422.
- Reuses shared dispatch_component_evaluations logic to ensure parity between execution and replay.
- Accurately compares semantic parity (rule identities, violation reasons, verdict parity).
- Preserves original evaluation records immutably.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.shared.auth.models import User
from app.shared.integration.adapters import ExecutionTrace
from app.shared.integration.contracts import (
    ComponentReferencesPlan,
    ReplayComparisonResponse,
)
from app.shared.integration.evidence import (
    compute_evidence_digest,
)
from app.shared.integration.executor import (
    dispatch_component_evaluations,
)
from app.shared.integration.models import (
    IntegrationExecutionModel,
    IntegrationRunPlanModel,
)
from app.shared.integration.service import canonical_json_digest
from app.shared.projects.models import Project

logger = logging.getLogger(__name__)

# Non-deterministic fields that vary per evaluation invocation and should not break semantic parity
NONDETERMINISTIC_EVALUATION_FIELDS = [
    "created_at_utc",
    "updated_at_utc",
    "started_at_utc",
    "completed_at_utc",
    "replayed_at_utc",
    "evaluator_timing_ms",
    "finding_id",
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
        plan_identifier: str | None = None,
    ) -> ReplayComparisonResponse:
        """Replay stored evidence against pinned configurations to verify semantic reproducibility."""
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

        # Verify nested plan identifier if provided
        if (
            plan_identifier
            and plan_record.integration_run_id != plan_identifier
            and plan_record.id != plan_identifier
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution '{execution_id}' does not belong to plan '{plan_identifier}'.",
            )

        # Verify execution record's plan digest matches plan record's plan digest
        if execution_record.plan_digest != plan_record.plan_digest:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Plan digest mismatch for execution '{execution_id}'. "
                    f"Execution recorded plan digest '{execution_record.plan_digest}', "
                    f"but plan '{plan_record.integration_run_id}' has '{plan_record.plan_digest}'."
                ),
            )

        # Verify plan payload integrity against recorded plan_digest
        computed_plan_digest = canonical_json_digest(plan_record.plan_payload)
        if computed_plan_digest != plan_record.plan_digest:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Plan payload integrity check failed for plan '{plan_record.integration_run_id}'. "
                    f"Recorded digest '{plan_record.plan_digest}', computed '{computed_plan_digest}'."
                ),
            )

        # 3. Retained Evidence Integrity Verification
        retained_bundle = execution_record.retained_evidence or {}
        if not retained_bundle:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Execution '{execution_id}' has no retained evidence to replay.",
            )

        actual_digest = compute_evidence_digest(retained_bundle)
        expected_digest = execution_record.retained_evidence_digest
        if actual_digest != expected_digest:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Retained evidence integrity check failed for execution '{execution_id}'. "
                    f"Expected digest '{expected_digest}', computed '{actual_digest}'. "
                    "Evidence has been tampered with or corrupted."
                ),
            )

        # Verify plan execution inputs digest
        plan_payload = plan_record.plan_payload or {}
        inputs_snapshot = plan_payload.get("execution_inputs_snapshot", {})
        expected_inputs_digest = plan_payload.get("execution_inputs_digest")
        if expected_inputs_digest:
            actual_inputs_digest = canonical_json_digest(inputs_snapshot)
            if actual_inputs_digest != expected_inputs_digest:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"Plan execution inputs integrity check failed during replay for execution '{execution_id}'. "
                        f"Expected digest '{expected_inputs_digest}', computed '{actual_inputs_digest}'."
                    ),
                )

        # Reconstruct primary and fault traces
        primary_trace_data = retained_bundle.get("primary_trace", {})
        primary_trace = ExecutionTrace(**primary_trace_data)
        fault_trace_data = retained_bundle.get("fault_trace")
        c3_fault_trace = (
            ExecutionTrace(**fault_trace_data) if fault_trace_data else None
        )
        c3_clean_data = retained_bundle.get("c3_clean_trace")
        c3_clean_trace = ExecutionTrace(**c3_clean_data) if c3_clean_data else None

        # 4. Extract frozen references and input snapshots
        ref_payload = plan_record.plan_payload.get("component_references", {})
        refs = ComponentReferencesPlan(**ref_payload)
        frozen_inputs = plan_record.plan_payload.get("execution_inputs_snapshot", {})

        # 5. Re-evaluate using shared evaluation dispatcher
        replayed_evaluations = dispatch_component_evaluations(
            db=self.db,
            project_id=project.project_id,
            execution_id=execution_id,
            refs=refs,
            frozen_inputs=frozen_inputs,
            primary_trace=primary_trace,
            c3_fault_trace=c3_fault_trace,
            c3_clean_trace=c3_clean_trace,
            is_replay=True,
        )

        # 6. Deep Semantic Parity Comparison
        original_evaluations: dict[str, Any] = execution_record.evaluations or {}
        divergence_reasons: list[str] = []
        is_semantic_parity = True

        for comp_name in ["C1", "C2", "C3", "C4"]:
            orig_c = original_evaluations.get(comp_name)
            repl_c = replayed_evaluations.get(comp_name)

            if orig_c is None and repl_c is None:
                continue
            if (orig_c is None) != (repl_c is None):
                is_semantic_parity = False
                divergence_reasons.append(
                    f"{comp_name}: evaluation presence differs (orig: {bool(orig_c)}, replayed: {bool(repl_c)})."
                )
                continue

            # Compare verdicts
            orig_verdict = orig_c.get("verdict")
            repl_verdict = repl_c.get("verdict")
            if orig_verdict != repl_verdict:
                is_semantic_parity = False
                divergence_reasons.append(
                    f"{comp_name}: verdict changed from '{orig_verdict}' to '{repl_verdict}'."
                )

            # Compare check/violation counts
            orig_viol = orig_c.get("violations_count", orig_c.get("findings_count", 0))
            repl_viol = repl_c.get("violations_count", repl_c.get("findings_count", 0))
            if orig_viol != repl_viol:
                is_semantic_parity = False
                divergence_reasons.append(
                    f"{comp_name}: violation count changed from {orig_viol} to {repl_viol}."
                )

            # Compare specific violated rules and failure reasons
            orig_reasons = orig_c.get("reasons", [])
            repl_reasons = repl_c.get("reasons", [])
            if orig_reasons != repl_reasons:
                is_semantic_parity = False
                divergence_reasons.append(
                    f"{comp_name}: reasons changed from {orig_reasons} to {repl_reasons}."
                )

            # For C1, compare individual tool call check outcomes preserving multiplicity
            if comp_name == "C1":
                orig_checks = [
                    (
                        c.get("check_id"),
                        c.get("tool_name"),
                        c.get("verdict"),
                        c.get("reason_code"),
                    )
                    for c in orig_c.get("checks", [])
                ]
                repl_checks = [
                    (
                        c.get("check_id"),
                        c.get("tool_name"),
                        c.get("verdict"),
                        c.get("reason_code"),
                    )
                    for c in repl_c.get("checks", [])
                ]
                if orig_checks != repl_checks:
                    is_semantic_parity = False
                    divergence_reasons.append(
                        f"C1: individual tool check sequences differ (orig: {orig_checks}, replayed: {repl_checks})."
                    )

            # For C2, compare violations sequence preserving multiplicity
            if comp_name == "C2":
                orig_violations = [
                    (
                        v.get("transition_id"),
                        v.get("violation_type"),
                        v.get("step_index"),
                        v.get("message"),
                    )
                    for v in orig_c.get("violations", [])
                ]
                repl_violations = [
                    (
                        v.get("transition_id"),
                        v.get("violation_type"),
                        v.get("step_index"),
                        v.get("message"),
                    )
                    for v in repl_c.get("violations", [])
                ]
                if orig_violations != repl_violations:
                    is_semantic_parity = False
                    divergence_reasons.append(
                        f"C2: violations sequence differs (orig: {orig_violations}, replayed: {repl_violations})."
                    )

            # For C3, compare rule statuses and supporting facts preserving multiplicity
            if comp_name == "C3":
                orig_rules = [
                    (
                        r.get("rule_id"),
                        r.get("status"),
                        r.get("reason_code"),
                        tuple(r.get("supporting_fact_ids") or []),
                    )
                    for r in orig_c.get("rule_results", [])
                ]
                repl_rules = [
                    (
                        r.get("rule_id"),
                        r.get("status"),
                        r.get("reason_code"),
                        tuple(r.get("supporting_fact_ids") or []),
                    )
                    for r in repl_c.get("rule_results", [])
                ]
                if orig_rules != repl_rules:
                    is_semantic_parity = False
                    divergence_reasons.append(
                        f"C3: rule evaluation sequences differ (orig: {orig_rules}, replayed: {repl_rules})."
                    )

            # For C4, compare individual findings preserving multiplicity
            if comp_name == "C4":
                orig_findings = [
                    (
                        f.get("rule_id"),
                        f.get("verdict"),
                        f.get("severity"),
                    )
                    for f in orig_c.get("findings", [])
                ]
                repl_findings = [
                    (
                        f.get("rule_id"),
                        f.get("verdict"),
                        f.get("severity"),
                    )
                    for f in repl_c.get("findings", [])
                ]
                if orig_findings != repl_findings:
                    is_semantic_parity = False
                    divergence_reasons.append(
                        f"C4: individual policy rule findings differ (orig: {orig_findings}, replayed: {repl_findings})."
                    )

        now_utc = datetime.now(UTC)
        return ReplayComparisonResponse(
            execution_id=execution_id,
            is_semantically_identical=is_semantic_parity,
            original_evaluations=original_evaluations,
            replayed_evaluations=replayed_evaluations,
            semantic_diffs=divergence_reasons,
            divergence_reasons=divergence_reasons,
            nondeterministic_fields_ignored=NONDETERMINISTIC_EVALUATION_FIELDS,
            replayed_at_utc=now_utc,
        )
