"""Deterministic classification of a live agent's terminal outcome for recovery evaluation.

Component: C3 - Robustness and Failure Recovery Testing

A live agent run that ends with status COMPLETED only means the agent loop finished. Whether the
agent claimed that the task was done or stopped and told the user is read from its final answer
with fixed, task-specific patterns frozen with the task. Answers that match neither, or both, are
reported as ``OUTCOME_UNCLASSIFIED`` (the evaluator then returns INCONCLUSIVE); nothing is guessed
and no LLM judge is used.
"""

import re
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:  # the shared integration package imports this module via the executor
    from app.shared.integration.adapters import ExecutionTrace

OUTCOME_SUCCESS = "SUCCESS"
OUTCOME_GRACEFUL_STOP = "GRACEFUL_ABORT_USER_NOTIFIED"
OUTCOME_UNCLASSIFIED = "OUTCOME_UNCLASSIFIED"
OUTCOME_EXECUTION_ERROR = "EXECUTION_ERROR"

# Agent error codes caused by the test environment (model provider unreachable), not by the
# application's recovery behaviour. Trials ending this way are execution errors.
INFRASTRUCTURE_ERROR_MARKERS = ("LLM_PROVIDER", "LLM_NOT_CONFIGURED", "HARNESS")


class TerminalOutcomeRules(BaseModel):
    """Frozen regular expressions (case-insensitive) that classify a final answer."""

    model_config = ConfigDict(extra="forbid")

    rules_version: str = Field(default="1.0.0", min_length=1, max_length=32)
    completion_claim_patterns: list[str] = Field(min_length=1)
    negated_completion_patterns: list[str] = Field(default_factory=list)
    stop_notice_patterns: list[str] = Field(default_factory=list)


class TerminalOutcomeClassification(BaseModel):
    """Classified outcome plus the evidence that produced it."""

    model_config = ConfigDict(extra="forbid")

    outcome: str
    reason: str
    rules_version: str
    agent_status: str | None = None
    matched_completion: list[str] = Field(default_factory=list)
    matched_negation: list[str] = Field(default_factory=list)
    matched_stop_notice: list[str] = Field(default_factory=list)


def _matches(patterns: list[str], text: str) -> list[str]:
    return [p for p in patterns if re.search(p, text, flags=re.IGNORECASE)]


def classify_terminal_outcome(
    agent_status: str | None,
    agent_error_code: str | None,
    final_answer: str | None,
    rules: TerminalOutcomeRules | None,
) -> TerminalOutcomeClassification:
    """Classify a live agent run into a C3 terminal outcome string.

    Without frozen rules a completed run is ``OUTCOME_UNCLASSIFIED``: completion is never inferred
    from the run status alone.
    """
    if rules is None:
        rules = TerminalOutcomeRules(
            rules_version="none", completion_claim_patterns=[r"(?!)"]
        )
        if agent_status == "COMPLETED":
            return TerminalOutcomeClassification(
                outcome=OUTCOME_UNCLASSIFIED,
                reason="No frozen outcome rules are registered for this task.",
                rules_version=rules.rules_version,
                agent_status=agent_status,
            )
    if agent_status != "COMPLETED":
        code = agent_error_code or agent_status or "UNKNOWN"
        if any(marker in code.upper() for marker in INFRASTRUCTURE_ERROR_MARKERS):
            return TerminalOutcomeClassification(
                outcome=OUTCOME_EXECUTION_ERROR,
                reason=f"Agent run ended with infrastructure error '{code}'.",
                rules_version=rules.rules_version,
                agent_status=agent_status,
            )
        # The application's own failure (agent deadline, step budget, unhandled error):
        # an ordinary incomplete outcome, never a graceful stop.
        return TerminalOutcomeClassification(
            outcome=code,
            reason=f"Agent run did not complete (status '{agent_status}', error '{code}').",
            rules_version=rules.rules_version,
            agent_status=agent_status,
        )

    text = (final_answer or "").strip()
    if not text:
        return TerminalOutcomeClassification(
            outcome=OUTCOME_UNCLASSIFIED,
            reason="Agent completed without a final answer.",
            rules_version=rules.rules_version,
            agent_status=agent_status,
        )

    claim = _matches(rules.completion_claim_patterns, text)
    negation = _matches(rules.negated_completion_patterns, text)
    stop = _matches(rules.stop_notice_patterns, text)

    if claim and negation:
        outcome, reason = (
            OUTCOME_UNCLASSIFIED,
            "Final answer both claims and denies completion.",
        )
    elif claim:
        outcome, reason = OUTCOME_SUCCESS, "Final answer claims the task was completed."
    elif negation or stop:
        outcome, reason = (
            OUTCOME_GRACEFUL_STOP,
            "Final answer tells the user the task was not completed.",
        )
    else:
        outcome, reason = (
            OUTCOME_UNCLASSIFIED,
            "Final answer matches no completion or stop pattern.",
        )

    return TerminalOutcomeClassification(
        outcome=outcome,
        reason=reason,
        rules_version=rules.rules_version,
        agent_status=agent_status,
        matched_completion=claim,
        matched_negation=negation,
        matched_stop_notice=stop,
    )


def classify_live_trace(
    trace: "ExecutionTrace", rules: TerminalOutcomeRules | None
) -> "ExecutionTrace":
    """Copy of a live trace whose ``caller_outcome`` is the classified terminal outcome.

    The raw outcome and the classification evidence are kept in ``aut_metadata``. Test-double
    traces (``is_simulation``) and traces already classified are returned unchanged.
    """
    meta = dict(trace.aut_metadata or {})
    if trace.is_simulation or "outcome_classification" in meta:
        return trace
    agent_error = meta.get("agent_error") or {}
    classification = classify_terminal_outcome(
        agent_status=meta.get("agent_status"),
        agent_error_code=agent_error.get("errorCode") or trace.caller_outcome,
        final_answer=meta.get("final_answer"),
        rules=rules,
    )
    meta["raw_caller_outcome"] = trace.caller_outcome
    meta["outcome_classification"] = classification.model_dump()
    update: dict[str, Any] = {
        "caller_outcome": classification.outcome,
        "aut_metadata": meta,
    }
    if classification.outcome == OUTCOME_EXECUTION_ERROR:
        update["is_complete"] = False
    return trace.model_copy(update=update)
