import '../../../tests/setup.js';
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  c3Api,
  FAULT_FAMILIES,
  EFFECT_PHASES,
  INTERCEPTION_HOOKS,
} from '../api.js';
import {
  DEMO_ADAPTER_MANIFEST,
  DEMO_TASK_FIXTURE_METADATA,
  DEMO_RECOVERY_CONTRACT,
  DEMO_GENERATION_POLICY,
  DEMO_CANDIDATE_CASE_VALID,
  DEMO_CANDIDATE_CASE_REJECTED,
  DEMONSTRATION_FROZEN_SUITE,
} from '../fixtures.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

describe('Component 3: Robustness and Failure Recovery Frontend Tests', () => {
  describe('1. API Endpoint Mappings and Contracts', () => {
    it('defines exactly the five operational fault families without treating duplicate effects as a fault family', () => {
      const expectedFamilies = [
        'TIMEOUT_DISCONNECTION',
        'TRANSIENT_5XX',
        'RATE_LIMIT_429',
        'TOOL_UNAVAILABILITY',
        'MALFORMED_RESPONSE',
      ];
      const actualKeys = Object.keys(FAULT_FAMILIES);

      assert.equal(actualKeys.length, 5);
      for (const fam of expectedFamilies) {
        assert.equal(actualKeys.includes(fam), true, `Missing expected fault family: ${fam}`);
      }

      // Explicit rule: Duplicate side effects are NOT an operational fault family
      assert.equal(actualKeys.includes('DUPLICATE_EFFECTS'), false);
      assert.equal(actualKeys.includes('DUPLICATE_SIDE_EFFECTS'), false);
      assert.equal(actualKeys.includes('DUPLICATE_CALLS'), false);
    });

    it('defines the four operational effect phases', () => {
      const expectedPhases = [
        'BEFORE_EFFECT',
        'AFTER_COMMIT',
        'PARTIAL_EFFECT',
        'NOT_APPLICABLE',
      ];
      const actualPhases = Object.keys(EFFECT_PHASES);

      assert.equal(actualPhases.length, 4);
      for (const phase of expectedPhases) {
        assert.equal(actualPhases.includes(phase), true, `Missing effect phase: ${phase}`);
      }
    });

    it('enforces required project_id on all persistence API operations', async () => {
      await assert.rejects(
        async () => c3Api.importSuite(null, {}),
        /Project ID is required/
      );
      await assert.rejects(
        async () => c3Api.listSuites('', {}),
        /Project ID is required/
      );
      await assert.rejects(
        async () => c3Api.getSuite(null, 'suite-1'),
        /Project ID is required/
      );
      await assert.rejects(
        async () => c3Api.listCases(undefined, {}),
        /Project ID is required/
      );
      await assert.rejects(
        async () => c3Api.getCase(null, 'case-1'),
        /Project ID is required/
      );
    });
  });

  describe('2. Project Context and Demonstration Scope Safeguards', () => {
    it('never uses the demonstration project default (proj-demo-qa) in place of the selected project in api calls', async () => {
      const apiCode = fs.readFileSync(path.resolve(__dirname, '../api.js'), 'utf8');

      // api.js must strictly require caller-provided projectId
      assert.equal(apiCode.includes('proj-demo-qa'), false, 'api.js should not hardcode proj-demo-qa');
    });

    it('candidate case fixtures declare matching fault_family and payload.family', () => {
      assert.equal(
        DEMO_CANDIDATE_CASE_VALID.fault_family,
        DEMO_CANDIDATE_CASE_VALID.payload.family
      );
      assert.equal(
        DEMO_CANDIDATE_CASE_REJECTED.fault_family,
        DEMO_CANDIDATE_CASE_REJECTED.payload.family
      );
    });

    it('recovery contract satisfies attempt-retry budget consistency rule', () => {
      // Rule: When initial_invocation_counts_as_attempt is true, max_task_attempts == 1 + max_retries
      assert.equal(DEMO_RECOVERY_CONTRACT.initial_invocation_counts_as_attempt, true);
      assert.equal(
        DEMO_RECOVERY_CONTRACT.max_task_attempts,
        1 + DEMO_RECOVERY_CONTRACT.max_retries,
        'max_task_attempts must equal 1 + max_retries'
      );
    });

    it('strictly forbids credentials, API keys, or database connection strings in contracts and fixtures', () => {
      const fixtureCode = fs.readFileSync(path.resolve(__dirname, '../fixtures.js'), 'utf8');
      const lowered = fixtureCode.toLowerCase();

      const forbiddenTokens = [
        'password',
        'api_key',
        'secret_key',
        'bearer_token',
        'postgresql://',
        'postgres://',
        'drop table',
        '<script',
      ];

      for (const token of forbiddenTokens) {
        assert.equal(
          lowered.includes(token),
          false,
          `Forbidden sensitive token found in fixture: ${token}`
        );
      }
    });
  });

  describe('3. Frozen Suite Integrity and Digest Standards', () => {
    it('verifies canonical 64-character SHA-256 suite digest in demonstration frozen suite', () => {
      assert.ok(DEMONSTRATION_FROZEN_SUITE.suite_digest);
      assert.equal(
        DEMONSTRATION_FROZEN_SUITE.suite_digest.length,
        64,
        'suite_digest must be a 64-character SHA-256 hex string'
      );
      assert.match(DEMONSTRATION_FROZEN_SUITE.suite_digest, /^[a-f0-9]{64}$/);
    });

    it('verifies semantic case fingerprints for all selected cases in frozen suite', () => {
      const { selected_cases, case_fingerprints } = DEMONSTRATION_FROZEN_SUITE;
      assert.ok(selected_cases.length > 0);

      for (const c of selected_cases) {
        assert.ok(
          case_fingerprints[c.case_id],
          `Missing fingerprint for case: ${c.case_id}`
        );
        assert.equal(
          case_fingerprints[c.case_id].length,
          64,
          `Case fingerprint must be 64-char SHA-256: ${c.case_id}`
        );
      }
    });

    it('confirms separate accounting counters in generation policy and results', () => {
      const { counters } = DEMONSTRATION_FROZEN_SUITE;
      assert.ok('examined_count' in counters);
      assert.ok('valid_count' in counters);
      assert.ok('rejected_count' in counters);
      assert.ok('duplicate_count' in counters);
      assert.ok('unique_count' in counters);
      assert.ok('selected_count' in counters);
      assert.ok('truncated' in counters);
      assert.equal(counters.selected_count, DEMONSTRATION_FROZEN_SUITE.selected_cases.length);
    });
  });

  describe('4. Dashboard Cards and Role Route Links', () => {
    it('verifies User Dashboard mounts C3DashboardCard with role USER and correct route targets', () => {
      const userDashboardPath = path.resolve(
        __dirname,
        '../../../pages/user/UserDashboard.jsx'
      );
      const userDashCode = fs.readFileSync(userDashboardPath, 'utf8');

      assert.equal(
        userDashCode.includes('C3DashboardCard'),
        true,
        'UserDashboard must import and render C3DashboardCard'
      );
      assert.equal(
        userDashCode.includes('role="USER"'),
        true,
        'UserDashboard must pass role="USER"'
      );
      assert.equal(
        userDashCode.includes('/app/robustness-recovery'),
        true,
        'UserDashboard must preserve route to /app/robustness-recovery'
      );
    });

    it('verifies Admin Dashboard mounts C3DashboardCard with role ADMIN and correct route targets', () => {
      const adminDashboardPath = path.resolve(
        __dirname,
        '../../../pages/admin/AdminDashboard.jsx'
      );
      const adminDashCode = fs.readFileSync(adminDashboardPath, 'utf8');

      assert.equal(
        adminDashCode.includes('C3DashboardCard'),
        true,
        'AdminDashboard must import and render C3DashboardCard'
      );
      assert.equal(
        adminDashCode.includes('role="ADMIN"'),
        true,
        'AdminDashboard must pass role="ADMIN"'
      );
      assert.equal(
        adminDashCode.includes('/admin/robustness-recovery'),
        true,
        'AdminDashboard must preserve route to /admin/robustness-recovery'
      );
    });

    it('verifies C3DashboardCard renders full title, project scope, and both action links', () => {
      const cardPath = path.resolve(
        __dirname,
        '../components/C3DashboardCard.jsx'
      );
      const cardCode = fs.readFileSync(cardPath, 'utf8');

      assert.equal(
        cardCode.includes('Robustness and Failure Recovery Testing'),
        true,
        'Must display full C3 title'
      );
      assert.equal(
        cardCode.includes('Open Workspace'),
        true,
        'Must include Open Workspace link'
      );
      assert.equal(
        cardCode.includes('Prepare Cases'),
        true,
        'Must include Prepare Cases link'
      );
      assert.equal(
        cardCode.includes('Unavailable (DB Offline)'),
        true,
        'Must explicitly handle unavailable DB state without fabricating zero'
      );
    });

    it('verifies App.jsx registers both C3 role routes under respective layouts', () => {
      const appPath = path.resolve(__dirname, '../../../App.jsx');
      const appCode = fs.readFileSync(appPath, 'utf8');

      assert.equal(appCode.includes('C3AdminWorkspace'), true);
      assert.equal(appCode.includes('C3UserWorkspace'), true);
      assert.equal(appCode.includes('Robustness and Failure Recovery Testing'), true);
      assert.equal(appCode.includes('path="robustness-recovery"'), true);
    });
  });
});
