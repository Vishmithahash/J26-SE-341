"""Focused regression suite for C3 Pre-Live Execution Readiness & Controlled Testing.

Component: C3 - Robustness and Failure Recovery Testing
Focus: Prerequisites, input grounding, exposure classification, mapping normalization,
       evidence retention, native controlled runner, and honesty safeguards.
"""

import json
import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c3_robustness_recovery.contracts.evaluation import (
    C2AssertionFact,
    C2FactValue,
    RecoveryEvaluationRequest,
    RecoveryRuleId,
    RecoveryVerdict,
    RuleEvaluationStatus,
)
from app.components.c3_robustness_recovery.contracts.generation import (
    FrozenSuite,
    ModelAssistedDraftRequest,
)
from app.components.c3_robustness_recovery.contracts.persistence import (
    ControlledExecutionRequest,
    EvaluationComputeRequest,
)
from app.components.c3_robustness_recovery.contracts.schemas import (
    CandidateFaultCase,
    EffectPhase,
    FaultFamily,
    InterceptionHook,
    RecoveryContract,
    ReleaseRule,
    ReleaseRuleType,
    TaskFixtureMetadata,
    TimeoutDisconnectionMode,
    TimeoutDisconnectionPayload,
)
from app.components.c3_robustness_recovery.runtime.adapter import (
    FUTURE_NEXACART_REQUIRED_CAPABILITIES,
    CallerIdentity,
    CleanupResult,
    CleanupStatus,
    DemonstrationFixtureManager,
    DemonstrationToolAdapter,
    RecoveryActor,
    TargetMode,
    check_real_target_prerequisites,
)
from app.components.c3_robustness_recovery.runtime.evidence import (
    CleanQualification,
    ExecutionStatus,
    ExposureStatus,
    FaultEpisodeRecord,
    FixtureComparability,
    MatchedPairEvidence,
    ReadinessStatus,
    RuntimeEvent,
    StateObservationReference,
    TimeoutBoundaryType,
    TrialEvidence,
    TrialRole,
    export_evidence_to_file,
    validate_evidence_linkage,
)
from app.components.c3_robustness_recovery.runtime.interceptor import (
    InterceptionPlan,
)
from app.components.c3_robustness_recovery.runtime.runner import (
    HarnessRunner,
    make_demonstration_candidate_case,
    make_demonstration_recovery_contract,
    make_demonstration_task_fixture_metadata,
)
from app.components.c3_robustness_recovery.runtime.suite_runner import (
    SuiteRunner,
    build_demonstration_generation_request,
)
from app.components.c3_robustness_recovery.services.c2_facts import (
    C2ToC3AssertionMapping,
    DEFAULT_C2_TO_C3_MAPPINGS,
    normalize_c2_to_c3_mapping,
    normalize_c2_to_c3_mappings,
)
from app.components.c3_robustness_recovery.services.generation import (
    generate_feasible_cases,
)
from app.components.c3_robustness_recovery.services.model_assisted_prep import (
    prepare_draft_inputs,
)
from app.components.c3_robustness_recovery.services.recovery_evaluation import (
    evaluate_recovery,
)
from app.components.c3_robustness_recovery.services.storage import (
    compute_and_store_evaluation,
    get_matched_pair,
    get_suite,
    store_frozen_suite,
    store_matched_pair,
)
from app.components.c3_robustness_recovery.services.suites import (
    verify_suite_integrity,
)
from app.database import Base, get_db
from app.main import app
from app.shared.auth.dependencies import require_active_user
from app.shared.auth.models import User, UserRole
from app.shared.llm.contracts import LLMGenerationResult
from app.shared.llm.service import LLMProviderService
from app.shared.projects.models import (
    Project,
    ProjectConnectionState,
    ProjectLifecycle,
)


