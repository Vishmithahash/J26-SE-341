import React, { useState, useMemo } from 'react';
import {
  Workflow,
  Search,
  Filter,
  RefreshCw,
  Eye,
  CheckCircle2,
  XCircle,
  HelpCircle,
  ShieldCheck,
  AlertCircle,
  Play,
} from 'lucide-react';
import { useC3Evaluations } from '../hooks/useC3Evaluations';
import { useC3MatchedPairs } from '../hooks/useC3MatchedPairs';
import { C3Badge } from './C3Badge';
import { C3ExplanationEvidenceView } from './C3ExplanationEvidenceView';
import {
  DEMO_EVALUATION_PASS_COMPLETED,
  DEMO_EVALUATION_PASS_GRACEFUL,
  DEMO_EVALUATION_FAIL,
  DEMO_EVALUATION_INCONCLUSIVE,
  DEMO_EVALUATION_NOT_EVALUATED,
  DEMO_C2_FACTS,
} from '../fixtures';

export const C3EvaluationsViewer = ({ projectId }) => {
  const [verdictFilter, setVerdictFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEvaluation, setSelectedEvaluation] = useState(null);
  const [isComputeModalOpen, setIsComputeModalOpen] = useState(false);
  const [selectedPairIdForCompute, setSelectedPairIdForCompute] = useState('');
  const [useCustomC2Facts, setUseCustomC2Facts] = useState(true);
  const [useDemoFallback] = useState(false);

  const queryFilters = useMemo(() => {
    const f = {};
    if (verdictFilter !== 'ALL' && verdictFilter !== 'NOT_EVALUATED') {
      f.recoveryVerdict = verdictFilter;
    }
    return f;
  }, [verdictFilter]);

  const {
    evaluations: serverEvaluations,
    verdictCounts: serverCounts,
    isLoading,
    isDbUnavailable,
    refetch,
    isComputing,
    computeError,
    computeAndPersistEvaluation,
  } = useC3Evaluations(projectId, queryFilters);

  // Retrieve existing pairs for compute evaluation selection
  const { pairs: existingPairs } = useC3MatchedPairs(projectId);

  // If DB is offline or fallback toggled, use authoritative demonstration presets
  const demoEvaluations = useMemo(
    () => [
      DEMO_EVALUATION_PASS_COMPLETED,
      DEMO_EVALUATION_PASS_GRACEFUL,
      DEMO_EVALUATION_FAIL,
      DEMO_EVALUATION_INCONCLUSIVE,
      DEMO_EVALUATION_NOT_EVALUATED,
    ],
    []
  );

  const isUsingFallback = (isDbUnavailable && serverEvaluations.length === 0) || useDemoFallback;
  const activeEvaluations = isUsingFallback ? demoEvaluations : serverEvaluations;

  // Filter evaluations by search and client-side verdict filter if using fallback
  const filteredEvaluations = useMemo(() => {
    return activeEvaluations.filter((ev) => {
      const v = ev.recovery_verdict;
      if (verdictFilter === 'NOT_EVALUATED') {
        if (v !== null && v !== undefined) return false;
      } else if (verdictFilter !== 'ALL') {
        if (v !== verdictFilter) return false;
      }

      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesId = (ev.evaluation_id || '').toLowerCase().includes(q);
        const matchesPair = (ev.pair_id || '').toLowerCase().includes(q);
        const matchesCase = (ev.case_id || '').toLowerCase().includes(q);
        const matchesFirstRule = (ev.first_violated_rule || '').toLowerCase().includes(q);
        return matchesId || matchesPair || matchesCase || matchesFirstRule;
      }
      return true;
    });
  }, [activeEvaluations, verdictFilter, searchQuery]);

  // Compute breakdown for stat cards
  const displayCounts = useMemo(() => {
    if (isUsingFallback) {
      let passCompleted = 0;
      let passGraceful = 0;
      let fail = 0;
      let inconclusive = 0;
      let notEvaluated = 0;

      activeEvaluations.forEach((ev) => {
        const v = ev.recovery_verdict;
        if (v === 'PASS_COMPLETED') passCompleted += 1;
        else if (v === 'PASS_GRACEFUL') passGraceful += 1;
        else if (v === 'FAIL') fail += 1;
        else if (v === 'INCONCLUSIVE') inconclusive += 1;
        else notEvaluated += 1;
      });

      return {
        passCompleted,
        passGraceful,
        fail,
        inconclusive,
        notEvaluated,
        eligibleEvaluatedCount: passCompleted + passGraceful + fail + inconclusive,
      };
    }
    return serverCounts;
  }, [isUsingFallback, activeEvaluations, serverCounts]);

  const handleComputeSubmit = async (e) => {
    e.preventDefault();
    if (!selectedPairIdForCompute) return;
    try {
      const c2Facts = useCustomC2Facts ? DEMO_C2_FACTS : [];
      await computeAndPersistEvaluation({
        pairId: selectedPairIdForCompute,
        c2Facts,
      });
      setIsComputeModalOpen(false);
      setSelectedPairIdForCompute('');
    } catch {
      // Error is captured in computeError
    }
  };

  return (
    <div className="space-y-6">
      {/* DB Offline or Demonstration Mode Notice */}
      {isDbUnavailable && (
        <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 text-xs text-amber-800 dark:text-amber-200 flex items-start justify-between gap-3 flex-wrap">
          <div className="flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">PostgreSQL Persistence Unavailable (503):</span>
              <p className="mt-0.5 text-amber-700 dark:text-amber-300">
                Displaying authoritative demonstration evaluation records. To persist new recovery evaluations, ensure PostgreSQL is running.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => refetch()}
            className="px-2.5 py-1 rounded-lg bg-amber-200 dark:bg-amber-900 text-amber-900 dark:text-amber-100 font-semibold hover:bg-amber-300 transition-colors"
          >
            Retry Connection
          </button>
        </div>
      )}

      {/* Primary Recovery Verdict Metrics Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {/* 1. Eligible Evaluated */}
        <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
            Eligible Evaluated
          </span>
          <div className="text-xl font-bold text-slate-900 dark:text-white mt-1">
            {displayCounts.eligibleEvaluatedCount}
          </div>
          <span className="text-[10px] text-slate-400 mt-0.5 block">
            Confirmed exposure trials
          </span>
        </div>

        {/* 2. Pass: Completed */}
        <div className="p-3.5 rounded-xl bg-emerald-50/50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-900/60 shadow-xs">
          <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider block flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" />
            Pass: Completed
          </span>
          <div className="text-xl font-bold text-emerald-700 dark:text-emerald-300 mt-1">
            {displayCounts.passCompleted}
          </div>
          <span className="text-[10px] text-emerald-600/80 dark:text-emerald-400/80 mt-0.5 block">
            Clean recovery completed
          </span>
        </div>

        {/* 3. Pass: Graceful */}
        <div className="p-3.5 rounded-xl bg-sky-50/50 dark:bg-sky-950/20 border border-sky-200 dark:border-sky-900/60 shadow-xs">
          <span className="text-[10px] font-semibold text-sky-600 dark:text-sky-400 uppercase tracking-wider block flex items-center gap-1">
            <ShieldCheck className="w-3 h-3" />
            Pass: Graceful
          </span>
          <div className="text-xl font-bold text-sky-700 dark:text-sky-300 mt-1">
            {displayCounts.passGraceful}
          </div>
          <span className="text-[10px] text-sky-600/80 dark:text-sky-400/80 mt-0.5 block">
            Permitted safe halt
          </span>
        </div>

        {/* 4. Fail */}
        <div className="p-3.5 rounded-xl bg-rose-50/50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/60 shadow-xs">
          <span className="text-[10px] font-semibold text-rose-600 dark:text-rose-400 uppercase tracking-wider block flex items-center gap-1">
            <XCircle className="w-3 h-3" />
            Fail
          </span>
          <div className="text-xl font-bold text-rose-700 dark:text-rose-300 mt-1">
            {displayCounts.fail}
          </div>
          <span className="text-[10px] text-rose-600/80 dark:text-rose-400/80 mt-0.5 block">
            Violated recovery rule
          </span>
        </div>

        {/* 5. Inconclusive */}
        <div className="p-3.5 rounded-xl bg-amber-50/50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/60 shadow-xs">
          <span className="text-[10px] font-semibold text-amber-600 dark:text-amber-400 uppercase tracking-wider block flex items-center gap-1">
            <HelpCircle className="w-3 h-3" />
            Inconclusive
          </span>
          <div className="text-xl font-bold text-amber-700 dark:text-amber-300 mt-1">
            {displayCounts.inconclusive}
          </div>
          <span className="text-[10px] text-amber-600/80 dark:text-amber-400/80 mt-0.5 block">
            Uncertain observations
          </span>
        </div>

        {/* 6. Not Evaluated (Kept separate!) */}
        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 shadow-xs">
          <span className="text-[10px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider block">
            Not Evaluated
          </span>
          <div className="text-xl font-bold text-slate-700 dark:text-slate-300 mt-1">
            {displayCounts.notEvaluated}
          </div>
          <span className="text-[10px] text-slate-400 mt-0.5 block">
            Ineligible (unreached/error)
          </span>
        </div>
      </div>

      {/* Control Bar: Search, Filters & Action Buttons */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 flex-1 min-w-[280px]">
          <div className="relative flex-1">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search by evaluation, case, pair ID, or violation..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 rounded-xl text-xs bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={verdictFilter}
              onChange={(e) => setVerdictFilter(e.target.value)}
              className="px-2.5 py-2 rounded-xl text-xs bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 focus:outline-hidden"
            >
              <option value="ALL">All Verdicts</option>
              <option value="PASS_COMPLETED">Pass: Completed</option>
              <option value="PASS_GRACEFUL">Pass: Graceful</option>
              <option value="FAIL">Fail</option>
              <option value="INCONCLUSIVE">Inconclusive</option>
              <option value="NOT_EVALUATED">Not Evaluated</option>
            </select>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isLoading}
            className="p-2 rounded-xl border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="Refresh evaluations"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>

          <button
            type="button"
            onClick={() => setIsComputeModalOpen(true)}
            className="px-3.5 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white flex items-center gap-1.5 shadow-xs transition-colors"
          >
            <Play className="w-3.5 h-3.5" />
            <span>Compute Recovery Evaluation</span>
          </button>
        </div>
      </div>

      {/* Evaluations Table */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 font-semibold text-slate-500 uppercase tracking-wider text-[10px]">
                <th className="py-3 px-4">Evaluation ID & Date</th>
                <th className="py-3 px-4">Recovery Verdict</th>
                <th className="py-3 px-4">Matched Pair & Case</th>
                <th className="py-3 px-4">First Violated Rule</th>
                <th className="py-3 px-4">Actor Attribution</th>
                <th className="py-3 px-4">Rule Results</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {isLoading && activeEvaluations.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-indigo-500" />
                    Loading recovery evaluations...
                  </td>
                </tr>
              ) : filteredEvaluations.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500 space-y-2">
                    <Workflow className="w-8 h-8 mx-auto text-slate-400" />
                    <div className="font-semibold text-slate-700 dark:text-slate-300">
                      No recovery evaluations found matching criteria
                    </div>
                    <p className="text-xs text-slate-400 max-w-sm mx-auto">
                      Compute an evaluation for an existing matched pair or load demonstration presets.
                    </p>
                  </td>
                </tr>
              ) : (
                filteredEvaluations.map((ev) => {
                  const evalObj = ev.evaluation || ev;
                  const verdict = ev.recovery_verdict || evalObj.recovery_verdict;
                  const ruleResults = evalObj.rule_results || [];
                  const satisfiedCount = ruleResults.filter((r) => r.status === 'SATISFIED').length;
                  const firstViolation = ev.first_violated_rule || evalObj.first_violated_rule;
                  const actor = ev.actor_attribution || evalObj.actor_attribution || 'UNKNOWN';

                  return (
                    <tr
                      key={ev.evaluation_id}
                      className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors"
                    >
                      <td className="py-3 px-4 font-mono">
                        <div className="font-semibold text-indigo-600 dark:text-indigo-400 truncate max-w-[150px]">
                          {ev.evaluation_id}
                        </div>
                        <span className="text-[10px] text-slate-400 block font-sans">
                          {ev.created_at_utc ? new Date(ev.created_at_utc).toLocaleString() : 'N/A'}
                        </span>
                      </td>

                      <td className="py-3 px-4">
                        {verdict ? (
                          <C3Badge status={verdict} />
                        ) : (
                          <C3Badge status="NOT_EVALUATED" />
                        )}
                      </td>

                      <td className="py-3 px-4 font-mono text-[11px]">
                        <div className="text-slate-800 dark:text-slate-200 font-semibold truncate max-w-[140px]">
                          {ev.pair_id}
                        </div>
                        <span className="text-[10px] text-slate-400 block truncate max-w-[140px]">
                          Case: {ev.case_id}
                        </span>
                      </td>

                      <td className="py-3 px-4 text-[11px]">
                        {firstViolation ? (
                          <span className="font-mono text-rose-600 dark:text-rose-400 font-semibold bg-rose-50 dark:bg-rose-950/40 px-1.5 py-0.5 rounded border border-rose-200 dark:border-rose-900">
                            {firstViolation}
                          </span>
                        ) : verdict === 'FAIL' ? (
                          <span className="text-slate-500 italic">Terminal outcome failure</span>
                        ) : (
                          <span className="text-emerald-600 dark:text-emerald-400 font-medium">None (Passed)</span>
                        )}
                      </td>

                      <td className="py-3 px-4 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                        {actor}
                      </td>

                      <td className="py-3 px-4 text-xs">
                        {ruleResults.length > 0 ? (
                          <span className="text-slate-600 dark:text-slate-400">
                            <strong className="text-slate-900 dark:text-white">{satisfiedCount}</strong> / {ruleResults.length} Satisfied
                          </span>
                        ) : (
                          <span className="text-slate-400 italic">Ineligible</span>
                        )}
                      </td>

                      <td className="py-3 px-4 text-right">
                        <button
                          type="button"
                          onClick={() => setSelectedEvaluation(ev)}
                          className="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 hover:bg-indigo-100 transition-colors inline-flex items-center gap-1"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          <span>Explain</span>
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal: Explanation & Evidence Detail View */}
      {selectedEvaluation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-xs overflow-y-auto">
          <div className="max-w-4xl w-full my-8 bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 p-6 space-y-6 max-h-[90vh] overflow-y-auto">
            <C3ExplanationEvidenceView
              evaluationRecord={selectedEvaluation}
              onClose={() => setSelectedEvaluation(null)}
            />
          </div>
        </div>
      )}

      {/* Modal: Compute Evaluation */}
      {isComputeModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-xs">
          <div className="max-w-lg w-full bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 p-6 space-y-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <Play className="w-4 h-4 text-indigo-600" />
                  <span>Compute & Store Recovery Evaluation</span>
                </h3>
                <p className="text-xs text-slate-500 mt-1">
                  Executes the authoritative server-side recovery evaluation engine against referenced evidence and C2 facts.
                </p>
              </div>
            </div>

            {computeError && (
              <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-xs text-rose-700 dark:text-rose-300">
                {computeError}
              </div>
            )}

            <form onSubmit={handleComputeSubmit} className="space-y-4 text-xs">
              <div>
                <label className="font-semibold text-slate-700 dark:text-slate-300 block mb-1">
                  Select Matched Trial Pair:
                </label>
                {existingPairs.length > 0 ? (
                  <select
                    value={selectedPairIdForCompute}
                    onChange={(e) => setSelectedPairIdForCompute(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:outline-hidden"
                    required
                  >
                    <option value="">-- Choose a pair --</option>
                    {existingPairs.map((p) => (
                      <option key={p.pair_id} value={p.pair_id}>
                        {p.pair_id} (Case: {p.case_id}, Exposure: {p.exposure_status}, Clean: {p.clean_qualification})
                      </option>
                    ))}
                  </select>
                ) : (
                  <div>
                    <input
                      type="text"
                      placeholder="Enter Pair ID (e.g. pair-demo-payment-001)"
                      value={selectedPairIdForCompute}
                      onChange={(e) => setSelectedPairIdForCompute(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white"
                      required
                    />
                    <span className="text-[10px] text-slate-400 mt-1 block">
                      Tip: You can use preset: <code className="font-mono text-indigo-500">pair-demo-payment-001</code>
                    </span>
                  </div>
                )}
              </div>

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-2">
                <label className="flex items-center gap-2 cursor-pointer font-semibold text-slate-800 dark:text-slate-200">
                  <input
                    type="checkbox"
                    checked={useCustomC2Facts}
                    onChange={(e) => setUseCustomC2Facts(e.target.checked)}
                    className="rounded text-indigo-600 focus:ring-0"
                  />
                  <span>Attach Component 2 Verified Assertion Facts</span>
                </label>
                <p className="text-[11px] text-slate-500 leading-relaxed pl-5">
                  Includes discrete C2 state assertions (<code className="font-mono">state_order_created: TRUE</code>, <code className="font-mono">duplicate_side_effect_detected: FALSE</code>, <code className="font-mono">idempotency_key_reused: TRUE</code>) consumed from workflow evidence.
                </p>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsComputeModalOpen(false)}
                  className="px-4 py-2 rounded-xl font-semibold bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={isComputing || !selectedPairIdForCompute}
                  className="px-4 py-2 rounded-xl font-semibold bg-indigo-600 hover:bg-indigo-700 text-white flex items-center gap-1.5 disabled:opacity-50"
                >
                  {isComputing ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Evaluating on Server...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-3.5 h-3.5" />
                      <span>Compute Evaluation</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
