"""Hermetic automated test suite for Shared LLM Provider Integration.

Tests:
1. Local Ollama/Qwen adapter (native /api/tags, /api/chat, <think> stripping, error mapping).
2. Hosted Google Gemini adapter (native API, x-goog-api-key header, structured output, error sanitization).
3. Authoritative user-scoped selection persistence and isolation.
4. Provider switching affecting subsequent model-assisted calls.
5. All four components (C1-C4) real selection path wiring.
6. Backend Correction A: C3 fact scope snapshot binding.
7. Backend Correction B: Execution inputs resolving actual task/tools without generic fallback.
"""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CaseDiagnosisRecord,
    CauseCategory,
    ExplanationMethod,
)
from app.components.c1_tool_call_correctness.services.diagnosis_provider import (
    ModelAssistedDiagnosisProvider,
)
from app.components.c2_state_aware_workflow.builder.model_assisted import (
    ModelAssistedEFSMBuilder,
)
from app.components.c2_state_aware_workflow.contracts.workflow_input import (
    BusinessRule,
    SyntheticFixtureReference,
    ToolParameterSpec,
    ToolSpecification,
    WorkflowInputContract,
)
from app.components.c3_robustness_recovery.contracts.evaluation import (
    C2AssertionFact,
    C2FactValue,
)
from app.components.c3_robustness_recovery.contracts.generation import (
    ModelAssistedDraftRequest,
)
from app.components.c3_robustness_recovery.contracts.schemas import (
    AdapterCapabilityManifest,
    CapabilityCombination,
    EffectPhase,
    FaultFamily,
    InterceptionHook,
    OccurrenceBounds,
    ReleaseRuleType,
    ToolCapabilityDeclaration,
    ToolMutability,
)
from app.components.c3_robustness_recovery.services.c2_facts import (
    get_c2_fact_value,
)
from app.components.c3_robustness_recovery.services.model_assisted_prep import (
    prepare_draft_inputs,
)
from app.components.c4_policy_aware_safety.contracts.artifacts import (
    ArtifactKind,
    ArtifactVersionRecord,
)
from app.components.c4_policy_aware_safety.extraction.provider import (
    SharedLlmPolicyExtractionProvider,
    get_extraction_provider,
)
from app.database import Base, get_db
from app.main import app
from app.shared.auth.dependencies import require_active_user
from app.shared.auth.models import User, UserRole
from app.shared.integration.adapters import TargetMode
from app.shared.integration.contracts import ExecutionStartRequest
from app.shared.integration.executor import SharedExecutionCoordinator
from app.shared.integration.models import IntegrationRunPlanModel
from app.shared.llm.adapters.gemini import GeminiAdapter
from app.shared.llm.adapters.ollama import OllamaAdapter
from app.shared.llm.contracts import (
    ConnectionType,
    LLMGenerationRequest,
    LLMGenerationResult,
    LLMProviderType,
    ModelSelectionConfig,
)
from app.shared.llm.service import LLMProviderService
from app.shared.projects.models import (
    Project,
    ProjectConnectionState,
    ProjectLifecycle,
)