# ---------------------------------------------------------------------------
# Test Fixtures (In-Memory Database & TestClient)
# ---------------------------------------------------------------------------


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_client(test_db):
    user = User(
        id=1001,
        name="C3 QA Tester",
        email="c3tester@example.com",
        canonical_email="c3tester@example.com",
        password_hash="testhash",
        role=UserRole.USER,
        is_active=True,
    )
    test_db.add(user)

    project = Project(
        project_id="proj-prelive-c3",
        owner_user_id=1001,
        name="Pre-Live C3 Verification",
        domain="ecommerce",
        environment="TEST",
        backend_base_url="http://127.0.0.1:8000",
        backend_health_url="http://127.0.0.1:8000/health",
        configuration_version=1,
        lifecycle=ProjectLifecycle.ACTIVE.value,
        connection_state=ProjectConnectionState.CONNECTED.value,
    )
    test_db.add(project)
    test_db.commit()

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_active_user] = lambda: user

    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def make_test_frozen_suite(project_id: str = "proj-prelive-c3") -> FrozenSuite:
    """Generate a valid FrozenSuite with verified cryptographic digest."""
    req = build_demonstration_generation_request()
    req.project_id = project_id
    resp = generate_feasible_cases(req)
    return resp.frozen_suite


def _make_test_matched_pair_evidence(
    project_id: str = "proj-prelive-c3",
    case_id: str = "case-test-001",
    pair_id: str = "pair-test-001",
    caller_outcome: str = "SUCCESS_CLEAN_RECOVERY",
    exposure_status: ExposureStatus = ExposureStatus.CONFIRMED,
) -> MatchedPairEvidence:
    clean = TrialEvidence(
        project_id=project_id,
        case_id=case_id,
        pair_id=pair_id,
        trial_id="tr-clean-001",
        run_id="run-001",
        trial_role=TrialRole.CLEAN,
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity=CallerIdentity.SCRIPTED_CALLER,
        recovery_actor=RecoveryActor.SCRIPTED_CALLER,
        fixture_namespace="ns-clean-001",
        initial_state_fingerprint="fp-init",
        final_state_fingerprint="fp-clean-final",
        events=[],
        episodes=[],
        tool_calls_count=1,
        subsequent_calls_count=0,
        observed_effects=["order_confirmed"],
        execution_status=ExecutionStatus.COMPLETED,
        caller_outcome=caller_outcome,
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
        evidence_complete=True,
    )
    fault = TrialEvidence(
        project_id=project_id,
        case_id=case_id,
        pair_id=pair_id,
        trial_id="tr-fault-001",
        run_id="run-001",
        trial_role=TrialRole.FAULT,
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity=CallerIdentity.SCRIPTED_CALLER,
        recovery_actor=RecoveryActor.SCRIPTED_CALLER,
        fixture_namespace="ns-fault-001",
        initial_state_fingerprint="fp-init",
        final_state_fingerprint="fp-fault-final",
        events=[
            RuntimeEvent(
                event_id="ev-f1",
                event_type="HOOK_ENTRY_FORWARDING",
                tool_id="demonstration_order_placement",
                occurrence=1,
            ),
            RuntimeEvent(
                event_id="ev-f2",
                event_type="CALLER_OBSERVATION",
                tool_id="demonstration_order_placement",
                occurrence=1,
            ),
        ],
        episodes=[
            FaultEpisodeRecord(
                episode_id="ep-001",
                target_tool_id="demonstration_order_placement",
                target_occurrence=1,
                interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
                effect_phase=EffectPhase.BEFORE_EFFECT,
                fault_family=FaultFamily.TIMEOUT_DISCONNECTION,
                fault_mode="CALLER_TIMEOUT_EXCEEDED",
                declared_caller_timeout_ms=20,
                timeout_boundary_type=TimeoutBoundaryType.CALLER_TIMEOUT_EXCEEDED,
                prevented_forwarding=True,
                caller_observed_timeout=True,
                elapsed_wait_ms=50.0,
            )
        ],
        tool_calls_count=2,
        subsequent_calls_count=1,
        observed_effects=["order_created_on_subsequent_call"],
        execution_status=ExecutionStatus.COMPLETED,
        caller_outcome=caller_outcome,
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
        evidence_complete=True,
        snapshot_id="snap-fault-001",
        observed_entity_id="ord-test-01",
        observation_reference=StateObservationReference(
            snapshot_id="snap-fault-001",
            snapshot_version="1.0.0",
            entity_id="ord-test-01",
            observation_scope="post_recovery",
            fingerprint="fp-fault-final",
        ),
    )
    return MatchedPairEvidence(
        project_id=project_id,
        case_id=case_id,
        pair_id=pair_id,
        run_id="run-001",
        readiness_status=ReadinessStatus.READY,
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity=CallerIdentity.SCRIPTED_CALLER,
        configuration_snapshot={"mode": "test"},
        clean_trial=clean,
        fault_trial=fault,
        fixture_comparability=FixtureComparability.EQUIVALENT_LOGICAL_STATE,
        clean_qualification=CleanQualification.QUALIFIED,
        exposure_status=exposure_status,
        exposure_assessed=True,
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
    )


