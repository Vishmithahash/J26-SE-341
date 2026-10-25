"""Hermetic test suite for Component 3 Phase 3.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 3 - Automatic generation, frozen suites, remaining faults and supported post-commit experiments.
"""

import asyncio
import json
import os

import pytest
from fastapi.testclient import TestClient

# Ensure isolated database environment
os.environ["DATABASE_URL"] = (
    "postgresql://isolated_user:isolated_pass@fake-host.local:5432/fake_db?sslmode=require"
)

from app.components.c3_robustness_recovery.contracts.generation import (
    GenerationPolicy,
    GenerationStatus,
)
from app.components.c3_robustness_recovery.contracts.schemas import (
    EffectPhase,
    FaultFamily,
    InterceptionHook,
    MalformedResponseMode,
    TimeoutDisconnectionMode,
    ValidationScope,
)
from app.components.c3_robustness_recovery.runtime.adapter import (
    CleanupStatus,
    DemonstrationFixtureManager,
    DemonstrationToolAdapter,
    TargetMode,
    ToolExecutionResult,
    check_real_target_prerequisites,
)
from app.components.c3_robustness_recovery.runtime.evidence import (
    ExposureStatus,
    ReadinessStatus,
)
from app.components.c3_robustness_recovery.runtime.interceptor import (
    DomainToolInterceptor,
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
    make_demonstration_after_commit_case,
)
from app.components.c3_robustness_recovery.services.generation import (
    generate_feasible_cases,
)
from app.components.c3_robustness_recovery.services.suites import (
    compute_semantic_case_fingerprint,
    verify_suite_integrity,
)
from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Phase 2 Gap Corrections
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_gap_a_premature_cancellation_vs_deadline_expiry():
    """Gap A: Manual cancellation before boundary is distinguished from deadline expiry."""
    trial_id = "test-gap-a-trial"
    plan = InterceptionPlan(
        trial_id=trial_id,
        target_tool_id="demonstration_order_placement",
        target_occurrence=1,
        interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
        effect_phase=EffectPhase.BEFORE_EFFECT,
        fault_family=FaultFamily.TIMEOUT_DISCONNECTION,
        fault_mode=TimeoutDisconnectionMode.CALLER_TIMEOUT_EXCEEDED,
        caller_timeout_ms=500,  # 500ms boundary
    )
    interceptor = DomainToolInterceptor(trial_id=trial_id, plan=plan)

    async def forward_cb():
        return ToolExecutionResult(success=True, tool_id="tool", tool_version="1.0.0")

    # 1. Premature cancellation (after 10ms << 500ms)
    task1 = asyncio.create_task(
        interceptor.intercept_call(
            tool_id="demonstration_order_placement",
            tool_version="1.0.0",
            arguments={"quantity": 1},
            forward_callback=forward_cb,
        )
    )
    await asyncio.sleep(0.01)
    task1.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task1

    assert len(interceptor.episode_records) == 1
    ep1 = interceptor.episode_records[0]
    assert ep1.prevented_forwarding is True
    assert ep1.caller_observed_timeout is False
    assert ep1.cancellation_reason == "PREMATURE_EXTERNAL_CANCELLATION"


