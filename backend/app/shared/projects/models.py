"""SQLAlchemy ORM models for Shared Projects, Input References, and Event History.

Component: Shared Projects Workspace
"""

import uuid
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProjectLifecycle(str, Enum):
    """Lifecycle status of a registered project."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class ProjectConnectionState(str, Enum):
    """Honest connection verification states."""

    NOT_CHECKED = "NOT_CHECKED"
    CONNECTED = "CONNECTED"
    PARTIAL = "PARTIAL"
    UNREACHABLE = "UNREACHABLE"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    DISCONNECTED = "DISCONNECTED"


class ProjectDomain(str, Enum):
    """Supported application business domains."""

    ECOMMERCE = "e-commerce"
    BOOKING = "booking"
    LEARNING_EXAMINATION = "learning/examination"
    CUSTOM = "custom"


class ProjectEnvironment(str, Enum):
    """Deployment tier of the connected target application."""

    DEVELOPMENT = "development"
    STAGING = "staging"


class ProjectHistoryEventType(str, Enum):
    """Append-only audit and state change event types."""

    PROJECT_CREATED = "PROJECT_CREATED"
    CONNECTION_SETTINGS_UPDATED = "CONNECTION_SETTINGS_UPDATED"
    PROJECT_UPDATED = "PROJECT_UPDATED"
    CONNECTION_CHECKED = "CONNECTION_CHECKED"
    DISCONNECTED = "DISCONNECTED"
    ARCHIVED = "ARCHIVED"
    RESTORED = "RESTORED"
    INPUT_REFERENCE_ADDED = "INPUT_REFERENCE_ADDED"


def generate_project_id(name: str) -> str:
    """Generate a stable, human-readable, collision-resistant project identifier.

    Compatible with existing string project identifiers used by components C1-C4.
    """
    clean_slug = "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-")[:20]
    random_suffix = uuid.uuid4().hex[:8]
    if clean_slug:
        return f"proj-{clean_slug}-{random_suffix}"
    return f"proj-{random_suffix}"


def generate_id(prefix: str = "ref") -> str:
    """Generate a unique identifier with a given prefix."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class Project(Base):
    """Shared application registration record."""

    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    owner_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=ProjectDomain.CUSTOM.value,
    )
    environment: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ProjectEnvironment.DEVELOPMENT.value,
    )
    backend_base_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    backend_health_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    agent_endpoint: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    agent_health_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    repository_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    configuration_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    lifecycle: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ProjectLifecycle.ACTIVE.value,
        index=True,
    )
    connection_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ProjectConnectionState.NOT_CHECKED.value,
        index=True,
    )
    last_check_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_successful_check_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    owner = relationship("User", foreign_keys=[owner_user_id], lazy="joined")
    input_references = relationship(
        "ProjectInputReference",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="desc(ProjectInputReference.registered_at_utc)",
        lazy="selectin",
    )
    history_events = relationship(
        "ProjectHistoryEvent",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="desc(ProjectHistoryEvent.timestamp_utc)",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Project(id={self.project_id!r}, name={self.name!r}, "
            f"owner={self.owner_user_id}, state={self.connection_state!r})>"
        )


class ProjectInputReference(Base):
    """Registered reference to project specifications, schemas, or requirements."""

    __tablename__ = "project_input_references"

    reference_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        index=True,
        default=lambda: generate_id("ref"),
    )
    project_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    reference_location: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False, default="1.0.0")
    registered_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    project = relationship("Project", back_populates="input_references")

    def __repr__(self) -> str:
        return (
            f"<ProjectInputReference(id={self.reference_id!r}, project={self.project_id!r}, "
            f"category={self.category!r}, label={self.label!r}, version={self.version!r})>"
        )


class ProjectHistoryEvent(Base):
    """Append-only audit trail and connection event record."""

    __tablename__ = "project_history_events"

    event_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        index=True,
        default=lambda: generate_id("evt"),
    )
    project_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    acting_account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    acting_account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timestamp_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    configuration_version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resulting_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    safe_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    project = relationship("Project", back_populates="history_events")

    def __repr__(self) -> str:
        return (
            f"<ProjectHistoryEvent(id={self.event_id!r}, project={self.project_id!r}, "
            f"type={self.event_type!r}, v={self.configuration_version})>"
        )
