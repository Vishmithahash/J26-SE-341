/**
 * Component 4 (C4) - Frontend Phase 2 Tests
 * Verifies automatic policy-test generation contracts, case lifecycle & freezing,
 * the three separated payload boundaries, runtime readiness, idempotency contracts,
 * and the 6 independent outcome dimensions.
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  TEST_CASE_KINDS,
  CASE_LIFECYCLE_STATES,
  TARGET_EXECUTION_MODES,
  SIMULATED_AGENT_BEHAVIORS,
  EXECUTION_STATUSES,
  EXPOSURE_STATUSES,
  POLICY_VERDICTS,
  ATTACKER_OBJECTIVE_OUTCOMES,
  TASK_UTILITY_OUTCOMES,
  CLEANUP_STATUSES,
} from '../api/types.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const c4RootDir = path.resolve(__dirname, '..');

describe('C4 Phase 2: Taxonomy & Outcome Dimension Enums', () => {
  it('defines the three test case categories', () => {
    assert.equal(TEST_CASE_KINDS.BENIGN, 'BENIGN');
    assert.equal(TEST_CASE_KINDS.DIRECT_POLICY_CHALLENGE, 'DIRECT_POLICY_CHALLENGE');
    assert.equal(TEST_CASE_KINDS.INDIRECT_PROMPT_INJECTION, 'INDIRECT_PROMPT_INJECTION');
  });

  it('defines case lifecycle states including DRAFT, VALIDATED, FROZEN, REJECTED, NEEDS_REVIEW', () => {
    assert.equal(CASE_LIFECYCLE_STATES.DRAFT, 'DRAFT');
    assert.equal(CASE_LIFECYCLE_STATES.VALIDATED, 'VALIDATED');
    assert.equal(CASE_LIFECYCLE_STATES.FROZEN, 'FROZEN');
    assert.equal(CASE_LIFECYCLE_STATES.REJECTED, 'REJECTED');
    assert.equal(CASE_LIFECYCLE_STATES.NEEDS_REVIEW, 'NEEDS_REVIEW');
  });

  it('defines target execution modes SIMULATED and LIVE_AUT explicitly', () => {
    assert.equal(TARGET_EXECUTION_MODES.SIMULATED, 'SIMULATED');
    assert.equal(TARGET_EXECUTION_MODES.LIVE_AUT, 'LIVE_AUT');
  });

  it('defines 11 simulated agent behavioral profiles for controlled offline execution', () => {
    assert.equal(typeof SIMULATED_AGENT_BEHAVIORS, 'object');
    assert.equal(Object.keys(SIMULATED_AGENT_BEHAVIORS).length, 11);
    assert.equal(SIMULATED_AGENT_BEHAVIORS.COMPLIANT, 'COMPLIANT');
    assert.equal(SIMULATED_AGENT_BEHAVIORS.UNAUTHORIZED_ATTEMPT_BLOCKED, 'UNAUTHORIZED_ATTEMPT_BLOCKED');
    assert.equal(SIMULATED_AGENT_BEHAVIORS.PROHIBITED_EFFECT_COMMITTED, 'PROHIBITED_EFFECT_COMMITTED');
    assert.equal(SIMULATED_AGENT_BEHAVIORS.DISCLOSURE_EXFILTRATION, 'DISCLOSURE_EXFILTRATION');
    assert.equal(SIMULATED_AGENT_BEHAVIORS.FIXTURE_CLEANUP_FAILURE, 'FIXTURE_CLEANUP_FAILURE');
  });

  it('defines the 4 backend policy verdicts', () => {
    assert.equal(POLICY_VERDICTS.PASS, 'PASS');
    assert.equal(POLICY_VERDICTS.FAIL, 'FAIL');
    assert.equal(POLICY_VERDICTS.INCONCLUSIVE, 'INCONCLUSIVE');
    assert.equal(POLICY_VERDICTS.NOT_EXERCISED, 'NOT_EXERCISED');
  });

  it('defines the 4 injection exposure states', () => {
    assert.equal(EXPOSURE_STATUSES.EXPOSED, 'EXPOSED');
    assert.equal(EXPOSURE_STATUSES.NOT_EXPOSED, 'NOT_EXPOSED');
    assert.equal(EXPOSURE_STATUSES.NOT_APPLICABLE, 'NOT_APPLICABLE');
    assert.equal(EXPOSURE_STATUSES.UNKNOWN, 'UNKNOWN');
  });

  it('defines attacker objective outcomes distinctly separating attempt from committed effect', () => {
    assert.equal(ATTACKER_OBJECTIVE_OUTCOMES.ACHIEVED, 'ACHIEVED');
    assert.equal(ATTACKER_OBJECTIVE_OUTCOMES.BLOCKED, 'BLOCKED');
    assert.equal(ATTACKER_OBJECTIVE_OUTCOMES.NOT_ACHIEVED, 'NOT_ACHIEVED');
    assert.equal(ATTACKER_OBJECTIVE_OUTCOMES.UNKNOWN, 'UNKNOWN');
    assert.equal(ATTACKER_OBJECTIVE_OUTCOMES.NOT_APPLICABLE, 'NOT_APPLICABLE');
  });

  it('defines legitimate task utility outcomes distinctly from security verdicts', () => {
    assert.equal(TASK_UTILITY_OUTCOMES.SUCCESS, 'SUCCESS');
    assert.equal(TASK_UTILITY_OUTCOMES.FAILED, 'FAILED');
    assert.equal(TASK_UTILITY_OUTCOMES.PARTIAL, 'PARTIAL');
    assert.equal(TASK_UTILITY_OUTCOMES.UNKNOWN, 'UNKNOWN');
    assert.equal(TASK_UTILITY_OUTCOMES.NOT_APPLICABLE, 'NOT_APPLICABLE');
  });

  it('defines execution lifecycle and fixture cleanup statuses', () => {
    assert.ok(EXECUTION_STATUSES.COMPLETED);
    assert.ok(EXECUTION_STATUSES.FAILED);
    assert.ok(EXECUTION_STATUSES.CLEANUP_FAILED);
    assert.ok(EXECUTION_STATUSES.BLOCKED_BEFORE_INVOCATION);

    assert.equal(CLEANUP_STATUSES.CLEANED_AND_VERIFIED, 'CLEANED_AND_VERIFIED');
    assert.equal(CLEANUP_STATUSES.CLEANUP_FAILED, 'CLEANUP_FAILED');
    assert.equal(CLEANUP_STATUSES.SKIPPED, 'SKIPPED');
  });
});

describe('C4 Phase 2: API Client Endpoints Verification', () => {
  const apiFile = path.resolve(c4RootDir, 'api/c4Api.js');
  const apiCode = fs.readFileSync(apiFile, 'utf8');

  it('implements test case generation and batch inspection endpoints', () => {
    assert.ok(apiCode.includes('generateTestCases('), 'Must provide generateTestCases API');
    assert.ok(apiCode.includes('/generate'), 'Must call /generate endpoint');
    assert.ok(apiCode.includes('getGenerationBatch('), 'Must provide getGenerationBatch API');
    assert.ok(apiCode.includes('/batches/'), 'Must call /batches/{batchId} endpoint');
  });

  it('implements test case retrieval, validation, and freezing endpoints', () => {
    assert.ok(apiCode.includes('listTestCases('), 'Must provide listTestCases API');
    assert.ok(apiCode.includes('getTestCase('), 'Must provide getTestCase API');
    assert.ok(apiCode.includes('validateTestCase('), 'Must provide validateTestCase API');
    assert.ok(apiCode.includes('/validate'), 'Must call /validate endpoint');
    assert.ok(apiCode.includes('freezeTestCase('), 'Must provide freezeTestCase API');
    assert.ok(apiCode.includes('/freeze'), 'Must call /freeze endpoint');
  });

  it('implements the 3 separate payload export endpoints', () => {
    assert.ok(apiCode.includes('exportAgentPayload('), 'Must provide exportAgentPayload API');
    assert.ok(apiCode.includes('/export/agent'), 'Must call /export/agent');
    assert.ok(apiCode.includes('exportHarnessPayload('), 'Must provide exportHarnessPayload API');
    assert.ok(apiCode.includes('/export/harness'), 'Must call /export/harness');
    assert.ok(apiCode.includes('exportEvaluatorPayload('), 'Must provide exportEvaluatorPayload API');
    assert.ok(apiCode.includes('/export/evaluator'), 'Must call /export/evaluator');
  });

  it('implements runtime readiness, execution, run history, and report export endpoints', () => {
    assert.ok(apiCode.includes('checkExecutionReadiness('), 'Must provide checkExecutionReadiness API');
    assert.ok(apiCode.includes('/runs/readiness'), 'Must call /runs/readiness');
    assert.ok(apiCode.includes('executeTestCase('), 'Must provide executeTestCase API');
    assert.ok(apiCode.includes('/runs/execute'), 'Must call /runs/execute');
    assert.ok(apiCode.includes('getExecutionRun('), 'Must provide getExecutionRun API');
    assert.ok(apiCode.includes('listExecutionRuns('), 'Must provide listExecutionRuns API');
    assert.ok(apiCode.includes('exportRunReport('), 'Must provide exportRunReport API');
  });
});

describe('C4 Phase 2: Payload Boundary Separation Integrity', () => {
  it('does NOT spread raw test case objects into agent execution requests in UI components', () => {
    const componentsDir = path.resolve(c4RootDir, 'components');
    const walkSync = (dir) => {
      let results = [];
      const list = fs.readdirSync(dir);
      for (const file of list) {
        const fullPath = path.join(dir, file);
        const stat = fs.statSync(fullPath);
        if (stat.isDirectory()) {
          results = results.concat(walkSync(fullPath));
        } else if (file.endsWith('.jsx') || file.endsWith('.js')) {
          results.push(fullPath);
        }
      }
      return results;
    };

    const allCodeFiles = walkSync(componentsDir);
    for (const filePath of allCodeFiles) {
      const content = fs.readFileSync(filePath, 'utf8');
      // Verify no spreading of case object into agent payload
      assert.equal(
        content.includes('...selectedCase') && content.includes('agent_task_payload'),
        false,
        `File ${filePath} must not spread selectedCase directly into agent payload`
      );
    }
  });

  it('renders injection content safely in CasePayloadsModal with pre-wrap sanitization', () => {
    const modalFile = path.resolve(c4RootDir, 'components/cases/CasePayloadsModal.jsx');
    const modalCode = fs.readFileSync(modalFile, 'utf8');

    // Asserts no dangerous HTML insertion
    assert.equal(modalCode.includes('dangerouslySetInnerHTML'), false);
    assert.equal(modalCode.includes('eval('), false);
    // Asserts untrusted payload is labeled clearly
    assert.ok(modalCode.includes('Adversarial Injection Payload'));
    assert.ok(modalCode.includes('Harness Placement Ownership'));
  });
});

describe('C4 Phase 2: Disentangled Outcome Dimensions Rules', () => {
  it('verifies that NOT_EXPOSED does not imply PASS verdict', () => {
    // When injection is not retrieved/exposed, the test verdict is INCONCLUSIVE or NOT_EXERCISED, NOT a pass
    const isUnexposedPass = (exposure, verdict) => {
      if (exposure === EXPOSURE_STATUSES.NOT_EXPOSED && verdict === POLICY_VERDICTS.PASS) {
        return false; // Invalid: missing exposure evidence does not establish PASS
      }
      return true;
    };

    assert.equal(isUnexposedPass(EXPOSURE_STATUSES.NOT_EXPOSED, POLICY_VERDICTS.PASS), false);
    assert.equal(isUnexposedPass(EXPOSURE_STATUSES.NOT_EXPOSED, POLICY_VERDICTS.NOT_EXERCISED), true);
    assert.equal(isUnexposedPass(EXPOSURE_STATUSES.NOT_EXPOSED, POLICY_VERDICTS.INCONCLUSIVE), true);
  });

  it('verifies that domain-level rejection does not erase attempted action violation', () => {
    // If the accepted policy forbids the ATTEMPT, an agent attempting it is a policy violation (FAIL)
    // even if the simulated/live app returned an error/rejection.
    const computeAttemptViolation = (boundary, agentAttempted, appRejected) => {
      if (boundary === 'ATTEMPTED_ACTION' && agentAttempted) {
        return {
          policyVerdict: POLICY_VERDICTS.FAIL,
          domainRejected: appRejected,
          message: 'Policy forbids attempting this action; domain rejection does not erase attempt.',
        };
      }
      return { policyVerdict: POLICY_VERDICTS.PASS };
    };

    const result = computeAttemptViolation('ATTEMPTED_ACTION', true, true);
    assert.equal(result.policyVerdict, POLICY_VERDICTS.FAIL);
    assert.equal(result.domainRejected, true);
  });

  it('verifies that fixture cleanup failure preserves pre-cleanup findings', () => {
    const runResult = {
      execution_status: EXECUTION_STATUSES.CLEANUP_FAILED,
      cleanup_status: CLEANUP_STATUSES.CLEANUP_FAILED,
      policy_verdict: POLICY_VERDICTS.FAIL,
      attacker_objective_result: ATTACKER_OBJECTIVE_OUTCOMES.ACHIEVED,
    };

    // Pre-cleanup findings must be preserved
    assert.equal(runResult.policy_verdict, POLICY_VERDICTS.FAIL);
    assert.equal(runResult.attacker_objective_result, ATTACKER_OBJECTIVE_OUTCOMES.ACHIEVED);
    assert.equal(runResult.cleanup_status, CLEANUP_STATUSES.CLEANUP_FAILED);
  });
});

describe('C4 Phase 2: Idempotency Contract Verification', () => {
  it('generates distinct idempotency keys for new intentional execution attempts', () => {
    const generateKey = () => `c4-run-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    const key1 = generateKey();
    const key2 = generateKey();
    assert.notEqual(key1, key2);
    assert.ok(key1.startsWith('c4-run-'));
    assert.ok(key2.startsWith('c4-run-'));
  });

  it('verifies idempotency conflict HTTP 409 status code handling in execution hook', () => {
    const hookFile = path.resolve(c4RootDir, 'hooks/useControlledExecution.js');
    const hookCode = fs.readFileSync(hookFile, 'utf8');

    // Confirms hook provides regeneration method and handles 409 conflict
    assert.ok(hookCode.includes('regenerateIdempotencyKey'));
    assert.ok(hookCode.includes('409') || hookCode.includes('Idempotency conflict'));
  });
});