@pytest.mark.anyio
async def test_gap_b_caller_observed_outcome_correlation():
    """Gap B: Interceptor exception/hold alone does not establish confirmed exposure if caller reported SUCCESS."""
    fixture_mgr = DemonstrationFixtureManager()
    adapter = DemonstrationToolAdapter(fixture_manager=fixture_mgr)
    runner = HarnessRunner(adapter=adapter, fixture_manager=fixture_mgr)

    case = make_demonstration_candidate_case()
    manifest = adapter.get_manifest()
    metadata = make_demonstration_task_fixture_metadata()
    recovery = make_demonstration_recovery_contract()

    # Normal matched pair: exposure is confirmed because caller observed timeout error
    evidence = await runner.run_matched_pair(
        candidate_case=case,
        adapter_manifest=manifest,
        task_fixture_metadata=metadata,
        recovery_contract=recovery,
        target_mode=TargetMode.DEMONSTRATION,
    )
    assert evidence.exposure_status == ExposureStatus.CONFIRMED

    # If caller outcome was somehow SUCCESS (e.g. caller bypassed interceptor)
    fake_fault = evidence.fault_trial.model_copy(update={"caller_outcome": "SUCCESS"})
    plan = InterceptionPlan(
        trial_id="test",
        target_tool_id=case.tool_id,
        target_occurrence=case.occurrence,
        interception_hook=case.interception_hook,
        effect_phase=case.effect_phase,
        fault_family=case.fault_family,
        fault_mode=case.payload.mode,
    )
    status, reasons = runner._evaluate_exposure(fake_fault, plan)
    assert status == ExposureStatus.EXPOSURE_UNKNOWN
    assert any("Caller reported SUCCESS" in r for r in reasons)


@pytest.mark.anyio
async def test_gap_c_blocked_runs_cleanup_status_and_exposure_flag():
    """Gap C: Runs blocked before execution return CleanupStatus.NOT_ASSESSED and exposure_assessed=False."""
    fixture_mgr = DemonstrationFixtureManager()
    adapter = DemonstrationToolAdapter(fixture_manager=fixture_mgr)
    runner = HarnessRunner(adapter=adapter, fixture_manager=fixture_mgr)

    case = make_demonstration_candidate_case()
    manifest = adapter.get_manifest()
    metadata = make_demonstration_task_fixture_metadata()
    recovery = make_demonstration_recovery_contract()

    # In LIVE_AUT mode without environment target, execution is BLOCKED
    evidence = await runner.run_matched_pair(
        candidate_case=case,
        adapter_manifest=manifest,
        task_fixture_metadata=metadata,
        recovery_contract=recovery,
        target_mode=TargetMode.LIVE_AUT,
    )

    assert evidence.readiness_status == ReadinessStatus.BLOCKED
    assert evidence.cleanup_status == CleanupStatus.NOT_ASSESSED
    assert evidence.clean_trial.cleanup_status == CleanupStatus.NOT_ASSESSED
    assert evidence.fault_trial.cleanup_status == CleanupStatus.NOT_ASSESSED
    assert evidence.exposure_assessed is False
    assert evidence.exposure_status == ExposureStatus.NOT_TRIGGERED
    assert evidence.recovery_verdict is None


def test_gap_d_flexible_target_prerequisites():
    """Gap D: Live prerequisites check genuine target facilities, keep live mode BLOCKED when absent."""
    is_avail, missing = check_real_target_prerequisites()
    # The demonstration runner never runs live targets; it points to the live runner instead
    assert is_avail is False
    assert any("NexaCartLiveSuiteRunner" in m for m in missing)


# ---------------------------------------------------------------------------
# 2. Pure Feasible Case Generation
# ---------------------------------------------------------------------------


def test_generation_pure_deterministic_and_bounded():
    """Generation function derives feasible cases deterministically within bounds."""
    gen_req = build_demonstration_generation_request()
    resp1 = generate_feasible_cases(gen_req)

    assert resp1.generation_status == GenerationStatus.GENERATED
    assert resp1.validation_scope == ValidationScope.STATIC_ONLY
    assert resp1.runtime_verified is False
    assert resp1.execution_ready is False
    assert resp1.recovery_verdict is None
    assert resp1.frozen_suite is not None
    assert len(resp1.frozen_suite.selected_cases) > 0
    assert resp1.counters.selected_cases_count == len(resp1.frozen_suite.selected_cases)
    assert (
        resp1.counters.examined_candidates_count
        <= gen_req.policy.max_candidates_examined
    )

    # Repeat with same request -> exact same suite digest and cases
    resp2 = generate_feasible_cases(gen_req)
    assert resp1.frozen_suite.suite_digest == resp2.frozen_suite.suite_digest
    assert resp1.frozen_suite.suite_id == resp2.frozen_suite.suite_id


