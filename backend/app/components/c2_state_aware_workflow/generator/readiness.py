"""Readiness validator for reference models and generated workflow tests.

Enforces MODEL NOT READY for unapproved or inconsistent reference models and
TEST NOT READY for ambiguous, infeasible, or degenerated test cases.
"""

from typing import Any

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    ExecutionMode,
    GeneratedTestDefinition,
    TestCategory,
    TestReadinessStatus,
)
from app.components.c2_state_aware_workflow.persistence.models import (
    C2ValidationReport,
    C2WorkflowModel,
)


class ModelNotReadyError(Exception):
    """Raised when an EFSM model does not satisfy the criteria for test generation."""

    def __init__(self, reasons: list[str]):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


class GenerationReadinessValidator:
    """Validates prerequisite readiness of reference models and generated tests."""

    @staticmethod
    def validate_model_readiness(
        model_record: C2WorkflowModel,
        latest_report: C2ValidationReport | None,
    ) -> tuple[bool, str, list[str]]:
        """Verify that a reference model is approved, validated, and hash-consistent."""
        reasons: list[str] = []

        if model_record.lifecycle_status != "APPROVED":
            reasons.append(
                f"Model '{model_record.model_id}' version '{model_record.version}' has lifecycle_status "
                f"'{model_record.lifecycle_status}', but must be 'APPROVED' for test generation."
            )

        if latest_report is None:
            reasons.append(
                "Model has never been validated (no validation report found)."
            )
        else:
            if latest_report.content_hash != model_record.content_hash:
                reasons.append(
                    f"Validation report content hash '{latest_report.content_hash}' does not match "
                    f"current model content hash '{model_record.content_hash}'."
                )
            if not latest_report.is_valid:
                reasons.append(
                    f"Model validation failed with {len(latest_report.errors)} error(s)."
                )

        is_ready = len(reasons) == 0
        readiness = "READY" if is_ready else "MODEL NOT READY"
        return is_ready, readiness, reasons

    @staticmethod
    def validate_test_readiness(
        case: GeneratedTestDefinition,
        model: EFSMModelDefinition,
        fixture_data: dict[str, Any] | None = None,
    ) -> tuple[TestReadinessStatus, list[str]]:
        """Validate an individual generated test definition against feasibility and ambiguity criteria."""
        reasons: list[str] = []

        # 1. Task non-emptiness
        if not case.task or not case.task.strip():
            reasons.append("Task prompt is missing or empty.")

        # 2. Fixture reference specified
        if not case.fixture_ref or not case.fixture_ref.strip():
            reasons.append("Fixture reference is missing or empty.")

        # 3. Path feasibility against model graph
        valid_trans_ids = {t.id for t in model.transitions}
        valid_state_ids = {s.id for s in model.states}

        if case.category != TestCategory.MUTATED:
            for path in case.private_reference_paths:
                for state in path:
                    if state not in valid_state_ids:
                        reasons.append(
                            f"Path references state '{state}' which is not in the EFSM model."
                        )

            for trans_seq in case.private_reference_transitions:
                for tid in trans_seq:
                    if tid not in valid_trans_ids:
                        reasons.append(
                            f"Reference path includes transition '{tid}' which does not exist in the model."
                        )

            # Check that accepting outcomes end in accepting states
            if case.category in (TestCategory.VALID, TestCategory.ALTERNATIVE):
                for path in case.private_reference_paths:
                    if path and path[-1] not in model.accepting_state_ids:
                        reasons.append(
                            f"Valid/Alternative test terminates in non-accepting state '{path[-1]}'."
                        )

            # Check that negative outcomes end in rejection states
            if case.category == TestCategory.NEGATIVE:
                for path in case.private_reference_paths:
                    if path and path[-1] not in model.rejection_state_ids:
                        reasons.append(
                            f"Negative test terminates in state '{path[-1]}' which is not a declared rejection state."
                        )

        # 4. Mutation checks
        if case.category == TestCategory.MUTATED:
            if case.mutation_provenance is None:
                reasons.append(
                    "Mutated test case is missing mutation_provenance metadata."
                )
            elif case.mutation_provenance.is_ambiguous_or_non_discriminating:
                reasons.append(
                    f"Mutation is non-discriminating: {case.mutation_provenance.ambiguity_reason}"
                )

            # Synthetic mutants must be tagged as synthetic_evaluator mode
            if case.execution_mode != ExecutionMode.SYNTHETIC_EVALUATOR:
                reasons.append(
                    f"Mutated test has execution mode '{case.execution_mode}', expected '{ExecutionMode.SYNTHETIC_EVALUATOR}'."
                )

        status = (
            TestReadinessStatus.TEST_READY
            if len(reasons) == 0
            else TestReadinessStatus.TEST_NOT_READY
        )
        return status, reasons
