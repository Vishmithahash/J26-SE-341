import re
from decimal import Decimal

from app.components.c4_policy_aware_safety.contracts.artifacts import (
    ArtifactVersionRecord,
    SourceReference,
)
from app.components.c4_policy_aware_safety.contracts.enums import (
    EvaluationBoundary,
    PolicyFamily,
    PolicyRequirement,
    RuleReviewStatus,
    Severity,
    ValidationIssueCode,
)
from app.components.c4_policy_aware_safety.contracts.predicates import (
    CompoundOperator,
    CompoundPredicate,
    PredicateCondition,
    PredicateOperator,
)
from app.components.c4_policy_aware_safety.contracts.rules import (
    CandidateRule,
    ValidationIssue,
)

AMBIGUOUS_KEYWORDS = [
    "reasonable",
    "appropriate",
    "discretionary",
    "as needed",
    "shortly",
    "fair",
    "unspecified",
    "normal",
]

# Pattern 1: Roles with <ROLE> must not <ACTION> <RESOURCE> exceeding <LIMIT> without <APPROVER_ROLE> approval.
PATTERN_REFUND_LIMIT = re.compile(
    r"[Rr]oles with\s+([A-Z0-9_]+)\s+must not\s+([a-z0-9_]+)\s+([a-z0-9_]+)\s+exceeding\s+(\$?[0-9]+(?:\.[0-9]{2})?)\s+without\s+([A-Z0-9_]+)\s+approval",
    re.IGNORECASE,
)

# Pattern 2: Roles with <ROLE> are forbidden from <ACTION> <RESOURCE>.
PATTERN_FORBIDDEN_ACTION = re.compile(
    r"[Rr]oles with\s+([A-Z0-9_]+)\s+are forbidden from\s+([a-z0-9_]+)\s+([a-z0-9_]+)",
    re.IGNORECASE,
)

# Pattern 3: No state change to <RESOURCE> may be committed by <ROLE> exceeding <LIMIT>.
PATTERN_COMMITTED_EFFECT = re.compile(
    r"[Nn]o state change to\s+([a-z0-9_]+)\s+may be committed by\s+([A-Z0-9_]+)\s+exceeding\s+(\$?[0-9]+(?:\.[0-9]{2})?)",
    re.IGNORECASE,
)

# Pattern 4: Information marked <MARKER> must not be disclosed to <RECIPIENT>.
PATTERN_CONFIDENTIALITY = re.compile(
    r"[Ii]nformation marked\s+([A-Z0-9_-]+)\s+must not be disclosed to\s+([a-z0-9_*-]+)",
    re.IGNORECASE,
)


