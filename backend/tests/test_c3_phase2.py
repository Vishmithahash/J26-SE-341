import asyncio
import copy
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure isolated database environment
os.environ["DATABASE_URL"] = (
    "postgresql://isolated_user:isolated_pass@fake-host.local:5432/fake_db?sslmode=require"
)

from app.components.c3_robustness_recovery.contracts.schemas import (
    AdapterCapabilityManifest,
    CandidateFaultCase,
    EffectPhase,
    FaultFamily,
    InterceptionHook,
    RecoveryContract,
    TaskFixtureMetadata,
    TimeoutDisconnectionMode,
)
from app.components.c3_robustness_recovery.runtime.adapter import (
    CallerIdentity,
    CleanupStatus,
    DemonstrationFixtureManager,
    DemonstrationToolAdapter,
    RecoveryActor,
    TargetMode,
)
from app.components.c3_robustness_recovery.runtime.evidence import (
    CleanQualification,
    ExecutionStatus,
    ExposureStatus,
    FaultEpisodeRecord,
    FixtureComparability,
    MatchedPairEvidence,
    ReadinessStatus,
    TimeoutBoundaryType,
    TrialEvidence,
    TrialRole,
    export_evidence_to_file,
    sanitize_arguments,
    validate_evidence_linkage,
)
from app.components.c3_robustness_recovery.runtime.interceptor import (
    DomainToolInterceptor,
    InterceptionPlan,
)
from app.components.c3_robustness_recovery.runtime.runner import (
    HarnessRunner,
    check_runtime_readiness,
    main_async,
    make_demonstration_candidate_case,
    make_demonstration_recovery_contract,
    make_demonstration_task_fixture_metadata,
)
from app.main import app


@dataclass
class TestSetup:
    __test__ = False

    fixture_mgr: DemonstrationFixtureManager
    adapter: DemonstrationToolAdapter
    runner: HarnessRunner
    case: CandidateFaultCase
    manifest: AdapterCapabilityManifest
    metadata: TaskFixtureMetadata
    recovery: RecoveryContract


def get_test_setup() -> TestSetup:
    fixture_mgr = DemonstrationFixtureManager()
    adapter = DemonstrationToolAdapter(fixture_manager=fixture_mgr)
    runner = HarnessRunner(adapter=adapter, fixture_manager=fixture_mgr)
    case = make_demonstration_candidate_case()
    manifest = adapter.get_manifest()
    metadata = make_demonstration_task_fixture_metadata()
    recovery = make_demonstration_recovery_contract()
    return TestSetup(
        fixture_mgr=fixture_mgr,
        adapter=adapter,
        runner=runner,
        case=case,
        manifest=manifest,
        metadata=metadata,
        recovery=recovery,
    )


# ---------------------------------------------------------------------------
# 1. Clean Forwarding & Qualification
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_clean_forwarding_and_qualification():
    s = get_test_setup()

    evidence = await s.runner.run_matched_pair(
        candidate_case=s.case,
        adapter_manifest=s.manifest,
        task_fixture_metadata=s.metadata,
        recovery_contract=s.recovery,
        target_mode=TargetMode.DEMONSTRATION,
        allow_scripted_retry=False,
    )

    assert evidence.readiness_status == ReadinessStatus.READY
    assert evidence.clean_trial.execution_status == ExecutionStatus.COMPLETED
    assert evidence.clean_trial.caller_outcome == "SUCCESS"
    assert evidence.clean_qualification == CleanQualification.QUALIFIED
    assert evidence.clean_trial.tool_calls_count == 1
    assert "order_confirmed_in_clean" in evidence.clean_trial.observed_effects
    assert evidence.recovery_verdict is None


