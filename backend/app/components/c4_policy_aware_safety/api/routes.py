from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.components.c4_policy_aware_safety.contracts.artifacts import (
    ArtifactCreate,
    ArtifactVersionRecord,
)
from app.components.c4_policy_aware_safety.contracts.bindings import (
    DomainBinding,
    compute_binding_hash,
)
from app.components.c4_policy_aware_safety.contracts.cases import (
    AgentVisiblePayload,
    CaseLifecycleState,
    EvaluatorPayload,
    HarnessPayload,
    PolicyTestCase,
)
from app.components.c4_policy_aware_safety.contracts.enums import (
    ContractLifecycleState,
    RuleReviewStatus,
)
from app.components.c4_policy_aware_safety.contracts.evaluator import (
    EvaluationReport,
    RuleEvaluationFinding,
)
from app.components.c4_policy_aware_safety.contracts.evidence import (
    EvaluationEvidencePackage,
)
from app.components.c4_policy_aware_safety.contracts.execution import (
    C4ExecutionRequest,
    C4ExecutionRunRecord,
    C4RuntimeReadinessReport,
    IdempotencyConflictError,
    TargetExecutionMode,
)
from app.components.c4_policy_aware_safety.contracts.extraction import (
    C4ExtractionJobRecord,
    CandidateRuleReviewRequest,
    ExtractionJobCreate,
    ExtractionReadinessReport,
)
from app.components.c4_policy_aware_safety.contracts.future import TestCaseKind
from app.components.c4_policy_aware_safety.contracts.generation import (
    GenerationReport,
    GenerationRequest,
)
from app.components.c4_policy_aware_safety.contracts.onboarding import (
    C4OnboardingJobRecord,
    DomainProfileDefinition,
    OnboardingJobCreate,
)
from app.components.c4_policy_aware_safety.contracts.regression import (
    ExecutionModeType,
    PolicyComparisonRecord,
    PolicyComparisonRequest,
    RegressionBatchRecord,
    RegressionPlanRecord,
    RegressionReport,
)
from app.components.c4_policy_aware_safety.contracts.rules import (
    CandidateRule,
    ContractAcceptanceRequest,
    ContractCreate,
    ContractValidationResult,
    PolicyContractVersion,
    PolicyRule,
)
from app.components.c4_policy_aware_safety.derivation.controlled_language import (
    ControlledLanguageExtractor,
)
from app.components.c4_policy_aware_safety.derivation.importer import (
    StructuredRuleImporter,
)
from app.components.c4_policy_aware_safety.derivation.intake import normalize_artifact
from app.components.c4_policy_aware_safety.domains.registry import domain_registry
from app.components.c4_policy_aware_safety.evaluator.engine import (
    DeterministicPolicyEvaluator,
)
from app.components.c4_policy_aware_safety.execution.adapters import (
    LiveAUTAdapterStub,
    SimulatedC4ApplicationAdapter,
)
from app.components.c4_policy_aware_safety.execution.runner import C4ExecutionRunner
from app.components.c4_policy_aware_safety.extraction.provider import (
    get_extraction_provider,
)
from app.components.c4_policy_aware_safety.freezing.service import CaseFreezingService
from app.components.c4_policy_aware_safety.generation.generator import (
    PolicyTestGenerator,
)
from app.components.c4_policy_aware_safety.onboarding.service import (
    C4OnboardingService,
)
from app.components.c4_policy_aware_safety.persistence.repository import C4Repository
from app.components.c4_policy_aware_safety.regression.service import C4RegressionService
from app.components.c4_policy_aware_safety.validation.case_validator import (
    PolicyTestCaseValidator,
)
from app.components.c4_policy_aware_safety.validation.validator import (
    PolicyContractValidator,
)
from app.database import get_db

router = APIRouter(prefix="/projects/{project_id}/c4", tags=["C4 Policy-Aware Safety"])


class RuleDerivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str = Field(..., description="Source artifact ID")
    artifact_version: int = Field(..., ge=1, description="Source artifact version")
    mode: str = Field(
        default="controlled_language",
        description="'controlled_language' or 'structured_import'",
    )
    structured_payload: list[dict[str, Any]] | None = Field(
        default=None,
        description="Structured rules payload if mode is 'structured_import'",
    )


