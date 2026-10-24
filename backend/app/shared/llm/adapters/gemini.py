"""Hosted Google Gemini provider adapter using the native Gemini Developer API."""

import json
import os
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import get_settings
from app.shared.llm.adapters.base import BaseLLMAdapter
from app.shared.llm.contracts import (
    ConnectionType,
    LLMGenerationRequest,
    LLMGenerationResult,
    LLMProviderType,
    LLMUsageMetadata,
    ProviderStatusInfo,
)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
PERMITTED_GEMINI_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-2.5-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]


class GeminiAdapter(BaseLLMAdapter):
    """Adapter for the native Google Gemini Developer API."""

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        settings = get_settings()
        # Retrieve key from parameter, settings SecretStr, or environment
        secret_val = (
            settings.gemini_api_key.get_secret_value()
            if settings.gemini_api_key
            else ""
        )
        self.api_key = api_key or secret_val or os.environ.get("GEMINI_API_KEY", "")
        self.default_model = (
            default_model or settings.gemini_model or "gemini-3.5-flash-lite"
        )
        self._external_client = http_client

    @property
    def provider_name(self) -> str:
        return LLMProviderType.GEMINI.value

    async def _get_client(self, timeout: float) -> tuple[httpx.AsyncClient, bool]:
        if self._external_client is not None:
            return self._external_client, False
        return httpx.AsyncClient(timeout=timeout), True

    def _sanitize(self, message: str) -> str:
        """Sanitize error messages to guarantee no secret exposure."""
        if not self.api_key or not self.api_key.strip():
            return message
        return message.replace(self.api_key, "[REDACTED]")

    async def check_availability(
        self, model_id: str | None = None
    ) -> ProviderStatusInfo:
        """Check if Gemini credentials are configured and model endpoint is reachable."""
        target_model = (model_id or self.default_model).strip()
        if not self.api_key or not self.api_key.strip():
            return ProviderStatusInfo(
                provider=self.provider_name,
                connection_type=ConnectionType.HOSTED.value,
                is_configured=False,
                is_available=False,
                configured_default_model=self.default_model,
                available_models=PERMITTED_GEMINI_MODELS,
                status_message="Gemini API key is not configured on the server",
                last_checked_at=datetime.now(UTC),
            )

        client, should_close = await self._get_client(timeout=5.0)
        try:
            # Query the specific model definition or models list with request header
            url = f"{GEMINI_BASE_URL}/models/{target_model}"
            headers = {
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            }
            resp = await client.get(url, headers=headers)

            if resp.status_code == 200:
                return ProviderStatusInfo(
                    provider=self.provider_name,
                    connection_type=ConnectionType.HOSTED.value,
                    is_configured=True,
                    is_available=True,
                    configured_default_model=self.default_model,
                    available_models=PERMITTED_GEMINI_MODELS,
                    status_message=f"Gemini API configured and verified ({target_model})",
                    last_checked_at=datetime.now(UTC),
                )
            elif resp.status_code in (401, 403):
                return ProviderStatusInfo(
                    provider=self.provider_name,
                    connection_type=ConnectionType.HOSTED.value,
                    is_configured=True,
                    is_available=False,
                    configured_default_model=self.default_model,
                    available_models=PERMITTED_GEMINI_MODELS,
                    status_message="Configured Gemini credentials are invalid or forbidden",
                    last_checked_at=datetime.now(UTC),
                )
            elif resp.status_code == 400:
                sanitized = self._sanitize(resp.text[:120])
                return ProviderStatusInfo(
                    provider=self.provider_name,
                    connection_type=ConnectionType.HOSTED.value,
                    is_configured=True,
                    is_available=False,
                    configured_default_model=self.default_model,
                    available_models=PERMITTED_GEMINI_MODELS,
                    status_message=f"Gemini API rejected request: {sanitized}",
                    last_checked_at=datetime.now(UTC),
                )
            elif resp.status_code == 404:
                return ProviderStatusInfo(
                    provider=self.provider_name,
                    connection_type=ConnectionType.HOSTED.value,
                    is_configured=True,
                    is_available=False,
                    configured_default_model=self.default_model,
                    available_models=PERMITTED_GEMINI_MODELS,
                    status_message=f"Configured model '{self.default_model}' is not found or unsupported",
                    last_checked_at=datetime.now(UTC),
                )
            elif resp.status_code == 429:
                return ProviderStatusInfo(
                    provider=self.provider_name,
                    connection_type=ConnectionType.HOSTED.value,
                    is_configured=True,
                    is_available=False,
                    configured_default_model=self.default_model,
                    available_models=PERMITTED_GEMINI_MODELS,
                    status_message="Gemini quota exhausted or rate limit encountered",
                    last_checked_at=datetime.now(UTC),
                )
            else:
                return ProviderStatusInfo(
                    provider=self.provider_name,
                    connection_type=ConnectionType.HOSTED.value,
                    is_configured=True,
                    is_available=False,
                    configured_default_model=self.default_model,
                    available_models=PERMITTED_GEMINI_MODELS,
                    status_message=f"Gemini API returned status {resp.status_code}",
                    last_checked_at=datetime.now(UTC),
                )
        except Exception as exc:  # noqa: BLE001
            sanitized = self._sanitize(str(exc))
            return ProviderStatusInfo(
                provider=self.provider_name,
                connection_type=ConnectionType.HOSTED.value,
                is_configured=True,
                is_available=False,
                configured_default_model=self.default_model,
                available_models=PERMITTED_GEMINI_MODELS,
                status_message=f"Gemini check failed: {sanitized}",
                last_checked_at=datetime.now(UTC),
            )
        finally:
            if should_close:
                await client.aclose()

    async def generate(
        self,
        request: LLMGenerationRequest,
        model_override: str | None = None,
    ) -> LLMGenerationResult:
        """Call native Gemini :generateContent endpoint with structured payload."""
        actual_model = model_override or self.default_model
        start_time = time.perf_counter()
        timeout = request.timeout_seconds

        if not self.api_key or not self.api_key.strip():
            return LLMGenerationResult(
                provider=self.provider_name,
                requested_model=actual_model,
                actual_model=actual_model,
                operation_reference=request.operation_reference,
                prompt_template_version=request.prompt_template_version,
                duration_ms=0.0,
                is_success=False,
                error_type="INVALID_CREDENTIALS",
                error_message="Gemini API key is not configured on the server",
            )

        # Prepare Gemini native request body
        generation_config: dict[str, Any] = {
            "temperature": request.temperature,
            "maxOutputTokens": request.max_tokens,
        }

        if request.response_schema is not None:
            generation_config["responseMimeType"] = "application/json"
            generation_config["responseSchema"] = request.response_schema

        body: dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": request.user_prompt}],
                }
            ],
            "generationConfig": generation_config,
        }

        if request.system_prompt:
            body["systemInstruction"] = {"parts": [{"text": request.system_prompt}]}

        url = f"{GEMINI_BASE_URL}/models/{actual_model}:generateContent"
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }

        client, should_close = await self._get_client(timeout=timeout)
        try:
            resp = await client.post(url, headers=headers, json=body)
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            if resp.status_code in (401, 403):
                sanitized_msg = self._sanitize(resp.text[:200])
                return LLMGenerationResult(
                    provider=self.provider_name,
                    requested_model=actual_model,
                    actual_model=actual_model,
                    operation_reference=request.operation_reference,
                    prompt_template_version=request.prompt_template_version,
                    duration_ms=duration_ms,
                    is_success=False,
                    error_type="INVALID_CREDENTIALS",
                    error_message=f"Gemini credentials invalid or forbidden: {sanitized_msg}",
                )

            if resp.status_code == 400:
                sanitized_msg = self._sanitize(resp.text[:200])
                return LLMGenerationResult(
                    provider=self.provider_name,
                    requested_model=actual_model,
                    actual_model=actual_model,
                    operation_reference=request.operation_reference,
                    prompt_template_version=request.prompt_template_version,
                    duration_ms=duration_ms,
                    is_success=False,
                    error_type="INVALID_REQUEST",
                    error_message=f"Gemini invalid request: {sanitized_msg}",
                )

            if resp.status_code == 404:
                return LLMGenerationResult(
                    provider=self.provider_name,
                    requested_model=actual_model,
                    actual_model=actual_model,
                    operation_reference=request.operation_reference,
                    prompt_template_version=request.prompt_template_version,
                    duration_ms=duration_ms,
                    is_success=False,
                    error_type="MODEL_UNAVAILABLE",
                    error_message=f"Gemini model '{actual_model}' not found or unsupported",
                )

            if resp.status_code == 429:
                return LLMGenerationResult(
                    provider=self.provider_name,
                    requested_model=actual_model,
                    actual_model=actual_model,
                    operation_reference=request.operation_reference,
                    prompt_template_version=request.prompt_template_version,
                    duration_ms=duration_ms,
                    is_success=False,
                    error_type="QUOTA_EXHAUSTED",
                    error_message="Gemini API quota exhausted or rate limit reached",
                )

            if resp.status_code != 200:
                sanitized_body = self._sanitize(resp.text[:250])
                return LLMGenerationResult(
                    provider=self.provider_name,
                    requested_model=actual_model,
                    actual_model=actual_model,
                    operation_reference=request.operation_reference,
                    prompt_template_version=request.prompt_template_version,
                    duration_ms=duration_ms,
                    is_success=False,
                    error_type="GENERAL_ERROR",
                    error_message=f"Gemini API returned status {resp.status_code}: {sanitized_body}",
                )

            data = resp.json()

            # Safety blocked responses
            prompt_feedback = data.get("promptFeedback", {})
            if prompt_feedback.get("blockReason"):
                return LLMGenerationResult(
                    provider=self.provider_name,
                    requested_model=actual_model,
                    actual_model=actual_model,
                    operation_reference=request.operation_reference,
                    prompt_template_version=request.prompt_template_version,
                    duration_ms=duration_ms,
                    is_success=False,
                    error_type="SAFETY_BLOCKED",
                    error_message=f"Gemini request blocked by safety filter: {prompt_feedback.get('blockReason')}",
                )

            candidates = data.get("candidates", [])
            if not candidates:
                return LLMGenerationResult(
                    provider=self.provider_name,
                    requested_model=actual_model,
                    actual_model=actual_model,
                    operation_reference=request.operation_reference,
                    prompt_template_version=request.prompt_template_version,
                    duration_ms=duration_ms,
                    is_success=False,
                    error_type="EMPTY_CANDIDATES",
                    error_message="Gemini returned no candidates in response",
                )

            candidate = candidates[0]
            finish_reason = candidate.get("finishReason", "")
            if finish_reason == "SAFETY":
                return LLMGenerationResult(
                    provider=self.provider_name,
                    requested_model=actual_model,
                    actual_model=actual_model,
                    operation_reference=request.operation_reference,
                    prompt_template_version=request.prompt_template_version,
                    duration_ms=duration_ms,
                    is_success=False,
                    error_type="SAFETY_BLOCKED",
                    error_message="Gemini candidate output blocked by safety filter",
                )

            parts = candidate.get("content", {}).get("parts", [])
            raw_text = "".join(p.get("text", "") for p in parts).strip()

            # Parse usage telemetry
            usage_meta = data.get("usageMetadata", {})
            prompt_tokens = usage_meta.get("promptTokenCount")
            candidate_tokens = usage_meta.get("candidatesTokenCount")
            total_tokens = usage_meta.get("totalTokenCount")
            usage = LLMUsageMetadata(
                prompt_tokens=prompt_tokens,
                completion_tokens=candidate_tokens,
                total_tokens=total_tokens,
                is_usage_known=(
                    prompt_tokens is not None and candidate_tokens is not None
                ),
            )

            # If structured output expected, parse JSON
            structured_data = None
            if request.response_schema is not None:
                try:
                    structured_data = json.loads(raw_text)
                except json.JSONDecodeError as err:
                    return LLMGenerationResult(
                        provider=self.provider_name,
                        requested_model=actual_model,
                        actual_model=actual_model,
                        operation_reference=request.operation_reference,
                        prompt_template_version=request.prompt_template_version,
                        raw_text=raw_text,
                        duration_ms=duration_ms,
                        is_success=False,
                        error_type="INVALID_OUTPUT",
                        error_message=f"Gemini output failed JSON parsing: {err}",
                        usage=usage,
                    )

            return LLMGenerationResult(
                provider=self.provider_name,
                requested_model=actual_model,
                actual_model=actual_model,
                operation_reference=request.operation_reference,
                prompt_template_version=request.prompt_template_version,
                generation_settings={
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                },
                raw_text=raw_text,
                structured_data=structured_data,
                usage=usage,
                duration_ms=round(duration_ms, 2),
                is_success=True,
            )

        except httpx.TimeoutException:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return LLMGenerationResult(
                provider=self.provider_name,
                requested_model=actual_model,
                actual_model=actual_model,
                operation_reference=request.operation_reference,
                prompt_template_version=request.prompt_template_version,
                duration_ms=duration_ms,
                is_success=False,
                error_type="TIMEOUT",
                error_message=f"Gemini request timed out after {timeout} seconds",
            )
        except Exception as exc:  # noqa: BLE001
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            sanitized = self._sanitize(str(exc))
            return LLMGenerationResult(
                provider=self.provider_name,
                requested_model=actual_model,
                actual_model=actual_model,
                operation_reference=request.operation_reference,
                prompt_template_version=request.prompt_template_version,
                duration_ms=duration_ms,
                is_success=False,
                error_type="GENERAL_ERROR",
                error_message=f"Gemini request error: {sanitized}",
            )
        finally:
            if should_close:
                await client.aclose()