# ---------------------------------------------------------------------------
# Regressions 1 & 2: Model-Assisted Input Grounding
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_missing_authoritative_fixture_metadata_cannot_produce_success():
    """Without declared authoritative fixture context, model input grounding cannot return SUCCESS."""
    req = ModelAssistedDraftRequest(
        project_id="proj-prelive-c3",
        domain="ecommerce",
        instructions="Draft test cases with order placement.",
        existing_task_fixture=None,  # Absent fixture metadata
        existing_adapter_manifest=None,
        existing_recovery_contract=None,
    )
    # Mock model response returning valid structure
    mock_result = LLMGenerationResult(
        provider="mock",
        requested_model="mock",
        actual_model="mock",
        is_success=True,
        structured_data={
            "task_fixture": {
                "task_id": "invented-task-999",
                "task_version": "1.0.0",
                "fixture_id": "invented-fixture-999",
                "fixture_version": "1.0.0",
                "domain": "ecommerce",
                "associated_tool_ids": ["invented_tool"],
                "associated_recovery_contract_ids": ["rc-01"],
            },
            "recovery_contract": {
                "contract_id": "rc-01",
                "contract_version": "1.0.0",
                "permitted_terminal_outcomes": ["SUCCESS_CLEAN_RECOVERY"],
                "max_task_attempts": 2,
                "max_retries": 1,
                "max_tool_calls_budget": 5,
                "max_total_timeout_ms": 5000,
                "required_state_assertions": ["state_order_created"],
            },
            "unresolved_references": [],
            "explanation": "Model drafted without authoritative context",
        },
    )

    with patch.object(LLMProviderService, "invoke_for_user", new_callable=AsyncMock, return_value=mock_result):
        res = await prepare_draft_inputs(req)
        assert res.status != "SUCCESS"
        assert res.status == "UNRESOLVED_REFERENCES"
        assert len(res.unresolved_references) > 0
        unresolved_text = " ".join(res.unresolved_references)
        assert "fixture" in unresolved_text.lower()
        assert "adapter" in unresolved_text.lower()


@pytest.mark.anyio
async def test_invented_reset_observation_assertion_claims_remain_unresolved():
    """Model-invented reset capabilities, tools, and assertions are explicitly flagged as unresolved."""
    fixture_mgr = DemonstrationFixtureManager()
    adapter = DemonstrationToolAdapter(fixture_mgr)
    manifest = adapter.get_manifest()

    req = ModelAssistedDraftRequest(
        project_id="proj-prelive-c3",
        domain="ecommerce",
        instructions="Draft test cases with refund tool.",
        existing_task_fixture=None,
        existing_adapter_manifest=manifest,
        existing_recovery_contract=None,
    )
    mock_result = LLMGenerationResult(
        provider="mock",
        requested_model="mock",
        actual_model="mock",
        is_success=True,
        structured_data={
            "task_fixture": {
                "task_id": "task-checkout",
                "task_version": "1.0.0",
                "fixture_id": "fix-demonstration-cart",
                "fixture_version": "1.0.0",
                "domain": "ecommerce",
                "associated_tool_ids": ["unregistered_refund_tool"],
                "associated_recovery_contract_ids": ["rc-01"],
            },
            "recovery_contract": {
                "contract_id": "rc-01",
                "contract_version": "1.0.0",
                "permitted_terminal_outcomes": ["SUCCESS_CLEAN_RECOVERY"],
                "max_task_attempts": 2,
                "max_retries": 1,
                "max_tool_calls_budget": 5,
                "max_total_timeout_ms": 5000,
                "required_state_assertions": ["invented_assertion"],
            },
            "unresolved_references": [],
            "explanation": "Model proposed unregistered tools",
        },
    )

    with patch.object(LLMProviderService, "invoke_for_user", new_callable=AsyncMock, return_value=mock_result):
        res = await prepare_draft_inputs(req)
        assert res.status != "SUCCESS"
        # Tool and assertion are not registered in manifest/contract
        assert any("unregistered_refund_tool" in u or "tool" in u.lower() for u in res.unresolved_references)


