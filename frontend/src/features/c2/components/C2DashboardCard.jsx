import React from 'react';
import { Link } from 'react-router-dom';
import {
  Workflow,
  ExternalLink,
  ArrowRight,
  FolderKanban,
  RefreshCw,
  AlertTriangle,
  Clock,
  Layers,
  Sparkles,
} from 'lucide-react';
import { useAuth } from '../../../context/AuthContext';
import { useProject } from '../../../context/ProjectContext';
import { useC2Dashboard } from '../hooks/useC2Dashboard.js';
import { VERDICT_CONFIG, PROVENANCE_CONFIG } from '../constants/resultsConfig.js';

export const C2DashboardCard = ({ role, basePath }) => {
  const { user } = useAuth();
  const { activeProject, activeProjectId, isLoadingActive } = useProject();

  const effectiveRole = role || (String(user?.role || '').toUpperCase() === 'ADMIN' ? 'ADMIN' : 'USER');
  const workspacePath = basePath || (effectiveRole === 'ADMIN' ? '/admin/workflow-testing' : '/app/workflow-testing');
  const projectsPath = effectiveRole === 'ADMIN' ? '/admin/projects' : '/app/projects';

  const {
    modelsCount,
    uniqueModelsCount,
    approvedModelsCount,
    suitesCount,
    latestEvaluation,
    modelsError,
    suitesError,
    evaluationsError,
    isLoading,
    refresh,
    hasPartialErrors,
  } = useC2Dashboard(activeProjectId, user?.id);

  // Verdict config lookup
  const latestVerdict = latestEvaluation?.verdict ? String(latestEvaluation.verdict).toUpperCase() : null;
  const verdictStyle = latestVerdict && VERDICT_CONFIG[latestVerdict] ? VERDICT_CONFIG[latestVerdict] : null;

  // Provenance config lookup
  const rawOrigin =
    latestEvaluation?.actual_execution_origin ||
    latestEvaluation?.collector_provenance?.actual_execution_origin ||
    latestEvaluation?.execution_provenance?.actual_execution_origin ||
    null;
  const provenanceStyle = rawOrigin && PROVENANCE_CONFIG[rawOrigin] ? PROVENANCE_CONFIG[rawOrigin] : null;

  // Formatted date
  const latestDate = latestEvaluation?.evaluated_at || latestEvaluation?.created_at;
  const formattedLatestDate = latestDate
    ? new Date(latestDate).toLocaleString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    : null;

  return (
    <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
      <div>
        {/* Top Bar: Icon, Active Scope Badge, and Refresh */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 shrink-0">
            <Workflow className="w-5 h-5" />
          </div>

          <div className="flex items-center gap-2">
            {activeProject ? (
              <span
                className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800 truncate max-w-[150px]"
                title={`Active Project: ${activeProject.name}`}
              >
                {activeProject.name}
              </span>
            ) : (
              <span className="text-[10px] font-medium text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 px-2 py-0.5 rounded border border-amber-200 dark:border-amber-900/60">
                No Project
              </span>
            )}

            {activeProjectId && (
              <button
                type="button"
                onClick={refresh}
                disabled={isLoading}
                className="p-1 rounded-md text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors disabled:opacity-50"
                title="Refresh C2 summaries"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
              </button>
            )}
          </div>
        </div>

        {/* Title & Subtitle */}
        <h3 className="text-sm font-bold text-slate-900 dark:text-white leading-snug">
          State-Aware Multi-Step Workflow Testing
        </h3>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          Extended Finite State Machine (EFSM) Conformance
        </p>

        {/* Main Content Area */}
        <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800">
          {isLoadingActive ? (
            <div className="py-4 text-center text-xs text-slate-400 animate-pulse">
              Validating active project...
            </div>
          ) : !activeProject || !activeProjectId ? (
            <div className="py-2 space-y-2">
              <p className="text-xs text-slate-600 dark:text-slate-400">
                Select a project to view workflow testing.
              </p>
              <Link
                to={projectsPath}
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline pt-1"
              >
                <FolderKanban className="w-3.5 h-3.5" />
                <span>Go to Projects Workspace</span>
                <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          ) : isLoading ? (
            <div className="py-4 text-center text-xs text-slate-400 animate-pulse flex items-center justify-center gap-2">
              <div className="w-4 h-4 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
              <span>Loading C2 summaries...</span>
            </div>
          ) : (
            <div className="space-y-3">
              {/* Models & Suites Metric Chips */}
              <div className="grid grid-cols-2 gap-2 text-xs">
                {/* Workflow Models */}
                <div className="p-2 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
                  <div className="flex items-center gap-1.5 text-[11px] text-slate-500 dark:text-slate-400">
                    <Layers className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                    <span>Models</span>
                  </div>
                  <div className="mt-1 font-semibold text-slate-900 dark:text-white truncate">
                    {modelsError ? (
                      <span className="text-slate-400 font-normal italic">Unavailable</span>
                    ) : (
                      <>
                        <span>{uniqueModelsCount ?? 0}</span>
                        <span className="text-[10px] text-slate-400 font-normal ml-1">
                          ({modelsCount ?? 0} ver, {approvedModelsCount ?? 0} app)
                        </span>
                      </>
                    )}
                  </div>
                </div>

                {/* Test Suites */}
                <div className="p-2 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
                  <div className="flex items-center gap-1.5 text-[11px] text-slate-500 dark:text-slate-400">
                    <Sparkles className="w-3.5 h-3.5 text-purple-500 shrink-0" />
                    <span>Test Suites</span>
                  </div>
                  <div className="mt-1 font-semibold text-slate-900 dark:text-white truncate">
                    {suitesError ? (
                      <span className="text-slate-400 font-normal italic">Unavailable</span>
                    ) : (
                      <span>{suitesCount ?? 0} suites</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Latest Evaluation Section */}
              <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 text-xs">
                <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400 mb-1">
                  <span className="font-medium">Latest Evaluation:</span>
                  {formattedLatestDate && (
                    <span className="text-[10px] text-slate-400 flex items-center gap-1 font-mono">
                      <Clock className="w-3 h-3" />
                      {formattedLatestDate}
                    </span>
                  )}
                </div>

                {evaluationsError ? (
                  <p className="text-slate-400 font-normal italic">Unavailable</p>
                ) : !latestEvaluation ? (
                  <p className="text-slate-400 font-normal italic">No evaluations yet</p>
                ) : (
                  <div className="space-y-1.5 pt-0.5">
                    <div className="flex items-center justify-between gap-1 flex-wrap">
                      {verdictStyle ? (
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${verdictStyle.badge}`}>
                          {verdictStyle.badgeText}
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                          {latestEvaluation.verdict || 'UNKNOWN'}
                        </span>
                      )}

                      {provenanceStyle ? (
                        <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${provenanceStyle.badge}`}>
                          {provenanceStyle.label}
                        </span>
                      ) : (
                        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500 border border-slate-200 dark:border-slate-700">
                          {rawOrigin || 'Unknown Origin'}
                        </span>
                      )}
                    </div>

                    {latestEvaluation.test_id && (
                      <p className="text-[11px] font-mono text-slate-600 dark:text-slate-400 truncate">
                        Case: {latestEvaluation.test_id}
                      </p>
                    )}
                  </div>
                )}
              </div>

              {/* Partial Availability Notice */}
              {hasPartialErrors && (
                <div className="p-2 rounded-lg bg-amber-50/70 dark:bg-amber-950/30 border border-amber-200/60 dark:border-amber-900/40 text-[11px] text-amber-800 dark:text-amber-300 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 truncate">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                    <span className="truncate">Some metrics unavailable</span>
                  </div>
                  <button
                    type="button"
                    onClick={refresh}
                    className="font-semibold underline hover:no-underline shrink-0"
                  >
                    Retry
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Card Footer: Open Workspace Link */}
      <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800">
        <Link
          to={workspacePath}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
        >
          <span>Open Workspace</span>
          <ExternalLink className="w-3.5 h-3.5" />
        </Link>
      </div>
    </div>
  );
};
