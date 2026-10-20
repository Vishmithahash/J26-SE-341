"""Deterministic policy diffing engine for Phase 5 comparison of accepted contracts."""

import hashlib
import json
import math
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.components.c4_policy_aware_safety.contracts.enums import (
    ContractLifecycleState,
    PolicyFamily,
)
from app.components.c4_policy_aware_safety.contracts.regression import (
    PolicyComparisonRecord,
    PolicyComparisonRequest,
    RuleChangeType,
    RuleDiffRecord,
)
from app.components.c4_policy_aware_safety.contracts.rules import (
    PolicyContractVersion,
    PolicyRule,
)


def _canonical_json(obj: Any) -> str:
    """Produce deterministic canonical JSON string without lossy numeric rounding.
    
    Preserves exact numeric precision (integer minor units, exact Decimals) and rejects
    unsupported non-finite floats (NaN, Inf).
    """
    def _normalize(val: Any) -> Any:
        if val is None or isinstance(val, (bool, str, int)):
            return val
        if isinstance(val, float):
            if math.isnan(val) or math.isinf(val):
                raise ValueError(
                    f"Non-finite numeric value '{val}' is unsupported in policy diffing."
                )
            # Exact decimal representation without lossy rounding
            return f"{Decimal(str(val)):f}" if abs(val) < 1e15 else str(val)
        if isinstance(val, Decimal):
            if not val.is_finite():
                raise ValueError(
                    f"Non-finite Decimal value '{val}' is unsupported in policy diffing."
                )
            return f"{val:f}"
        if hasattr(val, "model_dump"):
            return _normalize(val.model_dump(mode="json"))
        if isinstance(val, dict):
            return {str(k): _normalize(v) for k, v in val.items()}
        if isinstance(val, (list, tuple, set)):
            return [_normalize(item) for item in val]
        return str(val)

    dumped = _normalize(obj)
    return json.dumps(dumped, sort_keys=True)


