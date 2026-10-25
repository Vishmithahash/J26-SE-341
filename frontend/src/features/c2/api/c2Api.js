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
  async buildCandidateModel(projectId, workflowInput, autoValidate = true, mode = null) {
    if (!projectId) throw new Error('projectId is required to build a candidate model');
    let url = `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/models/build?auto_validate=${Boolean(
      autoValidate
    )}`;
    if (mode) {
      url += `&mode=${encodeURIComponent(mode)}`;
    }
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
  async listEvaluations(projectId, { suiteId, suite_id, testId, test_id, verdict, origin, modelVersion, model_version, limit, offset } = {}) {
    if (!projectId) throw new Error('projectId is required to list evaluations');
    const params = new URLSearchParams();
    const sid = suiteId || suite_id;
    const tid = testId || test_id;
    const orig = origin;
    const mver = modelVersion || model_version;
    if (sid) params.append('suite_id', sid);
    if (tid) params.append('test_id', tid);
    if (verdict) params.append('verdict', verdict);
    if (orig) params.append('origin', orig);
    if (mver) params.append('model_version', mver);
    if (limit) params.append('limit', limit);
    if (offset) params.append('offset', offset);
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

  // -------------------------------------------------------------------------
  // Phase 3: Coverage, Reports & Research Endpoints
  // -------------------------------------------------------------------------

  /**
   * Retrieve detailed observed coverage for a single evaluation run.
   * GET /api/v1/c2/projects/{project_id}/evaluations/{evaluation_id}/coverage
   */
  async getEvaluationCoverage(projectId, evaluationId) {
    if (!projectId || !evaluationId) {
      throw new Error('projectId and evaluationId are required to fetch coverage');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/evaluations/${encodeURIComponent(
        evaluationId
      )}/coverage`,
      { method: 'GET' }
    );
  },

  /**
   * Retrieve aggregate observed coverage for a suite across evaluated runs.
   * GET /api/v1/c2/projects/{project_id}/suites/{suite_id}/coverage
   */
  async getSuiteCoverage(projectId, suiteId) {
    if (!projectId || !suiteId) {
      throw new Error('projectId and suiteId are required to fetch suite coverage');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/suites/${encodeURIComponent(
        suiteId
      )}/coverage`,
      { method: 'GET' }
    );
  },

  /**
   * Retrieve structured C2 report contribution for a single evaluation run.
   * GET /api/v1/c2/projects/{project_id}/evaluations/{evaluation_id}/report
   */
  async getRunReport(projectId, evaluationId) {
    if (!projectId || !evaluationId) {
      throw new Error('projectId and evaluationId are required to fetch run report');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/evaluations/${encodeURIComponent(
        evaluationId
      )}/report`,
      { method: 'GET' }
    );
  },

  /**
   * Retrieve aggregated C2 report for an entire test suite.
   * GET /api/v1/c2/projects/{project_id}/suites/{suite_id}/report
   */
  async getSuiteReport(projectId, suiteId) {
    if (!projectId || !suiteId) {
      throw new Error('projectId and suiteId are required to fetch suite report');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/suites/${encodeURIComponent(
        suiteId
      )}/report`,
      { method: 'GET' }
    );
  },

  /**
   * Export versioned C2 report contribution JSON and check shared aggregator publishing status.
   * POST /api/v1/c2/projects/{project_id}/evaluations/{evaluation_id}/export-report
   */
  async exportC2ReportContribution(projectId, evaluationId) {
    if (!projectId || !evaluationId) {
      throw new Error('projectId and evaluationId are required to export report contribution');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/evaluations/${encodeURIComponent(
        evaluationId
      )}/export-report`,
      { method: 'POST' }
    );
  },

  /**
   * Import and validate an experiment dataset manifest.
   * POST /api/v1/c2/projects/{project_id}/datasets
   */
  async importExperimentDataset(projectId, manifest) {
    if (!projectId) throw new Error('projectId is required to import experiment dataset');
    return request(`${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/datasets`, {
      method: 'POST',
      body: JSON.stringify(manifest),
    });
  },

  /**
   * List all versioned experiment datasets for a project.
   * GET /api/v1/c2/projects/{project_id}/datasets
   */
  async listExperimentDatasets(projectId) {
    if (!projectId) throw new Error('projectId is required to list experiment datasets');
    return request(`${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/datasets`, {
      method: 'GET',
    });
  },

  /**
   * Retrieve full experiment dataset manifest.
   * GET /api/v1/c2/projects/{project_id}/datasets/{dataset_id}/versions/{version}
   */
  async getExperimentDataset(projectId, datasetId, version) {
    if (!projectId || !datasetId || !version) {
      throw new Error('projectId, datasetId, and version are required to fetch dataset');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/datasets/${encodeURIComponent(
        datasetId
      )}/versions/${encodeURIComponent(version)}`,
      { method: 'GET' }
    );
  },

  /**
   * Freeze an experiment dataset manifest to lock partitions and labels.
   * POST /api/v1/c2/projects/{project_id}/datasets/{dataset_id}/versions/{version}/freeze
   */
  async freezeExperimentDataset(projectId, datasetId, version) {
    if (!projectId || !datasetId || !version) {
      throw new Error('projectId, datasetId, and version are required to freeze dataset');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/datasets/${encodeURIComponent(
        datasetId
      )}/versions/${encodeURIComponent(version)}/freeze`,
      { method: 'POST' }
    );
  },

  /**
   * Configure and execute comparative baseline experiment (B1-B4).
   * POST /api/v1/c2/projects/{project_id}/experiments
   */
  async createAndRunExperiment(projectId, requestData) {
    if (!projectId) throw new Error('projectId is required to run an experiment');
    return request(`${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/experiments`, {
      method: 'POST',
      body: JSON.stringify(requestData),
    });
  },

  /**
   * List comparative baseline experiments for a project.
   * GET /api/v1/c2/projects/{project_id}/experiments
   */
  async listExperiments(projectId, datasetId = null) {
    if (!projectId) throw new Error('projectId is required to list experiments');
    const qs = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : '';
    return request(`${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/experiments${qs}`, {
      method: 'GET',
    });
  },

  /**
   * Retrieve full comparative research metrics report across B1, B2, B3, and B4.
   * GET /api/v1/c2/projects/{project_id}/experiments/{experiment_id}/baselines
   */
  async getExperimentBaselines(projectId, experimentId) {
    if (!projectId || !experimentId) {
      throw new Error('projectId and experimentId are required to fetch baselines');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/experiments/${encodeURIComponent(
        experimentId
      )}/baselines`,
      { method: 'GET' }
    );
  },

  /**
   * Retrieve fine-grained case prediction contracts and diagnostic records.
   * GET /api/v1/c2/projects/{project_id}/experiments/{experiment_id}/cases
   */
  async getExperimentCaseResults(projectId, experimentId, methodId = null) {
    if (!projectId || !experimentId) {
      throw new Error('projectId and experimentId are required to fetch case results');
    }
    const qs = methodId ? `?method_id=${encodeURIComponent(methodId)}` : '';
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/experiments/${encodeURIComponent(
        experimentId
      )}/cases${qs}`,
      { method: 'GET' }
    );
  },

  /**
   * Export benchmark comparison metrics in JSON or summary CSV format.
   * GET /api/v1/c2/projects/{project_id}/experiments/{experiment_id}/export?format={format}
   */
  async exportExperimentMetrics(projectId, experimentId, format = 'json') {
    if (!projectId || !experimentId) {
      throw new Error('projectId and experimentId are required to export experiment metrics');
    }
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/experiments/${encodeURIComponent(
        experimentId
      )}/export?format=${encodeURIComponent(format)}`,
      { method: 'GET' }
    );
  },

  // Ergonomic aliases for evaluation reports, replay reproduction and datasets
  async getEvaluationReport(projectId, evaluationId) {
    return this.getRunReport(projectId, evaluationId);
  },

  async exportReport(projectId, evaluationId, _format = 'json') {
    return this.exportC2ReportContribution(projectId, evaluationId);
  },

  async replayEvaluation(projectId, evaluationId, options = {}) {
    return this.reEvaluateExecution(projectId, evaluationId, options);
  },

  async listDatasets(projectId) {
    return this.listExperimentDatasets(projectId);
  },

  async getDataset(projectId, datasetId, version) {
    return this.getExperimentDataset(projectId, datasetId, version);
  },

  async freezeDataset(projectId, datasetId, version) {
    return this.freezeExperimentDataset(projectId, datasetId, version);
  },

  // ---------------------------------------------------------------------------
  // Live NexaCart execution (C2 individual workflow on the real application)
  // ---------------------------------------------------------------------------

  /**
   * NexaCart health, QA admin credentials and harness capabilities. Creates no data.
   * GET /api/v1/c2/projects/{project_id}/live/nexacart/readiness
   */
  async getLiveReadiness(projectId) {
    if (!projectId) throw new Error('projectId is required to check live NexaCart readiness');
    return request(`${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/live/nexacart/readiness`, {
      method: 'GET',
    });
  },

  /**
   * NexaCart reference workflows with their import, approval and suite status.
   * GET /api/v1/c2/projects/{project_id}/live/nexacart/workflows
   */
  async listLiveWorkflows(projectId) {
    if (!projectId) throw new Error('projectId is required to list NexaCart workflows');
    return request(`${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/live/nexacart/workflows`, {
      method: 'GET',
    });
  },

  /**
   * Import a NexaCart reference EFSM as a DRAFT model (validate and approve it on the Models tab).
   * POST /api/v1/c2/projects/{project_id}/live/nexacart/workflows/{model_id}/import
   */
  async importLiveWorkflow(projectId, modelId) {
    if (!projectId || !modelId) throw new Error('projectId and modelId are required to import a workflow');
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/live/nexacart/workflows/${encodeURIComponent(
        modelId
      )}/import`,
      { method: 'POST' }
    );
  },

  /**
   * Start a background live execution of generated cases (poll getLiveExecution).
   * POST /api/v1/c2/projects/{project_id}/live/nexacart/executions
   */
  async startLiveExecution(projectId, { suiteId, testIds } = {}) {
    if (!projectId || !suiteId) throw new Error('projectId and suiteId are required to start a live execution');
    return request(`${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/live/nexacart/executions`, {
      method: 'POST',
      body: JSON.stringify({ suite_id: suiteId, test_ids: testIds && testIds.length ? testIds : null }),
    });
  },

  /**
   * GET /api/v1/c2/projects/{project_id}/live/nexacart/executions/{execution_id}
   */
  async getLiveExecution(projectId, executionId) {
    if (!projectId || !executionId) throw new Error('projectId and executionId are required');
    return request(
      `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/live/nexacart/executions/${encodeURIComponent(
        executionId
      )}`,
      { method: 'GET' }
    );
  },

  /**
   * GET /api/v1/c2/projects/{project_id}/live/nexacart/executions?suite_id=
   */
  async listLiveExecutions(projectId, suiteId = null) {
    if (!projectId) throw new Error('projectId is required to list live executions');
    let url = `${C2_BASE_PATH}/projects/${encodeURIComponent(projectId)}/live/nexacart/executions`;
    if (suiteId) url += `?suite_id=${encodeURIComponent(suiteId)}`;
    return request(url, { method: 'GET' });
  },
};


