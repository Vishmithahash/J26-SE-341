"""Contracts and schemas for the shared LLM integration layer."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ConnectionType(str, Enum):
    LOCAL = "local"
    HOSTED = "hosted"


class LLMProviderType(str, Enum):
    OLLAMA = "ollama"
    GEMINI = "gemini"


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
    def resolve_model_field(cls, data: Any) -> Any:
        if isinstance(data, dict):
            m = data.get("model_id") or data.get("model") or "qwen3:4b"
            data["model_id"] = str(m).strip()
            data["model"] = str(m).strip()
        return data

    @field_validator("connection_type")
    @classmethod
    def validate_connection_type(cls, v: str) -> str:
        norm = v.strip().lower()
        if norm not in (ConnectionType.LOCAL.value, ConnectionType.HOSTED.value):
            raise ValueError(f"Invalid connection_type '{v}'. Must be 'local' or 'hosted'.")
        return norm

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        norm = v.strip().lower()
        if norm not in (LLMProviderType.OLLAMA.value, LLMProviderType.GEMINI.value):
            raise ValueError(f"Invalid provider '{v}'. Permitted providers are 'ollama' and 'gemini'.")
        return norm

    @field_validator("model_id")
    @classmethod
    def validate_model_id(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("model_id must not be empty.")
        return clean


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


class ConnectionTestResponse(BaseModel):
    """Result of an explicit connection/inference test."""

    success: bool
    provider: str
    model_id: str
    duration_ms: float
    status_message: str
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
