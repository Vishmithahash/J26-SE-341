import React, { useState } from 'react';
import {
  Activity,
  CheckCircle2,
  XCircle,
  Info,
  ChevronDown,
} from 'lucide-react';

export const ObservedCoverageViewer = ({
  coverage,
  modelId,
  modelVersion,
  isSuiteAggregate = false,
}) => {
  const [expandedMetric, setExpandedMetric] = useState(null);

  if (!coverage) {
    return (
      <div className="p-8 text-center text-xs text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl bg-white/40 dark:bg-slate-900/20">
        Observed coverage data is not available for this run. Run an evaluation to observe coverage.
      </div>
    );
  }

  const toggleMetric = (key) => {
    setExpandedMetric((prev) => (prev === key ? null : key));
  };

  const transCov = coverage.transition_coverage || null;
  const guardCov = coverage.guard_outcome_coverage || null;
  const pathCov = coverage.selected_path_coverage || null;
  const effectCov = coverage.state_effect_coverage || null;

  // Safe percentage helper: handles 0 denominator as "N/A"
  const renderPercentage = (num, den, ratio) => {
    if (den === 0 || den == null) {
      return { text: 'N/A (No targets)', isNA: true };
    }
    const pct = ratio != null ? (ratio * 100).toFixed(1) : ((num / den) * 100).toFixed(1);
    return { text: `${pct}%`, isNA: false };
  };

  return (
    <div className="space-y-4">
      {/* Scope and Separation Notice */}
      <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-2">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <h3 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
              {isSuiteAggregate ? 'Suite Aggregate Observed Coverage' : 'Run-Level Observed Workflow Coverage'}
            </h3>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 self-start sm:self-auto">
            Pinned Model: {coverage.model_id || modelId} v{coverage.model_version || modelVersion}
          </span>
        </div>
        <p className="text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
          Observed coverage measures Extended Finite State Machine model elements physically exercised by execution evidence.
          Planned test-suite generation coverage is maintained separately. Separate metrics are preferred over composite scores in accordance with backend specification.
        </p>
      </div>

      {/* 4 Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Metric 1: Transition Coverage */}
        {transCov && (
          <div
            onClick={() => toggleMetric('transitions')}
            className={`p-4 rounded-xl border cursor-pointer transition-all ${
              expandedMetric === 'transitions'
                ? 'border-indigo-600 dark:border-indigo-400 bg-indigo-50/20 dark:bg-indigo-950/20'
                : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-slate-300'
            }`}
          >
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-slate-700 dark:text-slate-300 uppercase text-[10px]">
                Transition Coverage
              </span>
              <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${expandedMetric === 'transitions' ? 'rotate-180' : ''}`} />
            </div>

            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-xl font-bold font-mono text-indigo-600 dark:text-indigo-400">
                {renderPercentage(transCov.numerator, transCov.denominator, transCov.coverage_ratio).text}
              </span>
              <span className="text-xs font-mono text-slate-500">
                ({transCov.numerator} / {transCov.denominator})
              </span>
            </div>

            <div className="mt-2 text-[10px] text-slate-400">
              {transCov.uncovered_targets?.length || 0} uncovered transitions
            </div>
          </div>
        )}

        {/* Metric 2: Guard Outcome Coverage */}
        {guardCov && (
          <div
            onClick={() => toggleMetric('guards')}
            className={`p-4 rounded-xl border cursor-pointer transition-all ${
              expandedMetric === 'guards'
                ? 'border-indigo-600 dark:border-indigo-400 bg-indigo-50/20 dark:bg-indigo-950/20'
                : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-slate-300'
            }`}
          >
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-slate-700 dark:text-slate-300 uppercase text-[10px]">
                Guard Outcome Coverage
              </span>
              <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${expandedMetric === 'guards' ? 'rotate-180' : ''}`} />
            </div>

            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-xl font-bold font-mono text-indigo-600 dark:text-indigo-400">
                {renderPercentage(guardCov.numerator, guardCov.denominator, guardCov.coverage_ratio).text}
              </span>
              <span className="text-xs font-mono text-slate-500">
                ({guardCov.numerator} / {guardCov.denominator})
              </span>
            </div>

            <div className="mt-2 text-[10px] text-slate-400 flex items-center gap-2">
              <span className="text-emerald-600 dark:text-emerald-400">T: {guardCov.guards_true_count || 0}</span>
              <span className="text-amber-600 dark:text-amber-400">F: {guardCov.guards_false_count || 0}</span>
              <span className="text-slate-500">?: {guardCov.guards_unknown_count || 0}</span>
            </div>
          </div>
        )}

        {/* Metric 3: Selected Path Coverage */}
        {pathCov && (
          <div
            onClick={() => toggleMetric('paths')}
            className={`p-4 rounded-xl border cursor-pointer transition-all ${
              expandedMetric === 'paths'
                ? 'border-indigo-600 dark:border-indigo-400 bg-indigo-50/20 dark:bg-indigo-950/20'
                : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-slate-300'
            }`}
          >
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-slate-700 dark:text-slate-300 uppercase text-[10px]">
                Selected-Path Coverage
              </span>
              <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${expandedMetric === 'paths' ? 'rotate-180' : ''}`} />
            </div>

            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-xl font-bold font-mono text-indigo-600 dark:text-indigo-400">
                {renderPercentage(pathCov.numerator, pathCov.denominator, pathCov.coverage_ratio).text}
              </span>
              <span className="text-xs font-mono text-slate-500">
                ({pathCov.numerator} / {pathCov.denominator})
              </span>
            </div>

            <div className="mt-2 text-[10px] text-slate-400">
              {pathCov.uncovered_paths?.length || 0} uncovered paths
            </div>
          </div>
        )}

        {/* Metric 4: State-Effect Coverage */}
        {effectCov && (
          <div
            onClick={() => toggleMetric('effects')}
            className={`p-4 rounded-xl border cursor-pointer transition-all ${
              expandedMetric === 'effects'
                ? 'border-indigo-600 dark:border-indigo-400 bg-indigo-50/20 dark:bg-indigo-950/20'
                : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-slate-300'
            }`}
          >
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-slate-700 dark:text-slate-300 uppercase text-[10px]">
                State-Effect Coverage
              </span>
              <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${expandedMetric === 'effects' ? 'rotate-180' : ''}`} />
            </div>

            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-xl font-bold font-mono text-indigo-600 dark:text-indigo-400">
                {renderPercentage(effectCov.numerator, effectCov.denominator, effectCov.coverage_ratio).text}
              </span>
              <span className="text-xs font-mono text-slate-500">
                ({effectCov.numerator} / {effectCov.denominator})
              </span>
            </div>

            <div className="mt-2 text-[10px] text-slate-400">
              {effectCov.unknown_checks?.length || 0} unknown checks
            </div>
          </div>
        )}
      </div>

      {/* Expanded Drill-Down Breakdown */}
      {expandedMetric && (
        <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-950/40 space-y-3 text-xs">
          {/* Transitions Drill-Down */}
          {expandedMetric === 'transitions' && transCov && (
            <div className="space-y-3">
              <h4 className="font-bold text-slate-900 dark:text-white uppercase text-[11px] tracking-wider">
                Transition Coverage Targets Breakdown
              </h4>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {/* Covered Transitions */}
                <div className="p-3 rounded-lg border border-emerald-200 dark:border-emerald-800 bg-emerald-50/40 dark:bg-emerald-950/20 space-y-1.5">
                  <span className="font-semibold text-emerald-800 dark:text-emerald-300 flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    Covered Transitions ({transCov.covered_targets?.length || 0})
                  </span>
                  <div className="flex flex-wrap gap-1 max-h-36 overflow-y-auto font-mono text-[10px]">
                    {transCov.covered_targets?.map((t, i) => (
                      <span key={i} className="px-1.5 py-0.5 rounded bg-white dark:bg-slate-900 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Uncovered Transitions */}
                <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-1.5">
                  <span className="font-semibold text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
                    <XCircle className="w-3.5 h-3.5 text-rose-500" />
                    Uncovered Transitions ({transCov.uncovered_targets?.length || 0})
                  </span>
                  <div className="flex flex-wrap gap-1 max-h-36 overflow-y-auto font-mono text-[10px]">
                    {transCov.uncovered_targets?.map((t, i) => (
                      <span key={i} className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Infeasible Targets if reported */}
              {transCov.proven_infeasible_targets?.length > 0 && (
                <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 text-[11px] text-amber-800 dark:text-amber-200">
                  <span className="font-bold">Proven Infeasible Transitions: </span>
                  {transCov.proven_infeasible_targets.map((inf, i) => (
                    <span key={i} className="font-mono ml-1">{JSON.stringify(inf)}</span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Guards Drill-Down */}
          {expandedMetric === 'guards' && guardCov && (
            <div className="space-y-3">
              <h4 className="font-bold text-slate-900 dark:text-white uppercase text-[11px] tracking-wider">
                Guard Outcome Coverage (TRUE vs FALSE Outcomes)
              </h4>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="p-3 rounded-lg border border-emerald-200 dark:border-emerald-800 bg-emerald-50/40 dark:bg-emerald-950/20">
                  <span className="text-[10px] text-emerald-700 uppercase font-semibold">Guards Evaluated TRUE</span>
                  <div className="text-lg font-bold font-mono text-emerald-800 dark:text-emerald-300 mt-1">
                    {guardCov.guards_true_count || 0}
                  </div>
                </div>

                <div className="p-3 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50/40 dark:bg-amber-950/20">
                  <span className="text-[10px] text-amber-700 uppercase font-semibold">Guards Evaluated FALSE</span>
                  <div className="text-lg font-bold font-mono text-amber-800 dark:text-amber-300 mt-1">
                    {guardCov.guards_false_count || 0}
                  </div>
                </div>

                <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold">Guards UNKNOWN / Ambiguous</span>
                  <div className="text-lg font-bold font-mono text-slate-600 dark:text-slate-400 mt-1">
                    {guardCov.guards_unknown_count || 0}
                  </div>
                </div>
              </div>

              <div className="text-[11px] text-slate-500">
                Total Outcome Targets: {guardCov.total_outcome_targets} • Deduplicated: {guardCov.repeated_observations_deduplicated ? 'Yes' : 'No'}
              </div>
            </div>
          )}

          {/* Paths Drill-Down */}
          {expandedMetric === 'paths' && pathCov && (
            <div className="space-y-3">
              <h4 className="font-bold text-slate-900 dark:text-white uppercase text-[11px] tracking-wider">
                Selected-Path Catalogue Coverage
              </h4>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-1">
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    Completed Catalogue Paths ({pathCov.completed_paths?.length || 0}):
                  </span>
                  <div className="flex flex-wrap gap-1 font-mono text-[10px]">
                    {pathCov.completed_paths?.map((p, i) => (
                      <span key={i} className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-200">
                        {p}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-1">
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    Uncovered Catalogue Paths ({pathCov.uncovered_paths?.length || 0}):
                  </span>
                  <div className="flex flex-wrap gap-1 font-mono text-[10px]">
                    {pathCov.uncovered_paths?.map((p, i) => (
                      <span key={i} className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                        {p}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Effects Drill-Down */}
          {expandedMetric === 'effects' && effectCov && (
            <div className="space-y-3">
              <h4 className="font-bold text-slate-900 dark:text-white uppercase text-[11px] tracking-wider">
                State-Effect Obligations & Defect-Detection Note
              </h4>

              <div className="p-3 rounded-lg bg-indigo-50/50 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-900/60 text-[11px] text-indigo-900 dark:text-indigo-200 flex items-start gap-2">
                <Info className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold">Important Defect-Detection Note: </span>
                  State-effect coverage measures whether declared database/state effect obligations were exercised with sufficient observations.
                  It is <span className="underline font-semibold">not</span> identical to defect-detection accuracy. Defect-detection accuracy is: {effectCov.fault_detection_status}.
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2 font-mono text-[11px]">
                <div className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                  <span className="text-slate-400 text-[10px] uppercase">Satisfied:</span>
                  <div className="text-emerald-600 font-bold mt-1">{effectCov.satisfied_checks?.length || 0}</div>
                </div>
                <div className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                  <span className="text-slate-400 text-[10px] uppercase">Violated:</span>
                  <div className="text-rose-600 font-bold mt-1">{effectCov.violated_checks?.length || 0}</div>
                </div>
                <div className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                  <span className="text-slate-400 text-[10px] uppercase">Unknown:</span>
                  <div className="text-slate-500 font-bold mt-1">{effectCov.unknown_checks?.length || 0}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