# ---------------------------------------------------------------------------
# Regressions 3 & 4: Normalizing C2 Assertion Mappings at C3 Boundary
# ---------------------------------------------------------------------------


def test_json_restored_mappings_work_without_attribute_error():
    """Pinned mappings restored from JSON dictionaries are normalized into validated models."""
    json_dicts = [
        {
            "c3_assertion_id": "order_created",
            "c3_assertion_version": "1.0.0",
            "c2_assertion_id": "order_created",
            "c2_assertion_version": "1.0.0",
            "entity_type": "order",
            "required_time_scope": "post_recovery",
            "project_id": "proj-prelive-c3",
        },
        {
            "c3_assertion_id": "refund_completed",
            "c3_assertion_version": "1.0.0",
            "c2_assertion_id": "refund_completed",
            "c2_assertion_version": "1.0.0",
            "entity_type": "order",
            "required_time_scope": "post_recovery",
        },
    ]

    normalized = normalize_c2_to_c3_mappings(json_dicts)
    assert len(normalized) == 2
    assert isinstance(normalized[0], C2ToC3AssertionMapping)
    assert normalized[0].c3_assertion_id == "order_created"
    assert normalized[0].entity_type == "order"
    assert normalized[0].project_id == "proj-prelive-c3"


def test_malformed_mappings_fail_safely():
    """Malformed or invalid mappings are safely rejected without raising AttributeError or HTTP 500."""
    malformed_inputs = [
        {"invalid_key": "junk"},
        "string_not_mapping",
        12345,
        None,
        {"c3_assertion_id": ""},  # empty string violates min_length
    ]

    for item in malformed_inputs:
        norm = normalize_c2_to_c3_mapping(item)
        assert norm is None

    normalized_list = normalize_c2_to_c3_mappings(malformed_inputs)
    assert len(normalized_list) > 0
    assert all(isinstance(m, C2ToC3AssertionMapping) for m in normalized_list)


# ---------------------------------------------------------------------------
# Regressions 5, 6, 7: Fault Reachability and Exposure Classification
# ---------------------------------------------------------------------------


def test_unreached_occurrence_evaluated_as_not_triggered():
    """Target occurrence 2 when only 1 call occurred evaluates to NOT_TRIGGERED, not EXPOSURE_UNKNOWN."""
    runner = HarnessRunner(
        adapter=DemonstrationToolAdapter(DemonstrationFixtureManager()),
        fixture_manager=DemonstrationFixtureManager(),
    )

    plan = InterceptionPlan(
        trial_id="tr-test-occ2",
        target_tool_id="demonstration_order_placement",
        target_occurrence=2,  # Case targets occurrence 2
        interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
        effect_phase=EffectPhase.BEFORE_EFFECT,
        fault_family=FaultFamily.TIMEOUT_DISCONNECTION,
        fault_mode=TimeoutDisconnectionMode.CALLER_TIMEOUT_EXCEEDED,
        caller_timeout_ms=20,
        fault_timing_ms=50,
        timeout_boundary_type=TimeoutBoundaryType.CALLER_TIMEOUT_EXCEEDED,
    )

    fault_trial = TrialEvidence(
        project_id="proj-prelive-c3",
        case_id="case-occ2-test",
        pair_id="pair-occ2-test",
        trial_id="tr-fault-occ2",
        run_id="run-occ2",
        trial_role=TrialRole.FAULT,
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity=CallerIdentity.SCRIPTED_CALLER,
        recovery_actor=RecoveryActor.SCRIPTED_CALLER,
        fixture_namespace="ns-fault",
        initial_state_fingerprint="fp1",
        final_state_fingerprint="fp2",
        events=[
            RuntimeEvent(
                event_id="ev-1",
                event_type="HOOK_ENTRY_FORWARDING",
                tool_id="demonstration_order_placement",
                occurrence=1,  # Only occurrence 1 was reached
            )
        ],
        episodes=[],
        execution_status=ExecutionStatus.COMPLETED,
        caller_outcome="SUCCESS_CLEAN_RECOVERY",
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
    )

    status, reasons = runner._evaluate_exposure(fault_trial, plan)
    assert status == ExposureStatus.NOT_TRIGGERED
    assert any("not invoked at planned occurrence 2" in r for r in reasons)


