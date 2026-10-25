import { request, ApiError } from '../../services/api.js';

/**
 * Component 1: Explainable Tool-Call Correctness Testing API Client.
 * Communicates with backend endpoints under /api/v1/projects/{projectId}/c1.
 * Strictly scopes calls to the active project ID and attaches the X-Project-ID header.
 */

export const CASE_CATEGORIES = [
  { id: 'CORRECT_BEHAVIOUR', label: 'Correct Behaviour', desc: 'Compliant invocation satisfying requirements' },
  { id: 'WRONG_TOOL_SELECTION', label: 'Wrong Tool Selection', desc: 'Invoking unneeded or forbidden tool' },
  { id: 'MISSING_ARGUMENTS', label: 'Missing Arguments', desc: 'Omitting required non-null arguments' },
  { id: 'MALFORMED_ARGUMENT_NAMES_OR_TYPES', label: 'Malformed Argument Names/Types', desc: 'Typo in parameter key or wrong type' },
  { id: 'INCORRECT_ARGUMENT_VALUES', label: 'Incorrect Argument Values', desc: 'Values violating bounded domain constraints' },
  { id: 'CONTEXTUAL_SOURCE_MISMATCH', label: 'Contextual Source Mismatch', desc: 'Value does not match contextual source data' },
  { id: 'INSUFFICIENT_EVIDENCE', label: 'Insufficient Evidence', desc: 'Required channel cannot provide conclusive verification' },
];

export const EVIDENCE_CHANNELS = [
  { id: 'AGENT_TRACE', label: 'Agent Trace' },
  { id: 'TOOL_CALL_LOG', label: 'Tool Call Log' },
  { id: 'AUT_DATABASE_DIFF', label: 'AUT Database Diff' },
  { id: 'HTTP_TRAFFIC', label: 'HTTP Traffic' },
  { id: 'CONSOLE_OUTPUT', label: 'Console Output' },
  { id: 'SYNTHETIC_FIXTURE', label: 'Synthetic Fixture (not application data)' },
];

export const COMPARISON_OPERATORS = [
  'EQUALS',
  'NOT_EQUALS',
  'GREATER_THAN',
  'LESS_THAN',
  'GREATER_EQUAL',
  'LESS_EQUAL',
  'IN_SET',
  'NOT_IN_SET',
  'REGEX_MATCH',
  'CONTAINS',
  'STARTS_WITH',
  'ENDS_WITH',
  'TYPE_EQUALS',
];

export const FIELD_PRESENCE_OPTIONS = [
  { id: 'ALLOWED', label: 'Allowed (Optional / Any)' },
  { id: 'REQUIRED_NON_NULL', label: 'Required Non-Null' },
  { id: 'REQUIRED_EXPLICIT_NULL', label: 'Required Explicit Null (key: null)' },
  { id: 'REQUIRED_PRESENT', label: 'Required Present (key must exist)' },
  { id: 'FORBIDDEN_OR_MISSING', label: 'Forbidden / Must Be Omitted' },
];

export const SOURCE_RELATIONSHIP_TYPES = [
  'EXACT_MATCH',
  'SUBSET_OF',
  'CASE_INSENSITIVE_MATCH',
  'NUMERIC_TOLERANCE',
];

export const CORRECTNESS_VERDICTS = {
  PASS: 'PASS',
  FAIL: 'FAIL',
  INCONCLUSIVE: 'INCONCLUSIVE',
};

export const RUN_STATUSES = {
  PENDING: 'PENDING',
  INITIALIZING: 'INITIALIZING',
  RUNNING: 'RUNNING',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
  ABORTED: 'ABORTED',
};

// A run the backend is still executing (not yet COMPLETED, FAILED or ABORTED)
export const isRunInFlight = (status) =>
  status === RUN_STATUSES.PENDING ||
  status === RUN_STATUSES.INITIALIZING ||
  status === RUN_STATUSES.RUNNING;

export const CASE_EXECUTION_STATUSES = {
  NOT_EXECUTED: 'NOT_EXECUTED',
  INITIALIZING: 'INITIALIZING',
  RUNNING: 'RUNNING',
  EXECUTED: 'EXECUTED',
  EXECUTION_ERROR: 'EXECUTION_ERROR',
  ABORTED: 'ABORTED',
};

export const TRACE_COMPLETENESS = {
  COMPLETE: 'COMPLETE',
  INCOMPLETE: 'INCOMPLETE',
  CORRUPTED: 'CORRUPTED',
  MISSING: 'MISSING',
};

