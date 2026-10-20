import abc
import difflib
import hashlib
import os
import re
import uuid
from pathlib import Path

from app.components.c1_tool_call_correctness.contracts.configuration import (
    ToolDefinition,
)
from app.components.c1_tool_call_correctness.contracts.correction import CandidatePatch
from app.components.c1_tool_call_correctness.contracts.diagnosis import (
    CandidateCodeLocation,
    CaseDiagnosisRecord,
    CauseCategory,
)

MAX_PATCH_SIZE_BYTES = 50 * 1024  # 50 KB max patch size

# Patterns of files that a patch is STRICTLY FORBIDDEN from modifying
FORBIDDEN_FILE_PATTERNS = [
    r"\.env",
    r"credentials",
    r"secret",
    r"token",
    r"key",
    r"^tests?/",
    r"test_.*\.py$",
    r"evaluator.*\.py$",
    r"alembic/",
    r"requirements\.txt$",
    r"\.git/",
]


class PatchValidationError(Exception):
    """Raised when a candidate patch fails validation or violates security scope."""


def validate_patch_content(
    diff_content: str,
    allowed_paths: list[str] | None = None,
) -> tuple[bool, str | None, list[str], int, int]:
    """Validates unified diff format, safety, bounds, and permitted file boundaries.
    Returns: (is_valid, error_message, modified_files, additions_count, deletions_count).
    """
    if not diff_content or not diff_content.strip():
        return False, "Patch content is empty.", [], 0, 0

    encoded = diff_content.encode("utf-8")
    if len(encoded) > MAX_PATCH_SIZE_BYTES:
        return (
            False,
            f"Patch size ({len(encoded)} bytes) exceeds maximum limit of {MAX_PATCH_SIZE_BYTES} bytes.",
            [],
            0,
            0,
        )

    modified_files: set[str] = set()
    additions = 0
    deletions = 0

    lines = diff_content.splitlines()
    for line in lines:
        if line.startswith(("--- a/", "+++ b/")):
            raw_path = line[6:].strip()
            # Clean and normalize path
            cleaned = os.path.normpath(raw_path).replace("\\", "/")

            # Path traversal check
            if ".." in cleaned or cleaned.startswith(("/", "\\")):
                return (
                    False,
                    f"Path traversal detected in patch header: {raw_path}",
                    [],
                    0,
                    0,
                )

            # Forbidden file check (tests, configs, evaluators, secrets)
            for pattern in FORBIDDEN_FILE_PATTERNS:
                if re.search(pattern, cleaned, re.IGNORECASE):
                    return (
                        False,
                        f"Patch touches forbidden or security-sensitive file: {cleaned}",
                        [],
                        0,
                        0,
                    )

            # Permitted paths check if specified
            if allowed_paths is not None:
                norm_allowed = [
                    os.path.normpath(p).replace("\\", "/") for p in allowed_paths
                ]
                if cleaned not in norm_allowed and not any(
                    cleaned.startswith(f"{a}/") for a in norm_allowed
                ):
                    return (
                        False,
                        f"File '{cleaned}' in patch is outside permitted scope: {allowed_paths}",
                        [],
                        0,
                        0,
                    )

            modified_files.add(cleaned)

        elif line.startswith("+") and not line.startswith("+++"):
            additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1

    if not modified_files:
        return (
            False,
            "Invalid unified diff: No target files identified in patch headers.",
            [],
            0,
            0,
        )

    return True, None, sorted(modified_files), additions, deletions


class PatchGenerationProvider(abc.ABC):
    """Abstract interface for candidate patch generation providers."""

    @abc.abstractmethod
    def generate_candidate_patch(
        self,
        diagnosis: CaseDiagnosisRecord,
        candidate_location: CandidateCodeLocation,
        source_root_path: Path,
        tool_definition: ToolDefinition | None = None,
    ) -> CandidatePatch | None:
        """Generate a single candidate patch for an identified code defect."""


