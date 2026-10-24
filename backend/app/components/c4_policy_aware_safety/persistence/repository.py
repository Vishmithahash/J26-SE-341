from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.components.c4_policy_aware_safety.contracts.artifacts import (
    ArtifactSection,
    ArtifactVersionRecord,
)
from app.components.c4_policy_aware_safety.contracts.bindings import DomainBinding
from app.components.c4_policy_aware_safety.contracts.cases import (
    CaseLifecycleState,
    PolicyTestCase,
)
from app.components.c4_policy_aware_safety.contracts.enums import (
    ArtifactKind,
    ContractLifecycleState,
)
from app.components.c4_policy_aware_safety.contracts.evaluation import (
    EvaluationDatasetRecord,
    ExperimentConfigRecord,
    ExperimentReportRecord,
    ReviewerDecision,
)
from app.components.c4_policy_aware_safety.contracts.evaluator import (
    RuleEvaluationFinding,
)
from app.components.c4_policy_aware_safety.contracts.execution import (
    C4ExecutionRunRecord,
    IdempotencyConflictError,
)
from app.components.c4_policy_aware_safety.contracts.extraction import (
    C4ExtractionJobRecord,
)
from app.components.c4_policy_aware_safety.contracts.generation import GenerationReport
from app.components.c4_policy_aware_safety.contracts.onboarding import (
    C4OnboardingJobRecord,
)
from app.components.c4_policy_aware_safety.contracts.regression import (
    HistoricalReEvaluationRecord,
    PolicyComparisonRecord,
    RegressionBatchRecord,
    RegressionPlanRecord,
)
from app.components.c4_policy_aware_safety.contracts.rules import (
    CandidateRule,
    PolicyContractVersion,
    PolicyRule,
)
from app.components.c4_policy_aware_safety.persistence.models import (
    C4ArtifactModel,
    C4CandidateRuleModel,
    C4ContractModel,
    C4DomainBindingModel,
    C4EvaluationDatasetModel,
    C4EvaluationReviewModel,
    C4ExecutionRunModel,
    C4ExperimentModel,
    C4ExtractionJobModel,
    C4FindingModel,
    C4GenerationBatchModel,
    C4HistoricalReEvaluationModel,
    C4OnboardingJobModel,
    C4PolicyComparisonModel,
    C4RegressionBatchModel,
    C4RegressionPlanModel,
    C4TestCaseModel,
)


