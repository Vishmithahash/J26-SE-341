"""Ollama provider adapter for local Qwen model inference."""

import json
import re
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
from app.shared.llm.schema_validator import validate_structured_schema

THINK_REGEX = re.compile(r"<think>.*?</think>", re.DOTALL)


class OllamaAdapter(BaseLLMAdapter):
    """Adapter for native Ollama API endpoints."""

    def __init__(
        self,
        base_url: str | None = None,
        default_model: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.default_model = default_model or settings.ollama_model
        self._external_client = http_client

    @property
    def provider_name(self) -> str:
        return LLMProviderType.OLLAMA.value

    async def _get_client(self, timeout: float) -> tuple[httpx.AsyncClient, bool]:
        if self._external_client is not None:
            return self._external_client, False
        return httpx.AsyncClient(base_url=self.base_url, timeout=timeout), True

    async def check_availability(
        self, model_id: str | None = None
    ) -> ProviderStatusInfo:
        """Query /api/tags to detect reachable Ollama daemon and discover installed Qwen models."""
        target_model = (model_id or self.default_model).strip()
        client, should_close = await self._get_client(timeout=5.0)
        try:
            resp = await client.get(f"{self.base_url}/api/tags")
            if resp.status_code != 200:
                return ProviderStatusInfo(
                    provider=self.provider_name,
                    connection_type=ConnectionType.LOCAL.value,
                    is_configured=True,
                    is_available=False,
                    configured_default_model=self.default_model,
                    available_models=[],
                    status_message=f"Ollama returned HTTP {resp.status_code}: {resp.text[:120]}",
                    last_checked_at=datetime.now(UTC),
                )

            data = resp.json()
            models_list = data.get("models", [])
            installed_names = [m.get("name", "") for m in models_list if m.get("name")]

            # Filter for installed Qwen models or permitted models
            qwen_models = [m for m in installed_names if "qwen" in m.lower()]
            if not qwen_models:
                # Still record installed models for visibility
                qwen_models = installed_names

            is_target_installed = any(
                target_model == name
                or (":" not in target_model and name == f"{target_model}:latest")
                for name in installed_names
            )

            status_msg = (
                f"Ollama active with {len(qwen_models)} installed model(s)"
                if is_target_installed
                else f"Ollama is running, but model '{target_model}' is not installed. Run: ollama pull {target_model}"
            )

            return ProviderStatusInfo(
                provider=self.provider_name,
                connection_type=ConnectionType.LOCAL.value,
                is_configured=True,
                is_available=is_target_installed,
                configured_default_model=self.default_model,
                available_models=qwen_models,
                status_message=status_msg,
                last_checked_at=datetime.now(UTC),
            )
        except (httpx.ConnectError, httpx.ConnectTimeout):
            return ProviderStatusInfo(
                provider=self.provider_name,
                connection_type=ConnectionType.LOCAL.value,
                is_configured=True,
                is_available=False,
                configured_default_model=self.default_model,
                available_models=[],
                status_message=f"Ollama is not running or unreachable at {self.base_url}",
                last_checked_at=datetime.now(UTC),
            )
        except Exception as exc:  # noqa: BLE001
            return ProviderStatusInfo(
                provider=self.provider_name,
                connection_type=ConnectionType.LOCAL.value,
                is_configured=True,
                is_available=False,
                configured_default_model=self.default_model,
                available_models=[],
                status_message=f"Ollama availability check failed: {exc}",
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
        """Call Ollama native /api/chat with non-streaming, bounded parameters."""
        actual_model = model_override or self.default_model
        start_time = time.perf_counter()
        timeout = request.timeout_seconds

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.user_prompt})

        options: dict[str, Any] = {
            "temperature": request.temperature,
            "num_predict": request.max_tokens,
        }
        if request.top_p is not None:
            options["top_p"] = request.top_p

        body: dict[str, Any] = {
            "model": actual_model,
            "messages": messages,
            "stream": False,
            "options": options,
        }

        # Bounded structured format
        if request.response_schema is not None:
            body["format"] = request.response_schema

        client, should_close = await self._get_client(timeout=timeout)
        try:
            resp = await client.post(f"{self.base_url}/api/chat", json=body)
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            if resp.status_code == 404:
                return LLMGenerationResult(
                    provider=self.provider_name,
                    requested_model=actual_model,
                    actual_model=actual_model,
                    operation_reference=request.operation_reference,
                    prompt_template_version=request.prompt_template_version,
                    duration_ms=duration_ms,
                    is_success=False,
                    error_type="MODEL_NOT_INSTALLED",
                    error_message=f"Model '{actual_model}' is not installed in Ollama. Run: ollama pull {actual_model}",
                )

            if resp.status_code != 200:
                return LLMGenerationResult(
                    provider=self.provider_name,
                    requested_model=actual_model,
                    actual_model=actual_model,
                    operation_reference=request.operation_reference,
                    prompt_template_version=request.prompt_template_version,
                    duration_ms=duration_ms,
                    is_success=False,
                    error_type="GENERAL_ERROR",
                    error_message=f"Ollama returned HTTP {resp.status_code}: {resp.text[:200]}",
                )

            data = resp.json()

            # Parse usage telemetry
            prompt_eval = data.get("prompt_eval_count")
            eval_count = data.get("eval_count")
            usage = LLMUsageMetadata(
                prompt_tokens=prompt_eval,
                completion_tokens=eval_count,
                total_tokens=(prompt_eval + eval_count)
                if (prompt_eval is not None and eval_count is not None)
                else None,
                is_usage_known=(prompt_eval is not None and eval_count is not None),
            )

            # Check completion status and truncation
            done = data.get("done", True)
            done_reason = data.get("done_reason")
            if not done or done_reason == "length":
                raw_content = data.get("message", {}).get("content", "")
                cleaned_text = THINK_REGEX.sub("", raw_content).strip()
                return LLMGenerationResult(
                    provider=self.provider_name,
                    requested_model=actual_model,
                    actual_model=actual_model,
                    operation_reference=request.operation_reference,
                    prompt_template_version=request.prompt_template_version,
                    duration_ms=duration_ms,
                    is_success=False,
                    error_type="INCOMPLETE_OUTPUT",
                    error_message=f"Model response was truncated by provider (done_reason={done_reason or 'length'}).",
                    raw_text=cleaned_text,
                    usage=usage,
                )

            raw_content = data.get("message", {}).get("content", "")

            # Handle Qwen <think> reasoning: Strip internal thought tokens from answer
            cleaned_text = THINK_REGEX.sub("", raw_content).strip()

            if not cleaned_text:
                return LLMGenerationResult(
                    provider=self.provider_name,
                    requested_model=actual_model,
                    actual_model=actual_model,
                    operation_reference=request.operation_reference,
                    prompt_template_version=request.prompt_template_version,
                    duration_ms=duration_ms,
                    is_success=False,
                    error_type="EMPTY_OUTPUT",
                    error_message="Model returned empty text output.",
                    raw_text="",
                    usage=usage,
                )

            # If structured output expected, parse and validate JSON
            structured_data = None
            if request.response_schema is not None:
                try:
                    structured_data = json.loads(cleaned_text)
                except json.JSONDecodeError as err:
                    return LLMGenerationResult(
                        provider=self.provider_name,
                        requested_model=actual_model,
                        actual_model=actual_model,
                        operation_reference=request.operation_reference,
                        prompt_template_version=request.prompt_template_version,
                        raw_text=cleaned_text,
                        duration_ms=duration_ms,
                        is_success=False,
                        error_type="INVALID_OUTPUT",
                        error_message=f"Model output failed JSON parsing: {err}",
                        usage=usage,
                    )
                is_valid_schema, schema_err = validate_structured_schema(
                    structured_data, request.response_schema
                )
                if not is_valid_schema:
                    return LLMGenerationResult(
                        provider=self.provider_name,
                        requested_model=actual_model,
                        actual_model=actual_model,
                        operation_reference=request.operation_reference,
                        prompt_template_version=request.prompt_template_version,
                        raw_text=cleaned_text,
                        duration_ms=duration_ms,
                        is_success=False,
                        error_type="INVALID_SCHEMA",
                        error_message=f"Model output violates required schema: {schema_err}",
                        usage=usage,
                    )

            applied_settings = {
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
            }
            if request.top_p is not None:
                applied_settings["top_p"] = request.top_p

            return LLMGenerationResult(
                provider=self.provider_name,
                requested_model=actual_model,
                actual_model=actual_model,
                operation_reference=request.operation_reference,
                prompt_template_version=request.prompt_template_version,
                generation_settings=applied_settings,
                raw_text=cleaned_text,
                structured_data=structured_data,
                usage=usage,
                duration_ms=round(duration_ms, 2),
                is_success=True,
            )

        except (httpx.ConnectError, httpx.ConnectTimeout):
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return LLMGenerationResult(
                provider=self.provider_name,
                requested_model=actual_model,
                actual_model=actual_model,
                operation_reference=request.operation_reference,
                prompt_template_version=request.prompt_template_version,
                duration_ms=duration_ms,
                is_success=False,
                error_type="SERVICE_UNREACHABLE",
                error_message=f"Ollama is not running or unreachable at {self.base_url}",
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
                error_message=f"Ollama request timed out after {timeout} seconds",
            )
        except Exception as exc:  # noqa: BLE001
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return LLMGenerationResult(
                provider=self.provider_name,
                requested_model=actual_model,
                actual_model=actual_model,
                operation_reference=request.operation_reference,
                prompt_template_version=request.prompt_template_version,
                duration_ms=duration_ms,
                is_success=False,
                error_type="GENERAL_ERROR",
                error_message=f"Ollama invocation error: {exc}",
            )
        finally:
            if should_close:
                await client.aclose()