export const CAUSE_CATEGORIES = {
  SUPPORTED_APPLICATION_CODE_DEFECT: 'SUPPORTED_APPLICATION_CODE_DEFECT',
  AGENT_BEHAVIOUR: 'AGENT_BEHAVIOUR',
  SPECIFICATION_OR_EXPECTATION_PROBLEM: 'SPECIFICATION_OR_EXPECTATION_PROBLEM',
  UNKNOWN: 'UNKNOWN',
};

export const SOURCE_RELATIONSHIP_STATUS = {
  OBSERVED: 'OBSERVED',
  INFERRED: 'INFERRED',
  UNKNOWN: 'UNKNOWN',
};

export const EVIDENCE_AVAILABILITY = {
  COMPLETE: 'COMPLETE',
  PARTIAL: 'PARTIAL',
  MISSING: 'MISSING',
  INSUFFICIENT: 'INSUFFICIENT',
};

export const DIAGNOSIS_STATUS = {
  PENDING: 'PENDING',
  COMPLETED: 'COMPLETED',
  INSUFFICIENT_EVIDENCE: 'INSUFFICIENT_EVIDENCE',
  FAILED: 'FAILED',
};

export const CORRECTION_STATUS = {
  PENDING: 'PENDING',
  GENERATED: 'GENERATED',
  VERIFYING: 'VERIFYING',
  VERIFIED: 'VERIFIED',
  UNVERIFIED: 'UNVERIFIED',
  INELIGIBLE: 'INELIGIBLE',
  FAILED: 'FAILED',
};

export const VERIFICATION_STEP_TYPES = [
  { id: 'REPRODUCE_ORIGINAL_FAILURE', label: '1. Reproduce Original Failure' },
  { id: 'APPLY_PATCH', label: '2. Apply Candidate Patch' },
  { id: 'BUILD_STATIC_CHECK', label: '3. Build / Static Syntax Check' },
  { id: 'RERUN_ORIGINAL_CASE', label: '4. Rerun Original Test Case' },
  { id: 'RUN_REGRESSION_CHECKS', label: '5. Run Regression Test Suite' },
  { id: 'RUN_INDEPENDENT_ACCEPTANCE', label: '6. Independent Acceptance Checks' },
];

export const STEP_EXECUTION_STATUS = {
  PASSED: 'PASSED',
  FAILED: 'FAILED',
  SKIPPED: 'SKIPPED',
  BLOCKED: 'BLOCKED',
  ERROR: 'ERROR',
};

export const REVIEW_DECISIONS = {
  PENDING: 'PENDING',
  ACCEPTED: 'ACCEPTED',
  REJECTED: 'REJECTED',
};

export const EXPORT_FORMATS = {
  JSON: 'JSON',
  CSV: 'CSV',
};

/**
 * Format arbitrary expectation or evidence value distinctly preserving types:
 * missing vs explicit null vs empty strings vs empty collections.
 */
export function formatValue(val) {
  if (val === undefined) return '<missing>';
  if (val === null) return 'null';
  if (typeof val === 'string') {
    if (val === '') return '"" (empty string)';
    return `"${val}"`;
  }
  if (Array.isArray(val)) {
    if (val.length === 0) return '[] (empty array)';
    return JSON.stringify(val);
  }
  if (typeof val === 'object') {
    if (Object.keys(val).length === 0) return '{} (empty object)';
    return JSON.stringify(val);
  }
  return String(val);
}

/**
 * Escape text for safe rendering in DOM, preventing executable HTML or script injection.
 */
