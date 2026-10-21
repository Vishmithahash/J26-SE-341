/**
 * Component 4 (C4) - Test Case Card Component
 * Displays case identity, pinned dependencies, lifecycle status, content hash, validation reasons, and action triggers.
 */

import React from 'react';
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  Lock,
  Layers,
  FileCheck,
  CheckCircle,
  AlertTriangle,
  Play,
  Eye,
  Hash,
} from 'lucide-react';
import { TEST_CASE_KINDS, CASE_LIFECYCLE_STATES } from '../../api/types.js';

export function TestCaseCard({
  testCase,
  onValidateCase,
  onFreezeCase,
  onInspectPayloads,
  onOpenExecution,
  isValidating,
  isFreezing,
}) {
  const isFrozen = testCase.lifecycle_state === CASE_LIFECYCLE_STATES.FROZEN;
  const isValidated = testCase.lifecycle_state === CASE_LIFECYCLE_STATES.VALIDATED;

  const getCategoryBadge = (kind) => {
    switch (kind) {
      case TEST_CASE_KINDS.BENIGN:
        return {
          label: 'Benign Control',
          style: 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800',
          icon: ShieldCheck,
        };
      case TEST_CASE_KINDS.DIRECT_POLICY_CHALLENGE:
        return {
          label: 'Direct Challenge',
          style: 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800',
          icon: Shield,
        };
      case TEST_CASE_KINDS.INDIRECT_PROMPT_INJECTION:
        return {
          label: 'Indirect Injection',
          style: 'bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800',
          icon: ShieldAlert,
        };
      default:
        return {
          label: kind,
          style: 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700',
          icon: Shield,
        };
    }
  };

  const getLifecycleBadge = (state) => {
    switch (state) {
      case CASE_LIFECYCLE_STATES.FROZEN:
        return 'bg-indigo-100 dark:bg-indigo-950/80 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800';
      case CASE_LIFECYCLE_STATES.VALIDATED:
        return 'bg-emerald-100 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800';
      case CASE_LIFECYCLE_STATES.REJECTED:
        return 'bg-rose-100 dark:bg-rose-950/80 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800';
      case CASE_LIFECYCLE_STATES.NEEDS_REVIEW:
        return 'bg-amber-100 dark:bg-amber-950/80 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800';
      default:
        return 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700';
    }
  };

  const categoryMeta = getCategoryBadge(testCase.test_kind);
  const CategoryIcon = categoryMeta.icon;

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm hover:border-slate-300 dark:hover:border-slate-700 transition-all space-y-4">
      {/* Top Header Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${categoryMeta.style}`}>
            <CategoryIcon className="w-3.5 h-3.5" />
            {categoryMeta.label}
          </span>

          <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold uppercase tracking-wider border ${getLifecycleBadge(testCase.lifecycle_state)}`}>
            {isFrozen && <Lock className="w-3 h-3" />}
            {testCase.lifecycle_state}
          </span>

          <span className="text-xs font-mono font-medium text-slate-500 dark:text-slate-400">
            v{testCase.case_version}
          </span>
        </div>

        <div className="text-[11px] font-mono text-slate-400 dark:text-slate-500">
          ID: {testCase.case_id}
        </div>
      </div>

      {/* Target Rule & Task Prompt */}
      <div>
        <div className="flex flex-wrap items-center gap-2 text-xs mb-1.5">
          <span className="font-semibold text-slate-700 dark:text-slate-300">Target Rule:</span>
          <span className="px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 font-mono text-[11px] font-medium border border-indigo-200/60 dark:border-indigo-800/60">
            {testCase.target_rule_id}
          </span>
          <span className="text-slate-400">•</span>
          <span className="text-slate-500 dark:text-slate-400 capitalize">
            Boundary: {testCase.expected_boundary?.toLowerCase() || 'attempted_action'}
          </span>
        </div>

        <p className="text-xs text-slate-800 dark:text-slate-200 font-medium leading-relaxed bg-slate-50 dark:bg-slate-800/40 p-3 rounded-xl border border-slate-200/60 dark:border-slate-700/60">
          <span className="text-slate-400 font-semibold mr-1.5">Task Prompt:</span>
          {testCase.agent_task_prompt}
        </p>
      </div>

      {/* Pinned Dependencies & Content Hash */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] font-mono text-slate-500 dark:text-slate-400 bg-slate-50/50 dark:bg-slate-800/20 p-2.5 rounded-xl border border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-1.5">
          <FileCheck className="w-3.5 h-3.5 text-indigo-500" />
          <span>Contract: {testCase.contract_id} (v{testCase.contract_version})</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Layers className="w-3.5 h-3.5 text-teal-500" />
          <span>Binding: {testCase.domain_id} (v{testCase.binding_version})</span>
        </div>
        {testCase.content_hash && (
          <div className="sm:col-span-2 flex items-center gap-1.5 text-slate-400 truncate">
            <Hash className="w-3.5 h-3.5 text-slate-400 shrink-0" />
            <span className="truncate">Hash: {testCase.content_hash}</span>
          </div>
        )}
      </div>

      {/* Validation Issues (if rejected or review needed) */}
      {testCase.validation_issues?.length > 0 && (
        <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 space-y-1 text-xs text-rose-800 dark:text-rose-300">
          <p className="font-bold flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
            Static Validation Issues ({testCase.validation_issues.length}):
          </p>
          <ul className="list-disc pl-5 space-y-0.5 text-[11px]">
            {testCase.validation_issues.map((issue, idx) => (
              <li key={idx}>
                <strong>{issue.issue_type}:</strong> {issue.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Action Buttons Row */}
      <div className="flex flex-wrap items-center justify-between gap-2 pt-3 border-t border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-2">
          {/* Validate Button */}
          {!isFrozen && (
            <button
              type="button"
              onClick={() => onValidateCase(testCase.case_id, testCase.case_version)}
              disabled={isValidating}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-50 transition-colors"
            >
              <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />
              <span>Validate</span>
            </button>
          )}

          {/* Freeze Button */}
          {!isFrozen && isValidated && (
            <button
              type="button"
              onClick={() => onFreezeCase(testCase.case_id, testCase.case_version)}
              disabled={isFreezing}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-sm disabled:opacity-50 transition-colors"
            >
              <Lock className="w-3.5 h-3.5" />
              <span>Freeze Snapshot</span>
            </button>
          )}

          {/* Payloads Inspector Modal Trigger */}
          <button
            type="button"
            onClick={() => onInspectPayloads(testCase)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/50 transition-colors"
          >
            <Eye className="w-3.5 h-3.5" />
            <span>Inspect 3 Payloads</span>
          </button>
        </div>

        {/* Execute Run Trigger (Only for FROZEN cases) */}
        {isFrozen ? (
          <button
            type="button"
            onClick={() => onOpenExecution(testCase)}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-sm transition-colors cursor-pointer"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>Execute Test</span>
          </button>
        ) : (
          <span className="text-[11px] text-slate-400 italic">
            Must freeze case to execute
          </span>
        )}
      </div>
    </div>
  );
}
