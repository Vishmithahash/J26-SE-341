import React, { useState } from 'react';
import {
  X,
  FileText,
  Download,
  Info,
  Send,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
} from 'lucide-react';

export const RunReportModal = ({
  isOpen,
  onClose,
  report,
  exportStatus,
  exportError,
  lastConfirmedReceipt,
  onExportReport,
  isExporting,
}) => {
  const [downloadSuccess, setDownloadSuccess] = useState(false);

  if (!isOpen || !report) return null;

  const provenance = report.execution_provenance || {};

  // Determine actual publication state
  let publicationState = 'NOT_PUBLISHED'; // 'CONFIRMED' | 'FAILED' | 'UNAVAILABLE' | 'NOT_PUBLISHED'
  if (exportError) {
    publicationState = 'FAILED';
  } else if (
    exportStatus?.published_to_shared_aggregator ||
    exportStatus?.publishing_status === 'PUBLISHED' ||
    report.published_to_shared_aggregator ||
    report.publishing_status === 'PUBLISHED' ||
    lastConfirmedReceipt
  ) {
    publicationState = 'CONFIRMED';
  } else if (
    report.publishing_status === 'UNAVAILABLE' ||
    report.publishing_status === 'UNKNOWN' ||
    exportStatus?.publishing_status === 'UNAVAILABLE' ||
    exportStatus?.publishing_status === 'UNKNOWN'
  ) {
    publicationState = 'UNAVAILABLE';
  } else {
    publicationState = 'NOT_PUBLISHED';
  }

  const activeReceipt = lastConfirmedReceipt || (publicationState === 'CONFIRMED' ? exportStatus || report : null);

  const downloadJSON = () => {
    const filename = `c2_report_${report.evaluation_id || report.run_id}.json`;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    setDownloadSuccess(true);
    setTimeout(() => setDownloadSuccess(false), 2500);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs overflow-y-auto">
      <div className="relative w-full max-w-3xl flex flex-col rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                  C2 Report Contribution
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                  v{report.contract_version || '2026.1'}
                </span>
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                Evaluation ID: <code className="font-mono">{report.evaluation_id}</code> • Run: <code className="font-mono">{report.run_id}</code>
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Dynamic Aggregator Publication Status Display */}
        {publicationState === 'CONFIRMED' && (
          <div className="p-4 bg-emerald-50/70 dark:bg-emerald-950/30 border-b border-emerald-100 dark:border-emerald-900/40 text-xs text-emerald-900 dark:text-emerald-200 flex items-start gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-semibold">Shared Aggregator Publication:</span>
                <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-900/60 text-emerald-800 dark:text-emerald-300 font-semibold">
                  Confirmed publication
                </span>
              </div>
              <p className="text-[11px] leading-relaxed text-emerald-800 dark:text-emerald-300">
                Report contribution has been published to the shared integration aggregator.
                {activeReceipt?.contribution_id && (
                  <span className="block font-mono text-[10px] mt-0.5 text-emerald-700 dark:text-emerald-400">
                    Contribution ID: {activeReceipt.contribution_id}
                  </span>
                )}
              </p>
            </div>
          </div>
        )}

        {publicationState === 'FAILED' && (
          <div className="p-4 bg-rose-50/70 dark:bg-rose-950/30 border-b border-rose-100 dark:border-rose-900/40 text-xs text-rose-900 dark:text-rose-200 flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-semibold">Shared Aggregator Publication:</span>
                <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-rose-100 dark:bg-rose-900/60 text-rose-800 dark:text-rose-300 font-semibold">
                  {exportError?.status === 409 ? 'Publication conflict (HTTP 409)' : 'Failed publication attempt'}
                </span>
              </div>
              <p className="text-[11px] leading-relaxed text-rose-800 dark:text-rose-300">
                {exportError?.message || 'Publication attempt failed.'}
              </p>
              <p className="text-[10px] text-rose-700 dark:text-rose-400">
                The report remains preserved and available for local inspection and download.
              </p>
              {lastConfirmedReceipt && (
                <div className="text-[10px] font-mono text-slate-600 dark:text-slate-400 mt-1 pt-1 border-t border-rose-200 dark:border-rose-900/40">
                  Last confirmed receipt preserved: {lastConfirmedReceipt.contribution_id || 'available'}
                </div>
              )}
            </div>
          </div>
        )}

        {publicationState === 'UNAVAILABLE' && (
          <div className="p-4 bg-amber-50/70 dark:bg-amber-950/30 border-b border-amber-100 dark:border-amber-900/40 text-xs text-amber-900 dark:text-amber-200 flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-semibold">Shared Aggregator Publication:</span>
                <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-amber-100 dark:bg-amber-900/60 text-amber-800 dark:text-amber-300 font-semibold">
                  Publication unavailable/unknown
                </span>
              </div>
              <p className="text-[11px] leading-relaxed text-amber-800 dark:text-amber-300">
                Shared integration publication service is currently unavailable or status is unknown.
              </p>
            </div>
          </div>
        )}

        {publicationState === 'NOT_PUBLISHED' && (
          <div className="p-4 bg-slate-50 dark:bg-slate-900/50 border-b border-slate-200 dark:border-slate-800 text-xs text-slate-700 dark:text-slate-300 flex items-start gap-2.5">
            <Info className="w-4 h-4 text-slate-500 dark:text-slate-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-semibold">Shared Aggregator Publication:</span>
                <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                  Not published
                </span>
              </div>
              <p className="text-[11px] leading-relaxed text-slate-600 dark:text-slate-400">
                Report has not been transmitted to the shared aggregator. Click &quot;Export report&quot; to publish finding.
              </p>
            </div>
          </div>
        )}

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto max-h-[60vh] space-y-4 text-xs">
          {/* Metadata Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50">
              <span className="text-[10px] text-slate-400 uppercase font-semibold">Verdict:</span>
              <div className="font-bold text-slate-900 dark:text-white mt-1">
                {report.verdict}
              </div>
              <span className="text-[10px] text-slate-500 font-mono">
                {report.verdict_category}
              </span>
            </div>

            <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50">
              <span className="text-[10px] text-slate-400 uppercase font-semibold">Actual Origin:</span>
              <div className="font-semibold text-slate-800 dark:text-slate-200 mt-1 truncate" title={provenance.actual_execution_origin}>
                {provenance.actual_execution_origin || 'synthetic_demonstration'}
              </div>
              <span className="text-[10px] font-mono text-slate-400">
                is_live: {provenance.is_live_execution ? 'true' : 'false'}
              </span>
            </div>

            <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50">
              <span className="text-[10px] text-slate-400 uppercase font-semibold">Runner & Evaluator:</span>
              <div className="font-mono text-slate-800 dark:text-slate-200 mt-1 truncate">
                {provenance.runner_id}
              </div>
              <span className="text-[10px] font-mono text-slate-400">
                {report.evaluator_version}
              </span>
            </div>

            <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50">
              <span className="text-[10px] text-slate-400 uppercase font-semibold">Evidence Digest:</span>
              <div className="font-mono text-indigo-600 dark:text-indigo-400 mt-1 truncate" title={report.evidence_digest}>
                {report.evidence_digest ? `${report.evidence_digest.substring(0, 12)}...` : 'None'}
              </div>
              <span className="text-[10px] text-slate-400">
                Content checksum
              </span>
            </div>
          </div>

          {/* Readiness & Observation Limitations */}
          {(report.readiness_limitations?.length > 0 || report.observation_limitations?.length > 0) && (
            <div className="p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 text-amber-900 dark:text-amber-200 space-y-2">
              <span className="font-bold text-[11px] uppercase tracking-wide">
                Readiness & Observation Limitations
              </span>
              <ul className="list-disc pl-5 space-y-1 text-[11px]">
                {report.readiness_limitations?.map((r, i) => (
                  <li key={`r-${i}`}>{r}</li>
                ))}
                {report.observation_limitations?.map((o, i) => (
                  <li key={`o-${i}`}>{o}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Full Report Payload (JSON) */}
          <div className="space-y-2">
            <span className="font-semibold text-slate-700 dark:text-slate-300">
              Complete Structured Report JSON:
            </span>
            <pre className="p-3 rounded-xl bg-slate-900 text-slate-200 font-mono text-[11px] overflow-x-auto max-h-64">
              {JSON.stringify(report, null, 2)}
            </pre>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between p-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/60">
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={isExporting}
              onClick={() => onExportReport && onExportReport(report.evaluation_id)}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-semibold shadow-xs transition-colors"
            >
              <Send className="w-3.5 h-3.5" />
              <span>{isExporting ? 'Exporting...' : 'Export report'}</span>
            </button>

            <button
              type="button"
              onClick={downloadJSON}
              title="Save report locally to your machine (independent of publication)"
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-semibold transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              <span>{downloadSuccess ? 'Downloaded locally!' : 'Download JSON (Local)'}</span>
            </button>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-200 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
