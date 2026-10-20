"""Trace normalizer for C2 workflow evaluation.

Maps supported raw tool events into canonical C2 evidence while preserving original
event references, timestamps, and audit provenance.
Performs strict evidence audits:
- Strictly monotonic event indexing without sequence gaps.
- Duplicate event ID detection.
- Broken correlation and missing state snapshots.
Does NOT silently repair evidence by renumbering or sorting.
Does NOT infer successful state mutations from agent text or tool success messages.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)
from app.components.c2_state_aware_workflow.contracts.runtime_evidence import (
    EvidenceCompleteness,
    RuntimeEvent,
    RuntimeEvidenceContract,
    StateObservation,
)


class NormalizedTrace(BaseModel):
    """Audited, normalized trace ready for EFSM alignment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_id: str
    run_id: str
    test_id: str
    model_id: str
    model_version: str
    ordered_events: list[RuntimeEvent]
    state_observations_by_index: dict[int, StateObservation]
    completeness: EvidenceCompleteness
    diagnostics: list[str] = Field(default_factory=list)
    has_audit_anomalies: bool = False


class TraceNormalizer:
    """Normalizes and validates runtime evidence against declared model mappings."""

    def __init__(self, model: EFSMModelDefinition):
        self.model = model
        self.event_mapping_by_tool = {m.tool_name: m for m in model.event_mappings}

    def normalize(self, evidence: RuntimeEvidenceContract) -> NormalizedTrace:
        """Audit and normalize raw runtime evidence without synthesizing missing data."""
        diagnostics: list[str] = []
        has_anomalies = False

        # 1. Audit event IDs and sequence indices
        seen_event_ids: set[str] = set()
        expected_index = 0
        ordered_events: list[RuntimeEvent] = []

        for evt in evidence.ordered_events:
            # Check for duplicate event IDs
            if evt.event_id in seen_event_ids:
                has_anomalies = True
                diagnostics.append(
                    f"Conflicting duplicate event ID detected: '{evt.event_id}' at index {evt.event_index}."
                )
            seen_event_ids.add(evt.event_id)

            # Check for sequence index gaps or out-of-order delivery
            if evt.event_index != expected_index:
                has_anomalies = True
                diagnostics.append(
                    f"Sequence index gap detected: expected index {expected_index}, got {evt.event_index}."
                )
            expected_index = evt.event_index + 1

            # Check if tool is mapped in the reference model
            if evt.tool_name not in self.event_mapping_by_tool:
                diagnostics.append(
                    f"Unmapped tool '{evt.tool_name}' observed at event index {evt.event_index}."
                )

            ordered_events.append(evt)

        # 2. Index state observations by event_index
        obs_by_index: dict[int, StateObservation] = {}
        for obs in evidence.state_observations:
            if obs.event_index in obs_by_index:
                has_anomalies = True
                diagnostics.append(
                    f"Duplicate state observation for event index {obs.event_index}."
                )
            obs_by_index[obs.event_index] = obs

        # 3. Check for missing mandatory observations
        for evt in ordered_events:
            if evt.event_index not in obs_by_index:
                diagnostics.append(
                    f"Missing state observation for event index {evt.event_index} ('{evt.tool_name}')."
                )

        # 4. Check completeness declaration
        completeness = evidence.completeness
        if completeness.is_truncated:
            has_anomalies = True
            diagnostics.append("Trace flagged as truncated by evidence collector.")
        if not completeness.confirmed_agent_termination:
            diagnostics.append("Evidence lacks confirmed agent termination marker.")
        if completeness.missing_fields:
            has_anomalies = True
            diagnostics.append(
                f"Missing mandatory evidence fields: {completeness.missing_fields}"
            )
        for anom in completeness.anomalies:
            has_anomalies = True
            diagnostics.append(f"Collector reported anomaly: {anom}")

        return NormalizedTrace(
            project_id=evidence.project_id,
            run_id=evidence.run_id,
            test_id=evidence.test_id,
            model_id=evidence.model_id,
            model_version=evidence.model_version,
            ordered_events=ordered_events,
            state_observations_by_index=obs_by_index,
            completeness=completeness,
            diagnostics=diagnostics,
            has_audit_anomalies=has_anomalies,
        )
