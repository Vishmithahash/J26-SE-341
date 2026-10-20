"""C4 Onboarding Orchestration Service connecting policy extraction, candidate review,
contract acceptance, test generation, freezing, and controlled execution across domains.
"""

import copy
import uuid
from datetime import UTC, datetime
from typing import Any

from app.components.c4_policy_aware_safety.contracts.artifacts import (
    ArtifactCreate,
    ArtifactKind,
)
from app.components.c4_policy_aware_safety.contracts.cases import PolicyTestCase
from app.components.c4_policy_aware_safety.contracts.enums import (
    ContractLifecycleState,
    RuleReviewStatus,
)
from app.components.c4_policy_aware_safety.contracts.execution import (
    C4ExecutionRunRecord,
    SimulatedAgentBehavior,
)
from app.components.c4_policy_aware_safety.contracts.extraction import (
    C4ExtractionJobRecord,
    CandidateRuleReviewRequest,
    ExtractionJobStatus,
)
from app.components.c4_policy_aware_safety.contracts.onboarding import (
    C4OnboardingJobRecord,
    OnboardingJobCreate,
    OnboardingJobStatus,
    OnboardingStep,
)
from app.components.c4_policy_aware_safety.contracts.rules import (
    CandidateRule,
    PolicyContractVersion,
    PolicyRule,
)
from app.components.c4_policy_aware_safety.derivation.intake import (
    compute_content_hash,
    normalize_artifact,
)
from app.components.c4_policy_aware_safety.domains.registry import (
    DomainRegistry,
    domain_registry,
)
from app.components.c4_policy_aware_safety.execution.adapters import (
    SimulatedC4ApplicationAdapter,
)
from app.components.c4_policy_aware_safety.execution.runner import C4ExecutionRunner
from app.components.c4_policy_aware_safety.extraction.extractor import (
    BoundedNLPolicyExtractor,
)
from app.components.c4_policy_aware_safety.extraction.provider import (
    get_extraction_provider,
)
from app.components.c4_policy_aware_safety.freezing.service import CaseFreezingService
from app.components.c4_policy_aware_safety.generation.generator import (
    PolicyTestGenerator,
)
from app.components.c4_policy_aware_safety.persistence.repository import C4Repository
from app.components.c4_policy_aware_safety.validation.case_validator import (
    PolicyTestCaseValidator,
)
from app.components.c4_policy_aware_safety.validation.validator import (
    PolicyContractValidator,
)


