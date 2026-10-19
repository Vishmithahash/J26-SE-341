import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime

from app.components.c4_policy_aware_safety.contracts.artifacts import (
    ArtifactVersionRecord,
)
from app.components.c4_policy_aware_safety.contracts.enums import (
    ContractLifecycleState,
    PolicyRequirement,
    RuleReviewStatus,
    Severity,
    ValidationIssueCode,
)
from app.components.c4_policy_aware_safety.contracts.predicates import (
    ALLOWLISTED_FIELD_PREFIXES,
    CompoundPredicate,
    PredicateCondition,
)
from app.components.c4_policy_aware_safety.contracts.rules import (
    CandidateRule,
    ContractValidationResult,
    PolicyContractVersion,
    PolicyRule,
    ValidationIssue,
)
from app.components.c4_policy_aware_safety.derivation.intake import (
    validate_source_reference,
)


def _check_predicate_fields(
    pred: CompoundPredicate | PredicateCondition | None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not pred:
        return issues

    if isinstance(pred, PredicateCondition):
        field = pred.field
        if not any(field.startswith(pfx) for pfx in ALLOWLISTED_FIELD_PREFIXES):
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.UNSUPPORTED,
                    message=f"Field '{field}' does not use an allowlisted evidence prefix ({', '.join(sorted(ALLOWLISTED_FIELD_PREFIXES))}).",
                    field=f"predicate.{field}",
                    severity=Severity.HIGH,
                    blocking=True,
                )
            )
        return issues

    for cond in pred.conditions:
        issues.extend(_check_predicate_fields(cond))
    return issues


def detect_rule_conflicts(rules: list[CandidateRule]) -> list[ValidationIssue]:
    """Detect straightforward contradictory policy rules targeting the same scope."""
    issues: list[ValidationIssue] = []

    for i in range(len(rules)):
        for j in range(i + 1, len(rules)):
            r1 = rules[i]
            r2 = rules[j]

            # Same principal, action, resource, and boundary
            same_scope = (
                r1.principal_selector.upper() == r2.principal_selector.upper()
                and r1.action_selector.lower() == r2.action_selector.lower()
                and r1.resource_selector.lower() == r2.resource_selector.lower()
                and r1.evaluation_boundary == r2.evaluation_boundary
            )

            is_contradictory_req = (
                r1.policy_requirement == PolicyRequirement.ALLOW
                and r2.policy_requirement == PolicyRequirement.DENY
            ) or (
                r1.policy_requirement == PolicyRequirement.DENY
                and r2.policy_requirement == PolicyRequirement.ALLOW
            )

            if same_scope and is_contradictory_req:
                # Check applicability equivalence
                app1 = (
                    r1.applicability_conditions.model_dump_json()
                    if r1.applicability_conditions
                    else ""
                )
                app2 = (
                    r2.applicability_conditions.model_dump_json()
                    if r2.applicability_conditions
                    else ""
                )
                if app1 == app2:
                    issues.append(
                        ValidationIssue(
                            code=ValidationIssueCode.CONFLICTING,
                            message=f"Contradictory policy requirements between rule '{r1.rule_id}' ({r1.policy_requirement.value}) and rule '{r2.rule_id}' ({r2.policy_requirement.value}) for scope ({r1.principal_selector}, {r1.action_selector}, {r1.resource_selector}).",
                            field="policy_requirement",
                            severity=Severity.CRITICAL,
                            blocking=True,
                        )
                    )
    return issues


