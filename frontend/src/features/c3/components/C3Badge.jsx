import React from 'react';

export const C3Badge = ({ status, label, className = '' }) => {
  const norm = (status || '').toUpperCase();

  let styles = 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700';

  if (norm === 'STATIC_VALID' || norm === 'SAVED' || norm === 'QUALIFIED' || norm === 'READY') {
    styles = 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800';
  } else if (norm === 'TEST_NOT_READY' || norm === 'FILTERED_OUT' || norm === 'UNCERTAIN' || norm === 'SAVING') {
    styles = 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800';
  } else if (norm === 'BLOCKED' || norm === 'FAILED' || norm === 'DISQUALIFIED' || norm === 'ERROR') {
    styles = 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800';
  } else if (norm === 'GENERATED' || norm === 'STATIC_ONLY' || norm === 'CONFIRMED') {
    styles = 'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-300 dark:border-indigo-800';
  } else if (norm === 'UNSAVED' || norm === 'NOT_APPLICABLE' || norm === 'NOT_TRIGGERED') {
    styles = 'bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700';
  }

  const displayText = label || status || 'Unknown';

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold tracking-tight border ${styles} ${className}`}
    >
      {displayText}
    </span>
  );
};
