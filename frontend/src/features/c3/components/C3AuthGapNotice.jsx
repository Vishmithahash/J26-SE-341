import React, { useState } from 'react';
import { ShieldAlert, ChevronDown, ChevronUp, Lock } from 'lucide-react';

export const C3AuthGapNotice = () => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="rounded-xl border border-indigo-200 dark:border-indigo-900/60 bg-indigo-50/50 dark:bg-indigo-950/20 p-4 text-xs">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <ShieldAlert className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
              <span>Project Authorization & Governance</span>
              <span className="text-[10px] font-normal px-1.5 py-0.2 rounded bg-indigo-200/60 dark:bg-indigo-900/40 text-indigo-800 dark:text-indigo-300">
                Authorized Session
              </span>
            </div>
            <p className="text-slate-600 dark:text-slate-300 mt-0.5 leading-relaxed">
              Component 3 operations are strictly scoped to the authorized project selected in your active session. Persistence, suite retrieval, and trial evidence requests enforce project access controls and role-based workspace routing.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-indigo-700 dark:text-indigo-300 hover:text-indigo-900 dark:hover:text-indigo-100 p-1 shrink-0 inline-flex items-center gap-1 font-medium"
          aria-label={isExpanded ? 'Collapse governance details' : 'Expand governance details'}
        >
          <span>{isExpanded ? 'Less' : 'Details'}</span>
          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
      </div>

      {isExpanded && (
        <div className="mt-3 pt-3 border-t border-indigo-200/70 dark:border-indigo-900/40 space-y-2 text-slate-800 dark:text-slate-200">
          <div className="flex items-center gap-1.5 font-semibold">
            <Lock className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
            <span>Active Safeguards & Security Boundaries:</span>
          </div>
          <ul className="list-disc list-inside space-y-1 text-slate-600 dark:text-slate-300 pl-1">
            <li>
              <strong>Active Project Binding:</strong> All queries, suites, candidate cases, and evidence records are scoped to the authenticated project identifier. Cross-project operations are rejected.
            </li>
            <li>
              <strong>Role-Scoped Workspaces:</strong> Administrative tools and governance controls require an authenticated administrative session; standard users access project-scoped testing workflows.
            </li>
            <li>
              <strong>Zero Secret Ingestion:</strong> The setup interface strictly disallows database credentials, API keys, or application secrets.
            </li>
            <li>
              <strong>Honest Availability:</strong> Unreachable database persistence returns explicit unavailable states rather than fabricated zero metrics.
            </li>
          </ul>
        </div>
      )}
    </div>
  );
};
