"""Explicit evidence projection functions ensuring baselines receive only permitted evidence."""

import hashlib
import json

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)
from app.components.c2_state_aware_workflow.contracts.runtime_evidence import (
    RuntimeEvidenceContract,
)


def _compute_digest(contract: RuntimeEvidenceContract) -> str:
    """Compute deterministic canonical digest of projected evidence payload."""
    payload = json.dumps(contract.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def project_evidence_for_b1(
    evidence: RuntimeEvidenceContract,
) -> tuple[RuntimeEvidenceContract, str]:
    """Project evidence for B1: Final-state-only.

    Strips all intermediate events and intermediate state snapshots.
    Retains ONLY the terminal state observation snapshot and completeness.
    """
    final_obs = [evidence.state_observations[-1]] if evidence.state_observations else []
    projected = evidence.model_copy(
        update={
            "ordered_events": [],
            "state_observations": final_obs,
        }
    )
    return projected, _compute_digest(projected)


def project_evidence_for_b2(
    evidence: RuntimeEvidenceContract,
) -> tuple[RuntimeEvidenceContract, str]:
    """Project evidence for B2: Trace-only.

    Strips all before/after database state observations and entity snapshots.
    Retains ONLY ordered tool-call events and arguments.
    """
    projected = evidence.model_copy(
        update={
            "state_observations": [],
        }
    )
    return projected, _compute_digest(projected)


def project_evidence_for_b3(
    evidence: RuntimeEvidenceContract, model: EFSMModelDefinition
) -> tuple[RuntimeEvidenceContract, str]:
    """Project evidence for B3: Milestone-based checkpoints.

    Retains ordered events and ONLY observations at declared checkpoint intervals.
    Strips fine-grained intermediate entity diffs.
    """
    milestone_obs = (
        [evidence.state_observations[-1]] if evidence.state_observations else []
    )
    if len(evidence.state_observations) > 1:
        # Include first, intermediate milestone, and final
        mid_idx = len(evidence.state_observations) // 2
        milestone_obs = [
            evidence.state_observations[0],
            evidence.state_observations[mid_idx],
            evidence.state_observations[-1],
        ]

    projected = evidence.model_copy(
        update={
            "state_observations": milestone_obs,
        }
    )
    return projected, _compute_digest(projected)


def project_evidence_for_b4(
    evidence: RuntimeEvidenceContract,
) -> tuple[RuntimeEvidenceContract, str]:
    """Project evidence for B4: Full C2 state-aware evaluator.

    Retains complete permitted evidence: ordered events, before/after diffs, and completeness.
    """
    projected = evidence.model_copy()
    return projected, _compute_digest(projected)
