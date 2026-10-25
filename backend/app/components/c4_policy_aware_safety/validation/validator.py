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
    PredicateOperator,
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
from app.components.c4_policy_aware_safety.predicates.evaluator import (
    field_reference_path,
)

SUPPORTED_PATH_ROOTS = {
    "principal": {"principal_id", "role", "roles", "attributes"},
    "tool_call": {"name", "arguments"},
    "action": {"tool_name", "arguments"},
    "authorization": {"status", "decision", "allowed", "reason", "decision_reason"},
    "approval": {"status", "approver_role", "approver_principal", "decision_reason", "approval_token"},
    "disclosure": {"marker", "recipient", "destination_channel"},
    "effect": {"target_entity", "state_change_observed", "committed_status", "delta"},
    "instruction": {"source_id", "source_type", "trust_classification", "claimed_role_in_text", "origin"},
    "trace": {"is_complete", "missing_stages", "total_events"},
    "resource": {"type", "id", "owner_id"},
    "context": None,  # dynamic keys permitted
}


def _validate_predicate_condition(pred: PredicateCondition) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    field = pred.field

    # 1. Check prefix
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

    parts = field.split(".")
    if len(parts) < 2 or any(len(p.strip()) == 0 for p in parts):
        issues.append(
            ValidationIssue(
                code=ValidationIssueCode.UNSUPPORTED,
                message=f"Field path '{field}' is malformed.",
                field=f"predicate.{field}",
                severity=Severity.HIGH,
                blocking=True,
            )
        )
        return issues

    root = parts[0]
    first_child = parts[1]
    allowed_children = SUPPORTED_PATH_ROOTS.get(root)
    if allowed_children is not None and first_child not in allowed_children and root != "resource":
        issues.append(
            ValidationIssue(
                code=ValidationIssueCode.UNSUPPORTED,
                message=f"Unsupported field path '{field}'. Root '{root}' does not support field '{first_child}'.",
                field=f"predicate.{field}",
                severity=Severity.HIGH,
                blocking=True,
            )
        )
        return issues

    # Validate that non-dynamic roots do not allow arbitrary nested subpaths (Section 4.C)
    dynamic_nested_roots = {
        ("tool_call", "arguments"),
        ("action", "arguments"),
        ("effect", "delta"),
        ("principal", "attributes"),
    }
    if len(parts) > 2 and root not in ("context", "resource") and (root, first_child) not in dynamic_nested_roots:
        issues.append(
            ValidationIssue(
                code=ValidationIssueCode.UNSUPPORTED,
                message=f"Unsupported nested field path '{field}'. Field '{root}.{first_child}' is a flat property and does not permit subpaths.",
                field=f"predicate.{field}",
                severity=Severity.HIGH,
                blocking=True,
            )
        )
        return issues

    # 2. Check operator and operand type compatibility
    op = pred.operator
    val = pred.value
    ref_path = field_reference_path(val)
    if ref_path is not None:
        # Operand is another evidence field: its type is only known at evaluation time.
        if not any(ref_path.startswith(pfx) for pfx in ALLOWLISTED_FIELD_PREFIXES):
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.UNSUPPORTED,
                    message=f"Field reference '{ref_path}' does not use an allowlisted evidence prefix.",
                    field=f"predicate.{field}",
                    severity=Severity.HIGH,
                    blocking=True,
                )
            )
        return issues
    from decimal import Decimal, InvalidOperation

    ordered_ops = {
        PredicateOperator.GREATER_THAN,
        PredicateOperator.GREATER_THAN_OR_EQUAL,
        PredicateOperator.LESS_THAN,
        PredicateOperator.LESS_THAN_OR_EQUAL,
    }
    if op in ordered_ops:
        is_num = False
        if isinstance(val, (int, float, Decimal)) and not isinstance(val, bool):
            is_num = True
        elif isinstance(val, str):
            try:
                Decimal(val)
                is_num = True
            except (InvalidOperation, ValueError):
                is_num = False
        if not is_num:
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.UNSUPPORTED,
                    message=f"Ordered comparison operator '{op.value}' requires a numeric or Decimal operand value, got {type(val).__name__} ({val!r}).",
                    field=f"predicate.{field}",
                    severity=Severity.HIGH,
                    blocking=True,
                )
            )

    if op in (PredicateOperator.IN, PredicateOperator.NOT_IN) and not isinstance(
        val, (list, tuple, set)
    ):
        issues.append(
            ValidationIssue(
                code=ValidationIssueCode.UNSUPPORTED,
                message=f"Membership operator '{op.value}' requires a collection operand value, got {type(val).__name__} ({val!r}).",
                field=f"predicate.{field}",
                severity=Severity.HIGH,
                blocking=True,
            )
        )

    return issues


def _check_predicate_fields(
    pred: CompoundPredicate | PredicateCondition | None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not pred:
        return issues

    if isinstance(pred, PredicateCondition):
        return _validate_predicate_condition(pred)

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

            # 4. Executability: the evaluator decides compliance from this predicate only, and an
            # empty predicate is always TRUE, so a DENY/REQUIRE rule without one could never FAIL.
            # (ALLOW rules are permission declarations and may have no condition.)
            if rule.policy_requirement != PolicyRequirement.ALLOW and (
                rule.compliance_conditions is None or not rule.compliance_conditions.conditions
            ):
                issues.append(
                    ValidationIssue(
                        code=ValidationIssueCode.UNSUPPORTED_CONDITION,
                        message=(
                            f"Rule '{rule.rule_id}' has no compliance condition, so it can never be violated. "
                            "Add a condition (e.g. from the reference rules) before contract acceptance."
                        ),
                        field="compliance_conditions",
                        severity=Severity.CRITICAL,
                        blocking=True,
                    )
                )

            # 4b. Predicate field allowlist check
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

    def validate_contract(
        self,
        contract: PolicyContractVersion,
        artifact_resolver: Callable[[str, str, int], ArtifactVersionRecord | None] | None = None,
    ) -> ContractValidationResult:
        resolver = artifact_resolver or (lambda p, a, v: None)
        candidates = [
            CandidateRule(
                project_id=r.project_id,
                rule_id=r.rule_id,
                rule_version=r.rule_version,
                policy_family=r.policy_family,
                principal_selector=r.principal_selector,
                action_selector=r.action_selector,
                resource_selector=r.resource_selector,
                applicability_conditions=r.applicability_conditions,
                policy_requirement=r.policy_requirement,
                compliance_conditions=r.compliance_conditions,
                evaluation_boundary=r.evaluation_boundary,
                required_evidence=r.required_evidence,
                severity=r.severity,
                source_references=r.source_references,
                validation_issues=[],
                review_status=r.review_status,
                extraction_metadata=r.acceptance_metadata or {},
            )
            for r in contract.rules
        ]
        return self.validate_contract_draft(
            contract.project_id,
            contract.contract_id,
            contract.version,
            candidates,
            resolver,
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
