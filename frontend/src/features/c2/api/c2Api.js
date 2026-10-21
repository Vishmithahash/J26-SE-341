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
};
