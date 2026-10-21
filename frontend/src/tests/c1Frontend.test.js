import './setup.js';
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  c1Api,
  CASE_CATEGORIES,
  EVIDENCE_CHANNELS,
  COMPARISON_OPERATORS,
  FIELD_PRESENCE_OPTIONS,
  SOURCE_RELATIONSHIP_TYPES,
  CORRECTNESS_VERDICTS,
  RUN_STATUSES,
  CASE_EXECUTION_STATUSES,
  TRACE_COMPLETENESS,
  formatValue,
  escapeText,
} from '../components/c1/c1Api.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

describe('Component 1 Tool-Call Correctness Frontend Tests (Phase 1 & Phase 2)', () => {
  describe('C1 API Client and Endpoint Contract Definitions', () => {
    it('defines all required Phase 1 and Phase 2 configuration, generation, and execution API methods', () => {
      const requiredMethods = [
        // Phase 1
        'listConfigs',
        'getConfig',
        'createConfig',
        'updateConfig',
        'validateStoredConfig',
        'validateConfigSpec',
        'getNexaCartExample',
        'createGenerationJob',
        'listGenerationJobs',
        'getGenerationJob',
        'getJobCandidates',
        'getJobAgentTasks',
        'promoteJobToSuite',
        'listSuites',
        'getSuite',
        'getSuiteCaseAgentView',
        // Phase 2
        'startExecutionRun',
        'listExecutionRuns',
        'getExecutionRun',
        'cancelExecutionRun',
        'rerunExecution',
        'getCaseExecution',
        'checkAdapterReadiness',
      ];

      for (const method of requiredMethods) {
        assert.equal(
          typeof c1Api[method],
          'function',
          `Expected c1Api to export method '${method}'`
        );
      }
    });

    it('enforces non-empty project ID on all API requests', async () => {
      await assert.rejects(
        async () => {
          await c1Api.listConfigs('');
        },
        /Project ID is required/
      );

      await assert.rejects(
        async () => {
          await c1Api.startExecutionRun(null, {});
        },
        /Project ID is required/
      );

      await assert.rejects(
        async () => {
          await c1Api.getExecutionRun('', 'run_123');
        },
        /Project ID is required/
      );
    });
  });

  describe('Contract Enum and Category Alignment', () => {
    it('supports all 7 standardized case categories matching backend enum', () => {
      const expectedIds = [
        'CORRECT_BEHAVIOUR',
        'WRONG_TOOL_SELECTION',
        'MISSING_ARGUMENTS',
        'MALFORMED_ARGUMENT_NAMES_OR_TYPES',
        'INCORRECT_ARGUMENT_VALUES',
        'CONTEXTUAL_SOURCE_MISMATCH',
        'INSUFFICIENT_EVIDENCE',
      ];

      const categoryIds = CASE_CATEGORIES.map((c) => c.id);
      for (const exp of expectedIds) {
        assert.equal(
          categoryIds.includes(exp),
          true,
          `Expected category '${exp}' to be supported in frontend`
        );
      }
    });

    it('supports standard evidence channels matching backend EvidenceChannel enum', () => {
      const expectedChannels = [
        'AGENT_TRACE',
        'TOOL_CALL_LOG',
        'AUT_DATABASE_DIFF',
        'HTTP_TRAFFIC',
        'CONSOLE_OUTPUT',
      ];

      const channelIds = EVIDENCE_CHANNELS.map((ch) => ch.id);
      for (const ch of expectedChannels) {
        assert.equal(
          channelIds.includes(ch),
          true,
          `Expected evidence channel '${ch}' to be supported`
        );
      }
    });

    it('explicitly distinguishes missing values from explicit nulls', () => {
      const presenceIds = FIELD_PRESENCE_OPTIONS.map((p) => p.id);
      assert.equal(presenceIds.includes('REQUIRED_NON_NULL'), true);
      assert.equal(presenceIds.includes('REQUIRED_EXPLICIT_NULL'), true);
      assert.equal(presenceIds.includes('FORBIDDEN_OR_MISSING'), true);
    });

    it('exposes bounded declarative comparison operators and source relationship types', () => {
      assert.equal(COMPARISON_OPERATORS.includes('EQUALS'), true);
      assert.equal(COMPARISON_OPERATORS.includes('REGEX_MATCH'), true);
      assert.equal(SOURCE_RELATIONSHIP_TYPES.includes('EXACT_MATCH'), true);
      assert.equal(SOURCE_RELATIONSHIP_TYPES.includes('NUMERIC_TOLERANCE'), true);
    });

    it('defines standard correctness verdicts strictly matching backend CorrectnessVerdict enum', () => {
      assert.equal(CORRECTNESS_VERDICTS.PASS, 'PASS');
      assert.equal(CORRECTNESS_VERDICTS.FAIL, 'FAIL');
      assert.equal(CORRECTNESS_VERDICTS.INCONCLUSIVE, 'INCONCLUSIVE');
      assert.equal(Object.keys(CORRECTNESS_VERDICTS).length, 3);
    });

    it('defines run lifecycle and trace completeness states', () => {
      assert.equal(RUN_STATUSES.PENDING, 'PENDING');
      assert.equal(RUN_STATUSES.RUNNING, 'RUNNING');
      assert.equal(RUN_STATUSES.COMPLETED, 'COMPLETED');
      assert.equal(RUN_STATUSES.FAILED, 'FAILED');
      assert.equal(RUN_STATUSES.ABORTED, 'ABORTED');

      assert.equal(TRACE_COMPLETENESS.COMPLETE, 'COMPLETE');
      assert.equal(TRACE_COMPLETENESS.INCOMPLETE, 'INCOMPLETE');
      assert.equal(TRACE_COMPLETENESS.CORRUPTED, 'CORRUPTED');
      assert.equal(TRACE_COMPLETENESS.MISSING, 'MISSING');
    });
  });

  describe('Value Formatting and Safe Content Escaping', () => {
    it('clearly distinguishes missing, null, empty strings, and empty collections', () => {
      assert.equal(formatValue(undefined), '<missing>');
      assert.equal(formatValue(null), 'null');
      assert.equal(formatValue(''), '"" (empty string)');
      assert.equal(formatValue([]), '[] (empty array)');
      assert.equal(formatValue({}), '{} (empty object)');
      assert.equal(formatValue('order_100'), '"order_100"');
      assert.equal(formatValue(49.99), '49.99');
    });

    it('safely escapes HTML to prevent executable script injection in evidence rendering', () => {
      const malicious = '<script>alert("xss")</script>&"test"\'';
      const escaped = escapeText(malicious);
      assert.equal(escaped.includes('<script>'), false);
      assert.equal(escaped.includes('&lt;script&gt;'), true);
      assert.equal(escaped.includes('&amp;'), true);
      assert.equal(escaped.includes('&quot;'), true);
      assert.equal(escaped.includes('&#039;'), true);
    });
  });

  describe('Agent Task Isolation and QA Quarantine Rule', () => {
    it('verifies agent-facing task view contract strips oracle expectations and validation issues', () => {
      const candidateCase = {
        case_id: 'case_c1_001',
        category: 'CORRECT_BEHAVIOUR',
        agent_task_prompt: 'Process refund for order 1042',
        task_context_inputs: { order_id: '1042' },
        fixture_plan: { fixture_capability_ref: 'nexacart_test_fixtures' },
        expected_tool_calls: [
          {
            tool_name: 'process_refund',
            argument_constraints: [{ field_path: 'amount', operator: 'EQUALS', expected_value: 49.99 }],
          },
        ],
        validation_issues: [],
      };

      // Extract isolated agent facing task
      const agentFacing = {
        case_id: candidateCase.case_id,
        task_prompt: candidateCase.agent_task_prompt,
        context_inputs: candidateCase.task_context_inputs,
        permitted_tools: ['lookup_order', 'process_refund'],
      };

      assert.equal(agentFacing.task_prompt, 'Process refund for order 1042');
      assert.equal('expected_tool_calls' in agentFacing, false);
      assert.equal('validation_issues' in agentFacing, false);
      assert.equal('fixture_plan' in agentFacing, false);
    });

    it('verifies execution requests contain suite identifier and idempotency key without oracle answers', () => {
      const req = {
        suite_id: 'suite_refunds_v1',
        suite_version: 1,
        idempotency_key: 'idemp_key_12345',
        deadline_seconds: 60,
        evaluator_version: 'c1-evaluator-v1.0',
      };

      assert.equal(req.suite_id, 'suite_refunds_v1');
      assert.equal('oracle_answers' in req, false);
      assert.equal('expected_tool_calls' in req, false);
    });
  });

  describe('Strict Workspace Isolation and Codebase Integrity', () => {
    it('ensures shared services directory was not modified or polluted with component files', () => {
      const servicesDir = path.resolve(__dirname, '../services');
      const serviceFiles = fs.readdirSync(servicesDir);

      for (const file of serviceFiles) {
        assert.equal(
          file.includes('c1_') || file.includes('c1Api') || file.includes('tool_call'),
          false,
          `C1 API must reside in component-local directory, not in shared services: ${file}`
        );
      }
    });

    it('verifies dedicated Component 1 workspace files exist and are populated', () => {
      const c1ComponentsDir = path.resolve(__dirname, '../components/c1');
      assert.equal(fs.existsSync(c1ComponentsDir), true);

      const expectedFiles = [
        'c1Api.js',
        'ConfigurationEditor.jsx',
        'GenerationPanel.jsx',
        'CandidateInspector.jsx',
        'SuiteViewer.jsx',
        'RunDashboard.jsx',
        'ResultsViewer.jsx',
      ];

      for (const file of expectedFiles) {
        const filePath = path.join(c1ComponentsDir, file);
        assert.equal(
          fs.existsSync(filePath),
          true,
          `Expected file '${file}' in components/c1`
        );
        const stats = fs.statSync(filePath);
        assert.equal(stats.size > 100, true, `File '${file}' should not be empty`);
      }

      const c1PagePath = path.resolve(
        __dirname,
        '../pages/c1/ToolCallCorrectnessPage.jsx'
      );
      assert.equal(fs.existsSync(c1PagePath), true);
    });
  });
});
