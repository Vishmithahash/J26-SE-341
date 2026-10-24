"""Artifact validation and transactional persistence service for Component 3 Phase 5.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 5 - Shared persistence, execution tracking, results and reporting.
"""

from sqlalchemy.orm import Session

from app.components.c3_robustness_recovery.contracts.evaluation import (
    RecoveryEvaluationRequest,
    RecoveryEvaluationResult,
    RecoveryVerdict,
)
from app.components.c3_robustness_recovery.contracts.generation import FrozenSuite
from app.components.c3_robustness_recovery.contracts.persistence import (
    CaseRecordResponse,
    EvaluationComputeRequest,
    EvaluationRecordResponse,
    MatchedPairRecordResponse,
    PaginatedResponse,
    SuiteRecordResponse,
    compute_content_digest,
)
from app.components.c3_robustness_recovery.contracts.schemas import (
    CandidateFaultCase,
    RecoveryContract,
)
from app.components.c3_robustness_recovery.repositories.persistence import (
    C3PersistenceRepository,
    EntityNotFoundError,
)
from app.components.c3_robustness_recovery.runtime.evidence import (
    MatchedPairEvidence,
    validate_evidence_linkage,
)
from app.components.c3_robustness_recovery.services.c2_facts import (
    normalize_c2_to_c3_mappings,
)
from app.components.c3_robustness_recovery.services.recovery_evaluation import (
    evaluate_recovery,
)
from app.components.c3_robustness_recovery.services.suites import (
    verify_suite_integrity,
)


def store_frozen_suite(
    db: Session, project_id: str, suite: FrozenSuite
) -> SuiteRecordResponse:
    """Validate suite integrity and idempotently persist it in a short transaction."""
    # 1. Enforce suite integrity and cryptographic digest verification
    verify_suite_integrity(suite)

    repo = C3PersistenceRepository(db)
    suite_model, _ = repo.save_frozen_suite(project_id=project_id, suite=suite)
    db.commit()

    return SuiteRecordResponse(
        suite_id=suite_model.suite_id,
        suite_digest=suite_model.suite_digest,
        project_id=suite_model.project_id,
        task_id=suite_model.task_id,
        tool_id=suite_model.tool_id,
        domain=suite_model.domain,
        schema_version=suite_model.schema_version,
        generator_version=suite_model.generator_version,
        total_cases=suite_model.total_cases,
        created_at_utc=suite_model.created_at_utc.isoformat(),
        frozen_suite=FrozenSuite.model_validate(suite_model.suite_snapshot),
    )


def get_suite(
    db: Session, project_id: str, suite_id_or_digest: str
) -> SuiteRecordResponse | None:
    """Retrieve stored frozen suite by digest or suite_id."""
    repo = C3PersistenceRepository(db)
    model = repo.get_suite_by_digest(project_id, suite_id_or_digest)
    if not model:
        model = repo.get_suite_by_id(project_id, suite_id_or_digest)
    if not model:
        return None

    return SuiteRecordResponse(
        suite_id=model.suite_id,
        suite_digest=model.suite_digest,
        project_id=model.project_id,
        task_id=model.task_id,
        tool_id=model.tool_id,
        domain=model.domain,
        schema_version=model.schema_version,
        generator_version=model.generator_version,
        total_cases=model.total_cases,
        created_at_utc=model.created_at_utc.isoformat(),
        frozen_suite=FrozenSuite.model_validate(model.suite_snapshot),
    )


