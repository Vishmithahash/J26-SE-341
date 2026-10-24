import { request, api, downloadFile } from '../../services/api.js';

/**
 * Shared Integration API Client
 *
 * Scoped strictly to authorized project context. Reuses existing authenticated
 * request utilities and token management. Does not store tokens in URLs or files.
 */
export const integrationApi = {
  /**
   * List integration run plans for the authorized project.
   */
  async listPlans(projectId, { page = 1, pageSize = 20 } = {}) {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    return request(
      `/api/v1/projects/${encodeURIComponent(projectId)}/integration/plans?${params.toString()}`,
      { method: 'GET' }
    );
  },

  /**
   * Retrieve a specific integration run plan by its ID or integration_run_id.
   */
  async getPlan(projectId, planId) {
    return request(
      `/api/v1/projects/${encodeURIComponent(projectId)}/integration/plans/${encodeURIComponent(planId)}`,
      { method: 'GET' }
    );
  },

  /**
   * List executions for an integration run plan.
   */
  async listExecutions(projectId, planId, { page = 1, pageSize = 20 } = {}) {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    return request(
      `/api/v1/projects/${encodeURIComponent(projectId)}/integration/plans/${encodeURIComponent(planId)}/executions?${params.toString()}`,
      { method: 'GET' }
    );
  },

  /**
   * Retrieve a specific execution record under a plan.
   */
  async getExecution(projectId, planId, executionId) {
    return request(
      `/api/v1/projects/${encodeURIComponent(projectId)}/integration/plans/${encodeURIComponent(planId)}/executions/${encodeURIComponent(executionId)}`,
      { method: 'GET' }
    );
  },

  /**
   * Retrieve or generate the combined cross-component QA report for an execution.
   */
  async getCombinedReport(projectId, planId, executionId) {
    return request(
      `/api/v1/projects/${encodeURIComponent(projectId)}/integration/plans/${encodeURIComponent(planId)}/executions/${encodeURIComponent(executionId)}/report`,
      { method: 'GET' }
    );
  },

  /**
   * List published combined QA reports for the project.
   */
  async listReports(
    projectId,
    { page = 1, pageSize = 20, component, verdict, executionMode } = {}
  ) {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (component) params.append('component', component);
    if (verdict) params.append('verdict', verdict);
    if (executionMode) params.append('execution_mode', executionMode);

    return request(
      `/api/v1/projects/${encodeURIComponent(projectId)}/integration/reports?${params.toString()}`,
      { method: 'GET' }
    );
  },

  /**
   * Authenticated export of the combined QA report as JSON or CSV.
   * Downloads the file directly in the browser without exposing tokens in URLs.
   * Reuses existing expired-session handling (clears session and invokes unauthorized callback on 401).
   */
  async exportReportFile(projectId, planId, executionId, format = 'json') {
    const url = `/api/v1/projects/${encodeURIComponent(projectId)}/integration/plans/${encodeURIComponent(planId)}/executions/${encodeURIComponent(executionId)}/report/export?format=${encodeURIComponent(format)}`;
    const { blob, disposition } = await downloadFile(url, { method: 'GET' });

    let filename = `report_${executionId}.${format}`;
    if (disposition) {
      const match = disposition.match(/filename="?([^";]+)"?/);
      if (match && match[1]) {
        filename = match[1];
      }
    }

    const downloadUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(downloadUrl);

    return { filename, success: true };
  },
};