# 1. Artifacts Intake
@router.post(
    "/artifacts",
    response_model=ArtifactVersionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new version of a policy artifact",
)
def register_artifact(
    project_id: str,
    create_req: ArtifactCreate,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    next_ver = repo.get_next_artifact_version(project_id, create_req.artifact_id)
    record = normalize_artifact(project_id, create_req, next_ver)
    return repo.save_artifact_version(record)


@router.get(
    "/artifacts/{artifact_id}/versions/{version}",
    response_model=ArtifactVersionRecord,
    summary="Get an artifact version by ID and version",
)
def get_artifact(
    project_id: str,
    artifact_id: str,
    version: int,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    artifact = repo.get_artifact_version(project_id, artifact_id, version)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{artifact_id}' v{version} not found in project '{project_id}'.",
        )
    return artifact


# 2. Rule Derivation / Import
@router.post(
    "/rules/derive",
    response_model=list[CandidateRule],
    status_code=status.HTTP_200_OK,
    summary="Derive or import candidate rules from an artifact version",
)
def derive_rules(
    project_id: str,
    request: RuleDerivationRequest,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    artifact = repo.get_artifact_version(
        project_id, request.artifact_id, request.artifact_version
    )
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{request.artifact_id}' v{request.artifact_version} not found.",
        )

    if request.mode == "controlled_language":
        extractor = ControlledLanguageExtractor()
        candidates = extractor.extract_from_artifact(artifact)
    elif request.mode == "structured_import":
        if not request.structured_payload:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="structured_payload is required when mode is 'structured_import'.",
            )
        importer = StructuredRuleImporter()
        candidates = importer.import_candidate_rules(
            project_id,
            request.structured_payload,
            artifact_resolver=repo.get_artifact_version,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported derivation mode '{request.mode}'. Supported: 'controlled_language', 'structured_import'.",
        )

    # Save candidates to persistence
    for cand in candidates:
        repo.save_candidate_rule(cand)

    return candidates


# 3. Policy Contracts
@router.post(
    "/contracts",
    response_model=PolicyContractVersion,
    status_code=status.HTTP_201_CREATED,
    summary="Create a draft policy contract from candidate rules",
)
def create_contract(
    project_id: str,
    create_req: ContractCreate,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    candidate_rules = repo.list_candidate_rules(project_id, create_req.rule_ids)
    if len(candidate_rules) != len(create_req.rule_ids):
        found_ids = {r.rule_id for r in candidate_rules}
        missing_ids = set(create_req.rule_ids) - found_ids
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate rules not found: {missing_ids}",
        )

    next_ver = repo.get_next_contract_version(project_id, create_req.contract_id)
    validator = PolicyContractValidator()
    # Contract is initially created as DRAFT or VALIDATED
    val_res = validator.validate_contract_draft(
        project_id,
        create_req.contract_id,
        next_ver,
        candidate_rules,
        repo.get_artifact_version,
    )

    # Convert candidate rules to policy rules for contract draft
    referenced_artifact_versions: dict[str, int] = {}
    draft_rules = []
    for cand in candidate_rules:
        for src in cand.source_references:
            referenced_artifact_versions[src.artifact_id] = src.artifact_version
        draft_rules.append(cand.model_dump(mode="json"))

    import hashlib
    import json

    canon_json = json.dumps(draft_rules, sort_keys=True)
    content_hash = hashlib.sha256(canon_json.encode("utf-8")).hexdigest()

    contract = PolicyContractVersion(
        contract_id=create_req.contract_id,
        project_id=project_id,
        version=next_ver,
        lifecycle_state=ContractLifecycleState.VALIDATED
        if val_res.is_valid
        else ContractLifecycleState.DRAFT,
        rules=[
            PolicyRule(
                project_id=cand.project_id,
                rule_id=cand.rule_id,
                rule_version=cand.rule_version,
                policy_family=cand.policy_family,
                principal_selector=cand.principal_selector,
                action_selector=cand.action_selector,
                resource_selector=cand.resource_selector,
                applicability_conditions=cand.applicability_conditions,
                policy_requirement=cand.policy_requirement,
                compliance_conditions=cand.compliance_conditions,
                evaluation_boundary=cand.evaluation_boundary,
                required_evidence=cand.required_evidence,
                severity=cand.severity,
                source_references=cand.source_references,
                review_status=RuleReviewStatus.VALIDATED
                if val_res.is_valid
                else RuleReviewStatus.DRAFT,
                acceptance_metadata={},
            )
            for cand in candidate_rules
        ],
        referenced_artifact_versions=referenced_artifact_versions,
        content_hash=content_hash,
    )
    return repo.save_contract_version(contract)


