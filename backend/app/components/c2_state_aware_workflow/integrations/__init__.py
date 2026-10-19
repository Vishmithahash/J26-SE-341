"""Integrations package for C2."""

from app.components.c2_state_aware_workflow.integrations.interfaces import (
    AgentExecutionInterface,
    EvidenceIngestionInterface,
    FixtureResetInterface,
    IntegrationStatus,
    LocalSyntheticFixtureManager,
    LocalSyntheticStateObserver,
    SharedIntakeInterface,
    StateObservationInterface,
    UnifiedReportingInterface,
)

__all__ = [
    "AgentExecutionInterface",
    "EvidenceIngestionInterface",
    "FixtureResetInterface",
    "IntegrationStatus",
    "LocalSyntheticFixtureManager",
    "LocalSyntheticStateObserver",
    "SharedIntakeInterface",
    "StateObservationInterface",
    "UnifiedReportingInterface",
]
