import hashlib
import json
from collections import defaultdict

from app.components.c1_tool_call_correctness.contracts.generation import (
    AgentFacingTask,
    GeneratedCandidateCase,
    GenerationSummary,
)


def extract_agent_facing_task(candidate: GeneratedCandidateCase) -> AgentFacingTask:
    """Extracts an isolated agent-facing task view.
    Strictly excludes QA expectations, oracle values, and validation findings.
    """
    permitted = [
        call.tool_name
        for call in candidate.expected_tool_calls
        if not call.is_forbidden
    ]
    return AgentFacingTask(
        case_id=candidate.case_id,
        task_prompt=candidate.agent_task_prompt,
        context_inputs=candidate.task_context_inputs,
        permitted_tools=permitted,
    )


def compute_suite_content_hash(cases: list[GeneratedCandidateCase]) -> str:
    """Computes a SHA-256 fingerprint over the accepted case expectations in canonical order."""
    case_fingerprints = [
        c.canonical_hash for c in sorted(cases, key=lambda x: x.case_id)
    ]
    raw = json.dumps(case_fingerprints, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SuiteSelector:
    """Performs semantic deduplication, validation filtering, and balanced bounded suite selection."""

    def __init__(self, max_accepted_cases: int = 10):
        self.max_accepted_cases = max_accepted_cases

    def process_and_select(
        self, candidates: list[GeneratedCandidateCase]
    ) -> tuple[
        list[GeneratedCandidateCase],
        list[GeneratedCandidateCase],
        GenerationSummary,
        str,
    ]:
        """Processes candidate cases:
        1. Identifies and removes semantic duplicates based on canonical hash.
        2. Filters out invalid candidates.
        3. Applies balanced round-robin category coverage up to max_accepted_cases.
        4. Calculates suite content hash and summary metrics.

        Returns:
            selected_cases: list of accepted cases for the suite.
            processed_candidates: full list of all candidates with status and rejection reasons.
            summary: GenerationSummary with counts.
            content_hash: SHA-256 content hash of the accepted suite.
        """
        seen_hashes: set[str] = set()
        deduped_valid_by_category: dict[str, list[GeneratedCandidateCase]] = (
            defaultdict(list)
        )

        duplicates_count = 0
        valid_count = 0
        invalid_count = 0
        category_counts: dict[str, int] = defaultdict(int)

        processed_all: list[GeneratedCandidateCase] = []

        for candidate in candidates:
            category_counts[candidate.category.value] += 1

            # 1. Semantic Deduplication check
            if candidate.canonical_hash in seen_hashes:
                duplicates_count += 1
                candidate.rejection_reason = (
                    "Semantic duplicate of another candidate in this generation run."
                )
                processed_all.append(candidate)
                continue

            seen_hashes.add(candidate.canonical_hash)

            # 2. Validation check
            if not candidate.is_valid:
                invalid_count += 1
                if not candidate.rejection_reason:
                    first_err = (
                        candidate.validation_issues[0].message
                        if candidate.validation_issues
                        else "Validation failure"
                    )
                    candidate.rejection_reason = (
                        f"Candidate validation failed: {first_err}"
                    )
                processed_all.append(candidate)
                continue

            valid_count += 1
            deduped_valid_by_category[candidate.category.value].append(candidate)
            processed_all.append(candidate)

        # 3. Deterministic balanced selection across categories
        selected_cases: list[GeneratedCandidateCase] = []
        categories = sorted(deduped_valid_by_category.keys())

        # Round-robin selection across available categories
        while len(selected_cases) < self.max_accepted_cases and any(
            deduped_valid_by_category.values()
        ):
            for cat in categories:
                if len(selected_cases) >= self.max_accepted_cases:
                    break
                if deduped_valid_by_category[cat]:
                    # Deterministic pick: sort by canonical_hash
                    deduped_valid_by_category[cat].sort(key=lambda c: c.canonical_hash)
                    chosen = deduped_valid_by_category[cat].pop(0)
                    selected_cases.append(chosen)

        # Mark unselected valid candidates
        selected_ids = {c.case_id for c in selected_cases}
        for cand in processed_all:
            if (
                cand.is_valid
                and cand.case_id not in selected_ids
                and not cand.rejection_reason
            ):
                cand.rejection_reason = (
                    "Exceeded max_accepted_cases quota for this generation run."
                )

        content_hash = compute_suite_content_hash(selected_cases)

        summary = GenerationSummary(
            total_generated=len(candidates),
            valid_candidates=valid_count,
            invalid_candidates=invalid_count,
            duplicates_removed=duplicates_count,
            selected_count=len(selected_cases),
            category_counts=dict(category_counts),
        )

        return selected_cases, processed_all, summary, content_hash
