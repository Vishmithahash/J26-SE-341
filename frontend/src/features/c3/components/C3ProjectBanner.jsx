import React from 'react';
import { Link } from 'react-router-dom';
import { FolderGit2, AlertTriangle, ExternalLink, ShieldCheck } from 'lucide-react';
import { useProject } from '../../../context/ProjectContext';
import { useAuth } from '../../../context/AuthContext';

export const C3ProjectBanner = () => {
  const { activeProject, activeProjectId, isLoadingActive } = useProject();
  const { user } = useAuth();

  const projectsPath = user?.role === 'ADMIN' ? '/admin/projects' : '/app/projects';

  if (isLoadingActive) {
    return (
      <div className="p-4 rounded-xl bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 animate-pulse flex items-center gap-3">
        <div className="w-5 h-5 bg-slate-300 dark:bg-slate-700 rounded" />
        <div className="h-4 bg-slate-300 dark:bg-slate-700 rounded w-48" />
      </div>
    );
  }

  if (!activeProject) {
    return (
      <div className="p-4 sm:p-5 rounded-2xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/80 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-xl bg-amber-100 dark:bg-amber-900/60 text-amber-700 dark:text-amber-300 shrink-0 mt-0.5">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-amber-900 dark:text-amber-200">
                No Active Project Selected
              </h2>
              <p className="text-xs text-amber-800/90 dark:text-amber-300/90 mt-1 leading-relaxed">
                Component 3 requires an authorized active project to prepare contracts, generate feasible cases, and inspect stored suites. The backend demonstration fallback default (<code className="font-mono bg-amber-200/50 dark:bg-amber-900/60 px-1 py-0.5 rounded">proj-demo-qa</code>) is strictly prohibited in place of a selected project.
              </p>
            </div>
          </div>

          <Link
            to={projectsPath}
            className="inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-amber-600 hover:bg-amber-700 text-white shrink-0 shadow-sm transition-colors"
          >
            <span>Select or Register a Project</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div className="flex items-start gap-3.5">
        <div className="p-2.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 shrink-0">
          <FolderGit2 className="w-5 h-5" />
        </div>
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Active Project Scope
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
              <ShieldCheck className="w-3 h-3" />
              Authorized
            </span>
          </div>
          <div className="flex items-baseline gap-2 mt-1 flex-wrap">
            <h2 className="text-base font-bold text-slate-900 dark:text-white">
              {activeProject.name}
            </h2>
            <code className="text-xs font-mono text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">
              {activeProjectId}
            </code>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Domain: <span className="font-medium text-slate-700 dark:text-slate-300 capitalize">{activeProject.domain || 'custom'}</span>
            {' • '}
            Environment: <span className="font-medium text-slate-700 dark:text-slate-300 capitalize">{activeProject.environment || 'development'}</span>
            {' • '}
            Connection: <span className="font-medium text-slate-700 dark:text-slate-300">{activeProject.connection_state || 'NOT_CHECKED'}</span>
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3 self-end md:self-center shrink-0">
        <Link
          to={projectsPath}
          className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline inline-flex items-center gap-1"
        >
          <span>Switch project</span>
          <ExternalLink className="w-3.5 h-3.5" />
        </Link>
      </div>
    </div>
  );
};
