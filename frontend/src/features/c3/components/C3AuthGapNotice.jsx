import React, { useState } from 'react';
import { ShieldAlert, ChevronDown, ChevronUp, Lock } from 'lucide-react';

export const C3AuthGapNotice = () => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="rounded-xl border border-amber-200 dark:border-amber-900/60 bg-amber-50/70 dark:bg-amber-950/20 p-4 text-xs">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <ShieldAlert className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold text-amber-900 dark:text-amber-200 flex items-center gap-1.5">
              <span>Security & Authorization Notice</span>
              <span className="text-[10px] font-normal px-1.5 py-0.2 rounded bg-amber-200/60 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300">
                Phase 1 Status
              </span>
            </div>
            <p className="text-amber-800/90 dark:text-amber-300/90 mt-0.5 leading-relaxed">
              C3 backend endpoints under <code className="font-mono bg-amber-100 dark:bg-amber-900/60 px-1 py-0.5 rounded">/api/v1/c3/*</code> currently operate unauthenticated at the routing layer. Logical project isolation is applied via <code className="font-mono bg-amber-100 dark:bg-amber-900/60 px-1 py-0.5 rounded">project_id</code>, but server-side ownership and role enforcement dependencies are pending multi-component integration.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-amber-700 dark:text-amber-300 hover:text-amber-900 dark:hover:text-amber-100 p-1 shrink-0 inline-flex items-center gap-1 font-medium"
          aria-label={isExpanded ? 'Collapse audit details' : 'Expand audit details'}
        >
          <span>{isExpanded ? 'Less' : 'Details'}</span>
          {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
      </div>

      {isExpanded && (
        <div className="mt-3 pt-3 border-t border-amber-200/70 dark:border-amber-900/40 space-y-2 text-amber-900 dark:text-amber-200">
          <div className="flex items-center gap-1.5 font-semibold">
            <Lock className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
            <span>Frontend Safeguards in Effect:</span>
          </div>
          <ul className="list-disc list-inside space-y-1 text-slate-700 dark:text-slate-300 pl-1">
            <li>
              <strong>Active Project Binding:</strong> All C3 queries and candidate generation requests strictly bind to the active project authorized in your session. The backend fallback default (<code className="font-mono">proj-demo-qa</code>) is never used as a silent substitute.
            </li>
            <li>
              <strong>Client Role Separation:</strong> Administrative workspaces require authenticated <code className="font-mono">ADMIN</code> role in the auth context; standard users are isolated to <code className="font-mono">/app/*</code>.
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