def test_missing_receipts_at_reached_hook_evaluated_as_exposure_unknown():
    """Hook entry reached at target occurrence but delivery evidence missing evaluates to EXPOSURE_UNKNOWN."""
    runner = HarnessRunner(
        adapter=DemonstrationToolAdapter(DemonstrationFixtureManager()),
        fixture_manager=DemonstrationFixtureManager(),
    )

    plan = InterceptionPlan(
        trial_id="tr-test-occ1",
        target_tool_id="demonstration_order_placement",
        target_occurrence=1,
        interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
        effect_phase=EffectPhase.BEFORE_EFFECT,
        fault_family=FaultFamily.TIMEOUT_DISCONNECTION,
        fault_mode=TimeoutDisconnectionMode.CALLER_TIMEOUT_EXCEEDED,
        caller_timeout_ms=20,
        fault_timing_ms=50,
        timeout_boundary_type=TimeoutBoundaryType.CALLER_TIMEOUT_EXCEEDED,
    )

    fault_trial = TrialEvidence(
        project_id="proj-prelive-c3",
        case_id="case-occ1-test",
        pair_id="pair-occ1-test",
        trial_id="tr-fault-occ1",
        run_id="run-occ1",
        trial_role=TrialRole.FAULT,
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity=CallerIdentity.SCRIPTED_CALLER,
        recovery_actor=RecoveryActor.SCRIPTED_CALLER,
        fixture_namespace="ns-fault",
        initial_state_fingerprint="fp1",
        final_state_fingerprint="fp2",
        events=[
            RuntimeEvent(
                event_id="ev-1",
                event_type="HOOK_ENTRY_FORWARDING",
                tool_id="demonstration_order_placement",
                occurrence=1,  # Occurrence 1 reached
            )
        ],
        episodes=[],  # No episode or delivery receipt
        execution_status=ExecutionStatus.COMPLETED,
        caller_outcome="SUCCESS_CLEAN_RECOVERY",
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
    )

    status, reasons = runner._evaluate_exposure(fault_trial, plan)
    assert status == ExposureStatus.EXPOSURE_UNKNOWN
    assert any("reached occurrence 1, but no fault episode" in r for r in reasons)


def test_confirmed_exposure_requires_correlated_delivery_evidence():
    """Correlated episode, hook entry, delivery, and caller observation confirm exposure."""
    runner = HarnessRunner(
        adapter=DemonstrationToolAdapter(DemonstrationFixtureManager()),
        fixture_manager=DemonstrationFixtureManager(),
    )

    plan = InterceptionPlan(
        trial_id="tr-fault-001",
        target_tool_id="demonstration_order_placement",
        target_occurrence=1,
        interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
        effect_phase=EffectPhase.BEFORE_EFFECT,
        fault_family=FaultFamily.TIMEOUT_DISCONNECTION,
        fault_mode=TimeoutDisconnectionMode.CALLER_TIMEOUT_EXCEEDED,
        caller_timeout_ms=20,
        fault_timing_ms=50,
        timeout_boundary_type=TimeoutBoundaryType.CALLER_TIMEOUT_EXCEEDED,
    )

    evidence = _make_test_matched_pair_evidence(exposure_status=ExposureStatus.CONFIRMED)
    status, reasons = runner._evaluate_exposure(evidence.fault_trial, plan)
    assert status == ExposureStatus.CONFIRMED
    assert any("Correlated evidence confirms" in r for r in reasons)


