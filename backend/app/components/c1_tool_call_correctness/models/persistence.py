import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base


class C1ProjectConfigModel(Base):
    """Persisted Component 1 project configuration version and tool/requirement snapshot."""

    __tablename__ = "c1_project_configs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    agent_connection_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    tools: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    requirements: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    tool_constraints: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    expectations: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    synthetic_fixture_refs: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    reset_capability: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    trace_capabilities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    suite_versions = relationship(
        "C1SuiteVersionModel",
        back_populates="config",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_c1_project_config_version"),
    )


class C1SuiteVersionModel(Base):
    """Accepted and immutable collection of test cases bound to a configuration snapshot."""

    __tablename__ = "c1_suite_versions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    suite_id: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    config_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("c1_project_configs.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cases: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    config = relationship("C1ProjectConfigModel", back_populates="suite_versions")

    __table_args__ = (
        UniqueConstraint(
            "project_id", "suite_id", "version", name="uq_c1_suite_version"
        ),
    )
