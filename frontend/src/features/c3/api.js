import { api, request } from '../../services/api.js';

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

// ---------------------------------------------------------------------------
// Phase 2 Distinct Status Dimensions
// ---------------------------------------------------------------------------

export const READINESS_STATUS = {
  READY: 'READY',
  NOT_READY: 'NOT_READY',
  BLOCKED: 'BLOCKED',
  TEST_NOT_READY: 'TEST_NOT_READY',
};

export const EXECUTION_TRACKING_STATUS = {
  PLANNED: 'PLANNED',
  RUNNING: 'RUNNING',
  COMPLETED: 'COMPLETED',
  CANCELLED: 'CANCELLED',
  INTERRUPTED: 'INTERRUPTED',
  ERROR: 'ERROR',
};

export const TRIAL_EXECUTION_STATUS = {
  COMPLETED: 'COMPLETED',
  EXECUTION_ERROR: 'EXECUTION_ERROR',
  CANCELLED: 'CANCELLED',
  TIMEOUT: 'TIMEOUT',
};

export const EXPOSURE_STATUS = {
  CONFIRMED: 'CONFIRMED',
  NOT_TRIGGERED: 'NOT_TRIGGERED',
  EXPOSURE_UNKNOWN: 'EXPOSURE_UNKNOWN',
};

export const CLEAN_QUALIFICATION = {
  QUALIFIED: 'QUALIFIED',
  DISQUALIFIED: 'DISQUALIFIED',
  UNKNOWN: 'UNKNOWN',
};

export const FIXTURE_COMPARABILITY = {
  EQUIVALENT_LOGICAL_STATE: 'EQUIVALENT_LOGICAL_STATE',
  NON_EQUIVALENT: 'NON_EQUIVALENT',
  UNKNOWN: 'UNKNOWN',
};

export const RECOVERY_VERDICT = {
  PASS_COMPLETED: 'PASS_COMPLETED',
  PASS_GRACEFUL: 'PASS_GRACEFUL',
  FAIL: 'FAIL',
  INCONCLUSIVE: 'INCONCLUSIVE',
};

export const RULE_EVALUATION_STATUS = {
  SATISFIED: 'SATISFIED',
  VIOLATED: 'VIOLATED',
  UNKNOWN: 'UNKNOWN',
  NOT_APPLICABLE: 'NOT_APPLICABLE',
};

export const EVALUATION_STATUS = {
  EVALUATED: 'EVALUATED',
  NOT_EVALUATED: 'NOT_EVALUATED',
  EVALUATION_ERROR: 'EVALUATION_ERROR',
};

export const C2_FACT_VALUE = {
  TRUE: 'TRUE',
  FALSE: 'FALSE',
  UNKNOWN: 'UNKNOWN',
};

export const RECOVERY_RULE_ID = {
  RULE_COMPLETION: 'RULE_COMPLETION',
  RULE_GRACEFUL_STOPPING: 'RULE_GRACEFUL_STOPPING',
  RULE_BUDGETS: 'RULE_BUDGETS',
  RULE_DUPLICATE_EFFECTS: 'RULE_DUPLICATE_EFFECTS',
  RULE_UNSAFE_RETRIES: 'RULE_UNSAFE_RETRIES',
  RULE_TRUTHFUL_COMPLETION: 'RULE_TRUTHFUL_COMPLETION',
};

export const RECOVERY_ACTOR = {
  SCRIPTED_CALLER: 'SCRIPTED_CALLER',
  AGENT: 'AGENT',
  SDK: 'SDK',
  ADAPTER: 'ADAPTER',
  MIDDLEWARE: 'MIDDLEWARE',
  UNKNOWN: 'UNKNOWN',
};

export const TARGET_MODE = {
  DEMONSTRATION: 'DEMONSTRATION',
  AUT: 'AUT',
  LIVE_AUT: 'LIVE_AUT',
};

