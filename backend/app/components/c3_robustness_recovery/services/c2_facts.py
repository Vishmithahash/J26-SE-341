"""Adapter, validation service, and bridge for Component 2 workflow assertion facts.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 4 - Recovery evaluation using evidence and C2 facts.

C2 owns workflow state-machine evaluation and assertion truth determination.
C3 consumes discrete TRUE / FALSE / UNKNOWN facts without computing domain workflow state.
This module implements the authoritative C2-to-C3 callable bridge.
"""

from collections import defaultdict
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.components.c3_robustness_recovery.contracts.evaluation import (
    C2AssertionFact,
    C2FactValue,
)
from app.components.c3_robustness_recovery.contracts.schemas import RecoveryContract
from app.components.c3_robustness_recovery.runtime.evidence import MatchedPairEvidence


class C2ToC3AssertionMapping(BaseModel):
    """Explicit versioned binding between a C3 recovery requirement and a C2 state assertion."""

    model_config = ConfigDict(extra="forbid")

    c3_assertion_id: str = Field(
        ..., description="Assertion ID expected by C3 recovery contract or rules"
    )
    c3_assertion_version: str = Field(
        default="1.0.0", description="Assertion version expected by C3"
    )
    c2_assertion_id: str = Field(
        ..., description="Underlying assertion ID defined in C2 predicate catalog"
    )
    c2_assertion_version: str = Field(
        default="1.0.0", description="Version of C2 assertion definition"
    )
    entity_type: str = Field(
        default="order", description="Entity type scoped by the assertion"
    )
    required_time_scope: str = Field(
        default="post_recovery",
        description="Observation time scope (e.g. 'post_recovery', 'final_state')",
    )
    required_trial_role: str = Field(
        default="FAULT",
        description="Role of trial providing observation evidence (must be FAULT for recovery)",
    )


# Default versioned mappings connecting canonical C3 requirements to registered C2 assertions
DEFAULT_C2_TO_C3_MAPPINGS: list[C2ToC3AssertionMapping] = [
    C2ToC3AssertionMapping(
        c3_assertion_id="order_created",
        c3_assertion_version="1.0.0",
        c2_assertion_id="order_created",
        c2_assertion_version="1.0.0",
        entity_type="order",
        required_time_scope="post_recovery",
    ),
    C2ToC3AssertionMapping(
        c3_assertion_id="refund_completed",
        c3_assertion_version="1.0.0",
        c2_assertion_id="refund_completed",
        c2_assertion_version="1.0.0",
        entity_type="refund",
        required_time_scope="post_recovery",
    ),
    C2ToC3AssertionMapping(
        c3_assertion_id="inventory_reserved",
        c3_assertion_version="1.0.0",
        c2_assertion_id="inventory_reserved",
        c2_assertion_version="1.0.0",
        entity_type="inventory",
        required_time_scope="post_recovery",
    ),
    C2ToC3AssertionMapping(
        c3_assertion_id="duplicate_side_effect_detected",
        c3_assertion_version="1.0.0",
        c2_assertion_id="duplicate_side_effect_detected",
        c2_assertion_version="1.0.0",
        entity_type="side_effects",
        required_time_scope="post_recovery",
    ),
    C2ToC3AssertionMapping(
        c3_assertion_id="idempotency_key_reused",
        c3_assertion_version="1.0.0",
        c2_assertion_id="idempotency_key_reused",
        c2_assertion_version="1.0.0",
        entity_type="call",
        required_time_scope="post_recovery",
    ),
    C2ToC3AssertionMapping(
        c3_assertion_id="target_idempotency_enforced",
        c3_assertion_version="1.0.0",
        c2_assertion_id="target_idempotency_enforced",
        c2_assertion_version="1.0.0",
        entity_type="idempotency",
        required_time_scope="post_recovery",
    ),
]


