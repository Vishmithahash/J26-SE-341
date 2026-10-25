import React, { useState } from 'react';
import {
  CheckCircle2,
  AlertCircle,
  Eye,
  Play,
  Download,
  Bot,
  ChevronDown,
  ChevronUp,
  Activity,
  Compass,
  AlertTriangle,
} from 'lucide-react';

const CATEGORY_COLORS = {
  valid: {
    bg: 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800',
    dot: 'bg-emerald-500',
    label: 'Valid Path',
  },
  alternative: {
    bg: 'bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800',
    dot: 'bg-blue-500',
    label: 'Alternative Path',
  },
  negative: {
    bg: 'bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800',
    dot: 'bg-amber-500',
    label: 'Negative Rejection',
  },
  mutated: {
    bg: 'bg-purple-50 dark:bg-purple-950/50 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800',
    dot: 'bg-purple-500',
    label: 'Workflow Mutant',
  },
};

export const TestCaseListView = ({
  suite,
  cases,
  selectedCase,
  onSelectCase,
  onOpenCaseDetail,
  onRunCase,
  onOpenAgentPayload,
  categoryFilter,
  onCategoryFilterChange,
  readinessFilter,
  onReadinessFilterChange,
  onExportQASuite,
  onExportAgentPayloads,
  isLoading,
  isExecutingCase,
}) => {
  const [showDiagnostics, setShowDiagnostics] = useState(false);

  if (!suite) {
    return (
      <div className="p-8 text-center text-xs text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl bg-white/40 dark:bg-slate-900/20">
        Select a test suite above to inspect its test cases and diagnostics.
      </div>
    );
  }

  const diagnostics = suite.diagnostics || {};
  const plannedTransCov = diagnostics.planned_transition_coverage || {};
  const plannedGuardCov = diagnostics.planned_guard_coverage || {};
  const categoryCounts = suite.category_counts || {};

  return (
    <div className="space-y-4">
      {/* Suite Details Bar & Exports */}
      <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-900 dark:text-white font-mono">
                {suite.suite_id}
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                Model: {suite.model_id} v{suite.model_version}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
              Seed {suite.seed} • Generator: {suite.generator_version} • Total cases: {suite.total_cases}
            </p>
          </div>

          {/* Export Actions: Full QA Suite vs Allowlisted Agent Payloads */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => onExportQASuite(suite.suite_id)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-medium transition-colors"
              title="Export complete test suite containing private reference paths and assertions for authorized testers"
            >
              <Download className="w-3.5 h-3.5 text-indigo-500" />
              <span>Full QA Suite</span>
            </button>

            <button
              type="button"
              onClick={() => onExportAgentPayloads(suite.suite_id)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-indigo-200 dark:border-indigo-900/60 bg-indigo-50/50 dark:bg-indigo-950/30 hover:bg-indigo-100/50 dark:hover:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 text-xs font-medium transition-colors"
              title="Export allowlisted agent task payloads strictly excluding private reference paths and assertions"
            >
              <Bot className="w-3.5 h-3.5" />
              <span>Agent Tasks (Redacted)</span>
            </button>

            <button
              type="button"
              onClick={() => setShowDiagnostics(!showDiagnostics)}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900 text-xs transition-colors"
            >
              <Activity className="w-3.5 h-3.5" />
              <span>Diagnostics</span>
              {showDiagnostics ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
          </div>
        </div>

        {/* Collapsible Generation Diagnostics & Planned Coverage Panel */}
        {showDiagnostics && (
          <div className="pt-3 border-t border-slate-100 dark:border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <Compass className="w-3.5 h-3.5 text-indigo-500" />
                Generation Run Diagnostics (Symbolic Path Search)
              </span>
              <span className="text-[10px] text-slate-400 italic">
                Planned Generation Coverage (Distinct from Observed Execution Coverage)
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
              <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/40">
                <div className="text-[10px] text-slate-400">Paths Explored</div>
                <div className="font-bold text-slate-900 dark:text-white font-mono">
                  {diagnostics.paths_explored ?? '-'}
                </div>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/40">
                <div className="text-[10px] text-slate-400">Deduplicated</div>
                <div className="font-bold text-slate-900 dark:text-white font-mono">
                  {diagnostics.cases_deduplicated_count ?? 0}
                </div>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/40">
                <div className="text-[10px] text-slate-400">Infeasible Targets</div>
                <div className="font-bold text-slate-900 dark:text-white font-mono">
                  {diagnostics.infeasible_targets_count ?? 0}
                </div>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/40">
                <div className="text-[10px] text-slate-400">Depth Limit Reached</div>
                <div className="font-bold text-slate-900 dark:text-white font-mono">
                  {diagnostics.depth_limit_reached ? 'Yes' : 'No'}
                </div>
              </div>
            </div>

            {/* Planned Coverage Ratios */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
              <div className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                <div className="flex items-center justify-between text-[11px] mb-1">
                  <span className="font-semibold text-slate-700 dark:text-slate-300">
                    Planned Transition Coverage
                  </span>
                  <span className="font-mono text-indigo-600 dark:text-indigo-400 font-bold">
                    {plannedTransCov.coverage_percentage != null
                      ? `${Number(plannedTransCov.coverage_percentage).toFixed(1)}%`
                      : '-'}
                  </span>
                </div>
                <div className="text-[10px] text-slate-400 font-mono">
                  Covered {plannedTransCov.covered_transitions_count ?? 0} of {plannedTransCov.total_transitions ?? '-'} transitions
                </div>
              </div>

              <div className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                <div className="flex items-center justify-between text-[11px] mb-1">
                  <span className="font-semibold text-slate-700 dark:text-slate-300">
                    Planned Guard Coverage
                  </span>
                  <span className="font-mono text-emerald-600 dark:text-emerald-400 font-bold">
                    {plannedGuardCov.planned_guard_outcome_coverage_pct != null
                      ? `${Number(plannedGuardCov.planned_guard_outcome_coverage_pct).toFixed(1)}%`
                      : '-'}
                  </span>
                </div>
                <div className="text-[10px] text-slate-400 font-mono">
                  Covered {plannedGuardCov.covered_guards_count ?? 0} of {plannedGuardCov.total_guards_defined ?? '-'} guards
                  {plannedGuardCov.total_outcome_targets != null &&
                    ` · ${(plannedGuardCov.guards_planned_true_count ?? 0) + (plannedGuardCov.guards_planned_false_count ?? 0)} of ${plannedGuardCov.total_outcome_targets} true/false outcomes`}
                </div>
              </div>
            </div>

            {/* Unresolved Constraints / Limits Warning if any */}
            {(diagnostics.unresolved_constraints?.length > 0 || diagnostics.generation_limits_hit?.length > 0) && (
              <div className="p-2.5 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/60 text-xs text-amber-800 dark:text-amber-200 space-y-1">
                <div className="flex items-center gap-1.5 font-semibold text-[11px]">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                  <span>Generation Constraints & Limits</span>
                </div>
                {diagnostics.unresolved_constraints?.map((c, i) => (
                  <div key={i} className="text-[10px] font-mono">Unresolved: {c}</div>
                ))}
                {diagnostics.generation_limits_hit?.map((l, i) => (
                  <div key={i} className="text-[10px] font-mono">Limit hit: {l}</div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-1">
        {/* Category Filter Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
          <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mr-1">
            Category:
          </span>
          <button
            type="button"
            onClick={() => onCategoryFilterChange('')}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
              categoryFilter === ''
                ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'
                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200'
            }`}
          >
            All ({suite.total_cases})
          </button>

          {['valid', 'alternative', 'negative', 'mutated'].map((cat) => {
            const count = categoryCounts[cat] || 0;
            const isSelected = categoryFilter === cat;
            const meta = CATEGORY_COLORS[cat];
            return (
              <button
                key={cat}
                type="button"
                onClick={() => onCategoryFilterChange(isSelected ? '' : cat)}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors border ${
                  isSelected
                    ? meta.bg
                    : 'border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                <span>{meta.label}</span>
                <span className="text-[10px] font-mono opacity-80">({count})</span>
              </button>
            );
          })}
        </div>

        {/* Readiness Filter */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
            Readiness:
          </span>
          <select
            value={readinessFilter}
            onChange={(e) => onReadinessFilterChange(e.target.value)}
            className="px-2.5 py-1 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-xs text-slate-700 dark:text-slate-300"
          >
            <option value="">All Statuses</option>
            <option value="TEST_READY">Ready Only</option>
            <option value="TEST_NOT_READY">Not Ready</option>
          </select>
        </div>
      </div>

      {/* Case List Table / Cards */}
      {isLoading ? (
        <div className="p-8 text-center text-xs text-slate-500">
          <div className="w-5 h-5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          Loading test cases...
        </div>
      ) : cases?.length === 0 ? (
        <div className="p-8 text-center text-xs text-slate-500 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl bg-white/40 dark:bg-slate-900/20">
          No test cases matching current filters.
        </div>
      ) : (
        <div className="space-y-2">
          {cases.map((c) => {
            const isSelected = selectedCase?.test_id === c.test_id;
            const categoryMeta = CATEGORY_COLORS[c.category] || CATEGORY_COLORS.valid;
            const isReady = c.is_ready;

            return (
              <div
                key={c.test_id}
                onClick={() => onSelectCase(c)}
                className={`p-3.5 rounded-xl border transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 cursor-pointer ${
                  isSelected
                    ? 'border-indigo-600 dark:border-indigo-500 bg-indigo-50/30 dark:bg-indigo-950/20 shadow-2xs'
                    : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-slate-300 dark:hover:border-slate-700'
                }`}
              >
                {/* Left: Metadata & Task */}
                <div className="space-y-1.5 flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-bold text-slate-900 dark:text-white font-mono">
                      {c.test_id}
                    </span>

                    {/* Category Badge */}
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border flex items-center gap-1 ${categoryMeta.bg}`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${categoryMeta.dot}`} />
                      <span>{categoryMeta.label}</span>
                    </span>

                    {/* Execution Mode Badge */}
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${
                        c.execution_mode === 'live_agent'
                          ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300'
                          : 'bg-purple-50 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300'
                      }`}
                    >
                      {c.execution_mode === 'live_agent' ? 'Live Agent Task' : 'Synthetic Evaluator Mutant'}
                    </span>

                    {/* Readiness Status */}
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded-full flex items-center gap-1 ${
                        isReady
                          ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300'
                          : 'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300'
                      }`}
                    >
                      {isReady ? (
                        <>
                          <CheckCircle2 className="w-3 h-3" />
                          <span>Ready</span>
                        </>
                      ) : (
                        <>
                          <AlertCircle className="w-3 h-3" />
                          <span>Not Ready</span>
                        </>
                      )}
                    </span>
                  </div>

                  {/* Task Prompt Snippet */}
                  <div className="text-xs text-slate-700 dark:text-slate-300 font-medium truncate">
                    {c.task}
                  </div>

                  <div className="text-[10px] text-slate-400 flex items-center gap-3">
                    <span>Fixture: <code className="font-mono">{c.fixture_ref}</code></span>
                    {c.seed != null && <span>Seed: <code className="font-mono">{c.seed}</code></span>}
                  </div>
                </div>

                {/* Right: Quick Action Buttons */}
                <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectCase(c);
                      onOpenCaseDetail(c);
                    }}
                    className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs flex items-center gap-1 transition-colors"
                    title="Inspect complete test definition, oracle assertions, and mutation provenance"
                  >
                    <Eye className="w-3.5 h-3.5 text-indigo-500" />
                    <span className="hidden sm:inline">Inspect</span>
                  </button>

                  {c.execution_mode === 'live_agent' && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectCase(c);
                        onOpenAgentPayload(c);
                      }}
                      className="p-1.5 rounded-lg border border-indigo-200 dark:border-indigo-900/60 bg-indigo-50/50 dark:bg-indigo-950/30 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100/50 text-xs flex items-center gap-1 transition-colors"
                      title="Inspect allowlisted agent task payload (proves private reference oracles are omitted)"
                    >
                      <Bot className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">Agent View</span>
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectCase(c);
                      onRunCase(suite.suite_id, c.test_id);
                    }}
                    disabled={isExecutingCase}
                    className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-semibold flex items-center gap-1 shadow-2xs transition-colors"
                    title="Execute test case with backend orchestration pipeline"
                  >
                    <Play className="w-3 h-3 fill-current" />
                    <span>Run</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
