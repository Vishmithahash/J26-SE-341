/**
 * Component 4 (C4) - Candidate Rule Card
 * Displays policy rule properties, exact selectors, conditions, provenance excerpts, and validation warnings.
 */

import React from 'react';
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Quote,
} from 'lucide-react';
import {
  POLICY_FAMILIES,
  POLICY_REQUIREMENTS,
  RULE_REVIEW_STATUSES,
  SEVERITY_LEVELS,
} from '../../api/types.js';

export function CandidateRuleCard({
  rule,
  isSelected,
  onToggleSelect,
  onOpenReview,
  isReviewing,
}) {
  const isAccepted = rule.review_status === RULE_REVIEW_STATUSES.ACCEPTED;
  const isRejected = rule.review_status === RULE_REVIEW_STATUSES.REJECTED;

  const familyBadgeStyle =
    rule.policy_family === POLICY_FAMILIES.AUTHORIZATION
      ? 'bg-purple-100 dark:bg-purple-950/70 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800'
      : rule.policy_family === POLICY_FAMILIES.CONFIDENTIALITY
      ? 'bg-blue-100 dark:bg-blue-950/70 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800'
      : 'bg-amber-100 dark:bg-amber-950/70 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800';

  const requirementBadgeStyle =
    rule.policy_requirement === POLICY_REQUIREMENTS.ALLOW
      ? 'bg-emerald-100 dark:bg-emerald-950/70 text-emerald-700 dark:text-emerald-300'
      : rule.policy_requirement === POLICY_REQUIREMENTS.DENY
      ? 'bg-rose-100 dark:bg-rose-950/70 text-rose-700 dark:text-rose-300'
      : 'bg-indigo-100 dark:bg-indigo-950/70 text-indigo-700 dark:text-indigo-300';

  const statusBadgeStyle = isAccepted
    ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border-emerald-300'
    : isRejected
    ? 'bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300 border-rose-300'
    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-300';

  const severityBadgeStyle =
    rule.severity === SEVERITY_LEVELS.CRITICAL
      ? 'text-rose-600 bg-rose-50 dark:bg-rose-950/50'
      : rule.severity === SEVERITY_LEVELS.HIGH
      ? 'text-amber-600 bg-amber-50 dark:bg-amber-950/50'
      : 'text-slate-600 bg-slate-50 dark:bg-slate-950/50';

  return (
    <div
      className={`rounded-2xl border p-5 transition-all ${
        isSelected
          ? 'border-indigo-500 bg-indigo-50/20 dark:bg-indigo-950/20 ring-1 ring-indigo-500 shadow-sm'
          : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm hover:border-slate-300 dark:hover:border-slate-700'
      }`}
    >
      {/* Top Header Row */}
      <div className="flex flex-wrap items-start justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            checked={isSelected}
            onChange={() => onToggleSelect(rule.rule_id)}
            className="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
            title="Select rule for contract drafting"
          />
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold text-slate-900 dark:text-white">
                {rule.rule_id}
              </span>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-100 dark:bg-slate-800 text-slate-500">
                v{rule.rule_version || 1}
              </span>
            </div>
          </div>
        </div>

        {/* Badges */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${familyBadgeStyle}`}>
            {rule.policy_family}
          </span>
          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${requirementBadgeStyle}`}>
            {rule.policy_requirement}
          </span>
          <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${severityBadgeStyle}`}>
            {rule.severity}
          </span>
          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${statusBadgeStyle}`}>
            {rule.review_status || 'DRAFT'}
          </span>
        </div>
      </div>

      {/* Selectors Grid (Role, Action, Resource, Boundary) */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 my-3 text-xs">
        <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200/60 dark:border-slate-800/60">
          <span className="text-[10px] uppercase font-semibold text-slate-400 block mb-0.5">
            Principal / Role
          </span>
          <span className="font-mono text-slate-800 dark:text-slate-200 font-semibold truncate block">
            {rule.principal_selector || '*'}
          </span>
        </div>

        <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200/60 dark:border-slate-800/60">
          <span className="text-[10px] uppercase font-semibold text-slate-400 block mb-0.5">
            Action / Tool
          </span>
          <span className="font-mono text-slate-800 dark:text-slate-200 font-semibold truncate block">
            {rule.action_selector || '*'}
          </span>
        </div>

        <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200/60 dark:border-slate-800/60">
          <span className="text-[10px] uppercase font-semibold text-slate-400 block mb-0.5">
            Resource
          </span>
          <span className="font-mono text-slate-800 dark:text-slate-200 font-semibold truncate block">
            {rule.resource_selector || '*'}
          </span>
        </div>

        <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200/60 dark:border-slate-800/60">
          <span className="text-[10px] uppercase font-semibold text-slate-400 block mb-0.5">
            Boundary
          </span>
          <span className="font-mono text-slate-800 dark:text-slate-200 font-semibold truncate block">
            {rule.evaluation_boundary || 'ATTEMPTED_ACTION'}
          </span>
        </div>
      </div>

      {/* Conditions (Preserving exact numbers without rounding) */}
      {rule.compliance_conditions && (
        <div className="my-2.5 p-2.5 rounded-xl bg-slate-50 dark:bg-slate-950/40 border border-slate-200/60 dark:border-slate-800/60 text-xs">
          <span className="text-[10px] uppercase font-semibold text-slate-400 block mb-1">
            Compliance Conditions
          </span>
          <pre className="font-mono text-[11px] text-slate-700 dark:text-slate-300 overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(rule.compliance_conditions, null, 2)}
          </pre>
        </div>
      )}

      {/* Provenance Excerpt (Rendered strictly as safe text) */}
      {rule.source_references && rule.source_references.length > 0 && (
        <div className="my-2.5 p-3 rounded-xl bg-indigo-50/40 dark:bg-indigo-950/20 border border-indigo-100 dark:border-indigo-900/40 text-xs">
          <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase text-indigo-700 dark:text-indigo-300 mb-1">
            <Quote className="w-3 h-3" />
            <span>Supporting Excerpt Provenance</span>
          </div>
          {rule.source_references.map((ref, idx) => (
            <div key={idx} className="space-y-1">
              <div className="text-[11px] text-slate-500 font-mono">
                Artifact: {ref.artifact_id} (v{ref.artifact_version})
                {ref.start_char != null && ` [chars ${ref.start_char}..${ref.end_char}]`}
              </div>
              <blockquote className="text-xs text-slate-700 dark:text-slate-300 italic pl-2 border-l-2 border-indigo-300 dark:border-indigo-700">
                {ref.supporting_excerpt}
              </blockquote>
            </div>
          ))}
        </div>
      )}

      {/* Validation Issues / Ambiguity Warnings Beside Affected Rule */}
      {rule.validation_issues && rule.validation_issues.length > 0 && (
        <div className="my-2.5 p-3 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900">
          <span className="text-[11px] font-bold text-amber-900 dark:text-amber-200 flex items-center gap-1 mb-1.5">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            <span>Rule Validation Warnings ({rule.validation_issues.length})</span>
          </span>
          <ul className="space-y-1 text-xs">
            {rule.validation_issues.map((iss, idx) => (
              <li key={idx} className="text-amber-800 dark:text-amber-300 flex items-start gap-1.5">
                <span className="font-mono text-[10px] px-1 py-0.2 bg-amber-200/60 dark:bg-amber-900/60 rounded">
                  {iss.code}
                </span>
                <span>{iss.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Review Notes / Review Metadata if already reviewed */}
      {rule.extraction_metadata?.review_decision && (
        <div className="my-2 p-2.5 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200/60 dark:border-slate-800/60 text-[11px] text-slate-500 flex items-center justify-between">
          <span>
            Reviewed by <strong>{rule.extraction_metadata.reviewed_by}</strong> ({rule.extraction_metadata.review_decision})
          </span>
          {rule.extraction_metadata.review_notes && (
            <span className="italic truncate max-w-xs text-slate-400">
              "{rule.extraction_metadata.review_notes}"
            </span>
          )}
        </div>
      )}

      {/* Bottom Review Action Buttons */}
      <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
        <span className="text-[11px] text-slate-400">
          Boundary: {rule.evaluation_boundary || 'ATTEMPTED_ACTION'}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onOpenReview(rule, 'REJECTED')}
            disabled={isReviewing}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-rose-200 dark:border-rose-900 text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/50 text-xs font-medium transition-colors"
          >
            <XCircle className="w-3.5 h-3.5" />
            <span>Reject</span>
          </button>
          <button
            type="button"
            onClick={() => onOpenReview(rule, 'ACCEPTED')}
            disabled={isReviewing}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium transition-colors shadow-sm"
          >
            <CheckCircle className="w-3.5 h-3.5" />
            <span>Accept Rule</span>
          </button>
        </div>
      </div>
    </div>
  );
}
