/**
 * Component 4 (C4) - Test Case List Component
 * Filterable, searchable catalog of generated policy test cases.
 */

import React, { useState, useMemo } from 'react';
import {
  Search,
  RotateCw,
  FolderOpen,
} from 'lucide-react';
import { TestCaseCard } from './TestCaseCard.jsx';
import { TEST_CASE_KINDS, CASE_LIFECYCLE_STATES } from '../../api/types.js';

export function TestCaseList({
  testCases,
  onValidateCase,
  onFreezeCase,
  onInspectPayloads,
  onOpenExecution,
  onRefresh,
  isLoadingCases,
  isValidatingCase,
  isFreezingCase,
}) {
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [lifecycleFilter, setLifecycleFilter] = useState('ALL');

  const filteredCases = useMemo(() => {
    return testCases.filter((c) => {
      if (categoryFilter !== 'ALL' && c.test_kind !== categoryFilter) return false;
      if (lifecycleFilter !== 'ALL' && c.lifecycle_state !== lifecycleFilter) return false;

      if (searchTerm.trim()) {
        const query = searchTerm.toLowerCase();
        const matchesId = c.case_id?.toLowerCase().includes(query);
        const matchesRule = c.target_rule_id?.toLowerCase().includes(query);
        const matchesPrompt = c.agent_task_prompt?.toLowerCase().includes(query);
        if (!matchesId && !matchesRule && !matchesPrompt) return false;
      }

      return true;
    });
  }, [testCases, categoryFilter, lifecycleFilter, searchTerm]);

  const metrics = useMemo(() => {
    const total = testCases.length;
    const benign = testCases.filter((c) => c.test_kind === TEST_CASE_KINDS.BENIGN).length;
    const challenge = testCases.filter(
      (c) => c.test_kind === TEST_CASE_KINDS.DIRECT_POLICY_CHALLENGE
    ).length;
    const injection = testCases.filter(
      (c) => c.test_kind === TEST_CASE_KINDS.INDIRECT_PROMPT_INJECTION
    ).length;
    const frozen = testCases.filter((c) => c.lifecycle_state === CASE_LIFECYCLE_STATES.FROZEN).length;
    const validated = testCases.filter(
      (c) => c.lifecycle_state === CASE_LIFECYCLE_STATES.VALIDATED
    ).length;
    return { total, benign, challenge, injection, frozen, validated };
  }, [testCases]);

  return (
    <div className="space-y-5">
      {/* Header and Summary Metrics */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded-lg bg-indigo-100 dark:bg-indigo-950/70 text-indigo-600 dark:text-indigo-400 font-bold text-xs flex items-center justify-center">
              2
            </span>
            <h3 className="text-base font-bold text-slate-900 dark:text-white">
              Generated Policy Test Cases ({testCases.length})
            </h3>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Independently validate generated cases, freeze immutable snapshots, and inspect payload boundaries.
          </p>
        </div>

        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={isLoadingCases}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isLoadingCases ? 'animate-spin text-indigo-600' : ''}`} />
            <span>Refresh</span>
          </button>
        )}
      </div>

      {/* Metrics Bar */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="px-3 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-medium">
          Total: <strong>{metrics.total}</strong>
        </span>
        <span className="px-3 py-1 rounded-lg bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 border border-emerald-200/50">
          Benign: <strong>{metrics.benign}</strong>
        </span>
        <span className="px-3 py-1 rounded-lg bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-300 border border-amber-200/50">
          Direct Challenge: <strong>{metrics.challenge}</strong>
        </span>
        <span className="px-3 py-1 rounded-lg bg-rose-50 dark:bg-rose-950/50 text-rose-700 dark:text-rose-300 border border-rose-200/50">
          Indirect Injection: <strong>{metrics.injection}</strong>
        </span>
        <span className="px-3 py-1 rounded-lg bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 border border-indigo-200/50 font-semibold">
          Frozen: <strong>{metrics.frozen}</strong>
        </span>
      </div>

      {/* Filters and Search Toolbar */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4 shadow-sm flex flex-col md:flex-row items-center gap-3">
        <div className="relative flex-1 w-full">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search by case ID, target rule, or prompt text..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        <div className="flex items-center gap-2 w-full md:w-auto">
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-700 dark:text-slate-300 font-medium"
          >
            <option value="ALL">All Categories</option>
            <option value={TEST_CASE_KINDS.BENIGN}>Benign Controls</option>
            <option value={TEST_CASE_KINDS.DIRECT_POLICY_CHALLENGE}>Direct Challenges</option>
            <option value={TEST_CASE_KINDS.INDIRECT_PROMPT_INJECTION}>Indirect Injections</option>
          </select>

          <select
            value={lifecycleFilter}
            onChange={(e) => setLifecycleFilter(e.target.value)}
            className="px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-700 dark:text-slate-300 font-medium"
          >
            <option value="ALL">All Lifecycle States</option>
            <option value={CASE_LIFECYCLE_STATES.FROZEN}>Frozen (Executable)</option>
            <option value={CASE_LIFECYCLE_STATES.VALIDATED}>Validated</option>
            <option value={CASE_LIFECYCLE_STATES.DRAFT}>Draft</option>
            <option value={CASE_LIFECYCLE_STATES.NEEDS_REVIEW}>Needs Review</option>
            <option value={CASE_LIFECYCLE_STATES.REJECTED}>Rejected</option>
          </select>
        </div>
      </div>

      {/* Test Cases List */}
      {filteredCases.length === 0 ? (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-10 text-center space-y-3">
          <FolderOpen className="w-10 h-10 text-slate-300 dark:text-slate-700 mx-auto" />
          <h4 className="text-sm font-bold text-slate-700 dark:text-slate-300">
            {testCases.length === 0
              ? 'No policy test cases generated yet'
              : 'No test cases match your filter criteria'}
          </h4>
          <p className="text-xs text-slate-500 dark:text-slate-400 max-w-md mx-auto">
            {testCases.length === 0
              ? 'Configure generation parameters in the form above and click "Generate Test Cases Batch" to create policy test cases.'
              : 'Try clearing the search query or adjusting the category and lifecycle filters.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filteredCases.map((tc) => (
            <TestCaseCard
              key={`${tc.case_id}-v${tc.case_version}`}
              testCase={tc}
              onValidateCase={onValidateCase}
              onFreezeCase={onFreezeCase}
              onInspectPayloads={onInspectPayloads}
              onOpenExecution={onOpenExecution}
              isValidating={isValidatingCase}
              isFreezing={isFreezingCase}
            />
          ))}
        </div>
      )}
    </div>
  );
}
