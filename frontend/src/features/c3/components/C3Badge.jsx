import React from 'react';

export const C3Badge = ({ status, label, className = '' }) => {
  const norm = (status || '').toUpperCase();

  let styles = 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700';
  let defaultLabel = null;

  if (
    norm === 'STATIC_VALID' ||
    norm === 'SAVED' ||
    norm === 'QUALIFIED' ||
    norm === 'READY' ||
    norm === 'CONFIRMED' ||
    norm === 'PASS_COMPLETED' ||
    norm === 'COMPLETED' ||
    norm === 'SATISFIED' ||
    norm === 'TRUE'
  ) {
    styles = 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800';
    if (norm === 'PASS_COMPLETED') defaultLabel = 'Pass: Completed';
    if (norm === 'SATISFIED') defaultLabel = 'Satisfied';
    if (norm === 'TRUE') defaultLabel = 'TRUE';
  } else if (
    norm === 'TEST_NOT_READY' ||
    norm === 'FILTERED_OUT' ||
    norm === 'UNCERTAIN' ||
    norm === 'SAVING' ||
    norm === 'NOT_TRIGGERED' ||
    norm === 'INCONCLUSIVE' ||
    norm === 'INTERRUPTED'
  ) {
    styles = 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800';
    if (norm === 'INCONCLUSIVE') defaultLabel = 'Inconclusive';
    if (norm === 'NOT_TRIGGERED') defaultLabel = 'Fault Unreached';
    if (norm === 'TEST_NOT_READY') defaultLabel = 'Test Not Ready';
  } else if (
    norm === 'BLOCKED' ||
    norm === 'FAILED' ||
    norm === 'FAIL' ||
    norm === 'DISQUALIFIED' ||
    norm === 'ERROR' ||
    norm === 'EXECUTION_ERROR' ||
    norm === 'VIOLATED' ||
    norm === 'FALSE'
  ) {
    styles = 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800';
    if (norm === 'FAIL') defaultLabel = 'Fail';
    if (norm === 'VIOLATED') defaultLabel = 'Violated';
    if (norm === 'EXECUTION_ERROR') defaultLabel = 'Execution Error';
    if (norm === 'FALSE') defaultLabel = 'FALSE';
  } else if (norm === 'PASS_GRACEFUL') {
    styles = 'bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/40 dark:text-sky-300 dark:border-sky-800';
    defaultLabel = 'Pass: Graceful';
  } else if (norm === 'DEMONSTRATION') {
    styles = 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-800';
    defaultLabel = 'Demonstration';
  } else if (norm === 'LIVE_AUT' || norm === 'AUT') {
    styles = 'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-300 dark:border-indigo-800';
    defaultLabel = 'Live Target';
  } else if (norm === 'IMPORTED') {
    styles = 'bg-teal-50 text-teal-700 border-teal-200 dark:bg-teal-950/40 dark:text-teal-300 dark:border-teal-800';
    defaultLabel = 'Imported';
  } else if (norm === 'GENERATED' || norm === 'STATIC_ONLY') {
    styles = 'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-300 dark:border-indigo-800';
  } else if (
    norm === 'NOT_EVALUATED' ||
    norm === 'UNSAVED' ||
    norm === 'NOT_APPLICABLE' ||
    norm === 'EXPOSURE_UNKNOWN' ||
    norm === 'UNKNOWN'
  ) {
    styles = 'bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700';
    if (norm === 'NOT_EVALUATED') defaultLabel = 'Not Evaluated';
    if (norm === 'NOT_APPLICABLE') defaultLabel = 'Not Applicable';
    if (norm === 'UNKNOWN') defaultLabel = 'UNKNOWN';
  }

  const displayText = label || defaultLabel || status || 'Unknown';

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold tracking-tight border ${styles} ${className}`}
    >
      {displayText}
    </span>
  );
};
