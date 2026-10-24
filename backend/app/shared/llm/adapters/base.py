"""Base interface for LLM provider adapters."""

from abc import ABC, abstractmethod

from app.shared.llm.contracts import (
    LLMGenerationRequest,
    LLMGenerationResult,
    ProviderStatusInfo,
)


class BaseLLMAdapter(ABC):
    """Abstract interface normalized across Local (Ollama) and Hosted (Gemini) providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (ollama, gemini)."""

    @abstractmethod
    async def check_availability(
        self, model_id: str | None = None
    ) -> ProviderStatusInfo:
        """Check provider reachability and list installed/available permitted models."""

    @abstractmethod
    async def generate(
        self,
        request: LLMGenerationRequest,
        model_override: str | None = None,
    ) -> LLMGenerationResult:
        """Execute non-streaming text or structured generation with usage telemetry."""