@router.get(
    "/contracts/{contract_id}/versions/{version}",
    response_model=PolicyContractVersion,
    summary="Get policy contract by ID and version",
)
def get_contract(
    project_id: str,
    contract_id: str,
    version: int,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    contract = repo.get_contract_version(project_id, contract_id, version)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract '{contract_id}' v{version} not found in project '{project_id}'.",
        )
    return contract


@router.post(
    "/contracts/{contract_id}/versions/{version}/validate",
    response_model=ContractValidationResult,
    summary="Validate a policy contract draft",
)
def validate_contract(
    project_id: str,
    contract_id: str,
    version: int,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    contract = repo.get_contract_version(project_id, contract_id, version)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found."
        )

    candidate_rules = repo.list_candidate_rules(
        project_id, [r.rule_id for r in contract.rules]
    )
    validator = PolicyContractValidator()
    return validator.validate_contract_draft(
        project_id, contract_id, version, candidate_rules, repo.get_artifact_version
    )


@router.post(
    "/contracts/{contract_id}/versions/{version}/accept",
    response_model=PolicyContractVersion,
    summary="Explicitly accept a validated policy contract",
)
def accept_contract(
    project_id: str,
    contract_id: str,
    version: int,
    accept_req: ContractAcceptanceRequest,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    contract = repo.get_contract_version(project_id, contract_id, version)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found."
        )

    candidate_rules = repo.list_candidate_rules(
        project_id, [r.rule_id for r in contract.rules]
    )
    validator = PolicyContractValidator()

    try:
        accepted_contract = validator.build_accepted_contract(
            project_id=project_id,
            contract_id=contract_id,
            version=version,
            candidate_rules=candidate_rules,
            artifact_resolver=repo.get_artifact_version,
            accepted_by=accept_req.accepted_by,
            rationale=accept_req.rationale,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contract cannot be accepted due to blocking validation issues: {e!s}",
        )

    return repo.save_contract_version(accepted_contract)


# 4. Evaluation
@router.post(
    "/evaluate",
    response_model=EvaluationReport,
    status_code=status.HTTP_200_OK,
    summary="Evaluate an accepted policy contract against supplied evidence",
)
def evaluate_evidence(
    project_id: str,
    evidence: EvaluationEvidencePackage,
    contract_id: Annotated[str, Query(description="Contract ID to evaluate against")],
    db: Annotated[Session, Depends(get_db)],
):
    if evidence.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Evidence project_id '{evidence.project_id}' does not match route project '{project_id}'.",
        )

    repo = C4Repository(db)
    contract = repo.get_contract_version(
        project_id, contract_id, evidence.contract_version
    )
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract '{contract_id}' v{evidence.contract_version} not found in project '{project_id}'.",
        )

    # Candidate rules and unaccepted contracts cannot be evaluated
    if contract.lifecycle_state != ContractLifecycleState.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contract '{contract_id}' v{evidence.contract_version} is in state '{contract.lifecycle_state.value}'. Only ACCEPTED contracts can be evaluated.",
        )

    evaluator = DeterministicPolicyEvaluator()
    report = evaluator.evaluate_contract(contract, evidence)

    # Persist findings
    for finding in report.findings:
        repo.save_finding(finding)

    return report


# 5. Findings Retrieval
@router.get(
    "/findings",
    response_model=list[RuleEvaluationFinding],
    summary="Retrieve stored evaluation findings",
)
def get_findings(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    case_id: str | None = Query(default=None),
    run_id: str | None = Query(default=None),
    contract_id: str | None = Query(default=None),
):
    repo = C4Repository(db)
    return repo.list_findings(
        project_id, case_id=case_id, run_id=run_id, contract_id=contract_id
    )


# 6. Domain Bindings
@router.post(
    "/bindings",
    response_model=DomainBinding,
    status_code=status.HTTP_201_CREATED,
    summary="Register a versioned domain binding",
)
def register_domain_binding(
    project_id: str,
    binding: DomainBinding,
    db: Annotated[Session, Depends(get_db)],
):
    if binding.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Binding project_id '{binding.project_id}' does not match route project '{project_id}'.",
        )
    repo = C4Repository(db)
    next_ver = repo.get_next_binding_version(project_id, binding.binding_id)
    binding.version = next_ver
    binding.content_hash = compute_binding_hash(binding)
    return repo.save_domain_binding(binding)


