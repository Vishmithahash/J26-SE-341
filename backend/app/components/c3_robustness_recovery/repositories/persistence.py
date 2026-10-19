"""Scoped database repository for Component 3 Phase 5 persistence.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 5 - Shared persistence, execution tracking, results and reporting.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.components.c3_robustness_recovery.contracts.evaluation import (
    RecoveryEvaluationResult,
)
from app.components.c3_robustness_recovery.contracts.generation import FrozenSuite
from app.components.c3_robustness_recovery.contracts.persistence import (
    ExecutionCreateRequest,
    ExecutionTrackingStatus,
    compute_content_digest,
)
from app.components.c3_robustness_recovery.models.persistence import (
    C3CaseModel,
    C3EvaluationModel,
    C3ExecutionModel,
    C3MatchedPairModel,
    C3SuiteModel,
)
from app.components.c3_robustness_recovery.runtime.evidence import (
    MatchedPairEvidence,
    sanitize_arguments,
)


class PersistenceError(Exception):
    """Base exception for persistence operations."""


class EntityNotFoundError(PersistenceError):
    """Raised when a requested entity does not exist within the given project scope."""


class ConflictError(PersistenceError):
    """Raised when an immutable content mismatch or invalid lifecycle transition occurs (HTTP 409)."""


class C3PersistenceRepository:
    """Scoped repository for C3 database operations.

    Enforces:
    - Strict logical project scoping on all reads and writes.
    - Immutability of stored snapshots: identical digests return existing record;
      divergent content under the same key raises ConflictError.
    - Bounded pagination and deterministic ordering.
    - Never modifies AUT or external tables.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # -----------------------------------------------------------------------
    # Suite and Case Operations
    # -----------------------------------------------------------------------

    def save_frozen_suite(
        self, project_id: str, suite: FrozenSuite
    ) -> tuple[C3SuiteModel, bool]:
        """Idempotently persist a frozen suite and its cases.

        Returns (model, created_new).
        Raises ConflictError if suite exists with divergent content.
        """
        existing = self.db.scalars(
            select(C3SuiteModel).where(C3SuiteModel.suite_digest == suite.suite_digest)
        ).first()

        if existing:
            if existing.project_id != project_id:
                raise ConflictError(
                    f"Suite digest '{suite.suite_digest}' already exists under a different project scope."
                )
            # Idempotent re-import of identical suite
            return existing, False

        # Verify no conflicting suite_id exists with different digest
        existing_id = self.db.scalars(
            select(C3SuiteModel).where(
                C3SuiteModel.project_id == project_id,
                C3SuiteModel.suite_id == suite.suite_id,
                C3SuiteModel.suite_digest != suite.suite_digest,
            )
        ).first()
        if existing_id:
            raise ConflictError(
                f"Suite ID '{suite.suite_id}' already exists in project '{project_id}' with a different digest."
            )

        sanitized_suite = sanitize_arguments(suite.model_dump(mode="json"))

        task_id = (
            suite.task_fixture_metadata.task_id
            if getattr(suite, "task_fixture_metadata", None)
            else (
                suite.selected_cases[0].task_id if suite.selected_cases else "unknown"
            )
        )
        domain = (
            suite.task_fixture_metadata.domain
            if getattr(suite, "task_fixture_metadata", None)
            else (
                suite.selected_cases[0].domain if suite.selected_cases else "ecommerce"
            )
        )
        tool_id = (
            suite.selected_cases[0].tool_id
            if suite.selected_cases
            else (
                suite.task_fixture_metadata.associated_tool_ids[0]
                if getattr(suite, "task_fixture_metadata", None)
                and suite.task_fixture_metadata.associated_tool_ids
                else "unknown"
            )
        )

        suite_model = C3SuiteModel(
            suite_id=suite.suite_id,
            suite_digest=suite.suite_digest,
            project_id=project_id,
            task_id=task_id,
            tool_id=tool_id,
            domain=domain,
            schema_version=suite.schema_version,
            generator_version=suite.generator_version,
            total_cases=len(suite.selected_cases),
            policy_snapshot=sanitize_arguments(suite.policy.model_dump(mode="json")),
            adapter_manifest_snapshot=sanitize_arguments(
                suite.adapter_manifest.model_dump(mode="json")
            ),
            task_fixture_metadata_snapshot=sanitize_arguments(
                suite.task_fixture_metadata.model_dump(mode="json")
            ),
            recovery_contract_snapshot=sanitize_arguments(
                suite.recovery_contract.model_dump(mode="json")
            ),
            suite_snapshot=sanitized_suite,
            created_at_utc=datetime.now(UTC),
        )

        for order, case in enumerate(suite.selected_cases):
            case_dict = sanitize_arguments(case.model_dump(mode="json"))
            content_digest = compute_content_digest(case_dict)
            case_model = C3CaseModel(
                case_id=case.case_id,
                suite_digest=suite.suite_digest,
                case_fingerprint=case.fingerprint
                if hasattr(case, "fingerprint") and case.fingerprint
                else content_digest[:16],
                content_digest=content_digest,
                project_id=project_id,
                case_family_id=case.case_family_id,
                fault_family=case.fault_family.value,
                effect_phase=case.effect_phase.value,
                interception_hook=case.interception_hook.value,
                target_tool_id=case.tool_id,
                case_order=order,
                case_snapshot=case_dict,
                created_at_utc=datetime.now(UTC),
            )
            suite_model.cases.append(case_model)

        self.db.add(suite_model)
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                f"Integrity conflict while saving suite '{suite.suite_id}': {exc.orig}"
            ) from exc

        return suite_model, True

    def get_suite_by_digest(
        self, project_id: str, suite_digest: str
    ) -> C3SuiteModel | None:
        """Retrieve a stored suite by its digest, scoped to project."""
        return self.db.scalars(
            select(C3SuiteModel).where(
                C3SuiteModel.project_id == project_id,
                C3SuiteModel.suite_digest == suite_digest,
            )
        ).first()

    def get_suite_by_id(self, project_id: str, suite_id: str) -> C3SuiteModel | None:
        """Retrieve the latest suite matching suite_id in project."""
        return self.db.scalars(
            select(C3SuiteModel)
            .where(
                C3SuiteModel.project_id == project_id,
                C3SuiteModel.suite_id == suite_id,
            )
            .order_by(C3SuiteModel.created_at_utc.desc(), C3SuiteModel.id.desc())
        ).first()

    def list_suites(
        self,
        project_id: str,
        domain: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[C3SuiteModel], int]:
        """List stored suites with deterministic pagination."""
        query = select(C3SuiteModel).where(C3SuiteModel.project_id == project_id)
        if domain:
            query = query.where(C3SuiteModel.domain == domain)

        count_query = select(func.count()).select_from(query.subquery())
        total = self.db.scalar(count_query) or 0

        items = list(
            self.db.scalars(
                query.order_by(
                    C3SuiteModel.created_at_utc.desc(), C3SuiteModel.id.desc()
                )
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return items, total

    def get_case(
        self, project_id: str, case_id: str, suite_digest: str | None = None
    ) -> C3CaseModel | None:
        """Retrieve a stored case snapshot by case_id within project scope."""
        query = select(C3CaseModel).where(
            C3CaseModel.project_id == project_id,
            C3CaseModel.case_id == case_id,
        )
        if suite_digest:
            query = query.where(C3CaseModel.suite_digest == suite_digest)
        return self.db.scalars(
            query.order_by(C3CaseModel.created_at_utc.desc(), C3CaseModel.id.desc())
        ).first()

    def list_cases(
        self,
        project_id: str,
        suite_digest: str | None = None,
        fault_family: str | None = None,
        effect_phase: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[C3CaseModel], int]:
        """List stored cases with deterministic ordering and bounded pagination."""
        query = select(C3CaseModel).where(C3CaseModel.project_id == project_id)
        if suite_digest:
            query = query.where(C3CaseModel.suite_digest == suite_digest)
        if fault_family:
            query = query.where(C3CaseModel.fault_family == fault_family)
        if effect_phase:
            query = query.where(C3CaseModel.effect_phase == effect_phase)

        count_query = select(func.count()).select_from(query.subquery())
        total = self.db.scalar(count_query) or 0

        items = list(
            self.db.scalars(
                query.order_by(
                    C3CaseModel.case_order.asc(),
                    C3CaseModel.created_at_utc.desc(),
                    C3CaseModel.id.desc(),
                )
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return items, total

    # -----------------------------------------------------------------------
    # Execution Tracking Operations
    # -----------------------------------------------------------------------

    def create_or_get_execution(
        self,
        project_id: str,
        request: ExecutionCreateRequest,
        suite_id: str,
    ) -> tuple[C3ExecutionModel, bool]:
        """Create a planned execution manifest or return existing identical execution."""
        existing = self.db.scalars(
            select(C3ExecutionModel).where(
                C3ExecutionModel.execution_id == request.execution_id
            )
        ).first()

        if existing:
            if existing.project_id != project_id:
                raise ConflictError(
                    f"Execution '{request.execution_id}' exists under a different project scope."
                )
            if existing.suite_digest != request.suite_digest:
                raise ConflictError(
                    f"Execution '{request.execution_id}' is bound to a different suite digest."
                )
            return existing, False

        manifest_data = {
            "planned_cases": request.planned_cases,
            "configuration": sanitize_arguments(request.configuration_snapshot),
        }

        exec_model = C3ExecutionModel(
            execution_id=request.execution_id,
            suite_digest=request.suite_digest,
            suite_id=suite_id,
            project_id=project_id,
            target_mode=request.target_mode,
            caller_identity=request.caller_identity,
            status=ExecutionTrackingStatus.PLANNED.value,
            planned_cases_count=len(request.planned_cases),
            executed_cases_count=0,
            blocked_cases_count=0,
            unsupported_cases_count=0,
            cancelled_cases_count=0,
            error_cases_count=0,
            manifest_snapshot=manifest_data,
            started_at_utc=datetime.now(UTC),
            created_at_utc=datetime.now(UTC),
        )

        self.db.add(exec_model)
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                f"Integrity conflict creating execution '{request.execution_id}': {exc.orig}"
            ) from exc

        return exec_model, True

    def update_execution_progress(
        self,
        project_id: str,
        execution_id: str,
        status: ExecutionTrackingStatus,
        executed_cases_count: int | None = None,
        blocked_cases_count: int | None = None,
        unsupported_cases_count: int | None = None,
        cancelled_cases_count: int | None = None,
        error_cases_count: int | None = None,
        halt_reason: str | None = None,
    ) -> C3ExecutionModel:
        """Update progress counts and lifecycle status of a tracked execution."""
        model = self.db.scalars(
            select(C3ExecutionModel).where(
                C3ExecutionModel.project_id == project_id,
                C3ExecutionModel.execution_id == execution_id,
            )
        ).first()

        if not model:
            raise EntityNotFoundError(
                f"Execution '{execution_id}' not found in project '{project_id}'."
            )

        # Enforce valid lifecycle transitions: terminal states cannot revert to running/planned
        terminal_statuses = {
            ExecutionTrackingStatus.COMPLETED.value,
            ExecutionTrackingStatus.CANCELLED.value,
            ExecutionTrackingStatus.INTERRUPTED.value,
            ExecutionTrackingStatus.ERROR.value,
        }
        if model.status in terminal_statuses and status.value not in terminal_statuses:
            raise ConflictError(
                f"Execution '{execution_id}' is already in terminal state '{model.status}'; cannot transition to '{status.value}'."
            )

        model.status = status.value
        if executed_cases_count is not None:
            model.executed_cases_count = executed_cases_count
        if blocked_cases_count is not None:
            model.blocked_cases_count = blocked_cases_count
        if unsupported_cases_count is not None:
            model.unsupported_cases_count = unsupported_cases_count
        if cancelled_cases_count is not None:
            model.cancelled_cases_count = cancelled_cases_count
        if error_cases_count is not None:
            model.error_cases_count = error_cases_count
        if halt_reason is not None:
            model.halt_reason = halt_reason

        if status in (
            ExecutionTrackingStatus.COMPLETED,
            ExecutionTrackingStatus.CANCELLED,
            ExecutionTrackingStatus.INTERRUPTED,
            ExecutionTrackingStatus.ERROR,
        ):
            model.completed_at_utc = datetime.now(UTC)

        self.db.flush()
        return model

    def get_execution(
        self, project_id: str, execution_id: str
    ) -> C3ExecutionModel | None:
        """Retrieve a tracked execution record scoped to project."""
        return self.db.scalars(
            select(C3ExecutionModel).where(
                C3ExecutionModel.project_id == project_id,
                C3ExecutionModel.execution_id == execution_id,
            )
        ).first()

    def list_executions(
        self,
        project_id: str,
        suite_digest: str | None = None,
        status: str | None = None,
        target_mode: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[C3ExecutionModel], int]:
        """List tracked executions with deterministic pagination."""
        query = select(C3ExecutionModel).where(
            C3ExecutionModel.project_id == project_id
        )
        if suite_digest:
            query = query.where(C3ExecutionModel.suite_digest == suite_digest)
        if status:
            query = query.where(C3ExecutionModel.status == status)
        if target_mode:
            query = query.where(C3ExecutionModel.target_mode == target_mode)

        count_query = select(func.count()).select_from(query.subquery())
        total = self.db.scalar(count_query) or 0

        items = list(
            self.db.scalars(
                query.order_by(
                    C3ExecutionModel.started_at_utc.desc(),
                    C3ExecutionModel.id.desc(),
                )
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return items, total

    # -----------------------------------------------------------------------
    # Matched Pair Evidence Operations
    # -----------------------------------------------------------------------

    def save_matched_pair(
        self,
        project_id: str,
        evidence: MatchedPairEvidence,
        execution_id: str | None = None,
    ) -> tuple[C3MatchedPairModel, bool]:
        """Idempotently persist matched trial pair evidence.

        Returns (model, created_new).
        Raises ConflictError if pair exists with conflicting digest.
        """
        sanitized_ev = sanitize_arguments(evidence.model_dump(mode="json"))
        evidence_digest = compute_content_digest(sanitized_ev)

        existing = self.db.scalars(
            select(C3MatchedPairModel).where(
                C3MatchedPairModel.pair_id == evidence.pair_id
            )
        ).first()

        if existing:
            if existing.project_id != project_id:
                raise ConflictError(
                    f"Matched pair '{evidence.pair_id}' already exists under a different project scope."
                )
            if existing.evidence_digest != evidence_digest:
                raise ConflictError(
                    f"Matched pair '{evidence.pair_id}' already exists with conflicting immutable evidence content."
                )
            return existing, False

        # Validate execution scope if execution_id is specified
        if execution_id:
            exec_model = self.db.scalars(
                select(C3ExecutionModel).where(
                    C3ExecutionModel.project_id == project_id,
                    C3ExecutionModel.execution_id == execution_id,
                )
            ).first()
            if not exec_model:
                raise EntityNotFoundError(
                    f"Referenced execution '{execution_id}' does not exist in project '{project_id}'."
                )

        pair_model = C3MatchedPairModel(
            pair_id=evidence.pair_id,
            execution_id=execution_id,
            case_id=evidence.case_id,
            project_id=project_id,
            run_id=evidence.run_id,
            clean_trial_id=evidence.clean_trial.trial_id,
            fault_trial_id=evidence.fault_trial.trial_id,
            readiness_status=evidence.readiness_status.value,
            clean_qualification=evidence.clean_qualification.value,
            exposure_status=evidence.exposure_status.value,
            exposure_assessed=evidence.exposure_assessed,
            cleanup_status=evidence.cleanup_status.value,
            clean_execution_status=evidence.clean_trial.execution_status.value,
            fault_execution_status=evidence.fault_trial.execution_status.value,
            evidence_complete=evidence.fault_trial.evidence_complete,
            evidence_digest=evidence_digest,
            evidence_snapshot=sanitized_ev,
            created_at_utc=datetime.now(UTC),
        )

        self.db.add(pair_model)
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                f"Integrity conflict while saving pair '{evidence.pair_id}': {exc.orig}"
            ) from exc

        return pair_model, True

    def get_matched_pair(
        self, project_id: str, pair_id: str
    ) -> C3MatchedPairModel | None:
        """Retrieve a matched pair evidence record by pair_id in project."""
        return self.db.scalars(
            select(C3MatchedPairModel).where(
                C3MatchedPairModel.project_id == project_id,
                C3MatchedPairModel.pair_id == pair_id,
            )
        ).first()

    def list_matched_pairs(
        self,
        project_id: str,
        execution_id: str | None = None,
        case_id: str | None = None,
        run_id: str | None = None,
        exposure_status: str | None = None,
        clean_qualification: str | None = None,
        fault_execution_status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[C3MatchedPairModel], int]:
        """List matched trial pairs with deterministic ordering and bounded pagination."""
        query = select(C3MatchedPairModel).where(
            C3MatchedPairModel.project_id == project_id
        )
        if execution_id:
            query = query.where(C3MatchedPairModel.execution_id == execution_id)
        if case_id:
            query = query.where(C3MatchedPairModel.case_id == case_id)
        if run_id:
            query = query.where(C3MatchedPairModel.run_id == run_id)
        if exposure_status:
            query = query.where(C3MatchedPairModel.exposure_status == exposure_status)
        if clean_qualification:
            query = query.where(
                C3MatchedPairModel.clean_qualification == clean_qualification
            )
        if fault_execution_status:
            query = query.where(
                C3MatchedPairModel.fault_execution_status == fault_execution_status
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = self.db.scalar(count_query) or 0

        items = list(
            self.db.scalars(
                query.order_by(
                    C3MatchedPairModel.created_at_utc.desc(),
                    C3MatchedPairModel.id.desc(),
                )
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return items, total

    # -----------------------------------------------------------------------
    # Evaluation Operations
    # -----------------------------------------------------------------------

    def save_evaluation(
        self,
        project_id: str,
        evaluation: RecoveryEvaluationResult,
        inputs_digest: str,
        c2_facts_provenance: list[dict[str, Any]],
    ) -> tuple[C3EvaluationModel, bool]:
        """Idempotently persist an authoritative recovery evaluation result.

        Uses uniqueness constraint on (pair_id, evaluator_version, rule_set_version, inputs_digest)
        to prevent duplicate computation records while supporting append-only evaluation history.
        """
        existing = self.db.scalars(
            select(C3EvaluationModel).where(
                C3EvaluationModel.pair_id == evaluation.pair_id,
                C3EvaluationModel.evaluator_version == evaluation.evaluator_version,
                C3EvaluationModel.rule_set_version == evaluation.rule_set_version,
                C3EvaluationModel.inputs_digest == inputs_digest,
            )
        ).first()

        if existing:
            if existing.project_id != project_id:
                raise ConflictError(
                    f"Evaluation for pair '{evaluation.pair_id}' exists in a different project scope."
                )
            return existing, False

        # Validate parent matched pair exists and belongs to project
        parent_pair = self.db.scalars(
            select(C3MatchedPairModel).where(
                C3MatchedPairModel.project_id == project_id,
                C3MatchedPairModel.pair_id == evaluation.pair_id,
            )
        ).first()
        if not parent_pair:
            raise EntityNotFoundError(
                f"Referenced matched pair '{evaluation.pair_id}' does not exist in project '{project_id}'."
            )

        sanitized_eval = sanitize_arguments(evaluation.model_dump(mode="json"))
        rule_results_data = [
            sanitize_arguments(r.model_dump(mode="json"))
            for r in evaluation.rule_results
        ]

        from uuid import uuid4

        evaluation_id = f"eval-{uuid4().hex[:12]}"

        eval_model = C3EvaluationModel(
            evaluation_id=evaluation_id,
            pair_id=evaluation.pair_id,
            case_id=evaluation.case_id,
            project_id=project_id,
            evaluator_version=evaluation.evaluator_version,
            rule_set_version=evaluation.rule_set_version,
            evaluation_status=evaluation.evaluation_status.value,
            recovery_verdict=evaluation.recovery_verdict.value
            if evaluation.recovery_verdict
            else None,
            first_violated_rule=evaluation.first_violated_rule,
            actor_attribution=evaluation.actor_attribution,
            inputs_digest=inputs_digest,
            c2_facts_provenance_snapshot=c2_facts_provenance,
            rule_results_snapshot=rule_results_data,
            evaluation_snapshot=sanitized_eval,
            created_at_utc=datetime.now(UTC),
        )

        self.db.add(eval_model)
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                f"Integrity conflict while saving evaluation for pair '{evaluation.pair_id}': {exc.orig}"
            ) from exc

        return eval_model, True

    def get_evaluation(
        self, project_id: str, evaluation_id: str
    ) -> C3EvaluationModel | None:
        """Retrieve a stored recovery evaluation by evaluation_id scoped to project."""
        return self.db.scalars(
            select(C3EvaluationModel).where(
                C3EvaluationModel.project_id == project_id,
                C3EvaluationModel.evaluation_id == evaluation_id,
            )
        ).first()

    def list_evaluations(
        self,
        project_id: str,
        pair_id: str | None = None,
        case_id: str | None = None,
        recovery_verdict: str | None = None,
        evaluator_version: str | None = None,
        rule_set_version: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[C3EvaluationModel], int]:
        """List stored recovery evaluations with deterministic ordering and bounded pagination."""
        query = select(C3EvaluationModel).where(
            C3EvaluationModel.project_id == project_id
        )
        if pair_id:
            query = query.where(C3EvaluationModel.pair_id == pair_id)
        if case_id:
            query = query.where(C3EvaluationModel.case_id == case_id)
        if recovery_verdict:
            query = query.where(C3EvaluationModel.recovery_verdict == recovery_verdict)
        if evaluator_version:
            query = query.where(
                C3EvaluationModel.evaluator_version == evaluator_version
            )
        if rule_set_version:
            query = query.where(C3EvaluationModel.rule_set_version == rule_set_version)

        count_query = select(func.count()).select_from(query.subquery())
        total = self.db.scalar(count_query) or 0

        items = list(
            self.db.scalars(
                query.order_by(
                    C3EvaluationModel.created_at_utc.desc(),
                    C3EvaluationModel.id.desc(),
                )
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return items, total
