import '../../../tests/setup.js';
import { describe, it, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { c4Api } from '../api/c4Api.js';
import { isLiveExecutionFinished, formatRate, REPETITION_OPTIONS } from '../hooks/useNexaCartLive.js';

const c4RootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

describe('Component 4: live NexaCart policy testing', () => {
  let captured = [];

  beforeEach(() => {
    captured = [];
    globalThis.fetch = async (url, options = {}) => {
      captured.push({ url, options });
      if (url.includes('/executions') && options.method === 'POST') {
        return { ok: true, status: 202, json: async () => ({ execution_id: 'c4x-1', status: 'RUNNING', total_cases: 7, completed_cases: 0 }) };
      }
      return { ok: true, status: 200, json: async () => ({ is_ready: true, status: 'READY', tools: [] }) };
    };
  });

  it('checks readiness and imports the NexaCart domain under the project scope', async () => {
    const ready = await c4Api.getNexaCartLiveReadiness('proj 1');
    assert.equal(ready.is_ready, true);
    await c4Api.importNexaCartLive('proj 1');
    assert.match(captured[0].url, /\/projects\/proj%201\/c4\/live\/nexacart\/readiness$/);
    assert.match(captured[1].url, /\/projects\/proj%201\/c4\/live\/nexacart\/import$/);
    assert.equal(captured[1].options.method, 'POST');
  });

  it('starts a live execution for the accepted contract and reads its progress', async () => {
    const body = { contract_id: 'nexacart-customer-assistant-contract', contract_version: 1, case_ids: null, repetitions: 3 };
    const started = await c4Api.startNexaCartLiveExecution('p1', body);
    assert.equal(started.status, 'RUNNING');
    assert.deepEqual(JSON.parse(captured[0].options.body), body);
    await c4Api.getNexaCartLiveExecution('p1', 'c4x-1');
    assert.match(captured[1].url, /\/c4\/live\/nexacart\/executions\/c4x-1$/);
  });

  it('stops polling only once the execution leaves RUNNING', () => {
    assert.equal(isLiveExecutionFinished({ status: 'RUNNING' }), false);
    assert.equal(isLiveExecutionFinished({ status: 'COMPLETED' }), true);
    assert.equal(isLiveExecutionFinished({ status: 'FAILED' }), true);
    assert.equal(isLiveExecutionFinished(null), false);
  });

  it('wires the live panels into Policy Preparation, Runs & Findings and run details', () => {
    const page = fs.readFileSync(path.resolve(c4RootDir, 'pages/PolicySafetyWorkspace.jsx'), 'utf8');
    assert.ok(page.includes('<NexaCartLiveImportPanel'));
    assert.ok(page.includes('<NexaCartLiveRunPanel'));
    assert.ok(page.includes('setCandidates(result.candidate_rules)'), 'imported rules enter the human review list');
    const runs = fs.readFileSync(path.resolve(c4RootDir, 'components/execution/ExecutionRunsSection.jsx'), 'utf8');
    assert.ok(runs.includes('<LiveNexaCartEvidence runRecord={currentRun} />'));
  });

  it('formats per-case rates and offers the proposal default of 3 runs per case', () => {
    assert.equal(formatRate(0.333), '33%');
    assert.equal(formatRate(1), '100%');
    assert.equal(formatRate(null), '—');
    assert.ok(REPETITION_OPTIONS.includes(3));
    const panel = fs.readFileSync(path.resolve(c4RootDir, 'components/live/NexaCartLivePanels.jsx'), 'utf8');
    assert.ok(panel.includes('useState(3)'), 'repetitions default to 3');
    assert.ok(panel.includes('<CaseRatesTable caseRates={execution.case_rates} />'));
    assert.ok(panel.includes('never counted as PASS'));
  });

  it('runs a frozen case against its own contract and binding, not the workspace selection', () => {
    const modal = fs.readFileSync(path.resolve(c4RootDir, 'components/execution/ExecutionModal.jsx'), 'utf8');
    assert.ok(modal.includes('bindingId: testCase.domain_id || domainBinding?.binding_id'));
    assert.ok(modal.includes('contractId: testCase.contract_id || acceptedContract?.contract_id'));
  });

  it('shows recorded instruction sources and the real excerpt fields in the evidence chain', () => {
    const chain = fs.readFileSync(path.resolve(c4RootDir, 'components/evidence/EvidenceChainViewer.jsx'), 'utf8');
    assert.ok(chain.includes('evaluation_report_summary?.evidence?.instruction_sources'));
    assert.ok(chain.includes('ruleRef?.supporting_excerpt'));
    assert.ok(chain.includes('ruleRef?.start_char'));
  });

  it('loads extracted candidates into review and labels simulated evaluation metrics', () => {
    const extraction = fs.readFileSync(path.resolve(c4RootDir, 'hooks/usePolicyExtraction.js'), 'utf8');
    assert.ok(extraction.includes('c4Api.listCandidateRules(projectId, extractedIds)'));
    const regression = fs.readFileSync(path.resolve(c4RootDir, 'hooks/usePolicyRegression.js'), 'utf8');
    assert.ok(!regression.includes("'binding-ecommerce-c4'"), 'no invalid hard-coded binding');
    const evaluation = fs.readFileSync(path.resolve(c4RootDir, 'components/evaluation/ResearchEvaluationSection.jsx'), 'utf8');
    assert.ok(evaluation.includes('Register Synthetic Demo Dataset'));
    assert.ok(evaluation.includes('experimentReport.evidence_basis'));
  });
});