@router.get(
    "/bindings/{binding_id}/versions/{version}",
    response_model=DomainBinding,
    summary="Retrieve a domain binding by ID and version",
)
def get_domain_binding(
    project_id: str,
    binding_id: str,
    version: int,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    binding = repo.get_domain_binding(project_id, binding_id, version)
    if not binding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain binding '{binding_id}' v{version} not found in project '{project_id}'.",
        )
    return binding


@router.get(
    "/bindings",
    response_model=list[DomainBinding],
    summary="List domain bindings for a project",
)
def list_domain_bindings(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    binding_id: Annotated[str | None, Query()] = None,
):
    repo = C4Repository(db)
    return repo.list_domain_bindings(project_id, binding_id=binding_id)


# 7. Test Case Generation
@router.post(
    "/generate",
    response_model=GenerationReport,
    status_code=status.HTTP_200_OK,
    summary="Automatically generate policy-specific test cases",
)
def generate_test_cases(
    project_id: str,
    request: GenerationRequest,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    contract = repo.get_contract_version(
        project_id, request.contract_id, request.contract_version
    )
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy contract '{request.contract_id}' v{request.contract_version} not found in project '{project_id}'.",
        )
    if contract.lifecycle_state != ContractLifecycleState.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contract '{request.contract_id}' v{request.contract_version} is in state '{contract.lifecycle_state.value}'. Only ACCEPTED contracts can be used for test generation.",
        )

    binding = repo.get_domain_binding(
        project_id, request.binding_id, request.binding_version
    )
    if not binding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain binding '{request.binding_id}' v{request.binding_version} not found in project '{project_id}'.",
        )

    generator = PolicyTestGenerator(config=request.config)
    cases, report = generator.generate_cases(contract, binding)

    if request.auto_validate:
        validator = PolicyTestCaseValidator()
        cases = validator.validate_batch(cases, contract, binding)
        report.validated_count = sum(
            1 for c in cases if c.lifecycle_state == CaseLifecycleState.VALIDATED
        )
        report.rejected_count = sum(
            1 for c in cases if c.lifecycle_state == CaseLifecycleState.REJECTED
        )
        report.review_needed_count = sum(
            1 for c in cases if c.lifecycle_state == CaseLifecycleState.NEEDS_REVIEW
        )

    if request.auto_freeze:
        freezer = CaseFreezingService()
        cases = freezer.freeze_batch(cases, contract)
        report.frozen_count = sum(
            1 for c in cases if c.lifecycle_state == CaseLifecycleState.FROZEN
        )

    repo.save_generation_batch(report)

    for case in cases:
        repo.save_test_case(case, batch_id=report.batch_id)

    return report


@router.get(
    "/batches/{batch_id}",
    response_model=GenerationReport,
    summary="Retrieve a generation batch report",
)
def get_generation_batch(
    project_id: str,
    batch_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    report = repo.get_generation_batch(project_id, batch_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation batch '{batch_id}' not found in project '{project_id}'.",
        )
    return report


# 8. Test Cases Management
@router.get(
    "/cases",
    response_model=list[PolicyTestCase],
    summary="List generated policy test cases",
)
def list_test_cases(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    batch_id: Annotated[str | None, Query()] = None,
    rule_id: Annotated[str | None, Query()] = None,
    category: Annotated[TestCaseKind | None, Query()] = None,
    lifecycle_state: Annotated[CaseLifecycleState | None, Query()] = None,
):
    repo = C4Repository(db)
    return repo.list_test_cases(
        project_id=project_id,
        batch_id=batch_id,
        rule_id=rule_id,
        category=category.value if category else None,
        lifecycle_state=lifecycle_state.value if lifecycle_state else None,
    )


@router.get(
    "/cases/{case_id}/versions/{version}",
    response_model=PolicyTestCase,
    summary="Retrieve a policy test case by ID and version",
)
def get_test_case(
    project_id: str,
    case_id: str,
    version: int,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    case = repo.get_test_case(project_id, case_id, version)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test case '{case_id}' v{version} not found in project '{project_id}'.",
        )
    return case


@router.post(
    "/cases/{case_id}/versions/{version}/validate",
    response_model=PolicyTestCase,
    summary="Independently validate a generated test case",
)
def validate_test_case(
    project_id: str,
    case_id: str,
    version: int,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    case = repo.get_test_case(project_id, case_id, version)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test case '{case_id}' v{version} not found in project '{project_id}'.",
        )
    contract = repo.get_contract_version(
        project_id, case.contract_id, case.contract_version
    )
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Associated contract '{case.contract_id}' v{case.contract_version} not found.",
        )
    binding = repo.get_domain_binding(
        project_id, case.domain_id, case.binding_version
    )
    if not binding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Associated domain binding '{case.domain_id}' v{case.binding_version} not found.",
        )

    validator = PolicyTestCaseValidator()
    validated_case, _ = validator.validate_case(case, contract, binding)
    return repo.save_test_case(validated_case)


