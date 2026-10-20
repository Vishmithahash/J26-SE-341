"""Independent reviewer workflow and inter-rater agreement computation for Phase 6.

Supports generation of blind review packets (model predictions hidden), collection of
independent judgments from Reviewer 1 and Reviewer 2, Cohen's Kappa agreement computation,
and explicit human adjudication for label finalization.
"""

from collections import Counter
from datetime import UTC, datetime

from app.components.c4_policy_aware_safety.contracts.evaluation import (
    AdjudicationRecord,
    EvaluationCaseRecord,
    EvaluationDatasetRecord,
    InterRaterAgreement,
    LabelOrigin,
    ReviewerDecision,
    ReviewPacket,
    ReviewStatus,
)
from app.components.c4_policy_aware_safety.contracts.rules import PolicyContractVersion


class ReviewService:
    """Manages independent review packets, decisions, agreement, and adjudication."""

    def create_review_packet(
        self,
        case: EvaluationCaseRecord,
        contract: PolicyContractVersion,
    ) -> ReviewPacket:
        """Create a blind review packet with predictions hidden from reviewers."""
        # Find relevant policy excerpt from the contract
        matching_rule = next(
            (r for r in contract.rules if r.rule_id == case.reference_attribution.rule_id),
            None,
        )
        policy_excerpt = ""
        if matching_rule and matching_rule.source_references:
            policy_excerpt = matching_rule.source_references[0].supporting_excerpt

        return ReviewPacket(
            packet_id=f"packet-{case.case_id}",
            project_id=case.project_id,
            case_id=case.case_id,
            policy_excerpt=policy_excerpt,
            tool_call_summary={
                "domain_id": case.domain_id,
                "case_category": case.case_category,
                "policy_family": case.policy_family.value,
            },
            evidence_summary={
                "source_type": case.source_type,
                "expected_applicability": case.expected_applicability,
            },
            created_at=datetime.now(UTC),
        )

    def calculate_inter_rater_agreement(
        self,
        decisions_1: list[ReviewerDecision],
        decisions_2: list[ReviewerDecision],
    ) -> InterRaterAgreement:
        """Calculate Cohen's Kappa between two independent reviewers.

        Cohen's Kappa:
            kappa = (p_o - p_e) / (1 - p_e)
        where:
            p_o = observed agreement rate
            p_e = hypothetical chance agreement rate
        """
        map_1 = {d.case_id: d.verdict_decision for d in decisions_1}
        map_2 = {d.case_id: d.verdict_decision for d in decisions_2}

        common_cases = sorted(set(map_1.keys()) & set(map_2.keys()))
        total = len(common_cases)

        if total == 0:
            return InterRaterAgreement(
                total_cases=0,
                agreed_count=0,
                disagreed_count=0,
                observed_agreement_po=0.0,
                chance_agreement_pe=0.0,
                cohens_kappa=None,
                interpretation="NO_DATA: Zero overlapping cases reviewed by both reviewers.",
            )

        agreed = sum(1 for c in common_cases if map_1[c] == map_2[c])
        disagreed = total - agreed
        p_o = agreed / total

        # Marginal distributions
        c1 = Counter(map_1[c] for c in common_cases)
        c2 = Counter(map_2[c] for c in common_cases)
        categories = sorted(set(c1.keys()) | set(c2.keys()))

        p_e = sum((c1.get(cat, 0) / total) * (c2.get(cat, 0) / total) for cat in categories)

        if p_e >= 1.0:
            kappa = 1.0 if p_o >= 1.0 else 0.0
        else:
            kappa = (p_o - p_e) / (1.0 - p_e)

        # Landis and Koch interpretation
        if kappa < 0:
            interp = "POOR: Less than chance agreement"
        elif kappa <= 0.20:
            interp = "SLIGHT: Slight agreement (0.01 - 0.20)"
        elif kappa <= 0.40:
            interp = "FAIR: Fair agreement (0.21 - 0.40)"
        elif kappa <= 0.60:
            interp = "MODERATE: Moderate agreement (0.41 - 0.60)"
        elif kappa <= 0.80:
            interp = "SUBSTANTIAL: Substantial agreement (0.61 - 0.80)"
        else:
            interp = "ALMOST_PERFECT: Near-perfect agreement (0.81 - 1.00)"

        return InterRaterAgreement(
            total_cases=total,
            agreed_count=agreed,
            disagreed_count=disagreed,
            observed_agreement_po=round(p_o, 4),
            chance_agreement_pe=round(p_e, 4),
            cohens_kappa=round(kappa, 4),
            interpretation=interp,
        )

    def adjudicate_disagreement(
        self,
        case: EvaluationCaseRecord,
        adjudication: AdjudicationRecord,
    ) -> EvaluationCaseRecord:
        """Apply an authoritative adjudication to finalize a disagreed label."""
        return case.model_copy(
            update={
                "expected_verdict": adjudication.final_verdict,
                "reference_attribution": adjudication.final_attribution,
                "label_origin": LabelOrigin.ADJUDICATED,
                "review_status": ReviewStatus.FINALIZED,
            }
        )

    def validate_split_leakage(
        self,
        dataset: EvaluationDatasetRecord,
    ) -> list[str]:
        """Verify that related scenario groups and variants do not span multiple splits."""
        group_to_splits: dict[str, set[str]] = {}
        for case in dataset.cases:
            group_to_splits.setdefault(case.scenario_group_id, set()).add(case.split.value)

        leakage_errors: list[str] = []
        for group_id, splits in group_to_splits.items():
            if len(splits) > 1:
                leakage_errors.append(
                    f"Data leakage detected: Scenario group '{group_id}' spans multiple splits: {', '.join(sorted(splits))}."
                )
        return leakage_errors
