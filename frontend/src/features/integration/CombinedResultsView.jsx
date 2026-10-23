import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link, useLocation } from 'react-router-dom';
import {
  ArrowLeft,
  Layers,
  FileText,
  Download,
  AlertCircle,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Shield,
  Activity,
  GitBranch,
  RefreshCw,
  FolderGit2,
  Check,
  Info,
} from 'lucide-react';
import { integrationApi } from './integrationApi';
import { projectsApi } from '../../services/projects';

/**
 * Format three-state cleanup values (true, false, null/undefined).
 * Must preserve distinct null/unavailable semantics without coalescing to false.
 */
function renderThreeStateCleanup(value, labelPositive, labelNegative, labelUnavailable) {
  if (value === true) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
        <Check className="w-3 h-3 text-emerald-600" />
        {labelPositive}
      </span>
    );
  }
  if (value === false) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800">
        <XCircle className="w-3 h-3 text-rose-600" />
        {labelNegative}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
      <Clock className="w-3 h-3 text-slate-400" />
      {labelUnavailable}
    </span>
  );
}

/**
 * Native Verdict Badge
 */
function VerdictBadge({ verdict }) {
  if (!verdict) {
    return (
      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-500">
        Unevaluated / Unavailable
      </span>
    );
  }

  const upper = String(verdict).toUpperCase();
  if (upper.includes('PASS')) {
    return (
      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
        {verdict}
      </span>
    );
  }
  if (upper.includes('FAIL')) {
    return (
      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800">
        {verdict}
      </span>
    );
  }
  if (upper.includes('INCONCLUSIVE') || upper.includes('PARTIAL')) {
    return (
      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
        {verdict}
      </span>
    );
  }
  if (upper.includes('NOT_READY') || upper.includes('BLOCKED')) {
    return (
      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
        {verdict}
      </span>
    );
  }

  return (
    <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
      {verdict}
    </span>
  );
}

