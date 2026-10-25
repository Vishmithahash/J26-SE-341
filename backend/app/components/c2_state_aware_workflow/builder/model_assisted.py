"""Model-assisted (LLM) candidate EFSM builder for Component 2.

Implements ModelAssistedProvider using the shared LLM provider service.
Proposes candidate EFSM definitions from workflow input requirements while
strictly enforcing schema validation, draft lifecycle status, and mandatory human review.
"""

import asyncio

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from app.components.c2_state_aware_workflow.builder.base import ModelAssistedProvider
from app.components.c2_state_aware_workflow.builder.deterministic import (
    DeterministicCandidateBuilder,
    InsufficientInputError,
)
from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
    WorkflowInvariant,
)
from app.components.c2_state_aware_workflow.contracts.workflow_input import (
    WorkflowInputContract,
)
from app.components.c2_state_aware_workflow.predicates.expressions import (
    StructuredPredicate,
)
from app.components.c2_state_aware_workflow.validator.structural import (
    StructuralValidator,
)
from app.shared.llm.contracts import LLMGenerationRequest

# Upper bound for the worker-thread wait; per-request timeouts are at most 300 s.
MAX_LLM_WAIT_SECONDS = 330.0
from app.shared.llm.service import LLMProviderService


class ModelAssistedEFSMBuilder(ModelAssistedProvider):
    """Proposes candidate EFSM models using the authenticated user's selected LLM provider."""

    def __init__(
        self,
        user_id: int | None = None,
        db: Session | None = None,
        llm_service: LLMProviderService | None = None,
        builder_version: str = "c2_model_assisted_v1",
    ):
        self.user_id = user_id
        self.db = db
        self.builder_version = builder_version
        self._llm_service = llm_service
        self.deterministic_fallback = DeterministicCandidateBuilder(
            builder_version=builder_version
        )

    def _get_service(self) -> LLMProviderService:
        if self._llm_service is not None:
            return self._llm_service
        from app.shared.llm.router import get_llm_service

        return get_llm_service()

    def is_available(self) -> bool:
        """Check if LLM service is available."""
        try:
            self._get_service()
            return True
        except Exception:  # noqa: BLE001
            return False

    def propose_model(
        self, workflow_input: WorkflowInputContract
    ) -> EFSMModelDefinition:
        """Propose candidate EFSM model using the user's selected model, validated against contracts."""
        # 1. Validate input sufficiency
        diagnostics: list[str] = []
        if not workflow_input.task or not workflow_input.task.strip():
            diagnostics.append("Missing required natural language task description.")
        if not workflow_input.business_rules:
            diagnostics.append(
                "Insufficient business rules: at least one domain business rule must be provided."
            )
        if not workflow_input.tool_specifications:
            diagnostics.append(
                "Insufficient tool specifications: at least one tool must be declared."
            )
        if (
            not workflow_input.synthetic_fixture
            or not workflow_input.synthetic_fixture.fixture_id
        ):
            diagnostics.append(
                "Insufficient fixture reference: a valid synthetic fixture reference is required."
            )

        if diagnostics:
            raise InsufficientInputError(
                f"Cannot build candidate EFSM due to {len(diagnostics)} diagnostic failure(s).",
                diagnostics=diagnostics,
            )

        # 2. Build deterministic baseline structure as template
        base_model = self.deterministic_fallback.build_candidate_model(workflow_input)

        # 3. Request LLM refinement of draft EFSM model
        service = self._get_service()
        declared_tools = [t.tool_name for t in workflow_input.tool_specifications]
        declared_rule_ids = [r.rule_id for r in workflow_input.business_rules]
        state_ids = [s.id for s in base_model.states]
        transition_ids = [t.id for t in base_model.transitions]

        system_prompt = (
            "You are a formal methods expert in state-machine test engineering. "
            "Propose candidate EFSM refinements, transitions, and milestone invariants for testing. "
            "Never invent fictitious tools outside the declared tool specifications. "
            f"Declared tools: {declared_tools}. "
            f"Declared baseline states: {state_ids}. "
            f"Declared baseline transitions: {transition_ids}. "
            "Return valid JSON conforming to the requested schema."
        )
        user_prompt = (
            f"Workflow Task: {workflow_input.task}\n"
            f"Business Rules: {[r.model_dump() for r in workflow_input.business_rules]}\n"
            f"Tool Specifications: {[t.model_dump() for t in workflow_input.tool_specifications]}\n"
            f"Fixture Namespace: {workflow_input.synthetic_fixture.fixture_id}\n\n"
            f"Baseline States: {state_ids}\n"
            f"Baseline Transitions: {transition_ids}\n"
            "Refine state descriptions, milestone names, and transition semantics."
        )

        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "state_refinements": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "state_id": {"type": "string"},
                            "description": {"type": "string"},
                            "milestone": {"type": "string"},
                        },
                        "required": ["state_id"],
                    },
                },
                "transition_refinements": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "transition_id": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["transition_id"],
                    },
                },
                "proposed_invariants": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "source_rule": {"type": "string"},
                            "predicate": {
                                "type": "object",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": ["comparison", "presence", "logical", "literal"],
                                    },
                                    "left": {"type": "object"},
                                    "op": {"type": "string"},
                                    "right": {},
                                    "target": {"type": "object"},
                                    "clauses": {"type": "array"},
                                    "value": {"type": "string"},
                                },
                                "required": ["type", "op"],
                            },
                        },
                        "required": ["id", "name", "predicate"],
                    },
                },
            },
            "required": ["name"],
        }

        gen_req = LLMGenerationRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            operation_reference="c2_propose_efsm",
            prompt_template_version="c2-builder-prompt-v2.0",
            response_schema=schema,
            temperature=0.0,
            max_tokens=2048,
            # qwen3.5's reasoning trace alone exceeded the 180 s budget; the refinement needs none
            metadata={"ollama_think": False},
        )

        failure_reason: str | None = None
        try:
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

            if loop and loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(
                        asyncio.run, self._async_invoke(service, gen_req)
                    )
                    # The request carries its own configured timeout; this only guards the worker thread.
                    gen_res = future.result(timeout=MAX_LLM_WAIT_SECONDS)
            else:
                gen_res = asyncio.run(self._async_invoke(service, gen_req))

            if gen_res.is_success and gen_res.structured_data:
                data = (
                    gen_res.structured_data
                    if isinstance(gen_res.structured_data, dict)
                    else {}
                )
                refined_name = data.get("name") or base_model.name
                provenance_tag = (
                    f"[Model-Assisted: {gen_res.provider}/{gen_res.actual_model}]"
                )
                user_desc = data.get("description") or base_model.description
                refined_desc = f"{provenance_tag} {user_desc}"

                # Apply validated state refinements
                refined_states = []
                state_ref_map = {
                    s.get("state_id"): s
                    for s in data.get("state_refinements", [])
                    if isinstance(s, dict) and s.get("state_id") in state_ids
                }
                for st in base_model.states:
                    if st.id in state_ref_map:
                        ref = state_ref_map[st.id]
                        new_desc = ref.get("description") or st.description
                        new_milestone = ref.get("milestone") or st.milestone
                        refined_states.append(
                            st.model_copy(
                                update={
                                    "description": new_desc,
                                    "milestone": new_milestone,
                                }
                            )
                        )
                    else:
                        refined_states.append(st)

                # Apply validated transition refinements
                refined_transitions = []
                trans_ref_map = {
                    t.get("transition_id"): t
                    for t in data.get("transition_refinements", [])
                    if isinstance(t, dict) and t.get("transition_id") in transition_ids
                }
                for tr in base_model.transitions:
                    if tr.id in trans_ref_map:
                        ref = trans_ref_map[tr.id]
                        new_desc = ref.get("description") or tr.description
                        refined_transitions.append(
                            tr.model_copy(update={"description": new_desc})
                        )
                    else:
                        refined_transitions.append(tr)

                # Apply validated proposed invariants grounded in declared rules
                new_invariants = list(base_model.invariants)
                existing_inv_ids = {inv.id for inv in new_invariants}
                predicate_adapter = TypeAdapter(StructuredPredicate)

                for prop in data.get("proposed_invariants", []):
                    if not isinstance(prop, dict):
                        continue
                    p_id = prop.get("id")
                    p_name = prop.get("name")
                    p_rule = prop.get("source_rule")
                    raw_pred = prop.get("predicate")

                    if not p_id or not p_name or p_id in existing_inv_ids:
                        continue

                    # Grounded check: rule must exist if specified
                    if p_rule and p_rule not in declared_rule_ids:
                        continue

                    if not isinstance(raw_pred, dict):
                        continue

                    try:
                        parsed_pred = predicate_adapter.validate_python(raw_pred)
                    except Exception:  # noqa: BLE001, S112
                        continue

                    new_invariants.append(
                        WorkflowInvariant(
                            id=p_id,
                            name=p_name,
                            predicate=parsed_pred,
                            description=prop.get("description")
                            or f"Model-proposed invariant grounded in {p_rule or 'domain rules'}",
                            source_rule=p_rule,
                        )
                    )
                    existing_inv_ids.add(p_id)

                candidate_model = base_model.model_copy(
                    update={
                        "name": refined_name,
                        "description": refined_desc,
                        "states": refined_states,
                        "transitions": refined_transitions,
                        "invariants": new_invariants,
                    }
                )

                # Validate the complete candidate model with native structural validator
                validator = StructuralValidator()
                errors, _warnings = validator.validate(candidate_model)
                if errors:
                    err_msg = "; ".join(e.get("message", "Validation error") for e in errors)
                    failure_reason = f"Candidate EFSM structural validation failed: {err_msg}"
                else:
                    return candidate_model
            else:
                failure_reason = (
                    gen_res.error_message
                    or "Structured proposal was empty or unsuccessful"
                )
        except Exception as exc:  # noqa: BLE001
            failure_reason = str(exc)

        # Explicitly labeled deterministic fallback
        labeled_desc = f"[Deterministic Fallback: LLM assistance failed - {failure_reason or 'unreachable'}] {base_model.description}"
        return base_model.model_copy(update={"description": labeled_desc})

    async def _async_invoke(
        self, service: LLMProviderService, req: LLMGenerationRequest
    ):
        if self.user_id:
            return await service.invoke_for_user(self.user_id, req, self.db)
        adapter = service.get_adapter("ollama")
        return await adapter.generate(req)
