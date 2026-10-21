import React from 'react';
import { Activity, Beaker, History, HelpCircle } from 'lucide-react';
import {
  PROVENANCE_TYPES,
  PROVENANCE_METADATA,
  getExecutionProvenance,
} from './provenanceUtils';

export const ExecutionProvenanceBadge = ({
  provenanceType,
  runOrCase,
  showDescription = false,
  compact = false,
}) => {
  const resolvedType =
    provenanceType || (runOrCase ? getExecutionProvenance(runOrCase) : PROVENANCE_TYPES.UNKNOWN_ORIGIN);

  const meta = PROVENANCE_METADATA[resolvedType] || PROVENANCE_METADATA[PROVENANCE_TYPES.UNKNOWN_ORIGIN];

  const getIcon = () => {
    switch (resolvedType) {
      case PROVENANCE_TYPES.LIVE_EXECUTION:
        return <Activity className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />;
      case PROVENANCE_TYPES.SYNTHETIC_DEMO:
        return <Beaker className="w-3 h-3 text-amber-600 dark:text-amber-400" />;
      case PROVENANCE_TYPES.IMPORTED_REPLAY:
        return <History className="w-3 h-3 text-purple-600 dark:text-purple-400" />;
      case PROVENANCE_TYPES.UNKNOWN_ORIGIN:
      default:
        return <HelpCircle className="w-3 h-3 text-slate-500 dark:text-slate-400" />;
    }
  };

  const getBadgeClasses = () => {
    switch (resolvedType) {
      case PROVENANCE_TYPES.LIVE_EXECUTION:
        return 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800/80';
      case PROVENANCE_TYPES.SYNTHETIC_DEMO:
        return 'bg-amber-50 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-amber-800/80';
      case PROVENANCE_TYPES.IMPORTED_REPLAY:
        return 'bg-purple-50 dark:bg-purple-950/60 text-purple-800 dark:text-purple-300 border-purple-200 dark:border-purple-800/80';
      case PROVENANCE_TYPES.UNKNOWN_ORIGIN:
      default:
        return 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700';
    }
  };

  return (
    <div className="inline-flex flex-col">
      <span
        title={meta.description}
        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md border text-[11px] font-semibold tracking-wide ${getBadgeClasses()}`}
      >
        {getIcon()}
        <span>{compact ? meta.shortLabel : meta.label}</span>
      </span>

      {showDescription && (
        <span className="text-[10px] text-slate-500 dark:text-slate-400 mt-1 max-w-xs leading-tight">
          {meta.description}
        </span>
      )}
    </div>
  );
};

export default ExecutionProvenanceBadge;