def list_suites(
    db: Session,
    project_id: str,
    domain: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedResponse[SuiteRecordResponse]:
    """List stored frozen suites with bounded pagination."""
    repo = C3PersistenceRepository(db)
    models, total = repo.list_suites(
        project_id, domain=domain, limit=limit, offset=offset
    )

    items = [
        SuiteRecordResponse(
            suite_id=m.suite_id,
            suite_digest=m.suite_digest,
            project_id=m.project_id,
            task_id=m.task_id,
            tool_id=m.tool_id,
            domain=m.domain,
            schema_version=m.schema_version,
            generator_version=m.generator_version,
            total_cases=m.total_cases,
            created_at_utc=m.created_at_utc.isoformat(),
            frozen_suite=FrozenSuite.model_validate(m.suite_snapshot),
        )
        for m in models
    ]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


def get_case(
    db: Session, project_id: str, case_id: str, suite_digest: str | None = None
) -> CaseRecordResponse | None:
    """Retrieve candidate fault case snapshot by case_id within project scope."""
    repo = C3PersistenceRepository(db)
    model = repo.get_case(project_id, case_id, suite_digest=suite_digest)
    if not model:
        return None

    return CaseRecordResponse(
        case_id=model.case_id,
        suite_digest=model.suite_digest,
        case_fingerprint=model.case_fingerprint,
        content_digest=model.content_digest,
        project_id=model.project_id,
        case_family_id=model.case_family_id,
        fault_family=model.fault_family,
        effect_phase=model.effect_phase,
        interception_hook=model.interception_hook,
        target_tool_id=model.target_tool_id,
        case_order=model.case_order,
        candidate_case=CandidateFaultCase.model_validate(model.case_snapshot),
        created_at_utc=model.created_at_utc.isoformat(),
    )


def list_cases(
    db: Session,
    project_id: str,
    suite_digest: str | None = None,
    fault_family: str | None = None,
    effect_phase: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedResponse[CaseRecordResponse]:
    """List stored cases with bounded pagination and filtering."""
    repo = C3PersistenceRepository(db)
    models, total = repo.list_cases(
        project_id,
        suite_digest=suite_digest,
        fault_family=fault_family,
        effect_phase=effect_phase,
        limit=limit,
        offset=offset,
    )

    items = [
        CaseRecordResponse(
            case_id=m.case_id,
            suite_digest=m.suite_digest,
            case_fingerprint=m.case_fingerprint,
            content_digest=m.content_digest,
            project_id=m.project_id,
            case_family_id=m.case_family_id,
            fault_family=m.fault_family,
            effect_phase=m.effect_phase,
            interception_hook=m.interception_hook,
            target_tool_id=m.target_tool_id,
            case_order=m.case_order,
            candidate_case=CandidateFaultCase.model_validate(m.case_snapshot),
            created_at_utc=m.created_at_utc.isoformat(),
        )
        for m in models
    ]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


def store_matched_pair(
    db: Session,
    project_id: str,
    evidence: MatchedPairEvidence,
    execution_id: str | None = None,
) -> MatchedPairRecordResponse:
    """Validate evidence linkage and idempotently persist matched pair evidence."""
    validate_evidence_linkage(evidence)
    if evidence.project_id != project_id:
        raise ValueError(
            f"Project scope mismatch: Evidence declares project '{evidence.project_id}', "
            f"which does not match requested project '{project_id}'."
        )
    if evidence.clean_trial.project_id != project_id:
        raise ValueError(
            f"Project scope mismatch: Clean trial declares project '{evidence.clean_trial.project_id}', "
            f"which does not match requested project '{project_id}'."
        )
    if evidence.fault_trial.project_id != project_id:
        raise ValueError(
            f"Project scope mismatch: Fault trial declares project '{evidence.fault_trial.project_id}', "
            f"which does not match requested project '{project_id}'."
        )
    repo = C3PersistenceRepository(db)
    stored_case = repo.get_case(project_id, evidence.case_id)
    if stored_case and stored_case.project_id != project_id:
        raise ValueError(
            f"Case reference mismatch: Stored case '{evidence.case_id}' belongs to project "
            f"'{stored_case.project_id}', not '{project_id}'."
        )
    pair_model, _ = repo.save_matched_pair(
        project_id=project_id, evidence=evidence, execution_id=execution_id
    )
    db.commit()

    return MatchedPairRecordResponse(
        pair_id=pair_model.pair_id,
        execution_id=pair_model.execution_id,
        case_id=pair_model.case_id,
        project_id=pair_model.project_id,
        run_id=pair_model.run_id,
        clean_trial_id=pair_model.clean_trial_id,
        fault_trial_id=pair_model.fault_trial_id,
        readiness_status=pair_model.readiness_status,
        clean_qualification=pair_model.clean_qualification,
        exposure_status=pair_model.exposure_status,
        exposure_assessed=pair_model.exposure_assessed,
        cleanup_status=pair_model.cleanup_status,
        clean_execution_status=pair_model.clean_execution_status,
        fault_execution_status=pair_model.fault_execution_status,
        evidence_complete=pair_model.evidence_complete,
        evidence_digest=pair_model.evidence_digest,
        created_at_utc=pair_model.created_at_utc.isoformat(),
        evidence=MatchedPairEvidence.model_validate(pair_model.evidence_snapshot),
    )


def get_matched_pair(
    db: Session, project_id: str, pair_id: str
) -> MatchedPairRecordResponse | None:
    """Retrieve stored matched trial pair evidence by pair_id."""
    repo = C3PersistenceRepository(db)
    model = repo.get_matched_pair(project_id, pair_id)
    if not model:
        return None

    return MatchedPairRecordResponse(
        pair_id=model.pair_id,
        execution_id=model.execution_id,
        case_id=model.case_id,
        project_id=model.project_id,
        run_id=model.run_id,
        clean_trial_id=model.clean_trial_id,
        fault_trial_id=model.fault_trial_id,
        readiness_status=model.readiness_status,
        clean_qualification=model.clean_qualification,
        exposure_status=model.exposure_status,
        exposure_assessed=model.exposure_assessed,
        cleanup_status=model.cleanup_status,
        clean_execution_status=model.clean_execution_status,
        fault_execution_status=model.fault_execution_status,
        evidence_complete=model.evidence_complete,
        evidence_digest=model.evidence_digest,
        created_at_utc=model.created_at_utc.isoformat(),
        evidence=MatchedPairEvidence.model_validate(model.evidence_snapshot),
    )


def list_matched_pairs(
    db: Session,
    project_id: str,
    execution_id: str | None = None,
    case_id: str | None = None,
    run_id: str | None = None,
    exposure_status: str | None = None,
    clean_qualification: str | None = None,
    fault_execution_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedResponse[MatchedPairRecordResponse]:
    """List stored matched trial pairs with bounded pagination."""
    repo = C3PersistenceRepository(db)
    models, total = repo.list_matched_pairs(
        project_id=project_id,
        execution_id=execution_id,
        case_id=case_id,
        run_id=run_id,
        exposure_status=exposure_status,
        clean_qualification=clean_qualification,
        fault_execution_status=fault_execution_status,
        limit=limit,
        offset=offset,
    )

    items = [
        MatchedPairRecordResponse(
            pair_id=m.pair_id,
            execution_id=m.execution_id,
            case_id=m.case_id,
            project_id=m.project_id,
            run_id=m.run_id,
            clean_trial_id=m.clean_trial_id,
            fault_trial_id=m.fault_trial_id,
            readiness_status=m.readiness_status,
            clean_qualification=m.clean_qualification,
            exposure_status=m.exposure_status,
            exposure_assessed=m.exposure_assessed,
            cleanup_status=m.cleanup_status,
            clean_execution_status=m.clean_execution_status,
            fault_execution_status=m.fault_execution_status,
            evidence_complete=m.evidence_complete,
            evidence_digest=m.evidence_digest,
            created_at_utc=m.created_at_utc.isoformat(),
            evidence=MatchedPairEvidence.model_validate(m.evidence_snapshot),
        )
        for m in models
    ]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


def compute_and_store_evaluation(
    db: Session, request: EvaluationComputeRequest
) -> EvaluationRecordResponse:
    """Compute and store an authoritative recovery evaluation from persisted inputs.

    Never accepts client-supplied verdicts as authoritative.
    Loads referenced stored evidence and contract snapshots, calls the real evaluator,
    and idempotently persists the versioned result.
    """
    repo = C3PersistenceRepository(db)

    # 1. Load referenced stored matched pair evidence
    pair_model = repo.get_matched_pair(request.project_id, request.pair_id)
    if not pair_model:
        raise EntityNotFoundError(
            f"Referenced matched pair '{request.pair_id}' does not exist in project '{request.project_id}'."
        )

    evidence = MatchedPairEvidence.model_validate(pair_model.evidence_snapshot)

    # 2. Load referenced case definition
    case_model = repo.get_case(request.project_id, pair_model.case_id)
    if not case_model:
        raise EntityNotFoundError(
            f"Referenced case '{pair_model.case_id}' does not exist in project '{request.project_id}'."
        )

    candidate_case = CandidateFaultCase.model_validate(case_model.case_snapshot)

    # 3. Load enclosing suite to obtain recovery contract
    suite_model = repo.get_suite_by_digest(request.project_id, case_model.suite_digest)
    if not suite_model:
        raise EntityNotFoundError(
            f"Enclosing suite '{case_model.suite_digest}' does not exist in project '{request.project_id}'."
        )

    recovery_contract = RecoveryContract.model_validate(
        suite_model.recovery_contract_snapshot
    )

    # 4. Compute inputs digest (evidence digest + sorted C2 facts)
    c2_facts_data = [
        f.model_dump(mode="json")
        for f in sorted(request.c2_facts, key=lambda x: (x.assertion_id, x.provenance))
    ]
    inputs_payload = {
        "evidence_digest": pair_model.evidence_digest,
        "c2_facts": c2_facts_data,
        "evaluator_version": request.evaluator_version,
        "rule_set_version": request.rule_set_version,
    }
    inputs_digest = compute_content_digest(inputs_payload)

    # 5. Resolve applicable mappings safely and execute pure deterministic recovery evaluation
    raw_mappings = getattr(request, "pinned_mappings", None)
    if not raw_mappings and suite_model.suite_snapshot:
        raw_mappings = suite_model.suite_snapshot.get("pinned_mappings")
    if not raw_mappings and suite_model.recovery_contract_snapshot:
        raw_mappings = suite_model.recovery_contract_snapshot.get("pinned_mappings")
    resolved_mappings = normalize_c2_to_c3_mappings(raw_mappings)

    eval_req = RecoveryEvaluationRequest(
        project_id=request.project_id,
        case_id=candidate_case.case_id,
        evaluator_version=request.evaluator_version,
        rule_set_version=request.rule_set_version,
        candidate_case=candidate_case,
        recovery_contract=recovery_contract,
        matched_evidence=evidence,
        c2_facts=request.c2_facts,
        suite_digest=suite_model.suite_digest,
        pinned_mappings=resolved_mappings,
    )
    eval_result = evaluate_recovery(eval_req)

    # Capture provenance snapshots
    provenance_snapshots = [
        {
            "assertion_id": f.assertion_id,
            "assertion_version": f.assertion_version,
            "value": f.value.value,
            "provenance": f.provenance,
            "entity_id": f.entity_id,
            "snapshot_id": f.snapshot_id,
            "time_scope": f.time_scope,
            "supporting_evidence_refs": f.supporting_evidence_refs,
        }
        for f in request.c2_facts
    ]

    # 6. Idempotently persist evaluation record
    eval_model, _ = repo.save_evaluation(
        project_id=request.project_id,
        evaluation=eval_result,
        inputs_digest=inputs_digest,
        c2_facts_provenance=provenance_snapshots,
    )
    db.commit()

    verdict_enum = (
        RecoveryVerdict(eval_model.recovery_verdict)
        if eval_model.recovery_verdict
        else None
    )

    return EvaluationRecordResponse(
        evaluation_id=eval_model.evaluation_id,
        pair_id=eval_model.pair_id,
        case_id=eval_model.case_id,
        project_id=eval_model.project_id,
        evaluator_version=eval_model.evaluator_version,
        rule_set_version=eval_model.rule_set_version,
        evaluation_status=eval_model.evaluation_status,
        recovery_verdict=verdict_enum,
        first_violated_rule=eval_model.first_violated_rule,
        actor_attribution=eval_model.actor_attribution,
        inputs_digest=eval_model.inputs_digest,
        created_at_utc=eval_model.created_at_utc.isoformat(),
        evaluation=eval_result,
    )


def get_evaluation(
    db: Session, project_id: str, evaluation_id: str
) -> EvaluationRecordResponse | None:
    """Retrieve stored recovery evaluation result by evaluation_id."""
    repo = C3PersistenceRepository(db)
    model = repo.get_evaluation(project_id, evaluation_id)
    if not model:
        return None

    verdict_enum = (
        RecoveryVerdict(model.recovery_verdict) if model.recovery_verdict else None
    )
    eval_obj = RecoveryEvaluationResult.model_validate(model.evaluation_snapshot)

    return EvaluationRecordResponse(
        evaluation_id=model.evaluation_id,
        pair_id=model.pair_id,
        case_id=model.case_id,
        project_id=model.project_id,
        evaluator_version=model.evaluator_version,
        rule_set_version=model.rule_set_version,
        evaluation_status=model.evaluation_status,
        recovery_verdict=verdict_enum,
        first_violated_rule=model.first_violated_rule,
        actor_attribution=model.actor_attribution,
        inputs_digest=model.inputs_digest,
        created_at_utc=model.created_at_utc.isoformat(),
        evaluation=eval_obj,
    )


def list_evaluations(
    db: Session,
    project_id: str,
    pair_id: str | None = None,
    case_id: str | None = None,
    recovery_verdict: str | None = None,
    evaluator_version: str | None = None,
    rule_set_version: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> PaginatedResponse[EvaluationRecordResponse]:
    """List stored evaluations with bounded pagination and filtering."""
    repo = C3PersistenceRepository(db)
    models, total = repo.list_evaluations(
        project_id=project_id,
        pair_id=pair_id,
        case_id=case_id,
        recovery_verdict=recovery_verdict,
        evaluator_version=evaluator_version,
        rule_set_version=rule_set_version,
        limit=limit,
        offset=offset,
    )

    items = [
        EvaluationRecordResponse(
            evaluation_id=m.evaluation_id,
            pair_id=m.pair_id,
            case_id=m.case_id,
            project_id=m.project_id,
            evaluator_version=m.evaluator_version,
            rule_set_version=m.rule_set_version,
            evaluation_status=m.evaluation_status,
            recovery_verdict=RecoveryVerdict(m.recovery_verdict)
            if m.recovery_verdict
            else None,
            first_violated_rule=m.first_violated_rule,
            actor_attribution=m.actor_attribution,
            inputs_digest=m.inputs_digest,
            created_at_utc=m.created_at_utc.isoformat(),
            evaluation=RecoveryEvaluationResult.model_validate(m.evaluation_snapshot),
        )
        for m in models
    ]
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)
