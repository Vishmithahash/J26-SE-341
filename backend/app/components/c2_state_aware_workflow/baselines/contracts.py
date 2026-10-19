"""Re-export baseline contracts for compatibility with baselines package."""

from app.components.c2_state_aware_workflow.contracts.baseline import (
    BaselinePredictionContract,
    BaselineType,
    EvidenceProjectionType,
)

__all__ = [
    "BaselinePredictionContract",
    "BaselineType",
    "EvidenceProjectionType",
]
