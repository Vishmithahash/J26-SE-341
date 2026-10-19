from datetime import UTC, datetime

from app.components.c4_policy_aware_safety.contracts.cases import (
    CaseLifecycleState,
    PolicyTestCase,
)
from app.components.c4_policy_aware_safety.contracts.enums import (
    ContractLifecycleState,
)
from app.components.c4_policy_aware_safety.contracts.rules import (
    PolicyContractVersion,
)


class CaseFreezingService:
    """Service for freezing validated policy test cases into immutable snapshots."""

    def freeze_case(
        self,
        case: PolicyTestCase,
        contract: PolicyContractVersion,
    ) -> PolicyTestCase:
        """Freeze a single validated test case.

        Raises ValueError if case has blocking issues, is already rejected,
        or contract is not accepted.
        """
        if case.lifecycle_state == CaseLifecycleState.FROZEN:
            # Already frozen; idempotent
            return case

        if case.is_obsolete:
            raise ValueError(
                f"Cannot freeze case '{case.case_id}' v{case.case_version}: Case is marked obsolete."
            )

        if case.lifecycle_state != CaseLifecycleState.VALIDATED:
            blocking_reasons = [
                i.message for i in case.validation_issues if i.blocking
            ]
            reasons_str = "; ".join(blocking_reasons) if blocking_reasons else f"State is {case.lifecycle_state.value}"
            raise ValueError(
                f"Cannot freeze case '{case.case_id}' v{case.case_version}: {reasons_str}"
            )

        if contract.lifecycle_state != ContractLifecycleState.ACCEPTED:
            raise ValueError(
                f"Cannot freeze case '{case.case_id}': contract '{contract.contract_id}' "
                f"is not in ACCEPTED state ({contract.lifecycle_state.value})."
            )

        now = datetime.now(UTC)
        content_hash = case.compute_content_hash()

        frozen_case = case.model_copy(
            update={
                "lifecycle_state": CaseLifecycleState.FROZEN,
                "content_hash": content_hash,
                "frozen_at": now,
                "updated_at": now,
            }
        )
        return frozen_case

    def freeze_batch(
        self,
        cases: list[PolicyTestCase],
        contract: PolicyContractVersion,
    ) -> list[PolicyTestCase]:
        """Freeze a list of validated cases."""
        return [self.freeze_case(c, contract) for c in cases]
