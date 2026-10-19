from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from app.components.c4_policy_aware_safety.contracts.artifacts import (
    ArtifactVersionRecord,
)
from app.components.c4_policy_aware_safety.contracts.enums import (
    RuleReviewStatus,
    Severity,
    ValidationIssueCode,
)
from app.components.c4_policy_aware_safety.contracts.rules import (
    CandidateRule,
    ValidationIssue,
)
from app.components.c4_policy_aware_safety.derivation.intake import (
    validate_source_reference,
)


class StructuredRuleImporter:
    """Imports explicit structured candidate policy rules with provenance verification."""

    def import_candidate_rules(
        self,
        project_id: str,
        rules_payload: list[dict[str, Any]],
        artifact_resolver: Callable[[str, str, int], ArtifactVersionRecord | None],
    ) -> list[CandidateRule]:
        imported: list[CandidateRule] = []

        for item in rules_payload:
            # Inject project_id if missing or mismatch
            raw_item = dict(item)
            raw_item["project_id"] = project_id

            try:
                candidate = CandidateRule.model_validate(raw_item)
            except (ValidationError, ValueError, TypeError) as e:
                # Malformed candidate definition
                rule_id = raw_item.get("rule_id", "MALFORMED_RULE")
                malformed_rule = CandidateRule(
                    project_id=project_id,
                    rule_id=rule_id,
                    rule_version=1,
                    policy_family=raw_item.get("policy_family", "AUTHORIZATION"),
                    principal_selector=raw_item.get("principal_selector", "*"),
                    action_selector=raw_item.get("action_selector", "*"),
                    resource_selector=raw_item.get("resource_selector", "*"),
                    policy_requirement=raw_item.get("policy_requirement", "DENY"),
                    compliance_conditions={"operator": "ALL", "conditions": []},
                    evaluation_boundary=raw_item.get(
                        "evaluation_boundary", "ATTEMPTED_ACTION"
                    ),
                    severity=Severity.HIGH,
                    validation_issues=[
                        ValidationIssue(
                            code=ValidationIssueCode.UNSUPPORTED,
                            message=f"Schema validation error on structured rule import: {e!s}",
                            severity=Severity.CRITICAL,
                            blocking=True,
                        )
                    ],
                    review_status=RuleReviewStatus.REJECTED,
                )
                imported.append(malformed_rule)
                continue

            # Verify source provenance
            issues: list[ValidationIssue] = list(candidate.validation_issues)
            if not candidate.source_references:
                issues.append(
                    ValidationIssue(
                        code=ValidationIssueCode.MISSING_SOURCE,
                        message="Rule does not reference any supporting source artifact.",
                        field="source_references",
                        severity=Severity.CRITICAL,
                        blocking=True,
                    )
                )
            else:
                for src in candidate.source_references:
                    ref_issues = validate_source_reference(
                        project_id, src, artifact_resolver
                    )
                    issues.extend(ref_issues)

            updated_status = (
                RuleReviewStatus.DRAFT
                if not any(i.blocking for i in issues)
                else RuleReviewStatus.REJECTED
            )

            candidate_with_issues = candidate.model_copy(
                update={"validation_issues": issues, "review_status": updated_status}
            )
            imported.append(candidate_with_issues)

        return imported
