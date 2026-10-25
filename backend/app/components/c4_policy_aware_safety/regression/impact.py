"""Policy impact and dependency analysis for Phase 5 selective regression."""

from app.components.c4_policy_aware_safety.contracts.bindings import DomainBinding
from app.components.c4_policy_aware_safety.contracts.cases import PolicyTestCase
from app.components.c4_policy_aware_safety.contracts.regression import (
    CaseDecisionAction,
    CaseImpactDecision,
    CaseImpactLevel,
    PolicyComparisonRecord,
    RuleChangeType,
    RuleDiffRecord,
)
from app.components.c4_policy_aware_safety.contracts.rules import (
    PolicyContractVersion,
    PolicyRule,
)


def _selector_matches(selector: str, target: str | None) -> bool:
    """Check whether a wildcard or exact selector matches target."""
    if not target or selector == "*":
        return True
    return selector.strip().upper() == target.strip().upper()


def _case_scope_overlaps_rule(
    case: PolicyTestCase,
    rule: PolicyRule,
    candidate_rules: dict[str, PolicyRule] | None = None,
) -> bool:
    """Determine whether a test case's scope overlaps with a policy rule's scope."""
    target_rule_id = getattr(case, "target_rule_id", getattr(case, "rule_id", ""))
    if candidate_rules and target_rule_id in candidate_rules:
        target_rule = candidate_rules[target_rule_id]
        if not (_selector_matches(rule.principal_selector, target_rule.principal_selector) or _selector_matches(target_rule.principal_selector, rule.principal_selector)):
            return False
        if not (
            _selector_matches(rule.action_selector, target_rule.action_selector)
            or _selector_matches(target_rule.action_selector, rule.action_selector)
        ):
            return False
        return bool(
            _selector_matches(rule.resource_selector, target_rule.resource_selector)
            or _selector_matches(target_rule.resource_selector, rule.resource_selector)
        )

    # Fallback to direct attribute checks
    case_role = getattr(case, "principal_selector", None)
    if not _selector_matches(rule.principal_selector, case_role):
        return False

    case_action = getattr(case, "action_selector", None)
    if not _selector_matches(rule.action_selector, case_action):
        return False

    case_res = getattr(case, "resource_selector", None)
    return not (case_res and not _selector_matches(rule.resource_selector, case_res))