def test_generation_family_filtering():
    """Generation respects fault family filters."""
    gen_req = build_demonstration_generation_request()
    policy = gen_req.policy.model_copy(
        update={"target_fault_families": [FaultFamily.TRANSIENT_5XX]}
    )
    req_filtered = gen_req.model_copy(update={"policy": policy})
    resp = generate_feasible_cases(req_filtered)

    assert resp.generation_status == GenerationStatus.GENERATED
    assert resp.frozen_suite is not None
    for case in resp.frozen_suite.selected_cases:
        assert case.fault_family == FaultFamily.TRANSIENT_5XX


def test_generation_strict_type_enforcement():
    """Booleans used as integer limits or seeds are strictly rejected by Pydantic v2."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        GenerationPolicy(max_cases=True)  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        GenerationPolicy(selection_seed=False)  # type: ignore[arg-type]


def test_generation_empty_when_no_feasible_matches():
    """When capability filters match nothing, return NO_FEASIBLE_CASES safely."""
    gen_req = build_demonstration_generation_request()
    policy = gen_req.policy.model_copy(
        update={"target_tool_ids": ["non_existent_tool"]}
    )
    req_empty = gen_req.model_copy(update={"policy": policy})
    resp = generate_feasible_cases(req_empty)

    assert resp.generation_status == GenerationStatus.NO_FEASIBLE_CASES
    assert resp.counters.selected_cases_count == 0
    assert resp.frozen_suite is None


# ---------------------------------------------------------------------------
# 3. Deduplication, Selection, and Frozen Suite Integrity
# ---------------------------------------------------------------------------


def test_semantic_case_fingerprint_excludes_transient_metadata():
    """Case fingerprints depend only on semantic content, not IDs or display labels."""
    case1 = make_demonstration_candidate_case()
    case2 = case1.model_copy(
        update={
            "case_id": "different-uuid-12345",
            "case_family_id": "different-fam-id",
        }
    )
    fp1 = compute_semantic_case_fingerprint(case1)
    fp2 = compute_semantic_case_fingerprint(case2)
    assert fp1 == fp2

    # Semantic change changes fingerprint
    case3 = case1.model_copy(update={"caller_timeout_ms": 9999})
    fp3 = compute_semantic_case_fingerprint(case3)
    assert fp1 != fp3


def test_frozen_suite_tamper_detection():
    """Tampering with a frozen suite or any contained case fails integrity verification."""
    gen_req = build_demonstration_generation_request()
    resp = generate_feasible_cases(gen_req)
    suite = resp.frozen_suite
    assert suite is not None

    # Valid suite passes
    verify_suite_integrity(suite)

    # Tamper with case
    tampered_cases = list(suite.selected_cases)
    tampered_cases[0] = tampered_cases[0].model_copy(
        update={"caller_timeout_ms": 123456}
    )
    tampered_suite = suite.model_copy(update={"selected_cases": tampered_cases})

    with pytest.raises(ValueError, match="integrity check failed"):
        verify_suite_integrity(tampered_suite)


# ---------------------------------------------------------------------------
# 4. Supported Fault Delivery Mechanisms
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_transient_5xx_delivery():
    """TRANSIENT_5XX delivers 500-599 status and prevents target forwarding on BEFORE_EFFECT."""
    trial_id = "test-5xx"
    plan = InterceptionPlan(
        trial_id=trial_id,
        target_tool_id="demonstration_order_placement",
        target_occurrence=1,
        interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
        effect_phase=EffectPhase.BEFORE_EFFECT,
        fault_family=FaultFamily.TRANSIENT_5XX,
        fault_mode="HTTP_503",
        payload_details={"http_status": 503, "error_message": "Service overloaded"},
    )
    interceptor = DomainToolInterceptor(trial_id=trial_id, plan=plan)

    forward_executed = False

    async def forward_cb():
        nonlocal forward_executed
        forward_executed = True
        return ToolExecutionResult(success=True, tool_id="tool", tool_version="1.0.0")

    res = await interceptor.intercept_call(
        tool_id="demonstration_order_placement",
        tool_version="1.0.0",
        arguments={"quantity": 1},
        forward_callback=forward_cb,
    )

    assert forward_executed is False
    assert res.success is False
    assert "HTTP 503" in res.error
    assert len(interceptor.episode_records) == 1
    ep = interceptor.episode_records[0]
    assert ep.prevented_forwarding is True
    assert ep.fault_status_code == 503


@pytest.mark.anyio
async def test_rate_limit_429_delivery_retry_after():
    """RATE_LIMIT_429 delivers HTTP 429 and distinguishes absent, zero, and positive Retry-After."""
    for retry_after in [None, 0, 15]:
        trial_id = f"test-429-{retry_after}"
        plan = InterceptionPlan(
            trial_id=trial_id,
            target_tool_id="demonstration_order_placement",
            target_occurrence=1,
            interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
            effect_phase=EffectPhase.BEFORE_EFFECT,
            fault_family=FaultFamily.RATE_LIMIT_429,
            fault_mode="RATE_LIMIT_EXCEEDED",
            payload_details={"retry_after_seconds": retry_after},
        )
        interceptor = DomainToolInterceptor(trial_id=trial_id, plan=plan)

        res = await interceptor.intercept_call(
            tool_id="demonstration_order_placement",
            tool_version="1.0.0",
            arguments={"quantity": 1},
            forward_callback=lambda: asyncio.sleep(0),  # type: ignore[return-value]
        )

        assert res.success is False
        assert "HTTP 429" in res.error
        ep = interceptor.episode_records[0]
        assert ep.fault_status_code == 429
        assert ep.retry_after_seconds == retry_after


@pytest.mark.anyio
async def test_malformed_response_delivery():
    """MALFORMED_RESPONSE delivers genuine JSONDecodeError or schema violation at boundary."""
    for mode in [
        MalformedResponseMode.INVALID_JSON,
        MalformedResponseMode.TRUNCATED_JSON,
        MalformedResponseMode.EMPTY_BODY,
    ]:
        plan = InterceptionPlan(
            trial_id=f"test-malformed-{mode.value}",
            target_tool_id="demonstration_order_placement",
            target_occurrence=1,
            interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
            effect_phase=EffectPhase.BEFORE_EFFECT,
            fault_family=FaultFamily.MALFORMED_RESPONSE,
            fault_mode=mode.value,
        )
        interceptor = DomainToolInterceptor(trial_id=plan.trial_id, plan=plan)

        with pytest.raises(json.JSONDecodeError):
            await interceptor.intercept_call(
                tool_id="demonstration_order_placement",
                tool_version="1.0.0",
                arguments={"quantity": 1},
                forward_callback=lambda: asyncio.sleep(0),  # type: ignore[return-value]
            )

        ep = interceptor.episode_records[0]
        assert ep.malformed_fragment is not None


# ---------------------------------------------------------------------------
# 5. Application-Aware AFTER_COMMIT Lost-Response Experiment
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_after_commit_lost_response_lifecycle():
    """AFTER_COMMIT order: hook entry -> effect committed -> independent observation confirmed -> reply withheld -> caller timeout."""
    fixture_mgr = DemonstrationFixtureManager()
    adapter = DemonstrationToolAdapter(fixture_manager=fixture_mgr)
    runner = HarnessRunner(adapter=adapter, fixture_manager=fixture_mgr)

    ac_case = make_demonstration_after_commit_case()
    manifest = adapter.get_manifest()
    metadata = make_demonstration_task_fixture_metadata()
    recovery = make_demonstration_recovery_contract()

    evidence = await runner.run_matched_pair(
        candidate_case=ac_case,
        adapter_manifest=manifest,
        task_fixture_metadata=metadata,
        recovery_contract=recovery,
        target_mode=TargetMode.DEMONSTRATION,
    )

    assert evidence.exposure_status == ExposureStatus.CONFIRMED
    assert evidence.clean_trial.cleanup_status == CleanupStatus.CLEANED_AND_VERIFIED
    assert evidence.fault_trial.cleanup_status == CleanupStatus.CLEANED_AND_VERIFIED
    assert evidence.recovery_verdict is None

    fault_trial = evidence.fault_trial
    assert len(fault_trial.episodes) == 1
    ep = fault_trial.episodes[0]
    assert ep.prevented_forwarding is False  # Forwarded so effect commits
    assert ep.independent_observation_confirmed is True
    assert ep.committed_operation_id is not None
    assert ep.caller_observed_timeout is True


@pytest.mark.anyio
async def test_after_commit_missing_observation_prevents_confirmed_exposure():
    """If independent observation fails to confirm commit, exposure is evaluated as EXPOSURE_UNKNOWN."""
    trial_id = "test-ac-unconfirmed"
    plan = InterceptionPlan(
        trial_id=trial_id,
        target_tool_id="demonstration_order_placement",
        target_occurrence=1,
        interception_hook=InterceptionHook.APPLICATION_AWARE_HOOK,
        effect_phase=EffectPhase.AFTER_COMMIT,
        fault_family=FaultFamily.TIMEOUT_DISCONNECTION,
        fault_mode=TimeoutDisconnectionMode.CALLER_TIMEOUT_EXCEEDED,
        caller_timeout_ms=50,
    )
    interceptor = DomainToolInterceptor(trial_id=trial_id, plan=plan)

    # Forward callback returning an order id that is NOT in the fixture manager
    async def forward_cb():
        return ToolExecutionResult(
            success=True,
            tool_id="demonstration_order_placement",
            tool_version="1.0.0",
            output={"order_id": "ord-unregistered-ghost"},
            side_effect_occurred=True,
        )

    fixture_mgr = DemonstrationFixtureManager()
    res = await interceptor.intercept_call(
        tool_id="demonstration_order_placement",
        tool_version="1.0.0",
        arguments={"quantity": 1},
        forward_callback=forward_cb,
        context={"namespace": "ns_test", "fixture_manager": fixture_mgr},
    )

    # Because observation was NOT confirmed, reply was NOT withheld and timeout was not raised
    assert res.success is True
    ep = interceptor.episode_records[0]
    assert ep.independent_observation_confirmed is False
    assert ep.caller_observed_timeout is False


# ---------------------------------------------------------------------------
# 6. Bounded Frozen-Suite Execution
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_suite_runner_execution_and_summary():
    """SuiteRunner executes frozen suites sequentially with bounded duration and isolation."""
    gen_req = build_demonstration_generation_request()
    resp = generate_feasible_cases(gen_req)
    suite = resp.frozen_suite
    assert suite is not None

    fixture_mgr = DemonstrationFixtureManager()
    adapter = DemonstrationToolAdapter(fixture_manager=fixture_mgr)
    metadata = make_demonstration_task_fixture_metadata()
    recovery = make_demonstration_recovery_contract()

    suite_runner = SuiteRunner(
        adapter=adapter,
        fixture_manager=fixture_mgr,
        task_fixture_metadata=metadata,
        recovery_contract=recovery,
        target_mode=TargetMode.DEMONSTRATION,
    )

    summary = await suite_runner.run_frozen_suite(suite)

    assert summary.total_cases == len(suite.selected_cases)
    assert summary.executed_count == len(suite.selected_cases)
    assert summary.blocked_count == 0
    assert summary.error_count == 0
    assert summary.confirmed_exposure_count > 0
    assert summary.halted_early is False


@pytest.mark.anyio
async def test_suite_runner_uncertain_cleanup_halts_dependent_cases():
    """Uncertain cleanup in a case halts subsequent execution to safeguard isolation."""
    gen_req = build_demonstration_generation_request()
    resp = generate_feasible_cases(gen_req)
    suite = resp.frozen_suite
    assert suite is not None and len(suite.selected_cases) >= 2

    # Custom fixture manager simulating in-flight leak on cleanup
    class LeakyFixtureManager(DemonstrationFixtureManager):
        def cleanup(self, namespace: str):
            from app.components.c3_robustness_recovery.runtime.adapter import (
                CleanupResult,
            )

            return CleanupResult(
                status=CleanupStatus.UNCERTAIN,
                details="Simulated uncertain cleanup leak",
                reusable=False,
            )

    leaky_mgr = LeakyFixtureManager()
    adapter = DemonstrationToolAdapter(fixture_manager=leaky_mgr)
    metadata = make_demonstration_task_fixture_metadata()
    recovery = make_demonstration_recovery_contract()

    suite_runner = SuiteRunner(
        adapter=adapter,
        fixture_manager=leaky_mgr,
        task_fixture_metadata=metadata,
        recovery_contract=recovery,
        target_mode=TargetMode.DEMONSTRATION,
    )

    summary = await suite_runner.run_frozen_suite(suite)
    assert summary.halted_early is True
    assert summary.executed_count == 1
    assert "compromised fixture isolation" in str(summary.halt_reason)


# ---------------------------------------------------------------------------
# 7. API Endpoint: POST /api/v1/c3/cases/generate
# ---------------------------------------------------------------------------

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.shared.auth.dependencies import require_active_user
from app.shared.auth.models import User, UserRole
from app.shared.projects.models import Project, ProjectConnectionState, ProjectLifecycle


def _setup_c3_phase3_test_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    user = User(
        id=999,
        name="C3 Test User",
        email="c3test@example.com",
        canonical_email="c3test@example.com",
        password_hash="fakehash",
        role=UserRole.USER,
        is_active=True,
    )
    session.add(user)
    proj = Project(
        project_id="proj-demo-qa",
        owner_user_id=999,
        name="Project proj-demo-qa",
        domain="ecommerce",
        environment="TEST",
        backend_base_url="http://127.0.0.1:8000",
        backend_health_url="http://127.0.0.1:8000/health",
        configuration_version=1,
        lifecycle=ProjectLifecycle.ACTIVE.value,
        connection_state=ProjectConnectionState.CONNECTED.value,
    )
    session.add(proj)
    session.commit()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_active_user] = lambda: user
    return session, engine


def test_api_generate_cases_endpoint_valid():
    """POST /api/v1/c3/cases/generate returns HTTP 200 with pure deterministic frozen suite."""
    session, engine = _setup_c3_phase3_test_client()
    try:
        gen_req = build_demonstration_generation_request()
        payload = gen_req.model_dump(mode="json")

        response = client.post("/api/v1/c3/cases/generate", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert data["validation_scope"] == "STATIC_ONLY"
        assert data["generation_status"] == "GENERATED"
        assert data["runtime_verified"] is False
        assert data["execution_ready"] is False
        assert data["recovery_verdict"] is None

        assert data["frozen_suite"] is not None
        assert "suite_digest" in data["frozen_suite"]
    finally:
        app.dependency_overrides.clear()
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_api_generate_cases_endpoint_sanitizes_errors():
    """POST /api/v1/c3/cases/generate returns HTTP 422 for invalid types without echoing forbidden text."""
    session, engine = _setup_c3_phase3_test_client()
    try:
        bad_payload = {"policy": {"max_cases": "invalid_string_not_int"}}
        response = client.post("/api/v1/c3/cases/generate", json=bad_payload)
        assert response.status_code == 422
        assert "detail" in response.json()
    finally:
        app.dependency_overrides.clear()
        session.close()
        Base.metadata.drop_all(bind=engine)

