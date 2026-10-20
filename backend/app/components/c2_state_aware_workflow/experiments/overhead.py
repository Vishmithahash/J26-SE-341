"""Overhead measurement and profiling service for C2 state-aware workflow testing.

Measures:
1. Runner-only execution.
2. Execution with observation and evidence recording.
3. Evaluator-only processing over retained frozen evidence.

Calculates median, p95, sample count, and measurement scope.
Bypasses result caches and uses high-resolution monotonic timers.
"""

import math
import statistics
import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LatencyStats(BaseModel):
    """Percentile latency metrics for a specific execution scope."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scope_name: str
    sample_count: int
    warmup_count: int
    median_ms: float
    p95_ms: float
    min_ms: float
    max_ms: float
    mean_ms: float
    std_dev_ms: float
    raw_measurements_ms: list[float] = Field(default_factory=list)


class OverheadProfileReport(BaseModel):
    """Full overhead comparison report across runner, observation, and evaluator scopes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    runner_only: LatencyStats
    runner_with_observation: LatencyStats
    evaluator_only: LatencyStats
    observation_overhead_ms: float
    observation_overhead_ratio: float
    total_overhead_p95_ms: float
    measurement_notes: list[str] = Field(default_factory=list)


class OverheadProfiler:
    """Profiles runtime execution and evaluation latencies with statistical rigor."""

    @staticmethod
    def measure_callable(
        fn: Callable[[], Any],
        repetitions: int = 20,
        warmup_iterations: int = 3,
        scope_name: str = "operation",
    ) -> LatencyStats:
        """Measure execution latency of a callable over warmups and repetitions."""
        # Warmup phase to stabilize JIT/OS caches
        for _ in range(warmup_iterations):
            fn()

        measurements: list[float] = []
        for _ in range(repetitions):
            t0 = time.perf_counter_ns()
            fn()
            t1 = time.perf_counter_ns()
            elapsed_ms = (t1 - t0) / 1_000_000.0
            measurements.append(round(elapsed_ms, 3))

        if not measurements:
            return LatencyStats(
                scope_name=scope_name,
                sample_count=0,
                warmup_count=warmup_iterations,
                median_ms=0.0,
                p95_ms=0.0,
                min_ms=0.0,
                max_ms=0.0,
                mean_ms=0.0,
                std_dev_ms=0.0,
            )

        sorted_ms = sorted(measurements)
        n = len(sorted_ms)
        median_val = statistics.median(sorted_ms)

        # Calculate P95 with nearest rank
        p95_index = max(0, min(n - 1, math.ceil(0.95 * n) - 1))
        p95_val = sorted_ms[p95_index]

        mean_val = statistics.mean(sorted_ms)
        std_dev_val = statistics.stdev(sorted_ms) if n > 1 else 0.0

        return LatencyStats(
            scope_name=scope_name,
            sample_count=n,
            warmup_count=warmup_iterations,
            median_ms=round(median_val, 3),
            p95_ms=round(p95_val, 3),
            min_ms=sorted_ms[0],
            max_ms=sorted_ms[-1],
            mean_ms=round(mean_val, 3),
            std_dev_ms=round(std_dev_val, 3),
            raw_measurements_ms=measurements,
        )

    @classmethod
    def compute_profile(
        cls,
        runner_fn: Callable[[], Any],
        observed_runner_fn: Callable[[], Any],
        evaluator_fn: Callable[[], Any],
        repetitions: int = 20,
        warmup_iterations: int = 3,
    ) -> OverheadProfileReport:
        """Measure and compute complete overhead profile across all three scopes."""
        runner_stats = cls.measure_callable(
            runner_fn,
            repetitions=repetitions,
            warmup_iterations=warmup_iterations,
            scope_name="runner_only",
        )
        observed_stats = cls.measure_callable(
            observed_runner_fn,
            repetitions=repetitions,
            warmup_iterations=warmup_iterations,
            scope_name="runner_with_observation",
        )
        evaluator_stats = cls.measure_callable(
            evaluator_fn,
            repetitions=repetitions,
            warmup_iterations=warmup_iterations,
            scope_name="evaluator_only",
        )

        obs_overhead = round(observed_stats.median_ms - runner_stats.median_ms, 3)
        obs_ratio = (
            round(obs_overhead / runner_stats.median_ms, 4)
            if runner_stats.median_ms > 0
            else 0.0
        )
        total_p95 = round(observed_stats.p95_ms + evaluator_stats.p95_ms, 3)

        notes = [
            f"Scope runner_only: {runner_stats.sample_count} runs (median={runner_stats.median_ms}ms, p95={runner_stats.p95_ms}ms)",
            f"Scope runner_with_observation: {observed_stats.sample_count} runs (median={observed_stats.median_ms}ms, p95={observed_stats.p95_ms}ms)",
            f"Scope evaluator_only: {evaluator_stats.sample_count} runs (median={evaluator_stats.median_ms}ms, p95={evaluator_stats.p95_ms}ms)",
            "Result caches bypassed for evaluator execution.",
        ]

        return OverheadProfileReport(
            runner_only=runner_stats,
            runner_with_observation=observed_stats,
            evaluator_only=evaluator_stats,
            observation_overhead_ms=obs_overhead,
            observation_overhead_ratio=obs_ratio,
            total_overhead_p95_ms=total_p95,
            measurement_notes=notes,
        )
