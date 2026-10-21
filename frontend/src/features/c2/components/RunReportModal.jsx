import React, { useState } from 'react';
import {
  X,
  FileText,
  Download,
  Info,
  Send,
} from 'lucide-react';

export const RunReportModal = ({
  isOpen,
  onClose,
  report,
  exportStatus,
  onExportReport,
  isExporting,
}) => {
  const [downloadSuccess, setDownloadSuccess] = useState(false);

  if (!isOpen || !report) return null;

  const provenance = report.execution_provenance || {};
  const isPublished = exportStatus?.published_to_shared_aggregator || report.published_to_shared_aggregator || false;
  const pubStatus = exportStatus?.publishing_status || report.publishing_status || 'STUB_PENDING_SHARED_AGGREGATOR';

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
                  C2 Report Contribution Contract
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

        {/* Aggregator Publication Status Disclosure */}
        <div className="p-4 bg-indigo-50/60 dark:bg-indigo-950/30 border-b border-indigo-100 dark:border-indigo-900/40 text-xs text-indigo-900 dark:text-indigo-200 flex items-start gap-2.5">
          <Info className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="font-semibold">Shared Aggregator Publication Status:</span>
              <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-indigo-100 dark:bg-indigo-900/60 text-indigo-800 dark:text-indigo-300">
                {pubStatus}
              </span>
            </div>
            <p className="text-[11px] leading-relaxed text-indigo-800 dark:text-indigo-300">
              A locally generated or downloaded report is maintained for local verification.
              Shared multi-component aggregator intake remains pending or stubbed on the server.
              {isPublished ? ' Published finding confirmed.' : ' Report has not been transmitted to a centralized multi-component aggregator.'}
            </p>
          </div>
        </div>

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
                SHA-256 Provenance
              </span>
            </div>
          </div>

          {/* Readiness & Observation Limitations */}
          {(report.readiness_limitations?.length > 0 || report.observation_limitations?.length > 0) && (
            <div className="p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 text-amber-900 dark:text-amber-200 space-y-2">
              <span className="font-bold text-[11px] uppercase tracking-wide">
                Honest Readiness & Observation Limitations
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
              <span>{isExporting ? 'Exporting...' : 'Export Finding via Adapter'}</span>
            </button>

            <button
              type="button"
              onClick={downloadJSON}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-semibold transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              <span>{downloadSuccess ? 'Downloaded!' : 'Download JSON'}</span>
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
