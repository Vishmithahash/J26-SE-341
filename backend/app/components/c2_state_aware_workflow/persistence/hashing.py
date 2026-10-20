"""Deterministic hashing for EFSM models and definitions.

Ensures that any behavioral change in states, transitions, guards, invariants,
effects, milestones, or outcomes changes the canonical content hash,
while transient metadata (timestamps, reviewer notes, status) is excluded.
"""

import hashlib
import json
from typing import Any

from app.components.c2_state_aware_workflow.contracts.efsm_model import (
    EFSMModelDefinition,
)

# Keys that are purely lifecycle or presentation metadata, not behavioral definition
EXCLUDED_METADATA_KEYS = {
    "created_at",
    "updated_at",
    "approved_at",
    "approved_by",
    "review_basis",
    "review_notes",
    "lifecycle_status",
    "is_active",
}


def _normalize_obj_for_hashing(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: _normalize_obj_for_hashing(v)
            for k, v in sorted(obj.items())
            if k not in EXCLUDED_METADATA_KEYS
        }
    if isinstance(obj, list):
        return [_normalize_obj_for_hashing(item) for item in obj]
    return obj


def compute_model_content_hash(definition: EFSMModelDefinition | dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash of the canonical model definition."""
    if isinstance(definition, EFSMModelDefinition):
        raw_dict = definition.model_dump(mode="json")
    else:
        raw_dict = definition

    normalized = _normalize_obj_for_hashing(raw_dict)
    canonical_json = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
