"""In-process local simulated disclosure sink for C4 confidentiality testing.

Captures simulated canary marker deliveries and exfiltration attempts safely
in memory without contacting any external network destinations.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class DisclosureObservation:
    """Record of an observed disclosure or exfiltration event to the local sink."""

    observation_id: str
    destination: str
    payload: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    detected_markers: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class LocalSimulatedDisclosureSink:
    """Hermetic, in-process destination sink for capturing exfiltrated confidential data."""

    def __init__(self) -> None:
        self._observations: list[DisclosureObservation] = []

    def record_disclosure(
        self,
        observation_id: str,
        destination: str,
        payload: str,
        known_markers: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DisclosureObservation:
        """Record an observed payload delivery to a simulated local destination."""
        detected: list[str] = []
        if known_markers:
            for marker in known_markers:
                if marker in payload:
                    detected.append(marker)

        obs = DisclosureObservation(
            observation_id=observation_id,
            destination=destination,
            payload=payload,
            detected_markers=detected,
            metadata=metadata or {},
        )
        self._observations.append(obs)
        return obs

    def get_observations(self) -> list[DisclosureObservation]:
        """Return all recorded disclosure observations."""
        return list(self._observations)

    def contains_marker(self, marker: str) -> bool:
        """Check if any delivered disclosure contained the synthetic canary marker."""
        return any(marker in obs.payload for obs in self._observations)

    def clear(self) -> None:
        """Clear recorded observations between fixture runs."""
        self._observations.clear()
