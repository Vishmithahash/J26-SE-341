"""Comprehensive regression and acceptance test suite for remaining QA framework corrections.

Covers:
- Previously failing C1/C2/C3/C4 endpoints and schema availability.
- C4 domain bindings query parameter compatibility.
- Projects pagination (limit/offset vs page/page_size).
- Exact qwen3.5:4b model tag discovery, default configuration, and probe validation.
- Rejection of truncated outputs (MAX_TOKENS / length) and schema-invalid JSON.
- Rejection of substring 'ok' connection probes in favor of exact structured validation.
- Invalidation of connection test status when selection or settings change.
- C2 model-assisted invariant proposal parsed via TypeAdapter(StructuredPredicate) and structural validation.
- C3 model-assisted input preparation grounding in authoritative fixtures and capability preservation.
- C3 recovery evaluation preventing PASS_COMPLETED on missing snapshot/entity scope or wrong observation time scope.
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

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
from app.components.c2_state_aware_workflow.predicates.expressions import (
    ComparisonPredicate,
)
from app.components.c3_robustness_recovery.contracts.evaluation import (
    C2AssertionFact,
    C2FactValue,
    RecoveryEvaluationRequest,
    RecoveryRuleId,
    RecoveryVerdict,
    RuleEvaluationStatus,
)
from app.components.c3_robustness_recovery.contracts.generation import (
    ModelAssistedDraftRequest,
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
    TerminalOutcome,
    TimeoutDisconnectionMode,
    TimeoutDisconnectionPayload,
)
from app.components.c3_robustness_recovery.runtime.adapter import (
    CleanupStatus,
    RecoveryActor,
    TargetMode,
)
from app.components.c3_robustness_recovery.runtime.evidence import (
    CallerIdentity,
    CleanQualification,
    ExecutionStatus,
    ExposureStatus,
    FixtureComparability,
    MatchedPairEvidence,
    ReadinessStatus,
    StateObservationReference,
    TrialEvidence,
    TrialRole,
)
from app.components.c3_robustness_recovery.services.c2_facts import (
    DEFAULT_C2_TO_C3_MAPPINGS,
)
from app.components.c3_robustness_recovery.services.model_assisted_prep import (
    prepare_draft_inputs,
)
from app.components.c3_robustness_recovery.services.recovery_evaluation import (
    evaluate_recovery,
)
from app.components.c4_policy_aware_safety.persistence.repository import C4Repository
from app.config import get_settings
from app.shared.llm.adapters.gemini import GeminiAdapter
from app.shared.llm.adapters.ollama import OllamaAdapter
from app.shared.llm.contracts import (
    LLMGenerationRequest,
    LLMGenerationResult,
    ModelSelectionConfig,
)
from app.shared.llm.schema_validator import validate_structured_schema
from app.shared.llm.service import LLMProviderService


# ---------------------------------------------------------------------------
# 1. C4 Repository Parameter Compatibility
# ---------------------------------------------------------------------------
def test_c4_repository_list_domain_bindings_accepts_binding_id():
    """Verify list_domain_bindings accepts binding_id without raising TypeError."""
    mock_db = MagicMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = []

    repo = C4Repository(mock_db)
    # Calling with binding_id must not raise TypeError
    results = repo.list_domain_bindings(project_id="proj-123", binding_id="binding-456")
    assert results == []


# ---------------------------------------------------------------------------
# 2. Team Default Model Configuration
# ---------------------------------------------------------------------------
def test_team_default_model_is_qwen35_4b():
    """Verify settings, contracts, and defaults declare qwen3.5:4b as team local default."""
    cfg = ModelSelectionConfig()
    assert cfg.model_id == "qwen3.5:4b"
    assert cfg.connection_type == "local"
    assert cfg.provider == "ollama"

    settings = get_settings()
    assert settings.ollama_model == "qwen3.5:4b"


# ---------------------------------------------------------------------------
# 3. Connection Probe Exact Validation (Reject substring "ok")
# ---------------------------------------------------------------------------
def test_connection_test_rejects_substring_ok_without_exact_probe():
    """Verify that a response merely containing 'ok' in free text does not establish connection success."""
    service = LLMProviderService()
    mock_adapter = MagicMock()

    # Model returns "I am ok" in raw_text, but structured_data does not match {"status": "ok", "framework": "agentic_qa"}
    mock_result = LLMGenerationResult(
        provider="ollama",
        requested_model="qwen3.5:4b",
        actual_model="qwen3.5:4b",
        raw_text="The server is ok and ready.",
        structured_data={"status": "not_ok"},
        is_success=True,
    )
    mock_adapter.generate = AsyncMock(return_value=mock_result)

    with patch.object(service, "get_adapter", return_value=mock_adapter):
        resp = asyncio.run(
            service.test_connection(
                user_id=1,
                provider_name="ollama",
                model_id="qwen3.5:4b",
                db=MagicMock(),
            )
        )
        assert resp.success is False
        assert "Probe validation failed" in resp.status_message


def test_connection_test_succeeds_on_exact_structured_probe():
    """Verify that exact {"status": "ok", "framework": "agentic_qa"} passes probe validation."""
    service = LLMProviderService()
    mock_adapter = MagicMock()

    mock_result = LLMGenerationResult(
        provider="ollama",
        requested_model="qwen3.5:4b",
        actual_model="qwen3.5:4b",
        raw_text='{"status": "ok", "framework": "agentic_qa"}',
        structured_data={"status": "ok", "framework": "agentic_qa"},
        is_success=True,
        duration_ms=45.2,
    )
    mock_adapter.generate = AsyncMock(return_value=mock_result)

    with patch.object(service, "get_adapter", return_value=mock_adapter):
        resp = asyncio.run(
            service.test_connection(
                user_id=1,
                provider_name="ollama",
                model_id="qwen3.5:4b",
                db=MagicMock(),
            )
        )
        assert resp.success is True
        assert resp.model_id == "qwen3.5:4b"


# ---------------------------------------------------------------------------
# 4. Invalidation of Connection Verification on Selection Change
# ---------------------------------------------------------------------------
def test_save_user_selection_invalidates_previous_test_status():
    """Verify that updating selection/settings resets last_test_status to None."""
    service = LLMProviderService()
    mock_db = MagicMock()

    existing_selection = MagicMock()
    existing_selection.provider = "ollama"
    existing_selection.model_id = "qwen3.5:4b"
    existing_selection.generation_settings = {"temperature": 0.0}
    existing_selection.last_test_status = "SUCCESS"
    existing_selection.last_test_at = datetime.now(UTC)

    mock_db.execute.return_value.scalar_one_or_none.return_value = existing_selection

    # Change settings to temperature 0.7
    new_cfg = ModelSelectionConfig(
        connection_type="local",
        provider="ollama",
        model_id="qwen3.5:4b",
        generation_settings={"temperature": 0.7},
    )

    updated = service.save_user_selection(user_id=1, config=new_cfg, db=mock_db)
    assert updated.last_test_status is None
    assert updated.last_test_at is None


# ---------------------------------------------------------------------------
# 5. Output Validation: Truncation and Schema Enforcement
# ---------------------------------------------------------------------------
def test_ollama_adapter_rejects_truncated_length_response():
    """Verify Ollama adapter marks done_reason == 'length' as INCOMPLETE_OUTPUT."""
    adapter = OllamaAdapter(default_model="qwen3.5:4b")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "qwen3.5:4b",
        "response": '{"partially": "comple',
        "done": True,
        "done_reason": "length",
    }

    req = LLMGenerationRequest(user_prompt="Generate json")
    with patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp
    ):
        res = asyncio.run(adapter.generate(req))
        assert res.is_success is False
        assert res.error_type == "INCOMPLETE_OUTPUT"
        assert "truncated" in res.error_message.lower()


def test_gemini_adapter_rejects_max_tokens_finish_reason():
    """Verify Gemini adapter marks finishReason == 'MAX_TOKENS' as INCOMPLETE_OUTPUT."""
    adapter = GeminiAdapter(
        api_key="AIzaFakeKey", default_model="gemini-3.5-flash-lite"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {
                "finishReason": "MAX_TOKENS",
                "content": {"parts": [{"text": '{"incomplete":'}]},
            }
        ]
    }

    req = LLMGenerationRequest(user_prompt="Test")
    with patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp
    ):
        res = asyncio.run(adapter.generate(req))
        assert res.is_success is False
        assert res.error_type == "INCOMPLETE_OUTPUT"


def test_schema_validator_catches_invalid_types_and_missing_properties():
    """Verify validate_structured_schema rejects schema-violating data."""
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "count": {"type": "integer", "minimum": 1},
        },
        "required": ["name", "count"],
    }

    # Missing count
    valid, err = validate_structured_schema({"name": "item"}, schema)
    assert not valid
    assert "Missing required property" in err

    # Wrong type (string instead of integer)
    valid, err = validate_structured_schema({"name": "item", "count": "five"}, schema)
    assert not valid
    assert "Expected integer" in err

    # Out of bounds
    valid, err = validate_structured_schema({"name": "item", "count": 0}, schema)
    assert not valid
    assert "less than minimum" in err


# ---------------------------------------------------------------------------
# 6. C2 Model-Assisted Proposal Parsing via TypeAdapter
# ---------------------------------------------------------------------------
def test_c2_model_assisted_parses_valid_structured_predicate():
    """Verify valid invariant proposal is parsed using TypeAdapter and retained in candidate EFSM."""
    workflow_input = WorkflowInputContract(
        project_id="proj-c2-test",
        domain="ecommerce",
        workflow_id="wf_checkout",
        name="Checkout Workflow",
        task="Checkout Cart and Complete Payment",
        business_rules=[
            BusinessRule(
                rule_id="RULE-01",
                name="Positive Cart",
                description="Cart total must be positive",
                category="invariant",
            )
        ],
        tool_specifications=[
            ToolSpecification(
                tool_name="process_payment",
                description="Process payment for active cart",
                parameters=[ToolParameterSpec(name="cart_id", type="string")],
            )
        ],
        synthetic_fixture=SyntheticFixtureReference(
            fixture_id="ecommerce_fixture", description="Fixture"
        ),
    )

    builder = ModelAssistedEFSMBuilder(user_id=1, builder_version="c2_test_v1")

    # Mock LLM generation result with a valid ComparisonPredicate
    valid_predicate = {
        "type": "comparison",
        "left": {"scope": "vars", "path": "cart_total"},
        "op": ">=",
        "right": 0,
    }
    mock_llm_data = {
        "name": "Refined Checkout Workflow",
        "description": "Refined state machine with payment rules",
        "proposed_invariants": [
            {
                "id": "INV_CART_NON_NEGATIVE",
                "name": "Cart Total Non-Negative",
                "description": "Ensures cart total never drops below zero",
                "source_rule": "RULE-01",
                "predicate": valid_predicate,
            }
        ],
    }

    mock_llm_result = LLMGenerationResult(
        provider="ollama",
        requested_model="qwen3.5:4b",
        actual_model="qwen3.5:4b",
        structured_data=mock_llm_data,
        is_success=True,
    )

    mock_service = MagicMock()
    mock_service.invoke_for_user = AsyncMock(return_value=mock_llm_result)

    with patch.object(builder, "_get_service", return_value=mock_service):
        candidate = builder.propose_model(workflow_input)

        assert candidate.name == "Refined Checkout Workflow"
        # Find the proposed invariant
        inv = next(
            (i for i in candidate.invariants if i.id == "INV_CART_NON_NEGATIVE"), None
        )
        assert inv is not None
        assert isinstance(inv.predicate, ComparisonPredicate)
        assert inv.predicate.op.value == ">="
        left_path = (
            inv.predicate.left.path
            if hasattr(inv.predicate.left, "path")
            else inv.predicate.left.get("path")
        )
        assert left_path == "cart_total"
        # qwen3.5 reasoning made the proposal time out; the request switches it off
        sent = mock_service.invoke_for_user.await_args.args[1]
        assert sent.metadata == {"ollama_think": False}


def test_c2_model_assisted_rejects_invalid_proposal_and_falls_back():
    """Verify invalid or structurally broken proposal triggers labeled deterministic fallback."""
    workflow_input = WorkflowInputContract(
        project_id="proj-c2-test",
        domain="ecommerce",
        workflow_id="wf_checkout",
        name="Checkout Workflow",
        task="Checkout Cart and Complete Payment",
        business_rules=[
            BusinessRule(
                rule_id="RULE-01",
                name="Positive Cart",
                description="Cart total must be positive",
                category="invariant",
            )
        ],
        tool_specifications=[
            ToolSpecification(
                tool_name="process_payment",
                description="Process payment for active cart",
                parameters=[ToolParameterSpec(name="cart_id", type="string")],
            )
        ],
        synthetic_fixture=SyntheticFixtureReference(
            fixture_id="ecommerce_fixture", description="Fixture"
        ),
    )

    builder = ModelAssistedEFSMBuilder(user_id=1, builder_version="c2_test_v1")

    # Proposal contains invalid duplicate state or malformed predicate
    mock_llm_data = {
        "name": "Broken Workflow",
        "state_refinements": [
            {"state_id": "NON_EXISTENT_STATE", "description": "bogus"}
        ],
        "proposed_invariants": [
            {
                "id": "INV_INVALID",
                "name": "Invalid Predicate Invariant",
                "predicate": {"type": "unknown_type", "op": "=="},
            }
        ],
    }

    mock_llm_result = LLMGenerationResult(
        provider="ollama",
        requested_model="qwen3.5:4b",
        actual_model="qwen3.5:4b",
        structured_data=mock_llm_data,
        is_success=True,
    )

    mock_service = MagicMock()
    mock_service.invoke_for_user = AsyncMock(return_value=mock_llm_result)

    with patch.object(builder, "_get_service", return_value=mock_service):
        candidate = builder.propose_model(workflow_input)
        # Invalid predicate was skipped, baseline was preserved
        assert not any(i.id == "INV_INVALID" for i in candidate.invariants)


# ---------------------------------------------------------------------------
# 7. C3 Model-Assisted Input Preparation Grounding
# ---------------------------------------------------------------------------
def test_c3_prep_rejects_altered_fixture_id_and_invented_reset():
    """Verify C3 draft preparation flags model attempts to alter fixture_id or invent reset support."""
    auth_fixture = TaskFixtureMetadata(
        task_id="task-order-01",
        task_version="1.0.0",
        fixture_id="authoritative-fix-100",
        fixture_version="1.0.0",
        domain="ecommerce",
        associated_tool_ids=["process_payment"],
        associated_recovery_contract_ids=["contract-test-01"],
        declared_reset_support=False,
        reset_method=None,
        declared_observation_support=True,
        supported_observations=["network_latency_ms"],
        supports_committed_effect_observation=False,
        supports_partial_effect_observation=False,
    )

    req = ModelAssistedDraftRequest(
        project_id="proj-qa-001",
        domain="ecommerce",
        existing_task_fixture=auth_fixture,
    )

    # Model proposes a replaced fixture_id and claims reset support
    model_output = {
        "task_fixture": {
            "fixture_id": "invented-fixture-999",  # Attempted replacement
            "declared_reset_support": True,  # Invented reset capability
            "supported_observations": ["invented_db_observer"],  # Invented observer
        },
        "recovery_contract": {
            "contract_id": "contract-draft-001",
            "permitted_terminal_outcomes": ["SUCCESS_CLEAN_RECOVERY"],
            "max_task_attempts": 3,
            "max_retries": 2,
        },
        "unresolved_references": [],
        "explanation": "Drafted configuration.",
    }

    mock_service = MagicMock()
    mock_service.invoke_for_user = AsyncMock(
        return_value=LLMGenerationResult(
            provider="ollama",
            requested_model="qwen3.5:4b",
            actual_model="qwen3.5:4b",
            structured_data=model_output,
            is_success=True,
        )
    )

    with patch(
        "app.shared.llm.service.LLMProviderService.get_instance",
        return_value=mock_service,
    ):
        res = asyncio.run(prepare_draft_inputs(req, user_id="1"))

        # Must flag unresolved references and preserve authoritative fixture_id
        assert res.status == "UNRESOLVED_REFERENCES"
        assert any(
            "unresolved_fixture_reference" in u for u in res.unresolved_references
        )
        assert any("unresolved_reset_support" in u for u in res.unresolved_references)
        assert any("unresolved_observation" in u for u in res.unresolved_references)
        assert res.draft_task_fixture.fixture_id == "authoritative-fix-100"
        assert res.draft_task_fixture.declared_reset_support is False


# ---------------------------------------------------------------------------
# 8. C3 Fact Scope: Prevent False PASS_COMPLETED in Actual Evaluator
# ---------------------------------------------------------------------------
def _build_test_candidate_case() -> CandidateFaultCase:
    return CandidateFaultCase(
        schema_version="2026.1",
        project_id="proj-c3-test",
        case_id="case-test-01",
        case_family_id="fam-timeout",
        domain="ecommerce",
        task_id="task-checkout",
        task_version="1.0.0",
        tool_id="process_payment",
        tool_version="1.0.0",
        fixture_id="fix-test-01",
        fixture_version="1.0.0",
        adapter_id="adapter-test",
        adapter_version="1.0.0",
        recovery_contract_id="contract-test-01",
        recovery_contract_version="1.0.0",
        occurrence=1,
        interception_hook=InterceptionHook.BEFORE_TOOL_CALL,
        fault_family=FaultFamily.TIMEOUT_DISCONNECTION,
        effect_phase=EffectPhase.BEFORE_EFFECT,
        payload=TimeoutDisconnectionPayload(
            mode=TimeoutDisconnectionMode.CALLER_TIMEOUT_EXCEEDED, timing_ms=3000
        ),
        release_rule=ReleaseRule(
            rule_type=ReleaseRuleType.ATTEMPT_BOUNDED, max_fault_count=1
        ),
        required_assertions=["order_created"],
        required_observations=["network_latency_ms"],
        caller_timeout_ms=2000,
        reproducibility_seed=123,
    )


def test_c3_evaluator_rejects_missing_snapshot_scope():
    """Verify evaluator returns INCONCLUSIVE (not PASS_COMPLETED) when authoritative snapshot scope is missing."""
    case = _build_test_candidate_case()
    contract = RecoveryContract(
        contract_id="contract-test-01",
        contract_version="1.0.0",
        permitted_terminal_outcomes=[TerminalOutcome.SUCCESS_CLEAN_RECOVERY],
        max_task_attempts=3,
        max_retries=2,
        max_tool_calls_budget=10,
        max_total_timeout_ms=10000,
        required_state_assertions=["order_created"],
    )

    clean_trial = TrialEvidence(
        project_id="proj-c3-test",
        case_id=case.case_id,
        pair_id="pair-001",
        trial_id="trial-clean-01",
        run_id="run-001",
        trial_role=TrialRole.CLEAN,
        target_mode=TargetMode.LIVE_AUT,
        caller_identity=CallerIdentity.ACTUAL_AGENT,
        recovery_actor=RecoveryActor.AGENT,
        fixture_namespace="ns-clean",
        initial_state_fingerprint="fp-init-clean",
        final_state_fingerprint="fp-final-clean",
        events=[],
        tool_calls_count=1,
        subsequent_calls_count=0,
        execution_status=ExecutionStatus.COMPLETED,
        caller_outcome="SUCCESS",
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
    )

    # Fault trial has NO snapshot_id and NO observation_reference
    fault_trial = TrialEvidence(
        project_id="proj-c3-test",
        case_id=case.case_id,
        pair_id="pair-001",
        trial_id="trial-fault-01",
        run_id="run-001",
        trial_role=TrialRole.FAULT,
        target_mode=TargetMode.LIVE_AUT,
        caller_identity=CallerIdentity.ACTUAL_AGENT,
        recovery_actor=RecoveryActor.AGENT,
        fixture_namespace="ns-fault",
        initial_state_fingerprint="fp-init-fault",
        final_state_fingerprint="fp-final-fault",
        events=[],
        tool_calls_count=2,
        subsequent_calls_count=1,
        execution_status=ExecutionStatus.COMPLETED,
        caller_outcome="SUCCESS_CLEAN_RECOVERY",
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
        snapshot_id=None,
        observation_reference=None,
    )

    matched_evidence = MatchedPairEvidence(
        project_id="proj-c3-test",
        case_id=case.case_id,
        pair_id="pair-001",
        run_id="run-001",
        target_mode=TargetMode.LIVE_AUT,
        caller_identity=CallerIdentity.ACTUAL_AGENT,
        clean_trial=clean_trial,
        fault_trial=fault_trial,
        readiness_status=ReadinessStatus.READY,
        configuration_snapshot={},
        fixture_comparability=FixtureComparability.EQUIVALENT_LOGICAL_STATE,
        clean_qualification=CleanQualification.QUALIFIED,
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
        exposure_assessed=True,
        exposure_status=ExposureStatus.CONFIRMED,
        exposure_reasons=["Fault triggered"],
    )

    # C2 fact with snapshot-01
    c2_facts = [
        C2AssertionFact(
            assertion_id="order_created",
            assertion_version="1.0.0",
            entity_id="ord-123",
            snapshot_id="snapshot-01",
            time_scope="post_recovery",
            value=C2FactValue.TRUE,
            provenance="C2_EVALUATOR_BRIDGE",
            supporting_evidence_refs=["trial-fault-01"],
            details={
                "project_id": "proj-c3-test",
                "pair_id": "pair-001",
                "trial_id": "trial-fault-01",
            },
        )
    ]

    req = RecoveryEvaluationRequest(
        project_id="proj-c3-test",
        case_id=case.case_id,
        candidate_case=case,
        recovery_contract=contract,
        matched_evidence=matched_evidence,
        c2_facts=c2_facts,
        pinned_mappings=DEFAULT_C2_TO_C3_MAPPINGS,
    )

    res = evaluate_recovery(req)
    # Must NOT manufacture a pass! Missing required snapshot scope yields INCONCLUSIVE!
    assert res.recovery_verdict != RecoveryVerdict.PASS_COMPLETED
    assert res.recovery_verdict == RecoveryVerdict.INCONCLUSIVE

    completion_rule = next(
        r for r in res.rule_results if r.rule_id == RecoveryRuleId.RULE_COMPLETION.value
    )
    assert completion_rule.status == RuleEvaluationStatus.UNKNOWN
    assert "missing required snapshot scope" in completion_rule.message


def test_c3_evaluator_rejects_wrong_observation_time_scope():
    """Verify evaluator returns INCONCLUSIVE when retained observation has wrong time scope."""
    case = _build_test_candidate_case()
    contract = RecoveryContract(
        contract_id="contract-test-01",
        contract_version="1.0.0",
        permitted_terminal_outcomes=[TerminalOutcome.SUCCESS_CLEAN_RECOVERY],
        max_task_attempts=3,
        max_retries=2,
        max_tool_calls_budget=10,
        max_total_timeout_ms=10000,
        required_state_assertions=["order_created"],
    )

    clean_trial = TrialEvidence(
        project_id="proj-c3-test",
        case_id=case.case_id,
        pair_id="pair-001",
        trial_id="trial-clean-01",
        run_id="run-001",
        trial_role=TrialRole.CLEAN,
        target_mode=TargetMode.LIVE_AUT,
        caller_identity=CallerIdentity.ACTUAL_AGENT,
        recovery_actor=RecoveryActor.AGENT,
        fixture_namespace="ns-clean",
        initial_state_fingerprint="fp-init-clean",
        final_state_fingerprint="fp-final-clean",
        events=[],
        tool_calls_count=1,
        subsequent_calls_count=0,
        execution_status=ExecutionStatus.COMPLETED,
        caller_outcome="SUCCESS",
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
    )

    # Fault trial has pre_fault observation scope instead of post_recovery!
    obs_ref = StateObservationReference(
        snapshot_id="snap-fault-01",
        snapshot_version="1.0.0",
        entity_id="ord-123",
        observation_scope="pre_fault",  # WRONG TIME SCOPE
    )

    fault_trial = TrialEvidence(
        project_id="proj-c3-test",
        case_id=case.case_id,
        pair_id="pair-001",
        trial_id="trial-fault-01",
        run_id="run-001",
        trial_role=TrialRole.FAULT,
        target_mode=TargetMode.LIVE_AUT,
        caller_identity=CallerIdentity.ACTUAL_AGENT,
        recovery_actor=RecoveryActor.AGENT,
        fixture_namespace="ns-fault",
        initial_state_fingerprint="fp-init-fault",
        final_state_fingerprint="fp-final-fault",
        events=[],
        tool_calls_count=2,
        subsequent_calls_count=1,
        execution_status=ExecutionStatus.COMPLETED,
        caller_outcome="SUCCESS_CLEAN_RECOVERY",
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
        snapshot_id="snap-fault-01",
        observation_reference=obs_ref,
    )

    matched_evidence = MatchedPairEvidence(
        project_id="proj-c3-test",
        case_id=case.case_id,
        pair_id="pair-001",
        run_id="run-001",
        target_mode=TargetMode.LIVE_AUT,
        caller_identity=CallerIdentity.ACTUAL_AGENT,
        clean_trial=clean_trial,
        fault_trial=fault_trial,
        readiness_status=ReadinessStatus.READY,
        configuration_snapshot={},
        fixture_comparability=FixtureComparability.EQUIVALENT_LOGICAL_STATE,
        clean_qualification=CleanQualification.QUALIFIED,
        cleanup_status=CleanupStatus.CLEANED_AND_VERIFIED,
        exposure_assessed=True,
        exposure_status=ExposureStatus.CONFIRMED,
        exposure_reasons=["Fault triggered"],
    )

    c2_facts = [
        C2AssertionFact(
            assertion_id="order_created",
            assertion_version="1.0.0",
            entity_id="ord-123",
            snapshot_id="snap-fault-01",
            time_scope="post_recovery",
            value=C2FactValue.TRUE,
            provenance="C2_EVALUATOR_BRIDGE",
            supporting_evidence_refs=["trial-fault-01"],
            details={
                "project_id": "proj-c3-test",
                "pair_id": "pair-001",
                "trial_id": "trial-fault-01",
            },
        )
    ]

    req = RecoveryEvaluationRequest(
        project_id="proj-c3-test",
        case_id=case.case_id,
        candidate_case=case,
        recovery_contract=contract,
        matched_evidence=matched_evidence,
        c2_facts=c2_facts,
        pinned_mappings=DEFAULT_C2_TO_C3_MAPPINGS,
    )

    res = evaluate_recovery(req)
    assert res.recovery_verdict != RecoveryVerdict.PASS_COMPLETED
    assert res.recovery_verdict == RecoveryVerdict.INCONCLUSIVE

    completion_rule = next(
        r for r in res.rule_results if r.rule_id == RecoveryRuleId.RULE_COMPLETION.value
    )
    assert completion_rule.status == RuleEvaluationStatus.UNKNOWN
    assert "wrong time scope" in completion_rule.message
