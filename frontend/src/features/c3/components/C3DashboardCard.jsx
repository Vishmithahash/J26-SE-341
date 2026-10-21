import React from 'react';
import { Link } from 'react-router-dom';
import {
  RotateCcw,
  ExternalLink,
  FolderGit2,
  AlertTriangle,
  Sparkles,
  GitCompare,
  Workflow,
} from 'lucide-react';
import { useProject } from '../../../context/ProjectContext';
import { useC3ProjectSuites } from '../hooks/useC3ProjectSuites';
import { useC3Executions } from '../hooks/useC3Executions';
import { useC3MatchedPairs } from '../hooks/useC3MatchedPairs';
import { useC3Evaluations } from '../hooks/useC3Evaluations';
import { C3Badge } from './C3Badge';

export const C3DashboardCard = ({ role = 'USER' }) => {
  const { activeProject, activeProjectId, isLoadingActive } = useProject();
  const {
    totalSuites,
    isLoading: isLoadingSuites,
    error: suiteError,
    isDbUnavailable: isSuiteDbUnavailable,
  } = useC3ProjectSuites(activeProjectId);

  const {
    latestExecution,
    isLoading: isLoadingExec,
    isDbUnavailable: isExecDbUnavailable,
  } = useC3Executions(activeProjectId);

  const {
    totalPairs,
    exposureCounts,
    isDbUnavailable: isPairsDbUnavailable,
  } = useC3MatchedPairs(activeProjectId);

  const {
    verdictCounts,
    isDbUnavailable: isEvalDbUnavailable,
  } = useC3Evaluations(activeProjectId);

  const isDbOffline =
    isSuiteDbUnavailable || isExecDbUnavailable || isPairsDbUnavailable || isEvalDbUnavailable;

  const isAdmin = role === 'ADMIN';
  const basePath = isAdmin ? '/admin/robustness-recovery' : '/app/robustness-recovery';

  return (
    <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
      <div>
        {/* Top bar with Icon and Status Pill */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 shrink-0">
            <RotateCcw className="w-5 h-5" />
          </div>
          <div className="flex items-center gap-1.5 flex-wrap">
            <C3Badge status="READY" label="Operational" />
            {isAdmin && (
              <span className="text-[10px] font-semibold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/40 px-2 py-0.5 rounded border border-indigo-200 dark:border-indigo-800">
                Admin View
              </span>
            )}
          </div>
        </div>

        {/* Full Title */}
        <h3 className="text-sm font-bold text-slate-900 dark:text-white leading-snug">
          Robustness and Failure Recovery Testing
        </h3>

        {/* Project Scope Section */}
        <div className="mt-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 text-xs">
          {isLoadingActive ? (
            <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded animate-pulse w-32" />
          ) : activeProject ? (
            <div>
              <div className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
                <FolderGit2 className="w-3.5 h-3.5 text-indigo-500" />
                <span className="font-semibold text-[11px] uppercase tracking-wider">
                  {isAdmin ? 'Selected Project Scope' : 'Active Project'}
                </span>
              </div>
              <div className="font-bold text-slate-900 dark:text-white mt-0.5 truncate">
                {activeProject.name}
              </div>
              <code className="text-[10px] text-slate-400 font-mono block truncate">
                ID: {activeProjectId}
              </code>
              {isAdmin && (
                <p className="text-[10px] text-slate-400 mt-1 italic leading-tight">
                  Scope: Authorized project records. Cross-project aggregate APIs absent; displaying scoped project summary.
                </p>
              )}
            </div>
          ) : (
            <div className="flex items-start gap-2 text-amber-700 dark:text-amber-400">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold">No project selected</span>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                  Link an authorized project to inspect suites, matched trials, and exposure.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Primary Metrics: Suites and Latest Execution */}
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/30 border border-slate-100 dark:border-slate-800">
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
              Stored Suites
            </span>
            <div className="text-base font-bold text-slate-900 dark:text-white mt-0.5">
              {!activeProjectId ? (
                <span className="text-xs font-normal text-slate-400">Project required</span>
              ) : isLoadingSuites ? (
                <div className="h-5 w-8 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
              ) : isDbOffline ? (
                <span className="text-xs font-medium text-amber-600 dark:text-amber-400">
                  Unavailable (DB Offline)
                </span>
              ) : suiteError ? (
                <span className="text-xs font-medium text-rose-500">Error</span>
              ) : totalSuites !== null ? (
                totalSuites
              ) : (
                <span className="text-xs font-normal text-slate-400">0</span>
              )}
            </div>
          </div>

          <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/30 border border-slate-100 dark:border-slate-800">
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
              Latest Execution
            </span>
            <div className="mt-0.5">
              {!activeProjectId ? (
                <span className="text-xs font-normal text-slate-400">Project required</span>
              ) : isLoadingExec ? (
                <div className="h-5 w-16 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
              ) : latestExecution ? (
                <div className="flex items-center gap-1.5 flex-wrap">
                  <C3Badge status={latestExecution.status} />
                  <span className="text-[10px] text-slate-400 font-mono">
                    {latestExecution.target_mode === 'LIVE_AUT' ? 'Live' : 'Demo'}
                  </span>
                </div>
              ) : (
                <span className="text-xs font-normal text-slate-400">None tracked</span>
              )}
            </div>
          </div>
        </div>

        {/* Phase 3 Recovery Verdict Breakdown for Active Project */}
        {activeProjectId && !isDbOffline && (
          <div className="mt-3 p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/30 border border-slate-100 dark:border-slate-800 text-xs space-y-1.5">
            <div className="flex items-center justify-between text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
              <span>Recovery Verdicts</span>
              <span>{verdictCounts.eligibleEvaluatedCount} Evaluated</span>
            </div>
            <div className="grid grid-cols-4 gap-1 pt-0.5 text-center">
              <div className="p-1 rounded bg-emerald-50/60 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-300">
                <span className="text-[9px] block">Completed</span>
                <span className="font-bold text-xs">{verdictCounts.passCompleted}</span>
              </div>
              <div className="p-1 rounded bg-sky-50/60 dark:bg-sky-950/20 text-sky-700 dark:text-sky-300">
                <span className="text-[9px] block">Graceful</span>
                <span className="font-bold text-xs">{verdictCounts.passGraceful}</span>
              </div>
              <div className="p-1 rounded bg-rose-50/60 dark:bg-rose-950/20 text-rose-700 dark:text-rose-300">
                <span className="text-[9px] block">Fail</span>
                <span className="font-bold text-xs">{verdictCounts.fail}</span>
              </div>
              <div className="p-1 rounded bg-amber-50/60 dark:bg-amber-950/20 text-amber-700 dark:text-amber-300">
                <span className="text-[9px] block">Inconc.</span>
                <span className="font-bold text-xs">{verdictCounts.inconclusive}</span>
              </div>
            </div>
            {verdictCounts.notEvaluated > 0 && (
              <span className="text-[10px] text-slate-400 block text-right">
                ({verdictCounts.notEvaluated} not evaluated / ineligible)
              </span>
            )}
          </div>
        )}

        {/* Phase 2 Exposure Breakdown for Active Project */}
        {activeProjectId && !isDbOffline && (
          <div className="mt-2 p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/30 border border-slate-100 dark:border-slate-800 text-xs space-y-1">
            <div className="flex items-center justify-between text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
              <span>Exposure Outcomes</span>
              <span>{totalPairs !== null ? `${totalPairs} Pairs` : ''}</span>
            </div>
            <div className="grid grid-cols-3 gap-1 pt-0.5 text-center">
              <div className="p-1 rounded bg-emerald-50/60 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-300">
                <span className="text-[9px] block">Confirmed</span>
                <span className="font-bold text-xs">{exposureCounts.confirmed}</span>
              </div>
              <div className="p-1 rounded bg-amber-50/60 dark:bg-amber-950/20 text-amber-700 dark:text-amber-300">
                <span className="text-[9px] block">Unreached</span>
                <span className="font-bold text-xs">{exposureCounts.notTriggered}</span>
              </div>
              <div className="p-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                <span className="text-[9px] block">Unknown</span>
                <span className="font-bold text-xs">{exposureCounts.unknown}</span>
              </div>
            </div>
          </div>
        )}

        {/* Concise Readiness Message */}
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-3 leading-relaxed">
          Robustness & recovery testing active. Deterministic recovery evaluation, explainable causal findings, C2 facts and reports connected.
        </p>
      </div>

      {/* Action Links */}
      <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs flex-wrap gap-2">
        <div className="flex items-center gap-3 flex-wrap">
          <Link
            to={`${basePath}#prepare`}
            className="inline-flex items-center gap-1 font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Prepare Cases</span>
          </Link>
          <Link
            to={`${basePath}#trials`}
            className="inline-flex items-center gap-1 font-semibold text-teal-600 dark:text-teal-400 hover:underline"
          >
            <GitCompare className="w-3.5 h-3.5" />
            <span>Trials</span>
          </Link>
          <Link
            to={`${basePath}#results`}
            className="inline-flex items-center gap-1 font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
          >
            <Workflow className="w-3.5 h-3.5" />
            <span>Results & Reports</span>
          </Link>
        </div>

        <Link
          to={basePath}
          className="inline-flex items-center gap-1 font-semibold text-slate-700 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-400"
        >
          <span>Open Workspace</span>
          <ExternalLink className="w-3.5 h-3.5" />
        </Link>
      </div>
    </div>
  );
};


