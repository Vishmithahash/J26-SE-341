"""Pure deterministic feasible candidate fault case generation and selection.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 3 - Automatic generation, frozen suites, remaining faults and supported post-commit experiments.
"""

import random
from collections import defaultdict

from pydantic import ValidationError

from app.components.c3_robustness_recovery.contracts.generation import (
    FaultGenerationRequest,
    FaultGenerationResponse,
    FrozenSuite,
    GenerationCounters,
    GenerationPolicy,
    GenerationStatus,
)
from app.components.c3_robustness_recovery.contracts.schemas import (
    CandidateFaultCase,
    EffectPhase,
    FaultFamily,
    FaultPayload,
    FaultValidationRequest,
    MalformedResponseMode,
    MalformedResponsePayload,
    RateLimit429Payload,
    ReleaseRule,
    ReleaseRuleType,
    TimeoutDisconnectionMode,
    TimeoutDisconnectionPayload,
    ToolMutability,
    ToolUnavailabilityMode,
    ToolUnavailabilityPayload,
    Transient5xxPayload,
    ValidationReason,
    ValidationScope,
    ValidationStatus,
)
from app.components.c3_robustness_recovery.services.suites import (
    compute_semantic_case_fingerprint,
    freeze_suite,
)
from app.components.c3_robustness_recovery.services.validation import (
    validate_fault_case,
)


def _derive_payloads_for_combination(
    family: FaultFamily,
    supported_modes: list[str],
    caller_timeout_ms: int,
) -> list[FaultPayload]:
    """Derive deterministic sample payloads permitted by the combination manifest."""
    payloads: list[FaultPayload] = []

    if family == FaultFamily.TIMEOUT_DISCONNECTION:
        for mode_str in supported_modes:
            try:
                mode = TimeoutDisconnectionMode(mode_str)
            except ValueError:
                continue

            if mode == TimeoutDisconnectionMode.CALLER_TIMEOUT_EXCEEDED:
                payloads.append(
                    TimeoutDisconnectionPayload(
                        mode=mode,
                        timing_ms=caller_timeout_ms + 1000,
                    )
                )
            elif mode == TimeoutDisconnectionMode.HANG_INDEFINITELY:
                payloads.append(
                    TimeoutDisconnectionPayload(
                        mode=mode,
                        timing_ms=None,
                    )
                )

    elif family == FaultFamily.TRANSIENT_5XX:
        status_map = {
            "HTTP_500": 500,
            "HTTP_502": 502,
            "HTTP_503": 503,
            "HTTP_504": 504,
        }
        for mode_str in supported_modes:
            status = status_map.get(mode_str, 500)
            payloads.append(
                Transient5xxPayload(
                    http_status=status,
                    error_code="TRANSIENT_SERVER_ERROR",
                    error_message=f"Injected transient {status} error",
                )
            )

    elif family == FaultFamily.RATE_LIMIT_429:
        payloads.append(
            RateLimit429Payload(
                http_status=429,
                retry_after_seconds=5,
                limit_scope="tool_call_rate_limit",
            )
        )
        payloads.append(
            RateLimit429Payload(
                http_status=429,
                retry_after_seconds=0,
                limit_scope="tool_call_rate_limit",
            )
        )

    elif family == FaultFamily.TOOL_UNAVAILABILITY:
        for mode_str in supported_modes:
            try:
                mode = ToolUnavailabilityMode(mode_str)
            except ValueError:
                continue
            payloads.append(
                ToolUnavailabilityPayload(
                    mode=mode,
                    retryable=True,
                    release_seconds=30,
                )
            )

    elif family == FaultFamily.MALFORMED_RESPONSE:
        for mode_str in supported_modes:
            try:
                mode = MalformedResponseMode(mode_str)
            except ValueError:
                continue
            frag = (
                '{"order_id": 123, <<malformed_json_syntax>>'
                if mode == MalformedResponseMode.INVALID_JSON
                else None
            )
            payloads.append(
                MalformedResponsePayload(
                    mode=mode,
                    raw_fragment=frag,
                )
            )

    return payloads


