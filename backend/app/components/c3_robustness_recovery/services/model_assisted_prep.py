"""Model-assisted input preparation service for Component 3.

Provides bounded, user-scoped LLM assistance to draft structured recovery parameters
and fixture metadata from supplied task, tool, and capability context.
Treats missing references as unresolved and strictly preserves deterministic validation.
"""

import json
from typing import Any

from app.components.c3_robustness_recovery.contracts.generation import (
    ModelAssistedDraftRequest,
    ModelAssistedDraftResponse,
)
from app.components.c3_robustness_recovery.contracts.schemas import (
    RecoveryContract,
    TaskFixtureMetadata,
    TerminalOutcome,
)
from app.shared.llm.contracts import LLMGenerationRequest
from app.shared.llm.service import LLMProviderService

C3_DRAFT_SYSTEM_PROMPT = """You are a QA testing assistant for tool-using LLM applications.
Your job is to draft structured test inputs for robustness and recovery evaluation (Component 3).
Rules:
1. Base your proposal strictly on the supplied task, tool, fixture, and capability information.
2. If any tool, fixture, or external reference is missing or cannot be verified from the supplied context, list it explicitly in unresolved_references.
3. Do NOT invent interception hooks, fixture observations, runtime assertion facts, confirmed fault exposure, or recovery passes.
4. Permitted terminal outcome values are:
   - SUCCESS_CLEAN_RECOVERY
   - SUCCESS_DEGRADED_FALLBACK
   - GRACEFUL_ABORT_USER_NOTIFIED
   - FAIL_SAFE_STOP
   Never use recovery verdicts (like PASS_COMPLETED or PASS_GRACEFUL) as terminal outcomes.
5. Output MUST be valid JSON adhering to the specified schema:
{
  "task_fixture": {
    "task_id": "...",
    "task_version": "1.0.0",
    "fixture_id": "...",
    "fixture_version": "1.0.0",
    "domain": "ecommerce",
    "associated_tool_ids": ["..."],
    "associated_recovery_contract_ids": ["..."],
    "declared_reset_support": false,
    "reset_method": null,
    "declared_observation_support": true,
    "supported_observations": ["..."],
    "supports_committed_effect_observation": false,
    "supports_partial_effect_observation": false
  },
  "recovery_contract": {
    "contract_id": "...",
    "contract_version": "1.0.0",
    "permitted_terminal_outcomes": ["SUCCESS_CLEAN_RECOVERY", "SUCCESS_DEGRADED_FALLBACK"],
    "graceful_stopping_conditions": ["..."],
    "initial_invocation_counts_as_attempt": true,
    "max_task_attempts": 3,
    "max_retries": 2,
    "max_tool_calls_budget": 10,
    "max_total_timeout_ms": 30000,
    "required_state_assertions": ["..."],
    "allow_duplicate_side_effects": false,
    "allow_retry_on_unverified_commit": false,
    "require_truthful_completion_reporting": true
  },
  "unresolved_references": ["..."],
  "explanation": "Summary of proposed recovery configuration"
}
"""


