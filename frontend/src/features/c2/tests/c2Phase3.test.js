import '../../../tests/setup.js';
import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { c2Api } from '../api/c2Api.js';
import { C2_VERDICTS, VERDICT_CONFIG, PROVENANCE_CONFIG, COVERAGE_STATUS } from '../constants/resultsConfig.js';

describe('Component 2 Phase 3: Workflow Results, Evidence, Coverage, Reports & Research Baselines', () => {
  let capturedRequests = [];

  beforeEach(() => {
    capturedRequests = [];
    globalThis.fetch = async (url, options = {}) => {
      capturedRequests.push({ url, options });

      // Mock C2 Phase 3 evaluation list
      if (
        url.includes('/evaluations') &&
        !url.includes('report') &&
        !url.includes('coverage') &&
        !url.includes('re-evaluate') &&
        !url.includes('verify-reproduction')
      ) {
        return {
          ok: true,
          status: 200,
          json: async () => ([
            {
              id: 1,
              evaluation_id: 'eval_pass_001',
              project_id: 'proj_alpha',
              suite_id: 'suite_gen_100',
              test_id: 'case_valid_01',
              run_id: 'run_live_01',
              model_id: 'c2_refund_efsm_nexacart',
              model_version: '1.0.0',
              verdict: 'PASS',
              actual_execution_origin: 'live_agent_run',
              conformance_score: 1.0,
              reasons: ['Execution strictly conformed to model transitions and postconditions.'],
              readiness_limitations: [],
              created_at: '2026-10-21T14:00:00Z',
            },
            {
              id: 2,
              evaluation_id: 'eval_exp_rej_002',
              project_id: 'proj_alpha',
              suite_id: 'suite_gen_100',
              test_id: 'case_neg_02',
              run_id: 'run_demo_02',
              model_id: 'c2_refund_efsm_nexacart',
              model_version: '1.0.0',
              verdict: 'EXPECTED REJECTION PASS',
              actual_execution_origin: 'scripted_synthetic_demonstration',
              conformance_score: 1.0,
              reasons: ['Agent correctly rejected invalid refund transition without reaching bad state.'],
              readiness_limitations: ['Synthetic scripted trace; not live multi-agent execution.'],
              created_at: '2026-10-21T14:05:00Z',
            },
            {
              id: 3,
              evaluation_id: 'eval_fail_003',
              project_id: 'proj_alpha',
              suite_id: 'suite_gen_100',
              test_id: 'case_mut_03',
              run_id: 'run_fixture_03',
              model_id: 'c2_refund_efsm_nexacart',
              model_version: '1.0.0',
              verdict: 'FAIL',
              actual_execution_origin: 'controlled_trace_fixture',
              conformance_score: 0.0,
              reasons: ['Divergence proven: event DISPATCH attempted before PAYMENT_CONFIRMED.'],
              readiness_limitations: [],
              first_proven_divergence: {
                event_index: 3,
                event_id: 'evt_dispatch_003',
                state_at_divergence: 'AWAITING_PAYMENT',
                attempted_event: 'DISPATCH',
                violated_rule: 'Guard [payment_status == "PAID"] evaluated to FALSE.',
                expected_alternatives: ['CONFIRM_PAYMENT', 'CANCEL_ORDER'],
                evidence_excerpt: 'Order dispatched while payment_status remained UNPAID in DB trace.',
              },
              created_at: '2026-10-21T14:10:00Z',
            },
            {
              id: 4,
              evaluation_id: 'eval_inconclusive_004',
              project_id: 'proj_alpha',
              suite_id: 'suite_gen_100',
              test_id: 'case_timeout_04',
              run_id: 'run_live_04',
              model_id: 'c2_refund_efsm_nexacart',
              model_version: '1.0.0',
              verdict: 'INCONCLUSIVE',
              actual_execution_origin: 'live_agent_run',
              conformance_score: 0.5,
              reasons: ['Execution trace terminated prematurely; intermediate state unknown.'],
              readiness_limitations: ['Trace truncated at step 4 of 8.'],
              divergence_localisation_uncertainty: 'Final outcome only. Incomplete agent trace prevents proving exact divergence location.',
              created_at: '2026-10-21T14:15:00Z',
            },
            {
              id: 5,
              evaluation_id: 'eval_model_not_ready_005',
              project_id: 'proj_alpha',
              suite_id: 'suite_gen_100',
              test_id: 'case_unready_05',
              run_id: 'run_fixture_05',
              model_id: 'c2_refund_efsm_draft',
              model_version: '0.1.0-draft',
              verdict: 'MODEL NOT READY',
              actual_execution_origin: 'controlled_trace_fixture',
              conformance_score: 0.0,
              reasons: ['Reference model is in DRAFT status and has not passed validation.'],
              readiness_limitations: ['Requires validation and explicit approval prior to evaluation.'],
              created_at: '2026-10-21T14:20:00Z',
            },
            {
              id: 6,
              evaluation_id: 'eval_test_not_ready_006',
              project_id: 'proj_alpha',
              suite_id: 'suite_gen_100',
              test_id: 'case_missing_schema_06',
              run_id: 'run_fixture_06',
              model_id: 'c2_refund_efsm_nexacart',
              model_version: '1.0.0',
              verdict: 'TEST NOT READY',
              actual_execution_origin: 'controlled_trace_fixture',
              conformance_score: 0.0,
              reasons: ['Test case contains invalid predicate syntax in assertions.'],
              readiness_limitations: ['Case flagged NOT READY during test generation.'],
              created_at: '2026-10-21T14:25:00Z',
            },
          ]),
        };
      }

      // Mock C2 evaluation coverage
      if (url.includes('/coverage')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            evaluation_id: 'eval_fail_003',
            project_id: 'proj_alpha',
            model_id: 'c2_refund_efsm_nexacart',
            model_version: '1.0.0',
            metrics: {
              transition_coverage: {
                numerator: 8,
                denominator: 10,
                ratio: 0.8,
                covered: ['t_lookup', 't_verify', 't_cancel', 't_refund_standard'],
                uncovered: ['t_refund_override', 't_manager_escalate'],
                unknown_or_ambiguous: [],
              },
              guard_outcome_coverage: {
                numerator: 12,
                denominator: 16,
                ratio: 0.75,
                true_outcomes_observed: 8,
                false_outcomes_observed: 4,
                unknown_outcomes_observed: 4,
                covered: ['guard_item_eligible:TRUE', 'guard_item_eligible:FALSE'],
                uncovered: ['guard_manager_approved:TRUE'],
              },
              selected_path_coverage: {
                numerator: 1,
                denominator: 1,
                ratio: 1.0,
                covered: ['path_standard_refund'],
                uncovered: [],
              },
              state_effect_coverage: {
                numerator: 0,
                denominator: 0,
                ratio: null,
                status: 'NOT_APPLICABLE',
                covered: [],
                uncovered: [],
                disclaimer: 'Zero target obligations identified for this evaluation slice.',
              },
            },
            composite_coverage_status: 'UNAVAILABLE_PREFER_SEPARATE_METRICS',
            composite_coverage_rationale: 'Composite coverage averaging masks critical unexercised guards. Metric separation preferred.',
            defect_detection_disclaimer: 'State-effect coverage measures state variable assertion checks; it is not equivalent to defect-detection accuracy without a labelled faulty dataset.',
          }),
        };
      }

      // Mock C2 report contribution
      if (url.includes('/report') && !url.includes('/export-report')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            report_schema_version: '2026.1',
            evaluation_id: 'eval_fail_003',
            project_id: 'proj_alpha',
            suite_id: 'suite_gen_100',
            test_id: 'case_mut_03',
            run_id: 'run_fixture_03',
            model_id: 'c2_refund_efsm_nexacart',
            model_version: '1.0.0',
            model_content_hash: 'sha256_mock_hash_efsm',
            evaluator_version: 'c2_evaluator_v1.2',
            fixture_version: 'c2_fixture_v1.0',
            actual_execution_origin: 'controlled_trace_fixture',
            verdict: 'FAIL',
            conformance_score: 0.0,
            reasons: ['Divergence proven: event DISPATCH attempted before PAYMENT_CONFIRMED.'],
            first_proven_divergence: {
              event_index: 3,
              event_id: 'evt_dispatch_003',
              state_at_divergence: 'AWAITING_PAYMENT',
              attempted_event: 'DISPATCH',
              violated_rule: 'Guard [payment_status == "PAID"] evaluated to FALSE.',
              expected_alternatives: ['CONFIRM_PAYMENT', 'CANCEL_ORDER'],
              evidence_excerpt: 'Order dispatched while payment_status remained UNPAID.',
            },
            readiness_limitations: [],
            evidence_summary: {
              total_events: 5,
              total_state_snapshots: 6,
              entity_continuity_verified: true,
              divergence_proven: true,
            },
            published_to_shared_aggregator: false,
            publishing_status: 'STUB_PENDING_SHARED_AGGREGATOR',
            content_digest_sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
            created_at: '2026-10-21T14:10:00Z',
          }),
        };
      }

      // Mock C2 export-report
      if (url.includes('/export-report')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            exported: true,
            evaluation_id: 'eval_fail_003',
            format: 'json',
            download_payload: {
              contract: 'C2ReportContributionContract',
              content_digest_sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
              published_to_shared_aggregator: false,
              publishing_status: 'STUB_PENDING_SHARED_AGGREGATOR',
            },
          }),
        };
      }

      // Mock C2 replay reproduction and re-evaluation
      if (url.includes('/re-evaluate') || url.includes('/verify-reproduction') || url.includes('/replay')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            evaluation_id: 'eval_fail_003',
            reproduction_mode: 'deterministic_retained_evidence_replay',
            executed_agent: false,
            agent_execution_disclaimer: 'Replay uses retained execution evidence fixtures. It does NOT invoke or interact with the live application agent.',
            original_verdict: 'FAIL',
            reproduced_verdict: 'FAIL',
            is_identical: true,
            divergence_reproduced: true,
            verified_at: '2026-10-21T14:30:00Z',
          }),
        };
      }

      // Mock C2 Research Datasets
      if (url.includes('/datasets') && !url.includes('/freeze')) {
        return {
          ok: true,
          status: 200,
          json: async () => ([
            {
              dataset_id: 'c2_nexacart_benchmark_v1',
              version: '1.0.0',
              status: 'FROZEN',
              name: 'NexaCart E-Commerce Multi-Step Benchmark',
              description: 'Standard benchmark dataset covering happy path, cancellations, refunds, and mutated agent traces.',
              independent_review_label: 'Peer-Reviewed Synthetic & Controlled Fixture Dataset',
              total_cases: 50,
              partitions: {
                DEVELOPMENT: { case_count: 35, frozen: true },
                HELD_OUT: { case_count: 15, frozen: true },
              },
              created_at: '2026-10-21T10:00:00Z',
            },
          ]),
        };
      }

      // Mock C2 Research Experiments (B1-B4 Baselines)
      if (url.includes('/experiments')) {
        return {
          ok: true,
          status: 200,
          json: async () => ([
            {
              experiment_id: 'exp_b1_b4_comparison',
              dataset_id: 'c2_nexacart_benchmark_v1',
              dataset_version: '1.0.0',
              dataset_partition: 'HELD_OUT',
              status: 'COMPLETED',
              sample_size: 15,
              cli_entrypoint: 'python -m app.components.c2_state_aware_workflow.experiments.cli',
              baselines: {
                B1: {
                  name: 'B1: Stateless Single-Turn Evaluation',
                  description: 'Evaluates each action independently without workflow state or history.',
                  precision: 0.62,
                  recall: 0.45,
                  f1_score: 0.52,
                  first_divergence_localization: 0.0,
                  state_effect_fault_detection: 0.20,
                  overhead_median_ms: 45,
                  overhead_p95_ms: 110,
                  notes: 'Cannot localize divergence; ignores multi-step state history.',
                },
                B2: {
                  name: 'B2: Standard ReAct Tracing',
                  description: 'Text log matching across sequential Thought/Action/Observation cycles.',
                  precision: 0.74,
                  recall: 0.68,
                  f1_score: 0.71,
                  first_divergence_localization: 0.35,
                  state_effect_fault_detection: 0.50,
                  overhead_median_ms: 180,
                  overhead_p95_ms: 420,
                  notes: 'Subject to false positives on benign paraphrasing and valid alternative paths.',
                },
                B3: {
                  name: 'B3: Unconstrained Multi-Step Agent',
                  description: 'LLM judge inspecting overall session trajectory without strict EFSM constraints.',
                  precision: 0.81,
                  recall: 0.75,
                  f1_score: 0.78,
                  first_divergence_localization: 0.58,
                  state_effect_fault_detection: 0.65,
                  overhead_median_ms: 1250,
                  overhead_p95_ms: 3100,
                  notes: 'High LLM execution overhead; non-deterministic evaluation outcomes.',
                },
                B4: {
                  name: 'B4: C2 State-Aware EFSM Conformance (Ours)',
                  description: 'Formal EFSM transitions, state variable assertions, and first proven divergence localization.',
                  precision: 0.96,
                  recall: 0.94,
                  f1_score: 0.95,
                  first_divergence_localization: 0.92,
                  state_effect_fault_detection: 0.93,
                  overhead_median_ms: 85,
                  overhead_p95_ms: 210,
                  notes: 'Provably localizes first divergence; strictly validates state mutations without LLM judge overhead.',
                },
              },
              created_at: '2026-10-21T15:00:00Z',
            },
          ]),
        };
      }

      return {
        ok: true,
        status: 200,
        json: async () => ({}),
      };
    };
  });

  it('Verifies all six C2 runtime verdicts are explicitly configured and distinct', () => {
    const requiredVerdicts = [
      'PASS',
      'EXPECTED REJECTION PASS',
      'FAIL',
      'INCONCLUSIVE',
      'MODEL NOT READY',
      'TEST NOT READY',
    ];

    assert.equal(C2_VERDICTS.length, 6);
    for (const verdict of requiredVerdicts) {
      assert.ok(VERDICT_CONFIG[verdict], `VERDICT_CONFIG must configure "${verdict}"`);
      assert.ok(VERDICT_CONFIG[verdict].label, `Verdict "${verdict}" must have a readable text label`);
      assert.ok(VERDICT_CONFIG[verdict].badge, `Verdict "${verdict}" must have distinct CSS styling`);
    }

    // Verify EXPECTED REJECTION PASS is not collapsed into simple PASS
    assert.notEqual(
      VERDICT_CONFIG['EXPECTED REJECTION PASS'].label,
      VERDICT_CONFIG['PASS'].label,
      'EXPECTED REJECTION PASS must have distinct text alongside color'
    );

    // Verify MODEL NOT READY and TEST NOT READY are distinct readiness limiters
    assert.notEqual(
      VERDICT_CONFIG['MODEL NOT READY'].label,
      VERDICT_CONFIG['TEST NOT READY'].label,
      'MODEL NOT READY and TEST NOT READY must be distinctly identifiable'
    );
  });

  it('Verifies execution provenance distinctions (live_agent_run, scripted_synthetic_demonstration, controlled_trace_fixture)', () => {
    const requiredProvenances = [
      'live_agent_run',
      'scripted_synthetic_demonstration',
      'controlled_trace_fixture',
    ];

    for (const prov of requiredProvenances) {
      assert.ok(PROVENANCE_CONFIG[prov], `PROVENANCE_CONFIG must configure "${prov}"`);
      assert.ok(PROVENANCE_CONFIG[prov].label, `Provenance "${prov}" must have a descriptive label`);
    }

    assert.equal(PROVENANCE_CONFIG['live_agent_run'].isLive, true);
    assert.equal(PROVENANCE_CONFIG['scripted_synthetic_demonstration'].isLive, false);
    assert.equal(PROVENANCE_CONFIG['controlled_trace_fixture'].isLive, false);
  });

  it('Loads evaluations with filter parameters and preserves actual provenance and readiness reasons', async () => {
    const evaluations = await c2Api.listEvaluations('proj_alpha', {
      suite_id: 'suite_gen_100',
      verdict: 'FAIL',
      origin: 'controlled_trace_fixture',
    });

    assert.equal(evaluations.length, 6);
    assert.equal(capturedRequests.length, 1);
    const req = capturedRequests[0];
    assert.ok(req.url.includes('/projects/proj_alpha/evaluations'));
    assert.ok(req.url.includes('suite_id=suite_gen_100'));
    assert.ok(req.url.includes('verdict=FAIL'));
    assert.ok(req.url.includes('origin=controlled_trace_fixture'));

    // Check that demonstration evaluation preserves synthetic limitation
    const demoEval = evaluations.find((e) => e.verdict === 'EXPECTED REJECTION PASS');
    assert.equal(demoEval.actual_execution_origin, 'scripted_synthetic_demonstration');
    assert.ok(demoEval.readiness_limitations.some((lim) => lim.includes('Synthetic')));

    // Check that model unready preserves distinct reason
    const unreadyModelEval = evaluations.find((e) => e.verdict === 'MODEL NOT READY');
    assert.ok(unreadyModelEval.reasons[0].includes('DRAFT status'));
  });

  it('Fetches evaluation details and verifies first-proven divergence metadata without fabrication', async () => {
    // Evaluation 3 has a proven divergence
    const evaluations = await c2Api.listEvaluations('proj_alpha');
    const failEval = evaluations.find((e) => e.evaluation_id === 'eval_fail_003');

    assert.ok(failEval.first_proven_divergence, 'First proven divergence must be present');
    assert.equal(failEval.first_proven_divergence.event_index, 3);
    assert.equal(failEval.first_proven_divergence.state_at_divergence, 'AWAITING_PAYMENT');
    assert.equal(failEval.first_proven_divergence.attempted_event, 'DISPATCH');
    assert.ok(failEval.first_proven_divergence.expected_alternatives.includes('CONFIRM_PAYMENT'));
    assert.ok(failEval.first_proven_divergence.evidence_excerpt.includes('payment_status remained UNPAID'));

    // Evaluation 4 has NO proven divergence but backend uncertainty explanation
    const inconclusiveEval = evaluations.find((e) => e.evaluation_id === 'eval_inconclusive_004');
    assert.equal(inconclusiveEval.first_proven_divergence, undefined);
    assert.ok(
      inconclusiveEval.divergence_localisation_uncertainty.includes('Incomplete agent trace'),
      'Backend uncertainty explanation must be displayed truthfully rather than inventing an earlier failure step'
    );
  });

  it('Fetches observed coverage and enforces separate metrics and zero-denominator handling', async () => {
    const coverage = await c2Api.getEvaluationCoverage('proj_alpha', 'eval_fail_003');

    assert.equal(coverage.evaluation_id, 'eval_fail_003');
    assert.ok(coverage.metrics.transition_coverage);
    assert.equal(coverage.metrics.transition_coverage.numerator, 8);
    assert.equal(coverage.metrics.transition_coverage.denominator, 10);
    assert.equal(coverage.metrics.transition_coverage.ratio, 0.8);

    // Guard coverage: true vs false vs unknown
    assert.equal(coverage.metrics.guard_outcome_coverage.true_outcomes_observed, 8);
    assert.equal(coverage.metrics.guard_outcome_coverage.false_outcomes_observed, 4);
    assert.equal(coverage.metrics.guard_outcome_coverage.unknown_outcomes_observed, 4);

    // Zero-denominator handling: ratio is null, status is NOT_APPLICABLE
    assert.equal(coverage.metrics.state_effect_coverage.ratio, null);
    assert.equal(coverage.metrics.state_effect_coverage.status, 'NOT_APPLICABLE');

    // Composite coverage rejection
    assert.equal(coverage.composite_coverage_status, COVERAGE_STATUS.PREFER_SEPARATE);
    assert.ok(coverage.defect_detection_disclaimer.includes('labelled faulty dataset'));
  });

  it('Fetches run report contribution and validates SHA-256 digest and truthful aggregator stub status', async () => {
    const report = await c2Api.getEvaluationReport('proj_alpha', 'eval_fail_003');

    assert.equal(report.evaluation_id, 'eval_fail_003');
    assert.equal(report.model_content_hash, 'sha256_mock_hash_efsm');
    assert.equal(report.content_digest_sha256, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855');

    // Aggregator status must be truthful
    assert.equal(report.published_to_shared_aggregator, false);
    assert.equal(report.publishing_status, 'STUB_PENDING_SHARED_AGGREGATOR');

    // Export report call
    const exportResult = await c2Api.exportReport('proj_alpha', 'eval_fail_003', 'json');
    assert.equal(exportResult.exported, true);
    assert.equal(exportResult.download_payload.published_to_shared_aggregator, false);
  });

  it('Replay reproduction verifies deterministic reproduction without calling live agent', async () => {
    const replayResult = await c2Api.replayEvaluation('proj_alpha', 'eval_fail_003');

    assert.equal(replayResult.evaluation_id, 'eval_fail_003');
    assert.equal(replayResult.executed_agent, false);
    assert.ok(replayResult.agent_execution_disclaimer.includes('does NOT invoke or interact with the live application agent'));
    assert.equal(replayResult.original_verdict, 'FAIL');
    assert.equal(replayResult.reproduced_verdict, 'FAIL');
    assert.equal(replayResult.is_identical, true);
  });

  it('Inspects Research datasets and verifies HELD_OUT partition immutability and B1-B4 baseline contracts', async () => {
    const datasets = await c2Api.listDatasets('proj_alpha');
    assert.equal(datasets.length, 1);
    const ds = datasets[0];
    assert.equal(ds.status, 'FROZEN');
    assert.equal(ds.partitions.HELD_OUT.frozen, true);
    assert.equal(ds.partitions.HELD_OUT.case_count, 15);

    const experiments = await c2Api.listExperiments('proj_alpha');
    assert.equal(experiments.length, 1);
    const exp = experiments[0];
    assert.ok(exp.baselines.B1);
    assert.ok(exp.baselines.B2);
    assert.ok(exp.baselines.B3);
    assert.ok(exp.baselines.B4);

    // B1: cannot localize divergence
    assert.equal(exp.baselines.B1.first_divergence_localization, 0.0);

    // B4 (Ours): EFSM conformance
    assert.equal(exp.baselines.B4.precision, 0.96);
    assert.equal(exp.baselines.B4.first_divergence_localization, 0.92);
    assert.equal(exp.baselines.B4.overhead_median_ms, 85);

    // CLI pipeline documentation check
    assert.equal(exp.cli_entrypoint, 'python -m app.components.c2_state_aware_workflow.experiments.cli');
  });

  it('Strictly isolates project requests and never makes calls to C1, C3 or C4 endpoints', async () => {
    await c2Api.listEvaluations('isolated_proj_999');
    await c2Api.getEvaluationCoverage('isolated_proj_999', 'eval_01');
    await c2Api.getEvaluationReport('isolated_proj_999', 'eval_01');
    await c2Api.listDatasets('isolated_proj_999');
    await c2Api.listExperiments('isolated_proj_999');

    for (const req of capturedRequests) {
      assert.ok(
        req.url.includes('/projects/isolated_proj_999/') || req.url.includes('/projects/proj_alpha/'),
        `Request URL "${req.url}" must be scoped to an authoritative project.`
      );
      assert.ok(!req.url.includes('/c1/'), `No requests may target C1 APIs: ${req.url}`);
      assert.ok(!req.url.includes('/c3/'), `No requests may target C3 APIs: ${req.url}`);
      assert.ok(!req.url.includes('/c4/'), `No requests may target C4 APIs: ${req.url}`);
    }
  });
});
