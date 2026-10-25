from enum import Enum
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    model_validator,
)


def _check_no_credentials_or_code(v: str) -> str:
    lowered = v.lower()
    dangerous_patterns = [
        "postgresql://",
        "postgres://",
        "password=",
        "secret=",
        "eval(",
        "exec(",
        "drop table",
        "select *",
        "select 1",
        "rm -rf",
        "__import__",
        "<script",
    ]
    for pattern in dangerous_patterns:
        if pattern in lowered:
            raise ValueError(
                "Input contains forbidden credentials, connection strings, or executable expressions."
            )
    return v


SafeStr = Annotated[str, AfterValidator(_check_no_credentials_or_code)]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FaultFamily(str, Enum):
    TIMEOUT_DISCONNECTION = "TIMEOUT_DISCONNECTION"
    TRANSIENT_5XX = "TRANSIENT_5XX"
    RATE_LIMIT_429 = "RATE_LIMIT_429"
    TOOL_UNAVAILABILITY = "TOOL_UNAVAILABILITY"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"


class EffectPhase(str, Enum):
    BEFORE_EFFECT = "BEFORE_EFFECT"
    AFTER_COMMIT = "AFTER_COMMIT"
    PARTIAL_EFFECT = "PARTIAL_EFFECT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class InterceptionHook(str, Enum):
    BEFORE_TOOL_CALL = "BEFORE_TOOL_CALL"
    AFTER_TOOL_CALL = "AFTER_TOOL_CALL"
    AROUND_TOOL_CALL = "AROUND_TOOL_CALL"
    APPLICATION_AWARE_HOOK = "APPLICATION_AWARE_HOOK"


class TimeoutDisconnectionMode(str, Enum):
    CALLER_TIMEOUT_EXCEEDED = "CALLER_TIMEOUT_EXCEEDED"
    SOCKET_DROP = "SOCKET_DROP"
    HANG_INDEFINITELY = "HANG_INDEFINITELY"
    CONNECTION_REFUSED = "CONNECTION_REFUSED"


class ToolUnavailabilityMode(str, Enum):
    CIRCUIT_BROKEN = "CIRCUIT_BROKEN"
    SERVICE_MAINTENANCE = "SERVICE_MAINTENANCE"
    DEPENDENCY_OFFLINE = "DEPENDENCY_OFFLINE"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"


class MalformedResponseMode(str, Enum):
    INVALID_JSON = "INVALID_JSON"
    TRUNCATED_JSON = "TRUNCATED_JSON"
    SCHEMA_VIOLATION = "SCHEMA_VIOLATION"
    UNEXPECTED_CONTENT_TYPE = "UNEXPECTED_CONTENT_TYPE"
    EMPTY_BODY = "EMPTY_BODY"


class ToolMutability(str, Enum):
    READ_ONLY = "READ_ONLY"
    SIDE_EFFECTING = "SIDE_EFFECTING"


