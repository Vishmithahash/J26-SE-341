"""Contracts and schemas for the shared LLM integration layer."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ConnectionType(str, Enum):
    LOCAL = "local"
    HOSTED = "hosted"


class LLMProviderType(str, Enum):
    OLLAMA = "ollama"
    GEMINI = "gemini"


class LLMErrorType(str, Enum):
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    INVALID_REQUEST = "INVALID_REQUEST"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    TIMEOUT = "TIMEOUT"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    SERVICE_UNREACHABLE = "SERVICE_UNREACHABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ModelSelectionConfig(BaseModel):
    """Model selection configuration stored per authenticated user."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    connection_type: str = Field(default=ConnectionType.LOCAL.value)
    provider: str = Field(default=LLMProviderType.OLLAMA.value)
    model_id: str = Field(default="qwen3:4b", min_length=1, max_length=128)
    model: str | None = None
    generation_settings: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def resolve_and_validate_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            m_id = data.get("model_id")
            m = data.get("model")
            if (
                m_id is not None
                and m is not None
                and str(m_id).strip() != str(m).strip()
            ):
                raise ValueError(
                    f"Conflicting 'model_id' ('{m_id}') and 'model' ('{m}') values provided."
                )
            chosen = m_id if m_id is not None else m
            if chosen is None or not str(chosen).strip():
                chosen = "qwen3:4b"
            clean_model = str(chosen).strip()
            data["model_id"] = clean_model
            data["model"] = clean_model

            # Validate connection_type and provider consistency
            conn_raw = data.get("connection_type", ConnectionType.LOCAL.value)
            if hasattr(conn_raw, "value"):
                conn_raw = conn_raw.value
            conn = str(conn_raw).strip().lower()
            if "." in conn:
                conn = conn.split(".")[-1]

            prov_raw = data.get("provider", LLMProviderType.OLLAMA.value)
            if hasattr(prov_raw, "value"):
                prov_raw = prov_raw.value
            prov = str(prov_raw).strip().lower()
            if "." in prov:
                prov = prov.split(".")[-1]

            if (
                conn == ConnectionType.LOCAL.value
                and prov != LLMProviderType.OLLAMA.value
            ):
                raise ValueError(
                    f"Invalid provider combination: connection_type 'local' requires provider 'ollama', got '{prov}'."
                )
            if (
                conn == ConnectionType.HOSTED.value
                and prov != LLMProviderType.GEMINI.value
            ):
                raise ValueError(
                    f"Invalid provider combination: connection_type 'hosted' requires provider 'gemini', got '{prov}'."
                )

            data["connection_type"] = conn
            data["provider"] = prov

            # Validate generation_settings
            gen_settings = data.get("generation_settings")
            if gen_settings is not None:
                if not isinstance(gen_settings, dict):
                    raise ValueError("generation_settings must be a dictionary.")
                cls._validate_generation_settings(gen_settings)

        return data

    @classmethod
    def _validate_generation_settings(cls, settings: dict[str, Any]) -> None:
        allowed_keys = {"temperature", "max_tokens", "top_p", "timeout_seconds"}
        for k, v in settings.items():
            if k not in allowed_keys:
                raise ValueError(
                    f"Unknown generation setting '{k}'. Allowed settings: {sorted(allowed_keys)}"
                )
            if k == "temperature" and (
                isinstance(v, bool)
                or not isinstance(v, (int, float))
                or not (0.0 <= v <= 2.0)
            ):
                raise ValueError(
                    "Setting 'temperature' must be a numeric value between 0.0 and 2.0."
                )
            elif k == "max_tokens" and (
                isinstance(v, bool) or not isinstance(v, int) or not (1 <= v <= 32768)
            ):
                raise ValueError(
                    "Setting 'max_tokens' must be an integer between 1 and 32768 (booleans rejected)."
                )
            elif k == "top_p" and (
                isinstance(v, bool)
                or not isinstance(v, (int, float))
                or not (0.0 <= v <= 1.0)
            ):
                raise ValueError(
                    "Setting 'top_p' must be a numeric value between 0.0 and 1.0."
                )
            elif k == "timeout_seconds" and (
                isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0
            ):
                raise ValueError("Setting 'timeout_seconds' must be a positive number.")

    @field_validator("connection_type")
    @classmethod
    def validate_connection_type(cls, v: Any) -> str:
        if hasattr(v, "value"):
            v = v.value
        norm = str(v).strip().lower()
        if "." in norm:
            norm = norm.split(".")[-1]
        if norm not in (ConnectionType.LOCAL.value, ConnectionType.HOSTED.value):
            raise ValueError(
                f"Invalid connection_type '{v}'. Must be 'local' or 'hosted'."
            )
        return norm

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: Any) -> str:
        if hasattr(v, "value"):
            v = v.value
        norm = str(v).strip().lower()
        if "." in norm:
            norm = norm.split(".")[-1]
        if norm not in (LLMProviderType.OLLAMA.value, LLMProviderType.GEMINI.value):
            raise ValueError(
                f"Invalid provider '{v}'. Permitted providers are 'ollama' and 'gemini'."
            )
        return norm

    @field_validator("model_id")
    @classmethod
    def validate_model_id(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("model_id must not be empty.")
        return clean


class SelectionSnapshot(BaseModel):
    """Immutable snapshot of the user's model selection resolved at operation start."""

    model_config = ConfigDict(frozen=True)

    user_id: int | str
    connection_type: str
    provider: str
    requested_model: str
    generation_settings: dict[str, Any] = Field(default_factory=dict)
    selection_version: int = 1
    operation_reference: str = "general"
    prompt_template_version: str = "v1.0.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProviderStatusInfo(BaseModel):
    """Truthful provider availability and capability report."""

    provider: str
    connection_type: str
    is_configured: bool
    is_available: bool
    configured_default_model: str
    available_models: list[str] = Field(default_factory=list)
    status_message: str
    last_checked_at: datetime | None = None
    last_test_status: str | None = None  # "SUCCESS", "FAILED", "NOT_TESTED"


class LLMUsageMetadata(BaseModel):
    """Token usage and cost accounting. Unavailable counts are represented as unknown (None)."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    is_usage_known: bool = False


class LLMGenerationRequest(BaseModel):
    """Standardized request envelope for model-assisted text and structured generation."""

    system_prompt: str | None = None
    user_prompt: str = ""
    prompt: str | None = None
    operation_reference: str = "general"
    prompt_template_version: str = "v1.0.0"
    temperature: float = 0.0
    max_tokens: int = 2048
    response_schema: dict[str, Any] | None = None
    timeout_seconds: float = 15.0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def resolve_prompts(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get("prompt") and not data.get("user_prompt"):
                data["user_prompt"] = data["prompt"]
            elif data.get("user_prompt") and not data.get("prompt"):
                data["prompt"] = data["user_prompt"]
        return data


class LLMGenerationResult(BaseModel):
    """Standardized result envelope for LLM invocations with complete traceability."""

    provider: str
    requested_model: str
    actual_model: str
    operation_reference: str = "general"
    prompt_template_version: str = "v1.0.0"
    generation_settings: dict[str, Any] = Field(default_factory=dict)
    raw_text: str = ""
    structured_data: dict[str, Any] | list[Any] | None = None
    usage: LLMUsageMetadata = Field(default_factory=LLMUsageMetadata)
    duration_ms: float = 0.0
    is_success: bool = True
    error_message: str | None = None
    error_type: str | None = None

    @property
    def content(self) -> str:
        return self.raw_text


class ConnectionTestRequest(BaseModel):
    """Request payload for bounded provider connection and inference test."""

    provider: str | None = None
    model_id: str | None = None
    model: str | None = None

    @model_validator(mode="before")
    @classmethod
    def resolve_model(cls, data: Any) -> Any:
        if isinstance(data, dict):
            m_id = data.get("model_id")
            m = data.get("model")
            if (
                m_id is not None
                and m is not None
                and str(m_id).strip() != str(m).strip()
            ):
                raise ValueError(
                    f"Conflicting 'model_id' ('{m_id}') and 'model' ('{m}') values provided in test request."
                )
            chosen = m_id if m_id is not None else m
            if chosen is not None:
                data["model_id"] = str(chosen).strip()
                data["model"] = str(chosen).strip()
        return data


class ConnectionTestResponse(BaseModel):
    """Result of an explicit connection/inference test."""

    success: bool
    provider: str
    model_id: str
    duration_ms: float
    status_message: str
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def model(self) -> str:
        return self.model_id

    @property
    def latency_ms(self) -> float:
        return self.duration_ms
