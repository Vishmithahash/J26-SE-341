import os

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

# Set fake isolated database URL before any application imports
os.environ["DATABASE_URL"] = (
    "postgresql://isolated_user:isolated_pass@fake-host.local:5432/fake_db?sslmode=require"
)

from app.components.c3_robustness_recovery.contracts.schemas import (
    AdapterCapabilityManifest,
    CandidateFaultCase,
    CapabilityCombination,
    EffectPhase,
    FaultFamily,
    FaultValidationRequest,
    InterceptionHook,
    OccurrenceBounds,
    RecoveryContract,
    ReleaseRule,
    ReleaseRuleType,
    TaskFixtureMetadata,
    TerminalOutcome,
    TimeoutDisconnectionMode,
    TimeoutDisconnectionPayload,
    ToolCapabilityDeclaration,
    ToolMutability,
    ValidationScope,
    ValidationStatus,
)
from app.components.c3_robustness_recovery.services.validation import (
    STATIC_VALID_PENDING_CHECKS,
    get_fault_catalog,
    validate_fault_case,
)
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def make_valid_request() -> FaultValidationRequest:
    candidate_case = CandidateFaultCase(
        schema_version="1.0.0",
        project_id="proj-qa-001",
        case_id="case-c3-001",
        case_family_id="fam-timeout-01",
        domain="ecommerce",
        task_id="task-checkout-01",
        task_version="1.0.0",
        tool_id="payment_gateway",
        tool_version="2.1.0",
        fixture_id="fix-cart-populated",
        fixture_version="1.0.0",
        adapter_id="adapter-payment-01",
        adapter_version="1.2.0",
        recovery_contract_id="rec-contract-01",
        recovery_contract_version="1.0.0",
        occurrence=1,
        interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
        fault_family=FaultFamily.TIMEOUT_DISCONNECTION,
        effect_phase=EffectPhase.BEFORE_EFFECT,
        payload=TimeoutDisconnectionPayload(
            mode=TimeoutDisconnectionMode.CALLER_TIMEOUT_EXCEEDED,
            timing_ms=5000,
        ),
        release_rule=ReleaseRule(
            rule_type=ReleaseRuleType.ATTEMPT_BOUNDED,
            max_fault_count=1,
        ),
        required_assertions=["state_order_created", "balance_unchanged"],
        required_observations=["network_latency_ms", "socket_closed_event"],
        caller_timeout_ms=3000,
        reproducibility_seed=42,
    )

    adapter_manifest = AdapterCapabilityManifest(
        adapter_id="adapter-payment-01",
        adapter_version="1.2.0",
        schema_version="1.0.0",
        tools=[
            ToolCapabilityDeclaration(
                tool_id="payment_gateway",
                tool_version="2.1.0",
                mutability=ToolMutability.SIDE_EFFECTING,
            )
        ],
        supported_combinations=[
            CapabilityCombination(
                tool_id="payment_gateway",
                fault_family=FaultFamily.TIMEOUT_DISCONNECTION,
                effect_phase=EffectPhase.BEFORE_EFFECT,
                interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
                supported_occurrence_bounds=OccurrenceBounds(
                    min_occurrence=1, max_occurrence=5
                ),
                allowed_release_rule_types=[
                    ReleaseRuleType.ATTEMPT_BOUNDED,
                    ReleaseRuleType.IMMEDIATE,
                ],
                supported_payload_modes=[
                    "CALLER_TIMEOUT_EXCEEDED",
                    "SOCKET_DROP",
                ],
                required_observation_capabilities=["network_latency_ms"],
            )
        ],
    )

    task_fixture_metadata = TaskFixtureMetadata(
        task_id="task-checkout-01",
        task_version="1.0.0",
        fixture_id="fix-cart-populated",
        fixture_version="1.0.0",
        domain="ecommerce",
        associated_tool_ids=["payment_gateway"],
        associated_recovery_contract_ids=["rec-contract-01"],
        declared_reset_support=True,
        reset_method="database_snapshot_restore",
        declared_observation_support=True,
        supported_observations=["network_latency_ms", "socket_closed_event"],
        supports_committed_effect_observation=True,
        supports_partial_effect_observation=True,
    )

    recovery_contract = RecoveryContract(
        contract_id="rec-contract-01",
        contract_version="1.0.0",
        permitted_terminal_outcomes=[
            TerminalOutcome.SUCCESS_CLEAN_RECOVERY,
            TerminalOutcome.GRACEFUL_ABORT_USER_NOTIFIED,
        ],
        graceful_stopping_conditions=["user_notified_timeout"],
        initial_invocation_counts_as_attempt=True,
        max_task_attempts=3,
        max_retries=2,
        max_tool_calls_budget=10,
        max_total_timeout_ms=30000,
        required_state_assertions=["state_order_created"],
        allow_duplicate_side_effects=False,
        allow_retry_on_unverified_commit=False,
        require_truthful_completion_reporting=True,
        future_finding_rules=["RULE_NO_DUPLICATE_CHARGE"],
    )

    return FaultValidationRequest(
        candidate_case=candidate_case,
        adapter_manifest=adapter_manifest,
        task_fixture_metadata=task_fixture_metadata,
        recovery_contract=recovery_contract,
    )


