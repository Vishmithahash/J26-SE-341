"""Evidence and grounding ablation engine for Phase 6.

Creates derived, non-mutating evidence views that separately remove:
1. Structured policy grounding (NO_GROUNDING).
2. Trusted-source / provenance information (NO_PROVENANCE, marking trust as UNKNOWN).
3. Action and effect evidence (NO_EFFECTS, masking tool effects and disclosure sinks).

Guarantees:
- Original immutable execution traces and evidence packages are never modified.
- Production evaluator behavior is never changed to run an ablation.
"""

import copy

from app.components.c4_policy_aware_safety.contracts.enums import (
    TrustClassification,
)
from app.components.c4_policy_aware_safety.contracts.evaluation import AblationType
from app.components.c4_policy_aware_safety.contracts.evidence import (
    EvaluationEvidencePackage,
)
from app.components.c4_policy_aware_safety.contracts.rules import PolicyContractVersion


class EvidenceAblationEngine:
    """Produces masked derived evidence packages and contract views for ablation experiments."""

    def create_ablated_evidence_view(
        self,
        evidence: EvaluationEvidencePackage,
        ablation_type: AblationType,
    ) -> EvaluationEvidencePackage:
        """Derive a masked evidence view without mutating the original evidence package."""
        if ablation_type == AblationType.NONE:
            return evidence

        # Deep copy to guarantee immutability of the source record
        ablated = copy.deepcopy(evidence)

        if ablation_type == AblationType.NO_PROVENANCE:
            # 1. Mask trust information to UNTRUSTED_CONTENT; do not falsely assume trusted
            for src in ablated.instruction_sources:
                src.trust_classification = TrustClassification.UNTRUSTED_CONTENT
            ablated.argument_provenance = []

        elif ablation_type == AblationType.NO_EFFECTS:
            # 2. Mask action/effect evidence and disclosure sinks
            ablated.effects = []
            ablated.disclosures = []
            for tool_ex in ablated.tool_executions:
                tool_ex.output = None
                tool_ex.status = "MASKED"

        return ablated

    def create_ablated_contract_view(
        self,
        contract: PolicyContractVersion,
        ablation_type: AblationType,
    ) -> PolicyContractVersion:
        """Derive an ablated contract view (e.g. removing source grounding)."""
        if ablation_type != AblationType.NO_GROUNDING:
            return contract

        ablated_contract = copy.deepcopy(contract)
        for rule in ablated_contract.rules:
            # Strip source coordinate grounding and excerpts
            rule.source_references = []
        return ablated_contract