@router.post(
    "/cases/{case_id}/versions/{version}/freeze",
    response_model=PolicyTestCase,
    summary="Freeze a validated test case to ensure snapshot immutability",
)
def freeze_test_case(
    project_id: str,
    case_id: str,
    version: int,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    case = repo.get_test_case(project_id, case_id, version)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test case '{case_id}' v{version} not found in project '{project_id}'.",
        )
    contract = repo.get_contract_version(
        project_id, case.contract_id, case.contract_version
    )
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Associated contract '{case.contract_id}' v{case.contract_version} not found.",
        )
    binding = repo.get_domain_binding(
        project_id, case.domain_id, case.binding_version
    )
    if not binding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Associated domain binding '{case.domain_id}' v{case.binding_version} not found.",
        )

    freezer = CaseFreezingService()
    try:
        frozen_case = freezer.freeze_case(case, contract)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot freeze case: {e!s}",
        )
    return repo.save_test_case(frozen_case)


# 9. Payload Exports
@router.get(
    "/cases/{case_id}/versions/{version}/export/agent",
    response_model=AgentVisiblePayload,
    summary="Export strictly agent-visible payload (no hidden goals or assertions)",
)
def export_agent_payload(
    project_id: str,
    case_id: str,
    version: int,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    case = repo.get_test_case(project_id, case_id, version)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test case '{case_id}' v{version} not found in project '{project_id}'.",
        )
    return case.build_agent_visible_payload()


@router.get(
    "/cases/{case_id}/versions/{version}/export/harness",
    response_model=HarnessPayload,
    summary="Export test harness orchestration payload",
)
def export_harness_payload(
    project_id: str,
    case_id: str,
    version: int,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    case = repo.get_test_case(project_id, case_id, version)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test case '{case_id}' v{version} not found in project '{project_id}'.",
        )
    return case.build_harness_payload()


@router.get(
    "/cases/{case_id}/versions/{version}/export/evaluator",
    response_model=EvaluatorPayload,
    summary="Export evaluator assertions and hidden validation ground truth",
)
def export_evaluator_payload(
    project_id: str,
    case_id: str,
    version: int,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    case = repo.get_test_case(project_id, case_id, version)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test case '{case_id}' v{version} not found in project '{project_id}'.",
        )
    return case.build_evaluator_payload()


# 9. Phase 3: Controlled Execution, Readiness, and Reporting
@router.post(
    "/runs/readiness",
    response_model=C4RuntimeReadinessReport,
    summary="Check runtime readiness of a case, domain binding, and execution adapter",
)
def check_execution_readiness(
    project_id: str,
    exec_req: C4ExecutionRequest,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    case = repo.get_test_case(project_id, exec_req.case_id, exec_req.case_version)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test case '{exec_req.case_id}' v{exec_req.case_version} not found in project '{project_id}'.",
        )
    binding = repo.get_domain_binding(project_id, exec_req.binding_id, exec_req.binding_version)
    if not binding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain binding '{exec_req.binding_id}' v{exec_req.binding_version} not found in project '{project_id}'.",
        )

    if exec_req.execution_mode == TargetExecutionMode.LIVE_AUT:
        adapter = LiveAUTAdapterStub()
    else:
        adapter = SimulatedC4ApplicationAdapter(behavior=exec_req.simulated_behavior)

    runner = C4ExecutionRunner(repo)
    return runner.check_readiness(case, binding, adapter)


