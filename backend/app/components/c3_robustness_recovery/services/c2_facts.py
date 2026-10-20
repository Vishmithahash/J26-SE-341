"""Minimal adapter and validation service for Component 2 workflow assertion facts.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 4 - Recovery evaluation using evidence and C2 facts.

C2 owns workflow state-machine evaluation and assertion truth determination.
C3 consumes discrete TRUE / FALSE / UNKNOWN facts without computing domain workflow state.
"""

from collections import defaultdict

from app.components.c3_robustness_recovery.contracts.evaluation import (
    C2AssertionFact,
    C2FactValue,
)


def validate_c2_facts(facts: list[C2AssertionFact]) -> tuple[bool, list[str]]:
    """Validate a collection of C2 assertion facts for internal consistency and scope conflicts.

    Rules:
    - Repeated facts across different time scopes or snapshots are valid (state changes over time).
    - Conflicting truth values (e.g. TRUE and FALSE) within the identical
      (assertion_id, entity_id, snapshot_id, time_scope, assertion_version) scope are rejected as conflicting evidence.
    - Contradictory assertion versions or conflicting values within an applicable scope prevent unjustified passes.
    """
    conflicts: list[str] = []
    scoped_values: dict[
        tuple[str, str, str | None, str | None, str | None], set[C2FactValue]
    ] = defaultdict(set)

    for fact in facts:
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
) -> C2FactValue:
    """Retrieve the discrete truth value of a specific assertion fact.

    Returns C2FactValue.UNKNOWN if no matching fact is provided or if conflicting
    matching facts exist within the applicable scope (prevents choosing a convenient
    fact to manufacture an unjustified pass).
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
        if time_scope is not None and fact.time_scope != time_scope:
            continue
        if entity_id is not None and fact.entity_id != entity_id:
            continue
        if snapshot_id is not None and fact.snapshot_id != snapshot_id:
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
    """Check availability of live Component 2 service in this workspace.

    Currently, app.components.c2_state_aware_workflow contains only an empty package marker.
    Live C2 service integration is therefore BLOCKED; offline/fixture facts are used.
    """
    return (
        False,
        (
            "Live C2 service integration is BLOCKED: app.components.c2_state_aware_workflow "
            "is an empty package marker in this workspace. Discrete fixture facts are consumed."
        ),
    )
