import React from 'react';
import { Link } from 'react-router-dom';
import {
  RotateCcw,
  ExternalLink,
  FolderGit2,
  AlertTriangle,
  Sparkles,
} from 'lucide-react';
import { useProject } from '../../../context/ProjectContext';
import { useC3ProjectSuites } from '../hooks/useC3ProjectSuites';
import { C3Badge } from './C3Badge';

export const C3DashboardCard = ({ role = 'USER' }) => {
  const { activeProject, activeProjectId, isLoadingActive } = useProject();
  const { totalSuites, isLoading: isLoadingSuites, error: suiteError, isDbUnavailable } =
    useC3ProjectSuites(activeProjectId);

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
            <C3Badge status="STATIC_ONLY" label="Phase 1 Active" />
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
                  Scope: Authorized project records. System-wide multi-project C3 aggregation is pending backend server-side authorization integration.
                </p>
              )}
            </div>
          ) : (
            <div className="flex items-start gap-2 text-amber-700 dark:text-amber-400">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold">No project selected</span>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                  Link an authorized project to prepare inputs and inspect suites.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Available Suite / Case Totals */}
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
              ) : isDbUnavailable ? (
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
              Fault Families
            </span>
            <div className="text-base font-bold text-slate-900 dark:text-white mt-0.5">
              5 Operational
            </div>
          </div>
        </div>

        {/* Concise Readiness Message */}
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-3 leading-relaxed">
          Static validation & deterministic suite generation ready. Live target runner execution blocked (Phase 1 platform status).
        </p>
      </div>

      {/* Action Links */}
      <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
        <Link
          to={`${basePath}#prepare`}
          className="inline-flex items-center gap-1 font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>Prepare Cases</span>
        </Link>

        <Link
          to={basePath}
          className="inline-flex items-center gap-1.5 font-semibold text-slate-700 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-400"
        >
          <span>Open Workspace</span>
          <ExternalLink className="w-3.5 h-3.5" />
        </Link>
      </div>
    </div>
  );
};
