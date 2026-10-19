from app.components.c3_robustness_recovery.contracts.schemas import (
    EffectPhase,
    FaultCatalogResponse,
    FaultFamily,
    FaultFamilyCatalogItem,
    FaultValidationRequest,
    FaultValidationResponse,
    InterceptionHook,
    ReleaseRuleType,
    TimeoutDisconnectionMode,
    ToolMutability,
    ValidationReason,
    ValidationScope,
    ValidationStatus,
)

# Mandatory pending checks for STATIC_VALID results
STATIC_VALID_PENDING_CHECKS = [
    "Actual fixture reset and initial-state verification",
    "Trigger reachability",
    "Observation access",
    "Installed adapter capability verification",
    "Injection/effect-phase fidelity",
]


def get_fault_catalog() -> FaultCatalogResponse:
    """Return the catalogue of the exactly five operational fault families."""
    families = [
        FaultFamilyCatalogItem(
            family=FaultFamily.TIMEOUT_DISCONNECTION,
            name="Timeout or Disconnection",
            description=(
                "Simulates network layer or transport delays, indefinite hangs, "
                "socket drops, or immediate connection refused events."
            ),
            supported_modes=[
                "CALLER_TIMEOUT_EXCEEDED",
                "SOCKET_DROP",
                "HANG_INDEFINITELY",
                "CONNECTION_REFUSED",
            ],
            effect_phases=[
                EffectPhase.BEFORE_EFFECT,
                EffectPhase.AFTER_COMMIT,
                EffectPhase.PARTIAL_EFFECT,
                EffectPhase.NOT_APPLICABLE,
            ],
            constraints_summary=(
                "Requires timing_ms between 0 and 600,000 ms. Can simulate delays exceeding caller timeout."
            ),
            injection_implemented=False,
            note="Injection is not implemented in Phase 1.",
        ),
        FaultFamilyCatalogItem(
            family=FaultFamily.TRANSIENT_5XX,
            name="Transient 5xx Server Response",
            description=(
                "Simulates transient server-side errors (500 Internal Server Error, "
                "502 Bad Gateway, 503 Service Unavailable, 504 Gateway Timeout)."
            ),
            supported_modes=["HTTP_500", "HTTP_502", "HTTP_503", "HTTP_504"],
            effect_phases=[
                EffectPhase.BEFORE_EFFECT,
                EffectPhase.AFTER_COMMIT,
                EffectPhase.PARTIAL_EFFECT,
                EffectPhase.NOT_APPLICABLE,
            ],
            constraints_summary=(
                "Requires http_status in range 500-599. Does not imply every 5xx error is safe to retry."
            ),
            injection_implemented=False,
            note="Injection is not implemented in Phase 1.",
        ),
        FaultFamilyCatalogItem(
            family=FaultFamily.RATE_LIMIT_429,
            name="HTTP 429 Rate Limiting",
            description=(
                "Simulates rate limit exhaustion with HTTP 429 response and optional "
                "Retry-After header specification."
            ),
            supported_modes=["RATE_LIMIT_EXCEEDED"],
            effect_phases=[
                EffectPhase.BEFORE_EFFECT,
                EffectPhase.NOT_APPLICABLE,
            ],
            constraints_summary=(
                "http_status is strictly 429. retry_after_seconds may be absent or non-negative (0 is distinct from absent)."
            ),
            injection_implemented=False,
            note="Injection is not implemented in Phase 1.",
        ),
        FaultFamilyCatalogItem(
            family=FaultFamily.TOOL_UNAVAILABILITY,
            name="Tool Unavailability",
            description=(
                "Simulates circuit breaking, scheduled maintenance windows, "
                "downstream dependency outages, or resource exhaustion."
            ),
            supported_modes=[
                "CIRCUIT_BROKEN",
                "SERVICE_MAINTENANCE",
                "DEPENDENCY_OFFLINE",
                "RESOURCE_EXHAUSTED",
            ],
            effect_phases=[
                EffectPhase.BEFORE_EFFECT,
                EffectPhase.NOT_APPLICABLE,
            ],
            constraints_summary=(
                "Requires unavailability mode, retryable flag, and optional bounded release_seconds."
            ),
            injection_implemented=False,
            note="Injection is not implemented in Phase 1.",
        ),
        FaultFamilyCatalogItem(
            family=FaultFamily.MALFORMED_RESPONSE,
            name="Malformed or Truncated Response",
            description=(
                "Simulates payload corruption, truncated JSON output, schema non-compliance, "
                "unexpected MIME types, or empty response bodies."
            ),
            supported_modes=[
                "INVALID_JSON",
                "TRUNCATED_JSON",
                "SCHEMA_VIOLATION",
                "UNEXPECTED_CONTENT_TYPE",
                "EMPTY_BODY",
            ],
            effect_phases=[
                EffectPhase.BEFORE_EFFECT,
                EffectPhase.AFTER_COMMIT,
                EffectPhase.PARTIAL_EFFECT,
                EffectPhase.NOT_APPLICABLE,
            ],
            constraints_summary=(
                "Requires malformed mode and optional bounded raw fragment up to 2048 chars."
            ),
            injection_implemented=False,
            note="Injection is not implemented in Phase 1.",
        ),
    ]

    return FaultCatalogResponse(
        schema_version="1.0.0",
        families=families,
        count=5,
        injection_active=False,
        note=(
            "All operational fault families are defined for static validation. "
            "Runtime injection is not implemented in Phase 1."
        ),
    )


