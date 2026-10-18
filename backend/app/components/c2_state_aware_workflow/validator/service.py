"""Cohesive validation service combining structural and bounded semantic checks."""

from typing import Any

from sqlalchemy.orm import Session

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)
from app.components.c2_state_aware_workflow.persistence.models import (
    C2ValidationReport,
    C2WorkflowModel,
)
from app.components.c2_state_aware_workflow.persistence.repository import (
    C2ModelRepository,
    ModelNotFoundError,
)
from app.components.c2_state_aware_workflow.validator.semantic import (
    BoundedSemanticValidator,
)
from app.components.c2_state_aware_workflow.validator.structural import (
    StructuralValidator,
)


class ModelValidationService:
    """Orchestrates model validation and records validation reports against pinned definitions."""

    def __init__(self, db: Session, max_search_depth: int = 20):
        self.db = db
        self.structural_validator = StructuralValidator()
        self.semantic_validator = BoundedSemanticValidator(
            max_search_depth=max_search_depth
        )
        self.repo = C2ModelRepository(db)

    def validate_definition(
        self,
        definition: EFSMModelDefinition | dict[str, Any],
    ) -> tuple[
        bool,
        str,
        dict[str, Any],
        list[dict[str, Any]],
        list[dict[str, Any]],
        dict[str, Any],
    ]:
        """Run structural and semantic validation on an in-memory EFSM definition."""
        if not isinstance(definition, EFSMModelDefinition):
            model_def = EFSMModelDefinition(**definition)
        else:
            model_def = definition

        struct_errors, struct_warnings = self.structural_validator.validate(model_def)
        sem_errors, sem_warnings, sem_diagnostics = self.semantic_validator.validate(
            model_def
        )

        all_errors = struct_errors + sem_errors
        all_warnings = struct_warnings + sem_warnings
        is_valid = len(all_errors) == 0
        readiness = "READY" if is_valid else "MODEL NOT READY"

        summary = {
            "is_valid": is_valid,
            "readiness": readiness,
            "total_errors": len(all_errors),
            "total_warnings": len(all_warnings),
            "states_count": len(model_def.states),
            "transitions_count": len(model_def.transitions),
            "invariants_count": len(model_def.invariants),
        }

        diagnostics = {
            **sem_diagnostics,
            "structural_checks_passed": len(struct_errors) == 0,
            "semantic_checks_passed": len(sem_errors) == 0,
        }

        return is_valid, readiness, summary, all_errors, all_warnings, diagnostics

    def validate_model_record(
        self,
        project_id: str,
        model_id: str,
        version: str,
    ) -> C2ValidationReport:
        """Fetch model record from database, validate its definition, and persist report."""
        record: C2WorkflowModel | None = self.repo.get_model(
            project_id, model_id, version
        )
        if record is None:
            raise ModelNotFoundError(
                f"Model '{model_id}' version '{version}' not found for project '{project_id}'."
            )

        is_valid, readiness, summary, errors, warnings, diagnostics = (
            self.validate_definition(record.definition)
        )

        report = self.repo.save_validation_report(
            model_record=record,
            is_valid=is_valid,
            readiness=readiness,
            summary=summary,
            errors=errors,
            warnings=warnings,
            diagnostics=diagnostics,
        )
        return report
