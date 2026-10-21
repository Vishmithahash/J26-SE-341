import React from 'react';
import {
  Layers,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Hash,
} from 'lucide-react';

export const TestSuiteListView = ({
  suites,
  selectedSuite,
  onSelectSuite,
  onOpenGenerateModal,
  isLoading,
  _suiteReadiness,
  hasApprovedModel,
}) => {
  return (
    <div className="space-y-4">
      {/* Top Action Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs">
        <div>
          <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Layers className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            Generated Test Suites ({suites?.length || 0})
          </h2>
          <p className="text-[11px] text-slate-500 dark:text-slate-400">
            Systematic workflow test suites generated from approved reference models
          </p>
        </div>

        <button
          type="button"
          onClick={onOpenGenerateModal}
          disabled={!hasApprovedModel}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-semibold shadow-xs transition-colors shrink-0"
          title={!hasApprovedModel ? 'Requires at least one approved model version' : 'Generate automatic test suite'}
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>Generate New Suite</span>
        </button>
      </div>

      {isLoading && suites?.length === 0 ? (
        <div className="p-12 text-center text-xs text-slate-500">
          <div className="w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          Loading test suites...
        </div>
      ) : suites?.length === 0 ? (
        <div className="p-8 rounded-xl border border-dashed border-slate-200 dark:border-slate-800 text-center space-y-3 bg-white/40 dark:bg-slate-900/20">
          <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 mx-auto flex items-center justify-center">
            <Layers className="w-5 h-5" />
          </div>
          <div className="space-y-1">
            <div className="text-xs font-semibold text-slate-800 dark:text-slate-200">
              No Test Suites Generated Yet
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 max-w-sm mx-auto">
              Select an approved workflow model version and generate coverage-guided test cases
              with alternatives, negative rejections, and evaluator mutants.
            </p>
          </div>
          {hasApprovedModel ? (
            <button
              type="button"
              onClick={onOpenGenerateModal}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 text-indigo-600 dark:text-indigo-400 text-xs font-medium transition-colors"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Generate First Suite</span>
            </button>
          ) : (
            <div className="text-[11px] text-amber-600 dark:text-amber-400 font-medium">
              Requires an approved model in the Models Workspace first.
            </div>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {suites.map((s) => {
            const isSelected = selectedSuite?.suite_id === s.suite_id;
            const categoryCounts = s.category_counts || {};

            return (
              <div
                key={s.suite_id}
                onClick={() => onSelectSuite(s)}
                className={`p-4 rounded-xl border text-left cursor-pointer transition-all space-y-3 ${
                  isSelected
                    ? 'border-indigo-600 dark:border-indigo-500 bg-indigo-50/40 dark:bg-indigo-950/20 ring-1 ring-indigo-500 shadow-sm'
                    : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-slate-300 dark:hover:border-slate-700'
                }`}
              >
                {/* Suite Header */}
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-xs font-bold text-slate-900 dark:text-white font-mono truncate max-w-[200px]" title={s.suite_id}>
                      {s.suite_id}
                    </div>
                    <div className="text-[10px] text-slate-500 dark:text-slate-400 flex items-center gap-1 mt-0.5">
                      <span>Model:</span>
                      <span className="font-semibold text-slate-700 dark:text-slate-300">
                        {s.model_id}
                      </span>
                      <span className="px-1 py-0.2 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 font-mono">
                        v{s.model_version}
                      </span>
                    </div>
                  </div>

                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0 flex items-center gap-1 ${
                      s.not_ready_cases_count === 0 && s.ready_cases_count > 0
                        ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
                        : 'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-200 dark:border-amber-800'
                    }`}
                  >
                    {s.not_ready_cases_count === 0 && s.ready_cases_count > 0 ? (
                      <>
                        <CheckCircle2 className="w-3 h-3" />
                        <span>Ready</span>
                      </>
                    ) : (
                      <>
                        <AlertCircle className="w-3 h-3" />
                        <span>Partial</span>
                      </>
                    )}
                  </span>
                </div>

                {/* Metrics Breakdown */}
                <div className="grid grid-cols-4 gap-1.5 p-2 rounded-lg bg-slate-50 dark:bg-slate-800/40 text-center">
                  <div>
                    <div className="text-[9px] text-slate-400 uppercase font-semibold">Total</div>
                    <div className="text-xs font-bold text-slate-900 dark:text-white font-mono">
                      {s.total_cases}
                    </div>
                  </div>
                  <div>
                    <div className="text-[9px] text-emerald-600 dark:text-emerald-400 uppercase font-semibold">Valid</div>
                    <div className="text-xs font-bold text-emerald-700 dark:text-emerald-300 font-mono">
                      {categoryCounts.valid || 0}
                    </div>
                  </div>
                  <div>
                    <div className="text-[9px] text-blue-600 dark:text-blue-400 uppercase font-semibold">Alt/Neg</div>
                    <div className="text-xs font-bold text-blue-700 dark:text-blue-300 font-mono">
                      {(categoryCounts.alternative || 0) + (categoryCounts.negative || 0)}
                    </div>
                  </div>
                  <div>
                    <div className="text-[9px] text-purple-600 dark:text-purple-400 uppercase font-semibold">Mutant</div>
                    <div className="text-xs font-bold text-purple-700 dark:text-purple-300 font-mono">
                      {categoryCounts.mutated || 0}
                    </div>
                  </div>
                </div>

                {/* Footer Metadata */}
                <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-100 dark:border-slate-800/80">
                  <span className="flex items-center gap-1 font-mono">
                    <Hash className="w-3 h-3" />
                    Seed {s.seed}
                  </span>
                  <span>
                    {s.created_at ? new Date(s.created_at).toLocaleDateString() : ''}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