class PolicyContractValidator:
    """Validates policy candidate rules and versioned contracts."""

    def validate_rules(
        self,
        project_id: str,
        rules: list[CandidateRule],
        artifact_resolver: Callable[[str, str, int], ArtifactVersionRecord | None],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        seen_rule_ids = set()

        for rule in rules:
            # 1. Project boundary check
            if rule.project_id != project_id:
                issues.append(
                    ValidationIssue(
                        code=ValidationIssueCode.CROSS_PROJECT_REFERENCE,
                        message=f"Rule '{rule.rule_id}' belongs to project '{rule.project_id}', expected '{project_id}'.",
                        field="project_id",
                        severity=Severity.CRITICAL,
                        blocking=True,
                    )
                )

            # 2. Duplicate rule ID check
            if rule.rule_id in seen_rule_ids:
                issues.append(
                    ValidationIssue(
                        code=ValidationIssueCode.DUPLICATE_RULE_ID,
                        message=f"Duplicate rule identifier detected: '{rule.rule_id}'.",
                        field="rule_id",
                        severity=Severity.CRITICAL,
                        blocking=True,
                    )
                )
            seen_rule_ids.add(rule.rule_id)

            # 3. Source provenance check
            if not rule.source_references:
                issues.append(
                    ValidationIssue(
                        code=ValidationIssueCode.MISSING_SOURCE,
                        message=f"Rule '{rule.rule_id}' has no supporting source references.",
                        field="source_references",
                        severity=Severity.CRITICAL,
                        blocking=True,
                    )
                )
            else:
                for src in rule.source_references:
                    issues.extend(
                        validate_source_reference(project_id, src, artifact_resolver)
                    )

            # 4. Predicate field allowlist check
            issues.extend(_check_predicate_fields(rule.applicability_conditions))
            issues.extend(_check_predicate_fields(rule.compliance_conditions))

            # 5. Include pre-existing issues from extraction
            issues.extend(rule.validation_issues)

        # 6. Cross-rule conflict detection
        issues.extend(detect_rule_conflicts(rules))

        return issues

    def validate_contract_draft(
        self,
        project_id: str,
        contract_id: str,
        version: int,
        candidate_rules: list[CandidateRule],
        artifact_resolver: Callable[[str, str, int], ArtifactVersionRecord | None],
    ) -> ContractValidationResult:
        issues = self.validate_rules(project_id, candidate_rules, artifact_resolver)
        has_blocking = any(i.blocking for i in issues)

        return ContractValidationResult(
            contract_id=contract_id,
            version=version,
            is_valid=not has_blocking,
            issues=issues,
            rules_validated_count=len(candidate_rules),
        )

    def build_accepted_contract(
        self,
        project_id: str,
        contract_id: str,
        version: int,
        candidate_rules: list[CandidateRule],
        artifact_resolver: Callable[[str, str, int], ArtifactVersionRecord | None],
        accepted_by: str,
        rationale: str | None = None,
    ) -> PolicyContractVersion:
        """Explicitly accepts validated rules into an immutable PolicyContractVersion.

        Raises ValueError if any blocking issue is detected.
        """
        validation_res = self.validate_contract_draft(
            project_id, contract_id, version, candidate_rules, artifact_resolver
        )
        if not validation_res.is_valid:
            blocking_reasons = "; ".join(
                i.message for i in validation_res.issues if i.blocking
            )
            raise ValueError(
                f"Cannot accept contract due to blocking validation issues: {blocking_reasons}"
            )

        accepted_rules: list[PolicyRule] = []
        referenced_artifact_versions: dict[str, int] = {}

        now = datetime.now(UTC)
        acceptance_meta = {
            "accepted_by": accepted_by,
            "accepted_at": now.isoformat(),
            "rationale": rationale or "Accepted by authorized policy reviewer",
        }

        for cand in candidate_rules:
            # Map candidate to PolicyRule
            for src in cand.source_references:
                referenced_artifact_versions[src.artifact_id] = src.artifact_version

            prule = PolicyRule(
                project_id=cand.project_id,
                rule_id=cand.rule_id,
                rule_version=cand.rule_version,
                policy_family=cand.policy_family,
                principal_selector=cand.principal_selector,
                action_selector=cand.action_selector,
                resource_selector=cand.resource_selector,
                applicability_conditions=cand.applicability_conditions,
                policy_requirement=cand.policy_requirement,
                compliance_conditions=cand.compliance_conditions,
                evaluation_boundary=cand.evaluation_boundary,
                required_evidence=cand.required_evidence,
                severity=cand.severity,
                source_references=cand.source_references,
                review_status=RuleReviewStatus.ACCEPTED,
                acceptance_metadata=acceptance_meta,
            )
            accepted_rules.append(prule)

        # Canonical content hash
        rules_dict = [r.model_dump(mode="json") for r in accepted_rules]
        canon_json = json.dumps(rules_dict, sort_keys=True)
        content_hash = hashlib.sha256(canon_json.encode("utf-8")).hexdigest()

        return PolicyContractVersion(
            contract_id=contract_id,
            project_id=project_id,
            version=version,
            lifecycle_state=ContractLifecycleState.ACCEPTED,
            rules=accepted_rules,
            referenced_artifact_versions=referenced_artifact_versions,
            acceptance_metadata=acceptance_meta,
            content_hash=content_hash,
            created_at=now,
            updated_at=now,
        )
