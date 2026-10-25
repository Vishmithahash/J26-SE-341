"""Service layer for managing user model selections and invoking selected LLM providers."""

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.shared.llm.adapters.gemini import GeminiAdapter
from app.shared.llm.adapters.ollama import OllamaAdapter
from app.shared.llm.contracts import (
    ConnectionTestResponse,
    LLMErrorType,
    LLMGenerationRequest,
    LLMGenerationResult,
    LLMProviderType,
    ModelSelectionConfig,
    ProviderStatusInfo,
    SelectionSnapshot,
)
from app.shared.llm.models import UserModelSelection

logger = logging.getLogger(__name__)

GEMINI_DISABLED_MESSAGE = (
    "Hosted Gemini is disabled. Local Ollama is the default provider; "
    "set GEMINI_ENABLED=true in backend/.env to allow credit-consuming Gemini calls."
)


class LLMProviderService:
    """Orchestrates model selection resolution, provider status checking, and model execution."""

    _instance: "LLMProviderService | None" = None

    @classmethod
    def get_instance(cls) -> "LLMProviderService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(
        self,
        ollama_adapter: OllamaAdapter | None = None,
        gemini_adapter: GeminiAdapter | None = None,
        gemini_enabled: bool | None = None,
    ):
        self.ollama_adapter = ollama_adapter or OllamaAdapter()
        self.gemini_adapter = gemini_adapter or GeminiAdapter()
        self.gemini_enabled = (
            get_settings().gemini_enabled if gemini_enabled is None else gemini_enabled
        )

    def _require_provider_enabled(self, provider_name: str) -> None:
        if provider_name == LLMProviderType.GEMINI.value and not self.gemini_enabled:
            raise ValueError(GEMINI_DISABLED_MESSAGE)

    def get_adapter(self, provider_name: str):
        norm = (provider_name or "").strip().lower()
        if norm == LLMProviderType.GEMINI.value:
            self._require_provider_enabled(norm)
            return self.gemini_adapter
        if norm == LLMProviderType.OLLAMA.value:
            return self.ollama_adapter
        raise ValueError(f"Unknown or unsupported LLM provider '{provider_name}'.")

    def get_user_selection(
        self,
        user_id: int | str,
        db: Session | None = None,
    ) -> UserModelSelection:
        """Fetch the persistent selection for an authenticated user, creating default if absent."""
        uid = int(user_id)
        close_db = False
        if db is None:
            from app.database import SessionLocal

            db = SessionLocal()
            close_db = True
        try:
            stmt = select(UserModelSelection).where(UserModelSelection.user_id == uid)
            selection = db.execute(stmt).scalar_one_or_none()
            if selection is None:
                settings = get_settings()
                selection = UserModelSelection(
                    user_id=uid,
                    connection_type="local",
                    provider=LLMProviderType.OLLAMA.value,
                    model_id=settings.ollama_model,
                    generation_settings={},
                    updated_at=datetime.now(UTC),
                )
                db.add(selection)
                db.commit()
                db.refresh(selection)
            return selection
        finally:
            if close_db and db is not None:
                db.close()

    def save_user_selection(
        self,
        user_id: int | str,
        config: ModelSelectionConfig,
        db: Session | None = None,
    ) -> UserModelSelection:
        """Update or create user's authoritative model selection."""
        self._require_provider_enabled((config.provider or "").strip().lower())
        uid = int(user_id)
        close_db = False
        if db is None:
            from app.database import SessionLocal

            db = SessionLocal()
            close_db = True
        try:
            stmt = select(UserModelSelection).where(UserModelSelection.user_id == uid)
            selection = db.execute(stmt).scalar_one_or_none()
            now = datetime.now(UTC)

            if selection is None:
                selection = UserModelSelection(
                    user_id=uid,
                    connection_type=config.connection_type,
                    provider=config.provider,
                    model_id=config.model_id,
                    generation_settings=config.generation_settings or {},
                    last_test_status=None,
                    last_test_at=None,
                    updated_at=now,
                )
                db.add(selection)
            else:
                if (
                    selection.provider != config.provider
                    or selection.model_id != config.model_id
                    or selection.generation_settings != (config.generation_settings or {})
                ):
                    selection.last_test_status = None
                    selection.last_test_at = None
                selection.connection_type = config.connection_type
                selection.provider = config.provider
                selection.model_id = config.model_id
                selection.generation_settings = config.generation_settings or {}
                selection.updated_at = now

            db.commit()
            db.refresh(selection)
            return selection
        finally:
            if close_db and db is not None:
                db.close()

    async def get_providers_status(
        self,
        db: Session | None = None,
        user_id: int | None = None,
    ) -> list[ProviderStatusInfo]:
        """Check and return availability of configured providers."""
        last_test_status = None
        user_sel = None
        ollama_model = None
        gemini_model = None

        if user_id is not None:
            close_db = False
            if db is None:
                from app.database import SessionLocal

                db = SessionLocal()
                close_db = True
            try:
                stmt = select(UserModelSelection).where(
                    UserModelSelection.user_id == int(user_id)
                )
                user_sel = db.execute(stmt).scalar_one_or_none()
                if user_sel:
                    last_test_status = user_sel.last_test_status
                    if user_sel.provider == LLMProviderType.OLLAMA.value:
                        ollama_model = user_sel.model_id
                    elif user_sel.provider == LLMProviderType.GEMINI.value:
                        gemini_model = user_sel.model_id
            finally:
                if close_db and db is not None:
                    db.close()

        # Query provider adapters for truthful availability of requested or default models
        ollama_status = await self.ollama_adapter.check_availability(
            model_id=ollama_model
        )
        if self.gemini_enabled:
            gemini_status = await self.gemini_adapter.check_availability(
                model_id=gemini_model
            )
        else:
            gemini_status = ProviderStatusInfo(
                provider=LLMProviderType.GEMINI.value,
                connection_type="hosted",
                is_configured=False,
                is_available=False,
                configured_default_model=self.gemini_adapter.default_model,
                available_models=[],
                status_message=GEMINI_DISABLED_MESSAGE,
                last_checked_at=datetime.now(UTC),
            )

        if user_sel is not None and last_test_status is not None:
            # Attach last test status ONLY if matching provider and model
            if user_sel.provider == LLMProviderType.OLLAMA.value:
                ollama_status.last_test_status = last_test_status
            elif user_sel.provider == LLMProviderType.GEMINI.value:
                gemini_status.last_test_status = last_test_status

        return [ollama_status, gemini_status]

    def get_provider_status(self, provider_name: str) -> ProviderStatusInfo:
        """Synchronously check basic configuration of the provider."""
        norm = (provider_name or "").strip().lower()
        adapter = self.get_adapter(norm)
        is_conf = bool(adapter.api_key) if hasattr(adapter, "api_key") else True
        return ProviderStatusInfo(
            provider=norm,
            connection_type="local"
            if norm == LLMProviderType.OLLAMA.value
            else "hosted",
            is_configured=is_conf,
            is_available=is_conf,
            configured_default_model=adapter.default_model,
            available_models=[adapter.default_model],
            status_message=f"{norm} configuration ready",
            last_checked_at=datetime.now(UTC),
        )

    def resolve_selection_snapshot(
        self,
        user_id: int | str,
        operation_reference: str = "general",
        prompt_template_version: str = "v1.0.0",
        db: Session | None = None,
    ) -> SelectionSnapshot:
        """Resolve selection into an immutable snapshot when an operation begins."""
        sel = self.get_user_selection(user_id, db)
        return SelectionSnapshot(
            user_id=int(user_id),
            connection_type=sel.connection_type,
            provider=sel.provider,
            requested_model=sel.model_id,
            generation_settings=dict(sel.generation_settings or {}),
            selection_version=1,
            operation_reference=operation_reference,
            prompt_template_version=prompt_template_version,
            created_at=datetime.now(UTC),
        )

    async def test_connection(
        self,
        user_id: int | str,
        provider_name: str | None,
        model_id: str | None,
        db: Session | None = None,
    ) -> ConnectionTestResponse:
        """Run an explicit, bounded non-streaming test inference."""
        uid = int(user_id)
        target_provider = (provider_name or "").strip().lower()
        if not target_provider:
            # Fall back to user's saved selection
            sel = self.get_user_selection(uid, db)
            target_provider = sel.provider
            target_model = model_id or sel.model_id
        else:
            target_model = model_id

        adapter = self.get_adapter(target_provider)
        if not target_model:
            target_model = (
                self.gemini_adapter.default_model
                if target_provider == LLMProviderType.GEMINI.value
                else self.ollama_adapter.default_model
            )

        test_request = LLMGenerationRequest(
            system_prompt="You are a QA framework test probe. Return JSON status.",
            user_prompt='Respond with a JSON object: {"status": "ok", "framework": "agentic_qa"}',
            operation_reference="connection_test",
            prompt_template_version="v1.0.0",
            temperature=0.0,
            max_tokens=500,
            response_schema={
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "framework": {"type": "string"},
                },
                "required": ["status"],
            },
            timeout_seconds=180.0,
        )

        res = await adapter.generate(test_request, model_override=target_model)

        # Probe validation: probe request asked for exact {"status": "ok", "framework": "agentic_qa"}
        probe_valid = (
            res.is_success
            and isinstance(res.structured_data, dict)
            and res.structured_data.get("status") == "ok"
            and res.structured_data.get("framework") == "agentic_qa"
        )
        test_succeeded = res.is_success and probe_valid

        # Update test status in database ONLY IF tested provider and model match the user's active saved selection!
        # Testing Gemini must NOT mark the user's different saved Ollama model as verified.
        close_db = False
        if db is None:
            from app.database import SessionLocal

            db = SessionLocal()
            close_db = True
        try:
            stmt = select(UserModelSelection).where(UserModelSelection.user_id == uid)
            selection = db.execute(stmt).scalar_one_or_none()
            if (
                selection
                and selection.provider == target_provider
                and selection.model_id == target_model
            ):
                selection.last_test_status = "SUCCESS" if test_succeeded else "FAILED"
                selection.last_test_at = datetime.now(UTC)
                db.commit()
        finally:
            if close_db and db is not None:
                db.close()

        if test_succeeded:
            return ConnectionTestResponse(
                success=True,
                provider=target_provider,
                model_id=res.actual_model,
                duration_ms=res.duration_ms,
                status_message=f"Inference succeeded on {target_provider} ({res.actual_model}) in {round(res.duration_ms, 2)}ms.",
                metadata={
                    "usage": res.usage.model_dump(),
                    "response": res.structured_data or res.raw_text[:100],
                },
            )
        else:
            fail_reason = (
                f"Probe validation failed: expected 'status: ok', got: {res.raw_text[:120]}"
                if res.is_success
                else (res.error_message or "Unknown failure")
            )
            return ConnectionTestResponse(
                success=False,
                provider=target_provider,
                model_id=target_model,
                duration_ms=res.duration_ms,
                status_message=f"Connection test failed: {fail_reason}",
                error=fail_reason,
                metadata={"error_type": res.error_type},
            )

    async def invoke_for_user(
        self,
        user_id: int | str,
        request: LLMGenerationRequest,
        db: Session | None = None,
    ) -> LLMGenerationResult:
        """Execute generation using the authenticated user's current saved provider and model.

        Transactions are never held open across external HTTP requests.
        """
        uid = int(user_id)
        # 1. Resolve user's frozen selection from database in a short transaction
        snapshot = self.resolve_selection_snapshot(
            uid,
            operation_reference=request.operation_reference,
            prompt_template_version=request.prompt_template_version,
            db=db,
        )

        apply_generation_limits(request, dict(snapshot.generation_settings))

        # 2. Resolve adapter
        try:
            adapter = self.get_adapter(snapshot.provider)
        except ValueError as err:
            return LLMGenerationResult(
                provider=snapshot.provider,
                requested_model=snapshot.requested_model,
                actual_model=snapshot.requested_model,
                operation_reference=request.operation_reference,
                prompt_template_version=request.prompt_template_version,
                is_success=False,
                error_message=str(err),
                error_type=LLMErrorType.INVALID_REQUEST.value,
            )

        # 3. Execute generation completely outside DB transaction
        result = await adapter.generate(
            request, model_override=snapshot.requested_model
        )

        return result


def apply_generation_limits(
    request: LLMGenerationRequest, user_settings: dict
) -> LLMGenerationRequest:
    """Resolve temperature, token, top-p and timeout limits for one request.

    Values the caller set explicitly win, then the user's saved generation settings,
    then the configured backend defaults (LLM_DEFAULT_TIMEOUT_SECONDS, LLM_DEFAULT_MAX_TOKENS).
    """
    explicit = request.model_fields_set
    settings = get_settings()
    if "temperature" not in explicit and "temperature" in user_settings:
        request.temperature = float(user_settings["temperature"])
    if "top_p" not in explicit and "top_p" in user_settings:
        request.top_p = float(user_settings["top_p"])
    if "max_tokens" not in explicit:
        request.max_tokens = int(
            user_settings.get("max_tokens", settings.llm_default_max_tokens)
        )
    if "timeout_seconds" not in explicit:
        request.timeout_seconds = float(
            user_settings.get("timeout_seconds", settings.llm_default_timeout_seconds)
        )
    return request