class C4OnboardingService:
    """Orchestrates end-to-end domain policy onboarding with explicit review gates."""

    def __init__(
        self,
        repository: C4Repository | None = None,
        registry: DomainRegistry | None = None,
    ) -> None:
        self.repository = repository
        self.registry = registry or domain_registry
        self.extractor = BoundedNLPolicyExtractor()
        self.contract_validator = PolicyContractValidator()
        self.generator = PolicyTestGenerator()
        self.case_validator = PolicyTestCaseValidator()
        self.freezer = CaseFreezingService()
        self.runner = C4ExecutionRunner(repository=repository)

    def start_onboarding(
        self,
        project_id: str,
        req: OnboardingJobCreate,
    ) -> C4OnboardingJobRecord:
        """Step 1 & 2: Initialize onboarding job and run bounded natural-language extraction."""
        job_id = f"onboard-{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)

        # 1. Fetch domain profile and ensure project-scoped binding
        profile = self.registry.get_profile(req.domain_id)
        binding = copy.deepcopy(profile.binding)
        binding.project_id = project_id
        if self.repository:
            existing_b = self.repository.get_domain_binding(
                project_id, binding.binding_id, binding.version
            )
            if not existing_b:
                self.repository.save_domain_binding(binding)
            else:
                binding = existing_b

        # 2. Retrieve or ingest source artifact
        artifact = None
        if self.repository:
            artifact = self.repository.get_artifact(
                project_id, req.artifact_id, req.artifact_version
            )

        if not artifact:
            # Create artifact from sample policy text
            create_req = ArtifactCreate(
                artifact_id=req.artifact_id,
                artifact_kind=ArtifactKind.POLICY_DOCUMENT,
                raw_content=profile.sample_policy_markdown,
                metadata={"source": "domain_profile_canonical_policy"},
            )
            artifact = normalize_artifact(project_id, create_req, req.artifact_version)
            if self.repository:
                self.repository.save_artifact(artifact)

        # 3. Create Extraction Job
        ext_job_id = f"ext-{uuid.uuid4().hex[:12]}"
        provider = get_extraction_provider(provider_id=req.provider_id)
        readiness = provider.check_readiness()

        candidate_rules: list[CandidateRule] = []
        ext_metadata: dict[str, Any] = {}
        all_issues: list[dict[str, Any]] = []
        gaps: list[dict[str, Any]] = []

        if not readiness.ready:
            ext_status = ExtractionJobStatus.BLOCKED
            err_msg = f"Extraction provider '{req.provider_id}' is not ready: {'; '.join(readiness.blockers)}"
        else:
            ext_status = ExtractionJobStatus.COMPLETED
            err_msg = None
            candidate_rules, ext_metadata = self.extractor.extract_candidates(
                artifact, binding
            )

            # Persist candidate rules (each in DRAFT or REJECTED status)
            for c in candidate_rules:
                if self.repository:
                    self.repository.save_candidate_rule(c)
                if c.validation_issues:
                    for iss in c.validation_issues:
                        all_issues.append(iss.model_dump())
                        if iss.code in ("UNSUPPORTED", "UNSUPPORTED_CONDITION"):
                            gaps.append(
                                {
                                    "rule_id": c.rule_id,
                                    "gap_type": "UNSUPPORTED_CONDITION",
                                    "description": iss.message,
                                }
                            )

        ext_record = C4ExtractionJobRecord(
            job_id=ext_job_id,
            project_id=project_id,
            artifact_id=artifact.artifact_id,
            artifact_version=artifact.version,
            provider_id=req.provider_id,
            model_identifier=ext_metadata.get("model_identifier", "mock-extractor"),
            status=ext_status,
            readiness_status=readiness.status,
            options={},
            job_metadata=ext_metadata,
            candidates_extracted=[c.rule_id for c in candidate_rules],
            validation_issues=all_issues,
            error_message=err_msg,
            created_at=now,
            completed_at=datetime.now(UTC),
        )
        if self.repository:
            self.repository.save_extraction_job(ext_record)

        # 4. Create Onboarding Job Record
        onboarding_record = C4OnboardingJobRecord(
            job_id=job_id,
            project_id=project_id,
            domain_id=req.domain_id,
            binding_id=req.binding_id,
            binding_version=req.binding_version,
            artifact_id=req.artifact_id,
            artifact_version=req.artifact_version,
            extraction_job_id=ext_job_id,
            status=OnboardingJobStatus.EXTRACTION_COMPLETE if ext_status == ExtractionJobStatus.COMPLETED else OnboardingJobStatus.FAILED,
            current_step=OnboardingStep.REVIEW_CANDIDATES if ext_status == ExtractionJobStatus.COMPLETED else OnboardingStep.EXTRACT_CANDIDATES,
            step_results={
                "extraction": {
                    "extracted_count": len(candidate_rules),
                    "candidate_rule_ids": [c.rule_id for c in candidate_rules],
                    "issues_count": len(all_issues),
                }
            },
            gaps=gaps,
            error_message=err_msg,
            created_at=now,
            updated_at=now,
        )
        if self.repository:
            self.repository.save_onboarding_job(onboarding_record)

        return onboarding_record

    def review_candidate(
        self,
        project_id: str,
        rule_id: str,
        review_req: CandidateRuleReviewRequest,
    ) -> CandidateRule:
        """Step 3: Explicit candidate review gate (DRAFT -> ACCEPTED / REJECTED)."""
        if not self.repository:
            raise RuntimeError("Repository required for candidate review.")

        candidate = self.repository.get_candidate_rule(project_id, rule_id)
        if not candidate:
            raise KeyError(f"Candidate rule '{rule_id}' not found in project '{project_id}'.")

        decision = review_req.decision.upper()
        if decision == "ACCEPTED":
            candidate.review_status = RuleReviewStatus.ACCEPTED
        else:
            candidate.review_status = RuleReviewStatus.REJECTED

        candidate.extraction_metadata.update(
            {
                "reviewed_by": review_req.reviewer,
                "reviewed_at": datetime.now(UTC).isoformat(),
                "review_decision": decision,
                "review_notes": review_req.review_notes,
                "is_synthetic_review": review_req.is_synthetic_review,
            }
        )

        self.repository.save_candidate_rule(candidate)
        return candidate

    def build_draft_contract(
        self,
        project_id: str,
        job_id: str,
    ) -> PolicyContractVersion:
        """Step 4: Build draft policy contract from explicitly accepted candidates."""
        if not self.repository:
            raise RuntimeError("Repository required to build contract.")

        job = self.repository.get_onboarding_job(project_id, job_id)
        if not job:
            raise KeyError(f"Onboarding job '{job_id}' not found.")

        # Gather candidates
        candidates = self.repository.list_candidate_rules(project_id)
        accepted_candidates = [
            c for c in candidates if c.review_status == RuleReviewStatus.ACCEPTED
        ]

        if not accepted_candidates:
            raise ValueError(
                "Cannot build draft contract: no candidate rules have been accepted. Review and accept candidates first."
            )

        policy_rules: list[PolicyRule] = []
        for c in accepted_candidates:
            rule = PolicyRule(
                project_id=project_id,
                rule_id=c.rule_id,
                rule_version=c.rule_version,
                policy_family=c.policy_family,
                principal_selector=c.principal_selector,
                action_selector=c.action_selector,
                resource_selector=c.resource_selector,
                applicability_conditions=c.applicability_conditions,
                policy_requirement=c.policy_requirement,
                compliance_conditions=c.compliance_conditions,
                evaluation_boundary=c.evaluation_boundary,
                required_evidence=c.required_evidence,
                severity=c.severity,
                source_references=c.source_references,
                review_status=RuleReviewStatus.ACCEPTED,
                acceptance_metadata=c.extraction_metadata,
            )
            policy_rules.append(rule)

        contract_id = f"contract-{job.domain_id}-{job.job_id[:8]}"
        contract = PolicyContractVersion(
            contract_id=contract_id,
            project_id=project_id,
            version=1,
            lifecycle_state=ContractLifecycleState.DRAFT,
            rules=policy_rules,
            referenced_artifact_versions={job.artifact_id: job.artifact_version},
            content_hash=compute_content_hash(f"{contract_id}:1:{len(policy_rules)}"),
        )

        # Validate draft contract
        resolver = (
            (lambda p, a, v: self.repository.get_artifact(p, a, v))
            if self.repository
            else None
        )
        validation_res = self.contract_validator.validate_contract(
            contract, artifact_resolver=resolver
        )
        if not validation_res.is_valid:
            blocking = [i.message for i in validation_res.issues if i.blocking]
            raise ValueError(f"Draft contract validation failed: {'; '.join(blocking)}")

        self.repository.save_contract(contract)

        # Update onboarding job
        job.draft_contract_id = contract_id
        job.contract_version = 1
        job.status = OnboardingJobStatus.DRAFT_CONTRACT_BUILT
        job.current_step = OnboardingStep.ACCEPT_CONTRACT
        job.step_results["contract_building"] = {
            "contract_id": contract_id,
            "rules_count": len(policy_rules),
        }
        job.updated_at = datetime.now(UTC)
        self.repository.save_onboarding_job(job)

        return contract

    def accept_contract(
        self,
        project_id: str,
        job_id: str,
        reviewer: str = "dev_reviewer",
        is_synthetic: bool = True,
    ) -> PolicyContractVersion:
        """Step 5: Explicitly accept draft contract (DRAFT -> ACCEPTED)."""
        if not self.repository:
            raise RuntimeError("Repository required to accept contract.")

        job = self.repository.get_onboarding_job(project_id, job_id)
        if not job or not job.draft_contract_id:
            raise KeyError(f"Onboarding job '{job_id}' has no draft contract.")

        contract = self.repository.get_contract(
            project_id, job.draft_contract_id, job.contract_version or 1
        )
        if not contract:
            raise KeyError(f"Contract '{job.draft_contract_id}' not found.")

        # Transition to ACCEPTED
        contract.lifecycle_state = ContractLifecycleState.ACCEPTED
        self.repository.save_contract(contract)

        job.status = OnboardingJobStatus.CONTRACT_ACCEPTED
        job.current_step = OnboardingStep.GENERATE_AND_FREEZE_CASES
        job.step_results["contract_acceptance"] = {
            "accepted_at": datetime.now(UTC).isoformat(),
            "accepted_by": reviewer,
            "is_synthetic_review": is_synthetic,
        }
        job.updated_at = datetime.now(UTC)
        self.repository.save_onboarding_job(job)

        return contract

    def generate_and_freeze_cases(
        self,
        project_id: str,
        job_id: str,
    ) -> list[PolicyTestCase]:
        """Step 6: Generate cases from accepted contract and freeze immutable snapshots."""
        if not self.repository:
            raise RuntimeError("Repository required to generate and freeze cases.")

        job = self.repository.get_onboarding_job(project_id, job_id)
        if not job or not job.draft_contract_id:
            raise KeyError(f"Onboarding job '{job_id}' not found.")

        contract = self.repository.get_contract(
            project_id, job.draft_contract_id, job.contract_version or 1
        )
        if not contract:
            raise KeyError(f"Accepted contract '{job.draft_contract_id}' not found.")

        profile = self.registry.get_profile(job.domain_id)
        binding = copy.deepcopy(profile.binding)
        binding.project_id = project_id
        if self.repository:
            existing_b = self.repository.get_domain_binding(
                project_id, binding.binding_id, binding.version
            )
            if existing_b:
                binding = existing_b
            else:
                self.repository.save_domain_binding(binding)

        # Generate test cases
        raw_cases, gen_report = self.generator.generate_cases(contract, binding)
        batch_id = gen_report.batch_id

        # Validate cases
        validated_cases: list[PolicyTestCase] = []
        for case in raw_cases:
            valid_case, _ = self.case_validator.validate_case(case, contract, binding)
            validated_cases.append(valid_case)

        # Freeze cases
        frozen_cases = self.freezer.freeze_batch(validated_cases, contract)

        # Save to repository
        for fc in frozen_cases:
            self.repository.save_test_case(fc)

        job.batch_id = batch_id
        job.status = OnboardingJobStatus.CASES_FROZEN
        job.current_step = OnboardingStep.EXECUTE_TESTS
        job.step_results["generation_and_freezing"] = {
            "batch_id": batch_id,
            "cases_count": len(frozen_cases),
            "case_ids": [c.case_id for c in frozen_cases],
        }
        job.updated_at = datetime.now(UTC)
        self.repository.save_onboarding_job(job)

        return frozen_cases

    def execute_onboarding_cases(
        self,
        project_id: str,
        job_id: str,
        behavior: SimulatedAgentBehavior = SimulatedAgentBehavior.COMPLIANT,
        execution_mode: str = "SIMULATED",
    ) -> list[C4ExecutionRunRecord]:
        """Step 7: Controlled execution of frozen cases against adapter."""
        if not self.repository:
            raise RuntimeError("Repository required to execute onboarding cases.")

        job = self.repository.get_onboarding_job(project_id, job_id)
        if not job:
            raise KeyError(f"Onboarding job '{job_id}' not found.")

        readiness = self.registry.check_domain_readiness(job.domain_id, execution_mode)
        if not readiness["is_ready"]:
            raise RuntimeError(
                f"Live AUT execution blocked for domain '{job.domain_id}': {'; '.join(readiness['blockers'])}"
            )

        contract = self.repository.get_contract(
            project_id, job.draft_contract_id, job.contract_version or 1
        )
        profile = self.registry.get_profile(job.domain_id)
        binding = copy.deepcopy(profile.binding)
        binding.project_id = project_id
        if self.repository:
            existing_b = self.repository.get_domain_binding(
                project_id, binding.binding_id, binding.version
            )
            if existing_b:
                binding = existing_b

        # Use simulated adapter for hermetic verification
        adapter = SimulatedC4ApplicationAdapter(behavior=behavior)

        # Load frozen cases
        frozen_cases = self.repository.list_test_cases(project_id, batch_id=job.batch_id)
        if not frozen_cases:
            # Fallback to listing all frozen cases in project
            all_cases = self.repository.list_test_cases(project_id)
            frozen_cases = [c for c in all_cases if c.contract_version == contract.version]

        run_records: list[C4ExecutionRunRecord] = []
        for case in frozen_cases:
            run = self.runner.execute_case(case, contract, binding, adapter)
            run_records.append(run)

        job.status = OnboardingJobStatus.COMPLETED
        job.current_step = OnboardingStep.EXECUTE_TESTS
        job.step_results["execution"] = {
            "executed_runs": len(run_records),
            "all_policy_verdicts": [r.policy_verdict for r in run_records],
            "all_attacker_outcomes": [r.attacker_objective_outcome.value for r in run_records],
        }
        job.updated_at = datetime.now(UTC)
        self.repository.save_onboarding_job(job)

        return run_records

    def get_onboarding_status(
        self,
        project_id: str,
        job_id: str,
    ) -> C4OnboardingJobRecord:
        """Retrieve onboarding job status and results."""
        if not self.repository:
            raise RuntimeError("Repository required.")
        job = self.repository.get_onboarding_job(project_id, job_id)
        if not job:
            raise KeyError(f"Onboarding job '{job_id}' not found in project '{project_id}'.")
        return job
