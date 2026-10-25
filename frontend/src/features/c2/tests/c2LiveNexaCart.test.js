import '../../../tests/setup.js';
import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { c2Api } from '../api/c2Api.js';
import { PROVENANCE_CONFIG } from '../constants/resultsConfig.js';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const source = (rel) => fs.readFileSync(path.resolve(here, rel), 'utf8');

describe('Component 2: live NexaCart workflow execution', () => {
  let captured = [];

  beforeEach(() => {
    captured = [];
    globalThis.fetch = async (url, options = {}) => {
      captured.push({ url, options });
      if (url.includes('/executions') && options.method === 'POST') {
        return {
          ok: true,
          status: 202,
          json: async () => ({ execution_id: 'c2x-abc', status: 'RUNNING', planned_test_ids: ['TC-1'] }),
        };
      }
      if (url.includes('/readiness')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({ ready: true, harness_version: '1.0.0', agent: { provider: 'OLLAMA' }, tools: [] }),
        };
      }
      return { ok: true, status: 200, json: async () => [] };
    };
  });

  it('checks readiness and lists reference workflows under the project scope', async () => {
    const ready = await c2Api.getLiveReadiness('proj 1');
    assert.equal(ready.ready, true);
    await c2Api.listLiveWorkflows('proj 1');
    assert.match(captured[0].url, /\/api\/v1\/c2\/projects\/proj%201\/live\/nexacart\/readiness$/);
    assert.match(captured[1].url, /\/api\/v1\/c2\/projects\/proj%201\/live\/nexacart\/workflows$/);
  });

  it('imports a reference workflow as a draft', async () => {
    await c2Api.importLiveWorkflow('p1', 'nxc_cancel_then_refund');
    assert.equal(captured[0].options.method, 'POST');
    assert.match(captured[0].url, /\/live\/nexacart\/workflows\/nxc_cancel_then_refund\/import$/);
  });

  it('starts a live execution with the selected cases and polls it', async () => {
    const rec = await c2Api.startLiveExecution('p1', { suiteId: 's1', testIds: ['TC-1', 'TC-2'] });
    assert.equal(rec.status, 'RUNNING');
    assert.deepEqual(JSON.parse(captured[0].options.body), { suite_id: 's1', test_ids: ['TC-1', 'TC-2'] });

    await c2Api.startLiveExecution('p1', { suiteId: 's1', testIds: [] });
    assert.deepEqual(JSON.parse(captured[1].options.body), { suite_id: 's1', test_ids: null });

    await c2Api.getLiveExecution('p1', 'c2x-abc');
    await c2Api.listLiveExecutions('p1', 's1');
    assert.match(captured[2].url, /\/live\/nexacart\/executions\/c2x-abc$/);
    assert.match(captured[3].url, /\/live\/nexacart\/executions\?suite_id=s1$/);
  });

  it('rejects calls without the required identifiers', async () => {
    await assert.rejects(() => c2Api.getLiveReadiness(''), /projectId/);
    await assert.rejects(() => c2Api.startLiveExecution('p1', {}), /suiteId/);
    assert.equal(captured.length, 0);
  });

  it('labels live NexaCart runs and live-trace mutants honestly', () => {
    assert.equal(PROVENANCE_CONFIG.live_nexacart_agent.isLive, true);
    assert.equal(PROVENANCE_CONFIG.live_trace_mutation.isLive, false);
    assert.match(PROVENANCE_CONFIG.live_trace_mutation.description, /not an observed agent failure/);
  });

  it('keeps suite detail, cases and case detail loads from cancelling each other', () => {
    const hook = source('../hooks/useC2Suites.js');
    assert.equal(hook.includes('generationRef'), false);
    for (const ref of ['suitesGenRef', 'suiteDetailGenRef', 'casesGenRef', 'caseDetailGenRef']) {
      assert.equal(hook.includes(`const ${ref} = useRef(0)`), true, ref);
    }
    // a case selected in the previous suite is not requested from the new one
    assert.equal(hook.includes('selectedCaseSummary.suite_id !== suiteId'), true);
  });

  it('shows planned coverage with the field names the generator returns', () => {
    const view = source('../components/TestCaseListView.jsx');
    for (const key of ['coverage_percentage', 'covered_transitions_count', 'covered_guards_count', 'total_guards_defined', 'planned_guard_outcome_coverage_pct']) {
      assert.equal(view.includes(key), true, key);
    }
  });

  it('compares generation budgets as numbers and preselects the approved model', () => {
    const modal = source('../components/TestSuiteGeneratorModal.jsx');
    assert.match(modal, /Number\(mutationBudget\) > Number\(caseBudget\)/);
    assert.match(modal, /if \(!selectedModelId && defaultModel\)/);
  });
});
