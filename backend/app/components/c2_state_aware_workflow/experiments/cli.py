"""Offline reproducible CLI command for C2 baseline comparisons, overhead profiling, and research evaluation.

Runs the complete 125-case multi-domain benchmark without requiring external network or paid credentials.
Usage:
    python -m app.components.c2_state_aware_workflow.experiments.cli [--output-dir DIR]
"""

import argparse
import json
import sys
from pathlib import Path

from app.components.c2_state_aware_workflow.baselines.contracts import BaselineType
from app.components.c2_state_aware_workflow.evaluator.fixtures import (
    ScriptedDemonstrationAgent,
)
from app.components.c2_state_aware_workflow.evaluator.observer import (
    IndependentStateObserver,
)
from app.components.c2_state_aware_workflow.evaluator.sut import SyntheticRefundSUT
from app.components.c2_state_aware_workflow.examples.refund_workflow import (
    build_synthetic_refund_efsm,
)
from app.components.c2_state_aware_workflow.experiments.benchmark import (
    BenchmarkSuiteBuilder,
)
from app.components.c2_state_aware_workflow.experiments.overhead import (
    OverheadProfiler,
)
from app.components.c2_state_aware_workflow.experiments.runner import (
    ExperimentRunner,
)


def run_benchmark_pipeline(output_dir: str | None = None) -> int:
    """Execute complete benchmark pipeline, baseline evaluation, overhead profiling, and report generation."""
    print("=" * 80)
    print(" C2: STATE-AWARE MULTI-STEP WORKFLOW TESTING — RESEARCH BENCHMARK PIPELINE")
    print("=" * 80)

    # 1. Build Multi-Domain Benchmark Suite (>=100 cases)
    print("\n[Step 1/4] Constructing versioned multi-domain benchmark suite...")
    builder = BenchmarkSuiteBuilder(project_id="c2_domain_portability_project")
    manifest, models, tests = builder.build_benchmark_manifest(
        dataset_id="c2_benchmark_v1",
        name="C2 Multi-Domain Portability & Robustness Benchmark",
        version="1.0.0",
    )
    print(f"  ✓ Total distinct cases: {manifest.case_count}")
    print(f"  ✓ Development partition: {manifest.development_count} cases")
    print(f"  ✓ Held-out partition:    {manifest.held_out_count} cases")
    print(f"  ✓ Workflows evaluated:   {len(models)} ({', '.join(models.keys())})")
    print(f"  ✓ Manifest digest:       {manifest.manifest_digest[:16]}...")
    print(f"  ✓ Manifest frozen:       {manifest.is_frozen}")

    # 2. Run Baselines B1–B4 over Frozen Retained Evidence
    print("\n[Step 2/4] Executing comparative evaluation across B1, B2, B3, and B4...")
    runner = ExperimentRunner()
    report, case_results = runner.run_experiment(
        experiment_id="exp_c2_benchmark_2026",
        experiment_name="C2 Multi-Domain Comparative Benchmark",
        manifest=manifest,
        models_by_id=models,
        tests_by_id=tests,
        eval_methods=[
            BaselineType.B1_FINAL_STATE_ONLY,
            BaselineType.B2_TRACE_ONLY,
            BaselineType.B3_MILESTONE_BASED,
            BaselineType.B4_FULL_C2,
        ],
    )
    print(f"  ✓ Total evaluations completed: {len(case_results)}")
    print(
        f"  ✓ Generated test validity rate: {report.generated_test_validity_rate * 100:.1f}%"
    )

    # 3. Measure Execution and Evaluation Overhead
    print(
        "\n[Step 3/4] Profiling runtime overhead across runner, observation, and evaluator scopes..."
    )
    refund_model = build_synthetic_refund_efsm()
    sut = SyntheticRefundSUT()
    observer = IndependentStateObserver(sut)
    agent = ScriptedDemonstrationAgent(sut, observer)
    sample_evidence = manifest.cases[0].frozen_evidence

    def runner_only():
        sut.reset()
        sut.get_customer_orders(customer_id=42)
        sut.select_order(customer_id=42, order_id=503)
        ref = sut.request_refund(
            customer_id=42, order_id=503, reason="Latest order refund"
        )
        ref_id = ref.get("refund_id") if isinstance(ref, dict) else "ref_001"
        sut.verify_refund_status(refund_id=ref_id)

    def observed_runner():
        sut.reset()
        agent.run_happy_path(
            project_id="c2_domain_portability_project",
            test_id="test_perf",
            run_id="run_perf",
            model_id="order_refund_workflow",
            model_version="1.0.0",
        )

    def evaluator_only():
        runner.baseline_service.b4.engine.evaluate(
            model=refund_model,
            test_def=tests[next(iter(tests.keys()))],
            evidence=sample_evidence,
        )

    overhead_report = OverheadProfiler.compute_profile(
        runner_fn=runner_only,
        observed_runner_fn=observed_runner,
        evaluator_fn=evaluator_only,
        repetitions=25,
        warmup_iterations=3,
    )
    print(
        f"  ✓ Runner-only latency:        median={overhead_report.runner_only.median_ms}ms, p95={overhead_report.runner_only.p95_ms}ms"
    )
    print(
        f"  ✓ Runner+Observation latency: median={overhead_report.runner_with_observation.median_ms}ms, p95={overhead_report.runner_with_observation.p95_ms}ms"
    )
    print(
        f"  ✓ Evaluator-only latency:     median={overhead_report.evaluator_only.median_ms}ms, p95={overhead_report.evaluator_only.p95_ms}ms"
    )
    print(
        f"  ✓ Observation overhead delta: {overhead_report.observation_overhead_ms}ms ({overhead_report.observation_overhead_ratio * 100:.2f}%)"
    )

    # 4. Print Metrics Comparison Table
    print(
        "\n[Step 4/4] Research Metrics Comparison Table (Workflow Violations = Positive Class):"
    )
    print("-" * 100)
    print(
        f"{'Method':<25} | {'Prec':<6} | {'Recall':<6} | {'F1':<6} | {'Loc Acc':<8} | {'Mutation':<8} | {'State Flts':<10} | {'Med (ms)':<8}"
    )
    print("-" * 100)
    for m_id, m_metrics in report.metrics_by_method.items():
        det = m_metrics.detection_metrics
        loc = m_metrics.localization_metrics
        p_str = f"{det.precision:.4f}" if det.precision is not None else "N/A"
        r_str = f"{det.recall:.4f}" if det.recall is not None else "N/A"
        f1_str = f"{det.f1_score:.4f}" if det.f1_score is not None else "N/A"
        loc_str = f"{loc.accuracy:.4f}" if loc.accuracy is not None else "N/A"
        mut_str = (
            f"{det.mutation_detection_score:.4f}"
            if det.mutation_detection_score is not None
            else "N/A"
        )
        eff_str = (
            f"{det.state_effect_fault_detection_score:.4f}"
            if det.state_effect_fault_detection_score is not None
            else "N/A"
        )
        med_str = f"{m_metrics.overhead_median_ms:.2f}"
        print(
            f"{m_id:<25} | {p_str:<6} | {r_str:<6} | {f1_str:<6} | {loc_str:<8} | {mut_str:<8} | {eff_str:<10} | {med_str:<8}"
        )
    print("-" * 100)

    # Acceptance Targets Evaluation
    print("\nAcceptance Targets Verification:")
    for target_key, passed in report.acceptance_criteria_results.items():
        mark = "✓ PASS" if passed else "✗ FAIL"
        print(f"  [{mark}] {target_key}")

    # Export Files
    out_path = Path(output_dir or "backend_c2_benchmark_results")
    out_path.mkdir(parents=True, exist_ok=True)

    manifest_file = out_path / "c2_benchmark_manifest.json"
    report_file = out_path / "c2_benchmark_report.json"
    csv_file = out_path / "c2_benchmark_metrics.csv"

    manifest_file.write_text(json.dumps(manifest.model_dump(mode="json"), indent=2))
    report_file.write_text(json.dumps(report.model_dump(mode="json"), indent=2))

    # CSV summary
    lines = [
        "method_id,precision,recall,f1_score,localization_accuracy,mutation_detection,state_fault_detection,overhead_median_ms,overhead_p95_ms"
    ]
    for m_id, m_metrics in report.metrics_by_method.items():
        det = m_metrics.detection_metrics
        loc = m_metrics.localization_metrics
        lines.append(
            f"{m_id},{det.precision},{det.recall},{det.f1_score},{loc.accuracy},"
            f"{det.mutation_detection_score},{det.state_effect_fault_detection_score},"
            f"{m_metrics.overhead_median_ms},{m_metrics.overhead_p95_ms}"
        )
    csv_file.write_text("\n".join(lines))

    print("\nSaved benchmark artifacts:")
    print(f"  - Manifest: {manifest_file.resolve()}")
    print(f"  - Report:   {report_file.resolve()}")
    print(f"  - CSV:      {csv_file.resolve()}")
    print("\nPipeline execution completed successfully.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Run C2 comparative research benchmark pipeline offline."
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to save reviewable JSON and CSV artifacts",
    )
    args = parser.parse_args()
    sys.exit(run_benchmark_pipeline(args.output_dir))


if __name__ == "__main__":
    main()
