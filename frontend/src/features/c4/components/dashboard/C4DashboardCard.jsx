import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ShieldCheck,
  ArrowRight,
  ExternalLink,
  Cpu,
  Layers,
  FileCheck,
  AlertCircle,
  FolderOpen,
} from 'lucide-react';
import { useProject } from '../../../../context/ProjectContext';
import { c4Api } from '../../api/c4Api';

export const C4DashboardCard = ({ basePath = '/app' }) => {
  const { activeProject } = useProject();
  const [readiness, setReadiness] = useState(null);
  const [bindings, setBindings] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const projectId = activeProject?.project_id;

  useEffect(() => {
    if (!projectId) {
      setReadiness(null);
      setBindings([]);
      setError(null);
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    Promise.allSettled([
      c4Api.getExtractionReadiness(projectId),
      c4Api.getBindings(projectId),
    ]).then(([readinessRes, bindingsRes]) => {
      if (!isMounted) return;

      if (readinessRes.status === 'fulfilled') {
        setReadiness(readinessRes.value);
      } else {
        setReadiness(null);
      }

      if (bindingsRes.status === 'fulfilled' && Array.isArray(bindingsRes.value)) {
        setBindings(bindingsRes.value);
      } else {
        setBindings([]);
      }

      setIsLoading(false);
    }).catch((err) => {
      if (!isMounted) return;
      setError(err?.message || 'Failed to load policy safety overview');
      setIsLoading(false);
    });

    return () => {
      isMounted = false;
    };
  }, [projectId]);

  const workspacePath = `${basePath}/policy-safety`;
  const projectsPath = `${basePath}/projects`;

  // 1. Empty State: No Project Selected
  if (!activeProject) {
    return (
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
        <div>
          <div className="flex items-start justify-between gap-3 mb-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 shrink-0">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <span className="text-[11px] font-medium text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/50 px-2 py-0.5 rounded border border-amber-200/50 dark:border-amber-900/50">
              No Project
            </span>
          </div>

          <h3 className="text-sm font-bold text-slate-900 dark:text-white leading-snug">
            Policy-Aware Safety and Prompt-Injection Testing
          </h3>

          <p className="text-xs text-slate-500 dark:text-slate-400 mt-2 leading-relaxed">
            Policy derivation, safety contract gates, and injection resilience testing require an active project scope.
          </p>

          <div className="mt-4 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/60 dark:border-slate-700/60 flex items-center gap-2.5">
            <FolderOpen className="w-4 h-4 text-slate-400 shrink-0" />
            <span className="text-xs text-slate-600 dark:text-slate-300">
              Select or create a project to enable Component 4.
            </span>
          </div>
        </div>

        <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <Link
            to={projectsPath}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
          >
            <span>Select Project</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
          <span className="text-[11px] text-slate-400">Scoped per project</span>
        </div>
      </div>
    );
  }

  // 2. Active Project Selected
  return (
    <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
      <div>
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 shrink-0">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <span className="text-[11px] font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/50 px-2 py-0.5 rounded border border-emerald-200/50 dark:border-emerald-900/50">
            Phase 1 Active
          </span>
        </div>

        <h3 className="text-sm font-bold text-slate-900 dark:text-white leading-snug">
          Policy-Aware Safety and Prompt-Injection Testing
        </h3>

        <div className="mt-2 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
          <span className="font-semibold text-slate-700 dark:text-slate-300 truncate max-w-[160px]">
            {activeProject.name}
          </span>
          <span>•</span>
          <span className="capitalize">{activeProject.domain || 'banking_fintech'}</span>
        </div>

        {/* Dynamic Status / Readiness Content */}
        <div className="mt-4 space-y-2">
          {isLoading ? (
            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-700/60 animate-pulse space-y-2">
              <div className="h-3 w-3/4 bg-slate-200 dark:bg-slate-700 rounded"></div>
              <div className="h-2.5 w-1/2 bg-slate-200 dark:bg-slate-700 rounded"></div>
            </div>
          ) : error ? (
            <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200/60 dark:border-amber-800/50 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
              <div className="text-xs text-amber-800 dark:text-amber-300">
                <p className="font-medium">Readiness query unavailable</p>
                <p className="text-[11px] text-amber-700/80 dark:text-amber-400/80">Backend endpoint returned an error.</p>
              </div>
            </div>
          ) : (
            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-700/60 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
                  <Cpu className="w-3.5 h-3.5 text-indigo-500" />
                  Extraction Engine:
                </span>
                <span className="font-medium text-slate-700 dark:text-slate-200">
                  {readiness?.active_mode === 'offline_mock'
                    ? 'Deterministic Regex (Offline Mock)'
                    : readiness?.provider || 'Offline Mock'}
                </span>
              </div>

              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
                  <Layers className="w-3.5 h-3.5 text-teal-500" />
                  Domain Bindings:
                </span>
                <span className="font-medium text-slate-700 dark:text-slate-200">
                  {bindings.length > 0 ? `${bindings.length} configured` : 'Default profile ready'}
                </span>
              </div>

              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
                  <FileCheck className="w-3.5 h-3.5 text-emerald-500" />
                  Contract Lifecycle:
                </span>
                <span className="font-medium text-slate-700 dark:text-slate-200">
                  Acceptance Gated
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
        <Link
          to={workspacePath}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
        >
          <span>Open C4 Workspace</span>
          <ExternalLink className="w-3.5 h-3.5" />
        </Link>
        <span className="text-[11px] text-slate-400">Policy & Safety</span>
      </div>
    </div>
  );
};
