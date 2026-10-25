"""Selective regeneration and revalidation service for Phase 5 regression planning."""


from app.components.c4_policy_aware_safety.contracts.bindings import DomainBinding
from app.components.c4_policy_aware_safety.contracts.cases import (
    CaseLifecycleState,
    PolicyTestCase,
)
from app.components.c4_policy_aware_safety.contracts.enums import (
    ContractLifecycleState,
)
from app.components.c4_policy_aware_safety.contracts.regression import (
    CaseDecisionAction,
    PlanLifecycleState,
    RegressionPlanRecord,
)
from app.components.c4_policy_aware_safety.contracts.rules import (
    PolicyContractVersion,
)
from app.components.c4_policy_aware_safety.freezing.service import CaseFreezingService
from app.components.c4_policy_aware_safety.generation.generator import (
    PolicyTestGenerator,
)
from app.components.c4_policy_aware_safety.validation.case_validator import (
    PolicyTestCaseValidator,
)


class RegressionRegenerationService:
    """Regenerates, revalidates, and freezes affected test cases for candidate policies."""

    def __init__(
        self,
        generator: PolicyTestGenerator | None = None,
        validator: PolicyTestCaseValidator | None = None,
        freezer: CaseFreezingService | None = None,
    ) -> None:
        self.generator = generator or PolicyTestGenerator()
        self.validator = validator or PolicyTestCaseValidator()
        self.freezer = freezer or CaseFreezingService()

    def regenerate_and_revalidate(
        self,
        plan: RegressionPlanRecord,
        candidate_contract: PolicyContractVersion,
        binding: DomainBinding,
        baseline_cases: list[PolicyTestCase],
    ) -> tuple[RegressionPlanRecord, list[PolicyTestCase]]:
        """
        Execute selective regeneration and revalidation according to plan decisions.
        Returns: (updated_plan, replacement_cases)
        """
        if candidate_contract.lifecycle_state != ContractLifecycleState.ACCEPTED:
            raise ValueError(
                f"Candidate contract '{candidate_contract.contract_id}' v{candidate_contract.version} "
                f"is not ACCEPTED ({candidate_contract.lifecycle_state.value}). Cannot regenerate."
            )

        baseline_by_id = {c.case_id: c for c in baseline_cases}

        # Generate fresh cases from candidate contract and binding
        candidate_generated_cases: list[PolicyTestCase] = []
        try:
            candidate_generated_cases, _ = self.generator.generate_cases(
                candidate_contract, binding
            )
        except Exception as e:  # noqa: BLE001
            plan.readiness_gaps.append(
                f"Generator failed to generate candidate suite cases: {e}"
            )

        candidate_case_map: dict[tuple[str, str], PolicyTestCase] = {
            (
                getattr(c, "target_rule_id", getattr(c, "rule_id", "")),
                c.test_kind.value if hasattr(c.test_kind, "value") else str(c.test_kind),
            ): c
            for c in candidate_generated_cases
        }

        replacement_cases: list[PolicyTestCase] = []
        proposed_replacements: list[str] = []
        retained_cases: list[str] = []
        retired_cases: list[str] = []

        for decision in plan.case_decisions:
            base_case = baseline_by_id.get(decision.case_id)

            if decision.action == CaseDecisionAction.REGENERATE:
                # Find corresponding generated case from candidate contract
                c_case = candidate_case_map.get(
                    (decision.target_rule_id, decision.test_kind)
                )
                if c_case is None:
                    # Look by target_rule_id alone
                    c_case = next(
                        (
                            c
                            for c in candidate_generated_cases
                            if getattr(c, "target_rule_id", getattr(c, "rule_id", ""))
                            == decision.target_rule_id
                        ),
                        None,
                    )

                if c_case is not None:
                    # Validate candidate case
                    val_case, issues = self.validator.validate_case(
                        c_case, candidate_contract, binding
                    )
                    has_blocking = any(i.blocking for i in issues)

                    if not has_blocking:
                        new_case_id = (
                            f"{decision.case_id}-v{decision.case_version + 1}"
                        )
                        linked_case = val_case.model_copy(
                            update={
                                "case_id": new_case_id,
                                "case_version": decision.case_version + 1,
                                "predecessor_case_id": decision.case_id,
                                "predecessor_case_version": decision.case_version,
                                "lifecycle_state": CaseLifecycleState.VALIDATED,
                            }
                        )
                        frozen = self.freezer.freeze_case(
                            linked_case, candidate_contract
                        )
                        decision.replacement_case_id = frozen.case_id
                        decision.replacement_case_version = frozen.case_version
                        decision.predecessor_case_id = decision.case_id
                        decision.predecessor_case_version = decision.case_version
                        proposed_replacements.append(frozen.case_id)
                        replacement_cases.append(frozen)
                    else:
                        decision.action = CaseDecisionAction.BLOCKED
                        blocking_reasons = [
                            i.message for i in issues if i.blocking
                        ]
                        plan.readiness_gaps.append(
                            f"Regenerated case for rule '{decision.target_rule_id}' failed validation: {'; '.join(blocking_reasons)}"
                        )
                else:
                    decision.action = CaseDecisionAction.BLOCKED
                    plan.readiness_gaps.append(
                        f"Missing generator capability or fixture to regenerate case '{decision.case_id}' targeting '{decision.target_rule_id}'."
                    )

            elif decision.action == CaseDecisionAction.REVALIDATE:
                if base_case is not None:
                    # Check if base case conforms to candidate contract
                    val_case, issues = self.validator.validate_case(
                        base_case, candidate_contract, binding
                    )
                    has_blocking = any(i.blocking for i in issues)

                    if not has_blocking:
                        new_case_id = (
                            f"{decision.case_id}-reval-v{decision.case_version + 1}"
                        )
                        reval_case = base_case.model_copy(
                            update={
                                "case_id": new_case_id,
                                "case_version": decision.case_version + 1,
                                "predecessor_case_id": decision.case_id,
                                "predecessor_case_version": decision.case_version,
                                "lifecycle_state": CaseLifecycleState.VALIDATED,
                            }
                        )
                        frozen = self.freezer.freeze_case(
                            reval_case, candidate_contract
                        )
                        decision.replacement_case_id = frozen.case_id
                        decision.replacement_case_version = frozen.case_version
                        decision.predecessor_case_id = decision.case_id
                        decision.predecessor_case_version = decision.case_version
                        proposed_replacements.append(frozen.case_id)
                        replacement_cases.append(frozen)
                    else:
                        decision.action = CaseDecisionAction.NEEDS_REVIEW
                        blocking_reasons = [
                            i.message for i in issues if i.blocking
                        ]
                        plan.readiness_gaps.append(
                            f"Revalidation of case '{decision.case_id}' failed under candidate contract: {'; '.join(blocking_reasons)}"
                        )
                else:
                    decision.action = CaseDecisionAction.BLOCKED

            elif decision.action == CaseDecisionAction.RETIRE:
                retired_cases.append(decision.case_id)

            elif decision.action == CaseDecisionAction.REVISE:
                # Multi-rule case: drop every rule the candidate contract no longer has (the
                # removed rule may be the primary target or a co-target) and bind the revised
                # case to the candidate contract.
                if base_case is not None:
                    kept = {r.rule_id for r in candidate_contract.rules}
                    revised_assertions = [
                        a
                        for a in getattr(base_case, "expected_assertions", []) or []
                        if getattr(a, "rule_id", None) in kept
                    ]
                    setup = dict(base_case.structured_setup or {})
                    if "hidden_challenged_rule_ids" in setup:
                        setup["hidden_challenged_rule_ids"] = [
                            r for r in setup["hidden_challenged_rule_ids"] if r in kept
                        ]
                    new_case_id = (
                        f"{decision.case_id}-revised-v{decision.case_version + 1}"
                    )
                    revised_case = base_case.model_copy(
                        update={
                            "case_id": new_case_id,
                            "case_version": decision.case_version + 1,
                            "predecessor_case_id": decision.case_id,
                            "predecessor_case_version": decision.case_version,
                            "contract_id": candidate_contract.contract_id,
                            "contract_version": candidate_contract.version,
                            "expected_assertions": revised_assertions,
                            "target_rule_ids": [
                                r for r in (base_case.target_rule_ids or []) if r in kept
                            ],
                            "structured_setup": setup,
                            "lifecycle_state": CaseLifecycleState.VALIDATED,
                        }
                    )
                    frozen = self.freezer.freeze_case(
                        revised_case, candidate_contract
                    )
                    decision.replacement_case_id = frozen.case_id
                    decision.replacement_case_version = frozen.case_version
                    decision.predecessor_case_id = decision.case_id
                    decision.predecessor_case_version = decision.case_version
                    proposed_replacements.append(frozen.case_id)
                    replacement_cases.append(frozen)

            elif decision.action == CaseDecisionAction.RETAIN:
                retained_cases.append(decision.case_id)

        # Update plan snapshot
        plan.proposed_replacement_cases = proposed_replacements
        plan.retained_cases = retained_cases
        plan.retired_cases = retired_cases
        plan.status = (
            PlanLifecycleState.VALIDATED
            if not plan.readiness_gaps
            else PlanLifecycleState.DRAFT
        )

        return plan, replacement_cases
