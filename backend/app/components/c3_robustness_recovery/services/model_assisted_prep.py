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
4. Output MUST be valid JSON adhering to the specified schema:
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
    "permitted_terminal_outcomes": ["PASS_COMPLETED", "PASS_GRACEFUL"],
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

    supplied_context = {
        "project_id": req.project_id,
        "task_id": req.task_id or (req.existing_task_fixture.task_id if req.existing_task_fixture else "task-order-recovery"),
        "tool_id": req.tool_id or "refund_api",
        "domain": req.domain,
        "instructions": req.instructions or "Draft recovery parameters for transient failures.",
    }
    if req.existing_task_fixture:
        supplied_context["existing_task_fixture"] = req.existing_task_fixture.model_dump()
    if req.existing_adapter_manifest:
        supplied_context["existing_adapter_tools"] = [
            t.tool_id for t in req.existing_adapter_manifest.tools
        ]
    if req.existing_recovery_contract:
        supplied_context["existing_recovery_contract"] = req.existing_recovery_contract.model_dump()

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
            "required": ["task_fixture", "recovery_contract", "unresolved_references", "explanation"],
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
        "provider": gen_result.provider.value if hasattr(gen_result.provider, "value") else str(gen_result.provider),
        "requested_model": gen_result.requested_model,
        "actual_model": gen_result.actual_model,
        "duration_ms": gen_result.duration_ms,
        "prompt_template_version": "v1.0.0",
        "usage": gen_result.usage.model_dump(),
    }

    try:
        content = gen_result.content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()
        data = json.loads(content)
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
            # Ensure domain and task id exist
            tf_data.setdefault("domain", req.domain)
            tf_data.setdefault("task_id", req.task_id or "task-draft-001")
            tf_data.setdefault("task_version", req.task_version or "1.0.0")
            tf_data.setdefault("fixture_id", "fixture-draft-001")
            tf_data.setdefault("fixture_version", "1.0.0")
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
            # Ensure attempt and retry consistency
            attempts = rc_data.get("max_task_attempts", 3)
            init_counts = rc_data.get("initial_invocation_counts_as_attempt", True)
            if init_counts:
                rc_data["max_retries"] = attempts - 1
            else:
                rc_data["max_retries"] = attempts
            # Ensure permitted terminal outcomes
            if "permitted_terminal_outcomes" in rc_data:
                rc_data["permitted_terminal_outcomes"] = [
                    TerminalOutcome(o) for o in rc_data["permitted_terminal_outcomes"]
                ]
            draft_rc = RecoveryContract.model_validate(rc_data)
        except Exception as e:  # noqa: BLE001
            unresolved.append(f"recovery_contract_validation_error: {e}")

    # Cross check tools: if task references tools not declared in adapter manifest, flag unresolved
    if draft_tf and req.existing_adapter_manifest:
        declared_tool_ids = {t.tool_id for t in req.existing_adapter_manifest.tools}
        for tid in draft_tf.associated_tool_ids:
            if tid not in declared_tool_ids:
                unresolved.append(f"unresolved_tool_reference: '{tid}' not found in adapter manifest")

    status = "SUCCESS" if not unresolved else "UNRESOLVED_REFERENCES"

    return ModelAssistedDraftResponse(
        status=status,
        draft_task_fixture=draft_tf,
        draft_adapter_manifest=req.existing_adapter_manifest,
        draft_recovery_contract=draft_rc,
        unresolved_references=unresolved,
        explanation=explanation,
        provider_metadata=provider_metadata,
    )
