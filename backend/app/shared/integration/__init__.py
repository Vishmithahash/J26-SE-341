"""Shared Integration Foundation package.

Component: Shared Integration Foundation (Part 1)
"""

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
from app.shared.integration.models import (
    IntegrationArtifactReferenceModel,
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
    "CorrelationMapping",
    "IntegrationArtifactReferenceModel",
    "IntegrationIdentifierMappingModel",
    "IntegrationPlanListResponse",
    "IntegrationPlanStatus",
    "IntegrationReadinessReport",
    "IntegrationRunPlanCreateRequest",
    "IntegrationRunPlanModel",
    "IntegrationRunPlanResponse",
    "IntegrationService",
    "NativeEntityType",
    "ReadinessIssueCode",
    "ReadinessSeverity",
    "ReadinessVerdict",
    "router",
]
