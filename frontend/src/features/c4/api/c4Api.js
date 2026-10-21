/**
 * Component 4 (C4) - Policy-Aware Safety & Prompt-Injection Testing
 * API Client Adapter for C4 Endpoints
 */

import { request, ApiError } from '../../../services/api.js';

const C4_API_BASE = (typeof import.meta !== 'undefined' && import.meta.env?.VITE_BACKEND_URL) || 'http://127.0.0.1:8000';

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
};

export { ApiError };
