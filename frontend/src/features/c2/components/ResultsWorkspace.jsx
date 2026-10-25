import React, { useEffect, useState } from 'react';
import {
  Activity,
  RotateCw,
  CheckCheck,
  FileText,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  AlertCircle,
  Info,
  RefreshCw,
} from 'lucide-react';
import { WorkflowEvidenceViewer } from './WorkflowEvidenceViewer';
import { ObservedCoverageViewer } from './ObservedCoverageViewer';
import { RunReportModal } from './RunReportModal';
import { VERDICT_CONFIG, PROVENANCE_CONFIG } from '../constants/resultsConfig.js';
import { c2Api } from '../api/c2Api.js';

const VERDICT_ICONS = {
  PASS: CheckCircle2,
  'EXPECTED REJECTION PASS': CheckCircle2,
  FAIL: XCircle,
  INCONCLUSIVE: AlertTriangle,
  'MODEL NOT READY': AlertCircle,
  'TEST NOT READY': AlertCircle,
};

export const ResultsWorkspace = ({
  projectId,
  resultsState,
}) => {
  const {
    evaluations,
    selectedEvaluation,
    retainedEvidence,
    observedCoverage,
    runReport,
    exportStatus,
    exportError,
    lastConfirmedReceipt,
    reproductionResult,
    suiteFilter,
    testFilter,
    verdictFilter,
    originFilter,
    modelVersionFilter,
    isLoadingEvaluations,
    isLoadingEvidence,
    isExportingReport,
    isReEvaluating,
    actionError,
    setSuiteFilter,
    setTestFilter,
    setVerdictFilter,
    setOriginFilter,
    setModelVersionFilter,
    selectEvaluation,
    exportReport,
    reEvaluate,
    verifyReproduction,
    refreshEvaluations,
    clearActionError,
  } = resultsState;

  const [activeViewTab, setActiveViewTab] = useState('evidence'); // 'evidence' | 'coverage'
  const [showReportModal, setShowReportModal] = useState(false);
  // The evaluated case's frozen definition: its planned reference path and category
  const [plannedCase, setPlannedCase] = useState(null);

  useEffect(() => {
    setPlannedCase(null);
    const suiteId = selectedEvaluation?.suite_id;
    const testId = selectedEvaluation?.test_id;
    if (!projectId || !suiteId || !testId) return undefined;
    let cancelled = false;
    c2Api
      .getTestCaseDetail(projectId, suiteId, testId)
      .then((detail) => {
        if (!cancelled) setPlannedCase(detail?.definition || null);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [projectId, selectedEvaluation?.suite_id, selectedEvaluation?.test_id]);

  const currentVerdict = selectedEvaluation?.verdict ? String(selectedEvaluation.verdict).toUpperCase() : null;
  const verdictConfig = currentVerdict && VERDICT_CONFIG[currentVerdict] ? VERDICT_CONFIG[currentVerdict] : null;
  const VerdictIcon = currentVerdict && VERDICT_ICONS[currentVerdict] ? VERDICT_ICONS[currentVerdict] : Info;

  return (
    <div className="space-y-6">
      {/* Action Error Banner */}
      {actionError && (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-xs text-rose-800 dark:text-rose-200 flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{actionError}</span>
          </div>
          <button
            type="button"
            onClick={clearActionError}
            className="text-xs font-semibold text-rose-700 dark:text-rose-300 hover:underline shrink-0"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* 1. Results Filter Bar */}
      <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <h2 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
              Workflow Evaluation Results & Evidence
            </h2>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
              {evaluations.length} records
            </span>
          </div>

          <button
            type="button"
            onClick={() => refreshEvaluations()}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 text-xs font-medium transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoadingEvaluations ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>

        {/* Filters Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 pt-1 text-xs">
          {/* Verdict Filter (all 6 verdicts) */}
          <div>
            <label className="text-[10px] font-semibold text-slate-400 uppercase">Verdict:</label>
            <select
              value={verdictFilter}
              onChange={(e) => setVerdictFilter(e.target.value)}
              className="w-full mt-1 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-xs"
            >
              <option value="">All Verdicts</option>
              <option value="PASS">PASS</option>
              <option value="EXPECTED REJECTION PASS">EXPECTED REJECTION PASS</option>
              <option value="FAIL">FAIL</option>
              <option value="INCONCLUSIVE">INCONCLUSIVE</option>
              <option value="MODEL NOT READY">MODEL NOT READY</option>
              <option value="TEST NOT READY">TEST NOT READY</option>
            </select>
          </div>

          {/* Execution Origin Filter */}
          <div>
            <label className="text-[10px] font-semibold text-slate-400 uppercase">Origin:</label>
            <select
              value={originFilter}
              onChange={(e) => setOriginFilter(e.target.value)}
              className="w-full mt-1 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-xs"
            >
              <option value="">All Origins</option>
              <option value="live_agent_run">Live Agent Run</option>
              <option value="live_nexacart_agent">Live NexaCart Agent</option>
              <option value="live_trace_mutation">Live-Trace Mutant</option>
              <option value="scripted_synthetic_demonstration">Scripted Demonstration</option>
              <option value="controlled_trace_fixture">Controlled Fixture</option>
            </select>
          </div>

          {/* Suite Filter */}
          <div>
            <label className="text-[10px] font-semibold text-slate-400 uppercase">Suite ID:</label>
            <input
              type="text"
              placeholder="Filter by suite..."
              value={suiteFilter}
              onChange={(e) => setSuiteFilter(e.target.value)}
              className="w-full mt-1 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-xs font-mono"
            />
          </div>

          {/* Test Case Filter */}
          <div>
            <label className="text-[10px] font-semibold text-slate-400 uppercase">Test ID:</label>
            <input
              type="text"
              placeholder="Filter by test..."
              value={testFilter}
              onChange={(e) => setTestFilter(e.target.value)}
              className="w-full mt-1 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-xs font-mono"
            />
          </div>

          {/* Model Version Filter */}
          <div>
            <label className="text-[10px] font-semibold text-slate-400 uppercase">Model Version:</label>
            <input
              type="text"
              placeholder="e.g. 1.0.0"
              value={modelVersionFilter}
              onChange={(e) => setModelVersionFilter(e.target.value)}
              className="w-full mt-1 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-xs font-mono"
            />
          </div>
        </div>
      </div>

      {/* 2. Main 2-Column Split: Evaluations List on Left, Active Result Detail on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Evaluations Card List (5 cols) */}
        <div className="lg:col-span-4 space-y-2">
          <div className="text-[11px] font-semibold text-slate-400 uppercase px-1">
            Evaluations ({evaluations.length})
          </div>

          {isLoadingEvaluations ? (
            <div className="p-12 text-center text-xs text-slate-500 border border-slate-200 dark:border-slate-800 rounded-xl bg-white dark:bg-slate-900">
              <div className="w-5 h-5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
              Loading evaluation results...
            </div>
          ) : evaluations.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl bg-white/40 dark:bg-slate-900/20">
              No evaluation results matching current filters.
            </div>
          ) : (
            <div className="space-y-2 max-h-[750px] overflow-y-auto pr-1">
              {evaluations.map((ev) => {
                const isSelected = selectedEvaluation?.evaluation_id === ev.evaluation_id;
                const vText = String(ev.verdict || 'PASS').toUpperCase();
                const vConfig = VERDICT_CONFIG[vText] || VERDICT_CONFIG.PASS;
                const VIcon = VERDICT_ICONS[vText] || CheckCircle2;
                const origin =
                  ev.collector_provenance?.actual_execution_origin ||
                  ev.actual_execution_origin ||
                  (ev.is_live_execution ? 'live_agent_run' : 'scripted_synthetic_demonstration');
                const pConfig = PROVENANCE_CONFIG[origin] || PROVENANCE_CONFIG.scripted_synthetic_demonstration;

                return (
                  <div
                    key={ev.evaluation_id}
                    onClick={() => selectEvaluation(ev)}
                    className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
                      isSelected
                        ? 'border-indigo-600 dark:border-indigo-500 bg-indigo-50/40 dark:bg-indigo-950/20 shadow-xs'
                        : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-slate-300 dark:hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border flex items-center gap-1 ${vConfig.bg}`}>
                        <VIcon className="w-3 h-3" />
                        <span>{vConfig.badgeText}</span>
                      </span>
                      <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${pConfig.badge}`}>
                        {pConfig.label}
                      </span>
                    </div>

                    <div className="mt-2 space-y-1">
                      <div className="text-xs font-bold font-mono text-slate-900 dark:text-white truncate">
                        {ev.test_id}
                      </div>
                      <div className="text-[10px] text-slate-500 flex items-center justify-between font-mono">
                        <span>Run: {ev.run_id}</span>
                        <span>{Number(ev.evaluator_timing_ms || 0).toFixed(1)} ms</span>
                      </div>
                    </div>

                    {/* Reasons snippet */}
                    {ev.reasons?.length > 0 && (
                      <p className="mt-1.5 text-[11px] text-slate-600 dark:text-slate-400 line-clamp-1 italic">
                        "{ev.reasons[0]}"
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Column: Active Evaluation Inspection Details (7 cols) */}
        <div className="lg:col-span-8 space-y-4">
          {selectedEvaluation ? (
            <>
              {/* Top Inspection Summary & Actions Bar */}
              <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-xl border ${verdictConfig ? verdictConfig.bg : 'bg-slate-100'}`}>
                      {VerdictIcon && <VerdictIcon className="w-5 h-5" />}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-bold text-slate-900 dark:text-white font-mono">
                          {selectedEvaluation.test_id}
                        </h3>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${verdictConfig ? verdictConfig.bg : ''}`}>
                          {selectedEvaluation.verdict}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-500 mt-0.5 font-mono">
                        Evaluation ID: {selectedEvaluation.evaluation_id} • Suite: {selectedEvaluation.suite_id || 'demonstration'}
                      </p>
                    </div>
                  </div>

                  {/* Top Action Buttons: Re-evaluate, Verify Reproduction, View Report */}
                  <div className="flex items-center gap-2 self-start sm:self-auto">
                    <button
                      type="button"
                      disabled={isReEvaluating}
                      onClick={() => reEvaluate(selectedEvaluation.evaluation_id)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-medium transition-colors"
                      title="Reproduce evaluation from retained evidence (does not re-execute agent)"
                    >
                      <RotateCw className={`w-3.5 h-3.5 ${isReEvaluating ? 'animate-spin' : ''}`} />
                      <span>Re-Evaluate</span>
                    </button>

                    <button
                      type="button"
                      disabled={isReEvaluating}
                      onClick={() => verifyReproduction(selectedEvaluation.evaluation_id)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-indigo-200 dark:border-indigo-800 bg-indigo-50/50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 text-xs font-medium hover:bg-indigo-100 transition-colors"
                      title="Independently verify deterministic replay reproduction against evidence digest"
                    >
                      <CheckCheck className="w-3.5 h-3.5" />
                      <span>Verify Reproduction</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setShowReportModal(true)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-xs transition-colors"
                      title="Inspect and export full structured C2 report contribution"
                    >
                      <FileText className="w-3.5 h-3.5" />
                      <span>C2 Report</span>
                    </button>
                  </div>
                </div>

                {/* Reproduction result banner if verified */}
                {reproductionResult && (
                  <div className="p-3 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-900 text-xs text-indigo-900 dark:text-indigo-200 flex items-start gap-2">
                    <CheckCheck className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-bold">Independent Replay Reproduction Verified: </span>
                      {reproductionResult.is_reproducible
                        ? 'Deterministic replay evaluation produced identical semantic outcome and verdict.'
                        : 'Replay divergence detected during evaluation reproduction.'}
                      <div className="text-[10px] font-mono text-indigo-700 dark:text-indigo-300 mt-0.5">
                        Digest: {reproductionResult.evidence_digest}
                      </div>
                    </div>
                  </div>
                )}

                {/* Reasons List */}
                {selectedEvaluation.reasons?.length > 0 && (
                  <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900/60 border border-slate-100 dark:border-slate-800 text-xs space-y-1">
                    <span className="font-semibold text-slate-500 uppercase text-[10px]">
                      Verdict Rationale:
                    </span>
                    <ul className="list-disc pl-5 space-y-0.5 text-slate-800 dark:text-slate-200">
                      {selectedEvaluation.reasons.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* View Tabs: Evidence vs Coverage */}
                <div className="flex items-center gap-2 pt-2 border-t border-slate-100 dark:border-slate-800 text-xs">
                  <button
                    type="button"
                    onClick={() => setActiveViewTab('evidence')}
                    className={`px-3 py-1.5 font-semibold rounded-lg transition-colors ${
                      activeViewTab === 'evidence'
                        ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'
                        : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                    }`}
                  >
                    Expected & Observed Evidence
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveViewTab('coverage')}
                    className={`px-3 py-1.5 font-semibold rounded-lg transition-colors ${
                      activeViewTab === 'coverage'
                        ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'
                        : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                    }`}
                  >
                    Observed Coverage Metrics
                  </button>
                </div>
              </div>

              {/* Sub-view: Evidence or Coverage */}
              {activeViewTab === 'evidence' ? (
                <WorkflowEvidenceViewer
                  evaluation={selectedEvaluation}
                  evidence={retainedEvidence}
                  isLoadingEvidence={isLoadingEvidence}
                  plannedCase={plannedCase}
                />
              ) : (
                <ObservedCoverageViewer
                  coverage={observedCoverage}
                  modelId={selectedEvaluation.model_id}
                  modelVersion={selectedEvaluation.model_version}
                />
              )}
            </>
          ) : (
            <div className="p-12 text-center text-xs text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl bg-white/40 dark:bg-slate-900/20">
              Select an evaluation on the left to inspect detailed workflow evidence, first divergence, and observed coverage.
            </div>
          )}
        </div>
      </div>

      {/* C2 Report Contribution Modal */}
      <RunReportModal
        isOpen={showReportModal}
        onClose={() => setShowReportModal(false)}
        report={runReport || selectedEvaluation}
        exportStatus={exportStatus}
        exportError={exportError}
        lastConfirmedReceipt={lastConfirmedReceipt}
        onExportReport={exportReport}
        isExporting={isExportingReport}
      />
    </div>
  );
};