# ---------------------------------------------------------------------------
# Regressions 8 & 14 & 15: Authoritative Scope & Honest Recovery Evaluation
# ---------------------------------------------------------------------------


def test_missing_or_wrong_time_scope_cannot_manufacture_recovery_pass():
    """Wrong observation time scope ('mid_trial') results in INCONCLUSIVE verdict, never PASS."""
    evidence = _make_test_matched_pair_evidence()
    evidence.fault_trial.observation_reference.observation_scope = "mid_trial"

    case = make_demonstration_candidate_case()
    contract = make_demonstration_recovery_contract()

    facts = [
        C2AssertionFact(
            assertion_id="order_created",
            assertion_version="1.0.0",
            value=C2FactValue.TRUE,
            time_scope="mid_trial",
            evaluator_version="1.0.0",
            provenance="C2_EVALUATOR_BRIDGE",
            entity_id="ord-test-01",
            snapshot_id="snap-fault-001",
            details={
                "project_id": "proj-prelive-c3",
                "trial_id": "tr-fault-001",
                "pair_id": "pair-test-001",
            },
        )
    ]

    req = RecoveryEvaluationRequest(
        project_id="proj-prelive-c3",
        case_id=case.case_id,
        candidate_case=case,
        recovery_contract=contract,
        matched_evidence=evidence,
        c2_facts=facts,
    )
    result = evaluate_recovery(req)
    assert result.recovery_verdict == RecoveryVerdict.INCONCLUSIVE
    assert result.recovery_verdict != RecoveryVerdict.PASS_COMPLETED


def test_missing_state_evidence_produces_honest_unknown_outcome():
    """Missing or UNKNOWN required state assertion facts yield INCONCLUSIVE, not PASS."""
    evidence = _make_test_matched_pair_evidence()
    case = make_demonstration_candidate_case()
    contract = make_demonstration_recovery_contract()

    req = RecoveryEvaluationRequest(
        project_id="proj-prelive-c3",
        case_id=case.case_id,
        candidate_case=case,
        recovery_contract=contract,
        matched_evidence=evidence,
        c2_facts=[],
    )
    result = evaluate_recovery(req)
    assert result.recovery_verdict == RecoveryVerdict.INCONCLUSIVE


def test_untriggered_fault_receives_no_recovery_pass():
    """An untriggered or unknown exposure trial must never receive a recovery pass."""
    evidence = _make_test_matched_pair_evidence(
        exposure_status=ExposureStatus.NOT_TRIGGERED
    )
    case = make_demonstration_candidate_case()
    contract = make_demonstration_recovery_contract()

    req = RecoveryEvaluationRequest(
        project_id="proj-prelive-c3",
        case_id=case.case_id,
        candidate_case=case,
        recovery_contract=contract,
        matched_evidence=evidence,
        c2_facts=[],
    )
    result = evaluate_recovery(req)
    assert result.recovery_verdict is None
    assert result.recovery_verdict != RecoveryVerdict.PASS_COMPLETED
    assert result.evaluation_status.value == "NOT_EVALUATED"


# ---------------------------------------------------------------------------
# Regressions 9 & 10: Evidence Retention and Project Scope Linkage
# ---------------------------------------------------------------------------


