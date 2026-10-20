"""High-level test generation service orchestrating generation, mutations, readiness, and persistence."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    GeneratedTestDefinition,
    GeneratedTestSuite,
    GenerateTestSuiteRequest,
    TestReadinessStatus,
)
from app.components.c2_state_aware_workflow.generator.engine import (
    CoverageGuidedGenerator,
)
from app.components.c2_state_aware_workflow.generator.mutations import (
    WorkflowMutator,
)
from app.components.c2_state_aware_workflow.generator.readiness import (
    GenerationReadinessValidator,
    ModelNotReadyError,
)
from app.components.c2_state_aware_workflow.persistence.models import (
    C2TestSuite,
    C2WorkflowModel,
)
from app.components.c2_state_aware_workflow.persistence.repository import (
    C2ModelRepository,
    ModelNotFoundError,
)


class TestGenerationService:
    """Orchestrates test generation from approved EFSM models, applies mutations, validates readiness, and persists suites."""

    __test__ = False

    def __init__(self, db: Session):
        self.db = db
        self.repo = C2ModelRepository(db)

    def generate_suite_for_model(
        self,
        project_id: str,
        model_id: str,
        version: str,
        request: GenerateTestSuiteRequest,
        fixture_data: dict[str, Any] | None = None,
    ) -> C2TestSuite:
        """Verify model readiness, generate test paths and mutations, validate cases, and persist suite."""
        model_record: C2WorkflowModel | None = self.repo.get_model(
            project_id, model_id, version
        )
        if model_record is None:
            raise ModelNotFoundError(
                f"Model '{model_id}' version '{version}' not found for project '{project_id}'."
            )

        # 1. Verify Model Readiness
        latest_report = self.repo.get_latest_validation_report(
            project_id, model_id, version
        )
        is_ready, _readiness_status, reasons = (
            GenerationReadinessValidator.validate_model_readiness(
                model_record, latest_report
            )
        )
        if not is_ready:
            raise ModelNotReadyError(reasons)

        model_def = EFSMModelDefinition(**model_record.definition)
        suite_id = f"suite_{model_id}_{version.replace('.', '_')}_{request.seed}_{uuid.uuid4().hex[:6]}"

        # 2. Coverage-Guided Path Generation
        generator = CoverageGuidedGenerator(config=request)
        base_cases, diagnostics = generator.generate(
            model=model_def,
            suite_id=suite_id,
            fixture_data=fixture_data,
        )

        all_cases: list[GeneratedTestDefinition] = list(base_cases)

        # 3. Controlled Workflow Mutation Generation
        if request.include_mutations and base_cases:
            mutator = WorkflowMutator(seed=request.seed)
            mutated_cases = mutator.generate_mutations(
                base_cases=base_cases,
                model=model_def,
                mutation_budget=request.mutation_budget,
                enabled_types=request.enabled_mutation_types,
            )
            all_cases.extend(mutated_cases)

        # 4. Individual Test Case Readiness Validation
        final_cases: list[GeneratedTestDefinition] = []
        ready_count = 0
        not_ready_count = 0
        readiness_breakdown: dict[str, int] = {
            TestReadinessStatus.TEST_READY.value: 0,
            TestReadinessStatus.TEST_NOT_READY.value: 0,
        }
        category_counts: dict[str, int] = {}

        for case in all_cases:
            # Pin content hash from approved record
            case_dict = case.model_dump()
            case_dict["model_content_hash"] = model_record.content_hash
            case_dict["suite_id"] = suite_id
            case_dict["project_id"] = project_id
            validated_case = GeneratedTestDefinition(**case_dict)

            test_status, test_reasons = (
                GenerationReadinessValidator.validate_test_readiness(
                    case=validated_case,
                    model=model_def,
                    fixture_data=fixture_data,
                )
            )

            # Update case with readiness findings
            case_dict["readiness"] = test_status
            case_dict["readiness_reasons"] = test_reasons
            refined_case = GeneratedTestDefinition(**case_dict)
            final_cases.append(refined_case)

            if test_status == TestReadinessStatus.TEST_READY:
                ready_count += 1
            else:
                not_ready_count += 1

            readiness_breakdown[test_status.value] = (
                readiness_breakdown.get(test_status.value, 0) + 1
            )
            cat_val = refined_case.category.value
            category_counts[cat_val] = category_counts.get(cat_val, 0) + 1

        # 5. Assemble and Persist GeneratedTestSuite
        diag_dict = diagnostics.model_dump()
        diag_dict["cases_generated_count"] = len(final_cases)
        diag_dict["readiness_breakdown"] = readiness_breakdown
        diag_dict["category_counts"] = category_counts

        suite_contract = GeneratedTestSuite(
            schema_version="2026.1",
            suite_id=suite_id,
            project_id=project_id,
            pinned_model_id=model_id,
            pinned_model_version=version,
            model_content_hash=model_record.content_hash,
            generator_version=request.generator_version,
            seed=request.seed,
            config=request.model_dump(),
            cases=final_cases,
            diagnostics=diagnostics,
            total_cases=len(final_cases),
            ready_cases_count=ready_count,
            not_ready_cases_count=not_ready_count,
            category_counts=category_counts,
        )

        persisted_suite = self.repo.save_test_suite(
            suite=suite_contract, model_record=model_record
        )
        return persisted_suite
