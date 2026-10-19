"""Bounded frozen-suite execution runner and local CLI.

Component: C3 - Robustness and Failure Recovery Testing
Phase: Phase 3 - Automatic generation, frozen suites, remaining faults and supported post-commit experiments.
"""

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from app.components.c3_robustness_recovery.contracts.generation import (
    FaultGenerationRequest,
    FrozenSuite,
    GenerationPolicy,
)
from app.components.c3_robustness_recovery.contracts.schemas import (
    CandidateFaultCase,
    EffectPhase,
    FaultFamily,
    InterceptionHook,
    RecoveryContract,
    ReleaseRule,
    ReleaseRuleType,
    TaskFixtureMetadata,
    TimeoutDisconnectionMode,
    TimeoutDisconnectionPayload,
)
from app.components.c3_robustness_recovery.runtime.adapter import (
    CallerIdentity,
    CleanupStatus,
    DemonstrationFixtureManager,
    DemonstrationToolAdapter,
    DomainToolAdapter,
    FixtureManager,
    TargetMode,
)
from app.components.c3_robustness_recovery.runtime.evidence import (
    ExposureStatus,
    MatchedPairEvidence,
    ReadinessStatus,
)
from app.components.c3_robustness_recovery.runtime.runner import (
    HarnessRunner,
    check_runtime_readiness,
    make_demonstration_recovery_contract,
    make_demonstration_task_fixture_metadata,
)
from app.components.c3_robustness_recovery.services.generation import (
    generate_feasible_cases,
)
from app.components.c3_robustness_recovery.services.suites import (
    verify_suite_integrity,
)


@dataclass(frozen=True)
class SuiteCaseExecutionResult:
    """Execution outcome for a single case within a frozen suite."""

    case_id: str
    status: str  # "EXECUTED", "BLOCKED", "UNSUPPORTED", "CANCELLED", "ERROR"
    evidence: MatchedPairEvidence | None = None
    blocked_reasons: list[str] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass(frozen=True)
class SuiteExecutionSummary:
    """Bounded suite execution summary report."""

    suite_id: str
    suite_digest: str
    total_cases: int
    executed_count: int
    blocked_count: int
    unsupported_count: int
    cancelled_count: int
    error_count: int
    confirmed_exposure_count: int
    not_triggered_count: int
    unknown_exposure_count: int
    case_results: list[SuiteCaseExecutionResult]
    overall_duration_ms: float
    halted_early: bool
    halt_reason: str | None = None