class C4Repository:
    """Persistence repository for C4 entities, strictly scoped by project_id."""

    def __init__(self, db: Session):
        self.db = db

    # 1. Artifacts
    def get_next_artifact_version(self, project_id: str, artifact_id: str) -> int:
        stmt = (
            select(C4ArtifactModel.version)
            .where(
                C4ArtifactModel.project_id == project_id,
                C4ArtifactModel.artifact_id == artifact_id,
            )
            .order_by(desc(C4ArtifactModel.version))
            .limit(1)
        )
        latest = self.db.execute(stmt).scalar_one_or_none()
        return (latest or 0) + 1

    def save_artifact_version(
        self, record: ArtifactVersionRecord
    ) -> ArtifactVersionRecord:
        model = C4ArtifactModel(
            project_id=record.project_id,
            artifact_id=record.artifact_id,
            version=record.version,
            artifact_kind=record.artifact_kind.value,
            content_hash=record.content_hash,
            normalized_content=record.normalized_content,
            sections=[s.model_dump() for s in record.sections],
            meta_data=record.metadata,
            created_at=record.created_at,
        )
        self.db.add(model)
        self.db.commit()
        return record

    def get_artifact_version(
        self, project_id: str, artifact_id: str, version: int
    ) -> ArtifactVersionRecord | None:
        stmt = select(C4ArtifactModel).where(
            C4ArtifactModel.project_id == project_id,
            C4ArtifactModel.artifact_id == artifact_id,
            C4ArtifactModel.version == version,
        )
        model = self.db.execute(stmt).scalar_one_or_none()
        if not model:
            return None

        return ArtifactVersionRecord(
            project_id=model.project_id,
            artifact_id=model.artifact_id,
            artifact_kind=ArtifactKind(model.artifact_kind),
            version=model.version,
            content_hash=model.content_hash,
            normalized_content=model.normalized_content,
            sections=[ArtifactSection.model_validate(s) for s in model.sections],
            metadata=model.meta_data,
            created_at=model.created_at,
        )

    # Aliases for artifact versioning
    save_artifact = save_artifact_version
    get_artifact = get_artifact_version

    # 2. Candidate Rules
    def save_candidate_rule(self, rule: CandidateRule) -> CandidateRule:
        stmt = select(C4CandidateRuleModel).where(
            C4CandidateRuleModel.project_id == rule.project_id,
            C4CandidateRuleModel.rule_id == rule.rule_id,
            C4CandidateRuleModel.rule_version == rule.rule_version,
        )
        existing = self.db.execute(stmt).scalar_one_or_none()
        rule_data = rule.model_dump(mode="json")
        issues_data = [i.model_dump(mode="json") for i in rule.validation_issues]

        if existing:
            existing.policy_family = rule.policy_family.value
            existing.review_status = rule.review_status.value
            existing.rule_data = rule_data
            existing.validation_issues = issues_data
        else:
            new_model = C4CandidateRuleModel(
                project_id=rule.project_id,
                rule_id=rule.rule_id,
                rule_version=rule.rule_version,
                policy_family=rule.policy_family.value,
                review_status=rule.review_status.value,
                rule_data=rule_data,
                validation_issues=issues_data,
            )
            self.db.add(new_model)

        self.db.commit()
        return rule

    def get_candidate_rule(
        self, project_id: str, rule_id: str, version: int = 1
    ) -> CandidateRule | None:
        stmt = select(C4CandidateRuleModel).where(
            C4CandidateRuleModel.project_id == project_id,
            C4CandidateRuleModel.rule_id == rule_id,
            C4CandidateRuleModel.rule_version == version,
        )
        model = self.db.execute(stmt).scalar_one_or_none()
        if not model:
            return None
        return CandidateRule.model_validate(model.rule_data)

    def list_candidate_rules(
        self, project_id: str, rule_ids: list[str] | None = None
    ) -> list[CandidateRule]:
        stmt = select(C4CandidateRuleModel).where(
            C4CandidateRuleModel.project_id == project_id
        )
        if rule_ids:
            stmt = stmt.where(C4CandidateRuleModel.rule_id.in_(rule_ids))
        models = self.db.execute(stmt).scalars().all()
        return [CandidateRule.model_validate(m.rule_data) for m in models]

    # 3. Policy Contracts
    def get_next_contract_version(self, project_id: str, contract_id: str) -> int:
        stmt = (
            select(C4ContractModel.version)
            .where(
                C4ContractModel.project_id == project_id,
                C4ContractModel.contract_id == contract_id,
            )
            .order_by(desc(C4ContractModel.version))
            .limit(1)
        )
        latest = self.db.execute(stmt).scalar_one_or_none()
        return (latest or 0) + 1

    def save_contract_version(
        self, contract: PolicyContractVersion
    ) -> PolicyContractVersion:
        stmt = select(C4ContractModel).where(
            C4ContractModel.project_id == contract.project_id,
            C4ContractModel.contract_id == contract.contract_id,
            C4ContractModel.version == contract.version,
        )
        existing = self.db.execute(stmt).scalar_one_or_none()
        rules_json = [r.model_dump(mode="json") for r in contract.rules]

        if existing:
            if existing.lifecycle_state == ContractLifecycleState.ACCEPTED.value:
                raise ValueError(
                    f"Contract '{contract.contract_id}' v{contract.version} is already ACCEPTED and immutable. Create a new version."
                )
            existing.lifecycle_state = contract.lifecycle_state.value
            existing.content_hash = contract.content_hash
            existing.rules_data = rules_json
            existing.referenced_artifact_versions = (
                contract.referenced_artifact_versions
            )
            existing.acceptance_metadata = contract.acceptance_metadata
            existing.updated_at = contract.updated_at
        else:
            model = C4ContractModel(
                project_id=contract.project_id,
                contract_id=contract.contract_id,
                version=contract.version,
                lifecycle_state=contract.lifecycle_state.value,
                content_hash=contract.content_hash,
                rules_data=rules_json,
                referenced_artifact_versions=contract.referenced_artifact_versions,
                acceptance_metadata=contract.acceptance_metadata,
                created_at=contract.created_at,
                updated_at=contract.updated_at,
            )
            self.db.add(model)

        self.db.commit()
        return contract

    def get_contract_version(
        self, project_id: str, contract_id: str, version: int
    ) -> PolicyContractVersion | None:
        stmt = select(C4ContractModel).where(
            C4ContractModel.project_id == project_id,
            C4ContractModel.contract_id == contract_id,
            C4ContractModel.version == version,
        )
        model = self.db.execute(stmt).scalar_one_or_none()
        if not model:
            return None

        rules = [PolicyRule.model_validate(r) for r in model.rules_data]
        return PolicyContractVersion(
            contract_id=model.contract_id,
            project_id=model.project_id,
            version=model.version,
            lifecycle_state=ContractLifecycleState(model.lifecycle_state),
            rules=rules,
            referenced_artifact_versions=model.referenced_artifact_versions,
            acceptance_metadata=model.acceptance_metadata,
            content_hash=model.content_hash,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    # Aliases for contract retrieval
    save_contract = save_contract_version
    get_contract = get_contract_version

    # 4. Findings
    def save_finding(self, finding: RuleEvaluationFinding) -> RuleEvaluationFinding:
        model = C4FindingModel(
            finding_id=finding.finding_id,
            project_id=finding.project_id,
            case_id=finding.case_id,
            run_id=finding.run_id,
            contract_id=finding.contract_id,
            contract_version=finding.contract_version,
            rule_id=finding.rule_id,
            rule_version=finding.rule_version,
            verdict=finding.verdict.value,
            violation_stage=finding.violation_stage.value
            if finding.violation_stage
            else None,
            finding_data=finding.model_dump(mode="json"),
            created_at=finding.created_at,
        )
        self.db.add(model)
        self.db.commit()
        return finding

    def list_findings(
        self,
        project_id: str,
        case_id: str | None = None,
        run_id: str | None = None,
        contract_id: str | None = None,
    ) -> list[RuleEvaluationFinding]:
        stmt = select(C4FindingModel).where(C4FindingModel.project_id == project_id)
        if case_id:
            stmt = stmt.where(C4FindingModel.case_id == case_id)
        if run_id:
            stmt = stmt.where(C4FindingModel.run_id == run_id)
        if contract_id:
            stmt = stmt.where(C4FindingModel.contract_id == contract_id)

        models = self.db.execute(stmt).scalars().all()
        return [RuleEvaluationFinding.model_validate(m.finding_data) for m in models]

    # 5. Domain Bindings
    def get_next_binding_version(self, project_id: str, binding_id: str) -> int:
        stmt = (
            select(C4DomainBindingModel.version)
            .where(
                C4DomainBindingModel.project_id == project_id,
                C4DomainBindingModel.binding_id == binding_id,
            )
            .order_by(desc(C4DomainBindingModel.version))
            .limit(1)
        )
        latest = self.db.execute(stmt).scalar_one_or_none()
        return (latest or 0) + 1

    def save_domain_binding(self, binding: DomainBinding) -> DomainBinding:
        stmt = select(C4DomainBindingModel).where(
            C4DomainBindingModel.project_id == binding.project_id,
            C4DomainBindingModel.binding_id == binding.binding_id,
            C4DomainBindingModel.version == binding.version,
        )
        existing = self.db.execute(stmt).scalar_one_or_none()
        if existing:
            raise ValueError(
                f"Domain binding '{binding.binding_id}' v{binding.version} already exists and is immutable."
            )

        model = C4DomainBindingModel(
            project_id=binding.project_id,
            binding_id=binding.binding_id,
            version=binding.version,
            content_hash=binding.content_hash,
            binding_data=binding.model_dump(mode="json"),
            created_at=binding.created_at,
        )
        self.db.add(model)
        self.db.commit()
        return binding

    def get_domain_binding(
        self, project_id: str, binding_id: str, version: int
    ) -> DomainBinding | None:
        stmt = select(C4DomainBindingModel).where(
            C4DomainBindingModel.project_id == project_id,
            C4DomainBindingModel.binding_id == binding_id,
            C4DomainBindingModel.version == version,
        )
        model = self.db.execute(stmt).scalar_one_or_none()
        if not model:
            return None
        return DomainBinding.model_validate(model.binding_data)

    def list_domain_bindings(
        self, project_id: str, binding_id: str | None = None
    ) -> list[DomainBinding]:
        stmt = (
            select(C4DomainBindingModel)
            .where(C4DomainBindingModel.project_id == project_id)
        )
        if binding_id is not None:
            stmt = stmt.where(C4DomainBindingModel.binding_id == binding_id)
        stmt = stmt.order_by(desc(C4DomainBindingModel.version))
        models = self.db.execute(stmt).scalars().all()
        return [DomainBinding.model_validate(m.binding_data) for m in models]

    # 6. Generation Batches
    def save_generation_batch(self, report: GenerationReport) -> GenerationReport:
        model = C4GenerationBatchModel(
            batch_id=report.batch_id,
            project_id=report.project_id,
            contract_id=report.contract_id,
            contract_version=report.contract_version,
            binding_id=report.binding_id,
            binding_version=report.binding_version,
            seed=report.seed,
            config_digest=report.config_digest,
            report_data=report.model_dump(mode="json"),
            created_at=report.created_at,
        )
        self.db.add(model)
        self.db.commit()
        return report

    def get_generation_batch(
        self, project_id: str, batch_id: str
    ) -> GenerationReport | None:
        stmt = select(C4GenerationBatchModel).where(
            C4GenerationBatchModel.project_id == project_id,
            C4GenerationBatchModel.batch_id == batch_id,
        )
        model = self.db.execute(stmt).scalar_one_or_none()
        if not model:
            return None
        return GenerationReport.model_validate(model.report_data)

    # 7. Test Cases
    def get_next_case_version(self, project_id: str, case_id: str) -> int:
        stmt = (
            select(C4TestCaseModel.case_version)
            .where(
                C4TestCaseModel.project_id == project_id,
                C4TestCaseModel.case_id == case_id,
            )
            .order_by(desc(C4TestCaseModel.case_version))
            .limit(1)
        )
        latest = self.db.execute(stmt).scalar_one_or_none()
        return (latest or 0) + 1

    def save_test_case(
        self, case: PolicyTestCase, batch_id: str | None = None
    ) -> PolicyTestCase:
        stmt = select(C4TestCaseModel).where(
            C4TestCaseModel.project_id == case.project_id,
            C4TestCaseModel.case_id == case.case_id,
            C4TestCaseModel.case_version == case.case_version,
        )
        existing = self.db.execute(stmt).scalar_one_or_none()
        case_dict = case.model_dump(mode="json")

        if existing:
            if existing.lifecycle_state == CaseLifecycleState.FROZEN.value:
                raise ValueError(
                    f"Test case '{case.case_id}' v{case.case_version} is FROZEN and immutable. Create a new version."
                )
            existing.lifecycle_state = case.lifecycle_state.value
            existing.content_hash = case.content_hash
            existing.case_data = case_dict
            if case.frozen_at:
                existing.frozen_at = case.frozen_at
        else:
            model = C4TestCaseModel(
                case_id=case.case_id,
                case_version=case.case_version,
                project_id=case.project_id,
                batch_id=batch_id,
                rule_id=case.target_rule_id,
                test_kind=case.test_kind.value,
                lifecycle_state=case.lifecycle_state.value,
                content_hash=case.content_hash,
                case_data=case_dict,
                created_at=case.created_at,
                frozen_at=case.frozen_at,
            )
            self.db.add(model)

        self.db.commit()
        return case

    def get_test_case(
        self, project_id: str, case_id: str, version: int | None = None
    ) -> PolicyTestCase | None:
        """Exact version lookup for a test case.
        
        If version is specified, returns that exact version or None (never falls back to latest).
        If version is None, explicitly delegates to get_latest_test_case.
        """
        if version is not None:
            stmt = select(C4TestCaseModel).where(
                C4TestCaseModel.project_id == project_id,
                C4TestCaseModel.case_id == case_id,
                C4TestCaseModel.case_version == version,
            )
            model = self.db.execute(stmt).scalar_one_or_none()
            if not model:
                return None
            return PolicyTestCase.model_validate(model.case_data)
        return self.get_latest_test_case(project_id, case_id)

    def get_latest_test_case(
        self, project_id: str, case_id: str
    ) -> PolicyTestCase | None:
        """Retrieve the latest version of a test case by case_id."""
        stmt = (
            select(C4TestCaseModel)
            .where(
                C4TestCaseModel.project_id == project_id,
                C4TestCaseModel.case_id == case_id,
            )
            .order_by(desc(C4TestCaseModel.case_version))
            .limit(1)
        )
        model = self.db.execute(stmt).scalar_one_or_none()
        if not model:
            return None
        return PolicyTestCase.model_validate(model.case_data)

    def list_test_cases(
        self,
        project_id: str,
        batch_id: str | None = None,
        rule_id: str | None = None,
        category: str | None = None,
        lifecycle_state: str | None = None,
    ) -> list[PolicyTestCase]:
        stmt = select(C4TestCaseModel).where(C4TestCaseModel.project_id == project_id)
        if batch_id:
            stmt = stmt.where(C4TestCaseModel.batch_id == batch_id)
        if rule_id:
            stmt = stmt.where(C4TestCaseModel.rule_id == rule_id)
        if category:
            stmt = stmt.where(C4TestCaseModel.test_kind == category)
        if lifecycle_state:
            stmt = stmt.where(C4TestCaseModel.lifecycle_state == lifecycle_state)

        models = self.db.execute(stmt).scalars().all()
        return [PolicyTestCase.model_validate(m.case_data) for m in models]

    # 8. Execution Runs
    def save_execution_run(self, run: C4ExecutionRunRecord) -> C4ExecutionRunRecord:
        stmt = select(C4ExecutionRunModel).where(
            C4ExecutionRunModel.project_id == run.project_id,
            C4ExecutionRunModel.run_id == run.run_id,
        )
        existing = self.db.execute(stmt).scalar_one_or_none()
        run_dict = run.model_dump(mode="json")

        if existing:
            existing.status = run.status.value
            existing.exposure_status = run.exposure_status.value
            existing.policy_verdict = run.policy_verdict
            existing.attacker_objective_outcome = run.attacker_objective_outcome.value
            existing.task_utility_outcome = run.task_utility_outcome.value
            existing.cleanup_status = run.cleanup_status.value
            existing.run_data = run_dict
            existing.error_message = run.error_message
            existing.completed_at = run.completed_at
        else:
            model = C4ExecutionRunModel(
                run_id=run.run_id,
                project_id=run.project_id,
                case_id=run.case_id,
                case_version=run.case_version,
                contract_id=run.contract_id,
                contract_version=run.contract_version,
                binding_id=run.binding_id,
                binding_version=run.binding_version,
                adapter_id=run.adapter_id,
                adapter_version=run.adapter_version,
                adapter_config_digest=run.adapter_config_digest,
                execution_mode=run.execution_mode.value,
                simulated_behavior=run.simulated_behavior,
                status=run.status.value,
                exposure_status=run.exposure_status.value,
                policy_verdict=run.policy_verdict,
                attacker_objective_outcome=run.attacker_objective_outcome.value,
                task_utility_outcome=run.task_utility_outcome.value,
                cleanup_status=run.cleanup_status.value,
                idempotency_key=run.idempotency_key,
                request_digest=run.request_digest,
                injection_target_verdict=run.injection_target_verdict,
                attempt_goal_outcome=run.attempt_goal_outcome.value
                if run.attempt_goal_outcome
                else None,
                commit_goal_outcome=run.commit_goal_outcome.value
                if run.commit_goal_outcome
                else None,
                backend_rejection_observed=run.backend_rejection_observed,
                run_data=run_dict,
                error_message=run.error_message,
                created_at=run.created_at,
                completed_at=run.completed_at,
            )
            self.db.add(model)

        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            if run.idempotency_key:
                existing_run = self.get_execution_run_by_idempotency(
                    run.project_id, run.idempotency_key
                )
                if existing_run:
                    if (
                        existing_run.request_digest
                        and run.request_digest
                        and existing_run.request_digest != run.request_digest
                    ):
                        raise IdempotencyConflictError(
                            f"Idempotency key '{run.idempotency_key}' previously used with different request parameters."
                        )
                    return existing_run
            raise
        return run

    def get_execution_run(
        self, project_id: str, run_id: str
    ) -> C4ExecutionRunRecord | None:
        stmt = select(C4ExecutionRunModel).where(
            C4ExecutionRunModel.project_id == project_id,
            C4ExecutionRunModel.run_id == run_id,
        )
        model = self.db.execute(stmt).scalar_one_or_none()
        if not model:
            return None
        return C4ExecutionRunRecord.model_validate(model.run_data)

    def get_execution_run_by_idempotency(
        self, project_id: str, idempotency_key: str
    ) -> C4ExecutionRunRecord | None:
        stmt = select(C4ExecutionRunModel).where(
            C4ExecutionRunModel.project_id == project_id,
            C4ExecutionRunModel.idempotency_key == idempotency_key,
        )
        model = self.db.execute(stmt).scalar_one_or_none()
        if not model:
            return None
        return C4ExecutionRunRecord.model_validate(model.run_data)

    def list_execution_runs(
        self,
        project_id: str,
        case_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[C4ExecutionRunRecord]:
        stmt = (
            select(C4ExecutionRunModel)
            .where(C4ExecutionRunModel.project_id == project_id)
            .order_by(desc(C4ExecutionRunModel.created_at))
            .offset(offset)
            .limit(limit)
        )
        if case_id:
            stmt = stmt.where(C4ExecutionRunModel.case_id == case_id)

        models = self.db.execute(stmt).scalars().all()
        return [C4ExecutionRunRecord.model_validate(m.run_data) for m in models]

    def get_execution_runs_by_case(
        self, project_id: str, case_id: str
    ) -> list[C4ExecutionRunRecord]:
        return self.list_execution_runs(project_id, case_id=case_id)

    # 8. Extraction Jobs
    def save_extraction_job(
        self, job: C4ExtractionJobRecord
    ) -> C4ExtractionJobRecord:
        stmt = select(C4ExtractionJobModel).where(
            C4ExtractionJobModel.project_id == job.project_id,
            C4ExtractionJobModel.job_id == job.job_id,
        )
        existing = self.db.execute(stmt).scalar_one_or_none()

        if existing:
            existing.status = job.status.value
            existing.readiness_status = job.readiness_status.value
            existing.options = job.options
            existing.job_metadata = job.job_metadata
            existing.candidates_extracted = job.candidates_extracted
            existing.validation_issues = job.validation_issues
            existing.error_message = job.error_message
            existing.completed_at = job.completed_at
        else:
            model = C4ExtractionJobModel(
                job_id=job.job_id,
                project_id=job.project_id,
                artifact_id=job.artifact_id,
                artifact_version=job.artifact_version,
                provider_id=job.provider_id,
                model_identifier=job.model_identifier,
                status=job.status.value,
                readiness_status=job.readiness_status.value,
                prompt_template_version=job.prompt_template_version,
                schema_version=job.schema_version,
                options=job.options,
                job_metadata=job.job_metadata,
                candidates_extracted=job.candidates_extracted,
                validation_issues=job.validation_issues,
                error_message=job.error_message,
                created_at=job.created_at,
                completed_at=job.completed_at,
            )
            self.db.add(model)

        self.db.commit()
        return job

    def get_extraction_job(
        self, project_id: str, job_id: str
    ) -> C4ExtractionJobRecord | None:
        stmt = select(C4ExtractionJobModel).where(
            C4ExtractionJobModel.project_id == project_id,
            C4ExtractionJobModel.job_id == job_id,
        )
        model = self.db.execute(stmt).scalar_one_or_none()
        if not model:
            return None
        return C4ExtractionJobRecord(
            job_id=model.job_id,
            project_id=model.project_id,
            artifact_id=model.artifact_id,
            artifact_version=model.artifact_version,
            provider_id=model.provider_id,
            model_identifier=model.model_identifier,
            status=model.status,
            readiness_status=model.readiness_status,
            prompt_template_version=model.prompt_template_version,
            schema_version=model.schema_version,
            options=model.options,
            job_metadata=model.job_metadata,
            candidates_extracted=model.candidates_extracted,
            validation_issues=model.validation_issues,
            error_message=model.error_message,
            created_at=model.created_at,
            completed_at=model.completed_at,
        )

    def list_extraction_jobs(
        self, project_id: str, limit: int = 50
    ) -> list[C4ExtractionJobRecord]:
        stmt = (
            select(C4ExtractionJobModel)
            .where(C4ExtractionJobModel.project_id == project_id)
            .order_by(desc(C4ExtractionJobModel.created_at))
            .limit(limit)
        )
        models = self.db.execute(stmt).scalars().all()
        return [
            C4ExtractionJobRecord(
                job_id=m.job_id,
                project_id=m.project_id,
                artifact_id=m.artifact_id,
                artifact_version=m.artifact_version,
                provider_id=m.provider_id,
                model_identifier=m.model_identifier,
                status=m.status,
                readiness_status=m.readiness_status,
                prompt_template_version=m.prompt_template_version,
                schema_version=m.schema_version,
                options=m.options,
                job_metadata=m.job_metadata,
                candidates_extracted=m.candidates_extracted,
                validation_issues=m.validation_issues,
                error_message=m.error_message,
                created_at=m.created_at,
                completed_at=m.completed_at,
            )
            for m in models
        ]

    # 9. Onboarding Jobs
    def save_onboarding_job(
        self, job: C4OnboardingJobRecord
    ) -> C4OnboardingJobRecord:
        stmt = select(C4OnboardingJobModel).where(
            C4OnboardingJobModel.project_id == job.project_id,
            C4OnboardingJobModel.job_id == job.job_id,
        )
        existing = self.db.execute(stmt).scalar_one_or_none()

        if existing:
            existing.status = job.status.value
            existing.current_step = job.current_step.value
            existing.extraction_job_id = job.extraction_job_id
            existing.draft_contract_id = job.draft_contract_id
            existing.contract_version = job.contract_version
            existing.batch_id = job.batch_id
            existing.step_results = job.step_results
            existing.gaps = job.gaps
            existing.error_message = job.error_message
            existing.updated_at = job.updated_at
        else:
            model = C4OnboardingJobModel(
                job_id=job.job_id,
                project_id=job.project_id,
                domain_id=job.domain_id,
                binding_id=job.binding_id,
                binding_version=job.binding_version,
                artifact_id=job.artifact_id,
                artifact_version=job.artifact_version,
                extraction_job_id=job.extraction_job_id,
                draft_contract_id=job.draft_contract_id,
                contract_version=job.contract_version,
                batch_id=job.batch_id,
                status=job.status.value,
                current_step=job.current_step.value,
                step_results=job.step_results,
                gaps=job.gaps,
                error_message=job.error_message,
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
            self.db.add(model)

        self.db.commit()
        return job

    def get_onboarding_job(
        self, project_id: str, job_id: str
    ) -> C4OnboardingJobRecord | None:
        stmt = select(C4OnboardingJobModel).where(
            C4OnboardingJobModel.project_id == project_id,
            C4OnboardingJobModel.job_id == job_id,
        )
        model = self.db.execute(stmt).scalar_one_or_none()
        if not model:
            return None
        return C4OnboardingJobRecord(
            job_id=model.job_id,
            project_id=model.project_id,
            domain_id=model.domain_id,
            binding_id=model.binding_id,
            binding_version=model.binding_version,
            artifact_id=model.artifact_id,
            artifact_version=model.artifact_version,
            extraction_job_id=model.extraction_job_id,
            draft_contract_id=model.draft_contract_id,
            contract_version=model.contract_version,
            batch_id=model.batch_id,
            status=model.status,
            current_step=model.current_step,
            step_results=model.step_results,
            gaps=model.gaps,
            error_message=model.error_message,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def list_onboarding_jobs(
        self, project_id: str, limit: int = 50
    ) -> list[C4OnboardingJobRecord]:
        stmt = (
            select(C4OnboardingJobModel)
            .where(C4OnboardingJobModel.project_id == project_id)
            .order_by(desc(C4OnboardingJobModel.created_at))
            .limit(limit)
        )
        models = self.db.execute(stmt).scalars().all()
        return [
            C4OnboardingJobRecord(
                job_id=m.job_id,
                project_id=m.project_id,
                domain_id=m.domain_id,
                binding_id=m.binding_id,
                binding_version=m.binding_version,
                artifact_id=m.artifact_id,
                artifact_version=m.artifact_version,
                extraction_job_id=m.extraction_job_id,
                draft_contract_id=m.draft_contract_id,
                contract_version=m.contract_version,
                batch_id=m.batch_id,
                status=m.status,
                current_step=m.current_step,
                step_results=m.step_results,
                gaps=m.gaps,
                error_message=m.error_message,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in models
        ]

    # 11. Policy Comparisons
    def save_policy_comparison(
        self, comparison: PolicyComparisonRecord
    ) -> PolicyComparisonRecord:
        stmt = select(C4PolicyComparisonModel).where(
            C4PolicyComparisonModel.project_id == comparison.project_id,
            C4PolicyComparisonModel.comparison_id == comparison.comparison_id,
        )
        existing = self.db.execute(stmt).scalar_one_or_none()
        comp_dict = comparison.model_dump(mode="json")

        if existing:
            existing.comparison_data = comp_dict
        else:
            model = C4PolicyComparisonModel(
                comparison_id=comparison.comparison_id,
                project_id=comparison.project_id,
                baseline_contract_id=comparison.baseline_contract_id,
                baseline_contract_version=comparison.baseline_contract_version,
                candidate_contract_id=comparison.candidate_contract_id,
                candidate_contract_version=comparison.candidate_contract_version,
                algorithm_version=comparison.algorithm_version,
                configuration_digest=comparison.configuration_digest,
                comparison_data=comp_dict,
                created_at=comparison.created_at,
            )
            self.db.add(model)

        self.db.commit()
        return comparison

    def get_policy_comparison(
        self, project_id: str, comparison_id: str
    ) -> PolicyComparisonRecord | None:
        stmt = select(C4PolicyComparisonModel).where(
            C4PolicyComparisonModel.project_id == project_id,
            C4PolicyComparisonModel.comparison_id == comparison_id,
        )
        model = self.db.execute(stmt).scalar_one_or_none()
        if not model:
            return None
        return PolicyComparisonRecord.model_validate(model.comparison_data)

    # 12. Regression Plans
    def save_regression_plan(
        self, plan: RegressionPlanRecord
    ) -> RegressionPlanRecord:
        stmt = select(C4RegressionPlanModel).where(
            C4RegressionPlanModel.project_id == plan.project_id,
            C4RegressionPlanModel.plan_id == plan.plan_id,
        )
        existing = self.db.execute(stmt).scalar_one_or_none()
        plan_dict = plan.model_dump(mode="json")

        if existing:
            existing.status = plan.status.value
            existing.plan_data = plan_dict
            existing.frozen_at = plan.frozen_at
        else:
            model = C4RegressionPlanModel(
                plan_id=plan.plan_id,
                project_id=plan.project_id,
                comparison_id=plan.comparison_id,
                baseline_contract_id=plan.baseline_contract_id,
                baseline_contract_version=plan.baseline_contract_version,
                candidate_contract_id=plan.candidate_contract_id,
                candidate_contract_version=plan.candidate_contract_version,
                binding_id=plan.binding_id,
                binding_version=plan.binding_version,
                status=plan.status.value,
                plan_digest=plan.plan_digest,
                plan_data=plan_dict,
                created_at=plan.created_at,
                frozen_at=plan.frozen_at,
            )
            self.db.add(model)

        self.db.commit()
        return plan

    def get_regression_plan(
        self, project_id: str, plan_id: str
    ) -> RegressionPlanRecord | None:
        stmt = select(C4RegressionPlanModel).where(
            C4RegressionPlanModel.project_id == project_id,
            C4RegressionPlanModel.plan_id == plan_id,
        )
        model = self.db.execute(stmt).scalar_one_or_none()
        if not model:
            return None
        return RegressionPlanRecord.model_validate(model.plan_data)

    # 13. Regression Batches
    def save_regression_batch(
        self, batch: RegressionBatchRecord
    ) -> RegressionBatchRecord:
        stmt = select(C4RegressionBatchModel).where(
            C4RegressionBatchModel.project_id == batch.project_id,
            C4RegressionBatchModel.batch_id == batch.batch_id,
        )
        existing = self.db.execute(stmt).scalar_one_or_none()
        batch_dict = batch.model_dump(mode="json")

        if existing:
            existing.status = batch.status
            existing.batch_data = batch_dict
            existing.completed_at = batch.completed_at
        else:
            model = C4RegressionBatchModel(
                batch_id=batch.batch_id,
                project_id=batch.project_id,
                plan_id=batch.plan_id,
                candidate_contract_id=batch.candidate_contract_id,
                candidate_contract_version=batch.candidate_contract_version,
                adapter_id=batch.adapter_id,
                execution_mode=batch.execution_mode.value,
                status=batch.status,
                idempotency_key=batch.idempotency_key,
                request_digest=batch.request_digest,
                batch_data=batch_dict,
                created_at=batch.created_at,
                completed_at=batch.completed_at,
            )
            self.db.add(model)

        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            if batch.idempotency_key:
                existing_batch = self.get_regression_batch_by_idempotency(
                    batch.project_id, batch.idempotency_key
                )
                if existing_batch:
                    if (
                        existing_batch.request_digest
                        and batch.request_digest
                        and existing_batch.request_digest != batch.request_digest
                    ):
                        raise IdempotencyConflictError(
                            f"Idempotency key '{batch.idempotency_key}' previously used with different batch parameters."
                        )
                    return existing_batch
            raise
        return batch

    def get_regression_batch_by_idempotency(
        self, project_id: str, idempotency_key: str
    ) -> RegressionBatchRecord | None:
        stmt = select(C4RegressionBatchModel).where(
            C4RegressionBatchModel.project_id == project_id,
            C4RegressionBatchModel.idempotency_key == idempotency_key,
        )
        model = self.db.execute(stmt).scalar_one_or_none()
        if not model:
            return None
        return RegressionBatchRecord.model_validate(model.batch_data)

    def get_latest_regression_batch(
        self, project_id: str, plan_id: str
    ) -> RegressionBatchRecord | None:
        stmt = (
            select(C4RegressionBatchModel)
            .where(
                C4RegressionBatchModel.project_id == project_id,
                C4RegressionBatchModel.plan_id == plan_id,
            )
            .order_by(desc(C4RegressionBatchModel.created_at))
            .limit(1)
        )
        model = self.db.execute(stmt).scalar_one_or_none()
        if not model:
            return None
        return RegressionBatchRecord.model_validate(model.batch_data)

    # 14. Historical Re-Evaluations
    def save_historical_re_evaluation(
        self, record: HistoricalReEvaluationRecord
    ) -> HistoricalReEvaluationRecord:
        model = C4HistoricalReEvaluationModel(
            re_eval_id=record.re_eval_id,
            project_id=record.project_id,
            source_run_id=record.source_run_id,
            original_contract_id=record.original_contract_id,
            original_contract_version=record.original_contract_version,
            candidate_contract_id=record.candidate_contract_id,
            candidate_contract_version=record.candidate_contract_version,
            derived_policy_verdict=record.derived_policy_verdict,
            re_eval_data=record.model_dump(mode="json"),
            created_at=record.created_at,
        )
        self.db.add(model)
        self.db.commit()
        return record

    def get_historical_re_evaluation(
        self, project_id: str, re_eval_id: str
    ) -> HistoricalReEvaluationRecord | None:
        stmt = select(C4HistoricalReEvaluationModel).where(
            C4HistoricalReEvaluationModel.project_id == project_id,
            C4HistoricalReEvaluationModel.re_eval_id == re_eval_id,
        )
        model = self.db.execute(stmt).scalar_one_or_none()
        if not model:
            return None
        return HistoricalReEvaluationRecord.model_validate(model.re_eval_data)

    def list_historical_re_evaluations(
        self, project_id: str, source_run_id: str | None = None
    ) -> list[HistoricalReEvaluationRecord]:
        stmt = (
            select(C4HistoricalReEvaluationModel)
            .where(C4HistoricalReEvaluationModel.project_id == project_id)
            .order_by(desc(C4HistoricalReEvaluationModel.created_at))
        )
        if source_run_id:
            stmt = stmt.where(C4HistoricalReEvaluationModel.source_run_id == source_run_id)
        models = self.db.execute(stmt).scalars().all()
        return [HistoricalReEvaluationRecord.model_validate(m.re_eval_data) for m in models]

    # 15. Evaluation Datasets
    def save_evaluation_dataset(
        self, dataset: EvaluationDatasetRecord
    ) -> EvaluationDatasetRecord:
        stmt = select(C4EvaluationDatasetModel).where(
            C4EvaluationDatasetModel.project_id == dataset.project_id,
            C4EvaluationDatasetModel.dataset_id == dataset.dataset_id,
            C4EvaluationDatasetModel.version == dataset.version,
        )
        existing = self.db.execute(stmt).scalar_one_or_none()
        dataset_dict = dataset.model_dump(mode="json")

        if existing:
            if existing.is_frozen:
                raise ValueError(
                    f"Evaluation dataset '{dataset.dataset_id}' v{dataset.version} is FROZEN and immutable."
                )
            existing.dataset_hash = dataset.dataset_hash
            existing.is_frozen = dataset.is_frozen
            existing.dataset_data = dataset_dict
            existing.frozen_at = dataset.frozen_at
        else:
            model = C4EvaluationDatasetModel(
                dataset_id=dataset.dataset_id,
                version=dataset.version,
                project_id=dataset.project_id,
                domain_id=dataset.domain_id,
                dataset_hash=dataset.dataset_hash,
                is_frozen=dataset.is_frozen,
                dataset_data=dataset_dict,
                created_at=dataset.created_at,
                frozen_at=dataset.frozen_at,
            )
            self.db.add(model)

        self.db.commit()
        return dataset

    def get_evaluation_dataset(
        self, project_id: str, dataset_id: str, version: int = 1
    ) -> EvaluationDatasetRecord | None:
        stmt = select(C4EvaluationDatasetModel).where(
            C4EvaluationDatasetModel.project_id == project_id,
            C4EvaluationDatasetModel.dataset_id == dataset_id,
            C4EvaluationDatasetModel.version == version,
        )
        model = self.db.execute(stmt).scalar_one_or_none()
        if not model:
            return None
        return EvaluationDatasetRecord.model_validate(model.dataset_data)

    def list_evaluation_datasets(self, project_id: str) -> list[EvaluationDatasetRecord]:
        stmt = (
            select(C4EvaluationDatasetModel)
            .where(C4EvaluationDatasetModel.project_id == project_id)
            .order_by(desc(C4EvaluationDatasetModel.created_at))
        )
        models = self.db.execute(stmt).scalars().all()
        return [EvaluationDatasetRecord.model_validate(m.dataset_data) for m in models]

    # 16. Evaluation Reviews
    def save_evaluation_review(
        self, review: ReviewerDecision, project_id: str
    ) -> ReviewerDecision:
        model = C4EvaluationReviewModel(
            review_id=review.review_id,
            project_id=project_id,
            case_id=review.case_id,
            reviewer_id=review.reviewer_id,
            verdict_decision=review.verdict_decision,
            review_data=review.model_dump(mode="json"),
            created_at=review.timestamp,
        )
        self.db.add(model)
        self.db.commit()
        return review

    def list_evaluation_reviews(
        self, project_id: str, case_id: str | None = None
    ) -> list[ReviewerDecision]:
        stmt = (
            select(C4EvaluationReviewModel)
            .where(C4EvaluationReviewModel.project_id == project_id)
            .order_by(desc(C4EvaluationReviewModel.created_at))
        )
        if case_id:
            stmt = stmt.where(C4EvaluationReviewModel.case_id == case_id)
        models = self.db.execute(stmt).scalars().all()
        return [ReviewerDecision.model_validate(m.review_data) for m in models]

    # 17. Experiments
    def save_experiment(
        self, config: ExperimentConfigRecord
    ) -> ExperimentConfigRecord:
        stmt = select(C4ExperimentModel).where(
            C4ExperimentModel.project_id == config.project_id,
            C4ExperimentModel.experiment_id == config.experiment_id,
        )
        existing = self.db.execute(stmt).scalar_one_or_none()
        config_dict = config.model_dump(mode="json")

        if existing:
            existing.experiment_data = config_dict
        else:
            model = C4ExperimentModel(
                experiment_id=config.experiment_id,
                project_id=config.project_id,
                domain_id=config.domain_id,
                dataset_id=config.dataset_id,
                strategy_type=config.strategy_type.value,
                status="CREATED",
                experiment_data=config_dict,
                created_at=config.created_at,
            )
            self.db.add(model)

        self.db.commit()
        return config

    def get_experiment_config(
        self, project_id: str, experiment_id: str
    ) -> ExperimentConfigRecord | None:
        stmt = select(C4ExperimentModel).where(
            C4ExperimentModel.project_id == project_id,
            C4ExperimentModel.experiment_id == experiment_id,
        )
        model = self.db.execute(stmt).scalar_one_or_none()
        if not model:
            return None
        return ExperimentConfigRecord.model_validate(model.experiment_data)

    def save_experiment_report(
        self, report: ExperimentReportRecord
    ) -> ExperimentReportRecord:
        stmt = select(C4ExperimentModel).where(
            C4ExperimentModel.project_id == report.project_id,
            C4ExperimentModel.experiment_id == report.experiment_id,
        )
        existing = self.db.execute(stmt).scalar_one_or_none()
        report_dict = report.model_dump(mode="json")

        if existing:
            existing.status = report.status.value
            existing.experiment_data = report_dict
            existing.completed_at = report.completed_at
        else:
            model = C4ExperimentModel(
                experiment_id=report.experiment_id,
                project_id=report.project_id,
                domain_id=report.config.domain_id,
                dataset_id=report.config.dataset_id,
                strategy_type=report.config.strategy_type.value,
                status=report.status.value,
                experiment_data=report_dict,
                created_at=report.config.created_at,
                completed_at=report.completed_at,
            )
            self.db.add(model)

        self.db.commit()
        return report

    def get_experiment_report(
        self, project_id: str, experiment_id: str
    ) -> ExperimentReportRecord | None:
        stmt = select(C4ExperimentModel).where(
            C4ExperimentModel.project_id == project_id,
            C4ExperimentModel.experiment_id == experiment_id,
        )
        model = self.db.execute(stmt).scalar_one_or_none()
        if not model:
            return None
        return ExperimentReportRecord.model_validate(model.experiment_data)