def validate_fault_case(
    request: FaultValidationRequest,
) -> FaultValidationResponse:
    """Perform pure, deterministic static validation of declared fault metadata.

    This function never interacts with the environment, network, database,
    or live tool targets. It returns safe reason codes and field paths.
    """
    reasons: list[ValidationReason] = []
    case = request.candidate_case
    manifest = request.adapter_manifest
    metadata = request.task_fixture_metadata
    recovery = request.recovery_contract

    # 1. Reference & Version Consistency
    if case.task_id != metadata.task_id or case.task_version != metadata.task_version:
        reasons.append(
            ValidationReason(
                code="TASK_REFERENCE_MISMATCH",
                message="Candidate task ID or version does not match task fixture metadata.",
                field_path="candidate_case.task_id",
            )
        )

    if (
        case.fixture_id != metadata.fixture_id
        or case.fixture_version != metadata.fixture_version
    ):
        reasons.append(
            ValidationReason(
                code="FIXTURE_REFERENCE_MISMATCH",
                message="Candidate fixture ID or version does not match task fixture metadata.",
                field_path="candidate_case.fixture_id",
            )
        )

    if (
        case.adapter_id != manifest.adapter_id
        or case.adapter_version != manifest.adapter_version
    ):
        reasons.append(
            ValidationReason(
                code="ADAPTER_REFERENCE_MISMATCH",
                message="Candidate adapter ID or version does not match adapter manifest.",
                field_path="candidate_case.adapter_id",
            )
        )

    if (
        case.recovery_contract_id != recovery.contract_id
        or case.recovery_contract_version != recovery.contract_version
    ):
        reasons.append(
            ValidationReason(
                code="RECOVERY_CONTRACT_REFERENCE_MISMATCH",
                message="Candidate recovery contract ID or version does not match recovery contract.",
                field_path="candidate_case.recovery_contract_id",
            )
        )

    if case.domain != metadata.domain:
        reasons.append(
            ValidationReason(
                code="DOMAIN_MISMATCH",
                message="Candidate domain does not match task fixture metadata domain.",
                field_path="candidate_case.domain",
            )
        )

    # 2. Task & Fixture Compatibility (Domain equality alone is insufficient)
    if case.tool_id not in metadata.associated_tool_ids:
        reasons.append(
            ValidationReason(
                code="TOOL_NOT_ASSOCIATED_WITH_TASK",
                message="Candidate tool is not declared in task fixture metadata associated tools.",
                field_path="candidate_case.tool_id",
            )
        )

    if case.recovery_contract_id not in metadata.associated_recovery_contract_ids:
        reasons.append(
            ValidationReason(
                code="CONTRACT_NOT_ASSOCIATED_WITH_TASK",
                message="Candidate recovery contract is not associated with task fixture metadata.",
                field_path="candidate_case.recovery_contract_id",
            )
        )

    # 3. Tool Existence & Mutability in Manifest
    manifest_tool = next((t for t in manifest.tools if t.tool_id == case.tool_id), None)
    if manifest_tool is None:
        reasons.append(
            ValidationReason(
                code="TOOL_NOT_FOUND_IN_MANIFEST",
                message="Candidate tool is not declared in the adapter capability manifest.",
                field_path="candidate_case.tool_id",
            )
        )
    else:
        # Check tool version match
        if manifest_tool.tool_version != case.tool_version:
            reasons.append(
                ValidationReason(
                    code="TOOL_VERSION_MISMATCH",
                    message="Tool version declared in manifest does not match candidate case tool version.",
                    field_path="candidate_case.tool_version",
                )
            )

        # Mutability constraints
        if manifest_tool.mutability == ToolMutability.READ_ONLY:
            if case.effect_phase in (
                EffectPhase.AFTER_COMMIT,
                EffectPhase.PARTIAL_EFFECT,
            ):
                reasons.append(
                    ValidationReason(
                        code="READ_ONLY_TOOL_INVALID_EFFECT_PHASE",
                        message=(
                            f"Read-only tool '{case.tool_id}' cannot specify effect phase '{case.effect_phase.value}'. "
                            "Read-only tools only support BEFORE_EFFECT or NOT_APPLICABLE."
                        ),
                        field_path="candidate_case.effect_phase",
                    )
                )
        elif (
            manifest_tool.mutability == ToolMutability.SIDE_EFFECTING
            and case.effect_phase == EffectPhase.NOT_APPLICABLE
        ):
            reasons.append(
                ValidationReason(
                    code="SIDE_EFFECTING_TOOL_INVALID_EFFECT_PHASE",
                    message=(
                        f"Side-effecting tool '{case.tool_id}' cannot specify NOT_APPLICABLE effect phase."
                    ),
                    field_path="candidate_case.effect_phase",
                )
            )

    # 4. Capability Combination Matching (No Cartesian Product Inference)
    matching_combinations = [
        c
        for c in manifest.supported_combinations
        if c.tool_id == case.tool_id
        and c.fault_family == case.fault_family
        and c.effect_phase == case.effect_phase
        and c.interception_hook == case.interception_hook
    ]

    if not matching_combinations:
        reasons.append(
            ValidationReason(
                code="UNSUPPORTED_CAPABILITY_COMBINATION",
                message=(
                    f"No declared capability combination supports tool '{case.tool_id}', "
                    f"family '{case.fault_family.value}', phase '{case.effect_phase.value}', "
                    f"and hook '{case.interception_hook.value}' in the manifest."
                ),
                field_path="candidate_case.fault_family",
            )
        )
    else:
        combination = matching_combinations[0]

        # Occurrence bounds check
        min_occ = combination.supported_occurrence_bounds.min_occurrence
        max_occ = combination.supported_occurrence_bounds.max_occurrence
        if not (min_occ <= case.occurrence <= max_occ):
            reasons.append(
                ValidationReason(
                    code="OCCURRENCE_OUT_OF_BOUNDS",
                    message=(
                        f"Candidate occurrence {case.occurrence} is outside the supported "
                        f"bounds [{min_occ}, {max_occ}] declared in the capability combination."
                    ),
                    field_path="candidate_case.occurrence",
                )
            )

        # Release rule type support
        if case.release_rule.rule_type not in combination.allowed_release_rule_types:
            reasons.append(
                ValidationReason(
                    code="UNSUPPORTED_RELEASE_RULE_TYPE",
                    message=(
                        f"Release rule type '{case.release_rule.rule_type.value}' is not allowed "
                        "by the matched capability combination."
                    ),
                    field_path="candidate_case.release_rule.rule_type",
                )
            )

        # Payload mode support
        payload_mode_str = getattr(case.payload, "mode", None)
        if payload_mode_str is not None:
            mode_val = (
                payload_mode_str.value
                if hasattr(payload_mode_str, "value")
                else str(payload_mode_str)
            )
        elif hasattr(case.payload, "http_status"):
            if case.fault_family == FaultFamily.RATE_LIMIT_429:
                mode_val = "RATE_LIMIT_EXCEEDED"
            else:
                mode_val = f"HTTP_{case.payload.http_status}"
        else:
            mode_val = None

        if (
            mode_val
            and mode_val not in combination.supported_payload_modes
            and case.fault_family.value not in combination.supported_payload_modes
        ):
            reasons.append(
                ValidationReason(
                    code="UNSUPPORTED_PAYLOAD_MODE",
                    message=(
                        f"Payload mode '{mode_val}' is not in the supported payload modes "
                        "declared for this combination."
                    ),
                    field_path="candidate_case.payload.mode",
                )
            )

        # Required observation capabilities
        for req_obs in combination.required_observation_capabilities:
            if req_obs not in case.required_observations:
                reasons.append(
                    ValidationReason(
                        code="MISSING_COMBINATION_OBSERVATION_REQUIREMENT",
                        message=(
                            f"Matched combination requires observation capability '{req_obs}' "
                            "which is missing from candidate required observations."
                        ),
                        field_path="candidate_case.required_observations",
                    )
                )

    # 5. Release Rule Constraints
    if case.release_rule.rule_type == ReleaseRuleType.ATTEMPT_BOUNDED:
        if (
            case.release_rule.max_fault_count is None
            or case.release_rule.max_fault_count < 1
        ):
            reasons.append(
                ValidationReason(
                    code="INVALID_ATTEMPT_BOUNDED_RELEASE_RULE",
                    message="ATTEMPT_BOUNDED release rule requires max_fault_count >= 1.",
                    field_path="candidate_case.release_rule.max_fault_count",
                )
            )
    elif case.release_rule.rule_type == ReleaseRuleType.TIME_BOUNDED and (
        case.release_rule.release_after_ms is None
        or case.release_rule.release_after_ms <= 0
    ):
        reasons.append(
            ValidationReason(
                code="INVALID_TIME_BOUNDED_RELEASE_RULE",
                message="TIME_BOUNDED release rule requires release_after_ms > 0.",
                field_path="candidate_case.release_rule.release_after_ms",
            )
        )

    # 6. Effect Phase Specific Metadata Requirements
    if case.effect_phase == EffectPhase.AFTER_COMMIT:
        if case.interception_hook != InterceptionHook.APPLICATION_AWARE_HOOK:
            reasons.append(
                ValidationReason(
                    code="AFTER_COMMIT_REQUIRES_APPLICATION_AWARE_HOOK",
                    message=(
                        "AFTER_COMMIT effect phase requires an APPLICATION_AWARE_HOOK. "
                        "A generic AFTER_TOOL_CALL hook alone does not establish AFTER_COMMIT."
                    ),
                    field_path="candidate_case.interception_hook",
                )
            )
        if not metadata.supports_committed_effect_observation:
            reasons.append(
                ValidationReason(
                    code="MISSING_COMMITTED_EFFECT_OBSERVATION_SUPPORT",
                    message="AFTER_COMMIT effect phase requires supports_committed_effect_observation in metadata.",
                    field_path="task_fixture_metadata.supports_committed_effect_observation",
                )
            )

    if case.effect_phase == EffectPhase.PARTIAL_EFFECT:
        if case.interception_hook != InterceptionHook.APPLICATION_AWARE_HOOK:
            reasons.append(
                ValidationReason(
                    code="PARTIAL_EFFECT_REQUIRES_APPLICATION_AWARE_HOOK",
                    message="PARTIAL_EFFECT effect phase requires an APPLICATION_AWARE_HOOK.",
                    field_path="candidate_case.interception_hook",
                )
            )
        if not metadata.supports_partial_effect_observation:
            reasons.append(
                ValidationReason(
                    code="MISSING_PARTIAL_EFFECT_OBSERVATION_SUPPORT",
                    message="PARTIAL_EFFECT effect phase requires supports_partial_effect_observation in metadata.",
                    field_path="task_fixture_metadata.supports_partial_effect_observation",
                )
            )

    # 7. Fixture Reset & Observation Support
    if (
        manifest_tool
        and manifest_tool.mutability == ToolMutability.SIDE_EFFECTING
        and not metadata.declared_reset_support
    ):
        reasons.append(
            ValidationReason(
                code="MISSING_FIXTURE_RESET_SUPPORT",
                message="Side-effecting tools require declared fixture reset support in task fixture metadata.",
                field_path="task_fixture_metadata.declared_reset_support",
            )
        )

    if not metadata.declared_observation_support:
        reasons.append(
            ValidationReason(
                code="MISSING_OBSERVATION_SUPPORT",
                message="Task fixture metadata must declare observation support.",
                field_path="task_fixture_metadata.declared_observation_support",
            )
        )

    for obs in case.required_observations:
        if obs not in metadata.supported_observations:
            reasons.append(
                ValidationReason(
                    code="UNSUPPORTED_OBSERVATION_REFERENCE",
                    message=(
                        f"Required observation reference '{obs}' is not declared in "
                        "task fixture supported observations."
                    ),
                    field_path="candidate_case.required_observations",
                )
            )

    # 8. Recovery Contract & Safety Constraints
    if (
        case.effect_phase == EffectPhase.AFTER_COMMIT
        and manifest_tool
        and manifest_tool.mutability == ToolMutability.SIDE_EFFECTING
        and not recovery.allow_duplicate_side_effects
        and recovery.max_retries is not None
        and recovery.max_retries > 0
        and not recovery.allow_retry_on_unverified_commit
    ):
        reasons.append(
            ValidationReason(
                code="UNSAFE_RETRY_ON_COMMITTED_EFFECT",
                message=(
                    "Retrying after an unverified committed side-effect without duplicate-effect "
                    "permission is unsafe and constitutes a recovery violation."
                ),
                field_path="recovery_contract.allow_duplicate_side_effects",
            )
        )

    # 9. Timeout & Duration Distinctions
    if case.fault_family == FaultFamily.TIMEOUT_DISCONNECTION:
        payload_mode = getattr(case.payload, "mode", None)
        if payload_mode == TimeoutDisconnectionMode.CALLER_TIMEOUT_EXCEEDED:
            if case.caller_timeout_ms is None or case.caller_timeout_ms <= 0:
                reasons.append(
                    ValidationReason(
                        code="MISSING_CALLER_TIMEOUT",
                        message=(
                            "CALLER_TIMEOUT_EXCEEDED mode requires candidate_case.caller_timeout_ms "
                            "to be specified and positive."
                        ),
                        field_path="candidate_case.caller_timeout_ms",
                    )
                )
            elif (
                case.payload.timing_ms is not None
                and case.payload.timing_ms <= case.caller_timeout_ms
            ):
                reasons.append(
                    ValidationReason(
                        code="FAULT_DURATION_MUST_EXCEED_CALLER_TIMEOUT",
                        message=(
                            f"CALLER_TIMEOUT_EXCEEDED requires fault duration timing_ms ({case.payload.timing_ms}) "
                            f"to exceed caller_timeout_ms ({case.caller_timeout_ms})."
                        ),
                        field_path="candidate_case.payload.timing_ms",
                    )
                )
        if (
            case.caller_timeout_ms is not None
            and case.caller_timeout_ms > recovery.max_total_timeout_ms
        ):
            reasons.append(
                ValidationReason(
                    code="CALLER_TIMEOUT_EXCEEDS_TRIAL_DEADLINE",
                    message=(
                        f"Caller timeout ({case.caller_timeout_ms} ms) cannot exceed "
                        f"recovery contract max_total_timeout_ms ({recovery.max_total_timeout_ms} ms)."
                    ),
                    field_path="candidate_case.caller_timeout_ms",
                )
            )
        if (
            getattr(case.payload, "timing_ms", None) is not None
            and case.payload.timing_ms > recovery.max_total_timeout_ms
        ):
            reasons.append(
                ValidationReason(
                    code="FAULT_DURATION_EXCEEDS_TRIAL_DEADLINE",
                    message=(
                        f"Fault duration ({case.payload.timing_ms} ms) cannot exceed "
                        f"recovery contract max_total_timeout_ms ({recovery.max_total_timeout_ms} ms)."
                    ),
                    field_path="candidate_case.payload.timing_ms",
                )
            )

    # 10. Response Formation
    if reasons:
        return FaultValidationResponse(
            validation_scope=ValidationScope.STATIC_ONLY,
            validation_status=ValidationStatus.TEST_NOT_READY,
            runtime_verified=False,
            execution_ready=False,
            reasons=reasons,
            pending_checks=[],
            recovery_verdict=None,
        )

    return FaultValidationResponse(
        validation_scope=ValidationScope.STATIC_ONLY,
        validation_status=ValidationStatus.STATIC_VALID,
        runtime_verified=False,
        execution_ready=False,
        reasons=[],
        pending_checks=list(STATIC_VALID_PENDING_CHECKS),
        recovery_verdict=None,
    )