# ---------------------------------------------------------------------------
# 2. Targeted Call Never Reaches Target
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_targeted_call_never_reaches_target():
    s = get_test_setup()

    # Disable retry to examine only the targeted call outcome
    evidence = await s.runner.run_matched_pair(
        candidate_case=s.case,
        adapter_manifest=s.manifest,
        task_fixture_metadata=s.metadata,
        recovery_contract=s.recovery,
        target_mode=TargetMode.DEMONSTRATION,
        allow_scripted_retry=False,
    )

    assert evidence.fault_trial.caller_outcome == "TIMEOUT_ABORTED"
    assert len(evidence.fault_trial.episodes) == 1
    episode = evidence.fault_trial.episodes[0]
    assert episode.prevented_forwarding is True
    assert episode.caller_observed_timeout is True

    # State in fault namespace should reflect 0 orders placed because targeted call was intercepted
    assert (
        "order_created_on_subsequent_call" not in evidence.fault_trial.observed_effects
    )
    assert evidence.exposure_status == ExposureStatus.CONFIRMED


# ---------------------------------------------------------------------------
# 3. Unrelated Tool Does Not Consume Occurrence
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_unrelated_tool_does_not_consume_occurrence():
    trial_id = "test-unrelated-trial"
    plan = InterceptionPlan(
        trial_id=trial_id,
        target_tool_id="demonstration_order_placement",
        target_occurrence=1,
        interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
        effect_phase=EffectPhase.BEFORE_EFFECT,
        fault_family=FaultFamily.TIMEOUT_DISCONNECTION,
        fault_mode=TimeoutDisconnectionMode.CALLER_TIMEOUT_EXCEEDED,
        caller_timeout_ms=30,
    )
    interceptor = DomainToolInterceptor(trial_id=trial_id, plan=plan)

    called_unrelated = False

    async def forward_unrelated():
        nonlocal called_unrelated
        called_unrelated = True
        from app.components.c3_robustness_recovery.runtime.adapter import (
            ToolExecutionResult,
        )

        return ToolExecutionResult(
            success=True, tool_id="catalog_search", tool_version="1.0.0"
        )

    # 1. Call unrelated tool
    res = await interceptor.intercept_call(
        tool_id="catalog_search",
        tool_version="1.0.0",
        arguments={"query": "keyboard"},
        forward_callback=forward_unrelated,
    )
    assert called_unrelated is True
    assert res.success is True
    # Occurrence counter for target tool should still be unconsumed
    assert interceptor.is_consumed is False

    # 2. Call target tool - it should now be intercepted as occurrence 1
    called_target = False

    async def forward_target():
        nonlocal called_target
        called_target = True
        from app.components.c3_robustness_recovery.runtime.adapter import (
            ToolExecutionResult,
        )

        return ToolExecutionResult(
            success=True,
            tool_id="demonstration_order_placement",
            tool_version="1.0.0",
        )

    with pytest.raises(TimeoutError):
        await interceptor.intercept_call(
            tool_id="demonstration_order_placement",
            tool_version="1.0.0",
            arguments={"quantity": 1},
            forward_callback=forward_target,
        )

    assert called_target is False
    assert interceptor.is_consumed is True


# ---------------------------------------------------------------------------
# 4. Atomic One-Shot Delivery Under Concurrency
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_atomic_one_shot_delivery_concurrent():
    trial_id = "test-concurrency-trial"
    plan = InterceptionPlan(
        trial_id=trial_id,
        target_tool_id="demonstration_order_placement",
        target_occurrence=1,
        interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
        effect_phase=EffectPhase.BEFORE_EFFECT,
        fault_family=FaultFamily.TIMEOUT_DISCONNECTION,
        fault_mode=TimeoutDisconnectionMode.CALLER_TIMEOUT_EXCEEDED,
        caller_timeout_ms=25,
    )
    interceptor = DomainToolInterceptor(trial_id=trial_id, plan=plan)

    forward_count = 0

    async def forward_target():
        nonlocal forward_count
        forward_count += 1
        from app.components.c3_robustness_recovery.runtime.adapter import (
            ToolExecutionResult,
        )

        return ToolExecutionResult(
            success=True,
            tool_id="demonstration_order_placement",
            tool_version="1.0.0",
        )

    async def invoke():
        try:
            return await interceptor.intercept_call(
                tool_id="demonstration_order_placement",
                tool_version="1.0.0",
                arguments={"quantity": 1},
                forward_callback=forward_target,
            )
        except TimeoutError:
            return "TIMEOUT"

    # Launch two concurrent calls
    results = await asyncio.gather(invoke(), invoke())

    # Exactly ONE must have timed out (injected), and exactly ONE must have forwarded
    assert results.count("TIMEOUT") == 1
    assert forward_count == 1
    assert len(interceptor.episode_records) == 1
    assert interceptor.is_consumed is True


