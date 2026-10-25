import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from app.components.c1_tool_call_correctness.contracts.configuration import (
    EvidenceChannel,
)
from app.components.c1_tool_call_correctness.contracts.generation import (
    FixturePreparationPlan,
)
from app.components.c1_tool_call_correctness.contracts.lifecycle import EvidenceRef
from app.components.c1_tool_call_correctness.services.evaluator_rules import (
    extract_path_value,
)


class SyntheticFixtureService:
    """Manages isolated synthetic fixture state, reset hooks, and expectation value resolution.
    Strictly isolated per session to prevent test data leakage between executions.
    """

    def __init__(self) -> None:
        # In-memory session store mapping session_id -> {record_id: {data}}
        self._session_stores: dict[str, dict[str, Any]] = {}

    def prepare_fixture(
        self,
        session_id: str,
        fixture_plan: FixturePreparationPlan,
    ) -> tuple[bool, dict[str, Any], list[EvidenceRef]]:
        """Prepares synthetic records and starting conditions in an isolated session sandbox.
        Returns (success, prepared_context, evidence_refs).
        """
        session_data: dict[str, Any] = {}
        # Populate synthetic records
        for record in fixture_plan.synthetic_records:
            session_data[record.record_id] = {
                "record_type": record.record_type,
                **record.attributes,
            }

        # Store starting conditions under a reserved key
        if fixture_plan.starting_conditions:
            session_data["_starting_conditions"] = dict(
                fixture_plan.starting_conditions
            )

        self._session_stores[session_id] = session_data

        # Serialize payload for evidence checksum
        raw_repr = json.dumps(session_data, sort_keys=True, default=str)
        checksum = hashlib.sha256(raw_repr.encode("utf-8")).hexdigest()

        evidence_ref = EvidenceRef(
            evidence_id=f"ev_fix_{session_id[:8]}",
            channel=EvidenceChannel.SYNTHETIC_FIXTURE,
            uri_or_pointer=f"sandbox://sessions/{session_id}/fixtures",
            checksum=checksum,
            captured_at=datetime.now(UTC),
            summary=(
                f"Synthetic in-memory fixture (not application data) initialized with {len(fixture_plan.synthetic_records)} records "
                f"for capability '{fixture_plan.fixture_capability_ref}'."
            ),
        )

        return True, session_data, [evidence_ref]

    def resolve_expectation_values(
        self,
        expectations: list[Any],
        session_context: dict[str, Any],
    ) -> list[Any]:
        """Resolves fixture-dependent expected values from prepared synthetic records
        and freezes the resolved expectations before presenting the task to the tested agent.
        """
        import copy

        resolved_list = []
        for spec in expectations:
            spec_copy = copy.deepcopy(spec)
            for constraint in spec_copy.argument_constraints:
                # If constraint has a source_relationship, resolve expected_value from session_context
                if constraint.source_relationship is not None:
                    rel = constraint.source_relationship
                    rec_id = rel.source_record_id
                    if rec_id in session_context:
                        found, val = extract_path_value(
                            session_context[rec_id], rel.source_path
                        )
                        if found and constraint.expected_value is None:
                            constraint.expected_value = val
            resolved_list.append(spec_copy)
        return resolved_list

    def reset_session(self, session_id: str) -> None:
        """Completely purges session synthetic data to ensure zero leakage across runs."""
        self._session_stores.pop(session_id, None)

    def get_session_data(self, session_id: str) -> dict[str, Any] | None:
        """Returns the current synthetic data for the session if present."""
        return self._session_stores.get(session_id)
