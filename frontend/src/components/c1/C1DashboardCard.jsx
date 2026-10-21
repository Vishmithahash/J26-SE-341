import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
  ListChecks,
  ExternalLink,
  Layers,
  PlayCircle,
  AlertCircle,
  CheckCircle,
  XCircle,
  HelpCircle,
  Clock,
  ArrowRight,
  FolderOpen,
  RefreshCw,
  Wrench,
} from 'lucide-react';
import { useProject } from '../../context/ProjectContext';
import { useAuth } from '../../context/AuthContext';
import { c1Api } from './c1Api';
import { ExecutionProvenanceBadge } from './ExecutionProvenanceBadge';

export const C1DashboardCard = ({ role = 'USER' }) => {
  const { user } = useAuth();
  const { activeProjectId, activeProject } = useProject();

  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [suitesCount, setSuitesCount] = useState(null);
  const [runsCount, setRunsCount] = useState(null);
  const [latestRun, setLatestRun] = useState(null);
  const [latestRunDetail, setLatestRunDetail] = useState(null);

  // Guard against stale asynchronous responses when project changes
  const requestTokenRef = useRef(0);

  // Role-correct path configuration
  const isAdmin = (role || user?.role) === 'ADMIN';
  const workspacePath = isAdmin ? '/admin/tool-call-correctness' : '/app/tool-call-correctness';
  const projectsPath = isAdmin ? '/admin/projects' : '/app/projects';

  useEffect(() => {
    requestTokenRef.current += 1;
    const currentToken = requestTokenRef.current;

    setSuitesCount(null);
    setRunsCount(null);
    setLatestRun(null);
    setLatestRunDetail(null);
    setErrorMsg(null);

    if (!activeProjectId) {
      return;
    }

    const fetchSummary = async () => {
      setIsLoading(true);
      try {
        const [suitesRes, runsRes] = await Promise.all([
          c1Api.listSuites(activeProjectId).catch(() => []),
          c1Api.listRuns(activeProjectId, { limit: 10 }).catch(() => []),
        ]);

        if (currentToken !== requestTokenRef.current) return;

        const suites = Array.isArray(suitesRes) ? suitesRes : [];
        const runs = Array.isArray(runsRes) ? runsRes : [];

        setSuitesCount(suites.length);
        setRunsCount(runs.length);

        if (runs.length > 0) {
          const firstRun = runs[0];
          setLatestRun(firstRun);

          // Retrieve full detail for authoritative provenance inspection
          c1Api
            .getRunDetail(activeProjectId, firstRun.run_id)
            .then((detail) => {
              if (currentToken === requestTokenRef.current) {
                setLatestRunDetail(detail);
              }
            })
            .catch(() => {
              // Non-blocking; summary remains authoritative
            });
        }
      } catch (err) {
        if (currentToken === requestTokenRef.current) {
          setErrorMsg(err.message || 'Failed to load tool-call correctness metrics.');
        }
      } finally {
        if (currentToken === requestTokenRef.current) {
          setIsLoading(false);
        }
      }
    };

    fetchSummary();
  }, [activeProjectId]);

  return (
    <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
      <div>
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 shrink-0">
            <ListChecks className="w-5 h-5" />
          </div>
          <span className="text-[11px] font-semibold text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/50 px-2 py-0.5 rounded-md border border-indigo-200/50 dark:border-indigo-800/50">
            Component 1
          </span>
        </div>

        <h3 className="text-sm font-bold text-slate-900 dark:text-white leading-snug">
          Explainable Tool-Call Correctness Testing
        </h3>

        {/* Scope Header */}
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-slate-500 dark:text-slate-400">Scope:</span>
          {activeProjectId ? (
            <span className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 font-medium text-slate-800 dark:text-slate-200 truncate max-w-[200px]">
              {activeProject?.name || activeProjectId}
            </span>
          ) : (
            <span className="text-slate-400 italic">None selected</span>
          )}
          {isAdmin && activeProjectId && (
            <span className="text-[10px] text-slate-400 font-mono">
              (Single Project)
            </span>
          )}
        </div>

        {/* Body Content */}
        <div className="mt-3">
          {!activeProjectId ? (
            <div className="py-3 px-3 rounded-xl border border-dashed border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 text-xs text-slate-500 dark:text-slate-400 space-y-2">
              <p>No active project selected. Select a project to view suites, runs, and correctness results.</p>
              <Link
                to={projectsPath}
                className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
              >
                <span>Select Project</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          ) : isLoading ? (
            <div className="space-y-2.5 py-2">
              <div className="h-4 bg-slate-100 dark:bg-slate-800 rounded animate-pulse w-3/4" />
              <div className="h-8 bg-slate-100 dark:bg-slate-800 rounded-lg animate-pulse" />
              <div className="h-4 bg-slate-100 dark:bg-slate-800 rounded animate-pulse w-1/2" />
            </div>
          ) : errorMsg ? (
            <div className="py-2.5 px-3 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-xs text-red-700 dark:text-red-300 space-y-1">
              <div className="flex items-center gap-1.5 font-semibold">
                <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                <span>Unable to load metrics</span>
              </div>
              <p className="text-[11px] text-red-600 dark:text-red-400">{errorMsg}</p>
            </div>
          ) : latestRun ? (
            <div className="space-y-3">
              {/* Provenance Badge & Run Status */}
              <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                <ExecutionProvenanceBadge runOrCase={latestRunDetail || latestRun} compact />
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                    latestRun.status === 'COMPLETED'
                      ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                      : latestRun.status === 'RUNNING'
                      ? 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300 animate-pulse'
                      : latestRun.status === 'ERROR'
                      ? 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300'
                      : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                  }`}
                >
                  {latestRun.status}
                </span>
              </div>

              {/* Latest Run Verdicts Breakdown (Scope: Latest Run) */}
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-100 dark:border-emerald-900/50">
                  <div className="text-base font-bold text-emerald-700 dark:text-emerald-400">
                    {latestRun.passed_cases}
                  </div>
                  <div className="text-[10px] font-semibold uppercase text-emerald-800 dark:text-emerald-300">
                    Pass
                  </div>
                </div>

                <div className="p-2 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-100 dark:border-red-900/50">
                  <div className="text-base font-bold text-red-700 dark:text-red-400">
                    {latestRun.failed_cases}
                  </div>
                  <div className="text-[10px] font-semibold uppercase text-red-800 dark:text-red-300">
                    Fail
                  </div>
                </div>

                <div className="p-2 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-100 dark:border-amber-900/50">
                  <div className="text-base font-bold text-amber-700 dark:text-amber-400">
                    {latestRun.inconclusive_cases}
                  </div>
                  <div className="text-[10px] font-semibold uppercase text-amber-800 dark:text-amber-300">
                    Inconcl.
                  </div>
                </div>
              </div>

              {/* Execution Errors Separated from Correctness Verdicts */}
              {latestRun.error_cases > 0 && (
                <div className="px-2.5 py-1.5 rounded-lg bg-orange-50 dark:bg-orange-950/40 border border-orange-200 dark:border-orange-900/60 text-[11px] text-orange-800 dark:text-orange-300 flex items-center justify-between">
                  <span className="font-semibold">Operational Execution Errors:</span>
                  <span className="font-mono font-bold">{latestRun.error_cases} (Excluded from Verdicts)</span>
                </div>
              )}

              {/* Latest Run Metadata */}
              <div className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center justify-between pt-1">
                <span className="font-mono truncate max-w-[130px]">
                  Run: {latestRun.run_id?.slice(0, 12)}...
                </span>
                <span>
                  {latestRun.created_at
                    ? new Date(latestRun.created_at).toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })
                    : 'Unknown time'}
                </span>
              </div>
            </div>
          ) : (
            <div className="py-3 px-3 rounded-xl border border-dashed border-slate-200 dark:border-slate-800 text-xs text-slate-500 dark:text-slate-400 space-y-1">
              <p className="font-medium text-slate-700 dark:text-slate-300">
                No test runs executed yet
              </p>
              <p className="text-[11px]">
                {suitesCount !== null && suitesCount > 0
                  ? `${suitesCount} test suite(s) available to execute in workspace.`
                  : 'Configure project endpoints and generate test suites to begin.'}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Footer Navigation Links */}
      <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800 flex flex-wrap items-center justify-between gap-2 text-xs">
        <Link
          to={workspacePath}
          className="inline-flex items-center gap-1.5 font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
        >
          <span>Open workspace</span>
          <ExternalLink className="w-3.5 h-3.5" />
        </Link>

        {latestRun && (
          <Link
            to={workspacePath}
            className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:underline"
          >
            <Wrench className="w-3 h-3 text-slate-400" />
            <span>Review corrections</span>
          </Link>
        )}
      </div>
    </div>
  );
};

export default C1DashboardCard;