export const CombinedResultsView = () => {
  const { projectId } = useParams();
  const location = useLocation();
  const basePath = location.pathname.startsWith('/admin') ? '/admin' : '/app';

  // State
  const [project, setProject] = useState(null);
  const [plans, setPlans] = useState([]);
  const [selectedPlanId, setSelectedPlanId] = useState(null);
  const [executions, setExecutions] = useState([]);
  const [selectedExecutionId, setSelectedExecutionId] = useState(null);
  const [report, setReport] = useState(null);

  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingExecutions, setIsLoadingExecutions] = useState(false);
  const [isLoadingReport, setIsLoadingReport] = useState(false);
  const [error, setError] = useState(null);
  const [exportingFormat, setExportingFormat] = useState(null);
  const [exportSuccess, setExportSuccess] = useState(null);

  // Load project metadata and plans for selected project
  useEffect(() => {
    let isCancelled = false;

    async function loadInitialData() {
      setIsLoading(true);
      setError(null);
      setProject(null);
      setPlans([]);
      setSelectedPlanId(null);
      setExecutions([]);
      setSelectedExecutionId(null);
      setReport(null);

      try {
        const [projRes, plansRes] = await Promise.all([
          projectsApi.getProject(projectId),
          integrationApi.listPlans(projectId, { page: 1, pageSize: 50 }),
        ]);

        if (isCancelled) return;

        setProject(projRes);
        const planItems = plansRes?.items || [];
        setPlans(planItems);
        if (planItems.length > 0) {
          setSelectedPlanId(planItems[0].plan_id || planItems[0].integration_run_id);
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err.message || 'Failed to load project integration results.');
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    if (projectId) {
      loadInitialData();
    }

    return () => {
      isCancelled = true;
    };
  }, [projectId]);

  // Load executions whenever selected plan changes
  useEffect(() => {
    let isCancelled = false;

    async function loadPlanExecutions() {
      if (!projectId || !selectedPlanId) {
        setExecutions([]);
        setSelectedExecutionId(null);
        setReport(null);
        return;
      }

      setIsLoadingExecutions(true);
      setExecutions([]);
      setSelectedExecutionId(null);
      setReport(null);

      try {
        const res = await integrationApi.listExecutions(projectId, selectedPlanId);
        if (isCancelled) return;

        const execItems = res?.items || [];
        setExecutions(execItems);
        if (execItems.length > 0) {
          setSelectedExecutionId(execItems[0].execution_id);
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err.message || 'Failed to load plan executions.');
        }
      } finally {
        if (!isCancelled) {
          setIsLoadingExecutions(false);
        }
      }
    }

    loadPlanExecutions();

    return () => {
      isCancelled = true;
    };
  }, [projectId, selectedPlanId]);

  // Load combined report whenever selected execution changes
  useEffect(() => {
    let isCancelled = false;

    async function loadReport() {
      if (!projectId || !selectedPlanId || !selectedExecutionId) {
        setReport(null);
        return;
      }

      setIsLoadingReport(true);
      setReport(null);

      try {
        const rep = await integrationApi.getCombinedReport(
          projectId,
          selectedPlanId,
          selectedExecutionId
        );
        if (isCancelled) return;
        setReport(rep);
      } catch (err) {
        if (!isCancelled) {
          // If 404, it means execution report hasn't been generated or findings are not ready
          setError(err.message || 'Failed to load combined report for execution.');
        }
      } finally {
        if (!isCancelled) {
          setIsLoadingReport(false);
        }
      }
    }

    loadReport();

    return () => {
      isCancelled = true;
    };
  }, [projectId, selectedPlanId, selectedExecutionId]);

  // Handle Export File
  const handleExport = async (format) => {
    if (!projectId || !selectedPlanId || !selectedExecutionId) return;
    setExportingFormat(format);
    setExportSuccess(null);
    setError(null);
    try {
      const result = await integrationApi.exportReportFile(
        projectId,
        selectedPlanId,
        selectedExecutionId,
        format
      );
      setExportSuccess(`Downloaded ${result.filename}`);
      setTimeout(() => setExportSuccess(null), 3000);
    } catch (err) {
      setError(err.message || `Failed to export report as ${format.toUpperCase()}.`);
    } finally {
      setExportingFormat(null);
    }
  };

  const selectedPlan = plans.find(
    (p) => p.plan_id === selectedPlanId || p.integration_run_id === selectedPlanId
  );
  const selectedExecution = executions.find(
    (e) => e.execution_id === selectedExecutionId
  );

  return (
    <div className="space-y-6">
      {/* Back and Navigation */}
      <div className="flex items-center justify-between">
        <Link
          to={`${basePath}/projects/${projectId}`}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Project Details</span>
        </Link>

        {project && (
          <div className="text-xs text-slate-400">
            Project: <strong className="text-slate-700 dark:text-slate-200">{project.name}</strong> ({project.project_id})
          </div>
        )}
      </div>

      {/* Header Banner */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="p-3 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
            <Layers className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
                Combined QA Results
              </h1>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 font-semibold">
                Multi-Component Integration
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Inspect correlated findings, component coverage, and native verdicts across C1, C2, C3, and C4 runs.
            </p>
          </div>
        </div>

        {/* Export buttons when report is available */}
        {report && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={Boolean(exportingFormat)}
              onClick={() => handleExport('json')}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-semibold shadow-xs transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              <span>{exportingFormat === 'json' ? 'Exporting...' : 'Export JSON'}</span>
            </button>

            <button
              type="button"
              disabled={Boolean(exportingFormat)}
              onClick={() => handleExport('csv')}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-semibold transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              <span>{exportingFormat === 'csv' ? 'Exporting...' : 'Export CSV'}</span>
            </button>
          </div>
        )}
      </div>

      {/* Notifications */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-xs flex items-start justify-between gap-3">
          <div className="flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">Notice: </span>
              {error}
            </div>
          </div>
          <button
            type="button"
            onClick={() => setError(null)}
            className="text-[11px] font-semibold hover:underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {exportSuccess && (
        <div className="p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{exportSuccess}</span>
        </div>
      )}

      {/* Loading State */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <div className="w-8 h-8 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs text-slate-400">Loading project integration results...</span>
        </div>
      ) : plans.length === 0 ? (
        /* Genuine Empty State */
        <div className="p-12 text-center rounded-2xl bg-white dark:bg-slate-900 border border-dashed border-slate-200 dark:border-slate-800">
          <div className="mx-auto w-12 h-12 rounded-2xl bg-slate-100 dark:bg-slate-800 text-slate-400 flex items-center justify-center mb-3">
            <FolderGit2 className="w-6 h-6" />
          </div>
          <h2 className="text-sm font-bold text-slate-800 dark:text-white">
            No Shared Integration Plans Found
          </h2>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 max-w-md mx-auto leading-relaxed">
            Component workspaces (Tool-Call Correctness, Workflow Testing, Robustness Recovery, and Policy Safety)
            maintain their own independent execution cycles. When cross-component integration plans are registered,
            their consolidated results will appear here.
          </p>
        </div>
      ) : (
        /* Plans & Executions Split View */
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Left Sidebar: Plans & Executions Selector */}
          <div className="space-y-4">
            {/* Run Plans Selector */}
            <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                  Integration Plans
                </span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">
                  {plans.length}
                </span>
              </div>

              <div className="space-y-1.5 max-h-56 overflow-y-auto">
                {plans.map((p) => {
                  const id = p.plan_id || p.integration_run_id;
                  const isSelected = selectedPlanId === id;
                  return (
                    <button
                      key={id}
                      type="button"
                      onClick={() => setSelectedPlanId(id)}
                      className={`w-full text-left p-2.5 rounded-xl text-xs transition-colors border ${
                        isSelected
                          ? 'bg-indigo-50 dark:bg-indigo-950/50 border-indigo-200 dark:border-indigo-800 text-indigo-900 dark:text-indigo-200 font-medium'
                          : 'bg-white dark:bg-slate-900 border-slate-100 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'
                      }`}
                    >
                      <div className="font-semibold truncate">{p.name || id}</div>
                      <div className="flex items-center gap-1.5 text-[10px] text-slate-400 mt-0.5">
                        <span className="font-mono">{p.integration_run_id}</span>
                        <span>•</span>
                        <span>{p.lifecycle_status}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Executions for Selected Plan */}
            <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                  Executions
                </span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">
                  {executions.length}
                </span>
              </div>

              {isLoadingExecutions ? (
                <div className="flex items-center justify-center py-6 text-xs text-slate-400">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin mr-1.5" /> Loading...
                </div>
              ) : executions.length === 0 ? (
                <div className="p-4 text-center text-xs text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
                  No executions recorded for this plan yet.
                </div>
              ) : (
                <div className="space-y-1.5 max-h-56 overflow-y-auto">
                  {executions.map((e) => {
                    const isSelected = selectedExecutionId === e.execution_id;
                    return (
                      <button
                        key={e.execution_id}
                        type="button"
                        onClick={() => setSelectedExecutionId(e.execution_id)}
                        className={`w-full text-left p-2.5 rounded-xl text-xs transition-colors border ${
                          isSelected
                            ? 'bg-indigo-50 dark:bg-indigo-950/50 border-indigo-200 dark:border-indigo-800 text-indigo-900 dark:text-indigo-200 font-medium'
                            : 'bg-white dark:bg-slate-900 border-slate-100 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'
                        }`}
                      >
                        <div className="font-mono truncate">{e.execution_id}</div>
                        <div className="flex items-center gap-1.5 text-[10px] text-slate-400 mt-0.5">
                          <span>{e.target_mode}</span>
                          <span>•</span>
                          <span className="uppercase font-semibold">{e.lifecycle_status}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Execution Status & Cleanup Card */}
            {selectedExecution && (
              <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-2.5 text-xs">
                <span className="text-[10px] text-slate-400 uppercase font-semibold">
                  Execution Details & Cleanup
                </span>
                <div className="space-y-1 text-slate-600 dark:text-slate-300">
                  <div>
                    <span className="text-slate-400">Target Mode: </span>
                    <span className="font-mono font-semibold">{selectedExecution.target_mode}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">Evidence Digest: </span>
                    <span className="font-mono text-[10px] truncate block" title={selectedExecution.retained_evidence_digest}>
                      {selectedExecution.retained_evidence_digest || 'None retained'}
                    </span>
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-100 dark:border-slate-800 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400 text-[11px]">Cleanup:</span>
                    {renderThreeStateCleanup(
                      selectedExecution.cleanup_successful,
                      'Cleaned & verified',
                      'Cleanup failed',
                      'Not assessed'
                    )}
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400 text-[11px]">Reusability:</span>
                    {renderThreeStateCleanup(
                      selectedExecution.cleanup_reusable,
                      'Reusable',
                      'Not reusable',
                      'Not assessed'
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Area: Combined Report Details */}
          <div className="lg:col-span-3 space-y-6">
            {isLoadingReport ? (
              <div className="p-12 text-center rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex flex-col items-center justify-center gap-3">
                <div className="w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
                <span className="text-xs text-slate-400">Loading combined QA report...</span>
              </div>
            ) : !report ? (
              <div className="p-12 text-center rounded-2xl bg-white dark:bg-slate-900 border border-dashed border-slate-200 dark:border-slate-800 text-xs text-slate-400">
                Select an execution on the left to inspect its consolidated multi-component findings and evaluation evidence.
              </div>
            ) : (
              <>
                {/* Report Overview Banner */}
                <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-slate-400">Report ID:</span>
                        <code className="text-xs font-mono font-bold text-slate-800 dark:text-slate-100">
                          {report.report_id}
                        </code>
                      </div>
                      <div className="flex items-center gap-2 text-[11px] text-slate-500 mt-1">
                        <span>Run: <code className="font-mono">{report.integration_run_id}</code></span>
                        <span>•</span>
                        <span>Digest: <code className="font-mono text-[10px]">{report.report_digest?.substring(0, 16)}...</code></span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-slate-500">Overall Verdict:</span>
                      <VerdictBadge verdict={report.completeness?.overall_verdict || 'NOT_EVALUATED'} />
                    </div>
                  </div>

                  {/* Summary Metric Cards */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-slate-100 dark:border-slate-800 text-xs">
                    <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
                      <span className="text-[10px] text-slate-400 uppercase font-semibold">Raw Findings</span>
                      <div className="text-lg font-bold text-slate-900 dark:text-white mt-0.5">
                        {report.raw_finding_count || 0}
                      </div>
                    </div>

                    <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
                      <span className="text-[10px] text-slate-400 uppercase font-semibold">Correlated Defect Groups</span>
                      <div className="text-lg font-bold text-indigo-600 dark:text-indigo-400 mt-0.5">
                        {report.grouped_defect_count || 0}
                      </div>
                    </div>

                    <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
                      <span className="text-[10px] text-slate-400 uppercase font-semibold">Requested Components</span>
                      <div className="text-sm font-semibold text-slate-800 dark:text-slate-200 mt-1">
                        {report.completeness?.requested_components?.join(', ') || 'None'}
                      </div>
                    </div>

                    <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
                      <span className="text-[10px] text-slate-400 uppercase font-semibold">Evaluated Components</span>
                      <div className="text-sm font-semibold text-emerald-600 dark:text-emerald-400 mt-1">
                        {report.completeness?.evaluated_components?.join(', ') || 'None'}
                      </div>
                    </div>
                  </div>

                  {/* Completeness Gaps if any */}
                  {(report.completeness?.not_ready_components?.length > 0 ||
                    report.completeness?.blocked_components?.length > 0 ||
                    report.completeness?.not_evaluated_components?.length > 0 ||
                    report.completeness?.pending_or_missing_evidence?.length > 0) && (
                    <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-amber-900 dark:text-amber-200 text-xs space-y-1">
                      <div className="font-semibold flex items-center gap-1.5">
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                        <span>Completeness Limitations:</span>
                      </div>
                      <div className="text-[11px] space-y-0.5 pl-5 list-disc">
                        {report.completeness.not_ready_components?.length > 0 && (
                          <div>Not Ready: {report.completeness.not_ready_components.join(', ')}</div>
                        )}
                        {report.completeness.blocked_components?.length > 0 && (
                          <div>Blocked: {report.completeness.blocked_components.join(', ')}</div>
                        )}
                        {report.completeness.not_evaluated_components?.length > 0 && (
                          <div>Not Evaluated: {report.completeness.not_evaluated_components.join(', ')}</div>
                        )}
                        {report.completeness.pending_or_missing_evidence?.map((gap, i) => (
                          <div key={i}>Evidence Gap: {gap}</div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Per-Component Contributions */}
                <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
                  <h2 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                    Component Contributions & Native Verdicts
                  </h2>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {['C1', 'C2', 'C3', 'C4'].map((compKey) => {
                      const contribution = report.component_contributions?.[compKey];
                      const titles = {
                        C1: 'Tool-Call Correctness (C1)',
                        C2: 'State-Aware Workflow (C2)',
                        C3: 'Robustness Recovery (C3)',
                        C4: 'Policy-Aware Safety (C4)',
                      };

                      return (
                        <div
                          key={compKey}
                          className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 space-y-3 text-xs"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-slate-800 dark:text-slate-100">
                              {titles[compKey]}
                            </span>
                            <VerdictBadge
                              verdict={contribution?.native_verdict || (contribution ? contribution.status : 'NOT EVALUATED')}
                            />
                          </div>

                          {contribution ? (
                            <div className="space-y-1.5 text-slate-600 dark:text-slate-300">
                              <div className="flex items-center justify-between text-[11px]">
                                <span className="text-slate-400">Referenced Entity:</span>
                                <code className="font-mono text-slate-700 dark:text-slate-300">
                                  {contribution.native_entity_id || 'None'}
                                </code>
                              </div>
                              <div className="flex items-center justify-between text-[11px]">
                                <span className="text-slate-400">Status:</span>
                                <span className="font-semibold uppercase">{contribution.status}</span>
                              </div>
                              <div className="flex items-center justify-between text-[11px]">
                                <span className="text-slate-400">Evaluator Version:</span>
                                <span className="font-mono">{contribution.evaluator_version}</span>
                              </div>
                              <div className="flex items-center justify-between text-[11px]">
                                <span className="text-slate-400">Checks / Violations:</span>
                                <span>{contribution.checks_or_rules_count} checks • {contribution.violations_or_findings_count} violations</span>
                              </div>

                              {contribution.evidence_references?.length > 0 && (
                                <div className="text-[10px] text-slate-400 pt-1 border-t border-slate-100 dark:border-slate-800">
                                  Evidence: {contribution.evidence_references.join(', ')}
                                </div>
                              )}

                              {contribution.non_evaluation_reasons?.length > 0 && (
                                <div className="p-2 rounded bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-200 text-[10px]">
                                  {contribution.non_evaluation_reasons.join('. ')}
                                </div>
                              )}
                            </div>
                          ) : (
                            <div className="text-slate-400 text-xs italic">
                              Not requested or evaluated in this execution.
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Correlated Defect Groups */}
                {report.correlated_defect_groups?.length > 0 && (
                  <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
                    <h2 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                      Correlated Defect Groups ({report.correlated_defect_groups.length})
                    </h2>

                    <div className="space-y-3">
                      {report.correlated_defect_groups.map((group) => (
                        <div
                          key={group.group_id}
                          className="p-3.5 rounded-xl border border-indigo-100 dark:border-indigo-900/50 bg-indigo-50/30 dark:bg-indigo-950/20 text-xs space-y-2"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-indigo-950 dark:text-indigo-200">
                              Cluster: {group.correlation_key}
                            </span>
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-100 dark:bg-indigo-900/60 text-indigo-800 dark:text-indigo-300">
                              Involved: {group.involved_components?.join(', ')}
                            </span>
                          </div>
                          <p className="text-[11px] text-slate-600 dark:text-slate-300">
                            {group.correlation_explanation}
                          </p>
                          <div className="text-[10px] font-mono text-slate-500">
                            Linked findings: {group.finding_ids?.join(', ')}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Unified Findings List */}
                {report.findings?.length > 0 && (
                  <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
                    <h2 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                      Individual Unified Findings ({report.findings.length})
                    </h2>

                    <div className="space-y-2 max-h-72 overflow-y-auto">
                      {report.findings.map((f) => (
                        <div
                          key={f.finding_id}
                          className="p-3 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40 text-xs space-y-1"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-slate-800 dark:text-slate-100 font-mono">
                                {f.component}
                              </span>
                              <span className="text-slate-400">•</span>
                              <span className="font-mono text-slate-600 dark:text-slate-400">
                                {f.rule_or_check_id}
                              </span>
                            </div>
                            <span className="font-semibold text-[10px] px-1.5 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                              {f.severity}
                            </span>
                          </div>
                          <div className="text-slate-700 dark:text-slate-300 text-[11px]">
                            {f.message}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
