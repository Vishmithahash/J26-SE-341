import React, { useState } from 'react';
import {
  X,
  UploadCloud,
  CheckCircle2,
  AlertTriangle,
  FileCode,
  ShieldCheck,
  Loader2,
} from 'lucide-react';
import { useC3EvidenceImport } from '../hooks/useC3EvidenceImport';
import {
  DEMO_MATCHED_PAIR_EVIDENCE,
  DEMO_MATCHED_PAIR_NOT_TRIGGERED,
  DEMO_MATCHED_PAIR_DISQUALIFIED_CLEAN,
  DEMO_TRACKED_EXECUTION,
} from '../fixtures';

export const C3EvidenceImportModal = ({ isOpen, onClose, projectId, onImportSuccess }) => {
  const [importType, setImportType] = useState('pair'); // 'pair' | 'execution'
  const [jsonText, setJsonText] = useState(
    JSON.stringify(DEMO_MATCHED_PAIR_EVIDENCE, null, 2)
  );
  const [clientSyntaxError, setClientSyntaxError] = useState(null);

  const {
    isImporting,
    importStatus,
    importedRecord,
    importError,
    importEvidence,
    resetImportState,
  } = useC3EvidenceImport();

  if (!isOpen) return null;

  const handleJsonChange = (e) => {
    const text = e.target.value;
    setJsonText(text);
    try {
      JSON.parse(text);
      setClientSyntaxError(null);
    } catch (err) {
      setClientSyntaxError(`JSON Syntax Error: ${err.message}`);
    }
  };

  const handleLoadPreset = (presetType) => {
    resetImportState();
    if (presetType === 'confirmed') {
      setImportType('pair');
      setJsonText(JSON.stringify(DEMO_MATCHED_PAIR_EVIDENCE, null, 2));
      setClientSyntaxError(null);
    } else if (presetType === 'not_triggered') {
      setImportType('pair');
      setJsonText(JSON.stringify(DEMO_MATCHED_PAIR_NOT_TRIGGERED, null, 2));
      setClientSyntaxError(null);
    } else if (presetType === 'disqualified') {
      setImportType('pair');
      setJsonText(JSON.stringify(DEMO_MATCHED_PAIR_DISQUALIFIED_CLEAN, null, 2));
      setClientSyntaxError(null);
    } else if (presetType === 'execution') {
      setImportType('execution');
      setJsonText(JSON.stringify(DEMO_TRACKED_EXECUTION, null, 2));
      setClientSyntaxError(null);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (clientSyntaxError || isImporting) return;

    const result = await importEvidence({
      type: importType,
      projectId,
      jsonContent: jsonText,
    });

    if (result.success && onImportSuccess) {
      onImportSuccess(result.data);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-teal-50 dark:bg-teal-950/60 text-teal-600 dark:text-teal-400 flex items-center justify-center">
              <UploadCloud className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                Import Evidence Artifact
              </h2>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                Project Scope: <code className="font-mono">{projectId || 'No project'}</code>
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Informational Disclosure */}
        <div className="px-6 py-2.5 bg-slate-50 dark:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800 text-[11px] text-slate-600 dark:text-slate-400 flex items-start gap-2">
          <ShieldCheck className="w-3.5 h-3.5 text-teal-600 dark:text-teal-400 shrink-0 mt-0.5" />
          <span>
            <strong>Honest Execution Disclosure:</strong> Importing evidence stores verified offline or CLI test records into project scope. It does not trigger a live target trial or generate synthetic fake receipts.
          </span>
        </div>

        {/* Content Body */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-4">
          {/* Target Type Selector */}
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                Artifact Type:
              </span>
              <div className="inline-flex rounded-lg border border-slate-200 dark:border-slate-800 p-0.5 bg-slate-100 dark:bg-slate-800 text-xs">
                <button
                  type="button"
                  onClick={() => setImportType('pair')}
                  className={`px-3 py-1 rounded-md font-medium transition-colors ${
                    importType === 'pair'
                      ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
                  }`}
                >
                  Matched Pair Evidence
                </button>
                <button
                  type="button"
                  onClick={() => setImportType('execution')}
                  className={`px-3 py-1 rounded-md font-medium transition-colors ${
                    importType === 'execution'
                      ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
                  }`}
                >
                  Execution Artifact
                </button>
              </div>
            </div>

            {/* Presets */}
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[11px] text-slate-400">Presets:</span>
              <button
                type="button"
                onClick={() => handleLoadPreset('confirmed')}
                className="text-[10px] px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 text-slate-600 dark:text-slate-300 hover:text-indigo-600 font-medium border border-slate-200 dark:border-slate-700"
              >
                Confirmed
              </button>
              <button
                type="button"
                onClick={() => handleLoadPreset('not_triggered')}
                className="text-[10px] px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 hover:bg-amber-50 dark:hover:bg-amber-950/40 text-slate-600 dark:text-slate-300 hover:text-amber-600 font-medium border border-slate-200 dark:border-slate-700"
              >
                Not-Triggered
              </button>
              <button
                type="button"
                onClick={() => handleLoadPreset('disqualified')}
                className="text-[10px] px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 hover:bg-rose-50 dark:hover:bg-rose-950/40 text-slate-600 dark:text-slate-300 hover:text-rose-600 font-medium border border-slate-200 dark:border-slate-700"
              >
                Failed Clean
              </button>
              <button
                type="button"
                onClick={() => handleLoadPreset('execution')}
                className="text-[10px] px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 hover:bg-teal-50 dark:hover:bg-teal-950/40 text-slate-600 dark:text-slate-300 hover:text-teal-600 font-medium border border-slate-200 dark:border-slate-700"
              >
                Execution Run
              </button>
            </div>
          </div>

          {/* JSON Textarea Editor */}
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs text-slate-500">
              <label htmlFor="evidence-json-editor" className="font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                <FileCode className="w-3.5 h-3.5" />
                <span>Evidence JSON Payload:</span>
              </label>
              <span>Max 2MB</span>
            </div>
            <textarea
              id="evidence-json-editor"
              rows={12}
              value={jsonText}
              onChange={handleJsonChange}
              className={`w-full font-mono text-xs p-3 rounded-xl border bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 focus:outline-hidden focus:ring-2 transition-colors ${
                clientSyntaxError
                  ? 'border-rose-400 focus:ring-rose-500'
                  : 'border-slate-200 dark:border-slate-800 focus:ring-indigo-500'
              }`}
            />
          </div>

          {/* Client Syntax Error Feedback */}
          {clientSyntaxError && (
            <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/50 text-xs text-rose-700 dark:text-rose-300 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{clientSyntaxError}</span>
            </div>
          )}

          {/* Backend Import Error Feedback */}
          {importError && (
            <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/50 text-xs text-rose-700 dark:text-rose-300 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold">Backend Import Error:</span>
                <p className="mt-0.5">{importError}</p>
              </div>
            </div>
          )}

          {/* Import Success Feedback */}
          {importStatus === 'success' && importedRecord && (
            <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-900/50 text-xs text-emerald-800 dark:text-emerald-200 flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600 mt-0.5" />
              <div>
                <span className="font-semibold">Evidence Successfully Imported!</span>
                <p className="mt-0.5">
                  Record ID: <code className="font-mono">{importedRecord.pair_id || importedRecord.execution_id}</code> persisted into project scope.
                </p>
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="pt-2 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isImporting}
              className="px-4 py-2 text-xs font-semibold rounded-xl text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isImporting || Boolean(clientSyntaxError) || !projectId}
              className="px-5 py-2 text-xs font-semibold rounded-xl bg-teal-600 hover:bg-teal-500 text-white shadow-xs disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors"
            >
              {isImporting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Validating & Storing...</span>
                </>
              ) : (
                <>
                  <UploadCloud className="w-3.5 h-3.5" />
                  <span>Import Evidence</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
