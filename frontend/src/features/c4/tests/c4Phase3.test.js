/**
 * Component 4 (C4) - Frontend Phase 3 Tests
 * Verifies findings, evidence-linked causal observation chain, reporting & authenticated exports,
 * policy-change regression diffing & impact plans, selective execution (fresh vs historical),
 * requirement-change transitions vs agent regressions, and supported research evaluation interfaces.
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  RULE_CHANGE_TYPES,
  CASE_IMPACT_LEVELS,
  CASE_DECISION_ACTIONS,
  PLAN_LIFECYCLE_STATES,
  REGRESSION_EXECUTION_MODES,
  VERDICT_TRANSITION_TYPES,
  VIOLATION_STAGES,
  TRUST_CLASSIFICATIONS,
  EVIDENCE_ORIGINS,
  RESEARCH_STRATEGIES,
  RESEARCH_ABLATIONS,
  DATASET_SPLITS,
  LABEL_ORIGINS,
  REVIEW_STATUSES,
  EXPERIMENT_STATUSES,
} from '../api/types.js';

import { c4Api } from '../api/c4Api.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const c4RootDir = path.resolve(__dirname, '..');

describe('C4 Phase 3: Taxonomy & Enums', () => {
  it('defines deterministic rule diff change types', () => {
    assert.equal(RULE_CHANGE_TYPES.SEMANTICALLY_MODIFIED, 'SEMANTICALLY_MODIFIED');
    assert.equal(RULE_CHANGE_TYPES.ADDED, 'ADDED');
    assert.equal(RULE_CHANGE_TYPES.REMOVED, 'REMOVED');
    assert.equal(RULE_CHANGE_TYPES.METADATA_ONLY, 'METADATA_ONLY');
    assert.equal(RULE_CHANGE_TYPES.PROVENANCE_ONLY, 'PROVENANCE_ONLY');
  });

  it('defines impact levels and test-case action decisions', () => {
    assert.equal(CASE_IMPACT_LEVELS.DEFINITELY_AFFECTED, 'DEFINITELY_AFFECTED');
    assert.equal(CASE_IMPACT_LEVELS.POSSIBLY_AFFECTED, 'POSSIBLY_AFFECTED');
    assert.equal(CASE_IMPACT_LEVELS.UNAFFECTED, 'UNAFFECTED');
    assert.equal(CASE_IMPACT_LEVELS.UNSUPPORTED, 'UNSUPPORTED');

    assert.equal(CASE_DECISION_ACTIONS.REGENERATE, 'REGENERATE');
    assert.equal(CASE_DECISION_ACTIONS.REVALIDATE, 'REVALIDATE');
    assert.equal(CASE_DECISION_ACTIONS.RETIRE, 'RETIRE');
    assert.equal(CASE_DECISION_ACTIONS.REVISE, 'REVISE');
    assert.equal(CASE_DECISION_ACTIONS.RETAIN, 'RETAIN');
    assert.equal(CASE_DECISION_ACTIONS.BLOCKED, 'BLOCKED');
  });

  it('defines regression execution modes keeping fresh execution and historical re-evaluation distinct', () => {
    assert.equal(REGRESSION_EXECUTION_MODES.FRESH_EXECUTION, 'FRESH_EXECUTION');
    assert.equal(REGRESSION_EXECUTION_MODES.HISTORICAL_RE_EVALUATION, 'HISTORICAL_RE_EVALUATION');
    assert.notEqual(
      REGRESSION_EXECUTION_MODES.FRESH_EXECUTION,
      REGRESSION_EXECUTION_MODES.HISTORICAL_RE_EVALUATION
    );
  });

  it('defines verdict transition types distinguishing policy changes from agent regressions', () => {
    assert.equal(VERDICT_TRANSITION_TYPES.PASS_TO_PASS, 'PASS_TO_PASS');
    assert.equal(VERDICT_TRANSITION_TYPES.PASS_TO_FAIL, 'PASS_TO_FAIL');
    assert.equal(VERDICT_TRANSITION_TYPES.FAIL_TO_PASS, 'FAIL_TO_PASS');
    assert.equal(VERDICT_TRANSITION_TYPES.FAIL_TO_FAIL, 'FAIL_TO_FAIL');
    assert.equal(VERDICT_TRANSITION_TYPES.NEW_COVERAGE, 'NEW_COVERAGE');
    assert.equal(VERDICT_TRANSITION_TYPES.RETIRED, 'RETIRED');
  });

  it('defines distinct violation stages according to backend findings', () => {
    assert.equal(VIOLATION_STAGES.ATTEMPTED_PROHIBITED_ACTION, 'ATTEMPTED_PROHIBITED_ACTION');
    assert.equal(VIOLATION_STAGES.COMPLETED_PROHIBITED_ACTION_OR_EFFECT, 'COMPLETED_PROHIBITED_ACTION_OR_EFFECT');
    assert.equal(VIOLATION_STAGES.EXFILTRATED_PROTECTED_DATA, 'EXFILTRATED_PROTECTED_DATA');
    assert.equal(VIOLATION_STAGES.INSTRUCTION_AUTHORITY_VIOLATION, 'INSTRUCTION_AUTHORITY_VIOLATION');
  });

  it('defines trust classifications for instruction authority', () => {
    assert.equal(TRUST_CLASSIFICATIONS.TRUSTED_GOVERNANCE, 'TRUSTED_GOVERNANCE');
    assert.equal(TRUST_CLASSIFICATIONS.UNTRUSTED_INDIRECT_CONTENT, 'UNTRUSTED_INDIRECT_CONTENT');
    assert.equal(TRUST_CLASSIFICATIONS.UNTRUSTED_EXTERNAL, 'UNTRUSTED_EXTERNAL');
  });

  it('defines research baseline strategies and reduced-evidence ablations', () => {
    assert.equal(RESEARCH_STRATEGIES.C4_POLICY_AWARE, 'C4_POLICY_AWARE');
    assert.equal(RESEARCH_STRATEGIES.MANUAL_SUITE, 'MANUAL_SUITE');
    assert.equal(RESEARCH_STRATEGIES.GENERIC_MODEL_GENERATOR, 'GENERIC_MODEL_GENERATOR');
    assert.equal(RESEARCH_STRATEGIES.TEXT_ONLY_EVALUATOR, 'TEXT_ONLY_EVALUATOR');

    assert.equal(RESEARCH_ABLATIONS.NONE, 'NONE');
    assert.equal(RESEARCH_ABLATIONS.NO_GROUNDING, 'NO_GROUNDING');
    assert.equal(RESEARCH_ABLATIONS.NO_PROVENANCE, 'NO_PROVENANCE');
    assert.equal(RESEARCH_ABLATIONS.NO_EFFECTS, 'NO_EFFECTS');
  });

  it('defines evaluation dataset splits and benchmark lifecycle states', () => {
    assert.equal(DATASET_SPLITS.DEV, 'DEV');
    assert.equal(DATASET_SPLITS.PILOT, 'PILOT');
    assert.equal(DATASET_SPLITS.HELD_OUT, 'HELD_OUT');
  });
});

describe('C4 Phase 3: API Client Method Signatures', () => {
  it('exposes contract comparison and diffing endpoints', () => {
    assert.equal(typeof c4Api.comparePolicyContracts, 'function');
    assert.equal(typeof c4Api.getPolicyComparison, 'function');
  });

  it('exposes typed regression impact planning, regeneration, freezing, and execution endpoints', () => {
    assert.equal(typeof c4Api.createRegressionPlan, 'function');
    assert.equal(typeof c4Api.getRegressionPlan, 'function');
    assert.equal(typeof c4Api.regenerateRegressionPlan, 'function');
    assert.equal(typeof c4Api.freezeRegressionPlan, 'function');
    assert.equal(typeof c4Api.executeRegressionPlan, 'function');
    assert.equal(typeof c4Api.getRegressionReport, 'function');
    assert.equal(typeof c4Api.reEvaluateHistorical, 'function');
  });

  it('exposes research dataset management, agreement calculation, and experiment orchestration endpoints', () => {
    assert.equal(typeof c4Api.registerEvaluationDataset, 'function');
    assert.equal(typeof c4Api.listEvaluationDatasets, 'function');
    assert.equal(typeof c4Api.getEvaluationDataset, 'function');
    assert.equal(typeof c4Api.freezeEvaluationDataset, 'function');
    assert.equal(typeof c4Api.recordReviewerDecision, 'function');
    assert.equal(typeof c4Api.getReviewerAgreement, 'function');
    assert.equal(typeof c4Api.createExperiment, 'function');
    assert.equal(typeof c4Api.executeExperiment, 'function');
    assert.equal(typeof c4Api.getExperimentReport, 'function');
  });
});

describe('C4 Phase 3: Component Structure & UI Verification', () => {
  it('implements EvidenceChainViewer.jsx visualizing the 4-step observation chain safely', () => {
    const filePath = path.join(c4RootDir, 'components', 'evidence', 'EvidenceChainViewer.jsx');
    assert.ok(fs.existsSync(filePath), 'EvidenceChainViewer.jsx must exist');
    const content = fs.readFileSync(filePath, 'utf-8');

    // Causal chain sequence
    assert.ok(content.includes('1. Instruction Source'), 'Shows instruction source');
    assert.ok(content.includes('2. Applicable Policy'), 'Shows applicable rule');
    assert.ok(content.includes('3. Observed Action'), 'Shows observed action');
    assert.ok(content.includes('4. Effect / Outcome'), 'Shows committed effect/outcome');

    // Observation limitations
    assert.ok(content.includes('Observation Limitations & Missing Evidence'), 'Surfaces missing evidence');

    // Safe rendering: no dangerouslySetInnerHTML
    assert.ok(!content.includes('dangerouslySetInnerHTML'), 'Must not execute or inject raw HTML');
  });

  it('implements FindingDetailsModal.jsx with embedded evidence chain viewer', () => {
    const filePath = path.join(c4RootDir, 'components', 'evidence', 'FindingDetailsModal.jsx');
    assert.ok(fs.existsSync(filePath), 'FindingDetailsModal.jsx must exist');
    const content = fs.readFileSync(filePath, 'utf-8');

    assert.ok(content.includes('EvidenceChainViewer'), 'Embeds EvidenceChainViewer');
    assert.ok(content.includes('Finding Details:'), 'Shows finding header');
    assert.ok(content.includes('Violation Stage:'), 'Shows violation stage');
  });

  it('implements ReportExportModal.jsx with authenticated client-side downloads without bearer tokens in URLs', () => {
    const filePath = path.join(c4RootDir, 'components', 'reports', 'ReportExportModal.jsx');
    assert.ok(fs.existsSync(filePath), 'ReportExportModal.jsx must exist');
    const content = fs.readFileSync(filePath, 'utf-8');

    assert.ok(content.includes('Blob'), 'Uses client-side Blob creation for downloads');
    assert.ok(!content.includes('?token='), 'Must not append bearer tokens to query strings');
    assert.ok(content.includes('Shared publication to an external QA dashboard is not available'), 'Clearly denotes unconfigured shared publication');
    assert.ok(content.includes('JSON Payload'), 'Supports structured JSON export');
    assert.ok(content.includes('Markdown Report'), 'Supports Markdown report export');
  });

  it('implements PolicyRegressionSection.jsx with rule diffs, action decisions, and execution modes', () => {
    const filePath = path.join(c4RootDir, 'components', 'regression', 'PolicyRegressionSection.jsx');
    assert.ok(fs.existsSync(filePath), 'PolicyRegressionSection.jsx must exist');
    const content = fs.readFileSync(filePath, 'utf-8');

    assert.ok(content.includes('RULE_CHANGE_TYPES'), 'Handles rule change types');
    assert.ok(content.includes('CASE_DECISION_ACTIONS'), 'Handles case decision actions');
    assert.ok(content.includes('REGRESSION_EXECUTION_MODES'), 'Distinguishes execution modes');
    assert.ok(content.includes('FRESH_EXECUTION'), 'Supports fresh agent execution');
    assert.ok(content.includes('HISTORICAL_RE_EVALUATION'), 'Supports historical re-evaluation');
    assert.ok(content.includes('does not constitute a fresh agent invocation or fresh coverage'), 'Warns user that historical re-evaluation is not fresh agent execution');
    assert.ok(content.includes('Requirement Change (Not Agent Regression)'), 'Displays requirement change transitions');
  });

  it('implements ResearchEvaluationSection.jsx with splits, inter-rater agreement, baselines, and proposal metrics', () => {
    const filePath = path.join(c4RootDir, 'components', 'evaluation', 'ResearchEvaluationSection.jsx');
    assert.ok(fs.existsSync(filePath), 'ResearchEvaluationSection.jsx must exist');
    const content = fs.readFileSync(filePath, 'utf-8');

    assert.ok(content.includes('DEV Partition'), 'Supports DEV split');
    assert.ok(content.includes('PILOT Partition'), 'Supports PILOT split');
    assert.ok(content.includes('HELD_OUT Partition'), 'Supports HELD_OUT benchmark split');
    assert.ok(content.includes("Cohen's Kappa"), "Computes Cohen's Kappa inter-rater agreement");
    assert.ok(content.includes('RESEARCH_STRATEGIES'), 'Handles baseline strategies');
    assert.ok(content.includes('RESEARCH_ABLATIONS'), 'Handles reduced-evidence ablations');
    assert.ok(content.includes('Category 1: Policy Extraction Quality'), 'Presents proposal metric Category 1');
    assert.ok(content.includes('Category 2: Generated Policy Tests & Coverage'), 'Presents proposal metric Category 2');
    assert.ok(content.includes('Category 3: Violation Detection & Reliability'), 'Presents proposal metric Category 3');
    assert.ok(content.includes('Category 4: Attacks & Exposure Verification'), 'Presents proposal metric Category 4');
    assert.ok(content.includes('Category 5: Legitimate Utility & Attribution Accuracy'), 'Presents proposal metric Category 5');
    assert.ok(content.includes('Category 6: Policy-Change Regression & Overhead'), 'Presents proposal metric Category 6');
  });

  it('implements C4DashboardCard.jsx with verdict distribution and outcome provenance', () => {
    const filePath = path.join(c4RootDir, 'components', 'dashboard', 'C4DashboardCard.jsx');
    assert.ok(fs.existsSync(filePath), 'C4DashboardCard.jsx must exist');
    const content = fs.readFileSync(filePath, 'utf-8');

    assert.ok(content.includes('Phases 1, 2 & 3 Complete'), 'Denotes full C4 phase completion');
    assert.ok(content.includes('Verdict Distribution'), 'Shows verdict distribution');
    assert.ok(content.includes('Latest Run Verdict:'), 'Shows latest run verdict');
    assert.ok(content.includes('Exposure:'), 'Shows exposure status');
    assert.ok(content.includes('Attacker:'), 'Shows attacker outcome');
    assert.ok(content.includes('Utility:'), 'Shows task utility outcome');
  });

  it('integrates Phase 3 sections and modals in PolicySafetyWorkspace.jsx', () => {
    const filePath = path.join(c4RootDir, 'pages', 'PolicySafetyWorkspace.jsx');
    assert.ok(fs.existsSync(filePath), 'PolicySafetyWorkspace.jsx must exist');
    const content = fs.readFileSync(filePath, 'utf-8');

    assert.ok(content.includes('PolicyRegressionSection'), 'Mounts PolicyRegressionSection');
    assert.ok(content.includes('ResearchEvaluationSection'), 'Mounts ResearchEvaluationSection');
    assert.ok(content.includes('FindingDetailsModal'), 'Mounts FindingDetailsModal');
    assert.ok(content.includes('ReportExportModal'), 'Mounts ReportExportModal');
    assert.ok(content.includes('Component 4 • Complete (Phases 1, 2 & 3 Active)'), 'Banner denotes Phase 1, 2, and 3 active');
  });
});
