"""Pydantic request and response schemas for Shared Projects Workspace.

Component: Shared Projects Workspace
"""

from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


def validate_http_url(url: str, field_name: str) -> str:
    """Validate that a URL string has http/https scheme and no embedded credentials."""
    trimmed = url.strip()
    if not trimmed:
        raise ValueError(f"{field_name} must not be empty.")

    parsed = urlparse(trimmed)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError(f"{field_name} must use http or https scheme.")

    if not parsed.netloc:
        raise ValueError(f"{field_name} is missing a host.")

    if parsed.username or parsed.password:
        raise ValueError(f"{field_name} must not contain embedded credentials (username/password).")

    return trimmed


class InputReferenceCreateRequest(BaseModel):
    """Payload to register an input reference."""

    category: str = Field(..., min_length=2, max_length=64)
    label: str = Field(..., min_length=2, max_length=255)
    reference_location: str = Field(..., min_length=1, max_length=2048)
    version: str = Field(default="1.0.0", min_length=1, max_length=64)


class InputReferenceResponse(BaseModel):
    """Public representation of an input reference record."""

    model_config = ConfigDict(from_attributes=True)

    reference_id: str
    project_id: str
    category: str
    label: str
    reference_location: str
    version: str
    registered_at_utc: datetime


class ProjectCreateRequest(BaseModel):
    """Payload for registering a new application project."""

    name: str = Field(..., min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    domain: str = Field(default="custom", max_length=64)
    environment: str = Field(default="development", max_length=32)
    backend_base_url: str = Field(..., max_length=1024)
    backend_health_url: str = Field(..., max_length=1024)
    agent_endpoint: str | None = Field(default=None, max_length=1024)
    agent_health_url: str | None = Field(default=None, max_length=1024)
    repository_url: str | None = Field(default=None, max_length=1024)
    initial_inputs: list[InputReferenceCreateRequest] = Field(default_factory=list)

    @field_validator("backend_base_url")
    @classmethod
    def validate_backend_base(cls, v: str) -> str:
        return validate_http_url(v, "backend_base_url")

    @field_validator("backend_health_url")
    @classmethod
    def validate_backend_health(cls, v: str) -> str:
        return validate_http_url(v, "backend_health_url")

    @field_validator("agent_endpoint")
    @classmethod
    def validate_agent_endpoint(cls, v: str | None) -> str | None:
        if v and v.strip():
            return validate_http_url(v, "agent_endpoint")
        return None

    @field_validator("agent_health_url")
    @classmethod
    def validate_agent_health(cls, v: str | None) -> str | None:
        if v and v.strip():
            return validate_http_url(v, "agent_health_url")
        return None


class ProjectUpdateRequest(BaseModel):
    """Payload for updating project details or connection configuration."""

    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    domain: str | None = Field(default=None, max_length=64)
    environment: str | None = Field(default=None, max_length=32)
    backend_base_url: str | None = Field(default=None, max_length=1024)
    backend_health_url: str | None = Field(default=None, max_length=1024)
    agent_endpoint: str | None = Field(default=None, max_length=1024)
    agent_health_url: str | None = Field(default=None, max_length=1024)
    repository_url: str | None = Field(default=None, max_length=1024)
    expected_version: int | None = Field(default=None)

    @field_validator("backend_base_url")
    @classmethod
    def validate_backend_base(cls, v: str | None) -> str | None:
        if v and v.strip():
            return validate_http_url(v, "backend_base_url")
        return None

    @field_validator("backend_health_url")
    @classmethod
    def validate_backend_health(cls, v: str | None) -> str | None:
        if v and v.strip():
            return validate_http_url(v, "backend_health_url")
        return None

    @field_validator("agent_endpoint")
    @classmethod
    def validate_agent_endpoint(cls, v: str | None) -> str | None:
        if v and v.strip():
            return validate_http_url(v, "agent_endpoint")
        return None

    @field_validator("agent_health_url")
    @classmethod
    def validate_agent_health(cls, v: str | None) -> str | None:
        if v and v.strip():
            return validate_http_url(v, "agent_health_url")
        return None


class OwnerSummary(BaseModel):
    """Safe owner user representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str


class ProjectResponse(BaseModel):
    """Detailed response for a registered project."""

    model_config = ConfigDict(from_attributes=True)

    project_id: str
    owner_user_id: int
    owner: OwnerSummary | None = None
    name: str
    description: str | None = None
    domain: str
    environment: str
    backend_base_url: str
    backend_health_url: str
    agent_endpoint: str | None = None
    agent_health_url: str | None = None
    repository_url: str | None = None
    configuration_version: int
    lifecycle: str
    connection_state: str
    last_check_timestamp: datetime | None = None
    last_successful_check_timestamp: datetime | None = None
    created_at_utc: datetime
    updated_at_utc: datetime
    input_references_count: int = 0


class ProjectListResponse(BaseModel):
    """Paginated project listing."""

    items: list[ProjectResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ProjectHistoryEventResponse(BaseModel):
    """Audit and state transition event log entry."""

    model_config = ConfigDict(from_attributes=True)

    event_id: str
    project_id: str
    acting_account_id: int
    acting_account_email: str | None = None
    timestamp_utc: datetime
    configuration_version: int
    event_type: str
    previous_state: dict | None = None
    resulting_state: dict | None = None
    safe_details: dict | None = None


class ProjectHistoryListResponse(BaseModel):
    """Paginated event history log."""

    items: list[ProjectHistoryEventResponse]
    total: int
    page: int
    page_size: int


class EndpointCheckOutcome(BaseModel):
    """Individual probe outcome for backend or agent endpoints."""

    configured: bool
    target_url: str | None = None
    status_code: int | None = None
    latency_ms: float | None = None
    reachable: bool = False
    auth_required: bool = False
    invalid_configuration: bool = False
    sanitized_error: str | None = None


class ConnectionCheckResponse(BaseModel):
    """Overall result of a backend-initiated connection check."""

    project_id: str
    configuration_version: int
    checked_at_utc: datetime
    connection_state: str
    backend_outcome: EndpointCheckOutcome
    agent_outcome: EndpointCheckOutcome
    summary: str
