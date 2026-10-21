/**
 * Component 4 (C4) - Policy-Aware Safety & Prompt-Injection Testing
 * API Client Adapter for C4 Endpoints
 */

import { request, ApiError } from '../../../services/api.js';

const C4_API_BASE =
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_BACKEND_URL) ||
  'http://127.0.0.1:8000';

function buildUrl(projectId, path) {
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${C4_API_BASE}/projects/${encodeURIComponent(projectId)}/c4${cleanPath}`;
}

export const c4Api = {
  /**
   * Check extraction provider configuration and operational readiness.
   * Distinguishes 'offline_mock' from external LLM providers.
   */
  async getExtractionReadiness(projectId, providerId = 'offline_mock') {
    const url = `${buildUrl(projectId, '/extraction/readiness')}?provider_id=${encodeURIComponent(providerId)}`;
    return request(url, { method: 'GET' });
  },

  /**
   * Register a new version of a policy artifact (POLICY_DOCUMENT, ROLE_DEFINITIONS, PERMISSIONS).
   */
  async registerArtifact(projectId, payload) {
    const url = buildUrl(projectId, '/artifacts');
    return request(url, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Retrieve an artifact by ID and version.
   */
  async getArtifact(projectId, artifactId, version) {
    const url = buildUrl(projectId, `/artifacts/${encodeURIComponent(artifactId)}/versions/${version}`);
    return request(url, { method: 'GET' });
  },

  /**
   * Derive or import candidate rules from an artifact version.
   * Mode: 'controlled_language' or 'structured_import'
   */
  async deriveRules(projectId, payload) {
    const url = buildUrl(projectId, '/rules/derive');
    return request(url, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Initiate a natural-language extraction job.
   */
  async startExtractionJob(projectId, payload) {
    const url = buildUrl(projectId, '/extraction/jobs');
    return request(url, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Poll / fetch extraction job status and results.
   */
  async getExtractionJob(projectId, jobId) {
    const url = buildUrl(projectId, `/extraction/jobs/${encodeURIComponent(jobId)}`);
    return request(url, { method: 'GET' });
  },

  /**
   * Human or dev review gate for an extracted candidate rule.
   * decision: 'ACCEPTED' | 'REJECTED'
   */
  async reviewCandidateRule(projectId, ruleId, payload) {
    const url = buildUrl(projectId, `/candidates/${encodeURIComponent(ruleId)}/review`);
    return request(url, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Create a draft policy contract from candidate rule IDs.
   */
  async createContractDraft(projectId, payload) {
    const url = buildUrl(projectId, '/contracts');
    return request(url, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Retrieve policy contract by ID and version.
   */
  async getContract(projectId, contractId, version) {
    const url = buildUrl(projectId, `/contracts/${encodeURIComponent(contractId)}/versions/${version}`);
    return request(url, { method: 'GET' });
  },

  /**
   * Validate a policy contract draft.
   */
  async validateContract(projectId, contractId, version) {
    const url = buildUrl(projectId, `/contracts/${encodeURIComponent(contractId)}/versions/${version}/validate`);
    return request(url, { method: 'POST' });
  },

  /**
   * Explicitly accept a validated policy contract.
   * Transitions lifecycle state from VALIDATED to ACCEPTED.
   */
  async acceptContract(projectId, contractId, version, payload) {
    const url = buildUrl(projectId, `/contracts/${encodeURIComponent(contractId)}/versions/${version}/accept`);
    return request(url, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * List domain profiles (E-Commerce, Booking, etc.).
   */
  async listDomains(projectId) {
    const url = buildUrl(projectId, '/domains');
    return request(url, { method: 'GET' });
  },

  /**
   * Check runtime and integration readiness for a domain.
   */
  async checkDomainReadiness(projectId, domainId, mode = 'SIMULATED') {
    const url = `${buildUrl(projectId, `/domains/${encodeURIComponent(domainId)}/readiness`)}?mode=${encodeURIComponent(mode)}`;
    return request(url, { method: 'GET' });
  },

  /**
   * List domain bindings for a project.
   */
  async listDomainBindings(projectId, bindingId = null) {
    const query = bindingId ? `?binding_id=${encodeURIComponent(bindingId)}` : '';
    const url = `${buildUrl(projectId, '/bindings')}${query}`;
    return request(url, { method: 'GET' });
  },

  /**
   * Retrieve a domain binding by ID and version.
   */
  async getDomainBinding(projectId, bindingId, version) {
    const url = buildUrl(projectId, `/bindings/${encodeURIComponent(bindingId)}/versions/${version}`);
    return request(url, { method: 'GET' });
  },

  /**
   * Register a new versioned domain binding.
   */
  async registerDomainBinding(projectId, payload) {
    const url = buildUrl(projectId, '/bindings');
    return request(url, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Start domain onboarding workflow across policy artifacts and domain bindings.
   */
  async startOnboardingJob(projectId, payload) {
    const url = buildUrl(projectId, '/onboarding/jobs');
    return request(url, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Get status and details of an onboarding job.
   */
  async getOnboardingJob(projectId, jobId) {
    const url = buildUrl(projectId, `/onboarding/jobs/${encodeURIComponent(jobId)}`);
    return request(url, { method: 'GET' });
  },

  // -------------------------------------------------------------
  // Phase 2: Automatic Policy Test Generation & Freezing
  // -------------------------------------------------------------

  /**
   * Automatically generate bounded policy test cases from accepted contract and domain binding.
   */
  async generateTestCases(projectId, payload) {
    const url = buildUrl(projectId, '/generate');
    return request(url, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Retrieve a generation batch report by batch ID.
   */
  async getGenerationBatch(projectId, batchId) {
    const url = buildUrl(projectId, `/batches/${encodeURIComponent(batchId)}`);
    return request(url, { method: 'GET' });
  },

  /**
   * List generated policy test cases with optional filters.
   */
  async listTestCases(projectId, params = {}) {
    const query = new URLSearchParams();
    if (params.batch_id) query.append('batch_id', params.batch_id);
    if (params.rule_id) query.append('rule_id', params.rule_id);
    if (params.category) query.append('category', params.category);
    if (params.lifecycle_state) query.append('lifecycle_state', params.lifecycle_state);

    const qs = query.toString() ? `?${query.toString()}` : '';
    const url = `${buildUrl(projectId, '/cases')}${qs}`;
    return request(url, { method: 'GET' });
  },

  /**
   * Retrieve a policy test case by ID and version.
   */
  async getTestCase(projectId, caseId, version) {
    const url = buildUrl(projectId, `/cases/${encodeURIComponent(caseId)}/versions/${version}`);
    return request(url, { method: 'GET' });
  },

  /**
   * Independently validate a generated test case against contract and domain binding.
   */
  async validateTestCase(projectId, caseId, version) {
    const url = buildUrl(projectId, `/cases/${encodeURIComponent(caseId)}/versions/${version}/validate`);
    return request(url, { method: 'POST' });
  },

  /**
   * Freeze a validated test case to ensure immutable snapshot and canonical content hash.
   */
  async freezeTestCase(projectId, caseId, version) {
    const url = buildUrl(projectId, `/cases/${encodeURIComponent(caseId)}/versions/${version}/freeze`);
    return request(url, { method: 'POST' });
  },

  // -------------------------------------------------------------
  // Phase 2: Three Payload Boundaries Exports
  // -------------------------------------------------------------

  /**
   * Export strictly agent-visible task payload (no hidden goals or oracle assertions).
   */
  async exportAgentPayload(projectId, caseId, version) {
    const url = buildUrl(projectId, `/cases/${encodeURIComponent(caseId)}/versions/${version}/export/agent`);
    return request(url, { method: 'GET' });
  },

  /**
   * Export test harness orchestration payload (injection placement and fixture requirements).
   */
  async exportHarnessPayload(projectId, caseId, version) {
    const url = buildUrl(projectId, `/cases/${encodeURIComponent(caseId)}/versions/${version}/export/harness`);
    return request(url, { method: 'GET' });
  },

  /**
   * Export evaluator oracle assertions and hidden validation ground truth.
   */
  async exportEvaluatorPayload(projectId, caseId, version) {
    const url = buildUrl(projectId, `/cases/${encodeURIComponent(caseId)}/versions/${version}/export/evaluator`);
    return request(url, { method: 'GET' });
  },

  // -------------------------------------------------------------
  // Phase 2: Runtime Readiness & Controlled Execution
  // -------------------------------------------------------------

  /**
   * Check runtime readiness of a case, domain binding, and execution adapter.
   */
  async checkExecutionReadiness(projectId, payload) {
    const url = buildUrl(projectId, '/runs/readiness');
    return request(url, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Execute a frozen policy test case through registered adapter.
   */
  async executeTestCase(projectId, payload) {
    const url = buildUrl(projectId, '/runs/execute');
    return request(url, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Retrieve a C4 execution run record by run ID.
   */
  async getExecutionRun(projectId, runId) {
    const url = buildUrl(projectId, `/runs/${encodeURIComponent(runId)}`);
    return request(url, { method: 'GET' });
  },

  /**
   * List execution runs for a project.
   */
  async listExecutionRuns(projectId, params = {}) {
    const query = new URLSearchParams();
    if (params.case_id) query.append('case_id', params.case_id);
    if (params.limit !== undefined) query.append('limit', String(params.limit));
    if (params.offset !== undefined) query.append('offset', String(params.offset));

    const qs = query.toString() ? `?${query.toString()}` : '';
    const url = `${buildUrl(projectId, '/runs')}${qs}`;
    return request(url, { method: 'GET' });
  },

  /**
   * Export explainable findings and report for an execution run.
   */
  async exportRunReport(projectId, runId) {
    const url = buildUrl(projectId, `/runs/${encodeURIComponent(runId)}/report`);
    return request(url, { method: 'GET' });
  },

  // -------------------------------------------------------------
  // Phase 3: Policy Change Diffing, Impact Planning & Regression
  // -------------------------------------------------------------

  /**
   * Compare two accepted policy contracts to generate a deterministic diff.
   */
  async comparePolicyContracts(projectId, payload) {
    const url = buildUrl(projectId, '/regression/compare');
    return request(url, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Retrieve an existing policy comparison record.
   */
  async getPolicyComparison(projectId, comparisonId) {
    const url = buildUrl(projectId, `/regression/comparisons/${encodeURIComponent(comparisonId)}`);
    return request(url, { method: 'GET' });
  },

  /**
   * Create a typed regression impact plan for a comparison and domain binding.
   */
  async createRegressionPlan(projectId, payload) {
    const url = buildUrl(projectId, '/regression/plans');
    return request(url, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Retrieve an existing regression plan by ID.
   */
  async getRegressionPlan(projectId, planId) {
    const url = buildUrl(projectId, `/regression/plans/${encodeURIComponent(planId)}`);
    return request(url, { method: 'GET' });
  },

  /**
   * Selectively regenerate and revalidate affected test cases for a regression plan.
   */
  async regenerateRegressionPlan(projectId, planId) {
    const url = buildUrl(projectId, `/regression/plans/${encodeURIComponent(planId)}/regenerate`);
    return request(url, { method: 'POST' });
  },

  /**
   * Freeze a validated regression plan into an immutable snapshot.
   */
  async freezeRegressionPlan(projectId, planId) {
    const url = buildUrl(projectId, `/regression/plans/${encodeURIComponent(planId)}/freeze`);
    return request(url, { method: 'POST' });
  },

  /**
   * Selectively execute a frozen regression plan against the target adapter.
   */
  async executeRegressionPlan(projectId, planId, payload = {}) {
    const url = buildUrl(projectId, `/regression/plans/${encodeURIComponent(planId)}/execute`);
    return request(url, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Retrieve an evidence-linked regression report for a plan.
   */
  async getRegressionReport(projectId, planId) {
    const url = buildUrl(projectId, `/regression/plans/${encodeURIComponent(planId)}/report`);
    return request(url, { method: 'GET' });
  },

  /**
   * Re-evaluate historical run evidence under candidate policy without fresh agent execution.
   */
  async reEvaluateHistorical(projectId, planId) {
    const url = buildUrl(projectId, `/regression/plans/${encodeURIComponent(planId)}/re-evaluate-historical`);
    return request(url, { method: 'POST' });
  },

  // -------------------------------------------------------------
  // Phase 3: Research Evaluation, Datasets, Reviews & Experiments
  // -------------------------------------------------------------

  /**
   * Register and validate a versioned evaluation dataset.
   */
  async registerEvaluationDataset(projectId, payload) {
    const url = buildUrl(projectId, '/evaluation/datasets');
    return request(url, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * List evaluation datasets for a project.
   */
  async listEvaluationDatasets(projectId) {
    const url = buildUrl(projectId, '/evaluation/datasets');
    return request(url, { method: 'GET' });
  },

  /**
   * Retrieve an evaluation dataset by ID and version.
   */
  async getEvaluationDataset(projectId, datasetId, version = 1) {
    const url = `${buildUrl(projectId, `/evaluation/datasets/${encodeURIComponent(datasetId)}`)}?version=${version}`;
    return request(url, { method: 'GET' });
  },

  /**
   * Freeze an evaluation dataset to guarantee benchmark immutability.
   */
  async freezeEvaluationDataset(projectId, datasetId, version = 1) {
    const url = `${buildUrl(projectId, `/evaluation/datasets/${encodeURIComponent(datasetId)}/freeze`)}?version=${version}`;
    return request(url, { method: 'POST' });
  },

  /**
   * Record an independent reviewer judgment.
   */
  async recordReviewerDecision(projectId, payload) {
    const url = buildUrl(projectId, '/evaluation/reviews');
    return request(url, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Calculate Cohen's Kappa agreement between two independent reviewers.
   */
  async getReviewerAgreement(projectId, reviewer1, reviewer2) {
    const query = new URLSearchParams({
      reviewer_1: reviewer1,
      reviewer_2: reviewer2,
    });
    const url = `${buildUrl(projectId, '/evaluation/reviews/agreement')}?${query.toString()}`;
    return request(url, { method: 'GET' });
  },

  /**
   * Create a reproducible evaluation experiment configuration.
   */
  async createExperiment(projectId, payload) {
    const url = buildUrl(projectId, '/evaluation/experiments');
    return request(url, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Execute reproducible evaluation experiment trials and compute stratified metrics.
   */
  async executeExperiment(projectId, experimentId) {
    const url = buildUrl(projectId, `/evaluation/experiments/${encodeURIComponent(experimentId)}/execute`);
    return request(url, { method: 'POST' });
  },

  /**
   * Retrieve a completed experiment report with uncertainty summaries.
   */
  async getExperimentReport(projectId, experimentId) {
    const url = buildUrl(projectId, `/evaluation/experiments/${encodeURIComponent(experimentId)}/report`);
    return request(url, { method: 'GET' });
  },
};

export { ApiError };
