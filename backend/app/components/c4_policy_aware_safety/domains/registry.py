"""Domain registry for C4 profile discovery and readiness checking."""

from typing import Any

from app.components.c4_policy_aware_safety.contracts.onboarding import (
    DomainProfileDefinition,
)
from app.components.c4_policy_aware_safety.domains.booking import BOOKING_DOMAIN_PROFILE
from app.components.c4_policy_aware_safety.domains.ecommerce import (
    ECOMMERCE_DOMAIN_PROFILE,
)


class DomainRegistry:
    """Registry managing available C4 domain profiles."""

    def __init__(self) -> None:
        self._profiles: dict[str, DomainProfileDefinition] = {
            ECOMMERCE_DOMAIN_PROFILE.domain_id: ECOMMERCE_DOMAIN_PROFILE,
            BOOKING_DOMAIN_PROFILE.domain_id: BOOKING_DOMAIN_PROFILE,
        }

    def register_profile(self, profile: DomainProfileDefinition) -> None:
        self._profiles[profile.domain_id] = profile

    def get_profile(self, domain_id: str) -> DomainProfileDefinition:
        if domain_id not in self._profiles:
            raise KeyError(f"Domain profile '{domain_id}' not found in registry.")
        return self._profiles[domain_id]

    def list_profiles(self) -> list[DomainProfileDefinition]:
        return list(self._profiles.values())

    def check_domain_readiness(
        self, domain_id: str, execution_mode: str = "SIMULATED"
    ) -> dict[str, Any]:
        """Check live vs simulated readiness for a domain."""
        profile = self.get_profile(domain_id)

        if execution_mode.upper() == "LIVE":
            return {
                "domain_id": profile.domain_id,
                "name": profile.name,
                "execution_mode": "LIVE",
                "is_ready": profile.is_live_available,
                "status": "BLOCKED" if not profile.is_live_available else "READY",
                "blockers": profile.live_blockers,
                "capabilities": list(profile.capabilities),
            }

        # Simulated execution is fully supported hermetically
        return {
            "domain_id": profile.domain_id,
            "name": profile.name,
            "execution_mode": "SIMULATED",
            "is_ready": True,
            "status": "READY",
            "blockers": [],
            "capabilities": list(profile.capabilities),
        }


# Global domain registry singleton
domain_registry = DomainRegistry()
