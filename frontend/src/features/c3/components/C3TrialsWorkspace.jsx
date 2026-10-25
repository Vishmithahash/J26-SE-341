import React, { useEffect, useState } from 'react';
import { c3Api } from '../api';
import {
  GitCompare,
  UploadCloud,
  FileSpreadsheet,
  Cpu,
  Layers,
  Info,
  RefreshCw,
} from 'lucide-react';
import { useC3MatchedPairs } from '../hooks/useC3MatchedPairs';
import { useC3Executions } from '../hooks/useC3Executions';
import { C3MatchedPairsViewer } from './C3MatchedPairsViewer';
import { C3RuntimeReadinessAudit } from './C3RuntimeReadinessAudit';
import { C3EvidenceImportModal } from './C3EvidenceImportModal';
import { C3ExecutionReportViewer } from './C3ExecutionReportViewer';
import { C3Badge } from './C3Badge';
import {
  DEMO_MATCHED_PAIR_EVIDENCE,
  DEMO_MATCHED_PAIR_NOT_TRIGGERED,
  DEMO_MATCHED_PAIR_DISQUALIFIED_CLEAN,
  DEMO_TRACKED_EXECUTION,
} from '../fixtures';

export const C3TrialsWorkspace = ({
  projectId,
  candidateCase,
  adapterManifest,
  taskFixtureMetadata,
  recoveryContract,
}) => {
  const [activeTab, setActiveTab] = useState('pairs'); // 'pairs' | 'executions' | 'readiness'
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [selectedExecutionId, setSelectedExecutionId] = useState(null);

  // Load project matched pairs
  const {
    pairs,
    totalPairs,
    exposureCounts,
    isLoading: isLoadingPairs,
    error: pairsError,
    isDbUnavailable: isPairsDbUnavailable,
    refreshPairs,
  } = useC3MatchedPairs(projectId);

  // Load project tracked executions
  const {
    executions,
    totalExecutions,
    isLoading: isLoadingExecutions,
    error: executionsError,
    isDbUnavailable: isExecDbUnavailable,
    refreshExecutions,
  } = useC3Executions(projectId);

  // Stored recovery evaluations (server-computed), keyed by pair. Latest first from the API.
  const [verdictsByPair, setVerdictsByPair] = useState({});
  useEffect(() => {
    if (!projectId) return undefined;
    const controller = new AbortController();
    c3Api
      .listEvaluations(projectId, { limit: 200 }, controller.signal)
      .then((res) => {
        const map = {};
        (res.items || []).forEach((e) => {
          if (!(e.pair_id in map) && e.recovery_verdict) map[e.pair_id] = e.recovery_verdict;
        });
        setVerdictsByPair(map);
      })
      .catch(() => setVerdictsByPair({}));
    return () => controller.abort();
  }, [projectId, pairs]);

  // Fallback offline demonstration state (if DB unmigrated or empty)
  const [offlineDemoPairs, setOfflineDemoPairs] = useState(null);
  const [offlineDemoExecutions, setOfflineDemoExecutions] = useState(null);

  const displayPairs = offlineDemoPairs || pairs;
  const displayExecutions = offlineDemoExecutions || executions;

  const handleLoadOfflineDemo = () => {
    setOfflineDemoPairs([
      DEMO_MATCHED_PAIR_EVIDENCE,
      DEMO_MATCHED_PAIR_NOT_TRIGGERED,
      DEMO_MATCHED_PAIR_DISQUALIFIED_CLEAN,
    ]);
    setOfflineDemoExecutions([DEMO_TRACKED_EXECUTION]);
  };

  const handleImportSuccess = () => {
    refreshPairs();
    refreshExecutions();
    setIsImportModalOpen(false);
  };

  return (
    <div className="space-y-6">
      {/* Top Controls & Navigation */}
      <div className="flex items-center justify-between gap-4 flex-wrap bg-white dark:bg-slate-900 p-4 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
        {/* Tabs */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              setActiveTab('pairs');
              setSelectedExecutionId(null);
            }}
            className={`px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-colors ${
              activeTab === 'pairs'
                ? 'bg-indigo-600 text-white shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            <GitCompare className="w-3.5 h-3.5" />
            <span>1. Matched Trial Pairs</span>
            {totalPairs !== null && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-indigo-500/30 text-white">
                {totalPairs}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('executions')}
            className={`px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-colors ${
              activeTab === 'executions'
                ? 'bg-indigo-600 text-white shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>2. Tracked Executions</span>
            {totalExecutions !== null && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-indigo-500/30 text-white">
                {totalExecutions}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveTab('readiness');
              setSelectedExecutionId(null);
            }}
            className={`px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-colors ${
              activeTab === 'readiness'
                ? 'bg-indigo-600 text-white shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            <span>3. Runtime Readiness & CLI</span>
          </button>
        </div>

        {/* Action Button: Import Evidence */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setIsImportModalOpen(true)}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white font-semibold text-xs transition-colors shadow-xs"
          >
            <UploadCloud className="w-3.5 h-3.5" />
            <span>Import Evidence</span>
          </button>
        </div>
      </div>

      {/* Tab 1: Matched Trial Pairs */}
      {activeTab === 'pairs' && (
        <div className="space-y-4">
          {/* Quick Metrics Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                Total Pairs
              </span>
              <div className="text-lg font-bold text-slate-900 dark:text-white mt-0.5">
                {displayPairs.length}
              </div>
            </div>

            <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
              <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider block">
                Confirmed Exposure
              </span>
              <div className="text-lg font-bold text-emerald-600 dark:text-emerald-400 mt-0.5">
                {exposureCounts.confirmed}
              </div>
            </div>

            <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
              <span className="text-[10px] font-semibold text-amber-600 dark:text-amber-400 uppercase tracking-wider block">
                Not Triggered (Unreached)
              </span>
              <div className="text-lg font-bold text-amber-600 dark:text-amber-400 mt-0.5">
                {exposureCounts.notTriggered}
              </div>
            </div>

            <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
              <span className="text-[10px] font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider block">
                Qualified Controls
              </span>
              <div className="text-lg font-bold text-indigo-600 dark:text-indigo-400 mt-0.5">
                {exposureCounts.cleanQualified}
              </div>
            </div>
          </div>

          <C3MatchedPairsViewer
            pairs={displayPairs}
            totalPairs={totalPairs}
            isLoading={isLoadingPairs}
            error={pairsError}
            isDbUnavailable={isPairsDbUnavailable}
            onRefresh={refreshPairs}
            onLoadOfflineDemo={handleLoadOfflineDemo}
            verdictsByPair={offlineDemoPairs ? {} : verdictsByPair}
          />
        </div>
      )}

      {/* Tab 2: Tracked Executions */}
      {activeTab === 'executions' && (
        <div className="space-y-4">
          {selectedExecutionId ? (
            <C3ExecutionReportViewer
              projectId={projectId}
              executionId={selectedExecutionId}
              onClose={() => setSelectedExecutionId(null)}
            />
          ) : (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-sm">
              <div className="p-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
                <h3 className="text-xs font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <Layers className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                  <span>Tracked Frozen Suite Executions</span>
                </h3>
                {refreshExecutions && (
                  <button
                    type="button"
                    onClick={refreshExecutions}
                    disabled={isLoadingExecutions}
                    className="p-1 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300"
                    title="Refresh executions"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isLoadingExecutions ? 'animate-spin' : ''}`} />
                  </button>
                )}
              </div>

              {isLoadingExecutions ? (
                <div className="p-8 text-center space-y-3">
                  <RefreshCw className="w-6 h-6 animate-spin mx-auto text-indigo-500" />
                  <p className="text-xs text-slate-500">Loading tracked executions...</p>
                </div>
              ) : executionsError ? (
                <div className="p-6 text-center space-y-3">
                  <Info className="w-6 h-6 mx-auto text-amber-500" />
                  <div className="text-xs text-slate-500">
                    <span className="font-semibold block text-slate-900 dark:text-white">
                      {isExecDbUnavailable ? 'Database Offline (HTTP 503)' : 'No Tracked Executions'}
                    </span>
                    <p className="mt-1">{executionsError}</p>
                  </div>
                  <button
                    type="button"
                    onClick={handleLoadOfflineDemo}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800 text-xs font-semibold hover:bg-indigo-100"
                  >
                    <span>Inspect Sample Demonstration Execution</span>
                  </button>
                </div>
              ) : displayExecutions.length === 0 ? (
                <div className="p-8 text-center space-y-3">
                  <Layers className="w-8 h-8 text-slate-300 dark:text-slate-700 mx-auto" />
                  <div className="text-xs text-slate-500">
                    <span className="font-bold text-slate-700 dark:text-slate-300 block">
                      No tracked suite executions in this project
                    </span>
                    <p className="mt-0.5">
                      Run <code className="font-mono">suite_runner.py</code> locally or import execution artifacts.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={handleLoadOfflineDemo}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800 text-xs font-semibold hover:bg-indigo-100"
                  >
                    <span>Load Demonstration Execution</span>
                  </button>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-500 font-semibold">
                      <tr>
                        <th className="py-3 px-4">Execution ID & Suite</th>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4">Target Mode</th>
                        <th className="py-3 px-4">Cases Breakdown</th>
                        <th className="py-3 px-4 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {displayExecutions.map((exec) => (
                        <tr
                          key={exec.execution_id}
                          className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors"
                        >
                          <td className="py-3 px-4">
                            <div className="font-mono font-bold text-slate-900 dark:text-white">
                              {exec.execution_id}
                            </div>
                            <div className="text-[10px] text-slate-400 font-mono truncate max-w-xs">
                              Suite Digest: {exec.suite_digest?.slice(0, 16)}...
                            </div>
                          </td>

                          <td className="py-3 px-4">
                            <C3Badge status={exec.status} />
                          </td>

                          <td className="py-3 px-4">
                            <C3Badge status={exec.target_mode || 'DEMONSTRATION'} />
                          </td>

                          <td className="py-3 px-4">
                            <div className="text-[11px] font-mono text-slate-700 dark:text-slate-300">
                              Planned: {exec.planned_cases_count} | Executed: {exec.executed_cases_count}
                            </div>
                          </td>

                          <td className="py-3 px-4 text-right">
                            <button
                              type="button"
                              onClick={() => setSelectedExecutionId(exec.execution_id)}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800 text-xs font-semibold hover:bg-indigo-100 transition-colors"
                            >
                              <FileSpreadsheet className="w-3.5 h-3.5" />
                              <span>View Report</span>
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Runtime Readiness & CLI */}
      {activeTab === 'readiness' && (
        <C3RuntimeReadinessAudit
          projectId={projectId}
          candidateCase={candidateCase}
          adapterManifest={adapterManifest}
          taskFixtureMetadata={taskFixtureMetadata}
          recoveryContract={recoveryContract}
        />
      )}

      {/* Evidence Import Modal */}
      <C3EvidenceImportModal
        isOpen={isImportModalOpen}
        onClose={() => setIsImportModalOpen(false)}
        projectId={projectId}
        onImportSuccess={handleImportSuccess}
      />
    </div>
  );
};
