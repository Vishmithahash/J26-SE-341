/**
 * Component 2: State-Aware Multi-Step Workflow Testing - API Client
 *
 * Scoped strictly to project_id. Connects to backend /api/v1/c2 endpoints.
 * All requests use the shared authenticated `request` client.
 */

import { request } from '../../../services/api.js';

const C2_BASE_PATH = '/api/v1/c2';

export const c2Api = {
  /**
   * List all workflow models registered under the project.
   * GET /api/v1/c2/projects/{project_id}/models
   */
  async listModels(projectId) {
    if (!projectId) throw new Error('projectId is required to list models');
    return request(`${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/models`, {
      method: 'GET',
    });
  },

  /**
   * Get specific model version definition and metadata.
   * GET /api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}
   */
  async getModel(projectId, modelId, version) {
    if (!projectId || !modelId || !version) {
      throw new Error('projectId, modelId, and version are required to fetch a model');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/models/${encodeURIComponent(
        modelId
      )}/versions/${encodeURIComponent(version)}`,
      { method: 'GET' }
    );
  },

  /**
   * Propose and build a candidate reference EFSM model from a WorkflowInputContract.
   * POST /api/v1/c2/projects/{project_id}/models/build?auto_validate=true
   */
  async buildCandidateModel(projectId, workflowInput, autoValidate = true) {
    if (!projectId) throw new Error('projectId is required to build a candidate model');
    const url = `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/models/build?auto_validate=${Boolean(
      autoValidate
    )}`;
    return request(url, {
      method: 'POST',
      body: JSON.stringify(workflowInput),
    });
  },

  /**
   * Directly create a draft EFSM model from a complete EFSMModelDefinition contract.
   * POST /api/v1/c2/projects/{project_id}/models
   */
  async createDraftModel(projectId, modelDefinition) {
    if (!projectId) throw new Error('projectId is required to create a draft model');
    return request(`${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/models`, {
      method: 'POST',
      body: JSON.stringify(modelDefinition),
    });
  },

  /**
   * Run structural and semantic validation on a specific model version.
   * POST /api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/validate
   */
  async validateModel(projectId, modelId, version) {
    if (!projectId || !modelId || !version) {
      throw new Error('projectId, modelId, and version are required to validate a model');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/models/${encodeURIComponent(
        modelId
      )}/versions/${encodeURIComponent(version)}/validate`,
      { method: 'POST' }
    );
  },

  /**
   * Retrieve validation reports history for a model version.
   * GET /api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/validation-reports
   */
  async getValidationReports(projectId, modelId, version) {
    if (!projectId || !modelId || !version) {
      throw new Error('projectId, modelId, and version are required to list validation reports');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/models/${encodeURIComponent(
        modelId
      )}/versions/${encodeURIComponent(version)}/validation-reports`,
      { method: 'GET' }
    );
  },

  /**
   * Check authoritative model readiness for test generation and review.
   * GET /api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/readiness
   */
  async getModelReadiness(projectId, modelId, version) {
    if (!projectId || !modelId || !version) {
      throw new Error('projectId, modelId, and version are required to check model readiness');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/models/${encodeURIComponent(
        modelId
      )}/versions/${encodeURIComponent(version)}/readiness`,
      { method: 'GET' }
    );
  },

  /**
   * Explicitly review and approve a validated model version.
   * POST /api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/approve
   */
  async approveModel(projectId, modelId, version, { reviewerId, reviewBasis, reviewNotes, reviewType }) {
    if (!projectId || !modelId || !version) {
      throw new Error('projectId, modelId, and version are required to approve a model');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/models/${encodeURIComponent(
        modelId
      )}/versions/${encodeURIComponent(version)}/approve`,
      {
        method: 'POST',
        body: JSON.stringify({
          reviewer_id: reviewerId,
          review_basis: reviewBasis,
          review_notes: reviewNotes || null,
          review_type: reviewType || 'SELF_REPORTED_DEVELOPMENT',
        }),
      }
    );
  },

  /**
   * Create a new draft version from an existing (or approved) model version.
   * POST /api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/new-draft
   */
  async createNewDraftVersion(projectId, modelId, version, { newVersion, description }) {
    if (!projectId || !modelId || !version) {
      throw new Error('projectId, modelId, and version are required to create a new draft');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/models/${encodeURIComponent(
        modelId
      )}/versions/${encodeURIComponent(version)}/new-draft`,
      {
        method: 'POST',
        body: JSON.stringify({
          new_version: newVersion,
          description: description || null,
        }),
      }
    );
  },

  // -------------------------------------------------------------------------
  // Phase 2: Test Suite Generation & Inspection Endpoints
  // -------------------------------------------------------------------------

  /**
   * Generate automatic test suite for an approved model version.
   * POST /api/v1/c2/projects/{project_id}/suites/generate
   */
  async generateTestSuite(projectId, payload) {
    if (!projectId) throw new Error('projectId is required to generate a test suite');
    return request(`${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/suites/generate`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * List all test suites for a project.
   * GET /api/v1/c2/projects/{project_id}/suites
   */
  async listTestSuites(projectId) {
    if (!projectId) throw new Error('projectId is required to list test suites');
    return request(`${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/suites`, {
      method: 'GET',
    });
  },

  /**
   * Get specific test suite details and diagnostics.
   * GET /api/v1/c2/projects/{project_id}/suites/{suite_id}
   */
  async getTestSuite(projectId, suiteId) {
    if (!projectId || !suiteId) {
      throw new Error('projectId and suiteId are required to fetch a test suite');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/suites/${encodeURIComponent(suiteId)}`,
      { method: 'GET' }
    );
  },

  /**
   * List test cases in a suite with optional category and readiness filters.
   * GET /api/v1/c2/projects/{project_id}/suites/{suite_id}/cases
   */
  async listTestCases(projectId, suiteId, { category, readiness } = {}) {
    if (!projectId || !suiteId) {
      throw new Error('projectId and suiteId are required to list test cases');
    }
    const params = new URLSearchParams();
    if (category) params.append('category', category);
    if (readiness) params.append('readiness', readiness);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/suites/${encodeURIComponent(suiteId)}/cases${qs}`,
      { method: 'GET' }
    );
  },

  /**
   * Get specific test case detail.
   * GET /api/v1/c2/projects/{project_id}/suites/{suite_id}/cases/{test_id}
   */
  async getTestCaseDetail(projectId, suiteId, testId) {
    if (!projectId || !suiteId || !testId) {
      throw new Error('projectId, suiteId, and testId are required to fetch a test case');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/suites/${encodeURIComponent(
        suiteId
      )}/cases/${encodeURIComponent(testId)}`,
      { method: 'GET' }
    );
  },

  /**
   * Check suite readiness breakdown.
   * GET /api/v1/c2/projects/{project_id}/suites/{suite_id}/readiness
   */
  async getSuiteReadiness(projectId, suiteId) {
    if (!projectId || !suiteId) {
      throw new Error('projectId and suiteId are required to check suite readiness');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/suites/${encodeURIComponent(suiteId)}/readiness`,
      { method: 'GET' }
    );
  },

  /**
   * Export full QA test suite (tester private: contains reference paths, assertions, mutations).
   * GET /api/v1/c2/projects/{project_id}/suites/{suite_id}/export/qa
   */
  async exportQASuite(projectId, suiteId) {
    if (!projectId || !suiteId) {
      throw new Error('projectId and suiteId are required to export QA suite');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/suites/${encodeURIComponent(suiteId)}/export/qa`,
      { method: 'GET' }
    );
  },

  /**
   * Export strictly allowlisted agent task payloads (agent facing: NO reference paths or assertions).
   * GET /api/v1/c2/projects/{project_id}/suites/{suite_id}/export/agent
   */
  async exportAgentTaskPayloads(projectId, suiteId) {
    if (!projectId || !suiteId) {
      throw new Error('projectId and suiteId are required to export agent task payloads');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/suites/${encodeURIComponent(suiteId)}/export/agent`,
      { method: 'GET' }
    );
  },

  /**
   * Get allowlisted agent task payload for a single case.
   * GET /api/v1/c2/projects/{project_id}/suites/{suite_id}/cases/{test_id}/agent-payload
   */
  async getCaseAgentPayload(projectId, suiteId, testId) {
    if (!projectId || !suiteId || !testId) {
      throw new Error('projectId, suiteId, and testId are required to fetch agent payload');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/suites/${encodeURIComponent(
        suiteId
      )}/cases/${encodeURIComponent(testId)}/agent-payload`,
      { method: 'GET' }
    );
  },

  // -------------------------------------------------------------------------
  // Phase 2: Execution & Conformance Evaluation Endpoints
  // -------------------------------------------------------------------------

  /**
   * Execute an isolated test case with the backend orchestration pipeline.
   * POST /api/v1/c2/projects/{project_id}/suites/{suite_id}/cases/{test_id}/run
   */
  async runCase(projectId, suiteId, testId, runId = null) {
    if (!projectId || !suiteId || !testId) {
      throw new Error('projectId, suiteId, and testId are required to run a test case');
    }
    const qs = runId ? `?run_id=${encodeURIComponent(runId)}` : '';
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/suites/${encodeURIComponent(
        suiteId
      )}/cases/${encodeURIComponent(testId)}/run${qs}`,
      { method: 'POST' }
    );
  },

  /**
   * Run a bounded batch of test cases for a suite.
   * POST /api/v1/c2/projects/{project_id}/suites/{suite_id}/run
   */
  async runSuite(projectId, suiteId, maxCases = 50) {
    if (!projectId || !suiteId) {
      throw new Error('projectId and suiteId are required to run a test suite');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/suites/${encodeURIComponent(suiteId)}/run`,
      {
        method: 'POST',
        body: JSON.stringify({ max_cases: maxCases }),
      }
    );
  },

  /**
   * Execute a clearly labeled offline synthetic demonstration of C2 workflow evaluation.
   * POST /api/v1/c2/projects/{project_id}/demonstrations/run
   */
  async runSyntheticDemonstration(projectId, requestData) {
    if (!projectId) throw new Error('projectId is required to run a demonstration');
    return request(`${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/demonstrations/run`, {
      method: 'POST',
      body: JSON.stringify(requestData),
    });
  },

  /**
   * List evaluation results for a project.
   * GET /api/v1/c2/projects/{project_id}/evaluations
   */
  async listEvaluations(projectId, { suiteId, testId, verdict } = {}) {
    if (!projectId) throw new Error('projectId is required to list evaluations');
    const params = new URLSearchParams();
    if (suiteId) params.append('suite_id', suiteId);
    if (testId) params.append('test_id', testId);
    if (verdict) params.append('verdict', verdict);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return request(`${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/evaluations${qs}`, {
      method: 'GET',
    });
  },

  /**
   * Get specific evaluation result.
   * GET /api/v1/c2/projects/{project_id}/evaluations/{evaluation_id}
   */
  async getEvaluation(projectId, evaluationId) {
    if (!projectId || !evaluationId) {
      throw new Error('projectId and evaluationId are required to fetch an evaluation');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/evaluations/${encodeURIComponent(evaluationId)}`,
      { method: 'GET' }
    );
  },

  /**
   * Retrieve original retained execution evidence for a run.
   * GET /api/v1/c2/projects/{project_id}/evidence/{run_id}
   */
  async getRetainedEvidence(projectId, runId) {
    if (!projectId || !runId) {
      throw new Error('projectId and runId are required to fetch retained evidence');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/evidence/${encodeURIComponent(runId)}`,
      { method: 'GET' }
    );
  },

  /**
   * Re-evaluate a previous execution from retained evidence.
   * POST /api/v1/c2/projects/{project_id}/evaluations/{evaluation_id}/re-evaluate
   */
  async reEvaluateExecution(projectId, evaluationId, { evaluatorVersion, evaluatorConfig } = {}) {
    if (!projectId || !evaluationId) {
      throw new Error('projectId and evaluationId are required to re-evaluate');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/evaluations/${encodeURIComponent(
        evaluationId
      )}/re-evaluate`,
      {
        method: 'POST',
        body: JSON.stringify({
          evaluator_version: evaluatorVersion || null,
          evaluator_config: evaluatorConfig || null,
        }),
      }
    );
  },

  /**
   * Independently verify replay reproduction from retained raw evidence.
   * POST /api/v1/c2/projects/{project_id}/evaluations/{evaluation_id}/verify-reproduction
   */
  async verifyReproduction(projectId, evaluationId) {
    if (!projectId || !evaluationId) {
      throw new Error('projectId and evaluationId are required to verify reproduction');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/evaluations/${encodeURIComponent(
        evaluationId
      )}/verify-reproduction`,
      { method: 'POST' }
    );
  },
};

