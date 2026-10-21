/**
 * Component 4 (C4) - Project Header Component
 * Displays active project context, domain, lifecycle state, and links to role-specific project switcher.
 */

import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldCheck, FolderKanban, AlertTriangle, ExternalLink } from 'lucide-react';
import { useAuth } from '../../../context/AuthContext';

export function ProjectHeader({ activeProject, isLoadingActive, availableProjects = [], onSelectProject }) {
  const { user } = useAuth();
  const isAdmin = user?.role === 'ADMIN';
  const projectsPath = isAdmin ? '/admin/projects' : '/app/projects';

  if (isLoadingActive) {
    return (
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 mb-6 flex items-center gap-3 animate-pulse">
        <div className="w-10 h-10 rounded-xl bg-slate-200 dark:bg-slate-800" />
        <div className="space-y-2 flex-1">
          <div className="h-4 bg-slate-200 dark:bg-slate-800 rounded w-1/4" />
          <div className="h-3 bg-slate-200 dark:bg-slate-800 rounded w-1/3" />
        </div>
      </div>
    );
  }

  if (!activeProject) {
    return (
      <div
        role="alert"
        className="bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 rounded-2xl p-6 mb-6 text-amber-900 dark:text-amber-200 shadow-sm"
      >
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-6 h-6 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <div>
              <h2 className="text-base font-semibold">No Active Project Selected</h2>
              <p className="text-xs text-amber-700 dark:text-amber-300 mt-0.5">
                Component 4 requires an active project to scope policy contracts, extraction jobs, and safety tests.
                All project-specific operations are currently disabled.
              </p>
              {availableProjects && availableProjects.length > 0 && onSelectProject && (
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold text-amber-900 dark:text-amber-200">
                    Quick Select:
                  </span>
                  {availableProjects.map((p) => (
                    <button
                      key={p.project_id}
                      onClick={() => onSelectProject(p)}
                      className="px-2.5 py-1 rounded-lg bg-amber-200/80 dark:bg-amber-900/60 hover:bg-amber-300 dark:hover:bg-amber-800 text-amber-950 dark:text-amber-100 text-xs font-medium border border-amber-300 dark:border-amber-700 transition-colors"
                    >
                      {p.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
          <Link
            to={projectsPath}
            className="inline-flex items-center gap-2 px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white font-medium text-xs rounded-xl transition-colors shadow-sm shrink-0"
          >
            <FolderKanban className="w-4 h-4" />
            <span>Select or Register Project</span>
            <ExternalLink className="w-3.5 h-3.5 ml-0.5" />
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 mb-6 shadow-sm">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-start md:items-center gap-3.5">
          <div className="w-11 h-11 rounded-xl bg-indigo-50 dark:bg-indigo-950/70 border border-indigo-200 dark:border-indigo-800 flex items-center justify-center text-indigo-600 dark:text-indigo-400 shrink-0">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-bold text-slate-900 dark:text-white tracking-tight">
                {activeProject.name}
              </h2>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 dark:bg-indigo-950/80 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 font-mono">
                {activeProject.project_id}
              </span>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                Domain: {activeProject.domain || 'ecommerce'}
              </span>
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                {activeProject.lifecycle || 'active'}
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Active Project Scope • Policy contracts, extraction jobs, and safety tests bound to this project
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {availableProjects && availableProjects.length > 1 && onSelectProject && (
            <select
              value={activeProject.project_id}
              onChange={(e) => {
                const p = availableProjects.find((x) => x.project_id === e.target.value);
                if (p) onSelectProject(p);
              }}
              aria-label="Active Project Switcher"
              className="text-xs bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-medium"
            >
              {availableProjects.map((p) => (
                <option key={p.project_id} value={p.project_id}>
                  {p.name}
                </option>
              ))}
            </select>
          )}
          <Link
            to={projectsPath}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-400 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg transition-colors"
            title="Switch active project"
          >
            <FolderKanban className="w-3.5 h-3.5" />
            <span>Manage Projects</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
