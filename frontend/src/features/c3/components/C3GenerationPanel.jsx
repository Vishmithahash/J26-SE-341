import React, { useState } from 'react';
import {
  Sparkles,
  RotateCw,
  Save,
  CheckCircle2,
  AlertTriangle,
  Fingerprint,
  Download,
  AlertCircle,
  FileCheck,
  Code,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { C3Badge } from './C3Badge.jsx';
import { useProject } from '../../../context/ProjectContext';

export const C3GenerationPanel = ({
  taskFixtureMetadata,
  adapterManifest,
  recoveryContract,
  generationPolicy,
  onGenerate,
  isGenerating,
  generationResult,
  generationError,
  onSaveSuite,
  isSaving,
  saveStatus,
  savedSuite,
  saveError,
}) => {
  const { activeProject, activeProjectId } = useProject();
  const [showRaw, setShowRaw] = useState(false);
  const [selectedCaseDetail, setSelectedCaseDetail] = useState(null);

  const handleGenerate = (e) => {
    e.preventDefault();
    if (!activeProjectId) {
      alert('Please select an active project before generating cases.');
      return;
    }

    const payload = {
      schema_version: '1.0.0',
      project_id: activeProjectId,
      domain: taskFixtureMetadata.domain || activeProject?.domain || 'ecommerce',
      task_id: taskFixtureMetadata.task_id,
      task_version: taskFixtureMetadata.task_version,
      task_fixture_metadata: taskFixtureMetadata,
      adapter_manifest: adapterManifest,
      recovery_contract: recoveryContract,
      policy: generationPolicy,
    };
    onGenerate(payload);
  };

  const handleSave = () => {
    if (!generationResult?.frozen_suite) return;
    if (!activeProjectId) return;
    onSaveSuite(activeProjectId, generationResult.frozen_suite);
  };

  const handleExportJson = () => {
    if (!generationResult?.frozen_suite) return;
    const blob = new Blob(
      [JSON.stringify(generationResult.frozen_suite, null, 2)],
      { type: 'application/json' }
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `frozen_suite_${generationResult.frozen_suite.suite_id}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const counters = generationResult?.counters || generationResult?.frozen_suite?.counters;
  const suite = generationResult?.frozen_suite;
  const cases = suite?.selected_cases || [];

  return (
    <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
      {/* Header and Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <span>Automatic Feasible Fault Case Generation</span>
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Pure deterministic generation, deduplication, and cryptographic freezing of candidate test suites.
          </p>
        </div>

        <button
          type="button"
          onClick={handleGenerate}
          disabled={isGenerating || !activeProjectId}
          className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white shadow-xs transition-colors shrink-0"
        >
          {isGenerating ? (
            <>
              <RotateCw className="w-3.5 h-3.5 animate-spin" />
              <span>Generating Feasible Cases...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-3.5 h-3.5" />
              <span>Generate Feasible Suite</span>
            </>
          )}
        </button>
      </div>

      {/* No active project warning */}
      {!activeProjectId && (
        <div className="p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-xs text-amber-800 dark:text-amber-300">
          Generation requires an authorized active project. Please select or register a project first.
        </div>
      )}

      {/* Error Notice */}
      {generationError && (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-700 dark:text-rose-300 flex items-start gap-2.5">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-semibold">Generation Failed</span>
            <p>{generationError}</p>
          </div>
        </div>
      )}

      {/* Results Section */}
      {generationResult && (
        <div className="space-y-5 pt-1">
          {/* Status & Save Banner */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-2.5 flex-wrap">
              <span className="text-sm font-bold text-slate-900 dark:text-white">
                Generation Status:
              </span>
              <C3Badge status={generationResult.generation_status} />
              <C3Badge status="STATIC_ONLY" label="Static Foundation Only" />

              {/* Persistence State */}
              {saveStatus === 'SAVED' ? (
                <C3Badge status="SAVED" label={savedSuite?.suite_id ? `Persisted (${savedSuite.suite_id})` : 'Persisted to Project'} />
              ) : saveStatus === 'SAVING' ? (
                <C3Badge status="SAVING" label="Saving to DB..." />
              ) : saveStatus === 'FAILED' ? (
                <C3Badge status="FAILED" label="Save Failed" />
              ) : (
                <C3Badge status="UNSAVED" label="In-Memory (Unsaved)" />
              )}
            </div>

            {/* Action buttons */}
            {suite && (
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  onClick={handleExportJson}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Export JSON</span>
                </button>

                <button
                  type="button"
                  onClick={handleSave}
                  disabled={isSaving || saveStatus === 'SAVED'}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white transition-colors shadow-xs"
                >
                  {isSaving ? (
                    <>
                      <RotateCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Saving...</span>
                    </>
                  ) : saveStatus === 'SAVED' ? (
                    <>
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Saved to Project</span>
                    </>
                  ) : (
                    <>
                      <Save className="w-3.5 h-3.5" />
                      <span>Save / Import Suite</span>
                    </>
                  )}
                </button>
              </div>
            )}
          </div>

          {/* Save Error */}
          {saveError && (
            <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-700 dark:text-rose-300">
              Save error: {saveError}
            </div>
          )}

          {/* Real-time Candidate Population Counters */}
          {counters && (
            <div className="space-y-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Candidate Search Population Accounting
              </span>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 text-center">
                  <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 block">Examined</span>
                  <span className="text-xl font-bold text-slate-900 dark:text-white mt-1 block">
                    {counters.examined_count ?? counters.examined_candidates_count ?? 0}
                  </span>
                  <span className="text-[10px] text-slate-400">permutations</span>
                </div>

                <div className="p-3 rounded-xl bg-emerald-50/50 dark:bg-emerald-950/20 border border-emerald-200/60 dark:border-emerald-800/60 text-center">
                  <span className="text-[11px] font-semibold text-emerald-700 dark:text-emerald-400 block">Valid</span>
                  <span className="text-xl font-bold text-emerald-900 dark:text-emerald-200 mt-1 block">
                    {counters.valid_count ?? 0}
                  </span>
                  <span className="text-[10px] text-emerald-600 dark:text-emerald-400">passed static checks</span>
                </div>

                <div className="p-3 rounded-xl bg-amber-50/50 dark:bg-amber-950/20 border border-amber-200/60 dark:border-amber-800/60 text-center">
                  <span className="text-[11px] font-semibold text-amber-700 dark:text-amber-400 block">Rejected</span>
                  <span className="text-xl font-bold text-amber-900 dark:text-amber-200 mt-1 block">
                    {counters.rejected_count ?? 0}
                  </span>
                  <span className="text-[10px] text-amber-600 dark:text-amber-400">incompatible</span>
                </div>

                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 text-center">
                  <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 block">Duplicate</span>
                  <span className="text-xl font-bold text-slate-900 dark:text-white mt-1 block">
                    {counters.duplicate_count ?? 0}
                  </span>
                  <span className="text-[10px] text-slate-400">fingerprint matches</span>
                </div>

                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 text-center">
                  <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 block">Unique</span>
                  <span className="text-xl font-bold text-slate-900 dark:text-white mt-1 block">
                    {counters.unique_count ?? 0}
                  </span>
                  <span className="text-[10px] text-slate-400">feasible pool</span>
                </div>

                <div className="p-3 rounded-xl bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-200/60 dark:border-indigo-800/60 text-center">
                  <span className="text-[11px] font-semibold text-indigo-700 dark:text-indigo-400 block">Selected</span>
                  <span className="text-xl font-bold text-indigo-900 dark:text-indigo-200 mt-1 block">
                    {counters.selected_count ?? counters.selected_cases_count ?? 0}
                  </span>
                  <span className="text-[10px] text-indigo-600 dark:text-indigo-400">frozen suite</span>
                </div>
              </div>

              {counters.truncated && (
                <div className="p-2.5 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-xs text-amber-800 dark:text-amber-300 flex items-center gap-2">
                  <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                  <span>
                    Search budget reached candidate search limit (<code className="font-mono">{counters.truncation_reason || 'max_candidates_examined'}</code>).
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Frozen Suite Metadata & Digest */}
          {suite && (
            <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
                <div>
                  <div className="flex items-center gap-2">
                    <FileCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                    <span className="text-sm font-bold text-slate-900 dark:text-white">
                      Frozen Suite Snapshot: <code className="font-mono text-indigo-600 dark:text-indigo-400">{suite.suite_id}</code>
                    </span>
                  </div>
                  <span className="text-xs text-slate-400 mt-0.5 block">
                    Generator Version: {suite.generator_version} • Seed: {suite.seed}
                  </span>
                </div>

                <div className="flex items-center gap-1.5">
                  <Fingerprint className="w-4 h-4 text-slate-400" />
                  <span className="text-xs font-semibold text-slate-500">Suite Digest (SHA-256):</span>
                </div>
              </div>

              {/* SHA-256 Digest Bar */}
              <div className="p-3 rounded-xl bg-slate-950 text-slate-100 font-mono text-xs break-all flex items-center justify-between gap-2 border border-slate-800">
                <span className="text-emerald-400 select-all">{suite.suite_digest}</span>
                <span className="text-[10px] text-slate-400 uppercase tracking-wider shrink-0 bg-slate-800 px-2 py-0.5 rounded">
                  Immutable Digest
                </span>
              </div>

              {/* Selected Cases Table */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Selected Feasible Cases ({cases.length})
                  </span>
                  <span className="text-[11px] text-slate-400">
                    Click case to inspect declared payload & fingerprint
                  </span>
                </div>

                <div className="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-xl">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400">
                        <th className="py-2.5 px-3 font-semibold">Case ID</th>
                        <th className="py-2.5 px-3 font-semibold">Tool</th>
                        <th className="py-2.5 px-3 font-semibold">Fault Family</th>
                        <th className="py-2.5 px-3 font-semibold">Phase</th>
                        <th className="py-2.5 px-3 font-semibold">Payload Mode</th>
                        <th className="py-2.5 px-3 font-semibold">Fingerprint (Prefix)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono">
                      {cases.map((c) => {
                        const fp = suite.case_fingerprints?.[c.case_id] || '';
                        const isExpanded = selectedCaseDetail?.case_id === c.case_id;

                        return (
                          <React.Fragment key={c.case_id}>
                            <tr
                              onClick={() => setSelectedCaseDetail(isExpanded ? null : c)}
                              className="hover:bg-slate-50 dark:hover:bg-slate-800/40 cursor-pointer text-slate-700 dark:text-slate-300"
                            >
                              <td className="py-2.5 px-3 font-semibold text-slate-900 dark:text-white">
                                {c.case_id}
                              </td>
                              <td className="py-2.5 px-3 text-slate-600 dark:text-slate-400">
                                {c.tool_id}
                              </td>
                              <td className="py-2.5 px-3">
                                <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                                  {c.fault_family}
                                </span>
                              </td>
                              <td className="py-2.5 px-3">
                                <span
                                  className={`px-1.5 py-0.5 rounded text-[10px] ${
                                    c.effect_phase === 'AFTER_COMMIT'
                                      ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300'
                                      : 'bg-teal-100 dark:bg-teal-900/40 text-teal-800 dark:text-teal-300'
                                  }`}
                                >
                                  {c.effect_phase}
                                </span>
                              </td>
                              <td className="py-2.5 px-3 text-slate-500">
                                {c.payload?.mode || c.payload?.http_status || 'standard'}
                              </td>
                              <td className="py-2.5 px-3 text-slate-400 text-[11px]">
                                {fp ? fp.substring(0, 16) + '...' : 'n/a'}
                              </td>
                            </tr>

                            {/* Expanded Case Snapshot Drawer */}
                            {isExpanded && (
                              <tr className="bg-slate-50/80 dark:bg-slate-800/50">
                                <td colSpan={6} className="p-4 space-y-2 text-xs font-sans">
                                  <div className="font-bold text-slate-900 dark:text-white flex items-center justify-between">
                                    <span>Case Snapshot: {c.case_id} ({c.case_family_id})</span>
                                    <span className="font-mono text-[10px] text-slate-400">
                                      Full Fingerprint: {fp}
                                    </span>
                                  </div>
                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1 text-slate-600 dark:text-slate-300">
                                    <div>
                                      <span className="font-semibold text-slate-500 block">Payload:</span>
                                      <pre className="p-2 rounded bg-slate-900 text-slate-100 text-[11px] font-mono mt-1 overflow-x-auto">
                                        {JSON.stringify(c.payload, null, 2)}
                                      </pre>
                                    </div>
                                    <div>
                                      <span className="font-semibold text-slate-500 block">Release Rule & Bounds:</span>
                                      <pre className="p-2 rounded bg-slate-900 text-slate-100 text-[11px] font-mono mt-1 overflow-x-auto">
                                        {JSON.stringify(c.release_rule, null, 2)}
                                      </pre>
                                      <div className="mt-2 text-[11px] text-slate-500">
                                        Assertions: {c.required_assertions?.join(', ')} • Observations: {c.required_observations?.join(', ')}
                                      </div>
                                    </div>
                                  </div>
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Suite Limitations */}
              {suite.limitations && suite.limitations.length > 0 && (
                <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 text-xs text-slate-600 dark:text-slate-400 space-y-1">
                  <span className="font-semibold text-slate-700 dark:text-slate-300">
                    Declared Suite Scope & Limitations:
                  </span>
                  <ul className="list-disc list-inside space-y-0.5 pl-1 text-[11px]">
                    {suite.limitations.map((lim, idx) => (
                      <li key={idx}>{lim}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Raw JSON Debug Accordion */}
          <div>
            <button
              type="button"
              onClick={() => setShowRaw(!showRaw)}
              className="text-xs text-slate-500 hover:text-slate-900 dark:hover:text-white flex items-center gap-1"
            >
              <Code className="w-3.5 h-3.5" />
              <span>{showRaw ? 'Hide Raw Generation Response' : 'Inspect Raw Generation Response'}</span>
              {showRaw ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
            {showRaw && (
              <pre className="mt-2 p-3 rounded-xl bg-slate-950 text-slate-100 text-[11px] font-mono overflow-x-auto max-h-60">
                {JSON.stringify(generationResult, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
