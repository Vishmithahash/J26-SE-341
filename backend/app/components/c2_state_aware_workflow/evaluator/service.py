"""High-level service orchestrating workflow evaluation and persistence."""

from typing import Any

from sqlalchemy.orm import Session

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)
from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    EvaluationResultContract,
)
from app.components.c2_state_aware_workflow.contracts.runtime_evidence import (
    RuntimeEvidenceContract,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    GeneratedTestDefinition,
)
from app.components.c2_state_aware_workflow.evaluator.engine import (
    ConformanceEvaluationEngine,
)
from app.components.c2_state_aware_workflow.persistence.repository import (
    C2ModelRepository,
    ModelNotFoundError,
    TestCaseNotFoundError,
)


class WorkflowEvaluationService:
    """Coordinates validation, alignment, verdict computation, and persistence."""

    def __init__(self, db: Session, max_configurations: int = 200):
        self.db = db
        self.repo = C2ModelRepository(db)
        self.engine = ConformanceEvaluationEngine(max_configurations=max_configurations)

    def evaluate_test_run(
        self,
        project_id: str,
        suite_id: str,
        test_id: str,
        evidence: RuntimeEvidenceContract,
        fixture_data: dict[str, Any] | None = None,
    ) -> EvaluationResultContract:
        """Evaluate a test run and store the result in the database."""
        # Retrieve test case definition
        case_record = self.repo.get_test_case(project_id, suite_id, test_id)
        if case_record is None:
            raise TestCaseNotFoundError(
                f"Test case '{test_id}' not found in suite '{suite_id}' for project '{project_id}'."
            )

        test_def = GeneratedTestDefinition(**case_record.definition)

        # Retrieve pinned reference model
        model_record = self.repo.get_model(
            project_id, test_def.pinned_model_id, test_def.pinned_model_version
        )
        if model_record is None:
            raise ModelNotFoundError(
                f"Pinned reference model '{test_def.pinned_model_id}' version '{test_def.pinned_model_version}' not found."
            )

        model_def = EFSMModelDefinition(**model_record.definition)
        is_approved = model_record.lifecycle_status == "APPROVED"

        # Execute evaluation
        eval_result = self.engine.evaluate(
            model=model_def,
            test_def=test_def,
            evidence=evidence,
            fixture_data=fixture_data,
            model_is_approved=is_approved,
            pinned_content_hash=model_record.content_hash,
        )

        eval_result = eval_result.model_copy(
            update={
                "project_id": project_id,
                "suite_id": suite_id,
                "run_id": evidence.run_id,
            }
        )

        # Persist evaluation result
        saved_record = self.repo.save_evaluation_result(
            project_id=project_id,
            suite_id=suite_id,
            test_id=test_id,
            run_id=evidence.run_id,
            result=eval_result,
        )

        return eval_result.model_copy(update={"evaluation_id": saved_record.id})