# ---------------------------------------------------------------------------
# Fault Catalogue Tests
# ---------------------------------------------------------------------------


def test_fault_catalog_contains_exactly_five_families():
    catalog = get_fault_catalog()
    assert catalog.count == 5
    assert len(catalog.families) == 5
    assert catalog.injection_active is False

    expected_families = {
        FaultFamily.TIMEOUT_DISCONNECTION,
        FaultFamily.TRANSIENT_5XX,
        FaultFamily.RATE_LIMIT_429,
        FaultFamily.TOOL_UNAVAILABILITY,
        FaultFamily.MALFORMED_RESPONSE,
    }
    actual_families = {f.family for f in catalog.families}
    assert actual_families == expected_families

    for item in catalog.families:
        assert item.injection_implemented is False
        assert "not implemented" in item.note.lower()


def test_fault_catalog_endpoint(client):
    response = client.get("/api/v1/c3/fault-catalog")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 5
    assert data["injection_active"] is False
    assert len(data["families"]) == 5


# ---------------------------------------------------------------------------
# Static Validation Tests
# ---------------------------------------------------------------------------


def test_consistent_case_static_valid():
    request = make_valid_request()
    response = validate_fault_case(request)

    assert response.validation_scope == ValidationScope.STATIC_ONLY
    assert response.validation_status == ValidationStatus.STATIC_VALID
    assert response.runtime_verified is False
    assert response.execution_ready is False
    assert response.reasons == []
    assert response.recovery_verdict is None
    assert response.pending_checks == STATIC_VALID_PENDING_CHECKS


