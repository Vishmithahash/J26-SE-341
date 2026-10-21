/**
 * Component 4 (C4) - Execution Runs and Independent Outcome Dimensions Section
 * Displays trial execution history and strictly disentangled evaluation outcome dimensions.
 */

import React, { useState } from 'react';
import {
  PlayCircle,
  RotateCw,
  Info,
  Activity,
  Download,
  Layers,
} from 'lucide-react';
import {
  POLICY_VERDICTS,
  EXPOSURE_STATUSES,
} from '../../api/types.js';

export function ExecutionRunsSection({
  runsList,
  activeRun,
  onSelectRun,
  onRefreshRuns,
  isLoadingRuns,
  onOpenFindingModal,
  onOpenExportModal,
}) {
  const [selectedRunId, setSelectedRunId] = useState(activeRun?.run_id || runsList[0]?.run_id || null);

  const currentRun = runsList.find((r) => r.run_id === selectedRunId) || activeRun || runsList[0];

  const getVerdictBadge = (verdict) => {
    switch (verdict) {
      case POLICY_VERDICTS.PASS:
        return 'bg-emerald-100 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800';
      case POLICY_VERDICTS.FAIL:
        return 'bg-rose-100 dark:bg-rose-950/80 text-rose-700 dark:text-rose-300 border-rose-300 dark:border-rose-800';
      case POLICY_VERDICTS.INCONCLUSIVE:
        return 'bg-amber-100 dark:bg-amber-950/80 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-800';
      case POLICY_VERDICTS.NOT_EXERCISED:
      default:
        return 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-300 dark:border-slate-700';
    }
  };

  const getExposureBadge = (exp) => {
    switch (exp) {
      case EXPOSURE_STATUSES.EXPOSED:
        return 'bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800';
      case EXPOSURE_STATUSES.NOT_EXPOSED:
        return 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700';
      case EXPOSURE_STATUSES.NOT_APPLICABLE:
        return 'bg-slate-50 dark:bg-slate-800/40 text-slate-500 border-slate-200/60';
      case EXPOSURE_STATUSES.UNKNOWN:
      default:
        return 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border-amber-200';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded-lg bg-indigo-100 dark:bg-indigo-950/70 text-indigo-600 dark:text-indigo-400 font-bold text-xs flex items-center justify-center">
              3
            </span>
            <h3 className="text-base font-bold text-slate-900 dark:text-white">
              Controlled Execution Runs ({runsList.length})
            </h3>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Independent evaluation dimensions disentangle execution status, injection exposure, policy verdict, attacker objective, task utility, and cleanup.
          </p>
        </div>

        {onRefreshRuns && (
          <button
            type="button"
            onClick={onRefreshRuns}
            disabled={isLoadingRuns}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isLoadingRuns ? 'animate-spin text-indigo-600' : ''}`} />
            <span>Refresh Runs</span>
          </button>
        )}
      </div>

      {runsList.length === 0 ? (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-10 text-center space-y-3">
          <PlayCircle className="w-10 h-10 text-slate-300 dark:text-slate-700 mx-auto" />
          <h4 className="text-sm font-bold text-slate-700 dark:text-slate-300">
            No execution runs recorded yet
          </h4>
          <p className="text-xs text-slate-500 dark:text-slate-400 max-w-md mx-auto">
            Switch to the <strong>Test Cases</strong> tab, freeze a validated policy test case snapshot, and click <strong>Execute Test</strong> to run a controlled trial.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Runs History List */}
          <div className="space-y-3 lg:col-span-1">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Run History
            </span>

            <div className="space-y-2 max-h-[680px] overflow-y-auto pr-1">
              {runsList.map((run) => {
                const isSelected = run.run_id === currentRun?.run_id;
                return (
                  <button
                    key={run.run_id}
                    type="button"
                    onClick={() => {
                      setSelectedRunId(run.run_id);
                      if (onSelectRun) onSelectRun(run);
                    }}
                    className={`w-full p-3.5 rounded-xl border text-left transition-all cursor-pointer ${
                      isSelected
                        ? 'border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/40 ring-1 ring-indigo-500/20'
                        : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-slate-300 dark:hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border uppercase tracking-wider ${getVerdictBadge(run.policy_verdict)}`}>
                        {run.policy_verdict}
                      </span>
                      <span className="text-[10px] font-mono text-slate-400">
                        {run.execution_mode}
                      </span>
                    </div>

                    <p className="text-xs font-bold text-slate-900 dark:text-white font-mono truncate">
                      {run.case_id}
                    </p>

                    <div className="flex items-center justify-between text-[11px] text-slate-400 mt-2 font-mono">
                      <span>Status: {run.status}</span>
                      <span>{new Date(run.created_at).toLocaleTimeString()}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right Column: Deep Inspector for the 6 Independent Outcome Dimensions */}
          {currentRun && (
            <div className="lg:col-span-2 space-y-5">
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-6">
                {/* Header & Lineage */}
                <div className="pb-4 border-b border-slate-100 dark:border-slate-800">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 px-2 py-0.5 rounded">
                      Execution Trial Analysis
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-slate-400">
                        Run ID: {currentRun.run_id}
                      </span>
                      {onOpenExportModal && (
                        <button
                          type="button"
                          onClick={() => onOpenExportModal(currentRun)}
                          className="px-2.5 py-1 rounded-lg bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-950/60 dark:hover:bg-indigo-900/60 text-indigo-600 dark:text-indigo-400 text-xs font-semibold border border-indigo-200 dark:border-indigo-800 transition-colors flex items-center gap-1"
                        >
                          <Download className="w-3.5 h-3.5" />
                          <span>Export Report</span>
                        </button>
                      )}
                    </div>
                  </div>

                  <h4 className="text-base font-bold text-slate-900 dark:text-white font-mono mt-1">
                    Case: {currentRun.case_id} (v{currentRun.case_version})
                  </h4>

                  <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500 font-mono mt-1">
                    <span>Adapter: {currentRun.adapter_id} ({currentRun.execution_mode})</span>
                    <span>•</span>
                    <span>Behavior: {currentRun.simulated_behavior || 'N/A'}</span>
                  </div>
                </div>

                {/* THE SIX INDEPENDENT OUTCOME DIMENSIONS */}
                <div>
                  <h5 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-3 flex items-center gap-1.5">
                    <Activity className="w-4 h-4 text-indigo-500" />
                    Six Independent Outcome Dimensions
                  </h5>

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {/* Dimension 1: Policy Verdict */}
                    <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-700/70 space-y-1">
                      <span className="text-[10px] font-bold uppercase text-slate-400 tracking-wider">
                        1. Policy Verdict
                      </span>
                      <p className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                        <span className={`px-2 py-0.5 rounded text-xs border ${getVerdictBadge(currentRun.policy_verdict)}`}>
                          {currentRun.policy_verdict}
                        </span>
                      </p>
                      <p className="text-[10px] text-slate-400 leading-tight pt-0.5">
                        Invariant compliance under accepted contract.
                      </p>
                    </div>

                    {/* Dimension 2: Injection Exposure */}
                    <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-700/70 space-y-1">
                      <span className="text-[10px] font-bold uppercase text-slate-400 tracking-wider">
                        2. Injection Exposure
                      </span>
                      <p className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                        <span className={`px-2 py-0.5 rounded text-xs border ${getExposureBadge(currentRun.exposure_status)}`}>
                          {currentRun.exposure_status}
                        </span>
                      </p>
                      <p className="text-[10px] text-slate-400 leading-tight pt-0.5">
                        Unretrieved source does not prove resistance.
                      </p>
                    </div>

                    {/* Dimension 3: Attacker Objective Outcome */}
                    <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-700/70 space-y-1">
                      <span className="text-[10px] font-bold uppercase text-slate-400 tracking-wider">
                        3. Attacker Objective
                      </span>
                      <p className="text-xs font-bold text-slate-900 dark:text-white">
                        Overall: <span className="font-mono text-indigo-600 dark:text-indigo-400">{currentRun.attacker_objective_outcome}</span>
                      </p>
                      <div className="text-[10px] text-slate-500 font-mono space-y-0.5 pt-0.5">
                        <div>Attempt: {currentRun.attempt_goal_outcome}</div>
                        <div>Commit: {currentRun.commit_goal_outcome}</div>
                      </div>
                    </div>

                    {/* Dimension 4: Legitimate Task Utility */}
                    <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-700/70 space-y-1">
                      <span className="text-[10px] font-bold uppercase text-slate-400 tracking-wider">
                        4. Legitimate Task Utility
                      </span>
                      <p className="text-sm font-bold text-slate-900 dark:text-white font-mono">
                        {currentRun.task_utility_outcome}
                      </p>
                      <p className="text-[10px] text-slate-400 leading-tight pt-0.5">
                        Benign task utility assessed separately from safety.
                      </p>
                    </div>

                    {/* Dimension 5: Execution Status */}
                    <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-700/70 space-y-1">
                      <span className="text-[10px] font-bold uppercase text-slate-400 tracking-wider">
                        5. Execution Status
                      </span>
                      <p className="text-sm font-bold text-slate-900 dark:text-white font-mono">
                        {currentRun.status}
                      </p>
                      <p className="text-[10px] text-slate-400 leading-tight pt-0.5">
                        Invocation and harness pipeline lifecycle.
                      </p>
                    </div>

                    {/* Dimension 6: Post-Trial Cleanup Status */}
                    <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-700/70 space-y-1">
                      <span className="text-[10px] font-bold uppercase text-slate-400 tracking-wider">
                        6. Fixture Cleanup Status
                      </span>
                      <p className="text-sm font-bold text-slate-900 dark:text-white font-mono">
                        {currentRun.cleanup_status}
                      </p>
                      <p className="text-[10px] text-slate-400 leading-tight pt-0.5">
                        Preserves trial findings even if cleanup fails.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Targeted Injection Verdict vs Overall Policy Notice */}
                {currentRun.injection_target_verdict && (
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/60 text-xs flex items-center justify-between">
                    <span className="font-semibold text-slate-700 dark:text-slate-300">
                      Targeted Injection Invariant Verdict:
                    </span>
                    <span className={`px-2.5 py-0.5 rounded text-xs font-bold border ${getVerdictBadge(currentRun.injection_target_verdict)}`}>
                      {currentRun.injection_target_verdict}
                    </span>
                  </div>
                )}

                {/* Backend Rejection Notice */}
                {currentRun.backend_rejection_observed && (
                  <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-xs text-amber-900 dark:text-amber-200 flex items-start gap-2">
                    <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-bold">Backend Domain Rejection Observed: </span>
                      The target domain rejected the attempted action. (Note: an application-level rejection does NOT erase an attempted-action violation when policy explicitly forbids the agent from even attempting the action).
                    </div>
                  </div>
                )}

                {/* Pre-Cleanup Effects (Preserved on Cleanup Failure) */}
                {currentRun.pre_cleanup_effects?.length > 0 && (
                  <div className="space-y-2">
                    <span className="text-xs font-bold text-slate-700 dark:text-slate-300">
                      Preserved Pre-Cleanup Effects ({currentRun.pre_cleanup_effects.length})
                    </span>
                    <pre className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-[11px] font-mono text-slate-700 dark:text-slate-300 overflow-x-auto">
                      {JSON.stringify(currentRun.pre_cleanup_effects, null, 2)}
                    </pre>
                  </div>
                )}

                {/* Findings List */}
                {currentRun.findings?.length > 0 && (
                  <div className="space-y-2">
                    <span className="text-xs font-bold text-slate-700 dark:text-slate-300">
                      Policy Findings & Invariant Violations ({currentRun.findings.length})
                    </span>
                    <div className="space-y-2">
                      {currentRun.findings.map((f, i) => (
                        <div
                          key={i}
                          className="p-3.5 rounded-xl bg-rose-50/50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900 text-xs space-y-2"
                        >
                          <div className="flex items-center justify-between font-bold text-rose-900 dark:text-rose-200">
                            <span>Finding: {f.rule_id || f.finding_type || 'INVARIANT_VIOLATION'}</span>
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-[10px]">{f.severity || 'HIGH'}</span>
                              {onOpenFindingModal && (
                                <button
                                  type="button"
                                  onClick={() => onOpenFindingModal(f, currentRun)}
                                  className="px-2 py-0.5 rounded bg-rose-200/80 hover:bg-rose-300 dark:bg-rose-900/60 dark:hover:bg-rose-800 text-[10px] font-bold text-rose-950 dark:text-rose-100 transition-colors"
                                >
                                  Inspect Evidence Chain
                                </button>
                              )}
                            </div>
                          </div>
                          <p className="text-rose-800 dark:text-rose-300 text-[11px]">
                            {f.description || f.message || f.explanation}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Inspect Run Evidence Chain Trigger */}
                {onOpenFindingModal && (!currentRun.findings || currentRun.findings.length === 0) && (
                  <div className="pt-2 flex justify-end">
                    <button
                      type="button"
                      onClick={() =>
                        onOpenFindingModal(
                          {
                            finding_id: `f-${currentRun.run_id}`,
                            rule_id: currentRun.case_id,
                            contract_id: currentRun.contract_id || 'contract-ecommerce-v1',
                            contract_version: currentRun.contract_version || 1,
                            rule_version: 1,
                            verdict: currentRun.policy_verdict || 'NOT_EXERCISED',
                            severity: 'HIGH',
                            violation_stage:
                              currentRun.attacker_objective_outcome === 'ACHIEVED'
                                ? 'COMPLETED_PROHIBITED_ACTION_OR_EFFECT'
                                : 'ATTEMPTED_PROHIBITED_ACTION',
                            explanation:
                              currentRun.evaluation_report_summary ||
                              'Evaluation summary based on retained evidence package.',
                            attack_outcome: currentRun.attacker_objective_outcome,
                            benign_utility: currentRun.task_utility_outcome,
                            observed_effect:
                              currentRun.pre_cleanup_effects?.length > 0
                                ? 'Pre-cleanup effects committed'
                                : 'No persistent state delta',
                            missing_evidence:
                              currentRun.exposure_status === 'UNKNOWN' ? ['Unobserved exposure event trace'] : [],
                          },
                          currentRun
                        )
                      }
                      className="px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-semibold transition-colors flex items-center gap-1.5"
                    >
                      <Layers className="w-3.5 h-3.5 text-indigo-500" />
                      <span>Inspect Complete Evidence Chain</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