export function escapeText(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function buildBaseUrl(projectId) {
  if (!projectId || typeof projectId !== 'string') {
    throw new Error('Project ID is required for Component 1 API operations.');
  }
  return `/api/v1/projects/${encodeURIComponent(projectId.trim())}/c1`;
}

function getC1Headers(projectId) {
  return {
    'X-Project-ID': projectId.trim(),
  };
}

export const c1Api = {
  // Phase 1: Configuration Endpoints
  async listConfigs(projectId) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/configs`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },

  async getConfig(projectId, configId) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/configs/${encodeURIComponent(configId)}`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },

  async createConfig(projectId, payload) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/configs`, {
      method: 'POST',
      headers: getC1Headers(projectId),
      body: JSON.stringify(payload),
    });
  },

  async updateConfig(projectId, configId, payload) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/configs/${encodeURIComponent(configId)}`, {
      method: 'PUT',
      headers: getC1Headers(projectId),
      body: JSON.stringify(payload),
    });
  },

  async validateStoredConfig(projectId, configId) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/configs/${encodeURIComponent(configId)}/validate`, {
      method: 'POST',
      headers: getC1Headers(projectId),
    });
  },

  async validateConfigSpec(projectId, payload) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/configs/validate-spec`, {
      method: 'POST',
      headers: getC1Headers(projectId),
      body: JSON.stringify(payload),
    });
  },

  async getNexaCartExample(projectId) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/examples/nexacart`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },

  // Live NexaCart: harness readiness and configuration import from the real tool registry
  async getNexaCartLiveReadiness(projectId) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/live/nexacart/readiness`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },

  async importNexaCartLiveConfig(projectId, target = 'main') {
    const base = buildBaseUrl(projectId);
    return request(`${base}/live/nexacart/config?target=${encodeURIComponent(target)}`, {
      method: 'POST',
      headers: getC1Headers(projectId),
    });
  },

  // Build features (code correction + sandbox verification are off in the PP1 build)
  async getFeatures(projectId) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/features`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },

  // Controlled-defect lab: a disposable NexaCart copy with one seeded defect on a local port
  async getDefectLab(projectId) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/live/nexacart/defect-lab`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },

  async startDefectLab(projectId, defectId) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/live/nexacart/defect-lab`, {
      method: 'POST',
      headers: getC1Headers(projectId),
      body: JSON.stringify({ defect_id: defectId }),
    });
  },

  async stopDefectLab(projectId) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/live/nexacart/defect-lab`, {
      method: 'DELETE',
      headers: getC1Headers(projectId),
    });
  },

  // Phase 1: Generation Endpoints
  async createGenerationJob(projectId, payload) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/generation/jobs`, {
      method: 'POST',
      headers: getC1Headers(projectId),
      body: JSON.stringify(payload),
    });
  },

  async listGenerationJobs(projectId) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/generation/jobs`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },

  async getGenerationJob(projectId, jobId) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/generation/jobs/${encodeURIComponent(jobId)}`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },

  async getJobCandidates(projectId, jobId, validOnly = false) {
    const base = buildBaseUrl(projectId);
    const query = validOnly ? '?valid_only=true' : '';
    return request(`${base}/generation/jobs/${encodeURIComponent(jobId)}/candidates${query}`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },

  async getJobAgentTasks(projectId, jobId) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/generation/jobs/${encodeURIComponent(jobId)}/agent-tasks`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },

  async promoteJobToSuite(projectId, jobId, { suiteId, suiteName }) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/generation/jobs/${encodeURIComponent(jobId)}/promote-suite`, {
      method: 'POST',
      headers: getC1Headers(projectId),
      body: JSON.stringify({
        suite_id: suiteId.trim(),
        name: suiteName.trim(),
      }),
    });
  },

  // Phase 1: Suite Endpoints
  async listSuites(projectId) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/suites`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },

  async getSuite(projectId, suiteId) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/suites/${encodeURIComponent(suiteId)}`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },

  async getSuiteCaseAgentView(projectId, suiteId, caseId) {
    const base = buildBaseUrl(projectId);
    return request(
      `${base}/suites/${encodeURIComponent(suiteId)}/cases/${encodeURIComponent(caseId)}/agent-view`,
      {
        method: 'GET',
        headers: getC1Headers(projectId),
      }
    );
  },

  // Phase 2: Execution Runs and Results Endpoints
  async startExecutionRun(projectId, payload) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/runs`, {
      method: 'POST',
      headers: getC1Headers(projectId),
      body: JSON.stringify(payload),
    });
  },

  async listExecutionRuns(projectId, { verdict = null, limit = 50, offset = 0 } = {}) {
    const base = buildBaseUrl(projectId);
    const params = new URLSearchParams();
    if (verdict) params.set('verdict', verdict);
    params.set('limit', String(limit));
    params.set('offset', String(offset));
    return request(`${base}/runs?${params.toString()}`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },

  async listRuns(projectId, options = {}) {
    return this.listExecutionRuns(projectId, options);
  },

  async getExecutionRun(projectId, runId) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/runs/${encodeURIComponent(runId)}`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },

  async getRunDetail(projectId, runId) {
    return this.getExecutionRun(projectId, runId);
  },

  async cancelExecutionRun(projectId, runId) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/runs/${encodeURIComponent(runId)}/cancel`, {
      method: 'POST',
      headers: getC1Headers(projectId),
    });
  },

  async rerunExecution(projectId, runId) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/runs/${encodeURIComponent(runId)}/rerun`, {
      method: 'POST',
      headers: getC1Headers(projectId),
    });
  },

  async getCaseExecution(projectId, runId, caseId) {
    const base = buildBaseUrl(projectId);
    return request(
      `${base}/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(caseId)}`,
      {
        method: 'GET',
        headers: getC1Headers(projectId),
      }
    );
  },

  async checkAdapterReadiness(projectId) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/adapter/readiness`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },

  // Phase 3: Diagnosis and Explanation Endpoints
  async diagnoseRun(projectId, runId, payload = {}) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/runs/${encodeURIComponent(runId)}/diagnose`, {
      method: 'POST',
      headers: getC1Headers(projectId),
      body: JSON.stringify(payload),
    });
  },

  async getDiagnosis(projectId, diagnosisId) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/diagnoses/${encodeURIComponent(diagnosisId)}`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },

  async getCaseDiagnosis(projectId, runId, caseId) {
    const base = buildBaseUrl(projectId);
    return request(
      `${base}/runs/${encodeURIComponent(runId)}/cases/${encodeURIComponent(caseId)}/diagnosis`,
      {
        method: 'GET',
        headers: getC1Headers(projectId),
      }
    );
  },

  async getDiagnosisCodeLocations(projectId, diagnosisId) {
    const base = buildBaseUrl(projectId);
    return request(
      `${base}/diagnoses/${encodeURIComponent(diagnosisId)}/code-locations`,
      {
        method: 'GET',
        headers: getC1Headers(projectId),
      }
    );
  },

  async listDiagnoses(projectId, { runId = null, limit = 50 } = {}) {
    const base = buildBaseUrl(projectId);
    const query = runId ? `?run_id=${encodeURIComponent(runId)}&limit=${limit}` : `?limit=${limit}`;
    return request(`${base}/diagnoses${query}`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },

  // Phase 3: Correction & Sandbox Verification Endpoints
  async requestCorrection(projectId, payload) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/corrections/attempts`, {
      method: 'POST',
      headers: getC1Headers(projectId),
      body: JSON.stringify(payload),
    });
  },

  async getCorrection(projectId, correctionId) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/corrections/${encodeURIComponent(correctionId)}`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },

  async getCorrectionDiff(projectId, correctionId) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/corrections/${encodeURIComponent(correctionId)}/diff`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },

  async submitReview(projectId, correctionId, payload) {
    const base = buildBaseUrl(projectId);
    return request(`${base}/corrections/${encodeURIComponent(correctionId)}/review`, {
      method: 'POST',
      headers: getC1Headers(projectId),
      body: JSON.stringify(payload),
    });
  },

  async listCorrections(projectId, { runId = null, limit = 50 } = {}) {
    const base = buildBaseUrl(projectId);
    const query = runId ? `?run_id=${encodeURIComponent(runId)}&limit=${limit}` : `?limit=${limit}`;
    return request(`${base}/corrections${query}`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },

  // Phase 3: Reporting & Exports Endpoints
  async getWorkflowReport(projectId, filters = {}) {
    const base = buildBaseUrl(projectId);
    const params = new URLSearchParams();
    if (filters.run_id) params.set('run_id', filters.run_id);
    if (filters.suite_id) params.set('suite_id', filters.suite_id);
    if (filters.verdict) params.set('verdict', filters.verdict);
    if (filters.cause_category) params.set('cause_category', filters.cause_category);
    if (filters.is_verified !== undefined && filters.is_verified !== null) {
      params.set('is_verified', String(filters.is_verified));
    }
    params.set('limit', String(filters.limit || 50));
    params.set('offset', String(filters.offset || 0));

    return request(`${base}/reports/workflow?${params.toString()}`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },

  async exportWorkflowReport(projectId, { runId = null, format = 'JSON' } = {}) {
    const base = buildBaseUrl(projectId);
    const query = runId ? `?run_id=${encodeURIComponent(runId)}&format=${format}` : `?format=${format}`;
    const token = sessionStorage.getItem('qa_auth_token');
    const headers = {
      ...getC1Headers(projectId),
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${base}/reports/export${query}`, {
      method: 'GET',
      headers,
    });

    if (!response.ok) {
      throw new Error(`Export failed with status ${response.status}`);
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `c1_workflow_report_${Date.now()}.${format.toLowerCase()}`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },

  // Phase 3: Research Metrics & Labels Endpoints
  async computeResearchMetrics(projectId, { runId = null, datasetSplit = null } = {}) {
    const base = buildBaseUrl(projectId);
    const params = new URLSearchParams();
    if (runId) params.set('run_id', runId);
    if (datasetSplit) params.set('dataset_split', datasetSplit);
    const query = params.toString() ? `?${params.toString()}` : '';

    return request(`${base}/research/metrics${query}`, {
      method: 'POST',
      headers: getC1Headers(projectId),
    });
  },

  async listReferenceLabels(projectId, filters = {}) {
    const base = buildBaseUrl(projectId);
    const params = new URLSearchParams();
    if (filters.dataset_split) params.set('dataset_split', filters.dataset_split);
    if (filters.task_family) params.set('task_family', filters.task_family);
    if (filters.label_version) params.set('label_version', filters.label_version);
    const query = params.toString() ? `?${params.toString()}` : '';

    return request(`${base}/research/labels${query}`, {
      method: 'GET',
      headers: getC1Headers(projectId),
    });
  },
};

export { ApiError };