def test_complete_evidence_survives_export_import_and_stored_evaluation(test_db):
    """Complete per-case evidence survives disk export, database import, and stored evaluation."""
    suite = make_test_frozen_suite("proj-prelive-c3")
    store_frozen_suite(test_db, "proj-prelive-c3", suite)

    first_case = suite.selected_cases[0]
    evidence = _make_test_matched_pair_evidence(
        project_id="proj-prelive-c3",
        case_id=first_case.case_id,
        pair_id="pair-retention-001",
    )

    # 1. Export evidence to file
    with tempfile.TemporaryDirectory() as tmpdir:
        exported_path = export_evidence_to_file(evidence, export_dir=tmpdir)
        assert exported_path.exists()
        with open(exported_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["pair_id"] == "pair-retention-001"
        assert data["project_id"] == "proj-prelive-c3"

    # 2. Store matched pair in database
    store_matched_pair(test_db, "proj-prelive-c3", evidence)

    # 3. Retrieve stored pair and verify integrity
    retrieved = get_matched_pair(test_db, "proj-prelive-c3", "pair-retention-001")
    assert retrieved is not None
    assert retrieved.evidence_complete is True
    assert retrieved.evidence.clean_trial.trial_id == "tr-clean-001"
    assert retrieved.evidence.fault_trial.trial_id == "tr-fault-001"

    # 4. Execute stored evaluation with C2 facts
    c2_facts = [
        C2AssertionFact(
            assertion_id="state_order_created",
            assertion_version="1.0.0",
            value=C2FactValue.TRUE,
            time_scope="post_recovery",
            evaluator_version="1.0.0",
            provenance="C2_EVALUATOR_BRIDGE",
            entity_id="ord-test-01",
            snapshot_id="snap-fault-001",
            supporting_evidence_refs=["tr-fault-001", "snap-fault-001"],
            details={
                "project_id": "proj-prelive-c3",
                "trial_id": "tr-fault-001",
                "pair_id": "pair-retention-001",
            },
        )
    ]
    eval_resp = compute_and_store_evaluation(
        test_db,
        EvaluationComputeRequest(
            project_id="proj-prelive-c3",
            pair_id="pair-retention-001",
            c2_facts=c2_facts,
        ),
    )
    assert eval_resp.evaluation_status == "EVALUATED"
    assert eval_resp.recovery_verdict == RecoveryVerdict.PASS_COMPLETED


def test_suite_case_project_mismatches_rejected_without_relabelling(test_db):
    """Importing evidence with mismatched project references fails safely with ValueError."""
    evidence = _make_test_matched_pair_evidence(project_id="proj-other-workspace")

    with pytest.raises(ValueError, match="Project scope mismatch"):
        store_matched_pair(test_db, "proj-prelive-c3", evidence)


# ---------------------------------------------------------------------------
# Regressions 11 & 12: Controlled Execution & Live Mode Blocker
# ---------------------------------------------------------------------------


def test_native_controlled_runner_executes_stored_suite(test_client, test_db):
    """Native runner executes stored suites sequentially and persists all evidence in DEMONSTRATION mode."""
    suite = make_test_frozen_suite("proj-prelive-c3")
    store_frozen_suite(test_db, "proj-prelive-c3", suite)

    response = test_client.post(
        "/api/v1/c3/executions/run-controlled",
        json={
            "project_id": "proj-prelive-c3",
            "suite_id_or_digest": suite.suite_id,
            "execution_mode": "DEMONSTRATION",
            "max_suite_duration_sec": 30.0,
            "per_case_timeout_sec": 5.0,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["target_mode"] == "DEMONSTRATION"
    assert data["status"] in ("COMPLETED", "RUNNING")
    assert data["total_cases"] == len(suite.selected_cases)
    assert data["executed_cases"] > 0
    assert len(data["pair_ids"]) == data["executed_cases"]
    assert data["confirmed_exposure_count"] > 0

    first_pair_id = data["pair_ids"][0]
    stored_pair = get_matched_pair(test_db, "proj-prelive-c3", first_pair_id)
    assert stored_pair is not None
    assert stored_pair.evidence.project_id == "proj-prelive-c3"


def test_live_mode_remains_explicitly_blocked(test_client, test_db):
    """LIVE_AUT execution remains blocked and check_real_target_prerequisites returns False."""
    response = test_client.post(
        "/api/v1/c3/executions/run-controlled",
        json={
            "project_id": "proj-prelive-c3",
            "suite_id_or_digest": "suite-any",
            "execution_mode": "LIVE_AUT",
        },
    )
    assert response.status_code == 400
    assert "LIVE_AUT execution mode is BLOCKED" in response.json()["detail"]

    is_ready, missing = check_real_target_prerequisites()
    assert is_ready is False
    missing_str = " ".join(missing)
    for cap in FUTURE_NEXACART_REQUIRED_CAPABILITIES:
        assert cap in missing_str


# ---------------------------------------------------------------------------
# Regression 13: Cleanup Uncertainty Prevents Fixture Reuse
# ---------------------------------------------------------------------------


def test_cleanup_uncertainty_prevents_fixture_reuse():
    """Uncertain cleanup marks the namespace unclean and prevents subsequent trial reuse."""
    fixture_mgr = DemonstrationFixtureManager()
    ns = "ns-unclean-test"

    fixture_mgr.prepare_fixture(ns)
    fixture_mgr.record_in_flight_start(ns)

    cleanup_res = fixture_mgr.cleanup(ns)
    assert cleanup_res.status == CleanupStatus.UNCERTAIN
    assert cleanup_res.reusable is False
    assert cleanup_res.in_flight_count == 1

    with pytest.raises(RuntimeError, match="marked UNCLEAN and cannot be reused"):
        fixture_mgr.prepare_fixture(ns)


# ---------------------------------------------------------------------------
# Regression 16: Complete End-to-End Controlled Path
# ---------------------------------------------------------------------------


def test_full_controlled_workflow_demonstration(test_db):
    """Complete verified C3 workflow:
    Prepare inputs -> Validate -> Automatically generate cases -> Save suite ->
    Run controlled clean/fault trials -> Retain evidence -> Compute recovery results -> Inspect/export.
    """
    project_id = "proj-prelive-c3"

    # 1. Prepare and generate suite
    suite = make_test_frozen_suite(project_id)
    verify_suite_integrity(suite)

    # 2. Save suite
    stored_suite = store_frozen_suite(test_db, project_id, suite)
    assert stored_suite.suite_id == suite.suite_id

    # 3. Run controlled clean/fault trials with SuiteRunner
    fixture_mgr = DemonstrationFixtureManager()
    adapter = DemonstrationToolAdapter(fixture_mgr)
    runner = SuiteRunner(
        adapter=adapter,
        fixture_manager=fixture_mgr,
        task_fixture_metadata=suite.task_fixture_metadata,
        recovery_contract=suite.recovery_contract,
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity=CallerIdentity.SCRIPTED_CALLER,
        max_suite_duration_sec=30.0,
        per_case_timeout_sec=5.0,
    )
    import asyncio
    summary = asyncio.run(runner.run_frozen_suite(suite))
    assert summary.executed_count > 0
    assert summary.confirmed_exposure_count > 0

    # 4. Retain evidence
    first_res = summary.case_results[0]
    assert first_res.evidence is not None
    pair_record = store_matched_pair(test_db, project_id, first_res.evidence)
    assert pair_record.pair_id == first_res.evidence.pair_id

    # 5. Compute recovery results
    c2_facts = [
        C2AssertionFact(
            assertion_id="state_order_created",
            assertion_version="1.0.0",
            value=C2FactValue.TRUE,
            time_scope="post_recovery",
            evaluator_version="1.0.0",
            provenance="C2_EVALUATOR_BRIDGE",
            entity_id=first_res.evidence.fault_trial.observed_entity_id,
            snapshot_id=first_res.evidence.fault_trial.snapshot_id,
            supporting_evidence_refs=[
                first_res.evidence.fault_trial.trial_id,
                first_res.evidence.fault_trial.snapshot_id,
            ],
            details={
                "project_id": project_id,
                "trial_id": first_res.evidence.fault_trial.trial_id,
                "pair_id": pair_record.pair_id,
            },
        )
    ]
    eval_record = compute_and_store_evaluation(
        test_db,
        EvaluationComputeRequest(
            project_id=project_id,
            pair_id=pair_record.pair_id,
            c2_facts=c2_facts,
        ),
    )
    assert eval_record.recovery_verdict == RecoveryVerdict.PASS_COMPLETED

    # 6. Inspect & export evidence
    with tempfile.TemporaryDirectory() as tmpdir:
        exported_file = export_evidence_to_file(first_res.evidence, export_dir=tmpdir)
        assert exported_file.exists()
        assert exported_file.stat().st_size > 0
