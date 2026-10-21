import { request } from '../../services/api.js';

export const FAULT_FAMILIES = {
  TIMEOUT_DISCONNECTION: 'TIMEOUT_DISCONNECTION',
  TRANSIENT_5XX: 'TRANSIENT_5XX',
  RATE_LIMIT_429: 'RATE_LIMIT_429',
  TOOL_UNAVAILABILITY: 'TOOL_UNAVAILABILITY',
  MALFORMED_RESPONSE: 'MALFORMED_RESPONSE',
};

export const EFFECT_PHASES = {
  BEFORE_EFFECT: 'BEFORE_EFFECT',
  AFTER_COMMIT: 'AFTER_COMMIT',
  PARTIAL_EFFECT: 'PARTIAL_EFFECT',
  NOT_APPLICABLE: 'NOT_APPLICABLE',
};

export const INTERCEPTION_HOOKS = {
  BEFORE_TOOL_CALL: 'BEFORE_TOOL_CALL',
  AFTER_TOOL_CALL: 'AFTER_TOOL_CALL',
  AROUND_TOOL_CALL: 'AROUND_TOOL_CALL',
  APPLICATION_AWARE_HOOK: 'APPLICATION_AWARE_HOOK',
};

export const c3Api = {
  /**
   * Retrieve authoritative operational fault families catalogue.
   */
  async getFaultCatalog(signal) {
    return request('/api/v1/c3/fault-catalog', {
      method: 'GET',
      signal,
    });
  },

  /**
   * Deterministically validate candidate fault case against adapter manifest,
   * fixture metadata, and recovery contract.
   */
  async validateCase(payload, signal) {
    return request('/api/v1/c3/cases/validate', {
      method: 'POST',
      body: JSON.stringify(payload),
      signal,
    });
  },

  /**
   * Pure deterministic feasible fault case generation, deduplication, and suite freezing.
   */
  async generateCases(payload, signal) {
    return request('/api/v1/c3/cases/generate', {
      method: 'POST',
      body: JSON.stringify(payload),
      signal,
    });
  },

  /**
   * Persist a verified frozen suite and candidate case snapshots into project scope.
   */
  async importSuite(projectId, frozenSuite, signal) {
    if (!projectId) {
      throw new Error('Project ID is required to import a frozen suite.');
    }
    return request('/api/v1/c3/suites/import', {
      method: 'POST',
      body: JSON.stringify({
        project_id: projectId,
        frozen_suite: frozenSuite,
      }),
      signal,
    });
  },

  /**
   * List stored frozen suites for an authorized project.
   */
  async listSuites(projectId, { domain, limit = 50, offset = 0 } = {}, signal) {
    if (!projectId) {
      throw new Error('Project ID is required to list stored suites.');
    }
    const params = new URLSearchParams();
    params.set('project_id', projectId);
    params.set('limit', String(limit));
    params.set('offset', String(offset));
    if (domain) params.set('domain', domain);

    return request(`/api/v1/c3/suites?${params.toString()}`, {
      method: 'GET',
      signal,
    });
  },

  /**
   * Retrieve stored frozen suite by ID or SHA-256 digest.
   */
  async getSuite(projectId, suiteIdOrDigest, signal) {
    if (!projectId) {
      throw new Error('Project ID is required to retrieve a stored suite.');
    }
    return request(
      `/api/v1/c3/suites/${encodeURIComponent(suiteIdOrDigest)}?project_id=${encodeURIComponent(projectId)}`,
      {
        method: 'GET',
        signal,
      }
    );
  },

  /**
   * List stored candidate fault cases for a project.
   */
  async listCases(
    projectId,
    { suiteDigest, faultFamily, effectPhase, limit = 50, offset = 0 } = {},
    signal
  ) {
    if (!projectId) {
      throw new Error('Project ID is required to list stored cases.');
    }
    const params = new URLSearchParams();
    params.set('project_id', projectId);
    params.set('limit', String(limit));
    params.set('offset', String(offset));
    if (suiteDigest) params.set('suite_digest', suiteDigest);
    if (faultFamily) params.set('fault_family', faultFamily);
    if (effectPhase) params.set('effect_phase', effectPhase);

    return request(`/api/v1/c3/cases?${params.toString()}`, {
      method: 'GET',
      signal,
    });
  },

  /**
   * Retrieve snapshot of an individual stored candidate fault case.
   */
  async getCase(projectId, caseId, suiteDigest, signal) {
    if (!projectId) {
      throw new Error('Project ID is required to retrieve a stored case.');
    }
    const params = new URLSearchParams();
    params.set('project_id', projectId);
    if (suiteDigest) params.set('suite_digest', suiteDigest);

    return request(`/api/v1/c3/cases/${encodeURIComponent(caseId)}?${params.toString()}`, {
      method: 'GET',
      signal,
    });
  },

  /**
   * Deterministically evaluate recovery rules against evidence and C2 facts.
   */
  async evaluateRecovery(payload, signal) {
    return request('/api/v1/c3/recovery/evaluate', {
      method: 'POST',
      body: JSON.stringify(payload),
      signal,
    });
  },
};