export const CALLER_IDENTITY = {
  SCRIPTED_CALLER: 'SCRIPTED_CALLER',
  AGENT: 'AGENT',
};

export const TIMEOUT_BOUNDARY_TYPE = {
  CALLER_TIMEOUT_EXCEEDED: 'CALLER_TIMEOUT_EXCEEDED',
  ELAPSED_TOOL_CALL_DEADLINE: 'ELAPSED_TOOL_CALL_DEADLINE',
  ACTUAL_TRANSPORT_TIMEOUT: 'ACTUAL_TRANSPORT_TIMEOUT',
  IMMEDIATE_SYNTHETIC_EXCEPTION: 'IMMEDIATE_SYNTHETIC_EXCEPTION',
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

  // -------------------------------------------------------------------------
  // Phase 2: Executions, Matched Pairs, Evidence Import, and Reporting
  // -------------------------------------------------------------------------

  /**
   * List tracked suite executions for an authorized project.
   */
  async listExecutions(
    projectId,
    { suiteDigest, status, targetMode, limit = 50, offset = 0 } = {},
    signal
  ) {
    if (!projectId) {
      throw new Error('Project ID is required to list executions.');
    }
    const params = new URLSearchParams();
    params.set('project_id', projectId);
    params.set('limit', String(limit));
    params.set('offset', String(offset));
    if (suiteDigest) params.set('suite_digest', suiteDigest);
    if (status) params.set('status', status);
    if (targetMode) params.set('target_mode', targetMode);

    return request(`/api/v1/c3/executions?${params.toString()}`, {
      method: 'GET',
      signal,
    });
  },

  /**
   * Retrieve a single tracked execution status by ID.
   */
  async getExecution(projectId, executionId, signal) {
    if (!projectId) {
      throw new Error('Project ID is required to retrieve an execution.');
    }
    return request(
      `/api/v1/c3/executions/${encodeURIComponent(executionId)}?project_id=${encodeURIComponent(projectId)}`,
      {
        method: 'GET',
        signal,
      }
    );
  },

  /**
   * Import an execution artifact without executing it.
   */
  async importExecution(payload, signal) {
    if (!payload?.project_id) {
      throw new Error('Project ID is required to import an execution artifact.');
    }
    return request('/api/v1/c3/executions/import', {
      method: 'POST',
      body: JSON.stringify(payload),
      signal,
    });
  },

  /**
   * List matched trial pairs for an authorized project.
   */
  async listPairs(
    projectId,
    {
      executionId,
      caseId,
      runId,
      exposureStatus,
      cleanQualification,
      faultExecutionStatus,
      limit = 50,
      offset = 0,
    } = {},
    signal
  ) {
    if (!projectId) {
      throw new Error('Project ID is required to list matched pairs.');
    }
    const params = new URLSearchParams();
    params.set('project_id', projectId);
    params.set('limit', String(limit));
    params.set('offset', String(offset));
    if (executionId) params.set('execution_id', executionId);
    if (caseId) params.set('case_id', caseId);
    if (runId) params.set('run_id', runId);
    if (exposureStatus) params.set('exposure_status', exposureStatus);
    if (cleanQualification) params.set('clean_qualification', cleanQualification);
    if (faultExecutionStatus) params.set('fault_execution_status', faultExecutionStatus);

    return request(`/api/v1/c3/pairs?${params.toString()}`, {
      method: 'GET',
      signal,
    });
  },

  /**
   * Retrieve an individual matched trial pair record and linked evidence.
   */
  async getPair(projectId, pairId, signal) {
    if (!projectId) {
      throw new Error('Project ID is required to retrieve a matched pair.');
    }
    return request(
      `/api/v1/c3/pairs/${encodeURIComponent(pairId)}?project_id=${encodeURIComponent(projectId)}`,
      {
        method: 'GET',
        signal,
      }
    );
  },

  /**
   * Import matched trial pair evidence.
   */
  async importPair(payload, signal) {
    if (!payload?.project_id) {
      throw new Error('Project ID is required to import matched pair evidence.');
    }
    return request('/api/v1/c3/pairs/import', {
      method: 'POST',
      body: JSON.stringify(payload),
      signal,
    });
  },

  /**
   * Compute and persist recovery evaluation from stored evidence.
   */
  async computeEvaluation(payload, signal) {
    if (!payload?.project_id) {
      throw new Error('Project ID is required to compute evaluation.');
    }
    return request('/api/v1/c3/evaluations/compute', {
      method: 'POST',
      body: JSON.stringify(payload),
      signal,
    });
  },

  /**
   * List stored recovery evaluations.
   */
  async listEvaluations(
    projectId,
    {
      pairId,
      caseId,
      recoveryVerdict,
      evaluatorVersion,
      ruleSetVersion,
      limit = 50,
      offset = 0,
    } = {},
    signal
  ) {
    if (!projectId) {
      throw new Error('Project ID is required to list evaluations.');
    }
    const params = new URLSearchParams();
    params.set('project_id', projectId);
    params.set('limit', String(limit));
    params.set('offset', String(offset));
    if (pairId) params.set('pair_id', pairId);
    if (caseId) params.set('case_id', caseId);
    if (recoveryVerdict) params.set('recovery_verdict', recoveryVerdict);
    if (evaluatorVersion) params.set('evaluator_version', evaluatorVersion);
    if (ruleSetVersion) params.set('rule_set_version', ruleSetVersion);

    return request(`/api/v1/c3/evaluations?${params.toString()}`, {
      method: 'GET',
      signal,
    });
  },

  /**
   * Retrieve an individual stored recovery evaluation by ID.
   */
  async getEvaluation(projectId, evaluationId, signal) {
    if (!projectId) {
      throw new Error('Project ID is required to retrieve an evaluation.');
    }
    return request(
      `/api/v1/c3/evaluations/${encodeURIComponent(evaluationId)}?project_id=${encodeURIComponent(projectId)}`,
      {
        method: 'GET',
        signal,
      }
    );
  },

  /**
   * Retrieve comprehensive structured execution report.
   */
  async getExecutionReport(projectId, executionId, signal) {
    if (!projectId) {
      throw new Error('Project ID is required to retrieve an execution report.');
    }
    return request(
      `/api/v1/c3/reports/executions/${encodeURIComponent(executionId)}?project_id=${encodeURIComponent(projectId)}`,
      {
        method: 'GET',
        signal,
      }
    );
  },

  /**
   * Helper to build export CSV URL for an execution report.
   */
  getExecutionReportCsvUrl(projectId, executionId) {
    return `/api/v1/c3/reports/executions/${encodeURIComponent(executionId)}/export?project_id=${encodeURIComponent(projectId)}`;
  },

  /**
   * Protected download of execution report CSV using authenticated fetch and Blob flow.
   * Never places authentication tokens in URLs.
   * Releases object URLs after triggering download.
   */
  async downloadExecutionReportCsv(projectId, executionId) {
    if (!projectId) {
      throw new Error('Project ID is required to export execution report CSV.');
    }
    if (!executionId) {
      throw new Error('Execution ID is required to export execution report CSV.');
    }
    const token = api.getToken();
    const headers = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    const url = `/api/v1/c3/reports/executions/${encodeURIComponent(executionId)}/export?project_id=${encodeURIComponent(projectId)}`;
    let response;
    try {
      response = await fetch(url, { method: 'GET', headers });
    } catch {
      throw new Error('Network error: unable to download CSV report.');
    }

    if (!response.ok) {
      let detail = `Download failed with status ${response.status}`;
      try {
        const errJson = await response.json();
        if (errJson.detail) {
          detail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
        }
      } catch {
        // non-JSON response body
      }
      throw new Error(detail);
    }

    const blob = await response.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    const filename = `report_${executionId}.csv`;
    try {
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      return { success: true, filename };
    } finally {
      window.URL.revokeObjectURL(blobUrl);
    }
  },
};

