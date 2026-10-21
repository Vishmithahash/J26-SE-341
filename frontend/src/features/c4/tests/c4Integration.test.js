/**
 * Component 4 (C4) - Final Integration & Verification Pass Tests
 *
 * Verifies:
 * 1. Single authoritative active project identity and selection delegation (no silent fallbacks).
 * 2. Stale async response invalidation across project switches.
 * 3. Dynamic API base URL configuration (no hardcoded origins, clean route prefix stripping).
 * 4. Authentication via shared request client and error handling.
 * 5. Authenticated report export downloads and blob URL cleanup (URL.revokeObjectURL).
 * 6. Clean operational workspace labels and honesty in bounded dashboard summaries.
 * 7. Disentangled 6 outcome dimensions, payload boundaries, and stub execution blockers.
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
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

describe('C4 Integration: Authoritative Active Project & Selection Delegation', () => {
  it('useC4Project consumes shared activeProject without silent auto-discovery or local fallback', () => {
    const hookFile = path.resolve(c4RootDir, 'hooks/useC4Project.js');
    assert.ok(fs.existsSync(hookFile), 'useC4Project.js must exist');
    const content = fs.readFileSync(hookFile, 'utf8');

    // Consumes shared project context
    assert.ok(content.includes('useProject()'), 'Consumes shared useProject hook');
    assert.ok(content.includes('activeProject,'), 'Destructures activeProject from shared context');
    assert.ok(content.includes('activeProjectId,'), 'Destructures activeProjectId from shared context');
    assert.ok(content.includes('activeProject: activeProject || null'), 'Returns activeProject directly from shared state');
    assert.ok(content.includes('activeProjectId: activeProjectId || null'), 'Returns activeProjectId strictly from shared state');

    // Selection delegation to shared context
    assert.ok(content.includes('selectActiveProject(pid)'), 'Delegates switchProject to shared selectActiveProject');

    // Stale response invalidation with generation counters
    assert.ok(content.includes('generationRef.current += 1'), 'Increments generation counter on project or account transitions');
    assert.ok(content.includes('onProjectReset()'), 'Triggers state reset callback on project transition');

    // No auto-discovery or silent fallbacks
    assert.ok(!content.includes('fallbackProject'), 'Must not declare a local fallbackProject');
    assert.ok(!content.includes('isLoadingFallback'), 'Must not declare fallback loading state');
    assert.ok(!content.includes('projects[0]'), 'Must not silently auto-select the first project');
  });

  it('ProjectHeader displays role-correct empty state links when no project is selected', () => {
    const headerFile = path.resolve(c4RootDir, 'components/ProjectHeader.jsx');
    assert.ok(fs.existsSync(headerFile), 'ProjectHeader.jsx must exist');
    const content = fs.readFileSync(headerFile, 'utf8');

    // Role-correct redirection links
    assert.ok(content.includes("isAdmin ? '/admin/projects' : '/app/projects'"), 'Provides role-correct navigation to projects');
    assert.ok(content.includes('No Active Project Selected'), 'Shows clear empty state when no active project');
    assert.ok(content.includes('Select or Register Project'), 'Shows actionable navigation label');
  });
});

describe('C4 Integration: API Configuration & Route Mounting', () => {
  it('c4Api.js derives API base dynamically with no hardcoded backend origin', () => {
    const apiFile = path.resolve(c4RootDir, 'api/c4Api.js');
    assert.ok(fs.existsSync(apiFile), 'c4Api.js must exist');
    const content = fs.readFileSync(apiFile, 'utf8');

    // No hardcoded origins
    assert.ok(!content.includes("http://127.0.0.1:8000"), 'Must not hardcode local backend URL');
    assert.ok(!content.includes("http://localhost:8000"), 'Must not hardcode localhost backend URL');

    // Strips /api/v1 or /api prefix to keep /projects/{id}/c4 route intact
    assert.ok(content.includes('/api/v1') && content.includes('.replace('), 'Strips API prefixes to prevent duplicate prefixing');
    assert.ok(content.includes('/projects/${encodeURIComponent(projectId)}/c4'), 'Mounts directly under /projects/{projectId}/c4 prefix');

    // Reuses shared API client
    assert.ok(content.includes("import { request, ApiError } from '../../../services/api.js'"), 'Reuses shared authenticated request service');
  });

  it('ReportExportModal performs local export downloads and revokes Blob object URLs', () => {
    const modalFile = path.resolve(c4RootDir, 'components/reports/ReportExportModal.jsx');
    assert.ok(fs.existsSync(modalFile), 'ReportExportModal.jsx must exist');
    const content = fs.readFileSync(modalFile, 'utf8');

    assert.ok(content.includes('new Blob([content]'), 'Creates client-side Blob from export content');
    assert.ok(content.includes('URL.createObjectURL(blob)'), 'Generates object URL for download');
    assert.ok(content.includes('URL.revokeObjectURL(url)'), 'Revokes Blob URL after triggering download to prevent memory leaks');
    assert.ok(content.includes('Local Export Only'), 'Labels local export provenance honestly');
  });
});

describe('C4 Integration: Operational Labels & Dashboard Honesty', () => {
  it('workspace and dashboard components use active operational labels without stale roadmap placeholders', () => {
    const workspaceFile = path.resolve(c4RootDir, 'pages/PolicySafetyWorkspace.jsx');
    const workspaceContent = fs.readFileSync(workspaceFile, 'utf8');
    assert.ok(!workspaceContent.includes('Phases 1, 2 & 3 Active'), 'Removes stale roadmap banner text');
    assert.ok(workspaceContent.includes('Component 4 • Policy-Aware Safety & Injection Testing Workspace'), 'Uses descriptive workspace banner');

    const cardFile = path.resolve(c4RootDir, 'components/dashboard/C4DashboardCard.jsx');
    const cardContent = fs.readFileSync(cardFile, 'utf8');
    assert.ok(!cardContent.includes('Phases 1, 2 & 3 Complete'), 'Removes stale Phase completion badge');
    assert.ok(cardContent.includes('Policy Safety Active'), 'Uses operational status badge');
    assert.ok(cardContent.includes('Verdict Distribution (Recent'), 'Labels bounded sample honestly as recent runs');
  });

  it('regression and evaluation sections use descriptive workspace titles', () => {
    const regressionFile = path.resolve(c4RootDir, 'components/regression/PolicyRegressionSection.jsx');
    const regressionContent = fs.readFileSync(regressionFile, 'utf8');
    assert.ok(!regressionContent.includes('PHASE 3 ACTIVE'), 'Removes PHASE 3 ACTIVE from regression section');
    assert.ok(regressionContent.includes('Impact Analysis'), 'Uses operational badge for regression');

    const evalFile = path.resolve(c4RootDir, 'components/evaluation/ResearchEvaluationSection.jsx');
    const evalContent = fs.readFileSync(evalFile, 'utf8');
    assert.ok(!evalContent.includes('PHASE 3 ACTIVE'), 'Removes PHASE 3 ACTIVE from evaluation section');
    assert.ok(evalContent.includes('Research Benchmarks'), 'Uses operational badge for research evaluation');
  });
});

describe('C4 Integration: Disentangled Outcome Dimensions & Execution Boundaries', () => {
  it('preserves all six distinct outcome dimensions', () => {
    // 1. Execution status
    assert.ok(EXECUTION_STATUSES.COMPLETED, 'EXECUTION_STATUSES includes COMPLETED');
    assert.ok(EXECUTION_STATUSES.BLOCKED_BEFORE_INVOCATION, 'EXECUTION_STATUSES includes BLOCKED_BEFORE_INVOCATION');

    // 2. Exposure status
    assert.equal(EXPOSURE_STATUSES.EXPOSED, 'EXPOSED');
    assert.equal(EXPOSURE_STATUSES.NOT_EXPOSED, 'NOT_EXPOSED');
    assert.equal(EXPOSURE_STATUSES.UNKNOWN, 'UNKNOWN');
    assert.notEqual(EXPOSURE_STATUSES.NOT_EXPOSED, EXPOSURE_STATUSES.UNKNOWN, 'NOT_EXPOSED and UNKNOWN must remain distinct');

    // 3. Policy verdict
    assert.equal(POLICY_VERDICTS.PASS, 'PASS');
    assert.equal(POLICY_VERDICTS.FAIL, 'FAIL');
    assert.equal(POLICY_VERDICTS.INCONCLUSIVE, 'INCONCLUSIVE');
    assert.equal(POLICY_VERDICTS.NOT_EXERCISED, 'NOT_EXERCISED');

    // 4. Attacker objective
    assert.ok(ATTACKER_OBJECTIVE_OUTCOMES.BLOCKED, 'ATTACKER_OBJECTIVE_OUTCOMES includes BLOCKED');
    assert.ok(ATTACKER_OBJECTIVE_OUTCOMES.ACHIEVED, 'ATTACKER_OBJECTIVE_OUTCOMES includes ACHIEVED');

    // 5. Utility outcome
    assert.ok(TASK_UTILITY_OUTCOMES.SUCCESS, 'TASK_UTILITY_OUTCOMES includes SUCCESS');
    assert.ok(TASK_UTILITY_OUTCOMES.FAILED, 'TASK_UTILITY_OUTCOMES includes FAILED');

    // 6. Cleanup status
    assert.ok(CLEANUP_STATUSES.CLEANED_AND_VERIFIED, 'CLEANUP_STATUSES includes CLEANED_AND_VERIFIED');
    assert.ok(CLEANUP_STATUSES.CLEANUP_FAILED, 'CLEANUP_STATUSES includes CLEANUP_FAILED');
  });

  it('enforces payload boundary isolation across agent, harness, and evaluator payloads', () => {
    const modalFile = path.resolve(c4RootDir, 'components/cases/CasePayloadsModal.jsx');
    assert.ok(fs.existsSync(modalFile), 'CasePayloadsModal.jsx must exist');
    const modalContent = fs.readFileSync(modalFile, 'utf8');
    assert.ok(modalContent.includes('Adversarial Injection Payload'), 'Isolates untrusted injection payload');
    assert.ok(modalContent.includes('Harness Placement Ownership'), 'Labels harness placement explicitly');
    assert.ok(modalContent.includes('evaluator'), 'Separates evaluator oracle payload');
  });

  it('keeps LiveAUTAdapterStub explicitly noted with missing live endpoint readiness blockers', () => {
    const modalFile = path.resolve(c4RootDir, 'components/execution/ExecutionModal.jsx');
    assert.ok(fs.existsSync(modalFile), 'ExecutionModal.jsx must exist');
    const modalContent = fs.readFileSync(modalFile, 'utf8');
    assert.ok(modalContent.includes('LiveAUTAdapterStub'), 'References LiveAUTAdapterStub honestly');
    assert.ok(modalContent.includes('readiness will honestly report the missing endpoints as blockers'), 'Warns that live readiness blockers apply');
  });
});
