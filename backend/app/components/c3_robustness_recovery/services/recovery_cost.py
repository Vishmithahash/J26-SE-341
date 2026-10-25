"""Recovery cost of live matched pairs (proposal RQ4, metric "Recovery cost").

Component: C3 - Robustness and Failure Recovery Testing

For each live pair the fault trial is compared with its clean control: extra wall-clock time,
extra tool calls, retries of the faulted tool, and extra LLM tokens (when NexaCart reported token
usage for both trials). Values come only from the stored evidence; a measure that is missing for
either trial is reported as None and left out of the averages, never estimated.
"""

from collections import defaultdict
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.components.c3_robustness_recovery.repositories.persistence import (
    C3PersistenceRepository,
)


def _delta(fault: float | None, clean: float | None) -> float | None:
    if fault is None or clean is None:
        return None
    return fault - clean


def _tokens(trial: dict[str, Any]) -> int | None:
    usage = trial.get("llm_usage") or {}
    total = usage.get("total")
    return int(total) if isinstance(total, int | float) else None


def pair_recovery_cost(
    evidence: dict[str, Any], verdict: str | None
) -> dict[str, Any] | None:
    """Cost record for one stored live pair, or None when the pair is not a live pair."""
    config = evidence.get("configuration_snapshot") or {}
    trials = config.get("aut_trials")
    if not trials:
        return None
    clean, fault = trials.get("clean") or {}, trials.get("fault") or {}
    planned = config.get("planned_fault") or {}
    clean_ms, fault_ms = clean.get("duration_ms"), fault.get("duration_ms")
    clean_calls = len(clean.get("tool_calls") or [])
    fault_calls = len(fault.get("tool_calls") or [])
    clean_tokens, fault_tokens = _tokens(clean), _tokens(fault)
    return {
        "pair_id": evidence.get("pair_id"),
        "case_id": evidence.get("case_id"),
        "execution_id": evidence.get("run_id"),
        "fault_family": planned.get("fault_family"),
        "effect_phase": planned.get("effect_phase"),
        "exposure_status": evidence.get("exposure_status"),
        "recovery_verdict": verdict,
        "clean_duration_ms": clean_ms,
        "fault_duration_ms": fault_ms,
        "extra_duration_ms": _delta(fault_ms, clean_ms),
        "clean_tool_calls": clean_calls,
        "fault_tool_calls": fault_calls,
        "extra_tool_calls": fault_calls - clean_calls,
        "retries": (evidence.get("fault_trial") or {}).get("subsequent_calls_count", 0),
        "clean_tokens": clean_tokens,
        "fault_tokens": fault_tokens,
        "extra_tokens": _delta(fault_tokens, clean_tokens),
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def avg(key: str) -> float | None:
        values = [r[key] for r in rows if r[key] is not None]
        return round(mean(values), 1) if values else None

    def count(key: str) -> int:
        return sum(1 for r in rows if r[key] is not None)

    return {
        "pairs": len(rows),
        "avg_extra_duration_ms": avg("extra_duration_ms"),
        "avg_extra_tool_calls": avg("extra_tool_calls"),
        "avg_retries": avg("retries"),
        "avg_extra_tokens": avg("extra_tokens"),
        "pairs_with_duration": count("extra_duration_ms"),
        "pairs_with_tokens": count("extra_tokens"),
    }


def project_recovery_cost(
    db: Session, project_id: str, execution_id: str | None = None
) -> dict[str, Any]:
    """Per-pair costs plus averages per (fault family, effect phase) and overall."""
    repo = C3PersistenceRepository(db)
    pairs, _ = repo.list_matched_pairs(
        project_id=project_id, execution_id=execution_id, limit=200
    )
    evaluations, _ = repo.list_evaluations(project_id=project_id, limit=200)
    verdicts: dict[str, str | None] = {}
    for e in evaluations:  # newest first: keep the latest verdict per pair
        verdicts.setdefault(e.pair_id, e.recovery_verdict)

    rows = [
        row
        for row in (
            pair_recovery_cost(p.evidence_snapshot or {}, verdicts.get(p.pair_id))
            for p in pairs
        )
        if row is not None
    ]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[
            (row["fault_family"] or "UNKNOWN", row["effect_phase"] or "UNKNOWN")
        ].append(row)
    return {
        "project_id": project_id,
        "execution_id": execution_id,
        "overall": _summary(rows),
        "groups": [
            {"fault_family": family, "effect_phase": phase, **_summary(items)}
            for (family, phase), items in sorted(groups.items())
        ],
        "pairs": rows,
        "notes": [
            "Extra cost = fault trial minus its clean control, from stored evidence only.",
            (
                "Tokens are shown only where NexaCart reported usage for both trials "
                "(pairs recorded before token capture have none)."
            ),
        ],
    }
