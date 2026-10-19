"""Experiment planning and split isolation service for Component 3 Phase 6.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 6 - Second domain, research validation, baselines, metrics, and final acceptance.
"""

from datetime import UTC, datetime

from app.components.c3_robustness_recovery.contracts.generation import FrozenSuite
from app.components.c3_robustness_recovery.contracts.persistence import (
    compute_content_digest,
)
from app.components.c3_robustness_recovery.contracts.research import (
    DatasetSplit,
    ExperimentBudgets,
    ExperimentManifest,
    ReviewerLabelRecord,
    ReviewerProvenance,
)
from app.components.c3_robustness_recovery.runtime.evidence import MatchedPairEvidence
from app.components.c3_robustness_recovery.services.suites import freeze_suite


def build_default_experiment_manifest(
    experiment_id: str = "exp-c3-v1",
    target_domains: list[str] | None = None,
    case_family_ids: list[str] | None = None,
    test_split_ratio: float = 0.4,
    generation_seed: int = 42,
    budgets: ExperimentBudgets | None = None,
) -> ExperimentManifest:
    """Build a deterministic, reproducible experiment manifest with strict family split isolation.

    Ensures that sibling variants belonging to the same case_family_id are NEVER
    split across TRAIN_DEV and HELD_OUT_TEST partitions.
    """
    domains = target_domains or ["ecommerce", "banking"]
    families = sorted(set(case_family_ids or []))

    family_splits: dict[str, DatasetSplit] = {}
    if not families:
        # Default representative families if none supplied
        families = [
            "fam-c3-payment_gateway-timeout_",
            "fam-c3-payment_gateway-transien",
            "fam-c3-payment_gateway-rate_lim",
            "fam-c3-payment_gateway-tool_una",
            "fam-c3-payment_gateway-malforme",
            "fam-c3-wire_transfer-timeout_",
            "fam-c3-wire_transfer-transien",
            "fam-c3-wire_transfer-rate_lim",
            "fam-c3-wire_transfer-tool_una",
            "fam-c3-wire_transfer-malforme",
        ]

    # Deterministic partition based on sorted index
    test_count = max(1, int(len(families) * test_split_ratio))
    for i, fam_id in enumerate(families):
        # Place latter portion in HELD_OUT_TEST
        if i >= len(families) - test_count:
            family_splits[fam_id] = DatasetSplit.HELD_OUT_TEST
        else:
            family_splits[fam_id] = DatasetSplit.TRAIN_DEV

    adapter_decls = {
        "adapter-demonstration-payment": "1.0.0",
        "adapter-banking-transfer-01": "1.0.0",
    }

    manifest = ExperimentManifest(
        experiment_id=experiment_id,
        version="1.0.0",
        title="Component 3 Robustness and Failure Recovery Research Protocol",
        description=(
            "Versioned research protocol specifying family-partitioned splits, "
            "adapter versions, execution budgets, and independent label requirements."
        ),
        target_domains=domains,
        adapter_declarations=adapter_decls,
        family_splits=family_splits,
        generation_seed=generation_seed,
        selection_seed=generation_seed,
        repetition_seeds=[generation_seed, generation_seed + 1, generation_seed + 2],
        repetitions_per_case=3,
        budgets=budgets or ExperimentBudgets(),
        evaluator_version="1.2.0",
        rule_set_version="1.2.0",
        created_at_utc=datetime.now(UTC).isoformat(),
    )

    verify_split_leakage(manifest)
    return manifest


def verify_split_leakage(manifest: ExperimentManifest) -> None:
    """Verify strictly that no case family appears in both TRAIN_DEV and HELD_OUT_TEST."""
    dev_families = {
        fam_id
        for fam_id, split in manifest.family_splits.items()
        if split == DatasetSplit.TRAIN_DEV
    }
    test_families = {
        fam_id
        for fam_id, split in manifest.family_splits.items()
        if split == DatasetSplit.HELD_OUT_TEST
    }

    intersection = dev_families & test_families
    if intersection:
        raise ValueError(
            f"Dataset leakage detected: Case families {sorted(intersection)} "
            f"appear in both TRAIN_DEV and HELD_OUT_TEST splits."
        )


def filter_suite_for_split(
    suite: FrozenSuite,
    manifest: ExperimentManifest,
    split: DatasetSplit,
) -> FrozenSuite:
    """Filter an immutable frozen suite to cases assigned to a specific partition."""
    verify_split_leakage(manifest)

    allowed_families = {
        fam_id for fam_id, s in manifest.family_splits.items() if s == split
    }

    selected = [
        case for case in suite.selected_cases if case.case_family_id in allowed_families
    ]

    counters = suite.counters.model_copy()
    counters.selected_count = len(selected)

    return freeze_suite(
        task_fixture_metadata=suite.task_fixture_metadata,
        adapter_manifest=suite.adapter_manifest,
        recovery_contract=suite.recovery_contract,
        policy=suite.policy,
        selected_cases=selected,
        counters=counters,
    )


def validate_reviewer_label(
    label: ReviewerLabelRecord,
    evidence: MatchedPairEvidence,
) -> tuple[bool, str | None]:
    """Validate that an independent reviewer label matches the evidence scope and digest."""
    if label.pair_id != evidence.pair_id:
        return (
            False,
            f"Label pair_id '{label.pair_id}' does not match evidence pair_id '{evidence.pair_id}'.",
        )
    if label.case_id != evidence.case_id:
        return (
            False,
            f"Label case_id '{label.case_id}' does not match evidence case_id '{evidence.case_id}'.",
        )
    if label.project_id != evidence.project_id:
        return (
            False,
            f"Label project_id '{label.project_id}' does not match evidence project_id '{evidence.project_id}'.",
        )
    actual_digest = getattr(
        evidence, "evidence_digest", None
    ) or compute_content_digest(evidence)
    if (
        label.evidence_digest
        and actual_digest
        and label.evidence_digest != actual_digest
    ):
        return (
            False,
            (
                f"Label evidence_digest '{label.evidence_digest}' does not match "
                f"actual evidence digest '{actual_digest}'."
            ),
        )
    return True, None


def check_research_accuracy_acceptance(
    labels: list[ReviewerLabelRecord],
) -> tuple[bool, list[str]]:
    """Determine whether independent reviewed research labels satisfy acceptance prerequisites.

    Developer-authored test assertions and synthetic fixture labels do NOT count as
    independently reviewed research ground truth.
    """
    missing: list[str] = []
    if not labels:
        missing.append(
            "No independent reference labels provided for evaluation trials. "
            "Research-accuracy acceptance is BLOCKED."
        )
        return False, missing

    independent_labels = [
        lbl
        for lbl in labels
        if lbl.reviewer_provenance
        in (ReviewerProvenance.INDEPENDENT_EXPERT, ReviewerProvenance.EXTERNAL_AUDITOR)
    ]

    if not independent_labels:
        missing.append(
            "Provided labels are synthetic unit fixtures (SYNTHETIC_FIXTURE_LABEL); "
            "no independently reviewed ground-truth labels exist. "
            "Live research-accuracy acceptance remains BLOCKED."
        )
        return False, missing

    return True, []