class SuiteRunner:
    """Executes frozen suites under sequential bounded runtime constraints.

    Safeguards:
    - Verifies suite integrity and digest before any target activity.
    - Resolves only installed, configured adapters.
    - Evaluates explicit readiness per case.
    - Runs matched clean/fault pairs only when eligible.
    - Enforces fresh isolated fixtures between trials.
    - Halts dependent suite execution if cleanup uncertainty occurs.
    - Enforces per-case and overall suite time bounds.
    """

    def __init__(
        self,
        adapter: DomainToolAdapter,
        fixture_manager: FixtureManager,
        task_fixture_metadata: TaskFixtureMetadata,
        recovery_contract: RecoveryContract,
        target_mode: TargetMode = TargetMode.DEMONSTRATION,
        caller_identity: CallerIdentity = CallerIdentity.SCRIPTED_CALLER,
        max_suite_duration_sec: float = 60.0,
        per_case_timeout_sec: float = 10.0,
    ) -> None:
        self.adapter = adapter
        self.fixture_manager = fixture_manager
        self.task_fixture_metadata = task_fixture_metadata
        self.recovery_contract = recovery_contract
        self.target_mode = target_mode
        self.caller_identity = caller_identity
        self.max_suite_duration_sec = max_suite_duration_sec
        self.per_case_timeout_sec = per_case_timeout_sec
        self.harness_runner = HarnessRunner(
            adapter=adapter,
            fixture_manager=fixture_manager,
        )

    async def run_frozen_suite(self, suite: FrozenSuite) -> SuiteExecutionSummary:
        """Run all eligible cases in a verified frozen suite."""
        # 1. Verify suite integrity before any activity
        verify_suite_integrity(suite)

        suite_start_time = time.perf_counter()
        manifest = self.adapter.get_manifest()

        results: list[SuiteCaseExecutionResult] = []
        executed_count = 0
        blocked_count = 0
        unsupported_count = 0
        cancelled_count = 0
        error_count = 0
        confirmed_exposure = 0
        not_triggered_exposure = 0
        unknown_exposure = 0

        halted_early = False
        halt_reason: str | None = None

        for case in suite.selected_cases:
            # Check overall suite duration limit
            elapsed_suite_sec = time.perf_counter() - suite_start_time
            if elapsed_suite_sec >= self.max_suite_duration_sec:
                halted_early = True
                halt_reason = f"Suite exceeded maximum total duration of {self.max_suite_duration_sec}s."
                cancelled_count += 1
                results.append(
                    SuiteCaseExecutionResult(
                        case_id=case.case_id,
                        status="CANCELLED",
                        blocked_reasons=["Suite timeout exceeded before case start."],
                    )
                )
                continue

            case_start = time.perf_counter()

            # 2. Check runtime readiness
            readiness = check_runtime_readiness(
                candidate_case=case,
                adapter_manifest=manifest,
                task_fixture_metadata=self.task_fixture_metadata,
                recovery_contract=self.recovery_contract,
                adapter=self.adapter,
                fixture_manager=self.fixture_manager,
                target_mode=self.target_mode,
                caller_identity=self.caller_identity,
            )

            if readiness.status != ReadinessStatus.READY:
                status_label = (
                    "BLOCKED"
                    if readiness.status == ReadinessStatus.BLOCKED
                    else "UNSUPPORTED"
                )
                if status_label == "BLOCKED":
                    blocked_count += 1
                else:
                    unsupported_count += 1

                case_duration = (time.perf_counter() - case_start) * 1000.0
                results.append(
                    SuiteCaseExecutionResult(
                        case_id=case.case_id,
                        status=status_label,
                        blocked_reasons=readiness.reasons,
                        duration_ms=case_duration,
                    )
                )
                continue

            # 3. Execute matched pair
            try:
                pair_evidence = await asyncio.wait_for(
                    self.harness_runner.run_matched_pair(
                        candidate_case=case,
                        adapter_manifest=manifest,
                        task_fixture_metadata=self.task_fixture_metadata,
                        recovery_contract=self.recovery_contract,
                        target_mode=self.target_mode,
                        caller_identity=self.caller_identity,
                    ),
                    timeout=self.per_case_timeout_sec,
                )
                case_duration = (time.perf_counter() - case_start) * 1000.0
                executed_count += 1

                if pair_evidence.exposure_status == ExposureStatus.CONFIRMED:
                    confirmed_exposure += 1
                elif pair_evidence.exposure_status == ExposureStatus.NOT_TRIGGERED:
                    not_triggered_exposure += 1
                else:
                    unknown_exposure += 1

                results.append(
                    SuiteCaseExecutionResult(
                        case_id=case.case_id,
                        status="EXECUTED",
                        evidence=pair_evidence,
                        duration_ms=case_duration,
                    )
                )

                # 4. Check cleanup isolation safeguard
                if pair_evidence.cleanup_status == CleanupStatus.UNCERTAIN:
                    halted_early = True
                    halt_reason = (
                        f"Cleanup uncertainty in case '{case.case_id}' compromised fixture isolation. "
                        "Dependent execution stopped."
                    )
                    break

            except TimeoutError:
                case_duration = (time.perf_counter() - case_start) * 1000.0
                cancelled_count += 1
                results.append(
                    SuiteCaseExecutionResult(
                        case_id=case.case_id,
                        status="CANCELLED",
                        blocked_reasons=[
                            f"Per-case timeout of {self.per_case_timeout_sec}s exceeded."
                        ],
                        duration_ms=case_duration,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                case_duration = (time.perf_counter() - case_start) * 1000.0
                error_count += 1
                results.append(
                    SuiteCaseExecutionResult(
                        case_id=case.case_id,
                        status="ERROR",
                        blocked_reasons=[
                            f"Harness error during trial execution: {exc}"
                        ],
                        duration_ms=case_duration,
                    )
                )

        overall_duration = (time.perf_counter() - suite_start_time) * 1000.0

        return SuiteExecutionSummary(
            suite_id=suite.suite_id,
            suite_digest=suite.suite_digest,
            total_cases=len(suite.selected_cases),
            executed_count=executed_count,
            blocked_count=blocked_count,
            unsupported_count=unsupported_count,
            cancelled_count=cancelled_count,
            error_count=error_count,
            confirmed_exposure_count=confirmed_exposure,
            not_triggered_count=not_triggered_exposure,
            unknown_exposure_count=unknown_exposure,
            case_results=results,
            overall_duration_ms=overall_duration,
            halted_early=halted_early,
            halt_reason=halt_reason,
        )


def make_demonstration_after_commit_case() -> CandidateFaultCase:
    """Create a demonstration CandidateFaultCase for the application-aware AFTER_COMMIT scenario."""
    return CandidateFaultCase(
        schema_version="1.0.0",
        project_id="proj-demo-qa",
        case_id="case-c3-after-commit-001",
        case_family_id="fam-after-commit",
        domain="ecommerce",
        task_id="task-checkout-demo",
        task_version="1.0.0",
        tool_id="demonstration_order_placement",
        tool_version="1.0.0",
        fixture_id="fix-demonstration-cart",
        fixture_version="1.0.0",
        adapter_id="adapter-demonstration-c3",
        adapter_version="1.0.0",
        recovery_contract_id="rec-demo-01",
        recovery_contract_version="1.0.0",
        occurrence=1,
        interception_hook=InterceptionHook.APPLICATION_AWARE_HOOK,
        fault_family=FaultFamily.TIMEOUT_DISCONNECTION,
        effect_phase=EffectPhase.AFTER_COMMIT,
        payload=TimeoutDisconnectionPayload(
            mode=TimeoutDisconnectionMode.CALLER_TIMEOUT_EXCEEDED,
            timing_ms=50,
        ),
        release_rule=ReleaseRule(
            rule_type=ReleaseRuleType.ATTEMPT_BOUNDED,
            max_fault_count=1,
        ),
        required_assertions=["state_order_created"],
        required_observations=["committed_order_verified", "caller_timeout_observed"],
        caller_timeout_ms=20,
    )


def build_demonstration_generation_request() -> FaultGenerationRequest:
    """Build a default valid FaultGenerationRequest covering demonstration capabilities."""
    fixture_mgr = DemonstrationFixtureManager()
    adapter = DemonstrationToolAdapter(fixture_manager=fixture_mgr)
    manifest = adapter.get_manifest()
    metadata = make_demonstration_task_fixture_metadata()
    recovery = make_demonstration_recovery_contract()

    return FaultGenerationRequest(
        schema_version="1.0.0",
        project_id="proj-demo-qa",
        task_id="task-checkout-demo",
        task_version="1.0.0",
        tool_id="demonstration_order_placement",
        tool_version="1.0.0",
        domain="ecommerce",
        adapter_manifest=manifest,
        task_fixture_metadata=metadata,
        recovery_contract=recovery,
        policy=GenerationPolicy(
            max_cases=10,
            max_candidates_examined=100,
            selection_seed=42,
            content_seed=101,
        ),
    )


async def main_async(args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Component 3 Phase 3 Bounded Frozen-Suite Runner and CLI"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--synthetic",
        action="store_true",
        help="Run hermetic frozen suites using generic demonstration adapter.",
    )
    group.add_argument(
        "--live",
        action="store_true",
        help="Attempt execution against live target AUT (NexaCart).",
    )

    parser.add_argument(
        "--generate",
        action="store_true",
        help="Automatically generate and freeze a feasible suite before execution.",
    )
    parser.add_argument(
        "--suite-file",
        help="Path to an existing JSON frozen suite to verify and execute.",
    )
    parser.add_argument(
        "--after-commit",
        action="store_true",
        help="Execute the application-aware AFTER_COMMIT lost-response demonstration.",
    )
    parser.add_argument(
        "--export-dir",
        default="evidence_output",
        help="Directory to save exported JSON artifacts.",
    )

    parsed = parser.parse_args(args)

    fixture_mgr = DemonstrationFixtureManager()
    adapter = DemonstrationToolAdapter(fixture_manager=fixture_mgr)
    metadata = make_demonstration_task_fixture_metadata()
    recovery = make_demonstration_recovery_contract()

    target_mode = TargetMode.LIVE_AUT if parsed.live else TargetMode.DEMONSTRATION

    print(f"[C3 Phase 3 Suite Runner] Mode: {target_mode.value}")

    # 1. Obtain or load the frozen suite
    suite: FrozenSuite | None = None
    if parsed.suite_file:
        suite_path = Path(parsed.suite_file)
        if not suite_path.exists():
            print(
                f"Error: Suite file '{parsed.suite_file}' not found.", file=sys.stderr
            )
            return 1
        with open(suite_path, encoding="utf-8") as f:  # noqa: ASYNC230
            data = json.load(f)
        suite = FrozenSuite.model_validate(data)
        print(f"Loaded suite '{suite.suite_id}' (digest: {suite.suite_digest[:16]}...)")
    else:
        # Generate on the fly
        gen_req = build_demonstration_generation_request()
        gen_resp = generate_feasible_cases(gen_req)
        suite = gen_resp.frozen_suite
        if not suite or not suite.selected_cases:
            print("Generation produced no feasible cases for suite.", file=sys.stderr)
            return 2
        print(
            f"Generated frozen suite '{suite.suite_id}' with {len(suite.selected_cases)} cases "
            f"(digest: {suite.suite_digest[:16]}...)"
        )

    # If AFTER_COMMIT scenario requested explicitly and not present in selected cases, add demonstration case
    if parsed.after_commit:
        after_commit_case = make_demonstration_after_commit_case()
        has_ac = any(
            c.effect_phase == EffectPhase.AFTER_COMMIT for c in suite.selected_cases
        )
        if not has_ac:
            from app.components.c3_robustness_recovery.services.suites import (
                freeze_suite,
            )

            cases_with_ac = list(suite.selected_cases) + [after_commit_case]
            suite = freeze_suite(
                task_fixture_metadata=suite.task_fixture_metadata,
                adapter_manifest=suite.adapter_manifest,
                recovery_contract=suite.recovery_contract,
                policy=suite.policy,
                selected_cases=cases_with_ac,
                counters=suite.counters,
            )
            print("Appended application-aware AFTER_COMMIT case to suite.")

    suite_runner = SuiteRunner(
        adapter=adapter,
        fixture_manager=fixture_mgr,
        task_fixture_metadata=metadata,
        recovery_contract=recovery,
        target_mode=target_mode,
        caller_identity=CallerIdentity.SCRIPTED_CALLER,
    )

    try:
        summary = await suite_runner.run_frozen_suite(suite)

        print("\n================== SUITE EXECUTION SUMMARY ==================")
        print(f"Suite ID:              {summary.suite_id}")
        print(f"Suite Digest:          {summary.suite_digest}")
        print(f"Total Cases:           {summary.total_cases}")
        print(f"Executed:              {summary.executed_count}")
        print(f"Blocked:               {summary.blocked_count}")
        print(f"Unsupported:           {summary.unsupported_count}")
        print(f"Cancelled:             {summary.cancelled_count}")
        print(f"Errors:                {summary.error_count}")
        print(f"Confirmed Exposures:   {summary.confirmed_exposure_count}")
        print(f"Not Triggered:         {summary.not_triggered_count}")
        print(f"Unknown Exposure:      {summary.unknown_exposure_count}")
        print(f"Overall Duration:      {summary.overall_duration_ms:.1f}ms")
        if summary.halted_early:
            print(f"HALTED EARLY:          {summary.halt_reason}")
        print("-------------------------------------------------------------")

        for r in summary.case_results:
            exp_status = r.evidence.exposure_status.value if r.evidence else "N/A"
            print(
                f"[{r.status}] Case: {r.case_id} | Exposure: {exp_status} ({r.duration_ms:.1f}ms)"
            )
            if r.blocked_reasons:
                for b in r.blocked_reasons:
                    print(f"    - {b}")

        # Save summary artifact to export directory
        export_dir = Path(parsed.export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)
        filename = f"suite_run_{summary.suite_id}_{uuid4().hex[:6]}.json"
        out_path = export_dir / filename

        artifact_data = {
            "suite_id": summary.suite_id,
            "suite_digest": summary.suite_digest,
            "total_cases": summary.total_cases,
            "executed_count": summary.executed_count,
            "blocked_count": summary.blocked_count,
            "unsupported_count": summary.unsupported_count,
            "cancelled_count": summary.cancelled_count,
            "error_count": summary.error_count,
            "confirmed_exposure_count": summary.confirmed_exposure_count,
            "not_triggered_count": summary.not_triggered_count,
            "unknown_exposure_count": summary.unknown_exposure_count,
            "overall_duration_ms": summary.overall_duration_ms,
            "halted_early": summary.halted_early,
            "halt_reason": summary.halt_reason,
            "recovery_verdict": None,
        }
        with open(out_path, "w", encoding="utf-8") as f:  # noqa: ASYNC230
            json.dump(artifact_data, f, indent=2)
        print(f"\nExported suite summary to: {out_path}")

        # If live execution was blocked, return exit code 2
        if parsed.live and summary.executed_count == 0 and summary.blocked_count > 0:
            return 2

        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[C3 Phase 3 Suite Runner] ERROR: {exc}", file=sys.stderr)
        return 1


def main() -> None:
    code = asyncio.run(main_async(sys.argv[1:]))
    sys.exit(code)


if __name__ == "__main__":
    main()
