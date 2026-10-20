"""Canonical snapshots, semantic case fingerprinting, and frozen-suite integrity verification.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 3 - Automatic generation, frozen suites, remaining faults and supported post-commit experiments.
"""

import copy
import hashlib
import json
from typing import Any

from app.components.c3_robustness_recovery.contracts.generation import (
    FrozenSuite,
    GenerationCounters,
    GenerationPolicy,
)
from app.components.c3_robustness_recovery.contracts.schemas import (
    AdapterCapabilityManifest,
    CandidateFaultCase,
    FaultValidationRequest,
    RecoveryContract,
    TaskFixtureMetadata,
    ValidationStatus,
)
from app.components.c3_robustness_recovery.services.validation import (
    validate_fault_case,
)


def compute_semantic_case_fingerprint(case: CandidateFaultCase) -> str:
    """Compute a deterministic SHA-256 fingerprint of the semantic content of a candidate fault case.

    Excludes generated identifier fields (`case_id`, `case_family_id`, `project_id`),
    timestamps, and presentation labels.
    """
    payload_dict = case.payload.model_dump(mode="json")
    release_dict = case.release_rule.model_dump(mode="json")

    semantic_payload = {
        "adapter_id": case.adapter_id,
        "adapter_version": case.adapter_version,
        "caller_timeout_ms": case.caller_timeout_ms,
        "domain": case.domain,
        "effect_phase": case.effect_phase.value,
        "fault_family": case.fault_family.value,
        "fixture_id": case.fixture_id,
        "fixture_version": case.fixture_version,
        "interception_hook": case.interception_hook.value,
        "occurrence": case.occurrence,
        "payload": payload_dict,
        "recovery_contract_id": case.recovery_contract_id,
        "recovery_contract_version": case.recovery_contract_version,
        "release_rule": release_dict,
        "required_assertions": sorted(case.required_assertions),
        "required_observations": sorted(case.required_observations),
        "task_id": case.task_id,
        "task_version": case.task_version,
        "tool_id": case.tool_id,
        "tool_version": case.tool_version,
    }

    canonical = json.dumps(semantic_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_suite_digest(suite_dict: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 digest over the entire frozen suite content.

    The digest scope strictly excludes the self-referential `suite_digest` field.
    """
    data = copy.deepcopy(suite_dict)
    data.pop("suite_digest", None)

    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def freeze_suite(
    task_fixture_metadata: TaskFixtureMetadata,
    adapter_manifest: AdapterCapabilityManifest,
    recovery_contract: RecoveryContract,
    policy: GenerationPolicy,
    selected_cases: list[CandidateFaultCase],
    counters: GenerationCounters,
    limitations: list[str] | None = None,
    suite_id: str | None = None,
) -> FrozenSuite:
    """Construct an immutable, reproducible FrozenSuite snapshot."""
    suite_identifier = (
        suite_id
        if suite_id
        else f"suite-c3-{task_fixture_metadata.task_id}-{policy.seed}"
    )

    case_fps: dict[str, str] = {}
    for case in selected_cases:
        case_fps[case.case_id] = compute_semantic_case_fingerprint(case)

    suite_payload = {
        "schema_version": "1.0.0",
        "suite_id": suite_identifier,
        "generator_version": "1.0.0",
        "seed": policy.seed,
        "policy": policy.model_dump(mode="json"),
        "task_fixture_metadata": task_fixture_metadata.model_dump(mode="json"),
        "adapter_manifest": adapter_manifest.model_dump(mode="json"),
        "recovery_contract": recovery_contract.model_dump(mode="json"),
        "selected_cases": [c.model_dump(mode="json") for c in selected_cases],
        "case_fingerprints": case_fps,
        "counters": counters.model_dump(mode="json"),
        "limitations": limitations or [],
    }

    digest = compute_suite_digest(suite_payload)
    suite_payload["suite_digest"] = digest

    return FrozenSuite.model_validate(suite_payload)


def verify_suite_integrity(
    suite: FrozenSuite, raise_on_error: bool = True
) -> tuple[bool, list[str]]:
    """Verify cryptographic digest, case fingerprints, and static consistency of a frozen suite.

    Raises:
        ValueError: If raise_on_error is True and integrity verification fails.

    Returns:
        tuple[bool, list[str]]: (is_valid, reasons)
    """
    reasons: list[str] = []

    # 1. Digest Verification
    suite_dict = suite.model_dump(mode="json")
    declared_digest = suite.suite_digest
    recomputed_digest = compute_suite_digest(suite_dict)

    if declared_digest != recomputed_digest:
        reasons.append(
            f"Suite digest mismatch: declared '{declared_digest}' != recomputed '{recomputed_digest}'."
        )

    # 2. Case Fingerprint Integrity
    for case in suite.selected_cases:
        expected_fp = suite.case_fingerprints.get(case.case_id)
        if not expected_fp:
            reasons.append(
                f"Case '{case.case_id}' missing from suite_fingerprints mapping."
            )
            continue

        actual_fp = compute_semantic_case_fingerprint(case)
        if expected_fp != actual_fp:
            reasons.append(
                f"Case '{case.case_id}' semantic fingerprint mismatch: declared '{expected_fp}' != actual '{actual_fp}'."
            )

    # 3. Static Re-validation Against Frozen Inputs
    for case in suite.selected_cases:
        val_req = FaultValidationRequest(
            candidate_case=case,
            adapter_manifest=suite.adapter_manifest,
            task_fixture_metadata=suite.task_fixture_metadata,
            recovery_contract=suite.recovery_contract,
        )
        val_res = validate_fault_case(val_req)
        if val_res.validation_status != ValidationStatus.STATIC_VALID:
            for r in val_res.reasons:
                reasons.append(
                    f"Case '{case.case_id}' failed static revalidation ({r.code}): {r.message}"
                )

    is_valid = len(reasons) == 0
    if not is_valid and raise_on_error:
        raise ValueError(f"Suite integrity check failed: {'; '.join(reasons)}")

    return is_valid, reasons
