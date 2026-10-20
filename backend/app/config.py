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
