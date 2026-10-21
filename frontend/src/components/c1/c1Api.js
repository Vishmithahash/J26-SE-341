import { request, ApiError } from '../../services/api.js';

/**
 * Component 1: Explainable Tool-Call Correctness Testing API Client.
 * Communicates with backend endpoints under /api/v1/projects/{projectId}/c1.
 * strictly scopes calls to the active project ID and attaches the X-Project-ID header.
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
  // Configuration Endpoints
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

  // Generation Endpoints
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

  // Suite Endpoints
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
};

export { ApiError };