async def prepare_draft_inputs(
    req: ModelAssistedDraftRequest,
    user_id: str | None = None,
) -> ModelAssistedDraftResponse:
    """Generate draft structured inputs using the user-selected LLM provider."""
    service = LLMProviderService.get_instance()

    # Do not invent default refund tools or default tasks when authoritative context is absent
    supplied_task_id = req.task_id or (
        req.existing_task_fixture.task_id if req.existing_task_fixture else None
    )
    supplied_tool_id = req.tool_id or (
        req.existing_adapter_manifest.tools[0].tool_id
        if req.existing_adapter_manifest and req.existing_adapter_manifest.tools
        else None
    )

    supplied_context: dict[str, Any] = {
        "project_id": req.project_id,
        "task_id": supplied_task_id,
        "tool_id": supplied_tool_id,
        "domain": req.domain,
        "instructions": req.instructions
        or "Draft recovery parameters for transient failures.",
    }
    if req.existing_task_fixture:
        supplied_context["existing_task_fixture"] = (
            req.existing_task_fixture.model_dump()
        )
    if req.existing_adapter_manifest:
        # Supply full relevant capability combinations rather than only tool names
        supplied_context["existing_adapter_manifest"] = {
            "adapter_id": req.existing_adapter_manifest.adapter_id,
            "adapter_version": req.existing_adapter_manifest.adapter_version,
            "tools": [
                {
                    "tool_id": t.tool_id,
                    "tool_version": t.tool_version,
                    "mutability": t.mutability.value
                    if hasattr(t.mutability, "value")
                    else str(t.mutability),
                }
                for t in req.existing_adapter_manifest.tools
            ],
            "supported_combinations": [
                {
                    "tool_id": c.tool_id,
                    "fault_family": c.fault_family.value
                    if hasattr(c.fault_family, "value")
                    else str(c.fault_family),
                    "effect_phase": c.effect_phase.value
                    if hasattr(c.effect_phase, "value")
                    else str(c.effect_phase),
                    "interception_hook": c.interception_hook.value
                    if hasattr(c.interception_hook, "value")
                    else str(c.interception_hook),
                    "min_occurrence": c.supported_occurrence_bounds.min_occurrence,
                    "max_occurrence": c.supported_occurrence_bounds.max_occurrence,
                    "allowed_release_rule_types": [
                        r.value if hasattr(r, "value") else str(r)
                        for r in c.allowed_release_rule_types
                    ],
                    "supported_payload_modes": c.supported_payload_modes,
                    "required_observation_capabilities": c.required_observation_capabilities,
                }
                for c in req.existing_adapter_manifest.supported_combinations
            ],
        }
    if req.existing_recovery_contract:
        supplied_context["existing_recovery_contract"] = (
            req.existing_recovery_contract.model_dump()
        )

    user_prompt = (
        f"Supplied Context:\n{json.dumps(supplied_context, indent=2)}\n\n"
        "Draft the structured task fixture and recovery contract JSON based solely on this context."
    )

    gen_req = LLMGenerationRequest(
        prompt=user_prompt,
        system_prompt=C3_DRAFT_SYSTEM_PROMPT,
        temperature=0.0,
        max_tokens=1500,
        response_schema={
            "type": "object",
            "properties": {
                "task_fixture": {"type": "object"},
                "recovery_contract": {"type": "object"},
                "unresolved_references": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "explanation": {"type": "string"},
            },
            "required": [
                "task_fixture",
                "recovery_contract",
                "unresolved_references",
                "explanation",
            ],
        },
        metadata={
            "operation": "c3_prepare_draft",
            "project_id": req.project_id,
        },
    )

    try:
        gen_result = await service.invoke_for_user(user_id=user_id, request=gen_req)
    except Exception as exc:  # noqa: BLE001
        return ModelAssistedDraftResponse(
            status="FAILED",
            explanation=f"Model assistance invocation failed: {exc}",
            unresolved_references=["provider_error"],
            provider_metadata={"error": str(exc)},
        )

    provider_metadata: dict[str, Any] = {
        "provider": gen_result.provider.value
        if hasattr(gen_result.provider, "value")
        else str(gen_result.provider),
        "requested_model": gen_result.requested_model,
        "actual_model": gen_result.actual_model,
        "duration_ms": gen_result.duration_ms,
        "prompt_template_version": "v1.0.0",
        "usage": gen_result.usage.model_dump(),
    }

    if not gen_result.is_success:
        return ModelAssistedDraftResponse(
            status="FAILED",
            explanation=f"Model assistance invocation failed: {gen_result.error_message or 'Unknown provider error'}",
            unresolved_references=["provider_error"],
            provider_metadata=provider_metadata,
        )

    try:
        if gen_result.structured_data and isinstance(gen_result.structured_data, dict):
            data = gen_result.structured_data
        else:
            raw = (gen_result.raw_text or "").strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw = "\n".join(lines).strip()
            data = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        return ModelAssistedDraftResponse(
            status="FAILED",
            explanation=f"Failed to parse model output as JSON: {exc}",
            unresolved_references=["malformed_model_output"],
            provider_metadata=provider_metadata,
        )

    unresolved: list[str] = list(data.get("unresolved_references", []))
    explanation: str = data.get("explanation", "Model-assisted draft prepared.")

    # Validate and build TaskFixtureMetadata
    draft_tf: TaskFixtureMetadata | None = None
    tf_data = data.get("task_fixture")
    if tf_data and isinstance(tf_data, dict):
        try:
            # Preserve authoritative fixture metadata if supplied
            if req.existing_task_fixture:
                auth_tf = req.existing_task_fixture
                # Detect and flag model altering authoritative fixture ID or version
                if "fixture_id" in tf_data and tf_data["fixture_id"] != auth_tf.fixture_id:
                    unresolved.append(
                        f"unresolved_fixture_reference: model attempted to replace authoritative fixture_id '{auth_tf.fixture_id}' with '{tf_data['fixture_id']}'"
                    )
                tf_data["fixture_id"] = auth_tf.fixture_id
                tf_data["fixture_version"] = auth_tf.fixture_version
                tf_data["task_id"] = auth_tf.task_id
                tf_data["task_version"] = auth_tf.task_version
                tf_data["domain"] = auth_tf.domain
                if "associated_tool_ids" not in tf_data or not tf_data["associated_tool_ids"]:
                    tf_data["associated_tool_ids"] = list(auth_tf.associated_tool_ids)
                if "associated_recovery_contract_ids" not in tf_data or not tf_data["associated_recovery_contract_ids"]:
                    tf_data["associated_recovery_contract_ids"] = list(auth_tf.associated_recovery_contract_ids)

                # Check reset facilities against authoritative fixture
                if not auth_tf.declared_reset_support and tf_data.get("declared_reset_support"):
                    unresolved.append(
                        "unresolved_reset_support: model invented declared_reset_support not supported by authoritative fixture"
                    )
                    tf_data["declared_reset_support"] = False
                    tf_data["reset_method"] = None
                elif auth_tf.declared_reset_support:
                    tf_data["declared_reset_support"] = True
                    tf_data["reset_method"] = auth_tf.reset_method

                # Check observation support against authoritative fixture
                if not auth_tf.declared_observation_support and tf_data.get("declared_observation_support"):
                    unresolved.append(
                        "unresolved_observation_support: model invented declared_observation_support not supported by authoritative fixture"
                    )
                    tf_data["declared_observation_support"] = False
                elif auth_tf.declared_observation_support:
                    tf_data["declared_observation_support"] = True

                # Check observation capabilities
                auth_obs = set(auth_tf.supported_observations)
                for obs in tf_data.get("supported_observations", []):
                    if obs not in auth_obs:
                        unresolved.append(
                            f"unresolved_observation: '{obs}' not supported by authoritative fixture"
                        )

                # Check effect observation flags
                if not auth_tf.supports_committed_effect_observation and tf_data.get("supports_committed_effect_observation"):
                    unresolved.append(
                        "unresolved_capability: model claimed supports_committed_effect_observation not supported by authoritative fixture"
                    )
                    tf_data["supports_committed_effect_observation"] = False
                if not auth_tf.supports_partial_effect_observation and tf_data.get("supports_partial_effect_observation"):
                    unresolved.append(
                        "unresolved_capability: model claimed supports_partial_effect_observation not supported by authoritative fixture"
                    )
                    tf_data["supports_partial_effect_observation"] = False
            else:
                # No authoritative fixture: missing facilities must NOT be filled with generic defaults
                fixture_id_val = tf_data.get("fixture_id")
                unresolved.append(
                    f"unresolved_fixture_reference: no authoritative fixture metadata declared; model-supplied fixture_id '{fixture_id_val or 'omitted'}' cannot be verified"
                )
                if not fixture_id_val:
                    tf_data["fixture_id"] = "draft-fixture-unverified"
                tf_data.setdefault("domain", req.domain)
                tf_data.setdefault("task_id", req.task_id or "task-draft-unverified")
                tf_data.setdefault("task_version", req.task_version or "1.0.0")
                tf_data.setdefault("fixture_version", "1.0.0")

                # If model invented reset facilities, flag as unresolved
                if tf_data.get("declared_reset_support") or tf_data.get("reset_method"):
                    unresolved.append(
                        "unresolved_reset_support: reset facility cannot be verified without declared authoritative fixture metadata"
                    )
                    tf_data["declared_reset_support"] = False
                    tf_data["reset_method"] = None

                # If model invented observation support, flag as unresolved
                if tf_data.get("declared_observation_support") or tf_data.get("supported_observations"):
                    unresolved.append(
                        "unresolved_observation_support: observation support cannot be verified without declared authoritative fixture metadata"
                    )
                    tf_data["declared_observation_support"] = False
                    tf_data["supported_observations"] = []

                # If model invented effect observation support, flag as unresolved
                if tf_data.get("supports_committed_effect_observation") or tf_data.get("supports_partial_effect_observation"):
                    unresolved.append(
                        "unresolved_capability: effect observation flags cannot be verified without declared authoritative fixture metadata"
                    )
                    tf_data["supports_committed_effect_observation"] = False
                    tf_data["supports_partial_effect_observation"] = False

            draft_tf = TaskFixtureMetadata.model_validate(tf_data)
        except Exception as e:  # noqa: BLE001
            unresolved.append(f"task_fixture_validation_error: {e}")

    # Validate and build RecoveryContract
    draft_rc: RecoveryContract | None = None
    rc_data = data.get("recovery_contract")
    if rc_data and isinstance(rc_data, dict):
        try:
            rc_data.setdefault("contract_id", "contract-draft-001")
            rc_data.setdefault("contract_version", "1.0.0")
            if req.existing_recovery_contract:
                auth_rc = req.existing_recovery_contract
                rc_data.setdefault("required_state_assertions", list(auth_rc.required_state_assertions))
                rc_data.setdefault("max_tool_calls_budget", auth_rc.max_tool_calls_budget)
                rc_data.setdefault("max_total_timeout_ms", auth_rc.max_total_timeout_ms)
            else:
                # Do not invent default required state assertions or pretend assertions exist without authoritative contract
                if rc_data.get("required_state_assertions"):
                    for assertion in rc_data["required_state_assertions"]:
                        unresolved.append(
                            f"unresolved_assertion_reference: state assertion '{assertion}' cannot be verified without declared authoritative recovery contract"
                        )
                else:
                    unresolved.append(
                        "missing_required_state_assertions: recovery contract requires declared authoritative state assertions"
                    )

            # Validate attempt and retry consistency without silent mutation
            attempts = rc_data.get("max_task_attempts")
            retries = rc_data.get("max_retries")
            init_counts = rc_data.get("initial_invocation_counts_as_attempt", True)
            if attempts is not None and retries is not None:
                expected_retries = attempts - 1 if init_counts else attempts
                if retries != expected_retries:
                    unresolved.append(
                        f"budget_inconsistency: proposed max_retries ({retries}) does not match max_task_attempts ({attempts}) when initial_invocation_counts_as_attempt={init_counts} (expected {expected_retries})"
                    )

            # Ensure permitted terminal outcomes adhere to TerminalOutcome enum
            if "permitted_terminal_outcomes" in rc_data and isinstance(
                rc_data["permitted_terminal_outcomes"], list
            ):
                valid_outcomes = []
                for o in rc_data["permitted_terminal_outcomes"]:
                    try:
                        valid_outcomes.append(TerminalOutcome(o))
                    except ValueError:
                        unresolved.append(
                            f"invalid_terminal_outcome: '{o}' is not a valid TerminalOutcome enum value"
                        )
                rc_data["permitted_terminal_outcomes"] = valid_outcomes

            # Ground required state assertions against supplied contract if present
            if req.existing_recovery_contract and "required_state_assertions" in rc_data:
                auth_assertions = set(req.existing_recovery_contract.required_state_assertions)
                for assertion in rc_data.get("required_state_assertions", []):
                    if assertion not in auth_assertions:
                        unresolved.append(
                            f"unresolved_assertion_reference: '{assertion}' not found in declared assertion references"
                        )

            draft_rc = RecoveryContract.model_validate(rc_data)
        except Exception as e:  # noqa: BLE001
            unresolved.append(f"recovery_contract_validation_error: {e}")

    # Cross check tools: if task references tools not declared in adapter manifest, flag unresolved
    if draft_tf:
        if req.existing_adapter_manifest:
            declared_tool_ids = {t.tool_id for t in req.existing_adapter_manifest.tools}
            for tid in draft_tf.associated_tool_ids:
                if tid not in declared_tool_ids:
                    unresolved.append(
                        f"unresolved_tool_reference: '{tid}' not found in adapter manifest"
                    )
        else:
            unresolved.append(
                "unresolved_tool_reference: no authoritative adapter manifest declared to verify tool associations"
            )

    has_authoritative_context = (
        req.existing_task_fixture is not None
        and req.existing_adapter_manifest is not None
        and req.existing_recovery_contract is not None
    )

    status = (
        "SUCCESS"
        if (not unresolved and draft_tf is not None and draft_rc is not None and has_authoritative_context)
        else (
            "UNRESOLVED_REFERENCES"
            if (draft_tf is not None or draft_rc is not None)
            else "FAILED"
        )
    )

    return ModelAssistedDraftResponse(
        status=status,
        draft_task_fixture=draft_tf,
        draft_adapter_manifest=req.existing_adapter_manifest,
        draft_recovery_contract=draft_rc,
        unresolved_references=unresolved,
        explanation=explanation,
        provider_metadata=provider_metadata,
    )