# ---------------------------------------------------------------------------
# 5. Subsequent Calls Pass Through
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_subsequent_calls_pass_through():
    s = get_test_setup()

    # allow_scripted_retry=True causes caller to retry on timeout
    evidence = await s.runner.run_matched_pair(
        candidate_case=s.case,
        adapter_manifest=s.manifest,
        task_fixture_metadata=s.metadata,
        recovery_contract=s.recovery,
        target_mode=TargetMode.DEMONSTRATION,
        allow_scripted_retry=True,
    )

    assert evidence.fault_trial.caller_outcome == "SUCCESS_AFTER_RETRY"
    assert evidence.fault_trial.recovery_actor == RecoveryActor.SCRIPTED_CALLER
    assert evidence.fault_trial.subsequent_calls_count == 1
    assert "order_created_on_subsequent_call" in evidence.fault_trial.observed_effects
    assert evidence.exposure_status == ExposureStatus.CONFIRMED


# ---------------------------------------------------------------------------
# 6. Missing or Contradictory Evidence Produces EXPOSURE_UNKNOWN
# ---------------------------------------------------------------------------


def test_missing_or_contradictory_evidence_produces_exposure_unknown():
    s = get_test_setup()

    plan = InterceptionPlan(
        trial_id="tr-test",
        target_tool_id=s.case.tool_id,
        target_occurrence=1,
        interception_hook=s.case.interception_hook,
        effect_phase=s.case.effect_phase,
        fault_family=s.case.fault_family,
        fault_mode=TimeoutDisconnectionMode.CALLER_TIMEOUT_EXCEEDED,
        caller_timeout_ms=20,
    )

    # 1. Contradictory evidence: episode claims forwarding was NOT prevented
    bad_episode = FaultEpisodeRecord(
        episode_id="ep-contradictory",
        target_tool_id=s.case.tool_id,
        target_occurrence=1,
        interception_hook=s.case.interception_hook,
        effect_phase=s.case.effect_phase,
        fault_family=s.case.fault_family,
        fault_mode="CALLER_TIMEOUT_EXCEEDED",
        declared_caller_timeout_ms=20,
        timeout_boundary_type=TimeoutBoundaryType.CALLER_TIMEOUT_EXCEEDED,
        prevented_forwarding=False,  # Contradiction!
        caller_observed_timeout=True,
        elapsed_wait_ms=25.0,
        consumed_atomically=True,
    )

    fault_trial = TrialEvidence(
        project_id="proj-1",
        case_id="case-1",
        pair_id="pair-1",
        trial_id="tr-test",
        run_id="run-1",
        trial_role=TrialRole.FAULT,
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity=CallerIdentity.SCRIPTED_CALLER,
        recovery_actor=RecoveryActor.UNKNOWN,
        fixture_namespace="ns-test",
        initial_state_fingerprint="fp1",
        final_state_fingerprint="fp2",
        episodes=[bad_episode],
        execution_status=ExecutionStatus.COMPLETED,
        caller_outcome="TIMEOUT",
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
    )

    status, reasons = s.runner._evaluate_exposure(fault_trial, plan)
    assert status == ExposureStatus.EXPOSURE_UNKNOWN
    assert any("failed to prevent forwarding" in r for r in reasons)


# ---------------------------------------------------------------------------
# 7. Unreached Trigger Produces NOT_TRIGGERED
# ---------------------------------------------------------------------------


