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
from app.components.c4_policy_aware_safety.contracts.future import TestCaseKind
from app.components.c4_policy_aware_safety.contracts.generation import (
    GenerationReport,
    GenerationRequest,
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
from app.components.c4_policy_aware_safety.evaluator.engine import (
    DeterministicPolicyEvaluator,
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

