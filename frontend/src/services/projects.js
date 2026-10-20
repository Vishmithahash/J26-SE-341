import { request } from './api.js';

export const CONNECTION_STATES = {
  NOT_CHECKED: 'NOT_CHECKED',
  CONNECTED: 'CONNECTED',
  PARTIAL: 'PARTIAL',
  UNREACHABLE: 'UNREACHABLE',
  AUTH_REQUIRED: 'AUTH_REQUIRED',
  INVALID_CONFIGURATION: 'INVALID_CONFIGURATION',
  DISCONNECTED: 'DISCONNECTED',
};

export const DOMAINS = [
  { value: 'custom', label: 'Custom Application' },
  { value: 'e-commerce', label: 'E-Commerce' },
  { value: 'booking', label: 'Booking & Reservations' },
  { value: 'learning/examination', label: 'Learning & Examination' },
];

export const ENVIRONMENTS = [
  { value: 'development', label: 'Development' },
  { value: 'staging', label: 'Staging' },
];

export const INPUT_CATEGORIES = [
  { value: 'requirements', label: 'Requirements Specification' },
  { value: 'api_tool_specification', label: 'API / Tool Specification' },
  { value: 'source_repository', label: 'Source Repository' },
  { value: 'database_schema', label: 'Database Schema Description' },
  { value: 'workflow_state_mapping', label: 'Workflow / State Mapping' },
  { value: 'policy_role_definition', label: 'Policy / Role Definition' },
  { value: 'fixture_reset_description', label: 'Fixture / Reset Description' },
  { value: 'adapter_observation_manifest', label: 'Adapter / Observation Manifest' },
];

export const projectsApi = {
  /**
   * List projects with pagination, search, and filters.
   */
  async listProjects({ limit = 20, offset = 0, search = '', lifecycle = '', connectionState = '' } = {}) {
    const params = new URLSearchParams();
    params.set('limit', String(limit));
    params.set('offset', String(offset));
    if (search && search.trim()) params.set('search', search.trim());
    if (lifecycle && lifecycle.trim()) params.set('lifecycle', lifecycle.trim());
    if (connectionState && connectionState.trim()) params.set('connection_state', connectionState.trim());

    return request(`/api/v1/projects?${params.toString()}`, {
      method: 'GET',
    });
  },

  /**
   * Get single project details along with last checks and input references.
   */
  async getProject(projectId) {
    return request(`/api/v1/projects/${encodeURIComponent(projectId)}`, {
      method: 'GET',
    });
  },

  /**
   * Register a new project.
   */
  async createProject(payload) {
    return request('/api/v1/projects', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Update project fields or connection URLs.
   */
  async updateProject(projectId, payload) {
    return request(`/api/v1/projects/${encodeURIComponent(projectId)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Trigger safe backend connection check for configured endpoints.
   */
  async checkConnection(projectId) {
    return request(`/api/v1/projects/${encodeURIComponent(projectId)}/check-connection`, {
      method: 'POST',
    });
  },

  /**
   * Explicitly disconnect project connection state.
   */
  async disconnectProject(projectId) {
    return request(`/api/v1/projects/${encodeURIComponent(projectId)}/disconnect`, {
      method: 'POST',
    });
  },

  /**
   * Archive project.
   */
  async archiveProject(projectId) {
    return request(`/api/v1/projects/${encodeURIComponent(projectId)}/archive`, {
      method: 'POST',
    });
  },

  /**
   * Restore archived project.
   */
  async restoreProject(projectId) {
    return request(`/api/v1/projects/${encodeURIComponent(projectId)}/restore`, {
      method: 'POST',
    });
  },

  /**
   * Get audit event history for a project.
   */
  async getProjectHistory(projectId, { limit = 20, offset = 0 } = {}) {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    });
    return request(`/api/v1/projects/${encodeURIComponent(projectId)}/history?${params.toString()}`, {
      method: 'GET',
    });
  },

  /**
   * Get input references for a project.
   */
  async getProjectInputs(projectId) {
    return request(`/api/v1/projects/${encodeURIComponent(projectId)}/inputs`, {
      method: 'GET',
    });
  },

  /**
   * Add a versioned input reference to a project.
   */
  async createProjectInput(projectId, payload) {
    return request(`/api/v1/projects/${encodeURIComponent(projectId)}/inputs`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
};