def generate_feasible_cases(
    request: FaultGenerationRequest,
) -> tuple[
    GenerationStatus,
    list[CandidateFaultCase],
    GenerationCounters,
    list[ValidationReason],
    FrozenSuite | None,
]:
    """Pure, deterministic generation, validation, and selection of feasible fault cases."""
    policy: GenerationPolicy = request.policy
    metadata = request.task_fixture_metadata
    manifest = request.adapter_manifest
    recovery = request.recovery_contract

    counters = GenerationCounters()
    rejection_reasons: list[ValidationReason] = []

    # 1. Baseline Task/Manifest Association Validation
    if not metadata.associated_tool_ids:
        rejection_reasons.append(
            ValidationReason(
                code="NO_ASSOCIATED_TOOLS",
                message="Task fixture metadata has no associated tools declared.",
                field_path="task_fixture_metadata.associated_tool_ids",
            )
        )
        return FaultGenerationResponse(
            validation_scope=ValidationScope.STATIC_ONLY,
            generation_status=GenerationStatus.TEST_NOT_READY,
            frozen_suite=None,
            counters=counters,
            reasons=rejection_reasons,
            pending_checks=[],
            runtime_verified=False,
            execution_ready=False,
            recovery_verdict=None,
        )

    # Deterministic RNG seeded by policy.seed
    rng = random.Random(policy.seed)

    # Eligible tools: declared in manifest and associated with task
    candidate_tools = [
        t for t in manifest.tools if t.tool_id in metadata.associated_tool_ids
    ]
    if policy.target_tool_ids:
        candidate_tools = [
            t for t in candidate_tools if t.tool_id in policy.target_tool_ids
        ]

    if not candidate_tools:
        rejection_reasons.append(
            ValidationReason(
                code="NO_MATCHING_TOOLS",
                message="No compatible tools found between adapter manifest and task metadata.",
                field_path="adapter_manifest.tools",
            )
        )
        return FaultGenerationResponse(
            validation_scope=ValidationScope.STATIC_ONLY,
            generation_status=GenerationStatus.NO_FEASIBLE_CASES,
            frozen_suite=None,
            counters=counters,
            reasons=rejection_reasons,
            pending_checks=[],
            runtime_verified=False,
            execution_ready=False,
            recovery_verdict=None,
        )

    feasible_pool: list[tuple[CandidateFaultCase, str]] = []
    seen_fingerprints: set[str] = set()

    caller_timeout_ms = 1000

    # 2. Bounded Candidate Enumeration
    for tool in candidate_tools:
        if counters.truncated:
            break

        matching_combinations = [
            c for c in manifest.supported_combinations if c.tool_id == tool.tool_id
        ]
        if policy.target_fault_families:
            matching_combinations = [
                c
                for c in matching_combinations
                if c.fault_family in policy.target_fault_families
            ]
        if policy.target_effect_phases:
            matching_combinations = [
                c
                for c in matching_combinations
                if c.effect_phase in policy.target_effect_phases
            ]

        for combo in matching_combinations:
            if counters.truncated:
                break

            # Mutability check: skip combinations violating read-only / side-effecting rules
            if tool.mutability == ToolMutability.READ_ONLY and combo.effect_phase in (
                EffectPhase.AFTER_COMMIT,
                EffectPhase.PARTIAL_EFFECT,
            ):
                continue
            if (
                tool.mutability == ToolMutability.SIDE_EFFECTING
                and combo.effect_phase == EffectPhase.NOT_APPLICABLE
            ):
                continue

            # Ensure task fixture supports observations required by combination
            missing_obs = [
                obs
                for obs in combo.required_observation_capabilities
                if obs not in metadata.supported_observations
            ]
            if missing_obs:
                continue

            # Sample permitted occurrence
            min_occ = combo.supported_occurrence_bounds.min_occurrence
            max_occ = combo.supported_occurrence_bounds.max_occurrence
            sample_occurrences = [min_occ]
            if max_occ > min_occ:
                sample_occurrences.append(min_occ + 1)

            # Sample permitted release rule
            sample_rules = []
            if ReleaseRuleType.ATTEMPT_BOUNDED in combo.allowed_release_rule_types:
                sample_rules.append(
                    ReleaseRule(
                        rule_type=ReleaseRuleType.ATTEMPT_BOUNDED,
                        max_fault_count=1,
                    )
                )
            elif ReleaseRuleType.IMMEDIATE in combo.allowed_release_rule_types:
                sample_rules.append(ReleaseRule(rule_type=ReleaseRuleType.IMMEDIATE))
            elif ReleaseRuleType.TIME_BOUNDED in combo.allowed_release_rule_types:
                sample_rules.append(
                    ReleaseRule(
                        rule_type=ReleaseRuleType.TIME_BOUNDED,
                        release_after_ms=5000,
                    )
                )

            # Derive concrete sample payloads
            payload_samples = _derive_payloads_for_combination(
                family=combo.fault_family,
                supported_modes=combo.supported_payload_modes,
                caller_timeout_ms=caller_timeout_ms,
            )

            # Required observations: combination observations or primary metadata observation
            case_obs = list(combo.required_observation_capabilities)
            if not case_obs and metadata.supported_observations:
                case_obs = [metadata.supported_observations[0]]

            for occurrence in sample_occurrences:
                for release_rule in sample_rules:
                    for payload in payload_samples:
                        counters.examined_count += 1
                        if counters.examined_count >= policy.max_candidates_examined:
                            counters.truncated = True
                            counters.truncation_reason = f"max_candidates_examined limit ({policy.max_candidates_examined}) reached."

                        candidate_dict = {
                            "schema_version": "1.0.0",
                            "project_id": request.project_id or f"{metadata.domain}-qa",
                            "case_id": "case-candidate-provisional",
                            "case_family_id": "fam-candidate-provisional",
                            "domain": metadata.domain,
                            "task_id": metadata.task_id,
                            "task_version": metadata.task_version,
                            "tool_id": tool.tool_id,
                            "tool_version": tool.tool_version,
                            "fixture_id": metadata.fixture_id,
                            "fixture_version": metadata.fixture_version,
                            "adapter_id": manifest.adapter_id,
                            "adapter_version": manifest.adapter_version,
                            "recovery_contract_id": recovery.contract_id,
                            "recovery_contract_version": recovery.contract_version,
                            "occurrence": occurrence,
                            "interception_hook": combo.interception_hook,
                            "fault_family": combo.fault_family,
                            "effect_phase": combo.effect_phase,
                            "payload": payload,
                            "release_rule": release_rule,
                            "required_assertions": recovery.required_state_assertions,
                            "required_observations": case_obs,
                            "caller_timeout_ms": caller_timeout_ms,
                            "reproducibility_seed": policy.seed,
                        }

                        try:
                            candidate = CandidateFaultCase.model_validate(
                                candidate_dict
                            )
                        except (ValidationError, ValueError):
                            counters.rejected_count += 1
                            continue

                        # Pure static validation
                        val_req = FaultValidationRequest(
                            candidate_case=candidate,
                            adapter_manifest=manifest,
                            task_fixture_metadata=metadata,
                            recovery_contract=recovery,
                        )
                        val_res = validate_fault_case(val_req)

                        if val_res.validation_status != ValidationStatus.STATIC_VALID:
                            counters.rejected_count += 1
                            continue

                        counters.valid_count += 1

                        # Deduplication using semantic content fingerprint
                        fp = compute_semantic_case_fingerprint(candidate)
                        if fp in seen_fingerprints:
                            counters.duplicate_count += 1
                        else:
                            seen_fingerprints.add(fp)
                            counters.unique_count += 1
                            feasible_pool.append((candidate, fp))

                        if counters.truncated:
                            break
                    if counters.truncated:
                        break
                if counters.truncated:
                    break

    if not feasible_pool:
        return (
            GenerationStatus.NO_FEASIBLE_CASES,
            [],
            counters,
            rejection_reasons,
            None,
        )

    # 3. Round-Robin Coverage Selection Across (tool_id, fault_family) Groups
    grouped_pool: dict[tuple[str, str], list[tuple[CandidateFaultCase, str]]] = (
        defaultdict(list)
    )
    for cand, fp in feasible_pool:
        key = (cand.tool_id, cand.fault_family.value)
        grouped_pool[key].append((cand, fp))

    # Shuffle each group deterministically using policy.seed
    for items in grouped_pool.values():
        rng.shuffle(items)

    selected_pool: list[tuple[CandidateFaultCase, str]] = []
    group_keys = sorted(grouped_pool.keys())

    round_idx = 0
    while len(selected_pool) < policy.max_cases:
        added_in_round = False
        for key in group_keys:
            if len(selected_pool) >= policy.max_cases:
                break
            if round_idx < len(grouped_pool[key]):
                selected_pool.append(grouped_pool[key][round_idx])
                added_in_round = True
        if not added_in_round:
            break
        round_idx += 1

    # 4. Deterministic Stable Identifier Assignment
    final_selected_cases: list[CandidateFaultCase] = []
    for cand, fp in selected_pool:
        family_slug = cand.fault_family.value.lower()[:8]
        deterministic_case_id = f"case-c3-{family_slug}-{fp[:8]}"
        deterministic_family_id = f"fam-c3-{cand.tool_id}-{family_slug}"

        cand_dict = cand.model_dump(mode="json")
        cand_dict["case_id"] = deterministic_case_id
        cand_dict["case_family_id"] = deterministic_family_id
        final_selected_cases.append(CandidateFaultCase.model_validate(cand_dict))

    counters.selected_count = len(final_selected_cases)

    frozen = None
    if final_selected_cases:
        # 5. Build Immutable Frozen Suite Snapshot
        frozen = freeze_suite(
            task_fixture_metadata=metadata,
            adapter_manifest=manifest,
            recovery_contract=recovery,
            policy=policy,
            selected_cases=final_selected_cases,
            counters=counters,
        )

    status = (
        GenerationStatus.GENERATED
        if final_selected_cases
        else GenerationStatus.NO_FEASIBLE_CASES
    )

    return FaultGenerationResponse(
        validation_scope=ValidationScope.STATIC_ONLY,
        generation_status=status,
        frozen_suite=frozen,
        counters=counters,
        reasons=rejection_reasons,
        pending_checks=[
            "Runtime adapter verification pending execution.",
            "Isolated fixture readiness check pending execution.",
        ],
        runtime_verified=False,
        execution_ready=False,
        recovery_verdict=None,
    )