def test_unreached_trigger_produces_not_triggered():
    s = get_test_setup()

    plan = InterceptionPlan(
        trial_id="tr-test",
        target_tool_id=s.case.tool_id,
        target_occurrence=1,
        interception_hook=s.case.interception_hook,
        effect_phase=s.case.effect_phase,
        fault_family=s.case.fault_family,
        fault_mode=TimeoutDisconnectionMode.CALLER_TIMEOUT_EXCEEDED,
        caller_timeout_ms=20,
    )

    # Empty events and no episodes -> tool was never reached
    fault_trial = TrialEvidence(
        project_id="proj-1",
        case_id="case-1",
        pair_id="pair-1",
        trial_id="tr-test",
        run_id="run-1",
        trial_role=TrialRole.FAULT,
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity=CallerIdentity.SCRIPTED_CALLER,
        recovery_actor=RecoveryActor.UNKNOWN,
        fixture_namespace="ns-test",
        initial_state_fingerprint="fp1",
        final_state_fingerprint="fp1",
        events=[],
        episodes=[],
        execution_status=ExecutionStatus.COMPLETED,
        caller_outcome="ABORTED_EARLY",
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
    )

    status, reasons = s.runner._evaluate_exposure(fault_trial, plan)
    assert status == ExposureStatus.NOT_TRIGGERED
    assert any("not invoked" in r for r in reasons)


# ---------------------------------------------------------------------------
# 8. Failed Clean Control Retained Without Rerun
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_failed_clean_control_retained_and_coexists_with_confirmed_exposure():
    s = get_test_setup()

    # Pre-drain initial balance in DemonstrationFixtureManager to cause clean control to fail
    orig_prepare = s.fixture_mgr.prepare_fixture

    def drained_prepare(namespace: str, config: dict | None = None):
        cfg = {"initial_balance": 0}  # 0 balance will fail order placement
        return orig_prepare(namespace, cfg)

    s.fixture_mgr.prepare_fixture = drained_prepare

    evidence = await s.runner.run_matched_pair(
        candidate_case=s.case,
        adapter_manifest=s.manifest,
        task_fixture_metadata=s.metadata,
        recovery_contract=s.recovery,
        target_mode=TargetMode.DEMONSTRATION,
        allow_scripted_retry=False,
    )

    # Clean control is retained as DISQUALIFIED
    assert evidence.clean_qualification == CleanQualification.DISQUALIFIED
    assert evidence.clean_trial.caller_outcome != "SUCCESS"

    # Confirmed exposure coexists despite clean control failure
    assert evidence.exposure_status == ExposureStatus.CONFIRMED

    # Limitation is explicitly recorded
    assert any(
        "Clean control trial was not qualified" in lim
        for lim in evidence.interpretation_limitations
    )


# ---------------------------------------------------------------------------
# 9. Equivalent Fresh Fixtures & Unique Namespaces
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_equivalent_fresh_fixtures_and_unique_namespaces():
    s = get_test_setup()

    evidence = await s.runner.run_matched_pair(
        candidate_case=s.case,
        adapter_manifest=s.manifest,
        task_fixture_metadata=s.metadata,
        recovery_contract=s.recovery,
        target_mode=TargetMode.DEMONSTRATION,
    )

    # Clean and fault namespaces must be strictly distinct
    clean_ns = evidence.clean_trial.fixture_namespace
    fault_ns = evidence.fault_trial.fixture_namespace
    assert clean_ns != fault_ns
    assert "clean" in clean_ns
    assert "fault" in fault_ns

    # Both trials must have begun with equivalent logical fingerprints
    assert (
        evidence.clean_trial.initial_state_fingerprint
        == evidence.fault_trial.initial_state_fingerprint
    )
    assert (
        evidence.fixture_comparability == FixtureComparability.EQUIVALENT_LOGICAL_STATE
    )


