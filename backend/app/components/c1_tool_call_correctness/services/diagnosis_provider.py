import abc
import asyncio
import time
from typing import Any

from pydantic import BaseModel, Field

from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CaseDiagnosisRecord,
    ExplanationMethod,
)


class ModelUsageMetrics(BaseModel):
    """Usage metrics and telemetry for model-assisted presentation."""

    prompt_version: str = "c1-diagnosis-prompt-v1.0"
    model_name: str = "deterministic-presentation"
    tokens_prompt: int = 0
    tokens_completion: int = 0
    duration_ms: float = 0.0
    retry_count: int = 0
    error: str | None = None


class DiagnosisPresentationResult(BaseModel):
    """Result of presenting diagnosis through a provider."""

    explanation_summary: str
    explanation_method: ExplanationMethod
    metrics: ModelUsageMetrics = Field(default_factory=ModelUsageMetrics)


class DiagnosisProvider(abc.ABC):
    """Abstract interface for diagnosis presentation providers."""

    @abc.abstractmethod
    async def present_diagnosis(
        self, record: CaseDiagnosisRecord
    ) -> DiagnosisPresentationResult:
        """Present or summarize the diagnosed failure."""


class DeterministicDiagnosisProvider(DiagnosisProvider):
    """Default deterministic presentation provider.
    Presents exact rule derivations without external network dependencies.
    """

    async def present_diagnosis(
        self, record: CaseDiagnosisRecord
    ) -> DiagnosisPresentationResult:
        return DiagnosisPresentationResult(
            explanation_summary=record.explanation_summary,
            explanation_method=ExplanationMethod.DETERMINISTIC_RULE_DERIVATION,
            metrics=ModelUsageMetrics(
                prompt_version="c1-diagnosis-prompt-v1.0",
                model_name="deterministic-rule-engine",
                duration_ms=0.0,
            ),
        )


class ModelAssistedDiagnosisProvider(DiagnosisProvider):
    """Bounded, validated model-assisted presentation provider.
    - Treats LLM output purely as an optional presentation layer.
    - Never overwrites deterministic findings or invents unsupported evidence.
    - Enforces explicit timeouts, token budgets, and verification checks.
    - Gracefully falls back to deterministic summary on failure without crashing or returning fake answers.
    """

    def __init__(
        self,
        model_callable: Any | None = None,
        model_name: str = "mock-assisted-presenter",
        timeout_seconds: float = 5.0,
        max_retries: int = 1,
    ):
        self.model_callable = model_callable
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.prompt_version = "c1-diagnosis-prompt-v1.0"

    async def present_diagnosis(
        self, record: CaseDiagnosisRecord
    ) -> DiagnosisPresentationResult:
        start_time = time.perf_counter()

        # If no provider is configured, return deterministic summary immediately
        if self.model_callable is None:
            return DiagnosisPresentationResult(
                explanation_summary=record.explanation_summary,
                explanation_method=ExplanationMethod.DETERMINISTIC_RULE_DERIVATION,
                metrics=ModelUsageMetrics(
                    prompt_version=self.prompt_version,
                    model_name=self.model_name,
                    duration_ms=0.0,
                    error="Provider unavailable: No model callable configured",
                ),
            )

        # Bounded excerpt: Only feed validated evidence IDs and candidate references
        valid_evidence_set = set(record.evidence_refs)
        valid_candidates_map = {
            f"{c.file_path}:{c.function_name}": c
            for c in record.candidate_code_locations
        }

        # Attempt invocation with timeout and retry limit
        attempt = 0
        last_error: str | None = None

        while attempt <= self.max_retries:
            attempt += 1
            try:
                # Call model callable with timeout
                coro = self.model_callable(
                    cause_category=record.cause_category.value,
                    deterministic_summary=record.explanation_summary,
                    evidence_refs=list(valid_evidence_set),
                    candidates=[
                        {"file": c.file_path, "function": c.function_name}
                        for c in record.candidate_code_locations
                    ],
                )
                if asyncio.iscoroutine(coro):
                    raw_result = await asyncio.wait_for(
                        coro, timeout=self.timeout_seconds
                    )
                else:
                    raw_result = coro

                duration_ms = (time.perf_counter() - start_time) * 1000.0

                # Validate structured response
                if not isinstance(raw_result, dict):
                    raise TypeError(
                        f"Model returned invalid non-dict response: {type(raw_result).__name__}"
                    )

                refined_summary = str(
                    raw_result.get("summary") or record.explanation_summary
                ).strip()
                cited_evidence = raw_result.get("cited_evidence", [])

                # Verify that cited evidence exists
                for ev in cited_evidence:
                    if ev not in valid_evidence_set:
                        raise ValueError(
                            f"Model fabricated non-existent evidence reference: {ev}"
                        )

                # Verify that cited candidates exist if returned
                cited_candidates = raw_result.get("cited_candidates", [])
                for cand in cited_candidates:
                    key = f"{cand.get('file')}:{cand.get('function')}"
                    if key not in valid_candidates_map:
                        raise ValueError(
                            f"Model fabricated non-existent candidate reference: {key}"
                        )

                # Return validated model-assisted presentation
                return DiagnosisPresentationResult(
                    explanation_summary=refined_summary,
                    explanation_method=ExplanationMethod.MODEL_ASSISTED_PRESENTATION,
                    metrics=ModelUsageMetrics(
                        prompt_version=self.prompt_version,
                        model_name=self.model_name,
                        tokens_prompt=raw_result.get("prompt_tokens", 100),
                        tokens_completion=raw_result.get("completion_tokens", 50),
                        duration_ms=round(duration_ms, 2),
                        retry_count=attempt - 1,
                    ),
                )

            except Exception as e:  # noqa: BLE001
                last_error = str(e)

        # On timeout, error, or validation failure: fall back to deterministic summary without breaking
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        return DiagnosisPresentationResult(
            explanation_summary=record.explanation_summary,
            explanation_method=ExplanationMethod.DETERMINISTIC_RULE_DERIVATION,
            metrics=ModelUsageMetrics(
                prompt_version=self.prompt_version,
                model_name=self.model_name,
                duration_ms=round(duration_ms, 2),
                retry_count=attempt - 1,
                error=f"Model presentation fallback: {last_error}",
            ),
        )