class ReleaseRuleType(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    TIME_BOUNDED = "TIME_BOUNDED"
    ATTEMPT_BOUNDED = "ATTEMPT_BOUNDED"
    MANUAL_RESET = "MANUAL_RESET"


class TerminalOutcome(str, Enum):
    SUCCESS_CLEAN_RECOVERY = "SUCCESS_CLEAN_RECOVERY"
    SUCCESS_DEGRADED_FALLBACK = "SUCCESS_DEGRADED_FALLBACK"
    GRACEFUL_ABORT_USER_NOTIFIED = "GRACEFUL_ABORT_USER_NOTIFIED"
    FAIL_SAFE_STOP = "FAIL_SAFE_STOP"


class ValidationScope(str, Enum):
    STATIC_ONLY = "STATIC_ONLY"


class ValidationStatus(str, Enum):
    STATIC_VALID = "STATIC_VALID"
    TEST_NOT_READY = "TEST_NOT_READY"


# ---------------------------------------------------------------------------
# Discriminated Payloads
# ---------------------------------------------------------------------------


class BaseFaultPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TimeoutDisconnectionPayload(BaseFaultPayload):
    family: Literal[FaultFamily.TIMEOUT_DISCONNECTION] = (
        FaultFamily.TIMEOUT_DISCONNECTION
    )
    mode: TimeoutDisconnectionMode
    timing_ms: StrictInt | None = Field(default=None, ge=0, le=600_000)


class Transient5xxPayload(BaseFaultPayload):
    family: Literal[FaultFamily.TRANSIENT_5XX] = FaultFamily.TRANSIENT_5XX
    http_status: StrictInt = Field(ge=500, le=599)
    error_code: SafeStr | None = Field(default=None, max_length=64)
    error_message: SafeStr | None = Field(default=None, max_length=512)


class RateLimit429Payload(BaseFaultPayload):
    family: Literal[FaultFamily.RATE_LIMIT_429] = FaultFamily.RATE_LIMIT_429
    http_status: Literal[429] = 429
    retry_after_seconds: StrictInt | None = Field(default=None, ge=0, le=86_400)
    limit_scope: SafeStr | None = Field(default=None, max_length=64)


class ToolUnavailabilityPayload(BaseFaultPayload):
    family: Literal[FaultFamily.TOOL_UNAVAILABILITY] = FaultFamily.TOOL_UNAVAILABILITY
    mode: ToolUnavailabilityMode
    retryable: StrictBool = False
    release_seconds: StrictInt | None = Field(default=None, ge=0, le=86_400)


class MalformedResponsePayload(BaseFaultPayload):
    family: Literal[FaultFamily.MALFORMED_RESPONSE] = FaultFamily.MALFORMED_RESPONSE
    mode: MalformedResponseMode
    raw_fragment: SafeStr | None = Field(default=None, max_length=2048)


FaultPayload = Annotated[
    TimeoutDisconnectionPayload
    | Transient5xxPayload
    | RateLimit429Payload
    | ToolUnavailabilityPayload
    | MalformedResponsePayload,
    Field(discriminator="family"),
]


# ---------------------------------------------------------------------------
# Release Rules and Bounds
# ---------------------------------------------------------------------------


class ReleaseRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_type: ReleaseRuleType
    max_fault_count: StrictInt | None = Field(default=None, ge=1, le=100)
    release_after_ms: StrictInt | None = Field(default=None, ge=0, le=600_000)


class OccurrenceBounds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_occurrence: StrictInt = Field(ge=1, le=100)
    max_occurrence: StrictInt = Field(ge=1, le=100)

    @model_validator(mode="after")
    def verify_bounds(self) -> "OccurrenceBounds":
        if self.min_occurrence > self.max_occurrence:
            raise ValueError(
                f"min_occurrence ({self.min_occurrence}) cannot exceed max_occurrence ({self.max_occurrence})."
            )
        return self


# ---------------------------------------------------------------------------
# Candidate Fault Case
# ---------------------------------------------------------------------------


class CandidateFaultCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: SafeStr = Field(min_length=1, max_length=32)
    project_id: SafeStr = Field(min_length=1, max_length=128)
    case_id: SafeStr = Field(min_length=1, max_length=128)
    case_family_id: SafeStr = Field(min_length=1, max_length=128)
    domain: SafeStr = Field(min_length=1, max_length=64)

    task_id: SafeStr = Field(min_length=1, max_length=128)
    task_version: SafeStr = Field(min_length=1, max_length=32)
    tool_id: SafeStr = Field(min_length=1, max_length=128)
    tool_version: SafeStr = Field(min_length=1, max_length=32)
    fixture_id: SafeStr = Field(min_length=1, max_length=128)
    fixture_version: SafeStr = Field(min_length=1, max_length=32)
    adapter_id: SafeStr = Field(min_length=1, max_length=128)
    adapter_version: SafeStr = Field(min_length=1, max_length=32)
    recovery_contract_id: SafeStr = Field(min_length=1, max_length=128)
    recovery_contract_version: SafeStr = Field(min_length=1, max_length=32)

    occurrence: StrictInt = Field(ge=1, le=100)
    interception_hook: InterceptionHook
    fault_family: FaultFamily
    effect_phase: EffectPhase
    payload: FaultPayload
    release_rule: ReleaseRule

    required_assertions: list[SafeStr] = Field(min_length=1, max_length=50)
    required_observations: list[SafeStr] = Field(min_length=1, max_length=50)
    caller_timeout_ms: StrictInt | None = Field(default=None, ge=0, le=600_000)
    reproducibility_seed: StrictInt | None = Field(default=None, ge=0, le=2_147_483_647)

    @model_validator(mode="after")
    def verify_family_matches_payload(self) -> "CandidateFaultCase":
        if self.fault_family != self.payload.family:
            raise ValueError(
                f"Candidate fault_family '{self.fault_family.value}' does not match payload family '{self.payload.family.value}'."
            )
        return self


# ---------------------------------------------------------------------------
# Adapter Capability Manifest
# ---------------------------------------------------------------------------


class ToolCapabilityDeclaration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_id: SafeStr = Field(min_length=1, max_length=128)
    tool_version: SafeStr = Field(min_length=1, max_length=32)
    mutability: ToolMutability


class CapabilityCombination(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_id: SafeStr = Field(min_length=1, max_length=128)
    fault_family: FaultFamily
    effect_phase: EffectPhase
    interception_hook: InterceptionHook
    supported_occurrence_bounds: OccurrenceBounds
    allowed_release_rule_types: list[ReleaseRuleType] = Field(
        min_length=1, max_length=10
    )
    supported_payload_modes: list[SafeStr] = Field(min_length=1, max_length=20)
    required_observation_capabilities: list[SafeStr] = Field(
        default_factory=list, max_length=20
    )


class AdapterCapabilityManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adapter_id: SafeStr = Field(min_length=1, max_length=128)
    adapter_version: SafeStr = Field(min_length=1, max_length=32)
    schema_version: SafeStr = Field(min_length=1, max_length=32)
    tools: list[ToolCapabilityDeclaration] = Field(min_length=1, max_length=100)
    supported_combinations: list[CapabilityCombination] = Field(
        min_length=1, max_length=200
    )

    @model_validator(mode="after")
    def verify_no_duplicate_combinations(self) -> "AdapterCapabilityManifest":
        seen = set()
        for c in self.supported_combinations:
            key = (
                c.tool_id,
                c.fault_family,
                c.effect_phase,
                c.interception_hook,
            )
            if key in seen:
                raise ValueError(
                    f"Duplicate capability combination declaration in manifest for tool '{c.tool_id}', family '{c.fault_family.value}', phase '{c.effect_phase.value}', hook '{c.interception_hook.value}'."
                )
            seen.add(key)
        return self


# ---------------------------------------------------------------------------
# Task and Fixture Metadata
# ---------------------------------------------------------------------------


class TaskFixtureMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: SafeStr = Field(min_length=1, max_length=128)
    task_version: SafeStr = Field(min_length=1, max_length=32)
    fixture_id: SafeStr = Field(min_length=1, max_length=128)
    fixture_version: SafeStr = Field(min_length=1, max_length=32)
    domain: SafeStr = Field(min_length=1, max_length=64)

    associated_tool_ids: list[SafeStr] = Field(min_length=1, max_length=100)
    associated_recovery_contract_ids: list[SafeStr] = Field(
        min_length=1, max_length=100
    )

    declared_reset_support: StrictBool = False
    reset_method: SafeStr | None = Field(default=None, max_length=128)
    declared_observation_support: StrictBool = False
    supported_observations: list[SafeStr] = Field(default_factory=list, max_length=100)
    supports_committed_effect_observation: StrictBool = False
    supports_partial_effect_observation: StrictBool = False


# ---------------------------------------------------------------------------
# Recovery Contract
# ---------------------------------------------------------------------------


class RecoveryContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_id: SafeStr = Field(min_length=1, max_length=128)
    contract_version: SafeStr = Field(min_length=1, max_length=32)

    permitted_terminal_outcomes: list[TerminalOutcome] = Field(
        min_length=1, max_length=10
    )
    graceful_stopping_conditions: list[SafeStr] = Field(
        default_factory=list, max_length=20
    )

    initial_invocation_counts_as_attempt: StrictBool = True
    max_task_attempts: StrictInt = Field(ge=1, le=50)
    max_retries: StrictInt | None = Field(default=None, ge=0, le=50)
    max_tool_calls_budget: StrictInt = Field(ge=1, le=500)
    max_total_timeout_ms: StrictInt = Field(gt=0, le=3_600_000)

    required_state_assertions: list[SafeStr] = Field(min_length=1, max_length=50)

    allow_duplicate_side_effects: StrictBool = False
    allow_retry_on_unverified_commit: StrictBool = False
    require_truthful_completion_reporting: StrictBool = True

    future_finding_rules: list[SafeStr] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def verify_attempt_retry_consistency(self) -> "RecoveryContract":
        if self.max_retries is not None:
            if (
                self.initial_invocation_counts_as_attempt
                and self.max_task_attempts != 1 + self.max_retries
            ):
                raise ValueError(
                    f"Contradictory attempt/retry budget: max_task_attempts ({self.max_task_attempts}) must equal 1 + max_retries ({self.max_retries}) when initial invocation counts as attempt 1."
                )
            if (
                not self.initial_invocation_counts_as_attempt
                and self.max_task_attempts != self.max_retries
            ):
                raise ValueError(
                    f"Contradictory attempt/retry budget: max_task_attempts ({self.max_task_attempts}) must equal max_retries ({self.max_retries}) when initial invocation does not count as a task attempt."
                )
        return self


# ---------------------------------------------------------------------------
# Validation Request & Response
# ---------------------------------------------------------------------------


class FaultValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_case: CandidateFaultCase
    adapter_manifest: AdapterCapabilityManifest
    task_fixture_metadata: TaskFixtureMetadata
    recovery_contract: RecoveryContract


class ValidationReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: SafeStr
    message: SafeStr
    field_path: SafeStr | None = None


class FaultValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_scope: ValidationScope = ValidationScope.STATIC_ONLY
    validation_status: ValidationStatus
    runtime_verified: Literal[False] = False
    execution_ready: Literal[False] = False
    reasons: list[ValidationReason] = Field(default_factory=list)
    pending_checks: list[SafeStr] = Field(default_factory=list)
    recovery_verdict: None = None


# ---------------------------------------------------------------------------
# Fault Catalogue Models
# ---------------------------------------------------------------------------


class FaultFamilyCatalogItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family: FaultFamily
    name: SafeStr
    description: SafeStr
    supported_modes: list[SafeStr]
    effect_phases: list[EffectPhase]
    constraints_summary: SafeStr
    injection_implemented: StrictBool = False
    # Where the family is injected at run time and with which effect phases
    runtime_support: list[SafeStr] = Field(default_factory=list)
    note: SafeStr = ""


class FaultCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: SafeStr = "1.0.0"
    families: list[FaultFamilyCatalogItem]
    count: StrictInt = 5
    injection_active: StrictBool = False
    note: SafeStr = ""
