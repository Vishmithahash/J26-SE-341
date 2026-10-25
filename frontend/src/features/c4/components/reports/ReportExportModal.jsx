/**
 * Component 4 (C4) - Report Export Modal
 * Provides authenticated, client-side downloadable reports in JSON and Markdown formats.
 * Preserves all identifiers, versions, execution provenance, and evidence limitations.
 * Never puts bearer tokens into URL query strings.
 * Differentiates local export from shared publication.
 */

import React, { useState } from 'react';
import { X, Download, CheckCircle2, Info } from 'lucide-react';

// Live NexaCart provenance for the Markdown report (empty for simulated runs).
function liveAgentRunMarkdown(reportData) {
  const live = reportData?.evaluation_report_summary?.live_nexacart;
  if (!live) return '';
  const calls = (live.tool_calls || [])
    .map(
      (c) =>
        `${c.call_index}. \`${c.tool_name}\` ${JSON.stringify(c.arguments)} — ${c.success ? 'ok' : `error: ${c.error}`}`
    )
    .join('\n');
  return `## Live NexaCart Agent Run
- **Agent Run ID:** ${live.nexacart_agent_run_id}
- **Model:** ${live.agent_model} (${live.agent_status})
- **Untrusted Payload Delivered:** ${live.injection_delivered ? 'yes' : 'no'}

### Tool Calls
${calls || 'The agent called no tools.'}

### Final Answer
${(live.final_answer || '').split('\n').map((line) => `> ${line}`).join('\n')}
`;
}

export function ReportExportModal({ isOpen, onClose, runRecord, runReport }) {
  const [exportFormat, setExportFormat] = useState('json');
  const [downloadSuccess, setDownloadSuccess] = useState(false);

  if (!isOpen || (!runRecord && !runReport)) return null;

  const reportData = runReport || runRecord;

  const handleDownload = () => {
    let content = '';
    let filename = `c4-report-${reportData.run_id || 'run'}.${exportFormat}`;
    let mimeType = 'application/json';

    if (exportFormat === 'json') {
      content = JSON.stringify(reportData, null, 2);
    } else {
      mimeType = 'text/markdown';
      filename = `c4-report-${reportData.run_id || 'run'}.md`;
      content = `# Component 4: Policy-Aware Safety and Prompt-Injection Test Report

## Executive Summary
- **Project ID:** ${reportData.project_id}
- **Run ID:** ${reportData.run_id}
- **Case ID:** ${reportData.case_id} (Version: ${reportData.case_version || 1})
- **Execution Mode:** ${reportData.execution_mode || 'SIMULATED'}
- **Policy Verdict:** ${reportData.policy_verdict || 'NOT_EXERCISED'}
- **Injection Exposure Status:** ${reportData.exposure_status || 'UNKNOWN'}
- **Attacker Objective Outcome:** ${reportData.attacker_objective_outcome || 'NOT_APPLICABLE'}
- **Legitimate Task Utility:** ${reportData.task_utility_outcome || 'UNKNOWN'}
- **Execution Lifecycle Status:** ${reportData.status || reportData.execution_status || 'COMPLETED'}
- **Fixture Cleanup Status:** ${reportData.cleanup_status || 'UNKNOWN'}

## Evaluation Findings
${
  reportData.findings && reportData.findings.length > 0
    ? reportData.findings
        .map(
          (f, idx) => `### Finding ${idx + 1}: ${f.rule_id} (${f.verdict})
- **Severity:** ${f.severity || 'HIGH'}
- **Violation Stage:** ${f.violation_stage || 'NONE'}
- **Attacker Outcome:** ${f.attack_outcome || 'NOT_APPLICABLE'}
- **Benign Utility:** ${f.benign_utility || 'UNKNOWN'}
- **Explanation:** ${f.explanation || 'No explanation provided.'}
${f.missing_evidence && f.missing_evidence.length > 0 ? `- **Observation Limitations:** ${f.missing_evidence.join(', ')}` : ''}
`
        )
        .join('\n')
    : 'No individual rule findings recorded for this run.'
}

${liveAgentRunMarkdown(reportData)}
## Evidence Integrity Notice
- **Publication Status:** Local Export Only (Shared Reporting Service is unconfigured or absent).
- **Provenance Authority:** Authentic backend-evaluated evidence package.
`;
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    setDownloadSuccess(true);
    setTimeout(() => setDownloadSuccess(false), 3000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 dark:bg-indigo-950/70 border border-indigo-200 dark:border-indigo-800 flex items-center justify-center text-indigo-600 dark:text-indigo-400">
              <Download className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                Export Test Run Findings Report
              </h3>
              <p className="text-xs text-slate-500 font-mono">
                Run ID: {reportData.run_id}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-5 text-xs">
          {/* Format Selection */}
          <div>
            <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-2">
              Select Export Format
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setExportFormat('json')}
                className={`p-3 rounded-xl border text-left transition-all ${
                  exportFormat === 'json'
                    ? 'bg-indigo-50 dark:bg-indigo-950/70 border-indigo-300 dark:border-indigo-700 text-indigo-900 dark:text-indigo-200'
                    : 'bg-slate-50 dark:bg-slate-950 border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300'
                }`}
              >
                <span className="font-bold block mb-0.5">JSON Payload</span>
                <span className="text-[11px] text-slate-500">
                  Full structured report with evidence events, rule diffs, and findings.
                </span>
              </button>

              <button
                type="button"
                onClick={() => setExportFormat('md')}
                className={`p-3 rounded-xl border text-left transition-all ${
                  exportFormat === 'md'
                    ? 'bg-indigo-50 dark:bg-indigo-950/70 border-indigo-300 dark:border-indigo-700 text-indigo-900 dark:text-indigo-200'
                    : 'bg-slate-50 dark:bg-slate-950 border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300'
                }`}
              >
                <span className="font-bold block mb-0.5">Markdown Report</span>
                <span className="text-[11px] text-slate-500">
                  Formatted summary for documentation, PR reviews, and audit compliance.
                </span>
              </button>
            </div>
          </div>

          {/* Publication Status Notice */}
          <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-1.5">
            <div className="flex items-center gap-1.5 font-bold text-slate-700 dark:text-slate-300">
              <Info className="w-3.5 h-3.5 text-indigo-500" />
              <span>Publication Scope Notice</span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
              Downloads are generated client-side from authenticated backend responses without exposing bearer tokens in URLs. Shared publication to an external QA dashboard is not available.
            </p>
          </div>

          {downloadSuccess && (
            <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>Report downloaded successfully.</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 dark:border-slate-800 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-semibold transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleDownload}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-sm shadow-indigo-500/20 transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download {exportFormat.toUpperCase()}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
