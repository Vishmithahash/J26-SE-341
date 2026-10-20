"""Bounded natural-language policy extractor with source grounding, decomposition, and validation."""

import re
from typing import Any

from app.components.c4_policy_aware_safety.contracts.artifacts import (
    ArtifactVersionRecord,
    SourceReference,
)
from app.components.c4_policy_aware_safety.contracts.bindings import DomainBinding
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
from app.components.c4_policy_aware_safety.extraction.provider import (
    PolicyExtractionProvider,
    get_extraction_provider,
)

ADVERSARIAL_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"system\s+prompt\s+override", re.IGNORECASE),
    re.compile(r"grant\s+admin\s+access", re.IGNORECASE),
    re.compile(r"bypass\s+(safety|policy|all)\s+checks?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
]


class BoundedNLPolicyExtractor:
    """Extracts bounded candidate policy rules from natural-language policy text.

    Enforces:
    1. Exact source coordinate grounding.
    2. Data-only authority (anti-prompt-injection defense).
    3. Sentence decomposition (permissions vs limits).
    4. Domain role/tool/resource binding validation.
    5. Draft-only lifecycle state (never automatically accepted).
    """

    def __init__(
        self,
        provider: PolicyExtractionProvider | None = None,
    ) -> None:
        self.provider = provider or get_extraction_provider()

    def extract_candidates(
        self,
        artifact: ArtifactVersionRecord,
        binding: DomainBinding,
        options: dict[str, Any] | None = None,
    ) -> tuple[list[CandidateRule], dict[str, Any]]:
        """
        Execute bounded extraction on artifact and validate candidates against domain bindings.
        Returns: (candidate_rules, provider_metadata)
        """
        opts = options or {}
        raw_candidates, meta = self.provider.extract_candidates(artifact, opts)

        candidate_rules: list[CandidateRule] = []

        for raw in raw_candidates:
            # 1. Output Schema Validation
            issues: list[ValidationIssue] = []
            if not isinstance(raw, dict):
                continue

            rule_id = raw.get("rule_id")
            policy_family_str = raw.get("policy_family")
            if not rule_id or not policy_family_str:
                # Malformed output
                issues.append(
                    ValidationIssue(
                        code=ValidationIssueCode.INVALID_SCHEMA,
                        message="Extracted output missing required 'rule_id' or 'policy_family'.",
                        field="rule_schema",
                        severity=Severity.CRITICAL,
                        blocking=True,
                    )
                )
                fake_rule = CandidateRule(
                    project_id=artifact.project_id,
                    rule_id=rule_id or f"MALFORMED_RULE_{len(candidate_rules) + 1}",
                    rule_version=1,
                    policy_family=PolicyFamily.AUTHORIZATION,
                    principal_selector="*",
                    action_selector="*",
                    resource_selector="*",
                    policy_requirement=PolicyRequirement.ALLOW,
                    compliance_conditions=CompoundPredicate(
                        operator=CompoundOperator.ALL, conditions=[]
                    ),
                    evaluation_boundary=EvaluationBoundary.ATTEMPTED_ACTION,
                    validation_issues=issues,
                    review_status=RuleReviewStatus.REJECTED,
                    extraction_metadata={"malformed_raw": raw},
                )
                candidate_rules.append(fake_rule)
                continue

            try:
                policy_family = PolicyFamily(policy_family_str)
            except ValueError:
                issues.append(
                    ValidationIssue(
                        code=ValidationIssueCode.INVALID_SCHEMA,
                        message=f"Unsupported policy family '{policy_family_str}'.",
                        field="policy_family",
                        severity=Severity.CRITICAL,
                        blocking=True,
                    )
                )
                policy_family = PolicyFamily.AUTHORIZATION

            principal_sel = raw.get("principal_selector", "*")
            action_sel = raw.get("action_selector", "*")
            resource_sel = raw.get("resource_selector", "*")
            req_str = raw.get("policy_requirement", "ALLOW")
            try:
                requirement = PolicyRequirement(req_str)
            except ValueError:
                requirement = PolicyRequirement.ALLOW

            eval_b_str = raw.get("evaluation_boundary", "ATTEMPTED_ACTION")
            try:
                eval_boundary = EvaluationBoundary(eval_b_str)
            except ValueError:
                eval_boundary = EvaluationBoundary.ATTEMPTED_ACTION

            supporting_excerpt = str(raw.get("supporting_excerpt", "")).strip()

            # 2. Anti-Prompt-Injection Filter & Data-Only Authority
            # Quoted attacks or prompt injections inside policy docs must NEVER become governance rules.
            # However: Do not use suspicious keywords alone to reject legitimate policy clauses (e.g. governance
            # rules stating that customer text saying "ignore previous instructions" cannot grant authority).
            is_governance_denial = (
                policy_family == PolicyFamily.INSTRUCTION_AUTHORITY
                or requirement == PolicyRequirement.DENY
                or any(
                    neg in supporting_excerpt.lower()
                    for neg in [
                        "cannot grant",
                        "never grant",
                        "must not",
                        "prohibit",
                        "denied",
                        "reject",
                        "disregard",
                        "untrusted",
                    ]
                )
            )

            is_injection = False
            has_quoted_attack = False
            for pat in ADVERSARIAL_INJECTION_PATTERNS:
                if pat.search(supporting_excerpt) or pat.search(str(raw.get("explanation", ""))):
                    has_quoted_attack = True
                    if not is_governance_denial or raw.get("is_injection_candidate"):
                        is_injection = True
                        break

            if is_injection or raw.get("is_injection_candidate"):
                issues.append(
                    ValidationIssue(
                        code=ValidationIssueCode.INJECTION_SUSPECTED,
                        message="Extracted candidate contains potential prompt-injection attack pattern or override text; rejected.",
                        field="supporting_excerpt",
                        severity=Severity.CRITICAL,
                        blocking=True,
                    )
                )
            elif has_quoted_attack:
                # Quoted attack text in legitimate governance: attach review issue for human review
                issues.append(
                    ValidationIssue(
                        code=ValidationIssueCode.AMBIGUOUS,
                        message="Candidate contains quoted untrusted attack pattern in governing rule; requires manual review before acceptance.",
                        field="supporting_excerpt",
                        severity=Severity.MEDIUM,
                        blocking=False,
                    )
                )

            # 3. Exact Source Reference Grounding
            source_refs: list[SourceReference] = []
            if supporting_excerpt:
                start_char = artifact.normalized_content.find(supporting_excerpt)
                if start_char == -1:
                    issues.append(
                        ValidationIssue(
                            code=ValidationIssueCode.EXCERPT_MISMATCH,
                            message=f"Supporting excerpt '{supporting_excerpt}' not found in artifact '{artifact.artifact_id}' v{artifact.version}.",
                            field="source_references.supporting_excerpt",
                            severity=Severity.CRITICAL,
                            blocking=True,
                        )
                    )
                    end_char = None
                else:
                    end_char = start_char + len(supporting_excerpt)
                    source_refs.append(
                        SourceReference(
                            project_id=artifact.project_id,
                            artifact_id=artifact.artifact_id,
                            artifact_version=artifact.version,
                            start_char=start_char,
                            end_char=end_char,
                            supporting_excerpt=supporting_excerpt,
                        )
                    )
            else:
                issues.append(
                    ValidationIssue(
                        code=ValidationIssueCode.MISSING_SOURCE,
                        message="Candidate rule does not declare a supporting excerpt for source grounding.",
                        field="source_references",
                        severity=Severity.HIGH,
                        blocking=True,
                    )
                )

            # 4. Domain Role / Tool / Resource Binding Validation
            if principal_sel != "*":
                known_roles = [r.role_name.upper() for r in binding.roles]
                if principal_sel.upper() not in known_roles:
                    issues.append(
                        ValidationIssue(
                            code=ValidationIssueCode.MISSING_ROLE,
                            message=f"Principal selector '{principal_sel}' not found in domain binding roles: {known_roles}.",
                            field="principal_selector",
                            severity=Severity.HIGH,
                            blocking=True,
                        )
                    )

            if action_sel != "*":
                known_tools = [t.tool_name.lower() for t in binding.tools]
                if action_sel.lower() not in known_tools:
                    issues.append(
                        ValidationIssue(
                            code=ValidationIssueCode.MISSING_TOOL,
                            message=f"Action selector '{action_sel}' not found in domain binding tools: {known_tools}.",
                            field="action_selector",
                            severity=Severity.HIGH,
                            blocking=True,
                        )
                    )

            if resource_sel != "*":
                known_res = [r.resource_type.lower() for r in binding.resources]
                if resource_sel.lower() not in known_res:
                    issues.append(
                        ValidationIssue(
                            code=ValidationIssueCode.MISSING_RESOURCE,
                            message=f"Resource selector '{resource_sel}' not found in domain binding resources: {known_res}.",
                            field="resource_selector",
                            severity=Severity.HIGH,
                            blocking=True,
                        )
                    )

            # 5. Predicate Semantics, Units, and Conditions
            app_pred = None
            if raw.get("applicability_field"):
                # Unit check: if threshold without verified units
                if "amount" in raw["applicability_field"] or "credit" in raw["applicability_field"]:
                    unit = raw.get("applicability_unit", "cents")
                    if unit not in ("cents", "USD", "currency"):
                        issues.append(
                            ValidationIssue(
                                code=ValidationIssueCode.MISSING_UNIT,
                                message="Threshold condition lacks explicit normalized monetary unit.",
                                field="applicability_conditions.unit",
                                severity=Severity.HIGH,
                                blocking=True,
                            )
                        )

                app_pred = CompoundPredicate(
                    operator=CompoundOperator.ALL,
                    conditions=[
                        PredicateCondition(
                            field=raw["applicability_field"],
                            operator=PredicateOperator(raw.get("applicability_operator", "GREATER_THAN")),
                            value=raw.get("applicability_value", 5000),
                        )
                    ],
                )

            comp_pred_list: list[PredicateCondition] = []
            if raw.get("compliance_field"):
                comp_pred_list.append(
                    PredicateCondition(
                        field=raw["compliance_field"],
                        operator=PredicateOperator(raw.get("compliance_operator", "EQUALS")),
                        value=raw.get("compliance_value", "APPROVED"),
                    )
                )

            # 6. Approval authority validation
            if (
                any("approval" in c.field for c in comp_pred_list)
                and not binding.approval_states
            ):
                issues.append(
                    ValidationIssue(
                        code=ValidationIssueCode.UNSUPPORTED_CONDITION,
                        message="Approval condition specified but domain binding defines no approval states.",
                        field="compliance_conditions.approval",
                        severity=Severity.HIGH,
                        blocking=True,
                    )
                )

            comp_pred = CompoundPredicate(
                operator=CompoundOperator.ALL,
                conditions=comp_pred_list,
            )

            # 7. Initial Lifecycle Review Status
            # Candidates with blocking issues start as REJECTED; valid candidates start as DRAFT
            has_blocking_issue = any(i.blocking for i in issues)
            status = RuleReviewStatus.REJECTED if has_blocking_issue else RuleReviewStatus.DRAFT

            candidate = CandidateRule(
                project_id=artifact.project_id,
                rule_id=rule_id,
                rule_version=1,
                policy_family=policy_family,
                principal_selector=principal_sel,
                action_selector=action_sel,
                resource_selector=resource_sel,
                applicability_conditions=app_pred,
                policy_requirement=requirement,
                compliance_conditions=comp_pred,
                evaluation_boundary=eval_boundary,
                required_evidence=raw.get("required_evidence", []),
                severity=Severity(raw.get("severity", "HIGH")),
                source_references=source_refs,
                validation_issues=issues,
                review_status=status,
                extraction_metadata={
                    "provider_id": meta.get("provider_id"),
                    "model_identifier": meta.get("model_identifier"),
                    "schema_version": meta.get("schema_version"),
                },
            )
            candidate_rules.append(candidate)

        # 8. Check for Straightforward Contradictions Between Candidate Rules
        self._check_conflicting_candidates(candidate_rules)

        return candidate_rules, meta

    def _check_conflicting_candidates(self, candidates: list[CandidateRule]) -> None:
        """Flag contradictory rules attempting contradictory permissions on identical selectors."""
        for i, c1 in enumerate(candidates):
            for j, c2 in enumerate(candidates):
                if i >= j:
                    continue
                if (
                    c1.policy_family == c2.policy_family
                    and c1.principal_selector == c2.principal_selector
                    and c1.action_selector == c2.action_selector
                    and c1.resource_selector == c2.resource_selector
                    and c1.policy_requirement == PolicyRequirement.ALLOW
                    and c2.policy_requirement == PolicyRequirement.DENY
                    and not c1.applicability_conditions
                    and not c2.applicability_conditions
                ):
                        conflict_issue = ValidationIssue(
                            code=ValidationIssueCode.CONFLICTING,
                            message=f"Rule '{c1.rule_id}' directly contradicts '{c2.rule_id}' with opposing requirements without conditions.",
                            field="policy_requirement",
                            severity=Severity.HIGH,
                            blocking=True,
                        )
                        c1.validation_issues.append(conflict_issue)
                        c2.validation_issues.append(conflict_issue)
                        c1.review_status = RuleReviewStatus.REJECTED
                        c2.review_status = RuleReviewStatus.REJECTED
