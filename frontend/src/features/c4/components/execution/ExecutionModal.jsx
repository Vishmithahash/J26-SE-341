/**
 * Component 4 (C4) - Controlled Execution Modal
 * Checks runtime readiness, configures target mode, enforces idempotency, and executes frozen policy test cases.
 */

import React, { useEffect } from 'react';
import {
  X,
  Play,
  AlertTriangle,
  CheckCircle2,
  Key,
  Server,
  Cpu,
} from 'lucide-react';
import { TARGET_EXECUTION_MODES, SIMULATED_AGENT_BEHAVIORS } from '../../api/types.js';

export function ExecutionModal({
  isOpen,
  testCase,
  domainBinding,
  acceptedContract,
  readinessReport,
  isCheckingReadiness,
  isExecuting,
  executionMode,
  setExecutionMode,
  simulatedBehavior,
  setSimulatedBehavior,
  idempotencyKey,
  onRegenerateIdempotencyKey,
  onCheckReadiness,
  onExecuteCase,
  onClose,
  error,
  successMessage,
}) {
  useEffect(() => {
    if (isOpen && testCase && domainBinding && acceptedContract) {
      onCheckReadiness({
        caseId: testCase.case_id,
        caseVersion: testCase.case_version,
        contractId: acceptedContract.contract_id,
        contractVersion: acceptedContract.version,
        bindingId: domainBinding.binding_id,
        bindingVersion: domainBinding.version,
        mode: executionMode,
        behavior: simulatedBehavior,
      });
    }
  }, [isOpen, testCase, domainBinding, acceptedContract, executionMode, simulatedBehavior, onCheckReadiness]);

  if (!isOpen || !testCase) return null;

  const handleModeChange = (newMode) => {
    setExecutionMode(newMode);
  };

  const handleBehaviorChange = (newBehavior) => {
    setSimulatedBehavior(newBehavior);
  };

  const handleExecute = (e) => {
    e.preventDefault();
    if (isExecuting || !readinessReport?.is_ready) return;

    onExecuteCase({
      caseId: testCase.case_id,
      caseVersion: testCase.case_version,
      contractId: acceptedContract?.contract_id || testCase.contract_id,
      contractVersion: acceptedContract?.version || testCase.contract_version,
      bindingId: domainBinding?.binding_id || testCase.domain_id,
      bindingVersion: domainBinding?.version || testCase.binding_version,
      mode: executionMode,
      behavior: simulatedBehavior,
      key: idempotencyKey,
    });
  };

  const isLive = executionMode === TARGET_EXECUTION_MODES.LIVE_AUT;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="execution-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm animate-in fade-in duration-150"
    >
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl w-full max-w-2xl shadow-2xl p-6 relative flex flex-col max-h-[90vh]">
        {/* Close Button */}
        <button
          onClick={onClose}
          disabled={isExecuting}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1 rounded-lg transition-colors"
          aria-label="Close dialog"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="pb-4 border-b border-slate-100 dark:border-slate-800">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded">
              Controlled Execution
            </span>
            <span className="text-xs font-mono font-medium text-slate-500">
              {testCase.case_id} (v{testCase.case_version})
            </span>
          </div>
          <h3 id="execution-modal-title" className="text-base font-bold text-slate-900 dark:text-white">
            Execute Frozen Policy Test Case
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Verify runtime readiness, configure the execution adapter, and safely launch controlled trial.
          </p>
        </div>

        {/* Body Content */}
        <form onSubmit={handleExecute} className="flex-1 overflow-y-auto py-4 space-y-5">
          {/* Target Execution Mode Selection */}
          <div>
            <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-2">
              Execution Target Mode
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => handleModeChange(TARGET_EXECUTION_MODES.SIMULATED)}
                className={`p-3.5 rounded-xl border text-left transition-all ${
                  !isLive
                    ? 'border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/40 ring-1 ring-indigo-500/20'
                    : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 opacity-60'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <Cpu className="w-4 h-4 text-indigo-500" />
                  <span className="text-xs font-bold text-slate-900 dark:text-white">
                    Simulated Application
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-snug">
                  Controlled, deterministic offline simulation with scripted behavioral profiles.
                </p>
              </button>

              <button
                type="button"
                onClick={() => handleModeChange(TARGET_EXECUTION_MODES.LIVE_AUT)}
                className={`p-3.5 rounded-xl border text-left transition-all ${
                  isLive
                    ? 'border-amber-500 bg-amber-50/50 dark:bg-amber-950/40 ring-1 ring-amber-500/20'
                    : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 opacity-60'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <Server className="w-4 h-4 text-amber-500" />
                  <span className="text-xs font-bold text-slate-900 dark:text-white">
                    Live AUT (System Under Test)
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-snug">
                  Live agent daemon connected to target environment (requires live credentials).
                </p>
              </button>
            </div>
          </div>

          {/* Mode-specific Controls */}
          {isLive ? (
            <div className="p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-xs text-amber-900 dark:text-amber-200 space-y-1">
              <p className="font-bold flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                Live Integration Notice
              </p>
              <p className="text-[11px] text-amber-800 dark:text-amber-300">
                Live execution mode is backed by <code>LiveAUTAdapterStub</code>. If live environment endpoints (e.g. <code>NEXACART_API_URL</code>) are not configured, readiness will honestly report the missing endpoints as blockers.
              </p>
            </div>
          ) : (
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                Simulated Agent Behavioral Profile
              </label>
              <select
                value={simulatedBehavior}
                onChange={(e) => handleBehaviorChange(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white"
              >
                <option value={SIMULATED_AGENT_BEHAVIORS.COMPLIANT}>
                  COMPLIANT: Fully obeys policy, refuses injections safely
                </option>
                <option value={SIMULATED_AGENT_BEHAVIORS.UNAUTHORIZED_ATTEMPT_BLOCKED}>
                  UNAUTHORIZED_ATTEMPT_BLOCKED: Attempts prohibited action, blocked by domain
                </option>
                <option value={SIMULATED_AGENT_BEHAVIORS.PROHIBITED_EFFECT_COMMITTED}>
                  PROHIBITED_EFFECT_COMMITTED: Attacker succeeds in committing unauthorized effect
                </option>
                <option value={SIMULATED_AGENT_BEHAVIORS.DISCLOSURE_EXFILTRATION}>
                  DISCLOSURE_EXFILTRATION: Leaks protected synthetic data canary to sink
                </option>
                <option value={SIMULATED_AGENT_BEHAVIORS.IGNORES_INJECTION_SOURCE}>
                  IGNORES_INJECTION_SOURCE: Untrusted injection source unretrieved
                </option>
                <option value={SIMULATED_AGENT_BEHAVIORS.MISSING_INSTRUMENTATION}>
                  MISSING_INSTRUMENTATION: Execution trace missing required observation points
                </option>
                <option value={SIMULATED_AGENT_BEHAVIORS.FIXTURE_CLEANUP_FAILURE}>
                  FIXTURE_CLEANUP_FAILURE: Preserves trial findings but fails post-test reset
                </option>
              </select>
            </div>
          )}

          {/* Idempotency Key Section */}
          <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700/60 space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                <Key className="w-3.5 h-3.5 text-indigo-500" />
                Idempotency Key
              </label>
              <button
                type="button"
                onClick={onRegenerateIdempotencyKey}
                disabled={isExecuting}
                className="text-[11px] font-semibold text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer"
              >
                Generate New Key
              </button>
            </div>
            <input
              type="text"
              value={idempotencyKey}
              readOnly
              className="w-full px-3 py-1.5 text-xs font-mono rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 text-slate-700 dark:text-slate-300"
            />
            <p className="text-[11px] text-slate-400 leading-snug">
              Preserve this key when retrying after a timeout. Reusing it with identical parameters returns the existing run; changing parameters triggers a 409 Conflict.
            </p>
          </div>

          {/* Runtime Readiness Report */}
          <div className="space-y-2">
            <span className="text-xs font-bold text-slate-700 dark:text-slate-300">
              Runtime Readiness Inspection
            </span>

            {isCheckingReadiness ? (
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 flex items-center gap-2 text-xs text-slate-500 animate-pulse">
                <div className="w-3.5 h-3.5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
                <span>Checking runtime environment readiness...</span>
              </div>
            ) : readinessReport ? (
              <div
                className={`p-4 rounded-xl border text-xs space-y-2 ${
                  readinessReport.is_ready
                    ? 'bg-emerald-50/60 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-800 text-emerald-900 dark:text-emerald-200'
                    : 'bg-rose-50/60 dark:bg-rose-950/20 border-rose-200 dark:border-rose-800 text-rose-900 dark:text-rose-200'
                }`}
              >
                <div className="flex items-center justify-between font-bold">
                  <div className="flex items-center gap-1.5">
                    {readinessReport.is_ready ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 text-rose-600" />
                    )}
                    <span>
                      {readinessReport.is_ready
                        ? 'Adapter & Environment Ready for Execution'
                        : 'Execution Blocked by Readiness Checks'}
                    </span>
                  </div>
                  <span className="font-mono text-[11px] uppercase">
                    {readinessReport.adapter_id} (v{readinessReport.adapter_version})
                  </span>
                </div>

                {readinessReport.blockers?.length > 0 && (
                  <ul className="list-disc pl-5 space-y-0.5 text-[11px] text-rose-800 dark:text-rose-300 font-medium">
                    {readinessReport.blockers.map((b, i) => (
                      <li key={i}>{b}</li>
                    ))}
                  </ul>
                )}

                {readinessReport.supported_capabilities?.length > 0 && (
                  <div className="text-[11px] text-slate-500 dark:text-slate-400 font-mono pt-1">
                    Capabilities: {readinessReport.supported_capabilities.slice(0, 5).join(', ')}...
                  </div>
                )}
              </div>
            ) : null}
          </div>

          {/* Feedback messages */}
          {error && (
            <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-800 dark:text-rose-300 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {successMessage && (
            <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-300 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Modal Action Buttons */}
          <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
            <button
              type="button"
              onClick={onClose}
              disabled={isExecuting}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={isExecuting || isCheckingReadiness || !readinessReport?.is_ready}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 dark:disabled:bg-slate-800 text-white font-bold text-xs transition-colors shadow-sm cursor-pointer disabled:cursor-not-allowed"
            >
              {isExecuting ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Executing Trial...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Execute Frozen Test</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
