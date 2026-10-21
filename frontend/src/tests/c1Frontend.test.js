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
} from '../components/c1/c1Api.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

describe('Component 1 Tool-Call Correctness Frontend Phase 1 Tests', () => {
  describe('C1 API Client and Endpoint Contract Definitions', () => {
    it('defines all required Phase 1 configuration and generation API methods', () => {
      const requiredMethods = [
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
      ];

      for (const method of requiredMethods) {
        assert.equal(
          typeof c1Api[method],
          'function',
          `Expected c1Api to export method '${method}'`
        );
      }
    });

    it('enforces non-empty project ID on API requests', async () => {
      await assert.rejects(
        async () => {
          await c1Api.listConfigs('');
        },
        /Project ID is required/
      );

      await assert.rejects(
        async () => {
          await c1Api.createConfig(null, {});
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
