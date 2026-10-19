"""Repository for versioned C2 EFSM models and validation reports."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session


def utc_now() -> datetime:
    return datetime.now(UTC)


from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)
from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    EvaluationResultContract,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    GeneratedTestSuite,
)
from app.components.c2_state_aware_workflow.persistence.hashing import (
    compute_model_content_hash,
)
from app.components.c2_state_aware_workflow.persistence.models import (
    C2EvaluationResult,
    C2TestCase,
    C2TestSuite,
    C2ValidationReport,
    C2WorkflowModel,
)


class C2PersistenceError(Exception):
    """Base exception for C2 persistence errors."""


class ModelNotFoundError(C2PersistenceError):
    """Raised when a requested model version is not found."""


class ModelAlreadyExistsError(C2PersistenceError):
    """Raised when attempting to create an already existing (project_id, model_id, version)."""


class ApprovedModelImmutableError(C2PersistenceError):
    """Raised when attempting to modify an approved model definition."""


class ApprovalBlockedError(C2PersistenceError):
    """Raised when approval requirements are not satisfied."""


class TestSuiteNotFoundError(C2PersistenceError):
    """Raised when a requested test suite is not found."""


class TestCaseNotFoundError(C2PersistenceError):
    """Raised when a requested test case is not found."""


class EvaluationResultNotFoundError(C2PersistenceError):
    """Raised when a requested evaluation result is not found."""


class C2ModelRepository:
    """Manages transactional persistence, immutability, and approval lifecycle for C2 models."""

    def __init__(self, db: Session):
        self.db = db

    def get_model(
        self, project_id: str, model_id: str, version: str
    ) -> C2WorkflowModel | None:
        stmt = select(C2WorkflowModel).where(
            C2WorkflowModel.project_id == project_id,
            C2WorkflowModel.model_id == model_id,
            C2WorkflowModel.version == version,
            C2WorkflowModel.is_active.is_(True),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_models(self, project_id: str) -> list[C2WorkflowModel]:
        stmt = (
            select(C2WorkflowModel)
            .where(
                C2WorkflowModel.project_id == project_id,
                C2WorkflowModel.is_active.is_(True),
            )
            .order_by(C2WorkflowModel.model_id, C2WorkflowModel.version.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def create_draft_model(
        self,
        project_id: str,
        definition: EFSMModelDefinition | dict[str, Any],
    ) -> C2WorkflowModel:
        if isinstance(definition, EFSMModelDefinition):
            def_dict = definition.model_dump(mode="json")
            model_id = definition.model_id
            version = definition.version
            name = definition.name
            description = definition.description
            schema_version = definition.schema_version
        else:
            def_dict = definition
            model_id = def_dict["model_id"]
            version = def_dict["version"]
            name = def_dict["name"]
            description = def_dict.get("description")
            schema_version = def_dict.get("schema_version", "2026.1")

        existing = self.get_model(project_id, model_id, version)
        if existing is not None:
            raise ModelAlreadyExistsError(
                f"Model '{model_id}' version '{version}' already exists for project '{project_id}'."
            )

        content_hash = compute_model_content_hash(def_dict)

        record = C2WorkflowModel(
            project_id=project_id,
            model_id=model_id,
            version=version,
            schema_version=schema_version,
            name=name,
            description=description,
            definition=def_dict,
            content_hash=content_hash,
            lifecycle_status="DRAFT",
            is_active=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def update_draft_model(
        self,
        project_id: str,
        model_id: str,
        version: str,
        definition: EFSMModelDefinition | dict[str, Any],
    ) -> C2WorkflowModel:
        record = self.get_model(project_id, model_id, version)
        if record is None:
            raise ModelNotFoundError(
                f"Model '{model_id}' version '{version}' not found for project '{project_id}'."
            )

        if record.lifecycle_status == "APPROVED":
            raise ApprovedModelImmutableError(
                f"Model '{model_id}' version '{version}' is APPROVED and immutable. Create a new draft version instead."
            )

        if isinstance(definition, EFSMModelDefinition):
            def_dict = definition.model_dump(mode="json")
            name = definition.name
            description = definition.description
        else:
            def_dict = definition
            name = def_dict.get("name", record.name)
            description = def_dict.get("description", record.description)

        content_hash = compute_model_content_hash(def_dict)

        record.definition = def_dict
        record.name = name
        record.description = description
        record.content_hash = content_hash
        # If model was previously validated, changing definition reverts status to DRAFT
        record.lifecycle_status = "DRAFT"
        record.updated_at = utc_now()

        self.db.commit()
        self.db.refresh(record)
        return record

    def save_validation_report(
        self,
        model_record: C2WorkflowModel,
        is_valid: bool,
        readiness: str,
        summary: dict[str, Any],
        errors: list[dict[str, Any]],
        warnings: list[dict[str, Any]],
        diagnostics: dict[str, Any],
    ) -> C2ValidationReport:
        report = C2ValidationReport(
            model_record_id=model_record.id,
            project_id=model_record.project_id,
            model_id=model_record.model_id,
            version=model_record.version,
            content_hash=model_record.content_hash,
            is_valid=is_valid,
            readiness=readiness,
            summary=summary,
            errors=errors,
            warnings=warnings,
            diagnostics=diagnostics,
            created_at=utc_now(),
        )
        self.db.add(report)

        # Promote to VALIDATED only if currently DRAFT and valid
        if is_valid and model_record.lifecycle_status == "DRAFT":
            model_record.lifecycle_status = "VALIDATED"
            model_record.updated_at = utc_now()

        self.db.commit()
        self.db.refresh(report)
        return report

    def get_latest_validation_report(
        self,
        project_id: str,
        model_id: str,
        version: str,
    ) -> C2ValidationReport | None:
        stmt = (
            select(C2ValidationReport)
            .where(
                C2ValidationReport.project_id == project_id,
                C2ValidationReport.model_id == model_id,
                C2ValidationReport.version == version,
            )
            .order_by(C2ValidationReport.created_at.desc())
        )
        return self.db.execute(stmt).scalars().first()

    def list_validation_reports(
        self,
        project_id: str,
        model_id: str,
        version: str,
    ) -> list[C2ValidationReport]:
        stmt = (
            select(C2ValidationReport)
            .where(
                C2ValidationReport.project_id == project_id,
                C2ValidationReport.model_id == model_id,
                C2ValidationReport.version == version,
            )
            .order_by(C2ValidationReport.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def approve_model(
        self,
        project_id: str,
        model_id: str,
        version: str,
        reviewer_id: str,
        review_basis: str,
        review_notes: str | None = None,
    ) -> C2WorkflowModel:
        record = self.get_model(project_id, model_id, version)
        if record is None:
            raise ModelNotFoundError(
                f"Model '{model_id}' version '{version}' not found for project '{project_id}'."
            )

        if record.lifecycle_status == "APPROVED":
            return record

        report = self.get_latest_validation_report(project_id, model_id, version)
        if report is None or not report.is_valid:
            raise ApprovalBlockedError(
                "Approval blocked: model has not passed structural and semantic validation."
            )

        if report.content_hash != record.content_hash:
            raise ApprovalBlockedError(
                "Approval blocked: validation report is stale (definition content hash does not match current model)."
            )

        if report.errors:
            raise ApprovalBlockedError(
                f"Approval blocked: validation report contains {len(report.errors)} unresolved errors."
            )

        record.lifecycle_status = "APPROVED"
        record.approved_by = reviewer_id
        record.approved_at = utc_now()
        record.review_basis = review_basis
        record.review_notes = review_notes
        record.updated_at = utc_now()

        self.db.commit()
        self.db.refresh(record)
        return record

    def create_new_draft_version(
        self,
        project_id: str,
        model_id: str,
        from_version: str,
        new_version: str,
        description: str | None = None,
    ) -> C2WorkflowModel:
        source = self.get_model(project_id, model_id, from_version)
        if source is None:
            raise ModelNotFoundError(
                f"Source model '{model_id}' version '{from_version}' not found for project '{project_id}'."
            )

        existing = self.get_model(project_id, model_id, new_version)
        if existing is not None:
            raise ModelAlreadyExistsError(
                f"Target version '{new_version}' for model '{model_id}' already exists in project '{project_id}'."
            )

        new_def = dict(source.definition)
        new_def["version"] = new_version
        if description:
            new_def["description"] = description

        content_hash = compute_model_content_hash(new_def)

        new_record = C2WorkflowModel(
            project_id=project_id,
            model_id=model_id,
            version=new_version,
            schema_version=source.schema_version,
            name=source.name,
            description=description or source.description,
            definition=new_def,
            content_hash=content_hash,
            lifecycle_status="DRAFT",
            is_active=True,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.db.add(new_record)
        self.db.commit()
        self.db.refresh(new_record)
        return new_record

    def save_test_suite(
        self,
        suite: GeneratedTestSuite,
        model_record: C2WorkflowModel,
    ) -> C2TestSuite:
        """Persist a generated test suite and all constituent test cases transactionally."""
        suite_record = C2TestSuite(
            project_id=suite.project_id,
            suite_id=suite.suite_id,
            model_record_id=model_record.id,
            model_id=suite.pinned_model_id,
            model_version=suite.pinned_model_version,
            model_content_hash=suite.model_content_hash,
            generator_version=suite.generator_version,
            seed=suite.seed,
            config=suite.config,
            diagnostics=suite.diagnostics.model_dump(mode="json"),
            total_cases=suite.total_cases,
            ready_cases_count=suite.ready_cases_count,
            not_ready_cases_count=suite.not_ready_cases_count,
            category_counts=suite.category_counts,
            created_at=utc_now(),
        )
        self.db.add(suite_record)
        self.db.flush()

        for case in suite.cases:
            case_record = C2TestCase(
                suite_record_id=suite_record.id,
                project_id=suite.project_id,
                suite_id=suite.suite_id,
                test_id=case.test_id,
                category=case.category.value,
                execution_mode=case.execution_mode.value,
                task=case.task,
                fixture_ref=case.fixture_ref,
                seed=case.seed,
                definition=case.model_dump(mode="json"),
                readiness=case.readiness.value,
                readiness_reasons=case.readiness_reasons,
                is_ready=(case.readiness.value == "TEST_READY"),
                created_at=utc_now(),
            )
            self.db.add(case_record)

        self.db.commit()
        self.db.refresh(suite_record)
        return suite_record

    def get_test_suite(self, project_id: str, suite_id: str) -> C2TestSuite | None:
        """Retrieve a specific test suite by project_id and suite_id."""
        stmt = select(C2TestSuite).where(
            C2TestSuite.project_id == project_id,
            C2TestSuite.suite_id == suite_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_test_suites(self, project_id: str) -> list[C2TestSuite]:
        """List all test suites for a given project."""
        stmt = (
            select(C2TestSuite)
            .where(C2TestSuite.project_id == project_id)
            .order_by(C2TestSuite.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_test_case(
        self, project_id: str, suite_id: str, test_id: str
    ) -> C2TestCase | None:
        """Retrieve an individual test case definition."""
        stmt = select(C2TestCase).where(
            C2TestCase.project_id == project_id,
            C2TestCase.suite_id == suite_id,
            C2TestCase.test_id == test_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_test_cases(
        self,
        project_id: str,
        suite_id: str,
        category: str | None = None,
        readiness: str | None = None,
    ) -> list[C2TestCase]:
        """List test cases for a suite with optional category and readiness filters."""
        stmt = select(C2TestCase).where(
            C2TestCase.project_id == project_id,
            C2TestCase.suite_id == suite_id,
        )
        if category:
            stmt = stmt.where(C2TestCase.category == category)
        if readiness:
            stmt = stmt.where(C2TestCase.readiness == readiness)
        stmt = stmt.order_by(C2TestCase.created_at.asc())
        return list(self.db.execute(stmt).scalars().all())

    def save_evaluation_result(
        self,
        project_id: str,
        suite_id: str,
        test_id: str,
        run_id: str,
        result: EvaluationResultContract,
    ) -> C2EvaluationResult:
        """Persist a conformance evaluation result pinned to exact model and suite/case."""
        # Check if record already exists for this (project_id, suite_id, test_id, run_id)
        stmt = select(C2EvaluationResult).where(
            C2EvaluationResult.project_id == project_id,
            C2EvaluationResult.suite_id == suite_id,
            C2EvaluationResult.test_id == test_id,
            C2EvaluationResult.run_id == run_id,
        )
        existing = self.db.execute(stmt).scalar_one_or_none()
        if existing is not None:
            # Update existing run result
            existing.verdict = result.verdict.value
            existing.reasons = result.reasons
            existing.violations = [v.model_dump(mode="json") for v in result.violations]
            existing.first_divergence = (
                result.first_divergence.model_dump(mode="json")
                if result.first_divergence
                else None
            )
            existing.coverage = result.coverage.model_dump(mode="json")
            existing.expected_states = result.expected_states
            existing.observed_states = result.observed_states
            existing.evidence_references = result.evidence_references
            existing.evaluator_timing_ms = result.evaluator_timing_ms
            self.db.commit()
            self.db.refresh(existing)
            return existing

        eval_record = C2EvaluationResult(
            project_id=project_id,
            suite_id=suite_id,
            test_id=test_id,
            run_id=run_id,
            model_id=result.model_id,
            model_version=result.model_version,
            model_content_hash=result.model_content_hash,
            evaluator_version=result.evaluator_version,
            verdict=result.verdict.value,
            reasons=result.reasons,
            violations=[v.model_dump(mode="json") for v in result.violations],
            first_divergence=(
                result.first_divergence.model_dump(mode="json")
                if result.first_divergence
                else None
            ),
            coverage=result.coverage.model_dump(mode="json"),
            expected_states=result.expected_states,
            observed_states=result.observed_states,
            evidence_references=result.evidence_references,
            evaluator_timing_ms=result.evaluator_timing_ms,
            created_at=utc_now(),
        )
        self.db.add(eval_record)
        self.db.commit()
        self.db.refresh(eval_record)
        return eval_record

    def get_evaluation_result(
        self, project_id: str, evaluation_id: str
    ) -> C2EvaluationResult | None:
        """Retrieve an evaluation record by project_id and evaluation_id."""
        stmt = select(C2EvaluationResult).where(
            C2EvaluationResult.project_id == project_id,
            C2EvaluationResult.id == evaluation_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_evaluation_results(
        self,
        project_id: str,
        suite_id: str | None = None,
        test_id: str | None = None,
        verdict: str | None = None,
    ) -> list[C2EvaluationResult]:
        """List evaluation records with optional suite, test, or verdict filters."""
        stmt = select(C2EvaluationResult).where(
            C2EvaluationResult.project_id == project_id
        )
        if suite_id:
            stmt = stmt.where(C2EvaluationResult.suite_id == suite_id)
        if test_id:
            stmt = stmt.where(C2EvaluationResult.test_id == test_id)
        if verdict:
            stmt = stmt.where(C2EvaluationResult.verdict == verdict)
        stmt = stmt.order_by(C2EvaluationResult.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())
