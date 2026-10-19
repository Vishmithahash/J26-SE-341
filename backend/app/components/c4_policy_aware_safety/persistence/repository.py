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
from app.components.c4_policy_aware_safety.contracts.generation import GenerationReport
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
    C4FindingModel,
    C4GenerationBatchModel,
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

