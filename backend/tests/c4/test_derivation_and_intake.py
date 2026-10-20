from app.components.c4_policy_aware_safety.contracts.artifacts import (
    ArtifactCreate,
    ArtifactSection,
    ArtifactVersionRecord,
    SourceReference,
)
from app.components.c4_policy_aware_safety.contracts.enums import (
    ArtifactKind,
    PolicyFamily,
    PolicyRequirement,
    ValidationIssueCode,
)
from app.components.c4_policy_aware_safety.derivation.controlled_language import (
    ControlledLanguageExtractor,
)
from app.components.c4_policy_aware_safety.derivation.importer import (
    StructuredRuleImporter,
)
from app.components.c4_policy_aware_safety.derivation.intake import (
    normalize_artifact,
    validate_source_reference,
)


def test_auto_detect_sections_and_hash():
    text = (
        "# Security Policy Overview\n"
        "This is general preamble.\n\n"
        "## 1. Refund Policies\n"
        "Roles with CUSTOMER_SUPPORT must not process_refund order_refund exceeding 5000 without MANAGER approval.\n\n"
        "## 2. Customer Protection\n"
        "Roles with CUSTOMER_SUPPORT are forbidden from delete_customer customer_profile.\n"
    )

    create_req = ArtifactCreate(
        artifact_id="policy-doc-01",
        artifact_kind=ArtifactKind.POLICY_DOCUMENT,
        raw_content=text,
    )
    record = normalize_artifact(
        project_id="proj-alpha", create_req=create_req, next_version=1
    )

    assert record.version == 1
    assert record.project_id == "proj-alpha"
    assert len(record.content_hash) == 64
    assert len(record.sections) >= 2


def test_source_reference_valid_and_invalid():
    sample_text = "Roles with CUSTOMER_SUPPORT must not process_refund order_refund exceeding 5000 without MANAGER approval."
    artifact = ArtifactVersionRecord(
        project_id="proj-alpha",
        artifact_id="art-01",
        artifact_kind=ArtifactKind.POLICY_DOCUMENT,
        version=1,
        content_hash="abc123hash",
        normalized_content=sample_text,
        sections=[
            ArtifactSection(
                section_id="sec-refund",
                title="Refund Section",
                content=sample_text,
                start_char=0,
                end_char=len(sample_text),
            )
        ],
        metadata={},
    )

    def resolver(proj, art_id, ver):
        if proj == "proj-alpha" and art_id == "art-01" and ver == 1:
            return artifact
        return None

    # 1. Valid source reference
    valid_ref = SourceReference(
        project_id="proj-alpha",
        artifact_id="art-01",
        artifact_version=1,
        section_id="sec-refund",
        supporting_excerpt=sample_text,
    )
    issues = validate_source_reference("proj-alpha", valid_ref, resolver)
    assert len(issues) == 0

    # 2. Version mismatch / artifact not found
    bad_ver_ref = SourceReference(
        project_id="proj-alpha",
        artifact_id="art-01",
        artifact_version=2,  # v2 does not exist
        supporting_excerpt=sample_text,
    )
    issues_bad_ver = validate_source_reference("proj-alpha", bad_ver_ref, resolver)
    assert any(i.code == ValidationIssueCode.INVALID_REFERENCE for i in issues_bad_ver)

    # 3. Cross-project reference rejection
    cross_proj_ref = SourceReference(
        project_id="proj-beta",  # Different project
        artifact_id="art-01",
        artifact_version=1,
        supporting_excerpt=sample_text,
    )
    issues_cross = validate_source_reference("proj-alpha", cross_proj_ref, resolver)
    assert any(
        i.code == ValidationIssueCode.CROSS_PROJECT_REFERENCE for i in issues_cross
    )

    # 4. Excerpt mismatch
    mismatch_ref = SourceReference(
        project_id="proj-alpha",
        artifact_id="art-01",
        artifact_version=1,
        section_id="sec-refund",
        supporting_excerpt="This excerpt does not exist in the source document at all.",
    )
    issues_mismatch = validate_source_reference("proj-alpha", mismatch_ref, resolver)
    assert any(i.code == ValidationIssueCode.EXCERPT_MISMATCH for i in issues_mismatch)


def test_tool_specification_cannot_grant_authorization():
    tool_text = "Tool process_refund is available with parameters amount and order_id."
    artifact = ArtifactVersionRecord(
        project_id="proj-alpha",
        artifact_id="tool-spec-01",
        artifact_kind=ArtifactKind.TOOL_SPECIFICATION,  # TOOL_SPECIFICATION
        version=1,
        content_hash="toolhash123",
        normalized_content=tool_text,
        sections=[
            ArtifactSection(
                section_id="sec-default", title="Tool Spec", content=tool_text
            )
        ],
        metadata={},
    )

    ref = SourceReference(
        project_id="proj-alpha",
        artifact_id="tool-spec-01",
        artifact_version=1,
        supporting_excerpt=tool_text,
    )
    issues = validate_source_reference("proj-alpha", ref, lambda p, a, v: artifact)
    assert any(
        i.code == ValidationIssueCode.INVALID_REFERENCE
        and "Tool specifications describe capabilities" in i.message
        for i in issues
    )