# ---------------------------------------------------------------------------
# 10. Configuration Snapshot Survives Input Mutation
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_configuration_snapshot_survives_input_mutation():
    s = get_test_setup()

    evidence = await s.runner.run_matched_pair(
        candidate_case=s.case,
        adapter_manifest=s.manifest,
        task_fixture_metadata=s.metadata,
        recovery_contract=s.recovery,
        target_mode=TargetMode.DEMONSTRATION,
    )

    snapshot_timeout = evidence.configuration_snapshot["candidate_case"][
        "caller_timeout_ms"
    ]

    # Mutate the original case object in memory
    s.case.caller_timeout_ms = 999999

    # Snapshot must remain unchanged
    assert (
        evidence.configuration_snapshot["candidate_case"]["caller_timeout_ms"]
        == snapshot_timeout
    )
    assert (
        evidence.configuration_snapshot["candidate_case"]["caller_timeout_ms"] != 999999
    )


# ---------------------------------------------------------------------------
# 11. Cancellation Never Forwards Intercepted Work Later
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_cancellation_never_forwards_intercepted_work_later():
    trial_id = "test-cancellation-trial"
    plan = InterceptionPlan(
        trial_id=trial_id,
        target_tool_id="demonstration_order_placement",
        target_occurrence=1,
        interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
        effect_phase=EffectPhase.BEFORE_EFFECT,
        fault_family=FaultFamily.TIMEOUT_DISCONNECTION,
        fault_mode=TimeoutDisconnectionMode.CALLER_TIMEOUT_EXCEEDED,
        caller_timeout_ms=500,  # Long hold
    )
    interceptor = DomainToolInterceptor(trial_id=trial_id, plan=plan)

    forward_executed = False

    async def forward_callback():
        nonlocal forward_executed
        forward_executed = True
        from app.components.c3_robustness_recovery.runtime.adapter import (
            ToolExecutionResult,
        )

        return ToolExecutionResult(
            success=True,
            tool_id="demonstration_order_placement",
            tool_version="1.0.0",
        )

    # Start intercept call and cancel it early
    task = asyncio.create_task(
        interceptor.intercept_call(
            tool_id="demonstration_order_placement",
            tool_version="1.0.0",
            arguments={"quantity": 1},
            forward_callback=forward_callback,
        )
    )
    await asyncio.sleep(0.01)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    # Target callback must NEVER have executed
    assert forward_executed is False

    # Check that cancellation recorded faithful episode evidence (Phase 3 Gap A correction)
    assert len(interceptor.episode_records) == 1
    ep = interceptor.episode_records[0]
    assert ep.prevented_forwarding is True
    assert ep.caller_observed_timeout is False
    assert ep.cancellation_reason == "PREMATURE_EXTERNAL_CANCELLATION"


# ---------------------------------------------------------------------------
# 12. Uncertain Cleanup Blocks Fixture Reuse
# ---------------------------------------------------------------------------


def test_uncertain_cleanup_blocks_fixture_reuse():
    fixture_mgr = DemonstrationFixtureManager()
    ns = "test-unclean-ns"
    fixture_mgr.prepare_fixture(ns)

    # Simulate an active in-flight operation that did not complete
    fixture_mgr.record_in_flight_start(ns)

    result = fixture_mgr.cleanup(ns)
    assert result.status == CleanupStatus.UNCERTAIN
    assert result.reusable is False

    # Attempting to reuse this unclean namespace must raise RuntimeError
    with pytest.raises(RuntimeError) as exc:
        fixture_mgr.prepare_fixture(ns)
    assert "cannot be reused" in str(exc.value)


# ---------------------------------------------------------------------------
# 13. Unsupported Runtime Modes Rejected Before Execution
# ---------------------------------------------------------------------------


def test_unsupported_runtime_modes_rejected_before_execution():
    s = get_test_setup()

    # Change case to SOCKET_DROP (not supported in Phase 2)
    case_dict = s.case.model_dump()
    case_dict["payload"]["mode"] = "SOCKET_DROP"
    bad_case = CandidateFaultCase.model_validate(case_dict)

    readiness = check_runtime_readiness(
        candidate_case=bad_case,
        adapter_manifest=s.manifest,
        task_fixture_metadata=s.metadata,
        recovery_contract=s.recovery,
        adapter=s.adapter,
        fixture_manager=s.fixture_mgr,
        target_mode=TargetMode.DEMONSTRATION,
        caller_identity=CallerIdentity.SCRIPTED_CALLER,
    )

    assert readiness.status == ReadinessStatus.NOT_READY
    assert any(
        "SOCKET_DROP and CONNECTION_REFUSED are not silently translated" in r
        for r in readiness.reasons
    )


