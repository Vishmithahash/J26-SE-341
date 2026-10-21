import React, { useState } from 'react';
import {
  X,
  Play,
  FlaskConical,
  AlertCircle,
  Info,
} from 'lucide-react';

const DEMO_SCENARIOS = [
  {
    id: 'happy_path',
    name: 'Happy Path Baseline',
    desc: 'Fully compliant multi-step refund execution',
    expectedVerdict: 'PASS',
  },
  {
    id: 'inspection_alternative',
    name: 'Valid Inspection Alternative',
    desc: 'Valid branch requiring manual item inspection before refund approval',
    expectedVerdict: 'PASS',
  },
  {
    id: 'unpaid_order_rejection',
    name: 'Negative Rejection (Unpaid Order)',
    desc: 'Negative test attempting refund on unpaid order; expected rejection by SUT',
    expectedVerdict: 'EXPECTED_REJECTION_PASS',
  },
  {
    id: 'skipped_step',
    name: 'Flawed: Skipped Step',
    desc: 'Demonstration agent skips required order verification step',
    expectedVerdict: 'FAIL',
  },
  {
    id: 'reordered_step',
    name: 'Flawed: Reordered Steps',
    desc: 'Agent invokes payment reversal before item return receipt',
    expectedVerdict: 'FAIL',
  },
  {
    id: 'repeated_step',
    name: 'Flawed: Repeated Step',
    desc: 'Duplicate execution of a non-idempotent refund transaction',
    expectedVerdict: 'FAIL',
  },
  {
    id: 'wrong_entity',
    name: 'Flawed: Wrong Entity ID',
    desc: 'Agent references mismatched order/item ID during transition',
    expectedVerdict: 'FAIL',
  },
  {
    id: 'premature_termination',
    name: 'Flawed: Premature Termination',
    desc: 'Trace terminates abruptly before reaching accepting terminal state',
    expectedVerdict: 'FAIL',
  },
  {
    id: 'missing_effect',
    name: 'Flawed: Missing Business Effect',
    desc: 'Action executed but required ledger database update was not observed',
    expectedVerdict: 'FAIL',
  },
  {
    id: 'protected_state_change',
    name: 'Flawed: Protected State Mutation',
    desc: 'Action illegally modifies immutable entity fields during rejection',
    expectedVerdict: 'FAIL',
  },
  {
    id: 'missing_observations',
    name: 'Observer Flaw: Missing Observations',
    desc: 'State observer fails to capture required variable snapshots',
    expectedVerdict: 'INCONCLUSIVE',
  },
  {
    id: 'truncated_trace',
    name: 'Observer Flaw: Truncated Trace',
    desc: 'Runtime trace collection ends unexpectedly with incomplete record',
    expectedVerdict: 'INCONCLUSIVE',
  },
];

export const DemonstrationRunnerModal = ({
  isOpen,
  onClose,
  modelId = 'c2_refund_efsm_nexacart',
  modelVersion = '1.0.0',
  onRunDemonstration,
  isExecuting,
}) => {
  const [selectedScenario, setSelectedScenario] = useState('happy_path');
  const [customerId, setCustomerId] = useState(42);
  const [targetOrderId, setTargetOrderId] = useState(503);
  const [localError, setLocalError] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLocalError(null);

    const payload = {
      scenario: selectedScenario,
      model_id: modelId,
      model_version: modelVersion,
      customer_id: Number(customerId),
      target_order_id: Number(targetOrderId),
    };

    try {
      await onRunDemonstration(payload);
      onClose();
    } catch (err) {
      setLocalError(err.message || 'Synthetic demonstration execution failed.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs overflow-y-auto">
      <div className="relative w-full max-w-2xl flex flex-col rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400">
              <FlaskConical className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                  Execute Synthetic Demonstration
                </h2>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 dark:bg-amber-900/60 text-amber-800 dark:text-amber-300 uppercase tracking-wide">
                  Synthetic Only
                </span>
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                Scripted demonstration of C2 workflow conformance evaluation • Strictly non-live
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Synthetic Disclosure Alert */}
        <div className="p-4 bg-amber-50/70 dark:bg-amber-950/40 border-b border-amber-200 dark:border-amber-900/50 text-xs text-amber-900 dark:text-amber-200 flex items-start gap-2.5">
          <Info className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-semibold">Honest Runner Capability Disclosure:</span>
            <p className="text-[11px] leading-relaxed text-amber-800 dark:text-amber-300">
              This action uses the backend's built-in <code className="font-mono font-bold">ScriptedDemonstrationAgent</code> and <code className="font-mono font-bold">LocalSyntheticRunnerAdapter</code>.
              It verifies conformance evaluation logic against known flaw scenarios. It does NOT invoke a live LLM application agent.
            </p>
          </div>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {localError && (
            <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-xs text-rose-800 dark:text-rose-200 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{localError}</span>
            </div>
          )}

          {/* Scenario Selection */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-800 dark:text-slate-200">
              Demonstration Scenario Flaw / Behavior:
            </label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-56 overflow-y-auto p-1">
              {DEMO_SCENARIOS.map((sc) => {
                const isSelected = selectedScenario === sc.id;
                return (
                  <div
                    key={sc.id}
                    onClick={() => setSelectedScenario(sc.id)}
                    className={`p-3 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? 'border-indigo-600 dark:border-indigo-400 bg-indigo-50/50 dark:bg-indigo-950/40'
                        : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-white dark:bg-slate-900'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-900 dark:text-white">
                        {sc.name}
                      </span>
                      <span
                        className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded ${
                          sc.expectedVerdict === 'PASS' || sc.expectedVerdict === 'EXPECTED_REJECTION_PASS'
                            ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300'
                            : sc.expectedVerdict === 'FAIL'
                            ? 'bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300'
                            : 'bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300'
                        }`}
                      >
                        {sc.expectedVerdict}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 leading-snug">
                      {sc.desc}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Model and Target Parameters */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="space-y-1">
              <label className="font-semibold text-slate-700 dark:text-slate-300">
                Customer ID:
              </label>
              <input
                type="number"
                value={customerId}
                onChange={(e) => setCustomerId(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-xs font-mono"
              />
            </div>
            <div className="space-y-1">
              <label className="font-semibold text-slate-700 dark:text-slate-300">
                Target Order ID:
              </label>
              <input
                type="number"
                value={targetOrderId}
                onChange={(e) => setTargetOrderId(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-xs font-mono"
              />
            </div>
          </div>

          <div className="p-3 rounded-xl bg-slate-100 dark:bg-slate-800 text-[11px] text-slate-600 dark:text-slate-400">
            Model: <code className="font-mono">{modelId} v{modelVersion}</code>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-200 dark:border-slate-800">
            <button
              type="button"
              onClick={onClose}
              disabled={isExecuting}
              className="px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-200 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isExecuting}
              className="inline-flex items-center gap-2 px-5 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-xs font-semibold shadow-xs transition-colors"
            >
              <Play className="w-3.5 h-3.5" />
              <span>{isExecuting ? 'Running Demonstration...' : 'Run Demonstration'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
