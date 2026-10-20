from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.components.c4_policy_aware_safety.contracts.artifacts import (
    ArtifactCreate,
    ArtifactVersionRecord,
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
from app.components.c4_policy_aware_safety.persistence.repository import C4Repository
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