class PolicyImpactAnalyzer:
    """Analyzes impact of policy diffs on test cases and computes regression decisions."""

    def analyze_impact(
        self,
        comparison: PolicyComparisonRecord,
        candidate_contract: PolicyContractVersion,
        baseline_cases: list[PolicyTestCase],
        binding: DomainBinding | None = None,
    ) -> list[CaseImpactDecision]:
        """Compute fine-grained impact decisions for all baseline cases."""
        diff_by_rule: dict[str, RuleDiffRecord] = {
            d.rule_id: d for d in comparison.rule_diffs
        }
        candidate_rules: dict[str, PolicyRule] = {
            r.rule_id: r for r in candidate_contract.rules
        }

        # Identify newly added rules to test for scope overlap
        added_rule_diffs = [
            d for d in comparison.rule_diffs if d.change_type == RuleChangeType.ADDED
        ]
        added_rules = [
            candidate_rules[d.rule_id]
            for d in added_rule_diffs
            if d.rule_id in candidate_rules
        ]

        # Identify permission/authorization modifications that might indirectly affect other rules
        modified_permission_rules = [
            d
            for d in comparison.rule_diffs
            if d.change_type == RuleChangeType.SEMANTICALLY_MODIFIED
            and d.affects_permission
        ]

        decisions: list[CaseImpactDecision] = []

        for case in baseline_cases:
            target_rule_id = getattr(case, "target_rule_id", getattr(case, "rule_id", ""))
            test_kind_val = (
                case.test_kind.value
                if hasattr(case.test_kind, "value")
                else str(case.test_kind)
            )
            target_diff = diff_by_rule.get(target_rule_id)

            # 0. A co-target rule of a multi-rule case was removed or semantically changed (the
            # primary target may be unchanged); the case's expectations for that rule are stale.
            primary_changed = target_diff is not None and target_diff.change_type in (
                RuleChangeType.REMOVED,
                RuleChangeType.SEMANTICALLY_MODIFIED,
            )
            changed_co_targets = [
                rule_id
                for rule_id in (getattr(case, "target_rule_ids", None) or [])
                if rule_id != target_rule_id
                and diff_by_rule.get(rule_id) is not None
                and diff_by_rule[rule_id].change_type
                in (RuleChangeType.REMOVED, RuleChangeType.SEMANTICALLY_MODIFIED)
            ]
            if changed_co_targets and not primary_changed:
                changes = ", ".join(
                    f"'{r}' {diff_by_rule[r].change_type.value.lower()}" for r in changed_co_targets
                )
                decisions.append(
                    CaseImpactDecision(
                        case_id=case.case_id,
                        case_version=case.case_version,
                        target_rule_id=target_rule_id,
                        test_kind=test_kind_val,
                        impact_level=CaseImpactLevel.DEFINITELY_AFFECTED,
                        action=CaseDecisionAction.REVISE,
                        reason=f"Co-target rule {changes} in candidate contract; multi-rule case needs revision.",
                        dependent_rule_ids=[target_rule_id, *changed_co_targets],
                    )
                )
                continue

            # 1. Target rule removed
            if target_diff and target_diff.change_type == RuleChangeType.REMOVED:
                # Check if case has multiple target rules
                if len(getattr(case, "target_rule_ids", []) or []) > 1:
                    decisions.append(
                        CaseImpactDecision(
                            case_id=case.case_id,
                            case_version=case.case_version,
                            target_rule_id=target_rule_id,
                            test_kind=test_kind_val,
                            impact_level=CaseImpactLevel.DEFINITELY_AFFECTED,
                            action=CaseDecisionAction.REVISE,
                            reason=f"Target rule '{target_rule_id}' was removed; multi-rule case needs revision.",
                            dependent_rule_ids=[target_rule_id],
                        )
                    )
                else:
                    decisions.append(
                        CaseImpactDecision(
                            case_id=case.case_id,
                            case_version=case.case_version,
                            target_rule_id=target_rule_id,
                            test_kind=test_kind_val,
                            impact_level=CaseImpactLevel.DEFINITELY_AFFECTED,
                            action=CaseDecisionAction.RETIRE,
                            reason=f"Sole target rule '{target_rule_id}' was removed in candidate contract.",
                            dependent_rule_ids=[target_rule_id],
                        )
                    )
                continue

            # 2. Target rule semantically modified
            if target_diff and target_diff.change_type == RuleChangeType.SEMANTICALLY_MODIFIED:
                # Threshold condition or boundary change requires regeneration
                if (
                    target_diff.affects_approval
                    or target_diff.affects_boundary
                    or "applicability_conditions" in target_diff.field_changes
                    or "compliance_conditions" in target_diff.field_changes
                    or "policy_requirement" in target_diff.field_changes
                ):
                    decisions.append(
                        CaseImpactDecision(
                            case_id=case.case_id,
                            case_version=case.case_version,
                            target_rule_id=target_rule_id,
                            test_kind=test_kind_val,
                            impact_level=CaseImpactLevel.DEFINITELY_AFFECTED,
                            action=CaseDecisionAction.REGENERATE,
                            reason=(
                                f"Target rule '{target_rule_id}' conditions/threshold/boundary changed "
                                f"({target_diff.change_description}); requires regenerated boundary values."
                            ),
                            dependent_rule_ids=[target_rule_id],
                        )
                    )
                else:
                    decisions.append(
                        CaseImpactDecision(
                            case_id=case.case_id,
                            case_version=case.case_version,
                            target_rule_id=target_rule_id,
                            test_kind=test_kind_val,
                            impact_level=CaseImpactLevel.DEFINITELY_AFFECTED,
                            action=CaseDecisionAction.REVALIDATE,
                            reason=(
                                f"Target rule '{target_rule_id}' semantically modified "
                                f"({target_diff.change_description}); requires revalidation."
                            ),
                            dependent_rule_ids=[target_rule_id],
                        )
                    )
                continue

            # 3. Target rule has only metadata or provenance change
            if target_diff and target_diff.change_type in (
                RuleChangeType.METADATA_ONLY,
                RuleChangeType.PROVENANCE_ONLY,
            ):
                decisions.append(
                    CaseImpactDecision(
                        case_id=case.case_id,
                        case_version=case.case_version,
                        target_rule_id=target_rule_id,
                        test_kind=test_kind_val,
                        impact_level=CaseImpactLevel.UNAFFECTED,
                        action=CaseDecisionAction.RETAIN,
                        reason=f"Target rule '{target_rule_id}' has non-semantic update only ({target_diff.change_type.value}); retained.",
                        dependent_rule_ids=[target_rule_id],
                    )
                )
                continue

            # 4. Check scope overlap from newly added rules
            overlapping_added_rule = None
            for ar in added_rules:
                if _case_scope_overlaps_rule(case, ar, candidate_rules):
                    overlapping_added_rule = ar
                    break

            if overlapping_added_rule:
                decisions.append(
                    CaseImpactDecision(
                        case_id=case.case_id,
                        case_version=case.case_version,
                        target_rule_id=target_rule_id,
                        test_kind=test_kind_val,
                        impact_level=CaseImpactLevel.POSSIBLY_AFFECTED,
                        action=CaseDecisionAction.REVALIDATE,
                        reason=(
                            f"New candidate rule '{overlapping_added_rule.rule_id}' overlaps in scope "
                            f"(action={overlapping_added_rule.action_selector}, resource={overlapping_added_rule.resource_selector}); "
                            "existing case requires revalidation to ensure continued validity."
                        ),
                        dependent_rule_ids=[target_rule_id, overlapping_added_rule.rule_id],
                    )
                )
                continue

            # 5. Check indirect dependency from modified permission rules
            indirect_perm_rule = None
            for pr in modified_permission_rules:
                c_rule = candidate_rules.get(pr.rule_id)
                if c_rule and _case_scope_overlaps_rule(case, c_rule, candidate_rules):
                    indirect_perm_rule = c_rule
                    break

            if indirect_perm_rule:
                decisions.append(
                    CaseImpactDecision(
                        case_id=case.case_id,
                        case_version=case.case_version,
                        target_rule_id=target_rule_id,
                        test_kind=test_kind_val,
                        impact_level=CaseImpactLevel.POSSIBLY_AFFECTED,
                        action=CaseDecisionAction.REVALIDATE,
                        reason=(
                            f"Supporting permission rule '{indirect_perm_rule.rule_id}' was modified; "
                            "dependent case requires revalidation."
                        ),
                        dependent_rule_ids=[target_rule_id, indirect_perm_rule.rule_id],
                    )
                )
                continue

            # 6. Unaffected rule
            decisions.append(
                CaseImpactDecision(
                    case_id=case.case_id,
                    case_version=case.case_version,
                    target_rule_id=target_rule_id,
                    test_kind=test_kind_val,
                    impact_level=CaseImpactLevel.UNAFFECTED,
                    action=CaseDecisionAction.RETAIN,
                    reason=f"Target rule '{target_rule_id}' and dependencies are unchanged in candidate contract.",
                    dependent_rule_ids=[target_rule_id],
                )
            )

        return decisions