def test_controlled_language_extractor_patterns_and_issues():
    doc_text = (
        "# Security Policies\n"
        "Roles with CUSTOMER_SUPPORT must not process_refund order_refund exceeding 5000 without MANAGER approval.\n"
        "Roles with CUSTOMER_SUPPORT are forbidden from delete_customer customer_profile.\n"
        "No state change to balance may be committed by SUPPORT exceeding 10000.\n"
        "Information marked CANARY_PII must not be disclosed to public_chat.\n"
        "Roles with SUPPORT must maintain a reasonable refund limit.\n"  # Ambiguous!
        "The agent shall always act nicely.\n"  # Unsupported grammar!
    )

    create_req = ArtifactCreate(
        artifact_id="policy-02",
        artifact_kind=ArtifactKind.POLICY_DOCUMENT,
        raw_content=doc_text,
    )
    record = normalize_artifact(
        project_id="proj-alpha", create_req=create_req, next_version=1
    )

    extractor = ControlledLanguageExtractor()
    candidates = extractor.extract_from_artifact(record)

    rule_ids = {c.rule_id for c in candidates}
    assert "RULE_CUSTOMER_SUPPORT_PROCESS_REFUND_LIMIT_5000" in rule_ids
    assert "RULE_CUSTOMER_SUPPORT_FORBID_DELETE_CUSTOMER" in rule_ids
    assert "RULE_SUPPORT_EFFECT_BALANCE_LIMIT_10000" in rule_ids
    assert "RULE_CONFIDENTIALITY_CANARY_PII" in rule_ids

    # Verify refund rule properties
    refund_rule = next(c for c in candidates if "PROCESS_REFUND" in c.rule_id)
    assert refund_rule.policy_family == PolicyFamily.AUTHORIZATION
    assert refund_rule.principal_selector == "CUSTOMER_SUPPORT"
    assert refund_rule.action_selector == "process_refund"
    assert refund_rule.policy_requirement == PolicyRequirement.REQUIRE

    # Check ambiguous rule issue
    ambiguous_rule = next(
        (
            c
            for c in candidates
            if any(i.code == ValidationIssueCode.AMBIGUOUS for i in c.validation_issues)
        ),
        None,
    )
    assert ambiguous_rule is not None
    assert any("reasonable" in i.message for i in ambiguous_rule.validation_issues)

    # Check unsupported sentence issue
    unsupported_rule = next(
        (
            c
            for c in candidates
            if any(
                i.code == ValidationIssueCode.UNSUPPORTED for i in c.validation_issues
            )
        ),
        None,
    )
    assert unsupported_rule is not None


def test_structured_rule_importer_provenance_validation():
    artifact_content = (
        "Roles with AGENT must not execute_shell system_shell without ADMIN approval."
    )
    artifact = ArtifactVersionRecord(
        project_id="proj-alpha",
        artifact_id="art-doc-01",
        artifact_kind=ArtifactKind.POLICY_DOCUMENT,
        version=1,
        content_hash="h123",
        normalized_content=artifact_content,
        sections=[
            ArtifactSection(section_id="sec-1", title="S1", content=artifact_content)
        ],
        metadata={},
    )

    importer = StructuredRuleImporter()
    payload = [
        {
            "rule_id": "RULE_IMPORTED_01",
            "rule_version": 1,
            "policy_family": "AUTHORIZATION",
            "principal_selector": "AGENT",
            "action_selector": "execute_shell",
            "resource_selector": "system_shell",
            "policy_requirement": "DENY",
            "compliance_conditions": {"operator": "ALL", "conditions": []},
            "evaluation_boundary": "ATTEMPTED_ACTION",
            "severity": "CRITICAL",
            "source_references": [
                {
                    "project_id": "proj-alpha",
                    "artifact_id": "art-doc-01",
                    "artifact_version": 1,
                    "section_id": "sec-1",
                    "supporting_excerpt": artifact_content,
                }
            ],
        }
    ]

    candidates = importer.import_candidate_rules(
        project_id="proj-alpha",
        rules_payload=payload,
        artifact_resolver=lambda p, a, v: artifact,
    )

    assert len(candidates) == 1
    assert candidates[0].rule_id == "RULE_IMPORTED_01"
    assert len(candidates[0].validation_issues) == 0
