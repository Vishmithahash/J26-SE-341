import React, { useState, useEffect } from 'react';
import {
  X,
  Bot,
  Download,
  ShieldCheck,
  ShieldAlert,
  Copy,
  Check,
} from 'lucide-react';
import { c2Api } from '../api/c2Api';

export const AgentPayloadModal = ({
  isOpen,
  onClose,
  projectId,
  suiteId,
  testId = null, // if null, exports suite-level payloads
}) => {
  const [payloads, setPayloads] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!isOpen || !projectId || !suiteId) {
      setPayloads(null);
      setError(null);
      return;
    }

    setIsLoading(true);
    setError(null);

    const promise = testId
      ? c2Api.getCaseAgentPayload(projectId, suiteId, testId)
      : c2Api.exportAgentTaskPayloads(projectId, suiteId);

    promise
      .then((data) => {
        setPayloads(data);
      })
      .catch((err) => {
        setError(
          err.message ||
            'Failed to retrieve agent payload. Mutant tests and unready cases are excluded from agent task exports.'
        );
        setPayloads(null);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [isOpen, projectId, suiteId, testId]);

  if (!isOpen) return null;

  const downloadJSON = () => {
    if (!payloads) return;
    const filename = testId
      ? `agent_payload_${testId}.json`
      : `agent_payloads_${suiteId}.json`;
    const blob = new Blob([JSON.stringify(payloads, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleCopy = () => {
    if (!payloads) return;
    navigator.clipboard.writeText(JSON.stringify(payloads, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isSingle = Boolean(testId);
  const count = Array.isArray(payloads) ? payloads.length : payloads ? 1 : 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs overflow-y-auto">
      <div className="relative w-full max-w-3xl flex flex-col rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                {isSingle
                  ? `Agent Task Payload (${testId})`
                  : `Exported Agent Task Payloads (${count})`}
              </h2>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                Strictly allowlisted task definitions for tested agents • Private oracle isolated
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

        {/* Isolation Guarantee Banner */}
        <div className="p-4 bg-emerald-50/60 dark:bg-emerald-950/30 border-b border-emerald-100 dark:border-emerald-900/40 text-xs text-emerald-900 dark:text-emerald-200 flex items-start gap-2.5">
          <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <div className="font-semibold">Private-Oracle Isolation Guarantee</div>
            <p className="text-[11px] leading-relaxed text-emerald-800 dark:text-emerald-300">
              In accordance with Component 2 specification, this export strictly transmits only
              task instructions, fixture references, and permitted runtime context. Reference
              paths, expected state transitions, assertions, mutation labels, and divergence
              indicators are completely redacted by the backend.
            </p>
          </div>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto max-h-[60vh] space-y-4">
          {isLoading ? (
            <div className="p-12 text-center text-xs text-slate-500">
              <div className="w-6 h-6 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
              Loading allowlisted agent payloads...
            </div>
          ) : error ? (
            <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-xs text-rose-800 dark:text-rose-200 space-y-1.5">
              <div className="font-semibold flex items-center gap-1.5">
                <ShieldAlert className="w-4 h-4 text-rose-600 shrink-0" />
                <span>Agent Payload Export Blocked</span>
              </div>
              <p className="text-[11px] leading-relaxed">{error}</p>
            </div>
          ) : payloads ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-slate-600 dark:text-slate-400">
                  Allowlisted Schema: <span className="font-mono text-slate-800 dark:text-slate-200">AgentTaskPayload</span>
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleCopy}
                    className="inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-medium transition-colors"
                  >
                    {copied ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                    <span>{copied ? 'Copied' : 'Copy JSON'}</span>
                  </button>
                  <button
                    type="button"
                    onClick={downloadJSON}
                    className="inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-medium shadow-2xs transition-colors"
                  >
                    <Download className="w-3 h-3" />
                    <span>Download JSON</span>
                  </button>
                </div>
              </div>

              <pre className="p-4 rounded-xl bg-slate-900 text-emerald-400 font-mono text-xs overflow-x-auto max-h-96">
                {JSON.stringify(payloads, null, 2)}
              </pre>
            </div>
          ) : null}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/60">
          <div className="text-[11px] text-slate-500 font-mono">
            GET /projects/{projectId}/suites/{suiteId}/{testId ? `cases/${testId}/agent-payload` : 'export/agent'}
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