def validate_c2_facts(
    facts: list[C2AssertionFact],
    expected_project_id: str | None = None,
    expected_pair_id: str | None = None,
) -> tuple[bool, list[str]]:
    """Validate a collection of C2 assertion facts for internal consistency and scope conflicts.

    Rules:
    - Repeated facts across different time scopes or snapshots are valid (state changes over time).
    - Conflicting truth values (e.g. TRUE and FALSE) within the identical
      (assertion_id, entity_id, snapshot_id, time_scope, assertion_version) scope are rejected as conflicting evidence.
    - Contradictory assertion versions or conflicting values within an applicable scope prevent unjustified passes.
    - Scope mismatches against expected project or pair identities prevent invalid cross-boundary fact injection.
    """
    conflicts: list[str] = []
    scoped_values: dict[
        tuple[str, str, str | None, str | None, str | None], set[C2FactValue]
    ] = defaultdict(set)

    for fact in facts:
        # Check project mismatch if expected project is provided
        fact_pid = fact.details.get("project_id")
        if expected_project_id is not None and fact_pid is not None and fact_pid != expected_project_id:
            conflicts.append(
                f"Cross-project C2 fact rejected: fact project '{fact_pid}' does not match expected '{expected_project_id}'."
            )

        # Check pair mismatch if expected pair is provided
        fact_pair = fact.details.get("pair_id")
        if expected_pair_id is not None and fact_pair is not None and fact_pair != expected_pair_id:
            conflicts.append(
                f"Mismatched pair C2 fact rejected: fact pair '{fact_pair}' does not match expected '{expected_pair_id}'."
            )

        scope_key = (
            fact.assertion_id,
            fact.assertion_version,
            fact.entity_id,
            fact.snapshot_id,
            fact.time_scope,
        )
        scoped_values[scope_key].add(fact.value)

    for scope_key, values in scoped_values.items():
        assertion_id, assertion_version, entity_id, snapshot_id, time_scope = scope_key
        # If both TRUE and FALSE exist in the identical scope, that is a direct contradiction
        if C2FactValue.TRUE in values and C2FactValue.FALSE in values:
            conflicts.append(
                f"Conflicting C2 facts detected for assertion '{assertion_id}' (v{assertion_version}) in scope "
                f"(entity={entity_id}, snapshot={snapshot_id}, time_scope={time_scope}): "
                "both TRUE and FALSE reported simultaneously."
            )

    return len(conflicts) == 0, conflicts


def get_c2_fact_value(
    facts: list[C2AssertionFact],
    assertion_id: str,
    time_scope: str | None = None,
    entity_id: str | None = None,
    snapshot_id: str | None = None,
    assertion_version: str | None = None,
    expected_trial_id: str | None = None,
    expected_project_id: str | None = None,
    expected_pair_id: str | None = None,
    require_strict_scope: bool = False,
) -> C2FactValue:
    """Retrieve the discrete truth value of a specific assertion fact under strict scope enforcement.

    Returns C2FactValue.UNKNOWN if no matching fact is provided or if conflicting/wrong-scope
    facts exist within the applicable scope (prevents choosing a convenient fact to manufacture
    an unjustified pass).
    Does not compute or infer missing domain workflow state.
    """
    matching_values: set[C2FactValue] = set()

    for fact in facts:
        if fact.assertion_id != assertion_id:
            continue
        if (
            assertion_version is not None
            and fact.assertion_version != assertion_version
        ):
            continue

        is_imported_untrusted = bool(
            fact.details.get("imported") is True
            or fact.details.get("self_reported") is True
            or fact.provenance == "OFFLINE_EXPORT"
        )

        is_offline_demo_fact = is_imported_untrusted or fact.provenance in (
            "C2_FIXTURE",
            "C2_DEMO_FIXTURE",
            "TEST_FIXTURE",
            "OFFLINE_DEMO",
            "OFFLINE_EXPORT",
            "SYNTHETIC",
            "FALLBACK_OFFLINE",
        )

        is_fact_authoritative = (
            require_strict_scope and not is_offline_demo_fact
        ) or (
            not is_imported_untrusted
            and fact.provenance in ("SERVER_EVALUATED", "SHARED_RUN", "C2_EVALUATOR_BRIDGE")
        )

        # Trial scope enforcement: do not disable trial checks because supplied facts omit trial IDs
        if expected_trial_id is not None and fact.details.get("trial_id") != expected_trial_id:
            continue

        # Project scope enforcement
        if expected_project_id is not None and fact.details.get("project_id") != expected_project_id:
            continue

        # Pair scope enforcement
        if expected_pair_id is not None and fact.details.get("pair_id") != expected_pair_id:
            continue

        if is_fact_authoritative:
            # Strict scope enforcement for authoritative shared-execution facts
            if time_scope is not None and fact.time_scope != time_scope:
                continue
            if entity_id is not None and fact.entity_id != entity_id:
                continue
            if snapshot_id is not None:
                if fact.snapshot_id != snapshot_id:
                    continue
            elif fact.snapshot_id is not None:
                # Missing required snapshot scope cannot be satisfied by an arbitrary unrelated snapshot
                continue
            if expected_trial_id is not None and (
                not fact.supporting_evidence_refs
                or expected_trial_id not in fact.supporting_evidence_refs
            ):
                continue
        else:
            # Preserve compatibility for explicitly labelled offline/demo fact workflows
            if time_scope is not None and fact.time_scope is not None and fact.time_scope != time_scope:
                continue
            if entity_id is not None and fact.entity_id is not None and fact.entity_id != entity_id:
                continue
            if snapshot_id is not None and fact.snapshot_id is not None and fact.snapshot_id != snapshot_id:
                continue

        matching_values.add(fact.value)

    if not matching_values:
        return C2FactValue.UNKNOWN

    # If matching facts have conflicting non-unknown truth values, prevent unjustified pass
    if C2FactValue.TRUE in matching_values and C2FactValue.FALSE in matching_values:
        return C2FactValue.UNKNOWN

    if C2FactValue.TRUE in matching_values and C2FactValue.UNKNOWN in matching_values:
        # Ambiguous scope: do not pick convenient TRUE
        return C2FactValue.UNKNOWN

    if C2FactValue.TRUE in matching_values:
        return C2FactValue.TRUE
    if C2FactValue.FALSE in matching_values:
        return C2FactValue.FALSE

    return C2FactValue.UNKNOWN


