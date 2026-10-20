"""Experiment planning and split isolation service for Component 3 Phase 6.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 6 - Second domain, research validation, baselines, metrics, and final acceptance.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.components.c3_robustness_recovery.contracts.evaluation import (
    RecoveryVerdict,
)
from app.components.c3_robustness_recovery.contracts.generation import FrozenSuite
from app.components.c3_robustness_recovery.contracts.persistence import (
    compute_content_digest,
)
from app.components.c3_robustness_recovery.contracts.research import (
    BlindedReviewerItem,
    BlindedReviewerPacket,
    DatasetSplit,
    ExperimentBudgets,
    ExperimentManifest,
    IndependentReviewerLabel,
    InterReviewerAgreementResult,
    MetricScore,
    ReconciliationRecord,
    ReviewerLabelRecord,
    ReviewerProvenance,
)
from app.components.c3_robustness_recovery.runtime.evidence import MatchedPairEvidence
from app.components.c3_robustness_recovery.services.suites import freeze_suite


def build_three_way_experiment_manifest(
    experiment_id: str = "exp-c3-phase7-v2",
    target_domains: list[str] | None = None,
    case_family_ids: list[str] | None = None,
    generation_seed: int = 42,
    budgets: ExperimentBudgets | None = None,
) -> ExperimentManifest:
    """Build a deterministic, reproducible 3-way experiment manifest (40% DEV, 20% VAL, 40% TEST).

    Case-family allocation with documented rounding:
    - Sibling variants sharing the same case_family_id are strictly co-located within one split.
    - Ratio: 40% DEVELOPMENT, 20% VALIDATION, 40% HELD_OUT_TEST.
    - Rounding policy:
        For N unique sorted families:
        dev_count = max(1, int(round(N * 0.40)))
        val_count = max(1, int(round(N * 0.20)))
        test_count = N - dev_count - val_count
        If test_count <= 0 and N >= 3:
            dev_count = max(1, dev_count - 1)
            test_count = N - dev_count - val_count
    - Zero data leakage: Sets of families across partitions are mutually disjoint.
    """
    domains = target_domains or ["ecommerce", "banking"]
    families = sorted(set(case_family_ids or []))

    if not families:
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

    n = len(families)
    family_splits: dict[str, DatasetSplit] = {}

    if n == 1:
        family_splits[families[0]] = DatasetSplit.DEVELOPMENT
    elif n == 2:
        family_splits[families[0]] = DatasetSplit.DEVELOPMENT
        family_splits[families[1]] = DatasetSplit.HELD_OUT_TEST
    else:
        dev_count = max(1, round(n * 0.40))
        val_count = max(1, round(n * 0.20))
        test_count = n - dev_count - val_count

        if test_count <= 0:
            dev_count = max(1, dev_count - 1)
            test_count = n - dev_count - val_count

        for i, fam_id in enumerate(families):
            if i < dev_count:
                family_splits[fam_id] = DatasetSplit.DEVELOPMENT
            elif i < dev_count + val_count:
                family_splits[fam_id] = DatasetSplit.VALIDATION
            else:
                family_splits[fam_id] = DatasetSplit.HELD_OUT_TEST

    adapter_decls = {
        "adapter-demonstration-payment": "1.0.0",
        "adapter-banking-transfer-01": "1.0.0",
    }

    manifest = ExperimentManifest(
        experiment_id=experiment_id,
        version="2.0.0",
        title="Component 3 Three-Way Research Protocol (Phase 7)",
        description=(
            "Versioned 3-way research protocol specifying 40/20/40 family-partitioned splits "
            "(DEVELOPMENT / VALIDATION / HELD_OUT_TEST), bounded execution budgets, and independent reviewer labeling."
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
        metadata={
            "protocol_version": "2.0.0",
            "split_ratio": {
                "development": 0.40,
                "validation": 0.20,
                "held_out_test": 0.40,
            },
            "planned_cases_target": 120,
            "planned_repetitions_target": 3,
        },
    )

    verify_split_leakage(manifest)
    return manifest


def build_default_experiment_manifest(
    experiment_id: str = "exp-c3-v1",
    target_domains: list[str] | None = None,
    case_family_ids: list[str] | None = None,
    test_split_ratio: float = 0.4,
    generation_seed: int = 42,
    budgets: ExperimentBudgets | None = None,
    split_protocol: str = "TWO_WAY",
) -> ExperimentManifest:
    """Build a deterministic, reproducible experiment manifest with strict family split isolation."""
    if split_protocol == "THREE_WAY":
        return build_three_way_experiment_manifest(
            experiment_id=experiment_id,
            target_domains=target_domains,
            case_family_ids=case_family_ids,
            generation_seed=generation_seed,
            budgets=budgets,
        )

    domains = target_domains or ["ecommerce", "banking"]
    families = sorted(set(case_family_ids or []))

    family_splits: dict[str, DatasetSplit] = {}
    if not families:
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

    test_count = max(1, int(len(families) * test_split_ratio))
    for i, fam_id in enumerate(families):
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
    """Verify strictly that no case family appears in more than one dataset split partition."""
    split_sets: dict[str, set[str]] = {}
    for fam_id, split in manifest.family_splits.items():
        s_val = split.value if hasattr(split, "value") else str(split)
        split_sets.setdefault(s_val, set()).add(fam_id)

    split_names = list(split_sets.keys())
    for idx_a in range(len(split_names)):
        for idx_b in range(idx_a + 1, len(split_names)):
            sa, sb = split_names[idx_a], split_names[idx_b]
            overlap = split_sets[sa] & split_sets[sb]
            if overlap:
                raise ValueError(
                    f"Dataset leakage detected: Case families {sorted(overlap)} "
                    f"appear in both {sa} and {sb} splits."
                )


def filter_suite_for_split(
    suite: FrozenSuite,
    manifest: ExperimentManifest,
    split: DatasetSplit,
) -> FrozenSuite:
    """Filter an immutable frozen suite to cases assigned to a specific partition."""
    verify_split_leakage(manifest)

    target_splits = {split}
    if split == DatasetSplit.TRAIN_DEV:
        target_splits.add(DatasetSplit.DEVELOPMENT)
    elif split == DatasetSplit.DEVELOPMENT:
        target_splits.add(DatasetSplit.TRAIN_DEV)

    allowed_families = {
        fam_id for fam_id, s in manifest.family_splits.items() if s in target_splits
    }

    selected = [
        case for case in suite.selected_cases if case.case_family_id in allowed_families
    ]

    counters = suite.counters.model_copy()
    counters.selected_count = len(selected)

    split_suffix = split.value.lower()
    return freeze_suite(
        task_fixture_metadata=suite.task_fixture_metadata,
        adapter_manifest=suite.adapter_manifest,
        recovery_contract=suite.recovery_contract,
        policy=suite.policy,
        selected_cases=selected,
        counters=counters,
        limitations=suite.limitations,
        suite_id=f"{suite.suite_id}-split-{split_suffix}",
    )


def export_blinded_reviewer_packet(
    suite: FrozenSuite,
    evidence_records: list[MatchedPairEvidence],
    experiment_id: str,
    project_id: str,
    protocol_version: str = "2.0.0",
) -> BlindedReviewerPacket:
    """Export an anonymized reviewer packet hiding evaluator verdicts and comparison methods.

    Strict research blinding requirements:
    - Machine evaluator verdicts, rule names, and baseline tags are stripped.
    - Raw tool call sequence, pre/post states, and caller-reported outcomes are preserved.
    - Deterministic digests are verified and included for exact linkage.
    """
    items: list[BlindedReviewerItem] = []
    cases_by_id = {c.case_id: c for c in suite.selected_cases}

    for ev in evidence_records:
        case = cases_by_id.get(ev.case_id)
        digest = getattr(ev, "evidence_digest", None) or compute_content_digest(ev)

        trace_summary: list[dict[str, Any]] = []
        events = getattr(ev.fault_trial, "events", []) or []
        for evt in events:
            trace_summary.append(
                {
                    "event_id": getattr(evt, "event_id", ""),
                    "event_type": getattr(evt, "event_type", ""),
                    "tool_id": getattr(evt, "tool_id", ""),
                    "occurrence": getattr(evt, "occurrence", 0),
                    "timestamp_iso": getattr(evt, "timestamp_iso", ""),
                }
            )

        contract_version = (
            suite.recovery_contract.contract_version
            if suite.recovery_contract
            else "1.0.0"
        )
        permitted = (
            [
                o.value if hasattr(o, "value") else str(o)
                for o in suite.recovery_contract.permitted_terminal_outcomes
            ]
            if suite.recovery_contract
            else []
        )
        max_retries = (
            suite.recovery_contract.max_retries if suite.recovery_contract else None
        )

        init_fp = getattr(ev.fault_trial, "initial_state_fingerprint", "")
        final_fp = getattr(ev.fault_trial, "final_state_fingerprint", "")
        exec_status = getattr(ev.fault_trial, "execution_status", "")
        status_val = (
            exec_status.value if hasattr(exec_status, "value") else str(exec_status)
        )

        items.append(
            BlindedReviewerItem(
                pair_id=ev.pair_id,
                case_id=ev.case_id,
                project_id=project_id,
                evidence_digest=digest,
                task_id=getattr(case, "task_id", getattr(ev, "task_id", "unknown")),
                tool_id=getattr(case, "tool_id", getattr(ev, "tool_id", "unknown")),
                observed_trace_summary=trace_summary,
                caller_reported_outcome=ev.fault_trial.caller_outcome,
                initial_state_observation={"fingerprint": init_fp},
                final_state_observation={"fingerprint": final_fp},
                contract_version=contract_version,
                permitted_terminal_outcomes=permitted,
                max_retries_allowed=max_retries,
                evidence_sufficient=bool(status_val in ("COMPLETED", "FAILED")),
            )
        )

    packet_id = f"packet-{experiment_id}-{uuid4().hex[:8]}"
    return BlindedReviewerPacket(
        packet_id=packet_id,
        project_id=project_id,
        experiment_id=experiment_id,
        protocol_version=protocol_version,
        total_cases=len(items),
        created_at_utc=datetime.now(UTC).isoformat(),
        items=items,
    )


def compute_inter_reviewer_agreement(
    labels_a: list[IndependentReviewerLabel],
    labels_b: list[IndependentReviewerLabel],
    comparison_key: str = "defect_present",
) -> InterReviewerAgreementResult:
    """Compute pre-reconciliation percentage agreement and Cohen's kappa between two reviewers.

    Handles edge cases:
    - Empty or unequal label sets
    - Zero variance / single-category ratings where chance agreement Pe = 1.0 (undefined kappa)
    """
    map_a = {lbl.pair_id: lbl for lbl in labels_a}
    map_b = {lbl.pair_id: lbl for lbl in labels_b}

    common_pairs = sorted(set(map_a.keys()) & set(map_b.keys()))
    rev_a_id = labels_a[0].reviewer_id if labels_a else "UNKNOWN_A"
    rev_b_id = labels_b[0].reviewer_id if labels_b else "UNKNOWN_B"

    n = len(common_pairs)
    if n == 0:
        return InterReviewerAgreementResult(
            reviewer_a_id=rev_a_id,
            reviewer_b_id=rev_b_id,
            total_pairs_compared=0,
            concordant_pairs_count=0,
            discordant_pairs_count=0,
            percentage_agreement=MetricScore(
                value=None,
                numerator=0,
                denominator=0,
                denominator_unit="matched_reviewed_pairs",
                is_defined=False,
                undefined_reason="No common reviewed pairs between reviewers.",
            ),
            cohens_kappa=MetricScore(
                value=None,
                numerator=0,
                denominator=0,
                denominator_unit="matched_reviewed_pairs",
                is_defined=False,
                undefined_reason="No common reviewed pairs between reviewers.",
            ),
            disputed_pair_ids=[],
            reconciliation_required=False,
        )

    concordant = 0
    discordant = 0
    disputed_ids: list[str] = []

    counts_a: dict[Any, int] = {}
    counts_b: dict[Any, int] = {}

    for pid in common_pairs:
        val_a = getattr(map_a[pid], comparison_key)
        val_b = getattr(map_b[pid], comparison_key)

        counts_a[val_a] = counts_a.get(val_a, 0) + 1
        counts_b[val_b] = counts_b.get(val_b, 0) + 1

        if val_a == val_b:
            concordant += 1
        else:
            discordant += 1
            disputed_ids.append(pid)

    po = concordant / n

    # Expected agreement Pe
    all_categories = set(counts_a.keys()) | set(counts_b.keys())
    pe = sum(
        (counts_a.get(cat, 0) / n) * (counts_b.get(cat, 0) / n)
        for cat in all_categories
    )

    if pe >= 1.0 or (1.0 - pe) < 1e-9:
        # Zero variance: both raters selected the exact same single category for 100% of cases
        kappa_metric = MetricScore(
            value=1.0 if concordant == n else 0.0,
            numerator=concordant,
            denominator=n,
            denominator_unit="matched_reviewed_pairs",
            is_defined=False,
            undefined_reason="Zero variance across categories (Pe >= 1.0); Cohen's kappa is mathematically undefined.",
        )
    else:
        kappa_val = max(-1.0, min(1.0, (po - pe) / (1.0 - pe)))
        kappa_metric = MetricScore(
            value=round(kappa_val, 4),
            numerator=concordant,
            denominator=n,
            denominator_unit="matched_reviewed_pairs",
            is_defined=True,
            undefined_reason=None,
        )

    percent_metric = MetricScore(
        value=round(po, 4),
        numerator=concordant,
        denominator=n,
        denominator_unit="matched_reviewed_pairs",
        is_defined=True,
        undefined_reason=None,
    )

    return InterReviewerAgreementResult(
        reviewer_a_id=rev_a_id,
        reviewer_b_id=rev_b_id,
        total_pairs_compared=n,
        concordant_pairs_count=concordant,
        discordant_pairs_count=discordant,
        percentage_agreement=percent_metric,
        cohens_kappa=kappa_metric,
        disputed_pair_ids=disputed_ids,
        reconciliation_required=bool(discordant > 0),
    )


def reconcile_disputed_labels(
    label_a: IndependentReviewerLabel,
    label_b: IndependentReviewerLabel,
    adjudicator_id: str,
    adjudicated_verdict: RecoveryVerdict,
    adjudicated_defect_present: bool,
    adjudication_rationale: str,
) -> ReconciliationRecord:
    """Create an append-only audit record resolving reviewer discordance without mutating original labels."""
    if label_a.pair_id != label_b.pair_id:
        raise ValueError(
            f"Cannot reconcile mismatched pairs: {label_a.pair_id} vs {label_b.pair_id}"
        )

    return ReconciliationRecord(
        reconciliation_id=f"rec-{label_a.pair_id}-{uuid4().hex[:8]}",
        pair_id=label_a.pair_id,
        case_id=label_a.case_id,
        adjudicator_id=adjudicator_id,
        reviewer_a_id=label_a.reviewer_id,
        reviewer_b_id=label_b.reviewer_id,
        reviewer_a_label_id=label_a.label_id,
        reviewer_b_label_id=label_b.label_id,
        adjudicated_verdict=adjudicated_verdict,
        adjudicated_defect_present=adjudicated_defect_present,
        adjudication_rationale=adjudication_rationale,
        adjudicated_at_utc=datetime.now(UTC).isoformat(),
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
