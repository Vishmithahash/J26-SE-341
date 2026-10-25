"""Workflow mutations applied to real (live) runtime evidence for oracle-sensitivity testing.

Generated MUTATED cases describe a controlled workflow fault (skipped, reordered, repeated,
illegal, wrong-entity, missing-effect, protected-state and premature-termination). In live mode
the mutation operator is applied to the real evidence of the mutant's parent case: the events,
arguments, results and NexaCart snapshots all come from that live run, and only the declared
fault is introduced. The resulting evidence is labelled ``live_trace_mutation`` and is never
reported as an observed agent failure; it measures whether the C2 oracle detects the fault
(mutation detection score).

An operator that cannot introduce a discriminating fault into the given trace (for example,
reordering a trace with a single state-changing step) returns ``applied=False`` with a reason,
so the case is reported NOT_APPLICABLE rather than scored.
"""

import copy
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)
from app.components.c2_state_aware_workflow.contracts.runtime_evidence import (
    RuntimeEvent,
    RuntimeEvidenceContract,
    StateObservation,
)
from app.components.c2_state_aware_workflow.contracts.test_definition import (
    MutationProvenance,
    MutationType,
)

LIVE_TRACE_MUTATION_MODE = "live_trace_mutation"
# Order-level actions preferred for an illegal (unmodelled) step, in this order.
_ILLEGAL_ACTION_CANDIDATES = ("cancel_order", "pay_order", "refund_order", "checkout")
_WRONG_ORDER_NUMBER = "NXC-QA-WRONG000"

Step = tuple[RuntimeEvent, StateObservation]


@dataclass
class LiveMutationResult:
    applied: bool
    evidence: RuntimeEvidenceContract | None = None
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)


