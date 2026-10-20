import pytest

from app.components.c4_policy_aware_safety.contracts.artifacts import (
    ArtifactSection,
    ArtifactVersionRecord,
    SourceReference,
)
from app.components.c4_policy_aware_safety.contracts.enums import (
    ArtifactKind,
    ContractLifecycleState,
    EvaluationBoundary,
    PolicyFamily,
    PolicyRequirement,
    RuleReviewStatus,
    ValidationIssueCode,
)
from app.components.c4_policy_aware_safety.contracts.predicates import (
    CompoundOperator,
    CompoundPredicate,
    PredicateCondition,
    PredicateOperator,
)
from app.components.c4_policy_aware_safety.contracts.rules import CandidateRule
from app.components.c4_policy_aware_safety.validation.validator import (
    PolicyContractValidator,
    detect_rule_conflicts,
)


@pytest.fixture
def sample_artifact():
    content = "Roles with CUSTOMER_SUPPORT must not process_refund order_refund exceeding 5000 without MANAGER approval."
    return ArtifactVersionRecord(
        project_id="proj-alpha",
        artifact_id="policy-01",
        artifact_kind=ArtifactKind.POLICY_DOCUMENT,
        version=1,
        content_hash="hash123456",
        normalized_content=content,
        sections=[ArtifactSection(section_id="sec-1", title="Sec 1", content=content)],
        metadata={},
    )


def test_duplicate_rule_id_detection(sample_artifact):
    src = SourceReference(
        project_id="proj-alpha",
        artifact_id="policy-01",
        artifact_version=1,
        section_id="sec-1",
        supporting_excerpt=sample_artifact.normalized_content,
    )

    r1 = CandidateRule(
        project_id="proj-alpha",
        rule_id="RULE_REFUND_LIMIT",
        rule_version=1,
        policy_family=PolicyFamily.AUTHORIZATION,
        principal_selector="CUSTOMER_SUPPORT",
        action_selector="process_refund",
        resource_selector="order_refund",
        policy_requirement=PolicyRequirement.REQUIRE,
        compliance_conditions=CompoundPredicate(
            operator=CompoundOperator.ALL, conditions=[]
        ),
        evaluation_boundary=EvaluationBoundary.ATTEMPTED_ACTION,
        source_references=[src],
    )
    r2 = CandidateRule(
        project_id="proj-alpha",
        rule_id="RULE_REFUND_LIMIT",  # Duplicate ID
        rule_version=1,
        policy_family=PolicyFamily.AUTHORIZATION,
        principal_selector="CUSTOMER_SUPPORT",
        action_selector="process_refund",
        resource_selector="order_refund",
        policy_requirement=PolicyRequirement.REQUIRE,
        compliance_conditions=CompoundPredicate(
            operator=CompoundOperator.ALL, conditions=[]
        ),
        evaluation_boundary=EvaluationBoundary.ATTEMPTED_ACTION,
        source_references=[src],
    )

    validator = PolicyContractValidator()
    issues = validator.validate_rules(
        "proj-alpha", [r1, r2], lambda p, a, v: sample_artifact
    )
    assert any(i.code == ValidationIssueCode.DUPLICATE_RULE_ID for i in issues)


def test_straightforward_conflict_detection(sample_artifact):
    src = SourceReference(
        project_id="proj-alpha",
        artifact_id="policy-01",
        artifact_version=1,
        section_id="sec-1",
        supporting_excerpt=sample_artifact.normalized_content,
    )

    # Rule 1 says ALLOW
    r1 = CandidateRule(
        project_id="proj-alpha",
        rule_id="RULE_ALLOW_REFUND",
        rule_version=1,
        policy_family=PolicyFamily.AUTHORIZATION,
        principal_selector="CUSTOMER_SUPPORT",
        action_selector="process_refund",
        resource_selector="order_refund",
        policy_requirement=PolicyRequirement.ALLOW,
        compliance_conditions=CompoundPredicate(
            operator=CompoundOperator.ALL, conditions=[]
        ),
        evaluation_boundary=EvaluationBoundary.ATTEMPTED_ACTION,
        source_references=[src],
    )
    # Rule 2 says DENY on identical scope
    r2 = CandidateRule(
        project_id="proj-alpha",
        rule_id="RULE_DENY_REFUND",
        rule_version=1,
        policy_family=PolicyFamily.AUTHORIZATION,
        principal_selector="CUSTOMER_SUPPORT",
        action_selector="process_refund",
        resource_selector="order_refund",
        policy_requirement=PolicyRequirement.DENY,
        compliance_conditions=CompoundPredicate(
            operator=CompoundOperator.ALL, conditions=[]
        ),
        evaluation_boundary=EvaluationBoundary.ATTEMPTED_ACTION,
        source_references=[src],
    )

    conflicts = detect_rule_conflicts([r1, r2])
    assert len(conflicts) > 0
    assert any(c.code == ValidationIssueCode.CONFLICTING for c in conflicts)


