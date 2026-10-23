"""Shared Integration Foundation package.

Component: Shared Integration Foundation (Part 1)
"""

from app.shared.integration.adapters import (
    ControlledTestTargetAdapter,
    LiveNexaCartTargetAdapter,
    TargetMode,
    TargetReadinessStatus,
)
from app.shared.integration.contracts import (
    C1ConfigReference,
    C2ModelReference,
    C3SuiteReference,
    C4PolicyReference,
    ComponentReadinessIssue,
    ComponentReadinessSummary,
    ComponentReferencesPlan,
    ComponentType,
    CorrelationMapping,
    ExecutionListResponse,
    ExecutionStartRequest,
    ExecutionStatusResponse,
    IntegrationPlanListResponse,
    IntegrationPlanStatus,
    IntegrationReadinessReport,
    IntegrationRunPlanCreateRequest,
    IntegrationRunPlanResponse,
    NativeEntityType,
    ReadinessIssueCode,
    ReadinessSeverity,
    ReadinessVerdict,
)
from app.shared.integration.executor import SharedExecutionCoordinator
from app.shared.integration.models import (
    IntegrationArtifactReferenceModel,
    IntegrationExecutionModel,
    IntegrationIdentifierMappingModel,
    IntegrationRunPlanModel,
)
from app.shared.integration.router import router
from app.shared.integration.service import IntegrationService

__all__ = [
    "C1ConfigReference",
    "C2ModelReference",
    "C3SuiteReference",
    "C4PolicyReference",
    "ComponentReadinessIssue",
    "ComponentReadinessSummary",
    "ComponentReferencesPlan",
    "ComponentType",
    "ControlledTestTargetAdapter",
    "CorrelationMapping",
    "ExecutionListResponse",
    "ExecutionStartRequest",
    "ExecutionStatusResponse",
    "IntegrationArtifactReferenceModel",
    "IntegrationExecutionModel",
    "IntegrationIdentifierMappingModel",
    "IntegrationPlanListResponse",
    "IntegrationPlanStatus",
    "IntegrationReadinessReport",
    "IntegrationRunPlanCreateRequest",
    "IntegrationRunPlanModel",
    "IntegrationRunPlanResponse",
    "IntegrationService",
    "LiveNexaCartTargetAdapter",
    "NativeEntityType",
    "ReadinessIssueCode",
    "ReadinessSeverity",
    "ReadinessVerdict",
    "SharedExecutionCoordinator",
    "TargetMode",
    "TargetReadinessStatus",
    "router",
]
