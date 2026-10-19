from sqlalchemy import desc, select
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
from app.components.c4_policy_aware_safety.contracts.evaluator import (
    RuleEvaluationFinding,
)
from app.components.c4_policy_aware_safety.contracts.execution import (
    C4ExecutionRunRecord,
)
from app.components.c4_policy_aware_safety.contracts.extraction import (
    C4ExtractionJobRecord,
)
from app.components.c4_policy_aware_safety.contracts.generation import GenerationReport
from app.components.c4_policy_aware_safety.contracts.onboarding import (
    C4OnboardingJobRecord,
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
    C4ExecutionRunModel,
    C4ExtractionJobModel,
    C4FindingModel,
    C4GenerationBatchModel,
    C4OnboardingJobModel,
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

    def list_domain_bindings(self, project_id: str) -> list[DomainBinding]:
        stmt = (
            select(C4DomainBindingModel)
            .where(C4DomainBindingModel.project_id == project_id)
            .order_by(desc(C4DomainBindingModel.version))
        )
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
        self, project_id: str, case_id: str, version: int = 1
    ) -> PolicyTestCase | None:
        stmt = select(C4TestCaseModel).where(
            C4TestCaseModel.project_id == project_id,
            C4TestCaseModel.case_id == case_id,
            C4TestCaseModel.case_version == version,
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

        self.db.commit()
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



