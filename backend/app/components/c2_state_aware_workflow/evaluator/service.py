"""High-level service orchestrating workflow evaluation, evidence retention, and reproduction."""

import hashlib
import json
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


def compute_evidence_digest(evidence_dict: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 digest of runtime evidence payload."""
    canonical_str = json.dumps(evidence_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


class WorkflowEvaluationService:
    """Coordinates validation, alignment, verdict computation, evidence retention, and reproduction."""

    def __init__(self, db: Session, max_configurations: int = 200):
        self.db = db
        self.repo = C2ModelRepository(db)
        self.max_configurations = max_configurations
        self.engine = ConformanceEvaluationEngine(max_configurations=max_configurations)

    def evaluate_test_run(
        self,
        project_id: str,
        suite_id: str,
        test_id: str,
        evidence: RuntimeEvidenceContract,
        fixture_data: dict[str, Any] | None = None,
        evaluator_version: str = "c2_evaluator_v1",
        evaluator_config: dict[str, Any] | None = None,
        runner_id: str | None = None,
        execution_provenance: dict[str, Any] | None = None,
    ) -> EvaluationResultContract:
        """Evaluate a test run, retain original evidence snapshot, and store the additive evaluation result."""
        # 1. Retrieve test case definition
        case_record = self.repo.get_test_case(project_id, suite_id, test_id)
        if case_record is None:
            raise TestCaseNotFoundError(
                f"Test case '{test_id}' not found in suite '{suite_id}' for project '{project_id}'."
            )

        test_def = GeneratedTestDefinition(**case_record.definition)

        # 2. Retrieve pinned reference model
        model_record = self.repo.get_model(
            project_id, test_def.pinned_model_id, test_def.pinned_model_version
        )
        if model_record is None:
            raise ModelNotFoundError(
                f"Pinned reference model '{test_def.pinned_model_id}' version '{test_def.pinned_model_version}' not found."
            )

        model_def = EFSMModelDefinition(**model_record.definition)
        is_approved = model_record.lifecycle_status == "APPROVED"

        # 3. Compute canonical evidence digest and retain original evidence
        evidence_dict = evidence.model_dump(mode="json")
        evidence_digest = compute_evidence_digest(evidence_dict)

        actual_runner_id = runner_id or evidence.collector_provenance.get(
            "runner_id", "c2_runner"
        )
        provenance = (
            execution_provenance
            or evidence.collector_provenance
            or {
                "intended_execution_mode": test_def.execution_mode.value,
                "actual_execution_origin": evidence.execution_mode,
                "runner_id": actual_runner_id,
            }
        )

        # Retain original evidence (raises ConflictingEvidenceIntegrityError if conflicting evidence exists under run_id)
        evidence_record = self.repo.save_execution_evidence(
            project_id=project_id,
            suite_id=suite_id,
            test_id=test_id,
            run_id=evidence.run_id,
            evidence_digest=evidence_digest,
            model_id=test_def.pinned_model_id,
            model_version=test_def.pinned_model_version,
            model_content_hash=model_record.content_hash,
            execution_mode=evidence.execution_mode,
            runner_id=actual_runner_id,
            evidence_payload=evidence_dict,
            execution_provenance=provenance,
        )

        # 4. Execute conformance evaluation
        cfg = dict(evaluator_config or {})
        max_configs = cfg.get("max_configurations", self.max_configurations)
        engine = (
            self.engine
            if max_configs == self.max_configurations
            else ConformanceEvaluationEngine(max_configurations=max_configs)
        )

        eval_result = engine.evaluate(
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
                "evaluator_version": evaluator_version,
            }
        )

        # 5. Persist additive evaluation result
        saved_record = self.repo.save_evaluation_result(
            project_id=project_id,
            suite_id=suite_id,
            test_id=test_id,
            run_id=evidence.run_id,
            result=eval_result,
            evaluator_config=cfg,
            evidence_digest=evidence_digest,
            execution_evidence_id=evidence_record.id,
        )

        return eval_result.model_copy(update={"evaluation_id": saved_record.id})

    def re_evaluate_execution(
        self,
        project_id: str,
        evaluation_id: str,
        evaluator_version: str | None = None,
        evaluator_config: dict[str, Any] | None = None,
    ) -> EvaluationResultContract:
        """Reproduce evaluation from retained evidence, pinned model, and test definition."""
        existing_eval = self.repo.get_evaluation_result(project_id, evaluation_id)
        if existing_eval is None:
            raise TestCaseNotFoundError(
                f"Evaluation result '{evaluation_id}' not found for project '{project_id}'."
            )

        evidence_rec = self.repo.get_execution_evidence(
            project_id, existing_eval.run_id
        )
        if evidence_rec is None:
            raise TestCaseNotFoundError(
                f"Retained evidence for run '{existing_eval.run_id}' not found."
            )

        evidence = RuntimeEvidenceContract(**evidence_rec.evidence_payload)

        new_version = evaluator_version or existing_eval.evaluator_version
        new_config = (
            evaluator_config
            if evaluator_config is not None
            else (existing_eval.evaluator_config or {})
        )

        # Retrieve test and model
        case_record = self.repo.get_test_case(
            project_id, existing_eval.suite_id, existing_eval.test_id
        )
        if case_record is None:
            raise TestCaseNotFoundError(
                f"Test case '{existing_eval.test_id}' not found."
            )
        test_def = GeneratedTestDefinition(**case_record.definition)

        model_record = self.repo.get_model(
            project_id, test_def.pinned_model_id, test_def.pinned_model_version
        )
        if model_record is None:
            raise ModelNotFoundError(
                f"Pinned model '{test_def.pinned_model_id}' not found."
            )
        model_def = EFSMModelDefinition(**model_record.definition)
        is_approved = model_record.lifecycle_status == "APPROVED"

        max_configs = new_config.get("max_configurations", self.max_configurations)
        engine = ConformanceEvaluationEngine(max_configurations=max_configs)

        eval_result = engine.evaluate(
            model=model_def,
            test_def=test_def,
            evidence=evidence,
            model_is_approved=is_approved,
            pinned_content_hash=model_record.content_hash,
        )

        eval_result = eval_result.model_copy(
            update={
                "project_id": project_id,
                "suite_id": existing_eval.suite_id,
                "run_id": existing_eval.run_id,
                "evaluator_version": new_version,
            }
        )

        saved_record = self.repo.save_evaluation_result(
            project_id=project_id,
            suite_id=existing_eval.suite_id,
            test_id=existing_eval.test_id,
            run_id=existing_eval.run_id,
            result=eval_result,
            evaluator_config=new_config,
            evidence_digest=evidence_rec.evidence_digest,
            execution_evidence_id=evidence_rec.id,
            reproduced_from_evaluation_id=existing_eval.id,
        )

        return eval_result.model_copy(update={"evaluation_id": saved_record.id})
