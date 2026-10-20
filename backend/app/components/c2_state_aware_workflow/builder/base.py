"""Abstract interface for optional model-assisted (LLM) builders."""

from abc import ABC, abstractmethod

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)
from app.components.c2_state_aware_workflow.contracts.workflow_input import (
    WorkflowInputContract,
)


class ModelAssistedProvider(ABC):
    """Abstract provider for optional LLM-assisted workflow candidate proposal.

    Core C2 functionality operates deterministically without requiring
    paid LLM credentials.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if credentials and network connectivity are available."""

    @abstractmethod
    def propose_model(
        self, workflow_input: WorkflowInputContract
    ) -> EFSMModelDefinition:
        """Propose a candidate EFSM from workflow requirements using LLM assistance."""