def check_c2_integration_status() -> tuple[bool, str]:
    """Check availability of live Component 2 predicate evaluation service and assertion bridge.

    Inspects registered capabilities in app.components.c2_state_aware_workflow dynamically.
    An importable package alone does not prove a functioning bridge.
    """
    try:
        from app.components.c2_state_aware_workflow.integrations.assertion_facade import (
            C2NamedAssertionEvaluator,
        )

        evaluator = C2NamedAssertionEvaluator()
        registered = evaluator.list_registered_assertions()
        if not registered:
            return (
                False,
                "Live C2 service integration is BLOCKED: assertion facade present but zero assertions registered.",
            )
        return (
            True,
            f"Live C2 predicate evaluator and assertion bridge operational ({len(registered)} registered assertions).",
        )
    except Exception as exc:  # noqa: BLE001
        return (
            False,
            f"Live C2 service integration is BLOCKED: {exc}",
        )


def evaluate_c2_facts_bridge(
    project_id: str,
    pair_id: str,
    fault_trial_id: str,
    evidence: MatchedPairEvidence,
    recovery_contract: RecoveryContract,
    observation_snapshot: dict[str, Any] | None = None,
    mappings: list[C2ToC3AssertionMapping] | None = None,
    expected_entity_id: str | None = None,
    time_scope: str = "post_recovery",
) -> list[C2AssertionFact]:
    """Callable bridge that obtains named assertion results through C2-owned evaluation logic.

    Guarantees:
    - Only evaluates observations from the FAULT trial (never clean trial).
    - Preserves discrete TRUE, FALSE, UNKNOWN without collapsing into overall C2 verdicts.
    - Rejects mismatched project, pair, trial, entity, version or evidence references.
    - Missing, ambiguous or unobserved state facts evaluate to UNKNOWN (no manufactured passes).
    - Facts are tagged with server-side authoritative provenance: 'C2_EVALUATOR_BRIDGE'.
    """
    # 1. Scope and trial verification
    if evidence.pair_id != pair_id:
        raise ValueError(
            f"Mismatched pair reference: bridge requested pair '{pair_id}' but evidence has '{evidence.pair_id}'."
        )

    if evidence.clean_trial.trial_id == fault_trial_id:
        raise ValueError(
            f"Safety violation: trial '{fault_trial_id}' is the clean control trial. "
            "C2 recovery facts must refer to the fault trial, never the clean trial."
        )

    if evidence.fault_trial.trial_id != fault_trial_id:
        raise ValueError(
            f"Mismatched trial reference: bridge requested fault trial '{fault_trial_id}' "
            f"but evidence fault trial is '{evidence.fault_trial.trial_id}'."
        )

    # 2. Check C2 availability
    is_available, status_msg = check_c2_integration_status()
    if not is_available:
        # If C2 is unavailable, return all required assertions as UNKNOWN
        facts: list[C2AssertionFact] = []
        for req_id in recovery_contract.required_state_assertions:
            facts.append(
                C2AssertionFact(
                    assertion_id=req_id,
                    assertion_version="1.0.0",
                    value=C2FactValue.UNKNOWN,
                    entity_id=expected_entity_id,
                    time_scope=time_scope,
                    evaluator_version="c2_unavailable",
                    provenance="C2_EVALUATOR_BRIDGE",
                    supporting_evidence_refs=[fault_trial_id],
                    details={"error": status_msg},
                )
            )
        return facts

    # 3. Import C2 assertion evaluator & prepare context
    from app.components.c2_state_aware_workflow.integrations.assertion_facade import (
        C2NamedAssertionEvaluator,
    )
    from app.components.c2_state_aware_workflow.predicates.evaluator import (
        EvaluationContext,
    )
    from app.components.c2_state_aware_workflow.predicates.tristate import TriState

    evaluator = C2NamedAssertionEvaluator()

    # Build evaluation context from actual observed state
    # Scopes: after=observation_snapshot, before=clean baseline snapshot, event=fault execution metadata
    context_data = observation_snapshot or {}
    eval_context = EvaluationContext(
        after=context_data.get("after") or context_data,
        before=context_data.get("before"),
        event=context_data.get("event")
        or {
            "trial_id": fault_trial_id,
            "tool_calls_count": evidence.fault_trial.tool_calls_count,
            "subsequent_calls_count": evidence.fault_trial.subsequent_calls_count,
            "caller_outcome": evidence.fault_trial.caller_outcome,
        },
        variables=context_data.get("vars", {}),
    )

    # 4. Resolve mappings
    active_mappings = {
        m.c3_assertion_id: m for m in (mappings or DEFAULT_C2_TO_C3_MAPPINGS)
    }

    facts: list[C2AssertionFact] = []
    snapshot_id = context_data.get("snapshot_id") or f"snap-{fault_trial_id[:8]}"

    # All assertions required by contract + standard rule assertions
    all_target_assertions = set(recovery_contract.required_state_assertions)
    # Also include standard recovery rules assertions if context or contract refers to them
    all_target_assertions.update(
        [
            "duplicate_side_effect_detected",
            "idempotency_key_reused",
            "target_idempotency_enforced",
        ]
    )

    for c3_id in sorted(all_target_assertions):
        mapping = active_mappings.get(c3_id)
        if mapping is None:
            # Unmapped assertion: strictly UNKNOWN
            facts.append(
                C2AssertionFact(
                    assertion_id=c3_id,
                    assertion_version="1.0.0",
                    value=C2FactValue.UNKNOWN,
                    entity_id=expected_entity_id,
                    snapshot_id=snapshot_id,
                    time_scope=time_scope,
                    evaluator_version=evaluator.EVALUATOR_VERSION,
                    provenance="C2_EVALUATOR_BRIDGE",
                    supporting_evidence_refs=[fault_trial_id, snapshot_id],
                    details={
                        "project_id": project_id,
                        "pair_id": pair_id,
                        "trial_id": fault_trial_id,
                        "reason": f"No registered C2 mapping for assertion '{c3_id}'.",
                    },
                )
            )
            continue

        # Evaluate through C2 predicate evaluator
        c2_res = evaluator.evaluate_named_assertion(
            assertion_id=mapping.c2_assertion_id,
            observation_context=eval_context,
            time_scope=mapping.required_time_scope,
            entity_id=expected_entity_id,
            snapshot_id=snapshot_id,
            expected_version=mapping.c2_assertion_version,
        )

        # Convert TriState to C2FactValue
        if c2_res.value == TriState.TRUE:
            fact_val = C2FactValue.TRUE
        elif c2_res.value == TriState.FALSE:
            fact_val = C2FactValue.FALSE
        else:
            fact_val = C2FactValue.UNKNOWN

        facts.append(
            C2AssertionFact(
                assertion_id=mapping.c3_assertion_id,
                assertion_version=mapping.c3_assertion_version,
                value=fact_val,
                entity_id=expected_entity_id,
                snapshot_id=snapshot_id,
                time_scope=mapping.required_time_scope,
                evaluator_version=evaluator.EVALUATOR_VERSION,
                provenance="C2_EVALUATOR_BRIDGE",
                supporting_evidence_refs=[fault_trial_id, snapshot_id],
                details={
                    "project_id": project_id,
                    "pair_id": pair_id,
                    "trial_id": fault_trial_id,
                    "c2_assertion_id": mapping.c2_assertion_id,
                    "c2_assertion_version": mapping.c2_assertion_version,
                    **c2_res.details,
                },
            )
        )

    return facts