class DeterministicPatchGenerator(PatchGenerationProvider):
    """Deterministic patch generator for supported argument mapping defects.
    Inspects AST discrepancies and synthesizes a safe unified diff aligning the function signature.
    """

    def generate_candidate_patch(
        self,
        diagnosis: CaseDiagnosisRecord,
        candidate_location: CandidateCodeLocation,
        source_root_path: Path,
        tool_definition: ToolDefinition | None = None,
    ) -> CandidatePatch | None:
        if diagnosis.cause_category != CauseCategory.SUPPORTED_APPLICATION_CODE_DEFECT:
            return None

        target_file = (source_root_path / candidate_location.file_path).resolve()
        if not target_file.is_file():
            return None

        try:
            original_text = target_file.read_text(encoding="utf-8")
        except OSError:
            return None

        orig_lines = original_text.splitlines(keepends=True)
        fn_name = candidate_location.function_name
        start_idx = candidate_location.line_start - 1  # 0-indexed line start

        # Check if tool_definition has parameter schema properties
        if not tool_definition:
            return None

        schema_props = list(tool_definition.parameters_schema.properties.keys())
        if not schema_props:
            return None

        # Look for def fn_name(...) line around start_idx
        def_line_idx: int | None = None
        for i in range(max(0, start_idx - 2), min(len(orig_lines), start_idx + 3)):
            if f"def {fn_name}(" in orig_lines[i]:
                def_line_idx = i
                break

        if def_line_idx is None:
            return None

        original_def_line = orig_lines[def_line_idx]

        # Extract parameters inside parentheses
        match = re.search(rf"def\s+{re.escape(fn_name)}\s*\((.*?)\)", original_def_line)
        if not match:
            return None

        current_params_str = match.group(1)
        current_param_tokens = [
            p.strip() for p in current_params_str.split(",") if p.strip()
        ]

        # Find schema properties not present in current function parameters
        missing_params = [
            sp
            for sp in schema_props
            if not any(p.split(":")[0].strip() == sp for p in current_param_tokens)
        ]
        if not missing_params:
            return None

        # Synthesize patched function signature incorporating the missing expected parameter(s)
        new_params = list(current_param_tokens)
        for mp in missing_params:
            # Add parameter before any default values or keyword-only args
            new_params.append(f"{mp}: Any = None")

        new_params_str = ", ".join(new_params)
        patched_def_line = (
            original_def_line[: match.start(1)]
            + new_params_str
            + original_def_line[match.end(1) :]
        )

        # Build modified lines
        modified_lines = list(orig_lines)
        modified_lines[def_line_idx] = patched_def_line

        # Ensure Any is imported if not present
        if (
            "from typing import Any" not in original_text
            and "import typing" not in original_text
        ):
            modified_lines.insert(0, "from typing import Any\n")

        # Generate unified diff
        rel_path = candidate_location.file_path.replace("\\", "/")
        diff_iter = difflib.unified_diff(
            orig_lines,
            modified_lines,
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
        )
        diff_content = "".join(diff_iter)

        is_valid, _err, modified_files, adds, dels = validate_patch_content(
            diff_content
        )
        if not is_valid:
            return None

        patch_hash = hashlib.sha256(diff_content.encode("utf-8")).hexdigest()
        patch_id = f"patch_{uuid.uuid4().hex[:12]}"

        return CandidatePatch(
            patch_id=patch_id,
            diff_content=diff_content,
            patch_hash=patch_hash,
            modified_files=modified_files,
            additions_count=adds,
            deletions_count=dels,
            rationale=(
                f"Aligned function '{fn_name}' signature to accept missing parameter(s) "
                f"{missing_params} declared in tool schema."
            ),
        )


class CorrectionEngine:
    """Manages patch generation, format validation, and scope verification.
    Guarantees:
    - At most one candidate patch generated per attempt.
    - Scope bounded strictly to permitted files.
    - No modifications to tests, benchmarks, or verification harnesses.
    """

    def __init__(self, provider: PatchGenerationProvider | None = None):
        self.provider = provider or DeterministicPatchGenerator()

    def generate_patch(
        self,
        diagnosis: CaseDiagnosisRecord,
        source_root_path: Path,
        tool_definitions: dict[str, ToolDefinition],
        allowed_paths: list[str] | None = None,
        patch_override: str | None = None,
    ) -> tuple[CandidatePatch | None, str | None]:
        """Generate or import and validate a single candidate patch."""
        # Case A: Externally supplied / imported patch
        if patch_override:
            is_valid, err, files, adds, dels = validate_patch_content(
                diff_content=patch_override,
                allowed_paths=allowed_paths,
            )
            if not is_valid:
                return None, f"Imported patch validation failed: {err}"

            patch_hash = hashlib.sha256(patch_override.encode("utf-8")).hexdigest()
            imported_patch = CandidatePatch(
                patch_id=f"patch_imported_{uuid.uuid4().hex[:8]}",
                diff_content=patch_override,
                patch_hash=patch_hash,
                modified_files=files,
                additions_count=adds,
                deletions_count=dels,
                rationale="Imported developer patch.",
            )
            return imported_patch, None

        # Case B: Generated patch via provider
        if not diagnosis.candidate_code_locations:
            return (
                None,
                "No candidate code locations available in diagnosis for patch generation.",
            )

        # Take the top-ranked candidate code location (rank 1)
        top_candidate = min(
            diagnosis.candidate_code_locations, key=lambda c: c.ranking_score
        )

        # Check allowed_paths boundary
        if allowed_paths is not None:
            norm_allowed = [
                os.path.normpath(p).replace("\\", "/") for p in allowed_paths
            ]
            norm_cand = os.path.normpath(top_candidate.file_path).replace("\\", "/")
            if norm_cand not in norm_allowed and not any(
                norm_cand.startswith(f"{a}/") for a in norm_allowed
            ):
                return (
                    None,
                    f"Candidate file '{top_candidate.file_path}' is outside permitted change scope.",
                )

        # Find matching tool definition
        target_tool: ToolDefinition | None = None
        for tdef in tool_definitions.values():
            if (
                tdef.code_mapping
                and tdef.code_mapping.function_name == top_candidate.function_name
            ):
                target_tool = tdef
                break

        patch = self.provider.generate_candidate_patch(
            diagnosis=diagnosis,
            candidate_location=top_candidate,
            source_root_path=source_root_path,
            tool_definition=target_tool,
        )

        if not patch:
            return (
                None,
                "Patch generator provider could not synthesize a valid candidate patch.",
            )

        # Final safety validation of generated patch
        is_valid, err, files, adds, dels = validate_patch_content(
            diff_content=patch.diff_content,
            allowed_paths=allowed_paths,
        )
        if not is_valid:
            return None, f"Synthesized patch failed safety validation: {err}"

        return patch, None