# ---------------------------------------------------------------------------
# 14. Safe Evidence, Linkage Validation & Serialization
# ---------------------------------------------------------------------------


def test_safe_evidence_linkage_validation_and_serialization():
    # Sensitive arguments are sanitized
    raw_args = {
        "item_id": "item-101",
        "api_key": "SECRET_KEY_12345",
        "nested": {"password": "RAW_PASSWORD"},
    }
    cleaned = sanitize_arguments(raw_args)
    assert "SECRET_KEY_12345" not in str(cleaned)
    assert "RAW_PASSWORD" not in str(cleaned)
    assert cleaned["api_key"] == "[REDACTED_SECRET]"
    assert cleaned["nested"]["password"] == "[REDACTED_SECRET]"

    # Linkage validation
    s = get_test_setup()
    evidence_coroutine = s.runner.run_matched_pair(
        candidate_case=s.case,
        adapter_manifest=s.manifest,
        task_fixture_metadata=s.metadata,
        recovery_contract=s.recovery,
    )
    evidence = asyncio.run(evidence_coroutine)
    assert validate_evidence_linkage(evidence) is True

    # Corrupt linkage and verify ValueError
    corrupt_evidence = copy.deepcopy(evidence)
    corrupt_evidence.fault_trial.pair_id = "different-pair-id"
    with pytest.raises(ValueError) as exc:
        validate_evidence_linkage(corrupt_evidence)
    assert "Linkage violation" in str(exc.value)

    # File export test
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = export_evidence_to_file(evidence, export_dir=tmp_dir)
        assert out_path.exists()
        assert out_path.suffix == ".json"

        # Content is valid JSON
        reloaded = MatchedPairEvidence.model_validate_json(
            out_path.read_text(encoding="utf-8")
        )
        assert reloaded.pair_id == evidence.pair_id


# ---------------------------------------------------------------------------
# 15. Live Mode Has No Silent Fallback
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_live_mode_has_no_silent_fallback():
    s = get_test_setup()

    # Attempting LIVE_AUT when NexaCart prerequisites are missing
    evidence = await s.runner.run_matched_pair(
        candidate_case=s.case,
        adapter_manifest=s.manifest,
        task_fixture_metadata=s.metadata,
        recovery_contract=s.recovery,
        target_mode=TargetMode.LIVE_AUT,
    )

    assert evidence.readiness_status == ReadinessStatus.BLOCKED
    assert any("Live AUT prerequisite missing" in r for r in evidence.readiness_reasons)
    # Never ran demonstration trial as a silent fallback
    assert evidence.clean_trial.caller_outcome == "NOT_RUN"
    assert evidence.target_mode == TargetMode.LIVE_AUT


# ---------------------------------------------------------------------------
# 16. Developer CLI Execution
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_developer_cli_synthetic_and_live():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # CLI with --synthetic must exit 0
        exit_code = await main_async(["--synthetic", "--export-dir", tmp_dir])
        assert exit_code == 0
        exported_files = list(Path(tmp_dir).glob("evidence_*.json"))
        assert len(exported_files) >= 1

    # CLI with --live must exit with code 2 (blocked/prerequisites missing)
    exit_code_live = await main_async(["--live"])
    assert exit_code_live == 2


# ---------------------------------------------------------------------------
# 17. Existing Routes & OpenAPI Remain Intact
# ---------------------------------------------------------------------------


def test_existing_application_routes_and_openapi_intact():
    with TestClient(app) as client:
        r_health = client.get("/health")
        assert r_health.status_code == 200

        r_cat = client.get("/api/v1/c3/fault-catalog")
        assert r_cat.status_code == 200

        r_spec = client.get("/openapi.json")
        assert r_spec.status_code == 200
        paths = r_spec.json()["paths"]
        assert "/api/v1/c3/fault-catalog" in paths
        assert "/api/v1/c3/cases/validate" in paths