def test_blocking_issues_prevent_acceptance(sample_artifact):
    src = SourceReference(
        project_id="proj-alpha",
        artifact_id="policy-01",
        artifact_version=1,
        section_id="sec-1",
        supporting_excerpt=sample_artifact.normalized_content,
    )

    # Unallowlisted field in predicate (blocking issue)
    invalid_rule = CandidateRule(
        project_id="proj-alpha",
        rule_id="RULE_INVALID_PRED",
        rule_version=1,
        policy_family=PolicyFamily.AUTHORIZATION,
        principal_selector="SUPPORT",
        action_selector="refund",
        resource_selector="order",
        policy_requirement=PolicyRequirement.DENY,
        compliance_conditions=CompoundPredicate(
            operator=CompoundOperator.ALL,
            conditions=[
                PredicateCondition(
                    field="dangerous_root.eval",  # Unallowlisted prefix
                    operator=PredicateOperator.EQUALS,
                    value=1,
                )
            ],
        ),
        evaluation_boundary=EvaluationBoundary.ATTEMPTED_ACTION,
        source_references=[src],
    )

    validator = PolicyContractValidator()
    with pytest.raises(ValueError) as exc:
        validator.build_accepted_contract(
            project_id="proj-alpha",
            contract_id="contract-01",
            version=1,
            candidate_rules=[invalid_rule],
            artifact_resolver=lambda p, a, v: sample_artifact,
            accepted_by="auditor@company.org",
        )
    assert "Cannot accept contract due to blocking validation issues" in str(exc.value)


def test_successful_contract_acceptance_and_immutability(sample_artifact):
    src = SourceReference(
        project_id="proj-alpha",
        artifact_id="policy-01",
        artifact_version=1,
        section_id="sec-1",
        supporting_excerpt=sample_artifact.normalized_content,
    )

    valid_rule = CandidateRule(
        project_id="proj-alpha",
        rule_id="RULE_VALID_REFUND_5000",
        rule_version=1,
        policy_family=PolicyFamily.AUTHORIZATION,
        principal_selector="CUSTOMER_SUPPORT",
        action_selector="process_refund",
        resource_selector="order_refund",
        applicability_conditions=CompoundPredicate(
            operator=CompoundOperator.ALL,
            conditions=[
                PredicateCondition(
                    field="tool_call.arguments.amount",
                    operator=PredicateOperator.GREATER_THAN,
                    value=5000,
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
                )
            ],
        ),
        evaluation_boundary=EvaluationBoundary.ATTEMPTED_ACTION,
        source_references=[src],
    )

    validator = PolicyContractValidator()
    contract = validator.build_accepted_contract(
        project_id="proj-alpha",
        contract_id="contract-01",
        version=1,
        candidate_rules=[valid_rule],
        artifact_resolver=lambda p, a, v: sample_artifact,
        accepted_by="compliance_officer_42",
        rationale="Approved for testing suite",
    )

    assert contract.lifecycle_state == ContractLifecycleState.ACCEPTED
    assert contract.version == 1
    assert contract.content_hash is not None
    assert len(contract.rules) == 1
    assert contract.rules[0].review_status == RuleReviewStatus.ACCEPTED
    assert contract.acceptance_metadata["accepted_by"] == "compliance_officer_42"