@router.post(
    "/runs/execute",
    response_model=C4ExecutionRunRecord,
    status_code=status.HTTP_200_OK,
    summary="Execute a frozen test case through registered adapter",
)
def execute_test_case(
    project_id: str,
    exec_req: C4ExecutionRequest,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    case = repo.get_test_case(project_id, exec_req.case_id, exec_req.case_version)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test case '{exec_req.case_id}' v{exec_req.case_version} not found in project '{project_id}'.",
        )
    contract = repo.get_contract_version(project_id, exec_req.contract_id, exec_req.contract_version)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy contract '{exec_req.contract_id}' v{exec_req.contract_version} not found in project '{project_id}'.",
        )
    binding = repo.get_domain_binding(project_id, exec_req.binding_id, exec_req.binding_version)
    if not binding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain binding '{exec_req.binding_id}' v{exec_req.binding_version} not found in project '{project_id}'.",
        )

    if exec_req.execution_mode == TargetExecutionMode.LIVE_AUT:
        adapter = LiveAUTAdapterStub()
    else:
        adapter = SimulatedC4ApplicationAdapter(behavior=exec_req.simulated_behavior)

    runner = C4ExecutionRunner(repo)
    try:
        return runner.execute_case(
            case=case,
            contract=contract,
            binding=binding,
            adapter=adapter,
            idempotency_key=exec_req.idempotency_key,
        )
    except IdempotencyConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get(
    "/runs/{run_id}",
    response_model=C4ExecutionRunRecord,
    summary="Retrieve a C4 execution run record",
)
def get_execution_run(
    project_id: str,
    run_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    run_rec = repo.get_execution_run(project_id, run_id)
    if not run_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution run '{run_id}' not found in project '{project_id}'.",
        )
    return run_rec


@router.get(
    "/runs",
    response_model=list[C4ExecutionRunRecord],
    summary="List execution runs for a project",
)
def list_execution_runs(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    case_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    repo = C4Repository(db)
    return repo.list_execution_runs(project_id, case_id=case_id, limit=limit, offset=offset)


@router.get(
    "/runs/{run_id}/report",
    summary="Export explainable findings and report for a run",
)
def export_run_report(
    project_id: str,
    run_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    run_rec = repo.get_execution_run(project_id, run_id)
    if not run_rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution run '{run_id}' not found in project '{project_id}'.",
        )
    return {
        "run_id": run_rec.run_id,
        "project_id": run_rec.project_id,
        "case_id": run_rec.case_id,
        "case_version": run_rec.case_version,
        "execution_status": run_rec.status.value,
        "exposure_status": run_rec.exposure_status.value,
        "policy_verdict": run_rec.policy_verdict,
        "attacker_objective_outcome": run_rec.attacker_objective_outcome.value,
        "task_utility_outcome": run_rec.task_utility_outcome.value,
        "cleanup_status": run_rec.cleanup_status.value,
        "pre_cleanup_effects": run_rec.pre_cleanup_effects,
        "summary": run_rec.evaluation_report_summary,
        "findings": run_rec.findings,
        "error_message": run_rec.error_message,
        "created_at": run_rec.created_at.isoformat(),
        "completed_at": run_rec.completed_at.isoformat() if run_rec.completed_at else None,
    }


# ==============================================================================
# Phase 4: Natural-Language Policy Extraction & Review Endpoints
# ==============================================================================


@router.get(
    "/extraction/readiness",
    response_model=ExtractionReadinessReport,
    summary="Check extraction provider configuration and operational readiness",
)
def check_extraction_readiness(
    project_id: str,
    provider_id: str = Query(default="offline_mock"),
):
    provider = get_extraction_provider(provider_id=provider_id)
    return provider.check_readiness()


@router.post(
    "/extraction/jobs",
    response_model=C4ExtractionJobRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a natural-language policy extraction job",
)
def start_extraction_job(
    project_id: str,
    req: ExtractionJobCreate,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    artifact = repo.get_artifact(project_id, req.artifact_id, req.artifact_version)
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source artifact '{req.artifact_id}' v{req.artifact_version} not found in project '{project_id}'.",
        )

    # Use default ecommerce binding for generic extraction validation
    profile = domain_registry.get_profile("domain-ecommerce-c4")
    service = C4OnboardingService(repository=repo)
    onboard_req = OnboardingJobCreate(
        domain_id=profile.domain_id,
        artifact_id=req.artifact_id,
        artifact_version=req.artifact_version,
        binding_id=profile.binding.binding_id,
        binding_version=profile.binding.version,
        provider_id=req.provider_id,
    )
    job = service.start_onboarding(project_id, onboard_req)
    if not job.extraction_job_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize extraction job.",
        )
    ext_job = repo.get_extraction_job(project_id, job.extraction_job_id)
    if not ext_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction job '{job.extraction_job_id}' not found.",
        )
    return ext_job


