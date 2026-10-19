import hashlib
import json
import re
from collections.abc import Callable

from app.components.c4_policy_aware_safety.contracts.artifacts import (
    ArtifactCreate,
    ArtifactSection,
    ArtifactVersionRecord,
    SourceReference,
)
from app.components.c4_policy_aware_safety.contracts.enums import (
    ArtifactKind,
    Severity,
    ValidationIssueCode,
)
from app.components.c4_policy_aware_safety.contracts.rules import ValidationIssue


def compute_content_hash(content: str) -> str:
    """Compute deterministic SHA-256 hash of normalized text."""
    normalized = content.strip().replace("\r\n", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def auto_detect_sections(text: str) -> list[ArtifactSection]:
    """Parse text into sections using markdown headings or numbered sections."""
    sections: list[ArtifactSection] = []
    lines = text.split("\n")

    current_section_id = "sec-preamble"
    current_title = "Preamble"
    current_lines: list[str] = []
    current_start = 0
    current_offset = 0

    heading_pattern = re.compile(r"^(#{1,6}\s+(.+)|([0-9]+\.[0-9]*\s+(.+)))$")

    for line in lines:
        match = heading_pattern.match(line.strip())
        if match:
            # Save preceding section if it had content
            if current_lines:
                sec_text = "\n".join(current_lines).strip()
                if sec_text:
                    sections.append(
                        ArtifactSection(
                            section_id=current_section_id,
                            title=current_title,
                            content=sec_text,
                            start_char=current_start,
                            end_char=current_offset,
                        )
                    )
            current_start = current_offset
            title = match.group(2) or match.group(4) or line.strip()
            slug = re.sub(r"[^a-zA-Z0-9_-]", "-", title.lower()).strip("-")
            current_section_id = f"sec-{slug}" if slug else f"sec-{len(sections) + 1}"
            current_title = title
            current_lines = [line]
        else:
            current_lines.append(line)
        current_offset += len(line) + 1  # newline

    if current_lines:
        sec_text = "\n".join(current_lines).strip()
        if sec_text:
            sections.append(
                ArtifactSection(
                    section_id=current_section_id,
                    title=current_title,
                    content=sec_text,
                    start_char=current_start,
                    end_char=current_offset,
                )
            )

    if not sections:
        sections.append(
            ArtifactSection(
                section_id="sec-root",
                title="Root Document",
                content=text.strip(),
                start_char=0,
                end_char=len(text),
            )
        )

    return sections


def normalize_artifact(
    project_id: str,
    create_req: ArtifactCreate,
    next_version: int,
) -> ArtifactVersionRecord:
    """Normalize and structure an incoming artifact payload into a versioned record."""
    raw = create_req.raw_content.strip().replace("\r\n", "\n")

    # Format normalization
    sections: list[ArtifactSection]
    if create_req.sections:
        sections = create_req.sections
    elif (
        create_req.artifact_kind == ArtifactKind.POLICY_DOCUMENT
        or create_req.artifact_kind == ArtifactKind.REQUIREMENTS
    ):
        sections = auto_detect_sections(raw)
    else:
        # Check if valid JSON
        try:
            parsed = json.loads(raw)
            normalized_json = json.dumps(parsed, sort_keys=True, indent=2)
            raw = normalized_json
        except (json.JSONDecodeError, ValueError):
            pass
        sections = [
            ArtifactSection(
                section_id="sec-default",
                title=f"{create_req.artifact_kind.value} Content",
                content=raw,
                start_char=0,
                end_char=len(raw),
            )
        ]

    content_hash = compute_content_hash(raw)

    return ArtifactVersionRecord(
        project_id=project_id,
        artifact_id=create_req.artifact_id,
        artifact_kind=create_req.artifact_kind,
        version=next_version,
        content_hash=content_hash,
        normalized_content=raw,
        sections=sections,
        metadata=create_req.metadata,
    )


def validate_source_reference(
    current_project_id: str,
    source_ref: SourceReference,
    artifact_resolver: Callable[[str, str, int], ArtifactVersionRecord | None],
) -> list[ValidationIssue]:
    """Validate that a source reference exists within the same project, exact version, and excerpt agrees."""
    issues: list[ValidationIssue] = []

    # 1. Reject cross-project references
    if source_ref.project_id != current_project_id:
        issues.append(
            ValidationIssue(
                code=ValidationIssueCode.CROSS_PROJECT_REFERENCE,
                message=f"Source reference project '{source_ref.project_id}' does not match current project '{current_project_id}'.",
                field="source_references.project_id",
                severity=Severity.CRITICAL,
                blocking=True,
            )
        )
        return issues

    # 2. Check artifact and version existence
    artifact = artifact_resolver(
        source_ref.project_id, source_ref.artifact_id, source_ref.artifact_version
    )
    if not artifact:
        issues.append(
            ValidationIssue(
                code=ValidationIssueCode.INVALID_REFERENCE,
                message=f"Artifact '{source_ref.artifact_id}' version {source_ref.artifact_version} not found in project '{current_project_id}'.",
                field="source_references.artifact_id",
                severity=Severity.CRITICAL,
                blocking=True,
            )
        )
        return issues

    # 3. Check section existence if specified
    target_content = artifact.normalized_content
    if source_ref.section_id:
        sec = next(
            (s for s in artifact.sections if s.section_id == source_ref.section_id),
            None,
        )
        if not sec:
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.INVALID_REFERENCE,
                    message=f"Section '{source_ref.section_id}' not found in artifact '{source_ref.artifact_id}' v{source_ref.artifact_version}.",
                    field="source_references.section_id",
                    severity=Severity.HIGH,
                    blocking=True,
                )
            )
        else:
            target_content = sec.content

    # 4. Check character span bounds and excerpt match at span if provided
    start_char = source_ref.start_char
    end_char = source_ref.end_char
    if start_char is not None or end_char is not None:
        if (
            start_char is None
            or end_char is None
            or start_char < 0
            or end_char > len(artifact.normalized_content)
            or start_char >= end_char
        ):
            issues.append(
                ValidationIssue(
                    code=ValidationIssueCode.INVALID_REFERENCE,
                    message=(
                        f"Character span [{start_char}:{end_char}] is invalid or out of bounds for "
                        f"artifact '{source_ref.artifact_id}' v{source_ref.artifact_version} (length {len(artifact.normalized_content)})."
                    ),
                    field="source_references.spans",
                    severity=Severity.CRITICAL,
                    blocking=True,
                )
            )
        else:
            span_text = artifact.normalized_content[start_char:end_char].strip()
            if span_text != source_ref.supporting_excerpt.strip():
                issues.append(
                    ValidationIssue(
                        code=ValidationIssueCode.EXCERPT_MISMATCH,
                        message=f"Supporting excerpt does not match content at character span [{start_char}:{end_char}].",
                        field="source_references.supporting_excerpt",
                        severity=Severity.CRITICAL,
                        blocking=True,
                    )
                )

    # 5. Check excerpt agreement
    excerpt = source_ref.supporting_excerpt.strip()
    if excerpt not in target_content and excerpt not in artifact.normalized_content:
        issues.append(
            ValidationIssue(
                code=ValidationIssueCode.EXCERPT_MISMATCH,
                message=f"Supporting excerpt does not match content in artifact '{source_ref.artifact_id}' v{source_ref.artifact_version}.",
                field="source_references.supporting_excerpt",
                severity=Severity.CRITICAL,
                blocking=True,
            )
        )

    # 5. Check tool specification capability disclaimer
    if artifact.artifact_kind == ArtifactKind.TOOL_SPECIFICATION:
        issues.append(
            ValidationIssue(
                code=ValidationIssueCode.INVALID_REFERENCE,
                message="Tool specifications describe capabilities and cannot serve as sole authorization policy sources.",
                field="source_references.artifact_kind",
                severity=Severity.HIGH,
                blocking=True,
            )
        )

    return issues
