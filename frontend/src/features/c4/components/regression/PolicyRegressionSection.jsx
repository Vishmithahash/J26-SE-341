/**
 * Component 4 (C4) - Policy-Change Regression & Diffing Section
 * Complete interface for:
 * 1. Comparing baseline and candidate policy contracts to produce deterministic diffs.
 * 2. Generating typed impact regression plans with case actions (REGENERATE, REVALIDATE, RETIRE, RETAIN).
 * 3. Inspecting case replacement lineage and freezing regression plans.
 * 4. Executing selective regression (Fresh Execution vs Historical Re-evaluation).
 * 5. Viewing evidence-linked regression reports and verdict transitions.
 */

import React from 'react';
import {
  GitCompare,
  ArrowRight,
  Play,
  RotateCcw,
  Lock,
  AlertTriangle,
  CheckCircle2,
  History,
  RefreshCw,
} from 'lucide-react';
import {
  RULE_CHANGE_TYPES,
  CASE_DECISION_ACTIONS,
  PLAN_LIFECYCLE_STATES,
  REGRESSION_EXECUTION_MODES,
} from '../../api/types.js';

export function PolicyRegressionSection({ regression, contracts }) {
  const {
    baselineContractId,
    setBaselineContractId,
    baselineContractVersion,
    setBaselineContractVersion,
    candidateContractId,
    setCandidateContractId,
    candidateContractVersion,
    setCandidateContractVersion,
    executionMode,
    setExecutionMode,
    idempotencyKey,
    regenerateIdempotencyKey,
    activeComparison,
    activePlan,
    activeReport,
    isComparing,
    isCreatingPlan,
    isRegenerating,
    isFreezing,
    isExecuting,
    error,
    successMessage,
    compareContracts,
    createPlan,
    regeneratePlan,
    freezePlan,
    executePlan,
    reEvaluateHistorical,
  } = regression;

  // Auto-populate baseline contract ID from accepted contracts if empty
  const acceptedContract = contracts?.acceptedContract;

  const handleUseAcceptedBaseline = () => {
    if (acceptedContract) {
      setBaselineContractId(acceptedContract.contract_id);
      setBaselineContractVersion(acceptedContract.version);
    }
  };

  const getChangeTypeBadge = (changeType) => {
    switch (changeType) {
      case RULE_CHANGE_TYPES.ADDED:
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300">ADDED</span>;
      case RULE_CHANGE_TYPES.REMOVED:
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-rose-100 text-rose-800 dark:bg-rose-950/70 dark:text-rose-300">REMOVED</span>;
      case RULE_CHANGE_TYPES.SEMANTICALLY_MODIFIED:
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-indigo-100 text-indigo-800 dark:bg-indigo-950/70 dark:text-indigo-300">SEMANTICALLY MODIFIED</span>;
      case RULE_CHANGE_TYPES.METADATA_ONLY:
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950/70 dark:text-amber-300">METADATA ONLY</span>;
      case RULE_CHANGE_TYPES.PROVENANCE_ONLY:
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-sky-100 text-sky-800 dark:bg-sky-950/70 dark:text-sky-300">PROVENANCE ONLY</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">UNCHANGED</span>;
    }
  };

  const getDecisionActionBadge = (action) => {
    switch (action) {
      case CASE_DECISION_ACTIONS.REGENERATE:
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-indigo-100 text-indigo-800 dark:bg-indigo-950/70 dark:text-indigo-300">REGENERATE</span>;
      case CASE_DECISION_ACTIONS.REVALIDATE:
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-sky-100 text-sky-800 dark:bg-sky-950/70 dark:text-sky-300">REVALIDATE</span>;
      case CASE_DECISION_ACTIONS.RETIRE:
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-rose-100 text-rose-800 dark:bg-rose-950/70 dark:text-rose-300">RETIRE</span>;
      case CASE_DECISION_ACTIONS.RETAIN:
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300">RETAIN</span>;
      case CASE_DECISION_ACTIONS.BLOCKED:
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950/70 dark:text-amber-300">BLOCKED</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">{action}</span>;
    }
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-150">
      {/* Header Banner */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-indigo-100 dark:bg-indigo-950/80 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                PHASE 3 ACTIVE
              </span>
              <h2 className="text-xl font-extrabold text-slate-900 dark:text-white tracking-tight">
                Policy-Change Tracking, Impact Diffing & Selective Regression
              </h2>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 max-w-3xl leading-relaxed">
              When organizational safety policies evolve, identify semantically modified rules, compute typed test-case impact decisions, selectively regenerate affected tests, and execute targeted regression runs with disentangled requirement-change transitions.
            </p>
          </div>
        </div>

        {/* Banners */}
        {error && (
          <div className="mt-4 p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-800 dark:text-rose-200 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{error}</span>
            </div>
          </div>
        )}

        {successMessage && (
          <div className="mt-4 p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-200 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}
      </div>

      {/* Step 1: Compare Contracts Configuration */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 dark:bg-indigo-950/70 border border-indigo-200 dark:border-indigo-800 flex items-center justify-center text-indigo-600 dark:text-indigo-400">
              <GitCompare className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                1. Select Baseline & Candidate Policy Contracts
              </h3>
              <p className="text-xs text-slate-500">
                Compare an accepted baseline contract version against a revised candidate version.
              </p>
            </div>
          </div>
          {acceptedContract && (
            <button
              onClick={handleUseAcceptedBaseline}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 border border-indigo-200 dark:border-indigo-800 transition-colors"
            >
              Use Accepted Contract as Baseline ({acceptedContract.contract_id} v{acceptedContract.version})
            </button>
          )}
        </div>

        {/* Inputs Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
          <div>
            <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Baseline Contract ID
            </label>
            <input
              type="text"
              value={baselineContractId}
              onChange={(e) => setBaselineContractId(e.target.value)}
              placeholder="e.g. contract-ecommerce-v1"
              className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Baseline Version
            </label>
            <input
              type="number"
              min="1"
              value={baselineContractVersion}
              onChange={(e) => setBaselineContractVersion(Math.max(1, parseInt(e.target.value, 10) || 1))}
              className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Candidate Contract ID
            </label>
            <input
              type="text"
              value={candidateContractId}
              onChange={(e) => setCandidateContractId(e.target.value)}
              placeholder="e.g. contract-ecommerce-v2"
              className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Candidate Version
            </label>
            <input
              type="number"
              min="1"
              value={candidateContractVersion}
              onChange={(e) => setCandidateContractVersion(Math.max(1, parseInt(e.target.value, 10) || 1))}
              className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
        </div>

        {/* Action Button */}
        <div className="flex justify-end pt-2">
          <button
            onClick={() => compareContracts()}
            disabled={isComparing || !baselineContractId || !candidateContractId}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 disabled:opacity-50 text-white font-semibold text-xs shadow-sm shadow-indigo-500/20 transition-all"
          >
            {isComparing ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Computing Semantic Diff...</span>
              </>
            ) : (
              <>
                <GitCompare className="w-4 h-4" />
                <span>Compare Contracts & Generate Diff</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Step 2: Policy Diff Inspector */}
      {activeComparison && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-6 animate-in fade-in">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <span>2. Policy Rule Diff Results</span>
                <span className="font-mono text-xs text-indigo-600 dark:text-indigo-400 font-normal">
                  ({activeComparison.comparison_id})
                </span>
              </h3>
              <p className="text-xs text-slate-500">
                Deterministic comparison of rules between baseline (v{activeComparison.baseline_contract_version}) and candidate (v{activeComparison.candidate_contract_version}).
              </p>
            </div>
            <button
              onClick={() => createPlan()}
              disabled={isCreatingPlan}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs transition-colors shadow-sm"
            >
              {isCreatingPlan ? 'Drafting Impact Plan...' : 'Draft Impact Regression Plan'}
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Rule Diffs Table */}
          <div className="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-xl">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-950 text-slate-500 border-b border-slate-200 dark:border-slate-800 font-semibold">
                <tr>
                  <th className="py-2.5 px-3">Rule ID</th>
                  <th className="py-2.5 px-3">Change Type</th>
                  <th className="py-2.5 px-3">Description</th>
                  <th className="py-2.5 px-3">Boundary / Property Impact</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
                {activeComparison.rule_diffs?.map((diff) => (
                  <tr key={diff.rule_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                    <td className="py-3 px-3 font-mono font-bold text-slate-900 dark:text-slate-100">
                      {diff.rule_id}
                    </td>
                    <td className="py-3 px-3">
                      {getChangeTypeBadge(diff.change_type)}
                    </td>
                    <td className="py-3 px-3 text-slate-700 dark:text-slate-300">
                      {diff.change_description}
                    </td>
                    <td className="py-3 px-3">
                      <div className="flex flex-wrap gap-1">
                        {diff.affects_boundary && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 font-mono">
                            Boundary
                          </span>
                        )}
                        {diff.affects_permission && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 font-mono">
                            Permission
                          </span>
                        )}
                        {diff.affects_confidentiality && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 font-mono">
                            Confidentiality
                          </span>
                        )}
                        {!diff.affects_boundary && !diff.affects_permission && !diff.affects_confidentiality && (
                          <span className="text-[10px] text-slate-400">None</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Step 3: Regression Plan & Case Impact Decisions */}
      {activePlan && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-6 animate-in fade-in">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                  3. Typed Regression Plan & Case Replacement Lineage
                </h3>
                <span
                  className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                    activePlan.status === PLAN_LIFECYCLE_STATES.FROZEN
                      ? 'bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300'
                      : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
                  }`}
                >
                  {activePlan.status}
                </span>
              </div>
              <p className="text-xs text-slate-500 font-mono">
                Plan ID: {activePlan.plan_id} • Digest: {activePlan.plan_digest?.substring(0, 12)}...
              </p>
            </div>

            {/* Plan Actions */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => regeneratePlan()}
                disabled={isRegenerating || activePlan.status === PLAN_LIFECYCLE_STATES.FROZEN}
                className="px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 disabled:opacity-40 text-xs font-semibold transition-colors flex items-center gap-1.5"
              >
                <RotateCcw className={`w-3.5 h-3.5 ${isRegenerating ? 'animate-spin' : ''}`} />
                <span>Selectively Regenerate Cases</span>
              </button>

              <button
                onClick={() => freezePlan()}
                disabled={isFreezing || activePlan.status === PLAN_LIFECYCLE_STATES.FROZEN}
                className="px-3.5 py-2 rounded-xl bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-950/60 dark:hover:bg-indigo-900/60 text-indigo-600 dark:text-indigo-400 disabled:opacity-40 text-xs font-semibold transition-colors flex items-center gap-1.5 border border-indigo-200 dark:border-indigo-800"
              >
                <Lock className="w-3.5 h-3.5" />
                <span>Freeze Plan Snapshot</span>
              </button>
            </div>
          </div>

          {/* Case Decisions Table with Lineage */}
          <div className="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-xl">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-950 text-slate-500 border-b border-slate-200 dark:border-slate-800 font-semibold">
                <tr>
                  <th className="py-2.5 px-3">Test Case</th>
                  <th className="py-2.5 px-3">Target Rule</th>
                  <th className="py-2.5 px-3">Impact Level</th>
                  <th className="py-2.5 px-3">Action</th>
                  <th className="py-2.5 px-3">Replacement / Predecessor Lineage</th>
                  <th className="py-2.5 px-3">Decision Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
                {activePlan.case_decisions?.map((dec) => (
                  <tr key={dec.case_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                    <td className="py-3 px-3 font-mono font-bold text-slate-900 dark:text-slate-100">
                      {dec.case_id} (v{dec.case_version})
                    </td>
                    <td className="py-3 px-3 font-mono text-indigo-600 dark:text-indigo-400">
                      {dec.target_rule_id}
                    </td>
                    <td className="py-3 px-3 font-medium text-slate-700 dark:text-slate-300">
                      {dec.impact_level}
                    </td>
                    <td className="py-3 px-3">
                      {getDecisionActionBadge(dec.action)}
                    </td>
                    <td className="py-3 px-3 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                      {dec.replacement_case_id ? (
                        <span className="text-emerald-600 dark:text-emerald-400">
                          Replaced by: {dec.replacement_case_id} v{dec.replacement_case_version}
                        </span>
                      ) : dec.predecessor_case_id ? (
                        <span className="text-slate-500">
                          Predecessor: {dec.predecessor_case_id} v{dec.predecessor_case_version}
                        </span>
                      ) : (
                        <span className="text-slate-400">Retained unchanged</span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-slate-600 dark:text-slate-400 text-[11px]">
                      {dec.reason}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Controlled Execution Controls */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
              <Play className="w-3.5 h-3.5 text-indigo-500" />
              Selective Regression Execution Mode
            </h4>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Fresh Execution vs Historical Re-evaluation */}
              <div className="space-y-2">
                <div className="flex gap-2">
                  <button
                    onClick={() => setExecutionMode(REGRESSION_EXECUTION_MODES.FRESH_EXECUTION)}
                    className={`flex-1 p-3 rounded-xl border text-left text-xs transition-all ${
                      executionMode === REGRESSION_EXECUTION_MODES.FRESH_EXECUTION
                        ? 'bg-indigo-50 dark:bg-indigo-950/70 border-indigo-300 dark:border-indigo-700 text-indigo-900 dark:text-indigo-200'
                        : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300'
                    }`}
                  >
                    <span className="font-bold block mb-0.5">Fresh Agent Execution</span>
                    <span className="text-[11px] text-slate-500 dark:text-slate-400">
                      Invokes simulated adapter for new or regenerated cases.
                    </span>
                  </button>

                  <button
                    onClick={() => setExecutionMode(REGRESSION_EXECUTION_MODES.HISTORICAL_RE_EVALUATION)}
                    className={`flex-1 p-3 rounded-xl border text-left text-xs transition-all ${
                      executionMode === REGRESSION_EXECUTION_MODES.HISTORICAL_RE_EVALUATION
                        ? 'bg-indigo-50 dark:bg-indigo-950/70 border-indigo-300 dark:border-indigo-700 text-indigo-900 dark:text-indigo-200'
                        : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300'
                    }`}
                  >
                    <span className="font-bold block mb-0.5">Historical Re-evaluation</span>
                    <span className="text-[11px] text-slate-500 dark:text-slate-400">
                      Re-scores existing traces against new candidate rules without agent execution.
                    </span>
                  </button>
                </div>

                <p className="text-[11px] text-slate-400 italic">
                  Note: Historical re-evaluation re-scores existing traces against candidate rules; it does not constitute a fresh agent invocation or fresh coverage.
                </p>
              </div>

              {/* Idempotency Key & Action */}
              <div className="space-y-2">
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Execution Idempotency Key
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={idempotencyKey}
                    readOnly
                    className="flex-1 px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-600 dark:text-slate-400 select-all"
                  />
                  <button
                    onClick={regenerateIdempotencyKey}
                    className="px-3 py-2 rounded-xl bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1"
                    title="Generate new idempotency key for intentional new submission"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    <span>New Key</span>
                  </button>
                </div>

                <div className="pt-2 flex justify-end">
                  {executionMode === REGRESSION_EXECUTION_MODES.HISTORICAL_RE_EVALUATION ? (
                    <button
                      onClick={() => reEvaluateHistorical()}
                      disabled={isExecuting}
                      className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs transition-colors flex items-center gap-2 shadow-sm"
                    >
                      <History className="w-4 h-4" />
                      <span>{isExecuting ? 'Re-evaluating...' : 'Run Historical Re-evaluation'}</span>
                    </button>
                  ) : (
                    <button
                      onClick={() => executePlan()}
                      disabled={isExecuting}
                      className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs transition-colors flex items-center gap-2 shadow-sm"
                    >
                      <Play className="w-4 h-4" />
                      <span>{isExecuting ? 'Executing...' : 'Execute Fresh Regression Run'}</span>
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Step 4: Evidence-Linked Regression Report & Verdict Transitions */}
      {activeReport && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-6 animate-in fade-in">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <span>4. Evidence-Linked Regression Report</span>
                <span className="font-mono text-xs text-indigo-600 dark:text-indigo-400 font-normal">
                  ({activeReport.report_id})
                </span>
              </h3>
              <p className="text-xs text-slate-500">
                Transitions between baseline (v{activeReport.baseline_contract_version}) and candidate (v{activeReport.candidate_contract_version}).
              </p>
            </div>
          </div>

          {/* Verdict Transitions Table */}
          <div className="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-xl">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-950 text-slate-500 border-b border-slate-200 dark:border-slate-800 font-semibold">
                <tr>
                  <th className="py-2.5 px-3">Case ID</th>
                  <th className="py-2.5 px-3">Rule ID</th>
                  <th className="py-2.5 px-3">Baseline → Candidate Verdict</th>
                  <th className="py-2.5 px-3">Transition Classification</th>
                  <th className="py-2.5 px-3">Explanation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
                {activeReport.verdict_transitions?.map((trans, i) => (
                  <tr key={i} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                    <td className="py-3 px-3 font-mono font-bold text-slate-900 dark:text-slate-100">
                      {trans.case_id}
                    </td>
                    <td className="py-3 px-3 font-mono text-indigo-600 dark:text-indigo-400">
                      {trans.rule_id}
                    </td>
                    <td className="py-3 px-3">
                      <div className="flex items-center gap-1.5 font-mono text-xs font-semibold">
                        <span className={trans.baseline_verdict === 'PASS' ? 'text-emerald-600' : 'text-rose-600'}>
                          {trans.baseline_verdict || 'NONE'}
                        </span>
                        <ArrowRight className="w-3 h-3 text-slate-400" />
                        <span className={trans.candidate_verdict === 'PASS' ? 'text-emerald-600' : 'text-rose-600'}>
                          {trans.candidate_verdict}
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      {trans.is_requirement_change ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300 border border-amber-300 dark:border-amber-800">
                          Requirement Change (Not Agent Regression)
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-100 text-indigo-800 dark:bg-indigo-950/80 dark:text-indigo-300 border border-indigo-300 dark:border-indigo-800">
                          {trans.transition_type}
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-slate-600 dark:text-slate-300 text-[11px]">
                      {trans.explanation}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
