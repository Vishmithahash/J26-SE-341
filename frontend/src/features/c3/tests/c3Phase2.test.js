import '../../../tests/setup.js';
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import {
  c3Api,
  READINESS_STATUS,
  EXECUTION_TRACKING_STATUS,
  TRIAL_EXECUTION_STATUS,
  EXPOSURE_STATUS,
  CLEAN_QUALIFICATION,
  FIXTURE_COMPARABILITY,
  RECOVERY_VERDICT,
  RECOVERY_ACTOR,
  TARGET_MODE,
  CALLER_IDENTITY,
  TIMEOUT_BOUNDARY_TYPE,
} from '../api.js';
import {
  DEMO_MATCHED_PAIR_EVIDENCE,
  DEMO_MATCHED_PAIR_NOT_TRIGGERED,
  DEMO_MATCHED_PAIR_DISQUALIFIED_CLEAN,
  DEMO_TRACKED_EXECUTION,
  DEMO_EXECUTION_REPORT,
} from '../fixtures.js';

describe('Component 3 Phase 2: Matched Clean/Fault Trials & Exposure Evidence', () => {
  describe('1. Distinct Status Dimensions', () => {
    it('defines separate readiness statuses including TEST_NOT_READY and BLOCKED', () => {
      assert.equal(READINESS_STATUS.READY, 'READY');
      assert.equal(READINESS_STATUS.NOT_READY, 'NOT_READY');
      assert.equal(READINESS_STATUS.BLOCKED, 'BLOCKED');
      assert.equal(READINESS_STATUS.TEST_NOT_READY, 'TEST_NOT_READY');
    });

    it('defines distinct execution tracking statuses and target modes', () => {
      assert.equal(EXECUTION_TRACKING_STATUS.PLANNED, 'PLANNED');
      assert.equal(EXECUTION_TRACKING_STATUS.RUNNING, 'RUNNING');
      assert.equal(EXECUTION_TRACKING_STATUS.COMPLETED, 'COMPLETED');
      assert.equal(EXECUTION_TRACKING_STATUS.CANCELLED, 'CANCELLED');
      assert.equal(EXECUTION_TRACKING_STATUS.INTERRUPTED, 'INTERRUPTED');
      assert.equal(EXECUTION_TRACKING_STATUS.ERROR, 'ERROR');

      assert.equal(TARGET_MODE.DEMONSTRATION, 'DEMONSTRATION');
      assert.equal(TARGET_MODE.LIVE_AUT, 'LIVE_AUT');
      assert.equal(CALLER_IDENTITY.SCRIPTED_CALLER, 'SCRIPTED_CALLER');
      assert.equal(CALLER_IDENTITY.AGENT, 'AGENT');
      assert.equal(TIMEOUT_BOUNDARY_TYPE.CALLER_TIMEOUT_EXCEEDED, 'CALLER_TIMEOUT_EXCEEDED');
      assert.equal(FIXTURE_COMPARABILITY.EQUIVALENT_LOGICAL_STATE, 'EQUIVALENT_LOGICAL_STATE');
      assert.ok(DEMO_TRACKED_EXECUTION.execution_id);
    });

    it('defines trial execution health and completion statuses including EXECUTION_ERROR', () => {
      assert.equal(TRIAL_EXECUTION_STATUS.COMPLETED, 'COMPLETED');
      assert.equal(TRIAL_EXECUTION_STATUS.EXECUTION_ERROR, 'EXECUTION_ERROR');
      assert.equal(TRIAL_EXECUTION_STATUS.TIMEOUT, 'TIMEOUT');
      assert.equal(TRIAL_EXECUTION_STATUS.CANCELLED, 'CANCELLED');
    });

    it('defines independent exposure status (CONFIRMED, NOT_TRIGGERED, EXPOSURE_UNKNOWN)', () => {
      assert.equal(EXPOSURE_STATUS.CONFIRMED, 'CONFIRMED');
      assert.equal(EXPOSURE_STATUS.NOT_TRIGGERED, 'NOT_TRIGGERED');
      assert.equal(EXPOSURE_STATUS.EXPOSURE_UNKNOWN, 'EXPOSURE_UNKNOWN');
    });

    it('defines clean control qualification statuses (QUALIFIED, DISQUALIFIED, UNKNOWN)', () => {
      assert.equal(CLEAN_QUALIFICATION.QUALIFIED, 'QUALIFIED');
      assert.equal(CLEAN_QUALIFICATION.DISQUALIFIED, 'DISQUALIFIED');
      assert.equal(CLEAN_QUALIFICATION.UNKNOWN, 'UNKNOWN');
    });

    it('defines authoritative recovery verdicts (PASS_COMPLETED, PASS_GRACEFUL, FAIL, INCONCLUSIVE)', () => {
      assert.equal(RECOVERY_VERDICT.PASS_COMPLETED, 'PASS_COMPLETED');
      assert.equal(RECOVERY_VERDICT.PASS_GRACEFUL, 'PASS_GRACEFUL');
      assert.equal(RECOVERY_VERDICT.FAIL, 'FAIL');
      assert.equal(RECOVERY_VERDICT.INCONCLUSIVE, 'INCONCLUSIVE');
    });

    it('defines recovery actor attribution categories without guessing browser-side', () => {
      assert.equal(RECOVERY_ACTOR.SCRIPTED_CALLER, 'SCRIPTED_CALLER');
      assert.equal(RECOVERY_ACTOR.AGENT, 'AGENT');
      assert.equal(RECOVERY_ACTOR.SDK, 'SDK');
      assert.equal(RECOVERY_ACTOR.ADAPTER, 'ADAPTER');
      assert.equal(RECOVERY_ACTOR.MIDDLEWARE, 'MIDDLEWARE');
      assert.equal(RECOVERY_ACTOR.UNKNOWN, 'UNKNOWN');
    });
  });

  describe('2. Matched Pair Evidence Linkage and Structure', () => {
    it('verifies that matched clean and fault trials share pair_id, case_id, project_id, and run_id', () => {
      const pair = DEMO_MATCHED_PAIR_EVIDENCE;
      assert.equal(pair.clean_trial.pair_id, pair.pair_id);
      assert.equal(pair.fault_trial.pair_id, pair.pair_id);
      assert.equal(pair.clean_trial.case_id, pair.case_id);
      assert.equal(pair.fault_trial.case_id, pair.case_id);
      assert.equal(pair.clean_trial.project_id, pair.project_id);
      assert.equal(pair.fault_trial.project_id, pair.project_id);
      assert.equal(pair.clean_trial.run_id, pair.run_id);
      assert.equal(pair.fault_trial.run_id, pair.run_id);
    });

    it('verifies clean trial has zero fault episodes and injection disabled', () => {
      const cleanTrial = DEMO_MATCHED_PAIR_EVIDENCE.clean_trial;
      assert.equal(cleanTrial.trial_role, 'CLEAN');
      assert.equal(cleanTrial.episodes.length, 0);
      assert.equal(cleanTrial.execution_status, 'COMPLETED');
    });

    it('verifies fault trial links exactly one targeted fault episode record', () => {
      const faultTrial = DEMO_MATCHED_PAIR_EVIDENCE.fault_trial;
      assert.equal(faultTrial.trial_role, 'FAULT');
      assert.equal(faultTrial.episodes.length, 1);
      const ep = faultTrial.episodes[0];
      assert.equal(ep.fault_family, 'TIMEOUT_DISCONNECTION');
      assert.equal(ep.effect_phase, 'BEFORE_EFFECT');
      assert.equal(ep.prevented_forwarding, true);
      assert.equal(ep.caller_observed_timeout, true);
    });

    it('retains failed clean baseline in dataset without retrying or hiding', () => {
      const disqualifiedPair = DEMO_MATCHED_PAIR_DISQUALIFIED_CLEAN;
      assert.equal(disqualifiedPair.clean_qualification, 'DISQUALIFIED');
      assert.equal(disqualifiedPair.clean_trial.execution_status, 'EXECUTION_ERROR');
      // The paired record is retained honestly with clean_qualification DISQUALIFIED
      assert.equal(disqualifiedPair.fixture_comparability, 'NON_EQUIVALENT');
    });

    it('distinguishes NOT_TRIGGERED exposure from confirmed recovery', () => {
      const notTriggeredPair = DEMO_MATCHED_PAIR_NOT_TRIGGERED;
      assert.equal(notTriggeredPair.exposure_status, 'NOT_TRIGGERED');
      // A not-triggered trial has 0 tool calls and did not trigger the fault
      assert.equal(notTriggeredPair.fault_trial.tool_calls_count, 0);
      assert.notEqual(notTriggeredPair.exposure_status, 'CONFIRMED');
    });
  });

  describe('3. Execution Reports and Explicit Denominators', () => {
    it('report provides explicit denominators for planned cases, executed pairs, and evaluated trials', () => {
      const rep = DEMO_EXECUTION_REPORT;
      assert.ok(rep.denominators.planned_cases);
      assert.ok(rep.denominators.executed_pairs);
      assert.ok(rep.denominators.evaluated_trials);
      assert.equal(rep.planned_cases_count, 5);
      assert.equal(rep.executed_cases_count, 5);
    });

    it('report separates clean baseline qualification, exposure outcomes, and recovery verdicts', () => {
      const rep = DEMO_EXECUTION_REPORT;
      assert.equal(rep.clean_qualified_count, 4);
      assert.equal(rep.clean_disqualified_count, 1);
      assert.equal(rep.confirmed_exposure_count, 4);
      assert.equal(rep.not_triggered_exposure_count, 1);
      assert.equal(rep.verdict_counts.pass_completed_count, 2);
      assert.equal(rep.verdict_counts.pass_graceful_count, 1);
      assert.equal(rep.verdict_counts.fail_count, 1);
      assert.equal(rep.verdict_counts.inconclusive_count, 0);
    });
  });

  describe('4. API Client and URL Generation', () => {
    it('generates correct CSV export URL for execution reports', () => {
      const url = c3Api.getExecutionReportCsvUrl('proj-test-123', 'exec-test-456');
      assert.equal(
        url,
        '/api/v1/c3/reports/executions/exec-test-456/export?project_id=proj-test-123'
      );
    });

    it('throws error when project_id is missing from persistence API calls', async () => {
      await assert.rejects(
        async () => {
          await c3Api.listExecutions(null);
        },
        { message: 'Project ID is required to list executions.' }
      );

      await assert.rejects(
        async () => {
          await c3Api.listPairs(null);
        },
        { message: 'Project ID is required to list matched pairs.' }
      );

      await assert.rejects(
        async () => {
          await c3Api.getExecutionReport(null, 'exec-123');
        },
        { message: 'Project ID is required to retrieve an execution report.' }
      );
    });
  });
});