class PolicyDiffEngine:
    """Compares two accepted policy contract versions deterministically."""

    def compare_contracts(
        self,
        request: PolicyComparisonRequest,
        baseline: PolicyContractVersion,
        candidate: PolicyContractVersion,
    ) -> PolicyComparisonRecord:
        """Execute deterministic policy diff between baseline and candidate contracts."""
        # 1. Project Scoping and Reference Verification
        if (
            baseline.project_id != request.project_id
            or candidate.project_id != request.project_id
        ):
            raise ValueError(
                f"Project mismatch in comparison: request={request.project_id}, "
                f"baseline={baseline.project_id}, candidate={candidate.project_id}"
            )

        if (
            baseline.contract_id != request.baseline_contract_id
            or baseline.version != request.baseline_contract_version
        ):
            raise ValueError(
                f"Baseline contract reference mismatch: expected {request.baseline_contract_id} v{request.baseline_contract_version}, "
                f"got {baseline.contract_id} v{baseline.version}"
            )

        if (
            candidate.contract_id != request.candidate_contract_id
            or candidate.version != request.candidate_contract_version
        ):
            raise ValueError(
                f"Candidate contract reference mismatch: expected {request.candidate_contract_id} v{request.candidate_contract_version}, "
                f"got {candidate.contract_id} v{candidate.version}"
            )

        # 2. Acceptance Gating: Both contracts must be in ACCEPTED state
        if baseline.lifecycle_state != ContractLifecycleState.ACCEPTED:
            raise ValueError(
                f"Cannot compare baseline contract in non-accepted state '{baseline.lifecycle_state.value}'. "
                "Only ACCEPTED contracts can serve as regression baselines."
            )

        if candidate.lifecycle_state != ContractLifecycleState.ACCEPTED:
            raise ValueError(
                f"Cannot compare candidate contract in non-accepted state '{candidate.lifecycle_state.value}'. "
                "Only ACCEPTED contracts can be compared for scored regression."
            )

        # 3. Compute Configuration Digest
        raw_digest_input = (
            f"{request.project_id}:{baseline.contract_id}:{baseline.version}:{baseline.content_hash}:"
            f"{candidate.contract_id}:{candidate.version}:{candidate.content_hash}:"
            f"{request.binding_id}:{request.binding_version}"
        )
        config_digest = hashlib.sha256(raw_digest_input.encode("utf-8")).hexdigest()

        # 4. Map Rules by rule_id
        baseline_rules = {r.rule_id: r for r in baseline.rules}
        candidate_rules = {r.rule_id: r for r in candidate.rules}

        all_rule_ids = sorted(set(baseline_rules.keys()) | set(candidate_rules.keys()))
        diffs: list[RuleDiffRecord] = []
        summary = {
            "added": 0,
            "removed": 0,
            "semantically_modified": 0,
            "metadata_only": 0,
            "provenance_only": 0,
            "unchanged": 0,
            "uncertain": 0,
            "total_rules": len(all_rule_ids),
        }

        for rule_id in all_rule_ids:
            b_rule = baseline_rules.get(rule_id)
            c_rule = candidate_rules.get(rule_id)

            if b_rule is None and c_rule is not None:
                diff = self._diff_added_rule(c_rule)
                summary["added"] += 1
            elif b_rule is not None and c_rule is None:
                diff = self._diff_removed_rule(b_rule)
                summary["removed"] += 1
            elif b_rule is not None and c_rule is not None:
                diff = self._diff_existing_rules(b_rule, c_rule)
                if diff.change_type == RuleChangeType.SEMANTICALLY_MODIFIED:
                    summary["semantically_modified"] += 1
                elif diff.change_type == RuleChangeType.METADATA_ONLY:
                    summary["metadata_only"] += 1
                elif diff.change_type == RuleChangeType.PROVENANCE_ONLY:
                    summary["provenance_only"] += 1
                elif diff.change_type == RuleChangeType.UNCHANGED:
                    summary["unchanged"] += 1
                else:
                    summary["uncertain"] += 1
            else:
                continue

            diffs.append(diff)

        comparison_id = f"cmp-{uuid.uuid4().hex[:12]}"
        return PolicyComparisonRecord(
            comparison_id=comparison_id,
            project_id=request.project_id,
            baseline_contract_id=baseline.contract_id,
            baseline_contract_version=baseline.version,
            baseline_contract_hash=baseline.content_hash,
            candidate_contract_id=candidate.contract_id,
            candidate_contract_version=candidate.version,
            candidate_contract_hash=candidate.content_hash,
            rule_diffs=diffs,
            summary=summary,
            algorithm_version="c4_diff_v1",
            configuration_digest=config_digest,
            created_at=datetime.now(UTC),
        )

    def _diff_added_rule(self, rule: PolicyRule) -> RuleDiffRecord:
        compliance_dump = _canonical_json(rule.compliance_conditions)
        affects_approval = "approval" in compliance_dump.lower()
        return RuleDiffRecord(
            rule_id=rule.rule_id,
            change_type=RuleChangeType.ADDED,
            baseline_rule_version=None,
            candidate_rule_version=rule.rule_version,
            change_description=f"Rule '{rule.rule_id}' was added in candidate contract ({rule.policy_family.value}).",
            field_changes={
                "principal_selector": {"old": None, "new": rule.principal_selector},
                "action_selector": {"old": None, "new": rule.action_selector},
                "resource_selector": {"old": None, "new": rule.resource_selector},
                "policy_requirement": {
                    "old": None,
                    "new": rule.policy_requirement.value,
                },
                "evaluation_boundary": {
                    "old": None,
                    "new": rule.evaluation_boundary.value,
                },
            },
            affects_boundary=True,
            affects_approval=affects_approval,
            affects_permission=(rule.policy_family == PolicyFamily.AUTHORIZATION),
            affects_confidentiality=(
                rule.policy_family == PolicyFamily.CONFIDENTIALITY
            ),
            affects_instruction_authority=(
                rule.policy_family == PolicyFamily.INSTRUCTION_AUTHORITY
            ),
        )

    def _diff_removed_rule(self, rule: PolicyRule) -> RuleDiffRecord:
        compliance_dump = _canonical_json(rule.compliance_conditions)
        affects_approval = "approval" in compliance_dump.lower()
        return RuleDiffRecord(
            rule_id=rule.rule_id,
            change_type=RuleChangeType.REMOVED,
            baseline_rule_version=rule.rule_version,
            candidate_rule_version=None,
            change_description=f"Rule '{rule.rule_id}' was removed in candidate contract.",
            field_changes={
                "rule_id": {"old": rule.rule_id, "new": None},
                "policy_family": {"old": rule.policy_family.value, "new": None},
            },
            affects_boundary=True,
            affects_approval=affects_approval,
            affects_permission=(rule.policy_family == PolicyFamily.AUTHORIZATION),
            affects_confidentiality=(
                rule.policy_family == PolicyFamily.CONFIDENTIALITY
            ),
            affects_instruction_authority=(
                rule.policy_family == PolicyFamily.INSTRUCTION_AUTHORITY
            ),
        )

    def _diff_existing_rules(
        self, baseline: PolicyRule, candidate: PolicyRule
    ) -> RuleDiffRecord:
        field_changes: dict[str, Any] = {}
        semantic_change = False

        # 1. Principal / Action / Resource Selectors
        if baseline.principal_selector != candidate.principal_selector:
            field_changes["principal_selector"] = {
                "old": baseline.principal_selector,
                "new": candidate.principal_selector,
            }
            semantic_change = True

        if baseline.action_selector != candidate.action_selector:
            field_changes["action_selector"] = {
                "old": baseline.action_selector,
                "new": candidate.action_selector,
            }
            semantic_change = True

        if baseline.resource_selector != candidate.resource_selector:
            field_changes["resource_selector"] = {
                "old": baseline.resource_selector,
                "new": candidate.resource_selector,
            }
            semantic_change = True

        # 2. Policy Requirement and Evaluation Boundary
        if baseline.policy_requirement != candidate.policy_requirement:
            field_changes["policy_requirement"] = {
                "old": baseline.policy_requirement.value,
                "new": candidate.policy_requirement.value,
            }
            semantic_change = True

        if baseline.evaluation_boundary != candidate.evaluation_boundary:
            field_changes["evaluation_boundary"] = {
                "old": baseline.evaluation_boundary.value,
                "new": candidate.evaluation_boundary.value,
            }
            semantic_change = True

        # 3. Predicates: Applicability & Compliance
        b_app_json = _canonical_json(baseline.applicability_conditions)
        c_app_json = _canonical_json(candidate.applicability_conditions)
        if b_app_json != c_app_json:
            field_changes["applicability_conditions"] = {
                "old": json.loads(b_app_json),
                "new": json.loads(c_app_json),
            }
            semantic_change = True

        b_comp_json = _canonical_json(baseline.compliance_conditions)
        c_comp_json = _canonical_json(candidate.compliance_conditions)
        if b_comp_json != c_comp_json:
            field_changes["compliance_conditions"] = {
                "old": json.loads(b_comp_json),
                "new": json.loads(c_comp_json),
            }
            semantic_change = True

        # 4. Required Evidence & Severity
        b_ev = sorted(baseline.required_evidence or [])
        c_ev = sorted(candidate.required_evidence or [])
        if b_ev != c_ev:
            field_changes["required_evidence"] = {"old": b_ev, "new": c_ev}
            semantic_change = True

        if baseline.severity != candidate.severity:
            field_changes["severity"] = {
                "old": baseline.severity.value,
                "new": candidate.severity.value,
            }
            semantic_change = True

        # 5. Non-semantic fields: Source references and metadata
        b_src_json = _canonical_json(baseline.source_references)
        c_src_json = _canonical_json(candidate.source_references)
        provenance_change = b_src_json != c_src_json

        metadata_change = (
            getattr(baseline, "explanation", None)
            != getattr(candidate, "explanation", None)
            or getattr(baseline, "tags", None) != getattr(candidate, "tags", None)
        )

        affects_approval = (
            "compliance_conditions" in field_changes
            and "approval" in _canonical_json(field_changes["compliance_conditions"])
        )
        affects_boundary = (
            "evaluation_boundary" in field_changes
            or "applicability_conditions" in field_changes
        )

        if semantic_change:
            desc_parts = [
                f"{k} changed" for k in field_changes
            ]
            return RuleDiffRecord(
                rule_id=candidate.rule_id,
                change_type=RuleChangeType.SEMANTICALLY_MODIFIED,
                baseline_rule_version=baseline.rule_version,
                candidate_rule_version=candidate.rule_version,
                change_description=f"Rule '{candidate.rule_id}' semantically modified: {', '.join(desc_parts)}.",
                field_changes=field_changes,
                affects_boundary=affects_boundary,
                affects_approval=affects_approval,
                affects_permission=(
                    candidate.policy_family == PolicyFamily.AUTHORIZATION
                    and any(
                        k in field_changes
                        for k in (
                            "principal_selector",
                            "action_selector",
                            "resource_selector",
                            "policy_requirement",
                        )
                    )
                ),
                affects_confidentiality=(
                    candidate.policy_family == PolicyFamily.CONFIDENTIALITY
                ),
                affects_instruction_authority=(
                    candidate.policy_family == PolicyFamily.INSTRUCTION_AUTHORITY
                ),
            )

        if provenance_change:
            return RuleDiffRecord(
                rule_id=candidate.rule_id,
                change_type=RuleChangeType.PROVENANCE_ONLY,
                baseline_rule_version=baseline.rule_version,
                candidate_rule_version=candidate.rule_version,
                change_description=f"Rule '{candidate.rule_id}' source reference/provenance coordinates updated; semantics unchanged.",
                field_changes={"source_references": {"updated": True}},
                affects_boundary=False,
                affects_approval=False,
                affects_permission=False,
                affects_confidentiality=False,
                affects_instruction_authority=False,
            )

        if metadata_change:
            return RuleDiffRecord(
                rule_id=candidate.rule_id,
                change_type=RuleChangeType.METADATA_ONLY,
                baseline_rule_version=baseline.rule_version,
                candidate_rule_version=candidate.rule_version,
                change_description=f"Rule '{candidate.rule_id}' metadata/explanation updated; semantics unchanged.",
                field_changes={"metadata": {"updated": True}},
                affects_boundary=False,
                affects_approval=False,
                affects_permission=False,
                affects_confidentiality=False,
                affects_instruction_authority=False,
            )

        return RuleDiffRecord(
            rule_id=candidate.rule_id,
            change_type=RuleChangeType.UNCHANGED,
            baseline_rule_version=baseline.rule_version,
            candidate_rule_version=candidate.rule_version,
            change_description=f"Rule '{candidate.rule_id}' is semantically and structurally identical in baseline and candidate.",
            field_changes={},
            affects_boundary=False,
            affects_approval=False,
            affects_permission=False,
            affects_confidentiality=False,
            affects_instruction_authority=False,
        )
