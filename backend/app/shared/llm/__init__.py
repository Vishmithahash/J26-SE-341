"""Shared LLM Integration layer supporting Local Ollama/Qwen and Hosted Google Gemini."""

from app.shared.llm.contracts import (
    ConnectionTestRequest,
    ConnectionTestResponse,
    ConnectionType,
    LLMGenerationRequest,
    LLMGenerationResult,
    LLMProviderType,
    ModelSelectionConfig,
    ProviderStatusInfo,
)
from app.shared.llm.models import UserModelSelection
from app.shared.llm.router import router
from app.shared.llm.service import LLMProviderService

__all__ = [
    "ConnectionTestRequest",
    "ConnectionTestResponse",
    "ConnectionType",
    "LLMGenerationRequest",
    "LLMGenerationResult",
    "LLMProviderService",
    "LLMProviderType",
    "ModelSelectionConfig",
    "ProviderStatusInfo",
    "UserModelSelection",
    "router",
]
