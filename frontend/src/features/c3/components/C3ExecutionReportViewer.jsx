import React, { useState, useEffect } from 'react';
import {
  FileSpreadsheet,
  Download,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';
import { c3Api } from '../api.js';
import { C3Badge } from './C3Badge';
import { DEMO_EXECUTION_REPORT } from '../fixtures.js';

export const C3ExecutionReportViewer = ({
  projectId,
  executionId,
  onClose,
  initialReport = null,
}) => {
  const [report, setReport] = useState(initialReport);
  const [isLoading, setIsLoading] = useState(!initialReport);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!initialReport && executionId && projectId) {
      let mounted = true;
      setIsLoading(true);
      setError(null);

      c3Api
        .getExecutionReport(projectId, executionId)
        .then((res) => {
          if (mounted) {
            setReport(res);
            setIsLoading(false);
          }
        })
        .catch((err) => {
          if (mounted) {
            setError(err.message || 'Failed to load execution report.');
            setIsLoading(false);
          }
        });

      return () => {
        mounted = false;
      };
    }
  }, [projectId, executionId, initialReport]);

  const handleExportCsv = () => {
    if (!projectId || !executionId) return;
    const url = c3Api.getExecutionReportCsvUrl(projectId, executionId);
    window.open(url, '_blank');
  };

  const handleUseDemoReport = () => {
    setReport(DEMO_EXECUTION_REPORT);
    setError(null);
  };

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap pb-4 border-b border-slate-100 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <FileSpreadsheet className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              <span>Structured Execution & Recovery Evaluation Report</span>
            </h3>
            {report?.status && <C3Badge status={report.status} />}
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Execution ID: <code className="font-mono">{executionId || report?.execution_id || 'exec-demo-001'}</code> | Suite ID: <code className="font-mono">{report?.suite_id || 'suite-demo-01'}</code>
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleExportCsv}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs transition-colors shadow-xs"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-semibold"
            >
              Back to Runs
            </button>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="p-8 text-center space-y-3">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto text-indigo-500" />
          <p className="text-xs text-slate-500">Compiling authoritative execution report...</p>
        </div>
      ) : error ? (
        <div className="p-6 text-center space-y-3">
          <AlertTriangle className="w-8 h-8 mx-auto text-amber-500" />
          <div className="text-xs text-slate-600 dark:text-slate-400 max-w-md mx-auto">
            <span className="font-semibold block text-slate-900 dark:text-white">
              Report Currently Unavailable
            </span>
            <p className="mt-1">{error}</p>
          </div>
          <button
            type="button"
            onClick={handleUseDemoReport}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800 text-xs font-semibold hover:bg-indigo-100"
          >
            <span>Inspect Sample Report Structure</span>
          </button>
        </div>
      ) : report ? (
        <div className="space-y-6 text-xs">
          {/* Explicit Denominators and Case Counts */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-2">
            <span className="font-bold text-slate-900 dark:text-white text-xs block">
              Explicit Denominators & Execution Volume:
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-semibold">
                  Planned Cases
                </span>
                <div className="text-lg font-bold text-slate-900 dark:text-white mt-0.5">
                  {report.planned_cases_count}
                </div>
                <p className="text-[10px] text-slate-400 mt-0.5">
                  Defined in frozen suite manifest
                </p>
              </div>

              <div className="p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-semibold">
                  Executed Pairs
                </span>
                <div className="text-lg font-bold text-indigo-600 dark:text-indigo-400 mt-0.5">
                  {report.executed_cases_count}
                </div>
                <p className="text-[10px] text-slate-400 mt-0.5">
                  Matched pairs initiated by runner
                </p>
              </div>

              <div className="p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-semibold">
                  Evaluated Trials
                </span>
                <div className="text-lg font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">
                  {(report.verdict_counts?.pass_completed_count || 0) +
                    (report.verdict_counts?.pass_graceful_count || 0) +
                    (report.verdict_counts?.fail_count || 0) +
                    (report.verdict_counts?.inconclusive_count || 0)}
                </div>
                <p className="text-[10px] text-slate-400 mt-0.5">
                  Passed clean & exposure gating
                </p>
              </div>
            </div>
          </div>

          {/* Breakdown Matrices: Clean Controls vs Exposure Outcomes vs Recovery Verdicts */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* 1. Clean Baseline Qualification */}
            <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 space-y-2">
              <span className="font-bold text-slate-900 dark:text-white block text-xs">
                Clean Baseline Controls:
              </span>
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 dark:text-slate-400">Qualified Controls:</span>
                  <span className="font-mono font-bold text-emerald-600">
                    {report.clean_qualified_count ?? 0}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 dark:text-slate-400">Disqualified (Retained):</span>
                  <span className="font-mono font-bold text-rose-600">
                    {report.clean_disqualified_count ?? 0}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 dark:text-slate-400">Indeterminate:</span>
                  <span className="font-mono font-bold text-slate-500">
                    {report.clean_indeterminate_count ?? 0}
                  </span>
                </div>
              </div>
            </div>

            {/* 2. Exposure Outcomes */}
            <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 space-y-2">
              <span className="font-bold text-slate-900 dark:text-white block text-xs">
                Exposure Outcomes:
              </span>
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 dark:text-slate-400">Confirmed Exposures:</span>
                  <span className="font-mono font-bold text-emerald-600">
                    {report.confirmed_exposure_count ?? 0}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 dark:text-slate-400">Not Triggered:</span>
                  <span className="font-mono font-bold text-amber-600">
                    {report.not_triggered_exposure_count ?? 0}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 dark:text-slate-400">Unknown Exposure:</span>
                  <span className="font-mono font-bold text-slate-500">
                    {report.unknown_exposure_count ?? 0}
                  </span>
                </div>
              </div>
            </div>

            {/* 3. Recovery Verdicts */}
            <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 space-y-2">
              <span className="font-bold text-slate-900 dark:text-white block text-xs">
                Recovery Verdicts:
              </span>
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 dark:text-slate-400">Pass Completed:</span>
                  <span className="font-mono font-bold text-emerald-600">
                    {report.verdict_counts?.pass_completed_count ?? 0}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 dark:text-slate-400">Pass Graceful:</span>
                  <span className="font-mono font-bold text-sky-600">
                    {report.verdict_counts?.pass_graceful_count ?? 0}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 dark:text-slate-400">Fail Verdict:</span>
                  <span className="font-mono font-bold text-rose-600">
                    {report.verdict_counts?.fail_count ?? 0}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 dark:text-slate-400">Inconclusive:</span>
                  <span className="font-mono font-bold text-amber-600">
                    {report.verdict_counts?.inconclusive_count ?? 0}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Rule Violations and Attribution */}
          {report.rule_violation_counts && Object.keys(report.rule_violation_counts).length > 0 && (
            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-2">
              <span className="font-bold text-slate-900 dark:text-white block text-xs">
                Evaluator Rule Violations:
              </span>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 font-mono text-[11px]">
                {Object.entries(report.rule_violation_counts).map(([rule, count]) => (
                  <div
                    key={rule}
                    className="p-2 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 flex items-center justify-between"
                  >
                    <span className="text-slate-600 dark:text-slate-300 truncate">{rule}</span>
                    <span className="font-bold text-rose-600 pl-2">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
};
