import React, { useState } from 'react';
import { Code, ChevronDown, ChevronRight } from 'lucide-react';

/**
 * Renders structured predicates and guard expressions strictly as static data.
 * Does NOT execute any arbitrary code, eval, or runtime logic in the browser.
 */

function formatFieldRef(ref) {
  if (!ref || typeof ref !== 'object') return String(ref);
  if (ref.scope && ref.path) {
    return `${ref.scope}.${ref.path}`;
  }
  return JSON.stringify(ref);
}

function formatValue(val) {
  if (val === null) return 'null';
  if (val === undefined) return 'undefined';
  if (typeof val === 'object' && val.scope) {
    return formatFieldRef(val);
  }
  if (typeof val === 'string') return `"${val}"`;
  return String(val);
}

function renderPredicateSummary(predicate) {
  if (!predicate) return 'None (Unconditional)';

  if (predicate.type === 'comparison') {
    const left = formatValue(predicate.left);
    const op = predicate.op || '==';
    const right = formatValue(predicate.right);
    return `${left} ${op} ${right}`;
  }

  if (predicate.type === 'presence') {
    const target = formatValue(predicate.target);
    const op = predicate.op;
    return `${target} ${op}`;
  }

  if (predicate.type === 'logical') {
    const op = predicate.op || 'AND';
    if (op === 'NOT') {
      const child = predicate.clauses?.[0] ? renderPredicateSummary(predicate.clauses[0]) : '';
      return `NOT (${child})`;
    }
    const children = (predicate.clauses || []).map((c) => renderPredicateSummary(c));
    return `(${children.join(` ${op} `)})`;
  }

  if (predicate.type === 'literal') {
    return String(predicate.value).toUpperCase();
  }

  if (typeof predicate === 'object') {
    try {
      return JSON.stringify(predicate);
    } catch {
      return '[Complex Expression]';
    }
  }

  return String(predicate);
}

export const PredicateViewer = ({ predicate, label = 'Guard Expression', showBadge = true }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!predicate) {
    return <span className="text-xs text-slate-400 italic">None (Unconditional)</span>;
  }

  const summary = renderPredicateSummary(predicate);

  return (
    <div className="text-xs font-mono">
      <div className="flex items-center gap-1.5 flex-wrap">
        {showBadge && (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
            {predicate.type || 'predicate'}
          </span>
        )}
        <code className="text-slate-800 dark:text-slate-200 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded break-all">
          {summary}
        </code>
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="p-1 rounded text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-200/50 dark:hover:bg-slate-700/50 transition-colors"
          title={isExpanded ? 'Collapse raw tree' : 'View raw JSON predicate tree'}
          aria-label="Toggle predicate tree"
        >
          {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </button>
      </div>

      {isExpanded && (
        <div className="mt-2 p-2.5 rounded-lg bg-slate-900 text-slate-200 text-[11px] overflow-x-auto border border-slate-700 shadow-inner">
          <div className="flex items-center justify-between pb-1.5 mb-1.5 border-b border-slate-800 text-[10px] text-slate-400">
            <span className="flex items-center gap-1">
              <Code className="w-3 h-3 text-indigo-400" />
              {label} Data Tree (Evaluated by Backend Engine)
            </span>
          </div>
          <pre className="m-0 leading-relaxed font-mono">
            {JSON.stringify(predicate, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};
