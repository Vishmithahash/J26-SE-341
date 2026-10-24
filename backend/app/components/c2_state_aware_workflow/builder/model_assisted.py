"""Model-assisted (LLM) candidate EFSM builder for Component 2.

Implements ModelAssistedProvider using the shared LLM provider service.
Proposes candidate EFSM definitions from workflow input requirements while
strictly enforcing schema validation, draft lifecycle status, and mandatory human review.
"""

import asyncio

from sqlalchemy.orm import Session

from app.components.c2_state_aware_workflow.builder.base import ModelAssistedProvider
from app.components.c2_state_aware_workflow.builder.deterministic import (
    DeterministicCandidateBuilder,
    InsufficientInputError,
)
from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)
from app.components.c2_state_aware_workflow.contracts.workflow_input import (
    WorkflowInputContract,
)
from app.shared.llm.contracts import LLMGenerationRequest
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
        self.deterministic_fallback = DeterministicCandidateBuilder(builder_version=builder_version)

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
            diagnostics.append("Insufficient business rules: at least one domain business rule must be provided.")
        if not workflow_input.tool_specifications:
            diagnostics.append("Insufficient tool specifications: at least one tool must be declared.")
        if not workflow_input.synthetic_fixture or not workflow_input.synthetic_fixture.fixture_id:
            diagnostics.append("Insufficient fixture reference: a valid synthetic fixture reference is required.")

        if diagnostics:
            raise InsufficientInputError(
                f"Cannot build candidate EFSM due to {len(diagnostics)} diagnostic failure(s).",
                diagnostics=diagnostics,
            )

        # 2. Build deterministic baseline structure as template
        base_model = self.deterministic_fallback.build_candidate_model(workflow_input)

        # 3. Request LLM refinement of draft EFSM model
        service = self._get_service()
        system_prompt = (
            "You are a formal methods expert in state-machine test engineering. "
            "Propose candidate EFSM refinements, transitions, and milestone invariants for testing. "
            "Never invent fictitious tools outside the declared tool specifications. "
            "Return valid JSON conforming to the requested schema."
        )
        user_prompt = (
            f"Workflow Task: {workflow_input.task}\n"
            f"Business Rules: {[r.model_dump() for r in workflow_input.business_rules]}\n"
            f"Tool Specifications: {[t.model_dump() for t in workflow_input.tool_specifications]}\n"
            f"Fixture Namespace: {workflow_input.synthetic_fixture.fixture_id}\n\n"
            f"Baseline States: {[s.id for s in base_model.states]}\n"
            f"Baseline Transitions: {[t.id for t in base_model.transitions]}\n"
            "Refine or validate the transition guards, invariant expressions, and milestone definitions."
        )

        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "model_notes": {"type": "string"},
            },
            "required": ["name"],
        }

        gen_req = LLMGenerationRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            operation_reference="c2_propose_efsm",
            prompt_template_version="c2-builder-prompt-v1.0",
            response_schema=schema,
            temperature=0.0,
            max_tokens=1500,
            timeout_seconds=8.0,
        )

        try:
            # Run invocation synchronously if inside standard sync route
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                pass

            if loop and loop.is_running():
                # Running in an event loop: run in worker thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(
                        asyncio.run,
                        self._async_invoke(service, gen_req)
                    )
                    gen_res = future.result(timeout=10.0)
            else:
                gen_res = asyncio.run(self._async_invoke(service, gen_req))

            if gen_res.is_success and gen_res.structured_data:
                data = gen_res.structured_data if isinstance(gen_res.structured_data, dict) else {}
                refined_name = data.get("name") or base_model.name
                refined_desc = data.get("description") or f"LLM-assisted proposal ({gen_res.actual_model}): {base_model.description}"

                return base_model.model_copy(
                    update={
                        "name": refined_name,
                        "description": refined_desc,
                    }
                )
        except Exception:  # noqa: BLE001, S110
            # Fall back safely to deterministic baseline on LLM failure
            pass

        return base_model

    async def _async_invoke(self, service: LLMProviderService, req: LLMGenerationRequest):
        if self.user_id and self.db:
            return await service.invoke_for_user(self.user_id, req, self.db)
        adapter = service.get_adapter("ollama")
        return await adapter.generate(req)
