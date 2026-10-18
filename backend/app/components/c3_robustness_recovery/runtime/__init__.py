"""Runtime package for Component 3 - Robustness and Failure Recovery Testing.

Phase 2: One-tool integration, matched trials, verified timeout exposure and safeguards.
"""

from app.components.c3_robustness_recovery.runtime.adapter import (
    CallerIdentity,
    CleanupResult,
    CleanupStatus,
    DemonstrationFixtureManager,
    DemonstrationToolAdapter,
    DomainToolAdapter,
    FixtureManager,
    RecoveryActor,
    TargetMode,
    ToolExecutionResult,
)
from app.components.c3_robustness_recovery.runtime.evidence import (
    CleanQualification,
    ExecutionStatus,
    ExposureStatus,
    FaultEpisodeRecord,
    FixtureComparability,
    ForwardingDecision,
    MatchedPairEvidence,
    ReadinessStatus,
    RuntimeEvent,
    TimeoutBoundaryType,
    TrialEvidence,
    TrialRole,
    export_evidence_to_file,
    validate_evidence_linkage,
)
from app.components.c3_robustness_recovery.runtime.interceptor import (
    DomainToolInterceptor,
    InterceptionPlan,
)

__all__ = [
    "CallerIdentity",
    "CleanQualification",
    "CleanupResult",
    "CleanupStatus",
    "DemonstrationFixtureManager",
    "DemonstrationToolAdapter",
    "DomainToolAdapter",
    "DomainToolInterceptor",
    "ExecutionStatus",
    "ExposureStatus",
    "FaultEpisodeRecord",
    "FixtureComparability",
    "FixtureManager",
    "ForwardingDecision",
    "InterceptionPlan",
    "MatchedPairEvidence",
    "ReadinessStatus",
    "RecoveryActor",
    "RuntimeEvent",
    "TargetMode",
    "TimeoutBoundaryType",
    "ToolExecutionResult",
    "TrialEvidence",
    "TrialRole",
    "export_evidence_to_file",
    "validate_evidence_linkage",
]
