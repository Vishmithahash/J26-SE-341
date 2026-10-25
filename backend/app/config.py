from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

ENV_FILE_PATH = Path(__file__).resolve().parent.parent / ".env"

SUPPORTED_SCHEMES = {"postgresql", "postgres", "postgresql+psycopg"}
ALLOWED_SSLMODES = {"require", "verify-ca", "verify-full"}
DISALLOWED_SSLMODES = {"disable", "allow", "prefer"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_name: str = Field(default="Agentic AI QA Framework API", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    database_url: SecretStr = Field(..., alias="DATABASE_URL")
    auth_secret_key: SecretStr = Field(default=SecretStr(""), alias="AUTH_SECRET_KEY")
    auth_jwt_algorithm: str = Field(default="HS256", alias="AUTH_JWT_ALGORITHM")
    auth_access_token_expire_minutes: int = Field(
        default=15, alias="AUTH_ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    auth_jwt_issuer: str | None = Field(default=None, alias="AUTH_JWT_ISSUER")
    auth_jwt_audience: str | None = Field(default=None, alias="AUTH_JWT_AUDIENCE")

    # LLM Provider Configuration
    # Hosted Gemini consumes credits; it is never called unless explicitly enabled.
    gemini_enabled: bool = Field(default=False, alias="GEMINI_ENABLED")
    gemini_api_key: SecretStr = Field(default=SecretStr(""), alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3.5-flash-lite", alias="GEMINI_MODEL")
    ollama_base_url: str = Field(default="http://127.0.0.1:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen3.5:4b", alias="OLLAMA_MODEL")
    # Defaults applied when neither the caller nor the user's saved selection sets a limit.
    llm_default_timeout_seconds: float = Field(
        default=180.0, gt=0, le=900, alias="LLM_DEFAULT_TIMEOUT_SECONDS"
    )
    llm_default_max_tokens: int = Field(
        default=2048, ge=16, le=32768, alias="LLM_DEFAULT_MAX_TOKENS"
    )

    # NexaCart application under test (external QA harness, see NexaCart src/qa/harness)
    nexacart_base_url: str = Field(
        default="http://localhost:3000/api/v1", alias="NEXACART_BASE_URL"
    )
    nexacart_qa_admin_email: str = Field(default="", alias="NEXACART_QA_ADMIN_EMAIL")
    nexacart_qa_admin_password: SecretStr = Field(
        default=SecretStr(""), alias="NEXACART_QA_ADMIN_PASSWORD"
    )
    # Must exceed NexaCart's AGENT_RUN_TIMEOUT_MS because one call waits for a whole agent run.
    nexacart_agent_run_timeout_seconds: float = Field(
        default=400.0, gt=0, le=1800, alias="NEXACART_AGENT_RUN_TIMEOUT_SECONDS"
    )
    # NexaCart backend root (read-only): C1 code-level diagnosis of NexaCart tool code and the
    # source of disposable copies for candidate-correction verification. Empty = unavailable.
    nexacart_source_root: str = Field(default="", alias="NEXACART_SOURCE_ROOT")
    # C1 candidate code correction + sandbox verification (defect lab). Off by default: the
    # progress-presentation-1 build shows the testing and explanation workflow only.
    c1_code_correction_enabled: bool = Field(
        default=False, alias="C1_CODE_CORRECTION_ENABLED"
    )

    @field_validator("database_url", mode="after")
    @classmethod
    def validate_database_url(cls, v: SecretStr) -> SecretStr:
        secret_val = v.get_secret_value().strip()
        if not secret_val:
            raise ValueError("DATABASE_URL must not be empty.")

        try:
            parsed = make_url(secret_val)
        except (ArgumentError, ValueError, Exception):  # noqa: BLE001
            raise ValueError("DATABASE_URL is malformed.") from None

        if parsed.drivername not in SUPPORTED_SCHEMES:
            raise ValueError(
                f"Unsupported database scheme '{parsed.drivername}'. Scheme must be postgresql, postgres, or postgresql+psycopg."
            )

        sslmode = parsed.query.get("sslmode", "").lower()
        if sslmode in DISALLOWED_SSLMODES:
            raise ValueError(
                f"Insecure sslmode '{sslmode}' is not permitted. Require 'require', 'verify-ca', or 'verify-full'."
            )
        if sslmode and sslmode not in ALLOWED_SSLMODES:
            raise ValueError(f"Unsupported sslmode '{sslmode}'.")

        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
