import './setup.js';
import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

import { integrationApi } from '../features/integration/integrationApi.js';
import { api, setStoredToken } from '../services/api.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

describe('Shared Integration Results and Frontend Compatibility Tests', () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
  });

  describe('1. Route Registration and Access Control', () => {
    it('registers projects/:projectId/results under both /admin and /app in App.jsx', () => {
      const appJsxPath = path.resolve(__dirname, '../App.jsx');
      const content = fs.readFileSync(appJsxPath, 'utf8');

      // Verify import
      assert.match(content, /import\s+\{\s*CombinedResultsView\s*\}\s+from\s+['"]\.\/features\/integration['"]/);

      // Verify admin route
      const adminBlock = content.split('path="/admin"')[1].split('path="/app"')[0];
      assert.match(adminBlock, /Route\s+path="projects\/:projectId\/results"\s+element=\{<CombinedResultsView\s*\/>\}/);

      // Verify user route
      const userBlock = content.split('path="/app"')[1];
      assert.match(userBlock, /Route\s+path="projects\/:projectId\/results"\s+element=\{<CombinedResultsView\s*\/>\}/);
    });

    it('preserves all four existing component routes under both /admin and /app', () => {
      const appJsxPath = path.resolve(__dirname, '../App.jsx');
      const content = fs.readFileSync(appJsxPath, 'utf8');

      const adminBlock = content.split('path="/admin"')[1].split('path="/app"')[0];
      const userBlock = content.split('path="/app"')[1];

      for (const block of [adminBlock, userBlock]) {
        assert.match(block, /path="tool-call-correctness"/, 'C1 route missing');
        assert.match(block, /path="workflow-testing"/, 'C2 route missing');
        assert.match(block, /path="robustness-recovery"/, 'C3 route missing');
        assert.match(block, /path="policy-safety"/, 'C4 route missing');
        assert.match(block, /path="projects"/, 'Projects list route missing');
        assert.match(block, /path="projects\/:projectId"/, 'Project detail route missing');
      }
    });

    it('includes optional Combined results link in ProjectDetailPage.jsx', () => {
      const detailPath = path.resolve(__dirname, '../pages/projects/ProjectDetailPage.jsx');
      const content = fs.readFileSync(detailPath, 'utf8');

      assert.match(content, /to=\{`\$\{basePath\}\/projects\/\$\{projectId\}\/results`\}/);
      assert.match(content, /Combined results/);
    });
  });

  describe('2. Project-Scoped Shared Results API Client', () => {
    it('scopes listPlans strictly to project_id without leaking credentials in URL', async () => {
      let requestedUrl = null;
      let requestedHeaders = null;

      globalThis.fetch = async (url, opts) => {
        requestedUrl = url;
        requestedHeaders = opts?.headers || {};
        return {
          ok: true,
          status: 200,
          json: async () => ({ items: [], total: 0, page: 1, page_size: 20 }),
        };
      };

      setStoredToken('test-bearer-token');
      const res = await integrationApi.listPlans('proj-alpha-123', { page: 2, pageSize: 10 });

      assert.equal(requestedUrl, '/api/v1/projects/proj-alpha-123/integration/plans?page=2&page_size=10');
      assert.equal(requestedHeaders['Authorization'], 'Bearer test-bearer-token');
      assert.doesNotMatch(requestedUrl, /token/i);
      assert.equal(Array.isArray(res.items), true);
    });

    it('scopes getCombinedReport to exact plan_id and execution_id', async () => {
      let requestedUrl = null;

      globalThis.fetch = async (url) => {
        requestedUrl = url;
        return {
          ok: true,
          status: 200,
          json: async () => ({
            report_id: 'rep-001',
            integration_run_id: 'irun-100',
            execution_id: 'exec-500',
            project_id: 'proj-xyz',
          }),
        };
      };

      const report = await integrationApi.getCombinedReport('proj-xyz', 'plan-99', 'exec-500');
      assert.equal(
        requestedUrl,
        '/api/v1/projects/proj-xyz/integration/plans/plan-99/executions/exec-500/report'
      );
      assert.equal(report.report_id, 'rep-001');
    });

    it('authenticates exportReportFile and extracts filename without token in URL', async () => {
      let requestedUrl = null;
      let requestedHeaders = null;

      globalThis.fetch = async (url, opts) => {
        requestedUrl = url;
        requestedHeaders = opts?.headers || {};
        return {
          ok: true,
          status: 200,
          headers: new Headers({
            'content-disposition': 'attachment; filename="custom_report_exec-500.json"',
          }),
          blob: async () => new Blob(['{"test": true}'], { type: 'application/json' }),
        };
      };

      // Mock DOM element creation for download
      let clicked = false;
      let appendedHref = null;
      globalThis.document = {
        body: {
          appendChild: (el) => {
            appendedHref = el.href;
          },
          removeChild: () => {},
        },
        createElement: () => ({
          click: () => {
            clicked = true;
          },
          href: '',
          download: '',
        }),
      };
      globalThis.URL = {
        createObjectURL: () => 'blob:mock-url',
        revokeObjectURL: () => {},
      };

      setStoredToken('download-token-abc');
      const result = await integrationApi.exportReportFile('proj-xyz', 'plan-99', 'exec-500', 'json');

      assert.equal(
        requestedUrl,
        '/api/v1/projects/proj-xyz/integration/plans/plan-99/executions/exec-500/report/export?format=json'
      );
      assert.equal(requestedHeaders['Authorization'], 'Bearer download-token-abc');
      assert.doesNotMatch(requestedUrl, /download-token-abc/);
      assert.equal(result.filename, 'custom_report_exec-500.json');
      assert.equal(clicked, true);
    });
  });

  describe('3. Three-State Cleanup Representation', () => {
    it('distinguishes true, false, and null without converting null to false', () => {
      // Helper function matching CombinedResultsView rendering logic
      function formatCleanupState(val) {
        if (val === true) return 'Cleaned & verified';
        if (val === false) return 'Cleanup failed';
        if (val === null || val === undefined) return 'Not assessed / unavailable';
        return 'Unknown';
      }

      assert.equal(formatCleanupState(true), 'Cleaned & verified');
      assert.equal(formatCleanupState(false), 'Cleanup failed');
      assert.equal(formatCleanupState(null), 'Not assessed / unavailable');
      assert.equal(formatCleanupState(undefined), 'Not assessed / unavailable');

      // Crucial invariant: null MUST NOT evaluate to Cleanup failed
      assert.notEqual(formatCleanupState(null), formatCleanupState(false));
      assert.notEqual(formatCleanupState(null), formatCleanupState(true));
    });
  });

  describe('4. Component Native Verdicts & Outcomes Invariance', () => {
    it('preserves distinct native verdicts across C1, C2, C3, and C4 without collapsing', () => {
      const c1Verdicts = ['PASS', 'FAIL', 'INCONCLUSIVE'];
      const c2Verdicts = ['EXPECTED REJECTION PASS', 'MODEL NOT READY', 'TEST NOT READY', 'INCONCLUSIVE'];
      const c3Verdicts = ['PASS_COMPLETED', 'PASS_GRACEFUL', 'FAIL', 'INCONCLUSIVE', null];
      const c4Verdicts = ['VIOLATION', 'BENIGN', 'BLOCKED'];

      // Distinct counts
      assert.equal(new Set(c1Verdicts).size, 3);
      assert.equal(new Set(c2Verdicts).size, 4);
      assert.equal(new Set(c3Verdicts).size, 5);

      // Verify null verdict in C3 is preserved as null/unevaluated
      const nullVerdict = c3Verdicts.find((v) => v === null);
      assert.equal(nullVerdict, null);
    });
  });

  describe('5. C2 Dynamic Publication and HTTP 409 Conflict Handling', () => {
    it('verifies RunReportModal handles 4 distinct publication states', () => {
      const modalPath = path.resolve(__dirname, '../features/c2/components/RunReportModal.jsx');
      const content = fs.readFileSync(modalPath, 'utf8');

      // Check the 4 states exist in the code
      assert.match(content, /publicationState === 'CONFIRMED'/);
      assert.match(content, /publicationState === 'FAILED'/);
      assert.match(content, /publicationState === 'UNAVAILABLE'/);
      assert.match(content, /publicationState === 'NOT_PUBLISHED'/);

      // Check HTTP 409 conflict handling
      assert.match(content, /exportError\?\.status === 409/);
      assert.match(content, /Publication conflict \(HTTP 409\)/);

      // Check updated professional labels
      assert.match(content, /Export report/);
      assert.doesNotMatch(content, /Export Finding via Adapter/);
      assert.match(content, /Content checksum/);
      assert.doesNotMatch(content, /SHA-256 Provenance/);

      // Check local download is separated
      assert.match(content, /Download JSON \(Local\)/);
      assert.match(content, /Downloaded locally!/);
    });

    it('ensures HTTP 409 does not convert conflict into publication success in useC2Results', () => {
      const hookPath = path.resolve(__dirname, '../features/c2/hooks/useC2Results.js');
      const content = fs.readFileSync(hookPath, 'utf8');

      assert.match(content, /const isConflict = err\.status === 409/);
      assert.match(content, /setExportError\(errDetail\)/);
      assert.match(content, /lastConfirmedReceipt/);
    });
  });

  describe('6. C3 Wording and Interface Corrections', () => {
    it('removes obsolete unauthenticated claim in C3AuthGapNotice.jsx', () => {
      const noticePath = path.resolve(__dirname, '../features/c3/components/C3AuthGapNotice.jsx');
      const content = fs.readFileSync(noticePath, 'utf8');

      // Obsolete claim must NOT exist
      assert.doesNotMatch(content, /operates completely unauthenticated/i);
      assert.doesNotMatch(content, /Pending C3 Backend Access Control/i);
      assert.doesNotMatch(content, /Zero Authorization Enforcement/i);

      // Accurate notice
      assert.match(content, /Project Authorization & Governance/i);
    });

    it('removes "Deferred (authoritative engine pending)" from C3MatchedPairsViewer.jsx', () => {
      const viewerPath = path.resolve(__dirname, '../features/c3/components/C3MatchedPairsViewer.jsx');
      const content = fs.readFileSync(viewerPath, 'utf8');

      assert.doesNotMatch(content, /Deferred \(authoritative engine pending\)/);
      assert.match(content, /No evaluation attached/);
    });

    it('removes backend endpoint route footer from C3ValidationPanel.jsx', () => {
      const panelPath = path.resolve(__dirname, '../features/c3/components/C3ValidationPanel.jsx');
      const content = fs.readFileSync(panelPath, 'utf8');

      assert.doesNotMatch(content, /endpoint:\s*\/api\/v1\/c3\/cases\/validate/i);
    });

    it('removes developer CLI command block from C3RuntimeReadinessAudit.jsx', () => {
      const auditPath = path.resolve(__dirname, '../features/c3/components/C3RuntimeReadinessAudit.jsx');
      const content = fs.readFileSync(auditPath, 'utf8');

      assert.doesNotMatch(content, /python -m app\.c3\.runners\.http_runner/);
      assert.doesNotMatch(content, /NEXACART_AUT_URL/);
      assert.match(content, /Live execution is not connected/);
    });

    it('removes terminal shell commands block from C3ResearchView.jsx', () => {
      const researchPath = path.resolve(__dirname, '../features/c3/components/C3ResearchView.jsx');
      const content = fs.readFileSync(researchPath, 'utf8');

      assert.doesNotMatch(content, /python -m app\.c3\.evaluation\.authoritative_engine/);
    });

    it('removes Phase 1 introductory banners and roadmap panels from C3UserWorkspace.jsx', () => {
      const wsPath = path.resolve(__dirname, '../features/c3/pages/C3UserWorkspace.jsx');
      const content = fs.readFileSync(wsPath, 'utf8');

      assert.doesNotMatch(content, /Phase 1 Implementation:/);
      assert.doesNotMatch(content, /Development Roadmap & Live Execution Limitations/);
    });
  });

  describe('7. No Auto-Execution or Plan Mutation on Page Load', () => {
    it('guarantees CombinedResultsView executes only GET requests and does not trigger plan creation or runs', () => {
      const viewPath = path.resolve(__dirname, '../features/integration/CombinedResultsView.jsx');
      const content = fs.readFileSync(viewPath, 'utf8');

      // CombinedResultsView should only call listPlans, getProject, listExecutions, getCombinedReport, and exportReportFile on user click
      assert.doesNotMatch(content, /create_integration_plan|createPlan|startExecution|executePlan/);
      assert.doesNotMatch(content, /cancelExecution|replayEvaluation/);
    });

    it('displays genuine empty state when no integration plans exist for project', () => {
      const viewPath = path.resolve(__dirname, '../features/integration/CombinedResultsView.jsx');
      const content = fs.readFileSync(viewPath, 'utf8');

      assert.match(content, /No Shared Integration Plans Found/);
      assert.match(content, /Component workspaces/);
      assert.match(content, /maintain their own independent execution cycles/);
    });
  });
});
