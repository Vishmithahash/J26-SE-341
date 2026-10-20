"""Configuration settings for Shared Projects connection handling and security policies.

Component: Shared Projects Workspace
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE_PATH = Path(__file__).resolve().parent.parent.parent.parent / ".env"


class ProjectSettings(BaseSettings):
    """Outbound connection policies and security controls for project verification."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    projects_allowed_origins: str = Field(
        default="http://localhost:8000,http://127.0.0.1:8000,http://localhost:8001,http://127.0.0.1:8001,http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
        alias="PROJECTS_ALLOWED_ORIGINS",
    )
    connection_timeout_seconds: float = Field(
        default=5.0,
        alias="PROJECTS_CONNECTION_TIMEOUT",
    )
    max_response_bytes: int = Field(
        default=10240,
        alias="PROJECTS_MAX_RESPONSE_BYTES",
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parsed list of allowed origin strings without surrounding whitespace."""
        return [
            item.strip()
            for item in self.projects_allowed_origins.split(",")
            if item.strip()
        ]


@lru_cache
def get_project_settings() -> ProjectSettings:
    """Cached singleton for project configuration settings."""
    return ProjectSettings()
