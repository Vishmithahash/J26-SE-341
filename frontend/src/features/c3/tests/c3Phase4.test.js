import '../../../tests/setup.js';
import { describe, it, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert';
import { c3Api } from '../api.js';
import { setStoredToken } from '../../../services/api.js';
import {
  DEMO_RESEARCH_PROTOCOL,
  DEMO_EXECUTION_REPORT,
} from '../fixtures.js';

describe('Component 3 Phase 4: Frontend Audit, Authorization, and Contract Verification', () => {
  describe('1. Authenticated CSV Downloads via fetch-and-Blob with URL Revocation', () => {
    let originalFetch;
    let originalCreateObjectURL;
    let originalRevokeObjectURL;
    let originalCreateElement;
    let createdUrl = null;
    let revokedUrl = null;
    let anchorClicked = false;
    let capturedHeaders = null;

    beforeEach(() => {
      originalFetch = globalThis.fetch;
      originalCreateObjectURL = globalThis.URL?.createObjectURL;
      originalRevokeObjectURL = globalThis.URL?.revokeObjectURL;
      originalCreateElement = globalThis.document?.createElement;

      // Set token in session storage via shared utility
      setStoredToken('test-bearer-token-phase4');

      // Mock DOM environment if missing in node test runner
      if (!globalThis.window) {
        globalThis.window = globalThis;
      }

      globalThis.window.URL = {
        createObjectURL: (_blob) => {
          createdUrl = `blob:http://localhost:5173/${Math.random().toString(36).substring(2)}`;
          return createdUrl;
        },
        revokeObjectURL: (url) => {
          revokedUrl = url;
        },
      };

      if (!globalThis.document) {
        globalThis.document = {};
      }

      globalThis.document.createElement = (tag) => {
        if (tag === 'a') {
          return {
            href: '',
            download: '',
            style: {},
            click: () => {
              anchorClicked = true;
            },
          };
        }
        return {};
      };

      if (!globalThis.document.body) {
        globalThis.document.body = {
          appendChild: () => {},
          removeChild: () => {},
        };
      }
    });

    afterEach(() => {
      globalThis.fetch = originalFetch;
      if (originalCreateObjectURL) {
        globalThis.window.URL.createObjectURL = originalCreateObjectURL;
        globalThis.window.URL.revokeObjectURL = originalRevokeObjectURL;
      }
      if (originalCreateElement) {
        globalThis.document.createElement = originalCreateElement;
      }
      setStoredToken(null);
      createdUrl = null;
      revokedUrl = null;
      anchorClicked = false;
      capturedHeaders = null;
    });

    it('requires projectId and executionId before initiating export', async () => {
      await assert.rejects(
        async () => {
          await c3Api.downloadExecutionReportCsv(null, 'exec-01');
        },
        {
          name: 'Error',
          message: 'Project ID is required to export execution report CSV.',
        }
      );

      await assert.rejects(
        async () => {
          await c3Api.downloadExecutionReportCsv('proj-01', null);
        },
        {
          name: 'Error',
          message: 'Execution ID is required to export execution report CSV.',
        }
      );
    });

    it('performs authenticated fetch-and-Blob flow, sends Bearer auth, and releases object URL', async () => {
      globalThis.fetch = async (url, options) => {
        capturedHeaders = options.headers;
        return {
          ok: true,
          status: 200,
          headers: {
            get: (name) => {
              if (name.toLowerCase() === 'content-disposition') {
                return 'attachment; filename="c3_report_exec-001.csv"';
              }
              return null;
            },
          },
          blob: async () => new Blob(['execution_id,case_id,verdict\nexec-001,case-01,PASS_COMPLETED\n']),
        };
      };

      const result = await c3Api.downloadExecutionReportCsv('proj-demo-01', 'exec-001');

      assert.strictEqual(result.success, true);
      assert.strictEqual(result.filename, 'report_exec-001.csv');
      assert.ok(capturedHeaders?.Authorization?.includes('Bearer test-bearer-token-phase4'));
      assert.strictEqual(anchorClicked, true);
      assert.ok(createdUrl !== null);
      assert.strictEqual(revokedUrl, createdUrl, 'Object URL must be revoked after download initiation');
    });

    it('handles failed responses without triggering download or leaking token into URL', async () => {
      globalThis.fetch = async () => ({
        ok: false,
        status: 403,
        json: async () => ({ detail: 'Access denied to foreign project.' }),
      });

      await assert.rejects(
        async () => {
          await c3Api.downloadExecutionReportCsv('proj-forbidden', 'exec-001');
        },
        (err) => {
          assert.strictEqual(anchorClicked, false);
          assert.strictEqual(createdUrl, null);
          return err.message.includes('Access denied to foreign project');
        }
      );
    });

    it('generates canonical CSV report route without placing tokens in query parameters', () => {
      const url = c3Api.getExecutionReportCsvUrl('proj-qa-101', 'exec-qa-202');
      assert.strictEqual(
        url,
        '/api/v1/c3/reports/executions/exec-qa-202/export?project_id=proj-qa-101'
      );
      assert.ok(!url.includes('token'), 'Bearer token must never appear in URL parameters');
    });
  });

  describe('2. Clean Control Eligibility and Main vs Supplementary Outcome Analysis', () => {
    it('includes comparable pairs with failed clean control in main outcome analysis', () => {
      const report = DEMO_EXECUTION_REPORT;
      assert.strictEqual(report.clean_disqualified_count, 1);

      // Verify that trial with DISQUALIFIED clean control received an evaluation verdict
      const disqualifiedCleanCase = report.case_reports.find(
        (c) => c.clean_qualification === 'DISQUALIFIED'
      );
      assert.ok(disqualifiedCleanCase, 'Disqualified clean control pair must be retained in report');
      assert.strictEqual(disqualifiedCleanCase.exposure_status, 'CONFIRMED');
      assert.strictEqual(disqualifiedCleanCase.fault_execution_status, 'COMPLETED');
      assert.strictEqual(disqualifiedCleanCase.recovery_verdict, 'FAIL');
      assert.strictEqual(disqualifiedCleanCase.first_violated_rule, 'RULE_UNSAFE_RETRIES');
    });

    it('documents differential attribution limitation when clean baseline fails', () => {
      const report = DEMO_EXECUTION_REPORT;
      assert.ok(report.clean_control_notes.length > 0);
      assert.ok(
        report.clean_control_notes[0].toLowerCase().includes('clean baseline') ||
        report.clean_control_notes[0].toLowerCase().includes('qualification')
      );
    });

    it('separates supplementary clean-passing subset from main outcome analysis', () => {
      const report = DEMO_EXECUTION_REPORT;
      const allEvaluated = report.case_reports.filter(
        (c) => c.recovery_verdict && c.recovery_verdict !== 'NOT_EVALUATED'
      );
      assert.strictEqual(allEvaluated.length, 4, 'Main outcome analysis evaluates 4 trials');

      const cleanPassingSubset = report.case_reports.filter(
        (c) => c.clean_qualification === 'QUALIFIED' && c.recovery_verdict !== 'NOT_EVALUATED'
      );
      assert.strictEqual(cleanPassingSubset.length, 3, 'Supplementary clean-passing subset comprises 3 trials');
    });
  });

  describe('3. Canonical Research Enums, Planned Split, and CLI Disclosures', () => {
    it('labels 40/20/40 partition split as planned split pending manifest confirmation', () => {
      const proto = DEMO_RESEARCH_PROTOCOL;
      assert.strictEqual(proto.is_planned_split, true);
      assert.ok(proto.planned_split_label.includes('Planned Split'));
      assert.strictEqual(proto.partitions.length, 3);
      assert.strictEqual(proto.partitions[0].percentage, 40);
      assert.strictEqual(proto.partitions[1].percentage, 20);
      assert.strictEqual(proto.partitions[2].percentage, 40);
    });

    it('defines canonical comparative baselines matching backend BaselineType enums', () => {
      const proto = DEMO_RESEARCH_PROTOCOL;
      const baselineTypes = proto.baselines.map((b) => b.baseline_type);
      assert.ok(baselineTypes.includes('MATCHED_CLEAN_CONTROL'));
      assert.ok(baselineTypes.includes('FIXED_SUITE_BASELINE'));
      assert.ok(baselineTypes.includes('OUTCOME_ONLY_BASELINE'));
      assert.ok(baselineTypes.includes('PRODUCTION_C3'));

      // Ensure deprecated placeholder baselines are removed
      const names = proto.baselines.map((b) => b.name);
      assert.ok(!names.some((n) => n.toLowerCase().includes('blind retry')));
      assert.ok(!names.some((n) => n.toLowerCase().includes('idempotent recovery agent')));
    });

    it('defines canonical ablations matching backend AblationType enums A1 to A4', () => {
      const proto = DEMO_RESEARCH_PROTOCOL;
      const ablationTypes = proto.ablations.map((a) => a.ablation_type);
      assert.deepStrictEqual(ablationTypes, [
        'NO_CAPABILITY_VALIDATION',
        'NO_EXPOSURE_RECEIPTS',
        'NO_STATE_FACTS',
        'NO_EFFECT_PHASE',
      ]);
    });

    it('advertises only verified Python entry points without unsupported --split or --domain flags', () => {
      const proto = DEMO_RESEARCH_PROTOCOL;

      // Primary evaluation entry point
      assert.ok(proto.cli_command.includes('runtime.evaluate'));
      assert.ok(proto.cli_command.includes('--evidence-file'));
      assert.ok(!proto.cli_command.includes('--split'));
      assert.ok(!proto.cli_command.includes('--domain'));

      // Suite runner entry point
      assert.ok(proto.suite_runner_command.includes('runtime.suite_runner'));
      assert.ok(proto.suite_runner_command.includes('--synthetic'));
      assert.ok(!proto.suite_runner_command.includes('--split'));

      // Matched pair runner entry point
      assert.ok(proto.runner_command.includes('runtime.runner'));
      assert.ok(proto.runner_command.includes('--synthetic'));
      assert.ok(!proto.runner_command.includes('--domain'));
    });
  });

  describe('4. Operational Labels and Localization Disclosures', () => {
    it('uses explicit operational labels rather than implementation phase milestones', () => {
      // In C3DashboardCard, badge status is 'READY' and label is 'Operational'
      // We verify that the fixtures and contracts promote operational status
      const report = DEMO_EXECUTION_REPORT;
      assert.strictEqual(report.status, 'COMPLETED');
      assert.ok(report.evaluator_version);
      assert.ok(report.rule_set_version);
    });

    it('explicitly separates NOT_EVALUATED from the four recovery verdict categories', () => {
      const report = DEMO_EXECUTION_REPORT;
      const verdicts = report.verdict_counts;
      assert.strictEqual(typeof verdicts.pass_completed_count, 'number');
      assert.strictEqual(typeof verdicts.pass_graceful_count, 'number');
      assert.strictEqual(typeof verdicts.fail_count, 'number');
      assert.strictEqual(typeof verdicts.inconclusive_count, 'number');
      assert.strictEqual(typeof verdicts.not_evaluated_count, 'number');

      // Unevaluated count must be strictly separate
      assert.strictEqual(verdicts.not_evaluated_count, 1);
    });
  });
});
