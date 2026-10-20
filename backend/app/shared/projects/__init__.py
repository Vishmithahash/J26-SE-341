"""Shared Projects Module - Application Registration & Connection Management.

Component: Shared Projects Workspace
"""

from app.shared.projects.models import (
    Project,
    ProjectConnectionState,
    ProjectDomain,
    ProjectEnvironment,
    ProjectHistoryEvent,
    ProjectHistoryEventType,
    ProjectInputReference,
    ProjectLifecycle,
)
from app.shared.projects.router import router

__all__ = [
    "Project",
    "ProjectConnectionState",
    "ProjectDomain",
    "ProjectEnvironment",
    "ProjectHistoryEvent",
    "ProjectHistoryEventType",
    "ProjectInputReference",
    "ProjectLifecycle",
    "router",
]