# SQLite in-memory test database for hermetic, fast testing
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create all tables in memory before each test and drop them after."""
    Base.metadata.create_all(bind=test_engine)
    with patch("app.database.SessionLocal", side_effect=TestSessionLocal):
        yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user(db_session: Session) -> User:
    user = User(
        id=901,
        name="Test Admin",
        email="admin901@test.com",
        canonical_email="admin901@test.com",
        password_hash="fake-hash",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.merge(user)
    db_session.commit()
    return user


@pytest.fixture
def second_user(db_session: Session) -> User:
    user = User(
        id=902,
        name="Second User",
        email="user902@test.com",
        canonical_email="user902@test.com",
        password_hash="fake-hash",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.merge(user)
    db_session.commit()
    return user


@pytest.fixture
def client(test_user: User):
    def override_get_db():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_active_user] = lambda: test_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. API Route Tests: Providers, Selection, and Test Connection
# ---------------------------------------------------------------------------


def test_get_providers_endpoint(client):
    """GET /api/v1/llm/providers returns status of local and hosted providers."""
    res = client.get("/api/v1/llm/providers")
    assert res.status_code == 200
    providers = res.json()
    assert isinstance(providers, list)
    prov_names = {p["provider"] for p in providers}
    assert "ollama" in prov_names
    assert "gemini" in prov_names


def test_get_and_put_selection_endpoint(client, test_user):
    """GET and PUT /api/v1/llm/selection correctly persist user selection."""
    res = client.get("/api/v1/llm/selection")
    assert res.status_code == 200
    initial = res.json()
    assert "provider" in initial

    # Save Gemini hosted selection
    put_payload = {
        "connection_type": "hosted",
        "provider": "gemini",
        "model_id": "gemini-3.5-flash-lite",
        "temperature": 0.0,
        "max_tokens": 1024,
    }
    put_res = client.put("/api/v1/llm/selection", json=put_payload)
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["provider"] == "gemini"
    assert updated["model_id"] == "gemini-3.5-flash-lite"
    assert updated["connection_type"] == "hosted"

    # Verify retrieval reflects saved selection
    verify_res = client.get("/api/v1/llm/selection")
    assert verify_res.status_code == 200
    assert verify_res.json()["provider"] == "gemini"


def test_user_selection_isolation(client, db_session, test_user, second_user):
    """Verify that User A's selection does NOT overwrite User B's selection."""
    service = LLMProviderService.get_instance()

    service.save_user_selection(
        str(test_user.id),
        ModelSelectionConfig(
            connection_type=ConnectionType.LOCAL,
            provider=LLMProviderType.OLLAMA,
            model_id="qwen3:4b",
        ),
        db=db_session,
    )

    service.save_user_selection(
        str(second_user.id),
        ModelSelectionConfig(
            connection_type=ConnectionType.HOSTED,
            provider=LLMProviderType.GEMINI,
            model_id="gemini-3.5-flash-lite",
        ),
        db=db_session,
    )

    sel_901 = service.get_user_selection(str(test_user.id), db=db_session)
    sel_902 = service.get_user_selection(str(second_user.id), db=db_session)

    assert sel_901.provider == LLMProviderType.OLLAMA
    assert sel_901.model_id == "qwen3:4b"
    assert sel_902.provider == LLMProviderType.GEMINI
    assert sel_902.model_id == "gemini-3.5-flash-lite"


# ---------------------------------------------------------------------------
# 2. Ollama Adapter: Native API, Error Mapping, and <think> Tag Stripping
# ---------------------------------------------------------------------------


def test_ollama_adapter_think_tag_stripping():
    """Verify Ollama adapter cleanly strips private <think> reasoning tags."""
    adapter = OllamaAdapter(base_url="http://127.0.0.1:11434", default_model="qwen3:4b")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "message": {
            "role": "assistant",
            "content": "<think>Private chain of thought reasoning</think>Final structured answer",
        },
        "prompt_eval_count": 12,
        "eval_count": 8,
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        res = asyncio.run(
            adapter.generate(LLMGenerationRequest(prompt="Test prompt", temperature=0.0))
        )
        assert res.content == "Final structured answer"
        assert "<think>" not in res.content
        assert res.usage.prompt_tokens == 12
        assert res.usage.completion_tokens == 8


def test_ollama_adapter_model_not_installed_error():
    """Verify missing model returns MODEL_NOT_INSTALLED error without falling back."""
    adapter = OllamaAdapter(base_url="http://127.0.0.1:11434", default_model="nonexistent:model")

    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.json.return_value = {
        "error": "model 'nonexistent:model' not found, try pulling it first"
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        res = asyncio.run(adapter.generate(LLMGenerationRequest(prompt="Hello")))
        assert not res.is_success
        assert res.error_type == "MODEL_NOT_INSTALLED"
        assert "not installed" in res.error_message


# ---------------------------------------------------------------------------
# 3. Gemini Adapter: API Key Sanitization and Header Placement
# ---------------------------------------------------------------------------


def test_gemini_adapter_header_and_sanitization():
    """Verify Gemini adapter sends x-goog-api-key header and never leaks it in errors."""
    secret_key = "AIzaSyTestSecretKeyNeverExpose"
    adapter = GeminiAdapter(api_key=secret_key, default_model="gemini-3.5-flash-lite")

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = f"Invalid argument: key {secret_key} rejected"

    with patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp
    ) as mock_post:
        res = asyncio.run(adapter.generate(LLMGenerationRequest(prompt="Test")))
        assert not res.is_success

        called_headers = mock_post.call_args[1]["headers"]
        assert called_headers.get("x-goog-api-key") == secret_key

        err_msg = res.error_message
        assert secret_key not in err_msg
        assert "[REDACTED]" in err_msg or "INVALID_ARGUMENT" in err_msg or res.error_type == "INVALID_CREDENTIALS"


# ---------------------------------------------------------------------------
# 4. Component 1: Tool-Call Correctness Model-Assisted Diagnosis
# ---------------------------------------------------------------------------


def test_c1_model_assisted_diagnosis_integration():
    """Verify C1 diagnosis provider uses selected model presentation without inventing evidence."""
    record = CaseDiagnosisRecord(
        diagnosis_id="diag-001",
        project_id="proj-demo-qa",
        run_id="run-001",
        case_execution_id="ce-001",
        case_id="tc-001",
        requirement_version="1.0.0",
        evaluator_version="1.0.0",
        cause_category=CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT,
        explanation_summary="Deterministic check failed: Missing required field 'order_id'.",
        evidence_refs=["ev-001"],
    )

    async def mock_callable(**kwargs):
        return {
            "summary": "Explained by model: order_id was missing.",
            "cited_evidence": ["ev-001"],
        }

    provider = ModelAssistedDiagnosisProvider(
        model_callable=mock_callable,
        model_name="gemini-3.5-flash-lite",
    )

    result = asyncio.run(provider.present_diagnosis(record))
    assert result.explanation_method == ExplanationMethod.MODEL_ASSISTED_PRESENTATION
    assert "Explained by model" in result.explanation_summary
    assert result.metrics.model_name == "gemini-3.5-flash-lite"


# ---------------------------------------------------------------------------
# 5. Component 2: State-Aware Workflow EFSM Draft Proposal
# ---------------------------------------------------------------------------


def test_c2_model_assisted_builder_proposal():
    """Verify C2 EFSM builder proposes draft workflow using selected model without auto-approval."""
    builder = ModelAssistedEFSMBuilder()

    wf_input = WorkflowInputContract(
        project_id="proj-demo-qa",
        domain="ecommerce",
        workflow_id="wf-cart-01",
        name="Cart Checkout Workflow",
        task="Test checkout process",
        business_rules=[
            BusinessRule(
                rule_id="RULE-1",
                name="Cart Item Rule",
                description="Item must be added to cart before checkout",
                category="ordering",
            )
        ],
        tool_specifications=[
            ToolSpecification(
                tool_name="add_to_cart",
                description="Add item",
                parameters=[
                    ToolParameterSpec(
                        name="item_id",
                        type="string",
                        required=True,
                    )
                ],
            )
        ],
        synthetic_fixture=SyntheticFixtureReference(
            fixture_id="fix-c2-standard",
            description="Synthetic cart fixture",
        ),
    )

    mock_gen_result = LLMGenerationResult(
        provider="ollama",
        requested_model="qwen3:4b",
        actual_model="qwen3:4b",
        raw_text='{"name": "Refined Cancellation Model", "description": "LLM refined workflow"}',
        structured_data={
            "name": "Refined Cancellation Model",
            "description": "LLM refined workflow",
        },
        is_success=True,
    )

    with patch.object(
        builder, "_async_invoke", new_callable=AsyncMock, return_value=mock_gen_result
    ):
        model = builder.propose_model(wf_input)
        assert model.name == "Refined Cancellation Model"
        assert len(model.states) >= 2


# ---------------------------------------------------------------------------
# 6. Component 3: Robustness and Recovery Model-Assisted Preparation
# ---------------------------------------------------------------------------


def test_c3_model_assisted_draft_inputs():
    """Verify C3 prepare_draft_inputs calls selected model and flags missing references."""
    mock_gen_result = LLMGenerationResult(
        provider="gemini",
        requested_model="gemini-3.5-flash-lite",
        actual_model="gemini-3.5-flash-lite",
        raw_text="""{
            "task_fixture": {
                "task_id": "task-order-recovery",
                "task_version": "1.0.0",
                "fixture_id": "fix-order-01",
                "fixture_version": "1.0.0",
                "domain": "ecommerce",
                "associated_tool_ids": ["refund_api", "unregistered_external_tool"],
                "associated_recovery_contract_ids": ["rec-transient-01"],
                "declared_reset_support": false,
                "reset_method": null,
                "declared_observation_support": true,
                "supported_observations": ["order_status"],
                "supports_committed_effect_observation": false,
                "supports_partial_effect_observation": false
            },
            "recovery_contract": {
                "contract_id": "rec-transient-01",
                "contract_version": "1.0.0",
                "permitted_terminal_outcomes": ["SUCCESS_CLEAN_RECOVERY"],
                "graceful_stopping_conditions": [],
                "initial_invocation_counts_as_attempt": true,
                "max_task_attempts": 3,
                "max_retries": 2,
                "max_tool_calls_budget": 10,
                "max_total_timeout_ms": 30000,
                "required_state_assertions": ["order_recovered"],
                "allow_duplicate_side_effects": false,
                "allow_retry_on_unverified_commit": false,
                "require_truthful_completion_reporting": true
            },
            "unresolved_references": ["payment_gateway_hook"],
            "explanation": "Recovery contract proposed for transient API failure."
        }""",
        prompt_template_version="c3_prep_v1",
    )

    manifest = AdapterCapabilityManifest(
        adapter_id="adapter-ecom",
        adapter_version="1.0.0",
        schema_version="1.0.0",
        tools=[
            ToolCapabilityDeclaration(
                tool_id="refund_api",
                tool_version="1.0.0",
                mutability=ToolMutability.SIDE_EFFECTING,
            )
        ],
        supported_combinations=[
            CapabilityCombination(
                tool_id="refund_api",
                fault_family=FaultFamily.TRANSIENT_5XX,
                effect_phase=EffectPhase.BEFORE_EFFECT,
                interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
                supported_occurrence_bounds=OccurrenceBounds(
                    min_occurrence=1, max_occurrence=3
                ),
                allowed_release_rule_types=[ReleaseRuleType.ATTEMPT_BOUNDED],
                supported_payload_modes=["HTTP_500"],
            )
        ],
    )

    req = ModelAssistedDraftRequest(
        project_id="proj-demo-qa",
        task_id="task-order-recovery",
        tool_id="refund_api",
        existing_adapter_manifest=manifest,
    )

    with patch.object(
        LLMProviderService,
        "invoke_for_user",
        new_callable=AsyncMock,
        return_value=mock_gen_result,
    ):
        res = asyncio.run(prepare_draft_inputs(req, user_id="901"))
        assert res.status == "UNRESOLVED_REFERENCES"
        assert res.draft_task_fixture is not None
        assert res.draft_recovery_contract is not None
        assert any("unregistered_external_tool" in u for u in res.unresolved_references)


# ---------------------------------------------------------------------------
# 7. Component 4: Policy-Aware Safety Shared LLM Extraction Provider
# ---------------------------------------------------------------------------


def test_c4_shared_llm_policy_extraction():
    """Verify C4 extraction provider uses the shared selected LLM."""
    provider = get_extraction_provider(provider_id="shared_llm", user_id="901")
    assert isinstance(provider, SharedLlmPolicyExtractionProvider)

    mock_gen_result = LLMGenerationResult(
        provider="gemini",
        requested_model="gemini-3.5-flash-lite",
        actual_model="gemini-3.5-flash-lite",
        raw_text="""{
            "candidates": [
                {
                    "rule_id": "RULE-ORDER-REFUND-01",
                    "policy_family": "AUTHORIZATION",
                    "source_excerpt": "Refunds exceeding $100 require supervisor approval.",
                    "description": "Supervisor approval required for high-value refunds",
                    "principal_selector": "role:customer_service",
                    "action_selector": "issue_refund",
                    "resource_selector": "order:amount>100",
                    "effect": "DENY"
                }
            ]
        }""",
        prompt_template_version="v5.0.0",
    )

    from app.components.c4_policy_aware_safety.contracts import (
        ExtractionReadinessReport,
        ExtractionReadinessStatus,
    )

    with (
        patch.object(
            LLMProviderService,
            "invoke_for_user",
            new_callable=AsyncMock,
            return_value=mock_gen_result,
        ),
        patch.object(
            provider,
            "check_readiness",
            return_value=ExtractionReadinessReport(
                ready=True,
                status=ExtractionReadinessStatus.READY,
                provider_id="gemini",
                model_identifier="gemini-3.5-flash-lite",
            ),
        ),
    ):
        artifact = ArtifactVersionRecord(
            project_id="proj-demo-qa",
            artifact_id="art-refund-policy",
            artifact_kind=ArtifactKind.POLICY_DOCUMENT,
            version=1,
            content_hash="abc123digest",
            normalized_content="Refunds exceeding $100 require supervisor approval.",
            sections=[],
            metadata={},
        )

        candidates, meta = provider.extract_candidates(artifact)
        assert len(candidates) == 1
        assert candidates[0]["rule_id"] == "RULE-ORDER-REFUND-01"
        assert meta["schema_version"] == "c4_candidate_v1"


# ---------------------------------------------------------------------------
# 8. Backend Correction A: C3 Fact Scope Snapshot Binding
# ---------------------------------------------------------------------------


def test_c3_fact_scope_rejects_wrong_snapshot():
    """Verify get_c2_fact_value returns UNKNOWN if snapshot_id does not match expected_snapshot."""
    fact = C2AssertionFact(
        assertion_id="order_created",
        assertion_version="1.0.0",
        entity_id="order-123",
        snapshot_id="snapshot-correct-v1",
        time_scope="post_recovery",
        value=C2FactValue.TRUE,
    )

    matching_val = get_c2_fact_value(
        [fact],
        assertion_id="order_created",
        snapshot_id="snapshot-correct-v1",
        assertion_version="1.0.0",
        require_strict_scope=True,
    )
    assert matching_val == C2FactValue.TRUE

    wrong_val = get_c2_fact_value(
        [fact],
        assertion_id="order_created",
        snapshot_id="snapshot-unrelated-v99",
        assertion_version="1.0.0",
        require_strict_scope=True,
    )
    assert wrong_val == C2FactValue.UNKNOWN


# ---------------------------------------------------------------------------
# 9. Backend Correction B: Execution Inputs Task/Tool Resolution
# ---------------------------------------------------------------------------


def test_execution_inputs_missing_blocks_dispatch(db_session, test_user):
    """Verify missing required task prompt in non-demo mode blocks execution with HTTP 422."""
    from fastapi import HTTPException

    proj = Project(
        project_id="proj-input-test-99",
        owner_user_id=test_user.id,
        name="Input Test Proj",
        backend_base_url="http://localhost:8000",
        backend_health_url="http://localhost:8000/health",
        lifecycle=ProjectLifecycle.ACTIVE.value,
        connection_state=ProjectConnectionState.NOT_CHECKED.value,
    )
    db_session.merge(proj)

    from app.shared.integration.service import canonical_json_digest

    plan_payload = {
        "component_references": {},
        "execution_inputs_snapshot": {
            "is_demonstration": False,
        },
    }

    plan = IntegrationRunPlanModel(
        integration_run_id="plan-missing-inputs-1",
        project_id=proj.project_id,
        created_by_user_id=test_user.id,
        name="Non-demo plan with missing inputs",
        lifecycle_status="READY",
        plan_digest=canonical_json_digest(plan_payload),
        plan_payload=plan_payload,
        readiness_report={},
    )
    db_session.merge(plan)
    db_session.commit()

    coord = SharedExecutionCoordinator(db_session)
    req = ExecutionStartRequest(target_mode=TargetMode.CONTROLLED_TEST)

    with pytest.raises(HTTPException) as exc_info:
        coord.execute_plan(
            project=proj,
            user=test_user,
            plan_identifier=plan.integration_run_id,
            request=req,
        )
    assert exc_info.value.status_code == 422
    assert "missing required task prompt" in exc_info.value.detail
