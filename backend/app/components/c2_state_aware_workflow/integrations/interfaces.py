"""Integration interfaces and adapter stubs for C2.

Provides typed interfaces for shared intake, fixture reset, agent execution,
state observation, evidence ingestion, and unified reporting.
Stubs clearly document unavailable shared services without simulating
unverified live connections.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from app.components.c2_state_aware_workflow.contracts.evaluation_result import (
    EvaluationResultContract,
)
from app.components.c2_state_aware_workflow.contracts.runtime_evidence import (
    RuntimeEvidenceContract,
)
from app.components.c2_state_aware_workflow.contracts.workflow_input import (
    WorkflowInputContract,
)


class IntegrationStatus(str, Enum):
    CONNECTED = "CONNECTED"
    LOCAL_SYNTHETIC = "LOCAL_SYNTHETIC"
    STUB_PENDING_SHARED_SERVICE = "STUB_PENDING_SHARED_SERVICE"


class SharedIntakeInterface(ABC):
    """Interface to shared project intake service for requirements and specifications."""

    status: IntegrationStatus = IntegrationStatus.STUB_PENDING_SHARED_SERVICE

    @abstractmethod
    def fetch_workflow_specification(
        self, project_id: str, workflow_id: str
    ) -> WorkflowInputContract | None:
        pass


class FixtureResetInterface(ABC):
    """Interface to shared fixture manager to reset environment to clean starting state."""

    status: IntegrationStatus = IntegrationStatus.LOCAL_SYNTHETIC

    @abstractmethod
    def reset_fixture(
        self, fixture_ref: str, seed: int | None = None
    ) -> dict[str, Any]:
        pass


class AgentExecutionInterface(ABC):
    """Interface to shared agent execution runner."""

    status: IntegrationStatus = IntegrationStatus.STUB_PENDING_SHARED_SERVICE

    @abstractmethod
    def execute_agent_task(
        self,
        task_prompt: str,
        available_tools: list[str],
        fixture_context: dict[str, Any],
    ) -> str:
        pass


class StateObservationInterface(ABC):
    """Interface for capturing intermediate and before/after application state."""

    status: IntegrationStatus = IntegrationStatus.LOCAL_SYNTHETIC

    @abstractmethod
    def capture_snapshot(self, entity_identifiers: dict[str, Any]) -> dict[str, Any]:
        pass


class EvidenceIngestionInterface(ABC):
    """Interface for ingesting runtime traces and state evidence for C2 evaluation."""

    status: IntegrationStatus = IntegrationStatus.LOCAL_SYNTHETIC

    @abstractmethod
    def ingest_evidence(self, evidence: RuntimeEvidenceContract) -> str:
        pass


class UnifiedReportingInterface(ABC):
    """Interface to publish C2 findings to the shared multi-component QA report."""

    status: IntegrationStatus = IntegrationStatus.STUB_PENDING_SHARED_SERVICE

    @abstractmethod
    def publish_component_finding(self, evaluation: EvaluationResultContract) -> str:
        pass


# Local synthetic implementations for local verification and testing


class LocalSyntheticFixtureManager(FixtureResetInterface):
    """Local synthetic fixture manager for reproducible testing."""

    def __init__(self, fixtures: dict[str, dict[str, Any]] | None = None):
        self._fixtures = dict(fixtures) if fixtures else {}

    def register_fixture(self, fixture_id: str, initial_state: dict[str, Any]) -> None:
        self._fixtures[fixture_id] = initial_state

    def reset_fixture(
        self, fixture_ref: str, seed: int | None = None
    ) -> dict[str, Any]:
        if fixture_ref in self._fixtures:
            # Return deep-copy-like dictionary
            return dict(self._fixtures[fixture_ref])
        return {"fixture_ref": fixture_ref, "status": "reset", "seed": seed}


class LocalSyntheticStateObserver(StateObservationInterface):
    """Local synthetic state observer for inspecting observable application entities."""

    def __init__(self, state_store: dict[str, Any] | None = None):
        self._state_store = dict(state_store) if state_store else {}

    def set_entity_state(
        self, entity_type: str, entity_id: Any, state: dict[str, Any]
    ) -> None:
        self._state_store.setdefault(entity_type, {})[str(entity_id)] = state

    def capture_snapshot(self, entity_identifiers: dict[str, Any]) -> dict[str, Any]:
        snapshot: dict[str, Any] = {}
        for entity_type, entity_id in entity_identifiers.items():
            if (
                entity_type in self._state_store
                and str(entity_id) in self._state_store[entity_type]
            ):
                snapshot[entity_type] = dict(
                    self._state_store[entity_type][str(entity_id)]
                )
        return snapshot