@router.get(
    "/extraction/jobs/{job_id}",
    response_model=C4ExtractionJobRecord,
    summary="Retrieve extraction job status and results",
)
def get_extraction_job(
    project_id: str,
    job_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    job = repo.get_extraction_job(project_id, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction job '{job_id}' not found in project '{project_id}'.",
        )
    return job


@router.post(
    "/candidates/{rule_id}/review",
    response_model=CandidateRule,
    summary="Explicit human or dev review gate for an extracted candidate rule",
)
def review_candidate_rule(
    project_id: str,
    rule_id: str,
    req: CandidateRuleReviewRequest,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    service = C4OnboardingService(repository=repo)
    try:
        return service.review_candidate(project_id, rule_id, req)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==============================================================================
# Phase 4: Domain Profiles & Onboarding Pipeline Endpoints
# ==============================================================================


@router.get(
    "/domains",
    response_model=list[DomainProfileDefinition],
    summary="List available domain profiles (E-Commerce, Booking)",
)
def list_domains(project_id: str):
    return domain_registry.list_profiles()


@router.get(
    "/domains/{domain_id}/readiness",
    summary="Check runtime and integration readiness for a domain",
)
def check_domain_readiness_endpoint(
    project_id: str,
    domain_id: str,
    mode: str = Query(default="SIMULATED", description="'SIMULATED' or 'LIVE'"),
):
    try:
        return domain_registry.check_domain_readiness(domain_id, mode)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/onboarding/jobs",
    response_model=C4OnboardingJobRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Start domain onboarding workflow across policy artifacts and domain bindings",
)
def start_onboarding(
    project_id: str,
    req: OnboardingJobCreate,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    service = C4OnboardingService(repository=repo)
    try:
        return service.start_onboarding(project_id, req)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/onboarding/jobs/{job_id}",
    response_model=C4OnboardingJobRecord,
    summary="Get status and details of an onboarding job",
)
def get_onboarding_job(
    project_id: str,
    job_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    service = C4OnboardingService(repository=repo)
    try:
        return service.get_onboarding_status(project_id, job_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/onboarding/jobs/{job_id}/build-draft-contract",
    response_model=PolicyContractVersion,
    summary="Assemble draft policy contract from explicitly accepted candidates",
)
def build_onboarding_draft_contract(
    project_id: str,
    job_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    service = C4OnboardingService(repository=repo)
    try:
        return service.build_draft_contract(project_id, job_id)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/onboarding/jobs/{job_id}/accept-contract",
    response_model=PolicyContractVersion,
    summary="Explicitly accept draft contract (DRAFT -> ACCEPTED review gate)",
)
def accept_onboarding_contract(
    project_id: str,
    job_id: str,
    db: Annotated[Session, Depends(get_db)],
    reviewer: str = Query(default="dev_reviewer"),
):
    repo = C4Repository(db)
    service = C4OnboardingService(repository=repo)
    try:
        return service.accept_contract(project_id, job_id, reviewer=reviewer)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/onboarding/jobs/{job_id}/generate-cases",
    response_model=list[PolicyTestCase],
    summary="Generate and freeze policy test cases for accepted contract",
)
def generate_onboarding_cases(
    project_id: str,
    job_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    service = C4OnboardingService(repository=repo)
    try:
        return service.generate_and_freeze_cases(project_id, job_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/onboarding/jobs/{job_id}/execute",
    response_model=list[C4ExecutionRunRecord],
    summary="Execute frozen onboarding cases against controlled target adapter",
)
def execute_onboarding_cases(
    project_id: str,
    job_id: str,
    db: Annotated[Session, Depends(get_db)],
    execution_mode: str = Query(default="SIMULATED", description="'SIMULATED' or 'LIVE'"),
):
    repo = C4Repository(db)
    service = C4OnboardingService(repository=repo)
    try:
        return service.execute_onboarding_cases(
            project_id, job_id, execution_mode=execution_mode
        )
    except RuntimeError as e:
        if "blocked" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# 11. Policy Regression and Diffing Routes
class RegressionPlanCreateRequest(BaseModel):
    comparison_id: str
    binding_id: str
    binding_version: int


class RegressionPlanExecuteRequest(BaseModel):
    execution_mode: str = "FRESH_EXECUTION"
    idempotency_key: str | None = None


@router.post(
    "/regression/compare",
    response_model=PolicyComparisonRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Compare two accepted policy contracts and produce deterministic diff",
)
def compare_policy_contracts(
    project_id: str,
    request: PolicyComparisonRequest,
    db: Annotated[Session, Depends(get_db)],
):
    if request.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project ID mismatch: route '{project_id}' != payload '{request.project_id}'.",
        )
    repo = C4Repository(db)
    service = C4RegressionService(repository=repo)
    try:
        return service.compare_contracts(request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/regression/comparisons/{comparison_id}",
    response_model=PolicyComparisonRecord,
    summary="Retrieve an existing policy comparison",
)
def get_policy_comparison(
    project_id: str,
    comparison_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    comparison = repo.get_policy_comparison(project_id, comparison_id)
    if not comparison:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison '{comparison_id}' not found in project '{project_id}'.",
        )
    return comparison


@router.post(
    "/regression/plans",
    response_model=RegressionPlanRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Build a typed regression plan with impact decisions",
)
def create_regression_plan(
    project_id: str,
    request: RegressionPlanCreateRequest,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    service = C4RegressionService(repository=repo)
    try:
        return service.create_regression_plan(
            project_id=project_id,
            comparison_id=request.comparison_id,
            binding_id=request.binding_id,
            binding_version=request.binding_version,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/regression/plans/{plan_id}",
    response_model=RegressionPlanRecord,
    summary="Retrieve an existing regression plan",
)
def get_regression_plan(
    project_id: str,
    plan_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    plan = repo.get_regression_plan(project_id, plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Regression plan '{plan_id}' not found in project '{project_id}'.",
        )
    return plan


@router.post(
    "/regression/plans/{plan_id}/regenerate",
    response_model=RegressionPlanRecord,
    summary="Selectively regenerate and revalidate affected cases for regression plan",
)
def regenerate_regression_plan(
    project_id: str,
    plan_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    service = C4RegressionService(repository=repo)
    try:
        updated_plan, _ = service.regenerate_plan(project_id, plan_id)
        return updated_plan
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/regression/plans/{plan_id}/freeze",
    response_model=RegressionPlanRecord,
    summary="Freeze a validated regression plan into immutable snapshot",
)
def freeze_regression_plan(
    project_id: str,
    plan_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    service = C4RegressionService(repository=repo)
    try:
        return service.freeze_plan(project_id, plan_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/regression/plans/{plan_id}/execute",
    response_model=RegressionBatchRecord,
    summary="Selectively execute frozen regression plan against target adapter",
)
def execute_regression_plan(
    project_id: str,
    plan_id: str,
    db: Annotated[Session, Depends(get_db)],
    payload: RegressionPlanExecuteRequest | None = None,
):
    repo = C4Repository(db)
    service = C4RegressionService(repository=repo)
    req = payload or RegressionPlanExecuteRequest()
    try:
        mode = ExecutionModeType(req.execution_mode)
    except ValueError:
        mode = ExecutionModeType.FRESH_EXECUTION

    try:
        batch, _ = service.execute_plan(
            project_id=project_id,
            plan_id=plan_id,
            execution_mode=mode,
            idempotency_key=req.idempotency_key,
        )
        return batch
    except IdempotencyConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/regression/plans/{plan_id}/report",
    response_model=RegressionReport,
    summary="Retrieve evidence-linked regression report for plan",
)
def get_regression_report(
    project_id: str,
    plan_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    service = C4RegressionService(repository=repo)
    report = service.get_regression_report(project_id, plan_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Regression report for plan '{plan_id}' not found.",
        )
    return report


@router.post(
    "/regression/plans/{plan_id}/re-evaluate-historical",
    response_model=RegressionBatchRecord,
    summary="Re-evaluate historical run evidence under candidate policy without fresh agent execution",
)
def re_evaluate_historical(
    project_id: str,
    plan_id: str,
    db: Annotated[Session, Depends(get_db)],
):
    repo = C4Repository(db)
    service = C4RegressionService(repository=repo)
    try:
        batch, _ = service.execute_plan(
            project_id=project_id,
            plan_id=plan_id,
            execution_mode=ExecutionModeType.HISTORICAL_RE_EVALUATION,
        )
        return batch
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))