class ControlledLanguageExtractor:
    """Deterministic policy rule extractor for explicit controlled-language patterns."""

    def extract_from_artifact(
        self, artifact: ArtifactVersionRecord
    ) -> list[CandidateRule]:
        candidates: list[CandidateRule] = []

        for section in artifact.sections:
            lines = section.content.split("\n")
            for line_idx, line in enumerate(lines):
                trimmed = line.strip()
                if not trimmed or trimmed.startswith("#"):
                    continue

                # Check for ambiguous wording in this line
                ambiguous_found = [
                    kw
                    for kw in AMBIGUOUS_KEYWORDS
                    if re.search(rf"\b{kw}\b", trimmed, re.IGNORECASE)
                ]

                # Pattern 1: Refund limit with approval
                m1 = PATTERN_REFUND_LIMIT.search(trimmed)
                if m1:
                    role, action, resource, limit_str, approver_role = m1.groups()
                    clean_limit = limit_str.replace("$", "")
                    limit_cents = (
                        int(Decimal(clean_limit) * 100)
                        if "." in clean_limit
                        else int(clean_limit)
                    )

                    source_ref = SourceReference(
                        project_id=artifact.project_id,
                        artifact_id=artifact.artifact_id,
                        artifact_version=artifact.version,
                        section_id=section.section_id,
                        supporting_excerpt=trimmed,
                    )

                    issues: list[ValidationIssue] = []
                    if ambiguous_found:
                        issues.append(
                            ValidationIssue(
                                code=ValidationIssueCode.AMBIGUOUS,
                                message=f"Ambiguous terms detected in rule text: {', '.join(ambiguous_found)}",
                                severity=Severity.MEDIUM,
                                blocking=False,
                            )
                        )

                    rule_id = f"RULE_{role}_{action.upper()}_LIMIT_{limit_cents}"
                    rule = CandidateRule(
                        project_id=artifact.project_id,
                        rule_id=rule_id,
                        rule_version=1,
                        policy_family=PolicyFamily.AUTHORIZATION,
                        principal_selector=role.upper(),
                        action_selector=action.lower(),
                        resource_selector=resource.lower(),
                        applicability_conditions=CompoundPredicate(
                            operator=CompoundOperator.ALL,
                            conditions=[
                                PredicateCondition(
                                    field="tool_call.arguments.amount",
                                    operator=PredicateOperator.GREATER_THAN,
                                    value=limit_cents,
                                )
                            ],
                        ),
                        policy_requirement=PolicyRequirement.REQUIRE,
                        compliance_conditions=CompoundPredicate(
                            operator=CompoundOperator.ALL,
                            conditions=[
                                PredicateCondition(
                                    field="approval.status",
                                    operator=PredicateOperator.EQUALS,
                                    value="APPROVED",
                                ),
                                PredicateCondition(
                                    field="approval.approver_role",
                                    operator=PredicateOperator.EQUALS,
                                    value=approver_role.upper(),
                                ),
                            ],
                        ),
                        evaluation_boundary=EvaluationBoundary.ATTEMPTED_ACTION,
                        required_evidence=[
                            "action_attempts",
                            "tool_executions",
                            "authorization_decisions",
                        ],
                        severity=Severity.HIGH,
                        source_references=[source_ref],
                        validation_issues=issues,
                        review_status=RuleReviewStatus.DRAFT,
                        extraction_metadata={
                            "extractor": "ControlledLanguageExtractor",
                            "pattern": "PATTERN_REFUND_LIMIT",
                            "line_number": line_idx + 1,
                        },
                    )
                    candidates.append(rule)
                    continue

                # Pattern 2: Absolute forbidden action
                m2 = PATTERN_FORBIDDEN_ACTION.search(trimmed)
                if m2:
                    role, action, resource = m2.groups()
                    source_ref = SourceReference(
                        project_id=artifact.project_id,
                        artifact_id=artifact.artifact_id,
                        artifact_version=artifact.version,
                        section_id=section.section_id,
                        supporting_excerpt=trimmed,
                    )
                    issues = []
                    if ambiguous_found:
                        issues.append(
                            ValidationIssue(
                                code=ValidationIssueCode.AMBIGUOUS,
                                message=f"Ambiguous terms: {', '.join(ambiguous_found)}",
                                severity=Severity.MEDIUM,
                                blocking=False,
                            )
                        )

                    rule_id = f"RULE_{role.upper()}_FORBID_{action.upper()}"
                    rule = CandidateRule(
                        project_id=artifact.project_id,
                        rule_id=rule_id,
                        rule_version=1,
                        policy_family=PolicyFamily.AUTHORIZATION,
                        principal_selector=role.upper(),
                        action_selector=action.lower(),
                        resource_selector=resource.lower(),
                        applicability_conditions=None,
                        policy_requirement=PolicyRequirement.DENY,
                        compliance_conditions=CompoundPredicate(
                            operator=CompoundOperator.ALL,
                            conditions=[
                                PredicateCondition(
                                    field="tool_call.name",
                                    operator=PredicateOperator.NOT_EQUALS,
                                    value=action.lower(),
                                )
                            ],
                        ),
                        evaluation_boundary=EvaluationBoundary.ATTEMPTED_ACTION,
                        required_evidence=["action_attempts"],
                        severity=Severity.CRITICAL,
                        source_references=[source_ref],
                        validation_issues=issues,
                        review_status=RuleReviewStatus.DRAFT,
                        extraction_metadata={
                            "extractor": "ControlledLanguageExtractor",
                            "pattern": "PATTERN_FORBIDDEN_ACTION",
                        },
                    )
                    candidates.append(rule)
                    continue

                # Pattern 3: Committed effect restriction
                m3 = PATTERN_COMMITTED_EFFECT.search(trimmed)
                if m3:
                    resource, role, limit_str = m3.groups()
                    clean_limit = limit_str.replace("$", "")
                    limit_cents = (
                        int(Decimal(clean_limit) * 100)
                        if "." in clean_limit
                        else int(clean_limit)
                    )
                    source_ref = SourceReference(
                        project_id=artifact.project_id,
                        artifact_id=artifact.artifact_id,
                        artifact_version=artifact.version,
                        section_id=section.section_id,
                        supporting_excerpt=trimmed,
                    )
                    rule_id = f"RULE_{role.upper()}_EFFECT_{resource.upper()}_LIMIT_{limit_cents}"
                    rule = CandidateRule(
                        project_id=artifact.project_id,
                        rule_id=rule_id,
                        rule_version=1,
                        policy_family=PolicyFamily.AUTHORIZATION,
                        principal_selector=role.upper(),
                        action_selector="*",
                        resource_selector=resource.lower(),
                        applicability_conditions=CompoundPredicate(
                            operator=CompoundOperator.ALL,
                            conditions=[
                                PredicateCondition(
                                    field="effect.delta.amount",
                                    operator=PredicateOperator.GREATER_THAN,
                                    value=limit_cents,
                                )
                            ],
                        ),
                        policy_requirement=PolicyRequirement.DENY,
                        compliance_conditions=CompoundPredicate(
                            operator=CompoundOperator.ALL,
                            conditions=[
                                PredicateCondition(
                                    field="effect.committed_status",
                                    operator=PredicateOperator.NOT_EQUALS,
                                    value="COMMITTED",
                                )
                            ],
                        ),
                        evaluation_boundary=EvaluationBoundary.COMMITTED_EFFECT,
                        required_evidence=["effects"],
                        severity=Severity.HIGH,
                        source_references=[source_ref],
                        validation_issues=[],
                        review_status=RuleReviewStatus.DRAFT,
                        extraction_metadata={
                            "extractor": "ControlledLanguageExtractor",
                            "pattern": "PATTERN_COMMITTED_EFFECT",
                        },
                    )
                    candidates.append(rule)
                    continue

                # Pattern 4: Confidentiality disclosure prohibition
                m4 = PATTERN_CONFIDENTIALITY.search(trimmed)
                if m4:
                    marker, recipient = m4.groups()
                    source_ref = SourceReference(
                        project_id=artifact.project_id,
                        artifact_id=artifact.artifact_id,
                        artifact_version=artifact.version,
                        section_id=section.section_id,
                        supporting_excerpt=trimmed,
                    )
                    rule_id = f"RULE_CONFIDENTIALITY_{marker.upper()}"
                    rule = CandidateRule(
                        project_id=artifact.project_id,
                        rule_id=rule_id,
                        rule_version=1,
                        policy_family=PolicyFamily.CONFIDENTIALITY,
                        principal_selector="*",
                        action_selector="*",
                        resource_selector=marker,
                        applicability_conditions=CompoundPredicate(
                            operator=CompoundOperator.ALL,
                            conditions=[
                                PredicateCondition(
                                    field="disclosure.marker",
                                    operator=PredicateOperator.EQUALS,
                                    value=marker,
                                )
                            ],
                        ),
                        policy_requirement=PolicyRequirement.DENY,
                        compliance_conditions=CompoundPredicate(
                            operator=CompoundOperator.ALL,
                            conditions=[
                                PredicateCondition(
                                    field="disclosure.recipient",
                                    operator=PredicateOperator.NOT_EQUALS,
                                    value=recipient,
                                )
                            ],
                        ),
                        evaluation_boundary=EvaluationBoundary.DISCLOSURE,
                        required_evidence=["disclosures"],
                        severity=Severity.CRITICAL,
                        source_references=[source_ref],
                        validation_issues=[],
                        review_status=RuleReviewStatus.DRAFT,
                        extraction_metadata={
                            "extractor": "ControlledLanguageExtractor",
                            "pattern": "PATTERN_CONFIDENTIALITY",
                        },
                    )
                    candidates.append(rule)
                    continue

                # Check if line looks like an attempted policy rule but outside supported patterns
                if any(
                    w in trimmed.lower()
                    for w in [
                        "must",
                        "forbidden",
                        "prohibited",
                        "allowed",
                        "shall",
                        "policy",
                    ]
                ):
                    source_ref = SourceReference(
                        project_id=artifact.project_id,
                        artifact_id=artifact.artifact_id,
                        artifact_version=artifact.version,
                        section_id=section.section_id,
                        supporting_excerpt=trimmed,
                    )
                    issues = [
                        ValidationIssue(
                            code=ValidationIssueCode.UNSUPPORTED,
                            message=f"Text resembles a policy requirement but does not match supported controlled-language grammar: '{trimmed}'",
                            severity=Severity.HIGH,
                            blocking=True,
                        )
                    ]
                    if ambiguous_found:
                        issues.append(
                            ValidationIssue(
                                code=ValidationIssueCode.AMBIGUOUS,
                                message=f"Ambiguous terms: {', '.join(ambiguous_found)}",
                                severity=Severity.HIGH,
                                blocking=True,
                            )
                        )
                    unsupported_rule = CandidateRule(
                        project_id=artifact.project_id,
                        rule_id=f"UNRESOLVED_LINE_{line_idx + 1}",
                        rule_version=1,
                        policy_family=PolicyFamily.AUTHORIZATION,
                        principal_selector="UNKNOWN",
                        action_selector="UNKNOWN",
                        resource_selector="UNKNOWN",
                        applicability_conditions=None,
                        policy_requirement=PolicyRequirement.DENY,
                        compliance_conditions=CompoundPredicate(
                            operator=CompoundOperator.ALL,
                            conditions=[],
                        ),
                        evaluation_boundary=EvaluationBoundary.ATTEMPTED_ACTION,
                        required_evidence=[],
                        severity=Severity.MEDIUM,
                        source_references=[source_ref],
                        validation_issues=issues,
                        review_status=RuleReviewStatus.REJECTED,
                        extraction_metadata={
                            "extractor": "ControlledLanguageExtractor",
                            "status": "UNSUPPORTED_GRAMMAR",
                        },
                    )
                    candidates.append(unsupported_rule)

        return candidates
