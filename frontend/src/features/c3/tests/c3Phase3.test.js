import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  RECOVERY_VERDICT,
  RULE_EVALUATION_STATUS,
  EVALUATION_STATUS,
  C2_FACT_VALUE,
  RECOVERY_RULE_ID,
  c3Api,
} from '../api.js';
import {
  DEMO_EVALUATION_PASS_COMPLETED,
  DEMO_EVALUATION_PASS_GRACEFUL,
  DEMO_EVALUATION_FAIL,
  DEMO_EVALUATION_INCONCLUSIVE,
  DEMO_EVALUATION_NOT_EVALUATED,
  DEMO_C2_FACTS,
  DEMO_RESEARCH_PROTOCOL,
  DEMO_EXECUTION_REPORT,
} from '../fixtures.js';

describe('Component 3 Phase 3: Recovery Evaluation, Explanations, Reports & Governance', () => {
  describe('1. Authoritative Recovery Verdicts & Status Orthogonality', () => {
    it('defines exactly four recovery verdicts for eligible fault trials', () => {
      assert.strictEqual(RECOVERY_VERDICT.PASS_COMPLETED, 'PASS_COMPLETED');
      assert.strictEqual(RECOVERY_VERDICT.PASS_GRACEFUL, 'PASS_GRACEFUL');
      assert.strictEqual(RECOVERY_VERDICT.FAIL, 'FAIL');
      assert.strictEqual(RECOVERY_VERDICT.INCONCLUSIVE, 'INCONCLUSIVE');

      const verdictKeys = Object.keys(RECOVERY_VERDICT);
      assert.strictEqual(verdictKeys.length, 4);
    });

    it('keeps non-verdict statuses (TEST_NOT_READY, EXECUTION_ERROR, NOT_TRIGGERED, NOT_EVALUATED) outside the verdict distribution', () => {
      const nonVerdictStatuses = ['TEST_NOT_READY', 'EXECUTION_ERROR', 'NOT_TRIGGERED', 'NOT_EVALUATED'];
      nonVerdictStatuses.forEach((status) => {
        assert.strictEqual(
          Object.values(RECOVERY_VERDICT).includes(status),
          false,
          `${status} must NOT be a recovery verdict`
        );
      });
    });

    it('ineligible trial returns null recovery_verdict and NOT_EVALUATED lifecycle status', () => {
      assert.strictEqual(DEMO_EVALUATION_NOT_EVALUATED.recovery_verdict, null);
      assert.strictEqual(
        DEMO_EVALUATION_NOT_EVALUATED.evaluation_status,
        EVALUATION_STATUS.NOT_EVALUATED
      );
      assert.ok(DEMO_EVALUATION_NOT_EVALUATED.evaluation.non_evaluation_reasons.length > 0);
    });

    it('distinguishes completed recovery (PASS_COMPLETED) from graceful stopping (PASS_GRACEFUL)', () => {
      assert.strictEqual(
        DEMO_EVALUATION_PASS_COMPLETED.recovery_verdict,
        RECOVERY_VERDICT.PASS_COMPLETED
      );
      assert.strictEqual(
        DEMO_EVALUATION_PASS_GRACEFUL.recovery_verdict,
        RECOVERY_VERDICT.PASS_GRACEFUL
      );
      assert.notStrictEqual(
        DEMO_EVALUATION_PASS_COMPLETED.recovery_verdict,
        DEMO_EVALUATION_PASS_GRACEFUL.recovery_verdict
      );
    });

    it('verifies inconclusive outcome fixture has null first_violated_rule and unknown duplicate effect rule', () => {
      assert.strictEqual(
        DEMO_EVALUATION_INCONCLUSIVE.recovery_verdict,
        RECOVERY_VERDICT.INCONCLUSIVE
      );
      assert.strictEqual(DEMO_EVALUATION_INCONCLUSIVE.first_violated_rule, null);
      const unknownRule = DEMO_EVALUATION_INCONCLUSIVE.evaluation.rule_results.find(
        (r) => r.rule_id === RECOVERY_RULE_ID.RULE_DUPLICATE_EFFECTS
      );
      assert.ok(unknownRule);
      assert.strictEqual(unknownRule.status, RULE_EVALUATION_STATUS.UNKNOWN);
    });
  });

  describe('2. Component 2 Discrete Assertion Facts Integration', () => {
    it('defines trusted C2 truth values: TRUE, FALSE, and UNKNOWN', () => {
      assert.strictEqual(C2_FACT_VALUE.TRUE, 'TRUE');
      assert.strictEqual(C2_FACT_VALUE.FALSE, 'FALSE');
      assert.strictEqual(C2_FACT_VALUE.UNKNOWN, 'UNKNOWN');
    });

    it('preserves assertion identifiers, provenance, and time scope from C2 facts', () => {
      assert.ok(DEMO_C2_FACTS.length >= 3);
      const fact = DEMO_C2_FACTS[0];
      assert.ok(fact.assertion_id);
      assert.ok(fact.provenance);
      assert.ok(['TRUE', 'FALSE', 'UNKNOWN'].includes(fact.value));
      assert.ok(fact.time_scope);
      assert.strictEqual(fact.provenance, 'C2_FIXTURE');
    });

    it('supports first observable violation tracking on failed trials', () => {
      assert.strictEqual(DEMO_EVALUATION_FAIL.recovery_verdict, RECOVERY_VERDICT.FAIL);
      assert.strictEqual(DEMO_EVALUATION_FAIL.first_violated_rule, 'RULE_UNSAFE_RETRIES');

      const violatedRule = DEMO_EVALUATION_FAIL.evaluation.rule_results.find(
        (r) => r.rule_id === 'RULE_UNSAFE_RETRIES'
      );
      assert.ok(violatedRule);
      assert.strictEqual(violatedRule.status, RULE_EVALUATION_STATUS.VIOLATED);
      assert.ok(violatedRule.reason_code);
    });
  });

  describe('3. Execution Reports and Explicit Denominators', () => {
    it('report contains explicit definitions for all three count denominators', () => {
      assert.ok(DEMO_EXECUTION_REPORT.denominators);
      assert.ok(DEMO_EXECUTION_REPORT.denominators.planned_cases);
      assert.ok(DEMO_EXECUTION_REPORT.denominators.executed_pairs);
      assert.ok(DEMO_EXECUTION_REPORT.denominators.evaluated_trials);
    });

    it('preserves clean control baseline qualification counts separately', () => {
      assert.strictEqual(typeof DEMO_EXECUTION_REPORT.clean_qualified_count, 'number');
      assert.strictEqual(typeof DEMO_EXECUTION_REPORT.clean_disqualified_count, 'number');
      assert.ok(DEMO_EXECUTION_REPORT.clean_disqualified_count > 0);
    });

    it('generates correct CSV export URL for execution reports', () => {
      const url = c3Api.getExecutionReportCsvUrl('proj-qa-001', 'exec-demo-001');
      assert.strictEqual(
        url,
        '/api/v1/c3/reports/executions/exec-demo-001/export?project_id=proj-qa-001'
      );
    });
  });

  describe('4. Three-Way Research Protocol & CLI Tooling Governance', () => {
    it('defines 40/20/40 partition percentages without client-side reviewer fabrication', () => {
      const parts = DEMO_RESEARCH_PROTOCOL.partitions;
      assert.strictEqual(parts.length, 3);
      const totalPct = parts.reduce((acc, p) => acc + p.percentage, 0);
      assert.strictEqual(totalPct, 100);

      const devSplit = parts.find((p) => p.name === 'development');
      const valSplit = parts.find((p) => p.name === 'validation');
      const testSplit = parts.find((p) => p.name === 'held_out_test');

      assert.strictEqual(devSplit?.percentage, 40);
      assert.strictEqual(valSplit?.percentage, 20);
      assert.strictEqual(testSplit?.percentage, 40);
    });

    it('documents all four comparative baselines B0 to B3 and ablations A1 to A3', () => {
      const baselineIds = DEMO_RESEARCH_PROTOCOL.baselines.map((b) => b.baseline_id);
      assert.deepStrictEqual(baselineIds, ['B0', 'B1', 'B2', 'B3']);

      const ablationIds = DEMO_RESEARCH_PROTOCOL.ablations.map((a) => a.ablation_id);
      assert.deepStrictEqual(ablationIds, ['A1', 'A2', 'A3']);
    });

    it('specifies explicit developer CLI execution command', () => {
      assert.ok(DEMO_RESEARCH_PROTOCOL.cli_command.includes('research_runner'));
      assert.ok(DEMO_RESEARCH_PROTOCOL.cli_command.includes('--split held_out'));
    });
  });

  describe('5. API Client Parameters and Boundary Enforcement', () => {
    it('throws error when project_id is missing from listEvaluations', async () => {
      await assert.rejects(
        async () => {
          await c3Api.listEvaluations(null);
        },
        {
          name: 'Error',
          message: 'Project ID is required to list evaluations.',
        }
      );
    });

    it('throws error when project_id is missing from getEvaluation', async () => {
      await assert.rejects(
        async () => {
          await c3Api.getEvaluation(null, 'eval-001');
        },
        {
          name: 'Error',
          message: 'Project ID is required to retrieve an evaluation.',
        }
      );
    });

    it('throws error when project_id is missing from computeEvaluation', async () => {
      await assert.rejects(
        async () => {
          await c3Api.computeEvaluation({});
        },
        {
          name: 'Error',
          message: 'Project ID is required to compute evaluation.',
        }
      );
    });
  });
});
