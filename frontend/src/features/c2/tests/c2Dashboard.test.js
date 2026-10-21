import '../../../tests/setup.js';
import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { c2Api } from '../api/c2Api.js';
import { C2_VERDICTS, VERDICT_CONFIG, PROVENANCE_CONFIG } from '../constants/resultsConfig.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

describe('Component 2 Dashboard Integration & Metrics Summary', () => {
  let capturedRequests = [];

  beforeEach(() => {
    capturedRequests = [];
    globalThis.fetch = async (url, options = {}) => {
      capturedRequests.push({ url, options });

      if (url.includes('/models')) {
        return {
          ok: true,
          status: 200,
          json: async () => [
            {
              id: 'rec_1',
              project_id: 'proj_alpha',
              model_id: 'model_refund',
              version: '1.0.0',
              lifecycle_status: 'APPROVED',
            },
            {
              id: 'rec_2',
              project_id: 'proj_alpha',
              model_id: 'model_refund',
              version: '1.1.0-draft',
              lifecycle_status: 'DRAFT',
            },
            {
              id: 'rec_3',
              project_id: 'proj_alpha',
              model_id: 'model_checkout',
              version: '1.0.0',
              lifecycle_status: 'APPROVED',
            },
          ],
        };
      }

      if (url.includes('/suites')) {
        return {
          ok: true,
          status: 200,
          json: async () => [
            { id: 1, suite_id: 'suite_001', total_cases: 20 },
            { id: 2, suite_id: 'suite_002', total_cases: 15 },
          ],
        };
      }

      if (url.includes('/evaluations')) {
        return {
          ok: true,
          status: 200,
          json: async () => [
            {
              evaluation_id: 'eval_old',
              test_id: 'case_001',
              verdict: 'FAIL',
              actual_execution_origin: 'controlled_trace_fixture',
              created_at: '2026-10-21T10:00:00Z',
            },
            {
              evaluation_id: 'eval_latest',
              test_id: 'case_002',
              verdict: 'EXPECTED REJECTION PASS',
              actual_execution_origin: 'scripted_synthetic_demonstration',
              created_at: '2026-10-21T15:30:00Z',
            },
          ],
        };
      }

      return {
        ok: true,
        status: 200,
        json: async () => ({}),
      };
    };
  });

  it('verifies UserDashboard and AdminDashboard both import and branch on C2DashboardCard', () => {
    const userDashPath = path.resolve(__dirname, '../../../pages/user/UserDashboard.jsx');
    const adminDashPath = path.resolve(__dirname, '../../../pages/admin/AdminDashboard.jsx');

    const userContent = fs.readFileSync(userDashPath, 'utf8');
    const adminContent = fs.readFileSync(adminDashPath, 'utf8');

    // Both must import C2DashboardCard
    assert.ok(
      userContent.includes("import { C2DashboardCard } from '../../features/c2/components/C2DashboardCard'"),
      'UserDashboard.jsx must import C2DashboardCard'
    );
    assert.ok(
      adminContent.includes("import { C2DashboardCard } from '../../features/c2/components/C2DashboardCard'"),
      'AdminDashboard.jsx must import C2DashboardCard'
    );

    // Both must branch on 'State-Aware Multi-Step Workflow Testing'
    assert.ok(
      userContent.includes("comp.name === 'State-Aware Multi-Step Workflow Testing'"),
      'UserDashboard.jsx must branch on State-Aware Multi-Step Workflow Testing'
    );
    assert.ok(
      adminContent.includes("comp.name === 'State-Aware Multi-Step Workflow Testing'"),
      'AdminDashboard.jsx must branch on State-Aware Multi-Step Workflow Testing'
    );

    // Verify role-correct prop passing
    assert.ok(userContent.includes('role="USER"'), 'UserDashboard must pass role="USER"');
    assert.ok(adminContent.includes('role="ADMIN"'), 'AdminDashboard must pass role="ADMIN"');
  });

  it('guarantees role-correct workspace and projects links without invented parameters', () => {
    const cardPath = path.resolve(__dirname, '../components/C2DashboardCard.jsx');
    const cardContent = fs.readFileSync(cardPath, 'utf8');

    // Role-correct workspace paths
    assert.ok(cardContent.includes('/admin/workflow-testing'), 'C2DashboardCard must support admin workspace link');
    assert.ok(cardContent.includes('/app/workflow-testing'), 'C2DashboardCard must support user workspace link');

    // Role-correct project paths when no project is selected
    assert.ok(cardContent.includes('/admin/projects'), 'C2DashboardCard must support admin projects link');
    assert.ok(cardContent.includes('/app/projects'), 'C2DashboardCard must support user projects link');

    // Explicit empty-project notice
    assert.ok(
      cardContent.includes('Select a project to view workflow testing.'),
      'C2DashboardCard must show clear empty project notice'
    );
  });

  it('guarantees no API requests are issued when no project is active', async () => {
    // Calling dashboard functions with empty/null projectId should throw or not issue requests
    await assert.rejects(async () => {
      await c2Api.listModels(null);
    }, /projectId is required/);

    await assert.rejects(async () => {
      await c2Api.listTestSuites(null);
    }, /projectId is required/);

    await assert.rejects(async () => {
      await c2Api.listEvaluations(null);
    }, /projectId is required/);

    assert.equal(capturedRequests.length, 0, 'No HTTP requests should be dispatched when projectId is missing');
  });

  it('correctly calculates unique models, total versions, and approved versions from API responses', async () => {
    const models = await c2Api.listModels('proj_alpha');
    assert.equal(models.length, 3, 'Total model versions count is 3');

    const uniqueModels = new Set(models.map((m) => m.model_id));
    assert.equal(uniqueModels.size, 2, 'Unique model count must distinguish duplicate model_id versions (2 unique)');

    const approvedModels = models.filter((m) => m.lifecycle_status === 'APPROVED');
    assert.equal(approvedModels.length, 2, 'Approved model-versions count is 2');
  });

  it('correctly extracts the latest evaluation chronologically', async () => {
    const evaluations = await c2Api.listEvaluations('proj_alpha');
    assert.equal(evaluations.length, 2);

    const sorted = [...evaluations].sort((a, b) => {
      const timeA = new Date(a.evaluated_at || a.created_at || 0).getTime();
      const timeB = new Date(b.evaluated_at || b.created_at || 0).getTime();
      return timeB - timeA;
    });

    const latest = sorted[0];
    assert.equal(latest.evaluation_id, 'eval_latest');
    assert.equal(latest.verdict, 'EXPECTED REJECTION PASS');
    assert.equal(latest.actual_execution_origin, 'scripted_synthetic_demonstration');
  });

  it('distinguishes empty successful responses from API failures', async () => {
    globalThis.fetch = async (url) => {
      if (url.includes('/models')) {
        return { ok: true, status: 200, json: async () => [] };
      }
      if (url.includes('/suites')) {
        return { ok: false, status: 503, json: async () => ({ detail: 'Database error' }) };
      }
      if (url.includes('/evaluations')) {
        return { ok: true, status: 200, json: async () => [] };
      }
      return { ok: true, status: 200, json: async () => ({}) };
    };

    // Models returned empty list successfully -> count is 0
    const models = await c2Api.listModels('proj_alpha');
    assert.equal(models.length, 0, 'Empty response returns 0 models');

    // Suites returned 503 error -> throws ApiError
    await assert.rejects(async () => {
      await c2Api.listTestSuites('proj_alpha');
    });

    // Evaluations returned empty list successfully -> count is 0
    const evaluations = await c2Api.listEvaluations('proj_alpha');
    assert.equal(evaluations.length, 0, 'Empty response returns 0 evaluations');
  });

  it('verifies all six runtime verdicts and execution provenances are defined for the card', () => {
    const requiredVerdicts = [
      'PASS',
      'EXPECTED REJECTION PASS',
      'FAIL',
      'INCONCLUSIVE',
      'MODEL NOT READY',
      'TEST NOT READY',
    ];

    for (const v of requiredVerdicts) {
      assert.ok(VERDICT_CONFIG[v], `VERDICT_CONFIG must configure verdict "${v}"`);
      assert.ok(VERDICT_CONFIG[v].badgeText, `Verdict "${v}" must define text badge`);
    }

    assert.equal(C2_VERDICTS.length, 6);
    assert.ok(PROVENANCE_CONFIG.live_agent_run);
    assert.ok(PROVENANCE_CONFIG.scripted_synthetic_demonstration);
    assert.ok(PROVENANCE_CONFIG.controlled_trace_fixture);
  });
});
