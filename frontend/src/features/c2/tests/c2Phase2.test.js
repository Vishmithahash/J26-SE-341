import '../../../tests/setup.js';
import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { c2Api } from '../api/c2Api.js';
import { LOCAL_RUNNER_CAPABILITIES } from '../hooks/useC2Execution.js';

describe('Component 2 Phase 2: Workflow Test Generation, Suite Inspection & Execution Controls', () => {
  let capturedRequests = [];

  beforeEach(() => {
    capturedRequests = [];
    globalThis.fetch = async (url, options = {}) => {
      capturedRequests.push({ url, options });

      // Mock responses based on URL pattern
      if (url.includes('/suites/generate')) {
        const body = options.body ? JSON.parse(options.body) : {};
        if (body.model_id === 'unready_model') {
          return {
            ok: false,
            status: 422,
            json: async () => ({
              detail: {
                message: 'Model is not ready for test suite generation.',
                readiness: 'MODEL NOT READY',
                reasons: ['Model has not been explicitly reviewed and approved.'],
              },
            }),
          };
        }
        return {
          ok: true,
          status: 201,
          json: async () => ({
            id: 1,
            project_id: 'proj_test',
            suite_id: 'suite_gen_123',
            model_id: body.model_id,
            model_version: body.version,
            model_content_hash: 'hash_abc123',
            generator_version: body.generator_version || 'c2_generator_v1',
            seed: body.seed ?? 42,
            total_cases: 20,
            ready_cases_count: 20,
            not_ready_cases_count: 0,
            category_counts: { valid: 8, alternative: 4, negative: 4, mutated: 4 },
            diagnostics: {
              paths_explored: 45,
              max_depth_reached: 12,
              planned_transition_coverage: { ratio: 0.95 },
              planned_guard_coverage: { ratio: 0.90 },
            },
            created_at: '2026-10-21T12:00:00Z',
          }),
        };
      }

      if (url.includes('/export/qa')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            schema_version: '2026.1',
            suite_id: 'suite_gen_123',
            cases: [
              {
                test_id: 'case_001',
                task: 'Refund order 503',
                category: 'valid',
                reference_path: [
                  { step: 1, transition_id: 't_lookup', from_state: 'IDLE', to_state: 'ORDER_LOADED' },
                  { step: 2, transition_id: 't_verify', from_state: 'ORDER_LOADED', to_state: 'ORDER_VERIFIED' },
                ],
                assertions: ['state == "REFUNDED"', 'ledger_updated == true'],
                expected_outcome: 'PASS',
              },
              {
                test_id: 'case_mutant_002',
                task: 'Refund order 503 with swapped steps',
                category: 'mutated',
                mutation: {
                  mutation_type: 'reordered_step',
                  target_transition_id: 't_verify',
                  mutated_path: ['t_verify', 't_lookup'],
                },
                reference_path: [{ step: 1, transition_id: 't_verify' }],
                assertions: ['divergence_detected == true'],
                expected_outcome: 'FAIL',
              },
            ],
          }),
        };
      }

      if (url.includes('/cases/case_mutant_002/agent-payload')) {
        return {
          ok: false,
          status: 400,
          json: async () => ({
            detail: "Test case 'case_mutant_002' has execution mode 'synthetic_evaluator_mutant' and cannot be exported for agent execution.",
          }),
        };
      }

      if (url.includes('/agent-payload') || url.includes('/export/agent')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            test_id: 'case_001',
            project_id: 'proj_test',
            task: 'Refund latest paid order 503',
            fixture_ref: 'synthetic_ecommerce_customer_42',
            permitted_context: { customer_id: 42, target_order_id: 503 },
          }),
        };
      }

      if (url.includes('/cases/case_001/run')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            schema_version: '2026.1',
            evaluation_id: 'eval_run_999',
            project_id: 'proj_test',
            suite_id: 'suite_gen_123',
            test_id: 'case_001',
            run_id: 'run_999',
            evaluator_version: 'c2_evaluator_v1',
            verdict: 'PASS',
            reasons: ['Execution trace conformed exactly to Extended Finite State Machine.'],
            violations: [],
            first_divergence: null,
            evaluator_timing_ms: 18,
            created_at: '2026-10-21T12:01:00Z',
          }),
        };
      }

      if (url.includes('/cases/case_negative_003/run')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            schema_version: '2026.1',
            evaluation_id: 'eval_run_neg_100',
            project_id: 'proj_test',
            suite_id: 'suite_gen_123',
            test_id: 'case_negative_003',
            run_id: 'run_neg_100',
            evaluator_version: 'c2_evaluator_v1',
            verdict: 'EXPECTED_REJECTION_PASS',
            reasons: ['Negative test correctly rejected by SUT as expected.'],
            violations: [],
            first_divergence: null,
            evaluator_timing_ms: 14,
            created_at: '2026-10-21T12:02:00Z',
          }),
        };
      }

      if (url.includes('/demonstrations/run')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            schema_version: '2026.1',
            evaluation_id: 'eval_demo_101',
            project_id: 'proj_test',
            suite_id: 'suite_demonstration',
            test_id: 'demo_test_skipped_step',
            run_id: 'demo_run_101',
            evaluator_version: 'c2_evaluator_v1',
            verdict: 'FAIL',
            reasons: ['Workflow step omitted by agent.'],
            violations: [
              {
                violation_type: 'MISSING_REQUIRED_STEP',
                state: 'ORDER_LOADED',
                description: 'Required verification transition t_verify was skipped before refund invocation.',
              },
            ],
            first_divergence: {
              step_index: 2,
              expected_state: 'ORDER_VERIFIED',
              observed_state: 'ORDER_LOADED',
              divergence_description: 'Expected transition t_verify but received t_refund',
            },
            evaluator_timing_ms: 22,
          }),
        };
      }

      if (url.includes('/re-evaluate')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            evaluation_id: 'eval_reproduced_102',
            verdict: 'PASS',
            reasons: ['Re-evaluated from retained evidence with identical verdict.'],
          }),
        };
      }

      if (url.includes('/verify-reproduction')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            is_reproducible: true,
            evidence_digest: 'sha256_mock_evidence_digest_xyz',
            matched_verdict: 'PASS',
          }),
        };
      }

      // Default fallback response
      return {
        ok: true,
        status: 200,
        json: async () => ({ status: 'ok', url }),
      };
    };
  });

  // ---------------------------------------------------------------------------
  // 1. Generation Requests and Readiness Gating
  // ---------------------------------------------------------------------------
  describe('1. Automatic Test Generation & Readiness Gating', () => {
    it('submits generation request strictly to the backend generation route', async () => {
      const payload = {
        model_id: 'c2_refund_efsm',
        version: '1.0.0',
        generator_version: 'c2_generator_v1',
        seed: 42,
        max_depth: 15,
        max_loop_visits: 1,
        case_budget: 20,
        include_alternatives: true,
        include_negative_rejections: true,
        include_mutations: true,
        mutation_budget: 8,
        enabled_mutation_types: ['skipped_step', 'reordered_step'],
        fixture_ref: 'synthetic_ecommerce_customer_42',
      };

      const result = await c2Api.generateTestSuite('proj_ecommerce_99', payload);

      assert.equal(capturedRequests.length, 1);
      assert.equal(
        capturedRequests[0].url,
        '/api/v1/c2/projects/proj_ecommerce_99/suites/generate'
      );
      assert.equal(capturedRequests[0].options.method, 'POST');
      assert.equal(result.suite_id, 'suite_gen_123');
      assert.equal(result.total_cases, 20);
    });

    it('rejects generation when projectId is missing', async () => {
      await assert.rejects(
        async () => {
          await c2Api.generateTestSuite('', { model_id: 'm1' });
        },
        {
          name: 'Error',
          message: 'projectId is required to generate a test suite',
        }
      );
    });

    it('propagates MODEL NOT READY (HTTP 422) if reference model is unapproved', async () => {
      const payload = {
        model_id: 'unready_model',
        version: '1.0.0',
        generator_version: 'c2_generator_v1',
      };

      await assert.rejects(
        async () => {
          await c2Api.generateTestSuite('proj_ecommerce_99', payload);
        },
        (err) => {
          assert.equal(err.status, 422);
          return true;
        }
      );
    });
  });

  // ---------------------------------------------------------------------------
  // 2. Category & Readiness Rendering and Inspection
  // ---------------------------------------------------------------------------
  describe('2. Suite and Case Inspection with 4 Categories', () => {
    it('scopes listTestSuites to the target project', async () => {
      await c2Api.listTestSuites('proj_qa_001');
      assert.equal(capturedRequests.length, 1);
      assert.equal(capturedRequests[0].url, '/api/v1/c2/projects/proj_qa_001/suites');
      assert.equal(capturedRequests[0].options.method, 'GET');
    });

    it('supports category and readiness query parameter filters', async () => {
      await c2Api.listTestCases('proj_qa_001', 'suite_123', {
        category: 'mutated',
        readiness: 'TEST_READY',
      });

      assert.equal(capturedRequests.length, 1);
      assert.equal(
        capturedRequests[0].url,
        '/api/v1/c2/projects/proj_qa_001/suites/suite_123/cases?category=mutated&readiness=TEST_READY'
      );
    });

    it('retrieves specific test case details with mutation provenance', async () => {
      await c2Api.getTestCaseDetail('proj_qa_001', 'suite_123', 'case_mutant_002');
      assert.equal(capturedRequests.length, 1);
      assert.equal(
        capturedRequests[0].url,
        '/api/v1/c2/projects/proj_qa_001/suites/suite_123/cases/case_mutant_002'
      );
    });

    it('checks suite readiness breakdown', async () => {
      await c2Api.getSuiteReadiness('proj_qa_001', 'suite_123');
      assert.equal(capturedRequests.length, 1);
      assert.equal(
        capturedRequests[0].url,
        '/api/v1/c2/projects/proj_qa_001/suites/suite_123/readiness'
      );
    });
  });

  // ---------------------------------------------------------------------------
  // 3. Private Oracle Isolation
  // ---------------------------------------------------------------------------
  describe('3. Private Oracle Isolation Boundary', () => {
    it('allows full QA test definition export ONLY through the tester-private QA endpoint', async () => {
      const qaSuite = await c2Api.exportQASuite('proj_qa_001', 'suite_gen_123');
      assert.equal(capturedRequests.length, 1);
      assert.equal(
        capturedRequests[0].url,
        '/api/v1/c2/projects/proj_qa_001/suites/suite_gen_123/export/qa'
      );

      // QA export includes private oracle data
      assert.ok(qaSuite.cases[0].reference_path);
      assert.ok(qaSuite.cases[0].assertions);
      assert.equal(qaSuite.cases[1].category, 'mutated');
      assert.ok(qaSuite.cases[1].mutation);
    });

    it('strictly isolates agent-facing payload from private reference paths and assertions', async () => {
      const agentPayload = await c2Api.getCaseAgentPayload('proj_qa_001', 'suite_gen_123', 'case_001');
      assert.equal(capturedRequests.length, 1);
      assert.equal(
        capturedRequests[0].url,
        '/api/v1/c2/projects/proj_qa_001/suites/suite_gen_123/cases/case_001/agent-payload'
      );

      // Verify strict allowlist
      assert.equal(agentPayload.test_id, 'case_001');
      assert.equal(agentPayload.project_id, 'proj_test');
      assert.equal(agentPayload.task, 'Refund latest paid order 503');
      assert.equal(agentPayload.fixture_ref, 'synthetic_ecommerce_customer_42');
      assert.ok(agentPayload.permitted_context);

      // VERIFY STRICT REDACTION: Agent must NEVER receive private oracle or expected outcomes
      assert.equal(agentPayload.reference_path, undefined);
      assert.equal(agentPayload.assertions, undefined);
      assert.equal(agentPayload.mutation, undefined);
      assert.equal(agentPayload.expected_outcome, undefined);
      assert.equal(agentPayload.expected_states, undefined);
      assert.equal(agentPayload.divergence_points, undefined);
    });

    it('rejects exporting mutant test cases to agent payloads with HTTP 400', async () => {
      await assert.rejects(
        async () => {
          await c2Api.getCaseAgentPayload('proj_qa_001', 'suite_gen_123', 'case_mutant_002');
        },
        (err) => {
          assert.equal(err.status, 400);
          return true;
        }
      );
    });
  });

  // ---------------------------------------------------------------------------
  // 4. Execution Controls & Runner Capabilities
  // ---------------------------------------------------------------------------
  describe('4. Execution Controls & Honest Runner Capabilities', () => {
    it('discloses local synthetic demonstration runner honestly (is_live: false)', () => {
      assert.equal(LOCAL_RUNNER_CAPABILITIES.isLiveExecution, false);
      assert.equal(LOCAL_RUNNER_CAPABILITIES.liveCapabilitiesAvailable, false);
      assert.equal(LOCAL_RUNNER_CAPABILITIES.runnerId, 'local_synthetic_runner_v1');
      assert.ok(
        LOCAL_RUNNER_CAPABILITIES.unavailableLiveCapabilities.includes('live_llm_runner')
      );
    });

    it('submits single test case execution to the backend run endpoint', async () => {
      const result = await c2Api.runCase('proj_test', 'suite_gen_123', 'case_001');
      assert.equal(capturedRequests.length, 1);
      assert.equal(
        capturedRequests[0].url,
        '/api/v1/c2/projects/proj_test/suites/suite_gen_123/cases/case_001/run'
      );
      assert.equal(capturedRequests[0].options.method, 'POST');
      assert.equal(result.verdict, 'PASS');
    });

    it('distinguishes EXPECTED REJECTION PASS for successful negative tests', async () => {
      const result = await c2Api.runCase('proj_test', 'suite_gen_123', 'case_negative_003');
      assert.equal(result.verdict, 'EXPECTED_REJECTION_PASS');
      assert.notEqual(result.verdict, 'FAIL');
    });

    it('submits bounded suite execution with max_cases configuration', async () => {
      await c2Api.runSuite('proj_test', 'suite_gen_123', 25);
      assert.equal(capturedRequests.length, 1);
      assert.equal(
        capturedRequests[0].url,
        '/api/v1/c2/projects/proj_test/suites/suite_gen_123/run'
      );
      assert.equal(capturedRequests[0].options.method, 'POST');
      assert.deepEqual(JSON.parse(capturedRequests[0].options.body), { max_cases: 25 });
    });

    it('clearly labels synthetic demonstrations and submits to demonstration route', async () => {
      const demoReq = {
        scenario: 'skipped_step',
        model_id: 'c2_refund_efsm_nexacart',
        model_version: '1.0.0',
        customer_id: 42,
        target_order_id: 503,
      };

      const result = await c2Api.runSyntheticDemonstration('proj_test', demoReq);
      assert.equal(capturedRequests.length, 1);
      assert.equal(
        capturedRequests[0].url,
        '/api/v1/c2/projects/proj_test/demonstrations/run'
      );
      assert.equal(result.verdict, 'FAIL');
      assert.equal(result.first_divergence.step_index, 2);
    });

    it('supports re-evaluation from retained original evidence', async () => {
      const result = await c2Api.reEvaluateExecution('proj_test', 'eval_run_999');
      assert.equal(capturedRequests.length, 1);
      assert.equal(
        capturedRequests[0].url,
        '/api/v1/c2/projects/proj_test/evaluations/eval_run_999/re-evaluate'
      );
      assert.equal(result.verdict, 'PASS');
    });

    it('supports independent replay reproduction verification', async () => {
      const result = await c2Api.verifyReproduction('proj_test', 'eval_run_999');
      assert.equal(capturedRequests.length, 1);
      assert.equal(
        capturedRequests[0].url,
        '/api/v1/c2/projects/proj_test/evaluations/eval_run_999/verify-reproduction'
      );
      assert.equal(result.is_reproducible, true);
    });
  });

  // ---------------------------------------------------------------------------
  // 5. Account & Project Switching
  // ---------------------------------------------------------------------------
  describe('5. Project Scoping & Switching', () => {
    it('strictly directs requests to whichever project is active', async () => {
      await c2Api.listTestSuites('project_aaa');
      await c2Api.listTestSuites('project_bbb');

      assert.equal(capturedRequests[0].url, '/api/v1/c2/projects/project_aaa/suites');
      assert.equal(capturedRequests[1].url, '/api/v1/c2/projects/project_bbb/suites');
    });

    it('fails fast when active project ID is undefined or empty', async () => {
      await assert.rejects(async () => c2Api.listTestSuites(null), /projectId is required/);
      await assert.rejects(async () => c2Api.runCase(null, 's1', 'c1'), /projectId/);
      await assert.rejects(async () => c2Api.runSuite(null, 's1'), /projectId/);
      await assert.rejects(async () => c2Api.exportQASuite(null, 's1'), /projectId/);
    });
  });
});
