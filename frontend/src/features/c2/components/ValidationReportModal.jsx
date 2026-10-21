import React from 'react';
import { X, CheckCircle2, AlertTriangle, XCircle, ShieldAlert, Layers } from 'lucide-react';

export const ValidationReportModal = ({ isOpen, onClose, report, history = [] }) => {
  if (!isOpen || !report) return null;

  const isValid = Boolean(report.is_valid);
  const errors = report.errors || [];
  const warnings = report.warnings || [];
  const summary = report.summary || {};
  const diagnostics = report.diagnostics || {};

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="validation-report-title"
    >
      <div className="bg-white dark:bg-[#131A26] rounded-2xl border border-slate-200 dark:border-slate-800 shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div
              className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                isValid
                  ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400'
                  : 'bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-400'
              }`}
            >
              {isValid ? <CheckCircle2 className="w-5 h-5" /> : <XCircle className="w-5 h-5" />}
            </div>
            <div>
              <h2 id="validation-report-title" className="text-base font-semibold text-slate-900 dark:text-white">
                Formal Model Validation Report
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Model: <code className="font-mono">{report.model_id}</code> (v{report.version})
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            aria-label="Close report modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-6">
          {/* Status Banner */}
          <div
            className={`p-4 rounded-xl border flex items-start gap-3.5 ${
              isValid
                ? 'bg-emerald-50/70 border-emerald-200 dark:bg-emerald-950/30 dark:border-emerald-900/60'
                : 'bg-rose-50/70 border-rose-200 dark:bg-rose-950/30 dark:border-rose-900/60'
            }`}
          >
            {isValid ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
            ) : (
              <ShieldAlert className="w-5 h-5 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
            )}
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span
                  className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                    isValid
                      ? 'bg-emerald-200/60 text-emerald-900 dark:bg-emerald-900/60 dark:text-emerald-200'
                      : 'bg-rose-200/60 text-rose-900 dark:bg-rose-900/60 dark:text-rose-200'
                  }`}
                >
                  {report.readiness || (isValid ? 'READY' : 'MODEL NOT READY')}
                </span>
                <span className="text-xs font-mono text-slate-500 dark:text-slate-400 truncate max-w-xs">
                  Hash: {report.content_hash}
                </span>
              </div>
              <p className="text-xs text-slate-700 dark:text-slate-300">
                {isValid
                  ? 'All structural graph integrity and bounded semantic checks completed with zero errors. Model is structurally sound.'
                  : `Model validation failed with ${errors.length} error(s). All structural and semantic blockers must be resolved before approval.`}
              </p>
            </div>
          </div>

          {/* Metrics Overview */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
              <div className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">Errors</div>
              <div className={`text-xl font-bold ${errors.length > 0 ? 'text-rose-600 dark:text-rose-400' : 'text-slate-900 dark:text-white'}`}>
                {summary.total_errors ?? errors.length}
              </div>
            </div>
            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
              <div className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">Warnings</div>
              <div className={`text-xl font-bold ${warnings.length > 0 ? 'text-amber-600 dark:text-amber-400' : 'text-slate-900 dark:text-white'}`}>
                {summary.total_warnings ?? warnings.length}
              </div>
            </div>
            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
              <div className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">States Verified</div>
              <div className="text-xl font-bold text-slate-900 dark:text-white">
                {summary.states_count ?? '-'}
              </div>
            </div>
            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
              <div className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">Transitions</div>
              <div className="text-xl font-bold text-slate-900 dark:text-white">
                {summary.transitions_count ?? '-'}
              </div>
            </div>
          </div>

          {/* Diagnostics Checks */}
          <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 text-xs space-y-2">
            <div className="font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-indigo-500" />
              Automated Check Diagnostics
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-slate-600 dark:text-slate-300">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${diagnostics.structural_checks_passed ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                <span>Structural Graph Integrity: {diagnostics.structural_checks_passed ? 'Passed' : 'Failed'}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${diagnostics.semantic_checks_passed ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                <span>Bounded Semantic Consistency: {diagnostics.semantic_checks_passed ? 'Passed' : 'Failed'}</span>
              </div>
            </div>
          </div>

          {/* Errors Section */}
          {errors.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-xs font-semibold text-rose-700 dark:text-rose-400 uppercase tracking-wider flex items-center gap-1.5">
                <XCircle className="w-4 h-4" />
                Structural & Semantic Errors ({errors.length})
              </h3>
              <div className="space-y-2">
                {errors.map((err, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-xl bg-rose-50/60 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/60 text-xs space-y-1"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-rose-900 dark:text-rose-200">
                        {err.code || 'VALIDATION_ERROR'}
                      </span>
                      {err.category && (
                        <span className="px-1.5 py-0.5 rounded text-[10px] bg-rose-100 dark:bg-rose-900 text-rose-800 dark:text-rose-200 uppercase">
                          {err.category}
                        </span>
                      )}
                    </div>
                    <p className="text-slate-800 dark:text-slate-200">{err.message}</p>
                    {(err.element_id || err.path) && (
                      <div className="text-[11px] font-mono text-slate-500 dark:text-slate-400">
                        {err.element_id && <span>Element: <code>{err.element_id}</code> </span>}
                        {err.path && <span>Path: <code>{err.path}</code></span>}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Warnings Section */}
          {warnings.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-xs font-semibold text-amber-700 dark:text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4" />
                Validation Warnings ({warnings.length})
              </h3>
              <div className="space-y-2">
                {warnings.map((warn, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-xl bg-amber-50/60 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/60 text-xs space-y-1"
                  >
                    <div className="font-semibold text-amber-900 dark:text-amber-200">
                      {warn.code || 'WARNING'}
                    </div>
                    <p className="text-slate-800 dark:text-slate-200">{warn.message}</p>
                    {warn.element_id && (
                      <div className="text-[11px] font-mono text-slate-500 dark:text-slate-400">
                        Element: <code>{warn.element_id}</code>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Past Reports List */}
          {history.length > 1 && (
            <div className="pt-4 border-t border-slate-200 dark:border-slate-800 space-y-2">
              <h4 className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                Validation Execution History ({history.length} runs recorded)
              </h4>
              <div className="space-y-1 text-xs">
                {history.map((h, i) => (
                  <div
                    key={h.id || i}
                    className="flex items-center justify-between p-2 rounded-lg bg-slate-50 dark:bg-slate-900/40 text-slate-600 dark:text-slate-300"
                  >
                    <span className="font-mono text-[11px]">
                      {new Date(h.created_at).toLocaleString()}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                        h.is_valid
                          ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                          : 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                      }`}
                    >
                      {h.is_valid ? 'Passed' : 'Failed'} ({h.errors?.length || 0} errors)
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium rounded-xl bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-200 hover:bg-slate-300 dark:hover:bg-slate-700 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