def test_validate_case_api_endpoint_200(client):
    request = make_valid_request()
    response = client.post(
        "/api/v1/c3/cases/validate",
        json=request.model_dump(mode="json"),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["validation_status"] == "STATIC_VALID"
    assert data["runtime_verified"] is False
    assert data["execution_ready"] is False
    assert len(data["pending_checks"]) == 5


def test_deliberate_delay_exceeding_caller_timeout_is_valid():
    request = make_valid_request()
    # timing_ms (5000) > caller_timeout_ms (3000) is valid in C3 to test timeout handling
    assert (
        request.candidate_case.payload.timing_ms
        > request.candidate_case.caller_timeout_ms
    )
    response = validate_fault_case(request)
    assert response.validation_status == ValidationStatus.STATIC_VALID


def test_exact_capability_matching_and_cross_product_rejection():
    request = make_valid_request()
    # Change interception_hook to AFTER_TOOL_CALL without declaring it in manifest
    case_dict = request.candidate_case.model_dump()
    case_dict["interception_hook"] = InterceptionHook.AFTER_TOOL_CALL.value
    request.candidate_case = CandidateFaultCase.model_validate(case_dict)

    response = validate_fault_case(request)
    assert response.validation_status == ValidationStatus.TEST_NOT_READY
    assert any(r.code == "UNSUPPORTED_CAPABILITY_COMBINATION" for r in response.reasons)


def test_task_reference_mismatches_return_test_not_ready():
    request = make_valid_request()
    case_dict = request.candidate_case.model_dump()
    case_dict["task_id"] = "different-task-id"
    request.candidate_case = CandidateFaultCase.model_validate(case_dict)

    response = validate_fault_case(request)
    assert response.validation_status == ValidationStatus.TEST_NOT_READY
    assert any(r.code == "TASK_REFERENCE_MISMATCH" for r in response.reasons)


def test_tool_not_associated_with_task_returns_test_not_ready():
    request = make_valid_request()
    meta_dict = request.task_fixture_metadata.model_dump()
    meta_dict["associated_tool_ids"] = ["other_unrelated_tool"]
    request.task_fixture_metadata = TaskFixtureMetadata.model_validate(meta_dict)

    response = validate_fault_case(request)
    assert response.validation_status == ValidationStatus.TEST_NOT_READY
    assert any(r.code == "TOOL_NOT_ASSOCIATED_WITH_TASK" for r in response.reasons)


def test_read_only_tool_mutability_incompatibility():
    request = make_valid_request()
    # Declare tool as READ_ONLY in manifest, but candidate claims AFTER_COMMIT
    manifest_dict = request.adapter_manifest.model_dump()
    manifest_dict["tools"][0]["mutability"] = ToolMutability.READ_ONLY.value
    manifest_dict["supported_combinations"][0]["effect_phase"] = (
        EffectPhase.AFTER_COMMIT.value
    )
    request.adapter_manifest = AdapterCapabilityManifest.model_validate(manifest_dict)

    case_dict = request.candidate_case.model_dump()
    case_dict["effect_phase"] = EffectPhase.AFTER_COMMIT.value
    request.candidate_case = CandidateFaultCase.model_validate(case_dict)

    response = validate_fault_case(request)
    assert response.validation_status == ValidationStatus.TEST_NOT_READY
    assert any(
        r.code == "READ_ONLY_TOOL_INVALID_EFFECT_PHASE" for r in response.reasons
    )


def test_after_commit_requires_committed_observation_support():
    request = make_valid_request()
    # Set AFTER_COMMIT phase, but task fixture metadata lacks committed observation support
    case_dict = request.candidate_case.model_dump()
    case_dict["effect_phase"] = EffectPhase.AFTER_COMMIT.value
    case_dict["interception_hook"] = InterceptionHook.APPLICATION_AWARE_HOOK.value
    request.candidate_case = CandidateFaultCase.model_validate(case_dict)

    meta_dict = request.task_fixture_metadata.model_dump()
    meta_dict["supports_committed_effect_observation"] = False
    request.task_fixture_metadata = TaskFixtureMetadata.model_validate(meta_dict)

    # Update manifest to match combination
    manifest_dict = request.adapter_manifest.model_dump()
    manifest_dict["supported_combinations"][0]["effect_phase"] = (
        EffectPhase.AFTER_COMMIT.value
    )
    manifest_dict["supported_combinations"][0]["interception_hook"] = (
        InterceptionHook.APPLICATION_AWARE_HOOK.value
    )
    request.adapter_manifest = AdapterCapabilityManifest.model_validate(manifest_dict)

    response = validate_fault_case(request)
    assert response.validation_status == ValidationStatus.TEST_NOT_READY
    assert any(
        r.code == "MISSING_COMMITTED_EFFECT_OBSERVATION_SUPPORT"
        for r in response.reasons
    )


def test_occurrence_bounds_rejection():
    request = make_valid_request()
    # Set occurrence to 10 (manifest bounds max is 5)
    case_dict = request.candidate_case.model_dump()
    case_dict["occurrence"] = 10
    request.candidate_case = CandidateFaultCase.model_validate(case_dict)

    response = validate_fault_case(request)
    assert response.validation_status == ValidationStatus.TEST_NOT_READY
    assert any(r.code == "OCCURRENCE_OUT_OF_BOUNDS" for r in response.reasons)


def test_missing_fixture_reset_for_side_effecting_tool():
    request = make_valid_request()
    meta_dict = request.task_fixture_metadata.model_dump()
    meta_dict["declared_reset_support"] = False
    request.task_fixture_metadata = TaskFixtureMetadata.model_validate(meta_dict)

    response = validate_fault_case(request)
    assert response.validation_status == ValidationStatus.TEST_NOT_READY
    assert any(r.code == "MISSING_FIXTURE_RESET_SUPPORT" for r in response.reasons)


# ---------------------------------------------------------------------------
# Strict Contract & Schema Constraints
# ---------------------------------------------------------------------------


def test_contradictory_budget_rejected_by_schema():
    contract_data = {
        "contract_id": "rec-01",
        "contract_version": "1.0.0",
        "permitted_terminal_outcomes": ["SUCCESS_CLEAN_RECOVERY"],
        "initial_invocation_counts_as_attempt": True,
        "max_task_attempts": 5,
        "max_retries": 1,  # Contradicts: 5 != 1 + 1
        "max_tool_calls_budget": 10,
        "max_total_timeout_ms": 10000,
        "required_state_assertions": ["state_ok"],
        "allow_duplicate_side_effects": False,
        "allow_retry_on_unverified_commit": False,
        "require_truthful_completion_reporting": True,
    }
    with pytest.raises(ValidationError) as exc:
        RecoveryContract.model_validate(contract_data)
    assert "Contradictory attempt/retry budget" in str(exc.value)


def test_boolean_rejected_for_strict_integer():
    rule_data = {
        "rule_type": "ATTEMPT_BOUNDED",
        "max_fault_count": True,  # Boolean passed for StrictInt
    }
    with pytest.raises(ValidationError):
        ReleaseRule.model_validate(rule_data)


def test_canary_secret_sanitization_in_422(client):
    canary = "CANARY_SECRET_12345"
    payload = {"candidate_case": {"schema_version": f"postgresql://{canary}@host/db"}}
    response = client.post("/api/v1/c3/cases/validate", json=payload)
    assert response.status_code == 422
    assert canary not in response.text


def test_pydantic_model_json_schema_and_serialization():
    req = make_valid_request()
    json_schema = FaultValidationRequest.model_json_schema()
    assert "properties" in json_schema
    assert "candidate_case" in json_schema["properties"]

    dumped_json = req.model_dump_json()
    assert isinstance(dumped_json, str)
    reloaded = FaultValidationRequest.model_validate_json(dumped_json)
    assert reloaded.candidate_case.case_id == req.candidate_case.case_id


def test_all_endpoints_registered_and_existing_intact(client):
    # Verify foundation endpoints
    r_root = client.get("/")
    assert r_root.status_code == 200

    r_health = client.get("/health")
    assert r_health.status_code == 200

    # Verify docs and openapi
    r_docs = client.get("/docs")
    assert r_docs.status_code == 200

    r_schema = client.get("/openapi.json")
    assert r_schema.status_code == 200
    paths = r_schema.json()["paths"]

    assert "/" in paths
    assert "/health" in paths
    assert "/health/db" in paths
    assert "/api/v1/c3/fault-catalog" in paths
    assert "/api/v1/c3/cases/validate" in paths