def _flatten(node: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, value in node.items():
            out.update(_flatten(value, f"{prefix}.{key}" if prefix else str(key)))
        return out
    return {prefix: node}


def _set_path(node: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def _as_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation:
            return None
    return None


def _changed_paths(before: dict[str, Any], after: dict[str, Any]) -> dict[str, tuple]:
    flat_before, flat_after = _flatten(before), _flatten(after)
    return {
        path: (flat_before.get(path), value)
        for path, value in flat_after.items()
        if flat_before.get(path) != value
    }


def _undo(state: dict[str, Any], changes: dict[str, tuple]) -> dict[str, Any]:
    """Remove one step's effect from a later state (values the step set go back)."""
    result = copy.deepcopy(state)
    flat = _flatten(result)
    for path, (old, new) in changes.items():
        if path in flat and flat[path] == new:
            _set_path(result, path, old)
    return result


def _repeat(state: dict[str, Any], changes: dict[str, tuple]) -> dict[str, Any]:
    """Apply one step's numeric deltas once more (counts and totals accumulate)."""
    result = copy.deepcopy(state)
    flat = _flatten(result)
    for path, (old, new) in changes.items():
        old_d, new_d, cur_d = (
            _as_decimal(old),
            _as_decimal(new),
            _as_decimal(flat.get(path)),
        )
        if None in (old_d, new_d, cur_d):
            continue
        updated = cur_d + (new_d - old_d)
        current = flat[path]
        if isinstance(current, int):
            _set_path(result, path, int(updated))
        elif isinstance(current, float):
            _set_path(result, path, float(updated))
        else:
            _set_path(result, path, f"{updated:.2f}")
    return result


class LiveTraceMutator:
    """Applies one declared mutation operator to the evidence of a live parent run."""

    def __init__(self, model: EFSMModelDefinition):
        self.model = model
        self.mapped_tools = {m.tool_name for m in model.event_mappings}

    def mutate(
        self,
        parent: RuntimeEvidenceContract,
        provenance: MutationProvenance,
        test_id: str,
        run_id: str,
        fixture_context: dict[str, Any] | None = None,
    ) -> LiveMutationResult:
        steps = self._steps(parent)
        if steps is None:
            return LiveMutationResult(
                False,
                reason="The parent live trace has no state observation for every event.",
            )
        effect_idx = [
            i
            for i, (_e, obs) in enumerate(steps)
            if obs.before_state != obs.after_state
        ]
        operator = {
            MutationType.SKIPPED_STEP: self._skipped,
            MutationType.REORDERED_STEP: self._reordered,
            MutationType.REPEATED_STEP: self._repeated,
            MutationType.ILLEGAL_TRANSITION: self._illegal,
            MutationType.WRONG_ENTITY: self._wrong_entity,
            MutationType.MISSING_EFFECT: self._missing_effect,
            MutationType.UNEXPECTED_PROTECTED_STATE_CHANGE: self._protected_change,
            MutationType.PREMATURE_TERMINATION: self._premature,
        }[provenance.mutation_type]
        mutated, reason, details = operator(steps, effect_idx, fixture_context or {})
        if mutated is None:
            return LiveMutationResult(False, reason=reason)
        evidence = self._rebuild(parent, mutated, test_id, run_id, provenance, details)
        return LiveMutationResult(
            True, evidence=evidence, reason=reason, details=details
        )

    # -- operators -------------------------------------------------------------

    def _skipped(self, steps: list[Step], effect_idx: list[int], _fx):
        if not effect_idx:
            return None, "The parent trace has no state-changing step to skip.", {}
        k = effect_idx[0]
        changes = _changed_paths(steps[k][1].before_state, steps[k][1].after_state)
        mutated = steps[:k] + [
            (
                ev,
                self._obs(
                    ev, _undo(o.before_state, changes), _undo(o.after_state, changes)
                ),
            )
            for ev, o in steps[k + 1 :]
        ]
        return (
            mutated,
            f"Removed state-changing step '{steps[k][0].tool_name}' (event {k}) and its effects.",
            {"skipped_event_index": k, "skipped_tool": steps[k][0].tool_name},
        )

    def _reordered(self, steps: list[Step], effect_idx: list[int], _fx):
        if len(effect_idx) < 2:
            return (
                None,
                (
                    "The parent trace has a single state-changing step; moving it relative to a "
                    "read-only lookup is a permitted alternative path, so reordering is not "
                    "discriminating."
                ),
                {},
            )
        a, b = effect_idx[0], effect_idx[1]
        mutated = list(steps)
        mutated[a], mutated[b] = steps[b], steps[a]
        return (
            mutated,
            f"Swapped dependent steps '{steps[a][0].tool_name}' and '{steps[b][0].tool_name}'.",
            {"swapped_event_indices": [a, b]},
        )

    def _repeated(self, steps: list[Step], effect_idx: list[int], _fx):
        if not effect_idx:
            return None, "The parent trace has no state-changing step to repeat.", {}
        k = effect_idx[-1]
        event, obs = steps[k]
        changes = _changed_paths(obs.before_state, obs.after_state)
        repeated_after = _repeat(obs.after_state, changes)
        duplicate = (
            event.model_copy(update={"event_id": f"{event.event_id}-repeat"}),
            self._obs(event, obs.after_state, repeated_after),
        )
        later = [
            (
                ev,
                self._obs(
                    ev,
                    _repeat(o.before_state, changes),
                    _repeat(o.after_state, changes),
                ),
            )
            for ev, o in steps[k + 1 :]
        ]
        return (
            steps[: k + 1] + [duplicate] + later,
            f"Repeated state-changing step '{event.tool_name}' (event {k}) with its effect applied twice.",
            {"repeated_event_index": k, "repeated_tool": event.tool_name},
        )

    def _illegal(self, steps: list[Step], effect_idx: list[int], fx: dict[str, Any]):
        tool = next(
            (t for t in _ILLEGAL_ACTION_CANDIDATES if t not in self.mapped_tools), None
        )
        if tool is None:
            return None, "Every order-level action is part of this model.", {}
        at = effect_idx[0] if effect_idx else len(steps)
        state = (
            steps[at][1].before_state
            if at < len(steps)
            else (steps[-1][1].after_state if steps else {})
        )
        args = {"orderNumber": fx["orderNumber"]} if fx.get("orderNumber") else {}
        illegal = RuntimeEvent(
            event_index=0,
            event_id="mutant-illegal-action",
            tool_name=tool,
            arguments=args,
            observable_result={"ok": True, "data": {}},
        )
        mutated = (
            steps[:at] + [(illegal, self._obs(illegal, state, state))] + steps[at:]
        )
        return (
            mutated,
            f"Inserted action '{tool}', which the workflow does not permit, before event {at}.",
            {"inserted_event_index": at, "inserted_tool": tool},
        )

    def _wrong_entity(self, steps: list[Step], effect_idx: list[int], _fx):
        k = next(
            (i for i in effect_idx if "orderNumber" in steps[i][0].arguments), None
        )
        if k is None:
            return (
                None,
                "No state-changing step in the parent trace names an order.",
                {},
            )
        event, obs = steps[k]
        original = event.arguments["orderNumber"]
        wrong = event.model_copy(
            update={
                "arguments": {**event.arguments, "orderNumber": _WRONG_ORDER_NUMBER}
            }
        )
        mutated = list(steps)
        mutated[k] = (wrong, obs)
        return (
            mutated,
            (
                f"Step '{event.tool_name}' (event {k}) now targets order {_WRONG_ORDER_NUMBER} "
                f"instead of {original}."
            ),
            {
                "event_index": k,
                "original_order": original,
                "wrong_order": _WRONG_ORDER_NUMBER,
            },
        )

    def _missing_effect(self, steps: list[Step], effect_idx: list[int], _fx):
        if not effect_idx:
            return None, "The parent trace has no state-changing step.", {}
        k = effect_idx[-1]
        event, obs = steps[k]
        changes = _changed_paths(obs.before_state, obs.after_state)
        mutated = steps[:k] + [
            (event, self._obs(event, obs.before_state, obs.before_state))
        ]
        mutated += [
            (
                ev,
                self._obs(
                    ev, _undo(o.before_state, changes), _undo(o.after_state, changes)
                ),
            )
            for ev, o in steps[k + 1 :]
        ]
        return (
            mutated,
            (
                f"Step '{event.tool_name}' (event {k}) still reports success but NexaCart state "
                "is left unchanged."
            ),
            {"event_index": k, "tool": event.tool_name},
        )

    def _protected_change(self, steps: list[Step], _effect_idx: list[int], _fx):
        if not self.model.protected_fields or not steps:
            return None, "The model declares no protected fields.", {}
        event, obs = steps[-1]
        flat = _flatten(obs.after_state)
        path = next(
            (
                pf.field_path
                for pf in reversed(self.model.protected_fields)
                if pf.field_path in flat
            ),
            None,
        )
        if path is None:
            return None, "No protected field is present in the observed state.", {}
        old = flat[path]
        new = self._different_value(path, old)
        after = copy.deepcopy(obs.after_state)
        _set_path(after, path, new)
        mutated = steps[:-1] + [(event, self._obs(event, obs.before_state, after))]
        return (
            mutated,
            f"Protected field '{path}' changed from {old!r} to {new!r} in the final state.",
            {"field_path": path, "original": old, "mutated": new},
        )

    def _premature(self, steps: list[Step], effect_idx: list[int], _fx):
        if not effect_idx:
            return None, "The parent trace has no state-changing step.", {}
        k = effect_idx[-1]
        return (
            steps[:k],
            f"The agent stops before state-changing step '{steps[k][0].tool_name}' (event {k}).",
            {"truncated_at_event_index": k},
        )

    # -- helpers ---------------------------------------------------------------

    @staticmethod
    def _different_value(path: str, old: Any) -> Any:
        if path.endswith(("status", "Status")):
            return "PENDING" if old != "PENDING" else "CANCELLED"
        number = _as_decimal(old)
        if number is not None:
            changed = number + 1
            return int(changed) if isinstance(old, int) else f"{changed:.2f}"
        return f"{old}-changed"

    @staticmethod
    def _obs(event: RuntimeEvent, before: dict, after: dict) -> StateObservation:
        return StateObservation(
            event_index=event.event_index,
            before_state=copy.deepcopy(before),
            after_state=copy.deepcopy(after),
            state_diff={},
        )

    @staticmethod
    def _steps(evidence: RuntimeEvidenceContract) -> list[Step] | None:
        by_index = {o.event_index: o for o in evidence.state_observations}
        steps: list[Step] = []
        for event in evidence.ordered_events:
            obs = by_index.get(event.event_index)
            if obs is None:
                return None
            steps.append((event, obs))
        return steps

    @staticmethod
    def _rebuild(
        parent: RuntimeEvidenceContract,
        steps: list[Step],
        test_id: str,
        run_id: str,
        provenance: MutationProvenance,
        details: dict[str, Any],
    ) -> RuntimeEvidenceContract:
        events: list[RuntimeEvent] = []
        observations: list[StateObservation] = []
        for idx, (event, obs) in enumerate(steps):
            events.append(event.model_copy(update={"event_index": idx}))
            observations.append(obs.model_copy(update={"event_index": idx}))
        return RuntimeEvidenceContract(
            schema_version=parent.schema_version,
            project_id=parent.project_id,
            suite_id=parent.suite_id,
            run_id=run_id,
            test_id=test_id,
            model_id=parent.model_id,
            model_version=parent.model_version,
            model_content_hash=parent.model_content_hash,
            ordered_events=events,
            state_observations=observations,
            completeness=parent.completeness,
            execution_mode=LIVE_TRACE_MUTATION_MODE,
            collector_provenance={
                **parent.collector_provenance,
                "actual_execution_origin": LIVE_TRACE_MUTATION_MODE,
                "is_live_execution": False,
                "derived_from_live_execution": True,
                "parent_test_id": parent.test_id,
                "parent_run_id": parent.run_id,
                "mutation_type": provenance.mutation_type.value,
                "mutation_description": provenance.description,
                "mutation_details": details,
                "note": (
                    "Controlled mutant of a real NexaCart trace for oracle-sensitivity testing; "
                    "not an observed agent failure."
                ),
            },
        )
