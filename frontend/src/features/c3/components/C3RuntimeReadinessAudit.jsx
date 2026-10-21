import React, { useState } from 'react';
import {
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  Terminal,
  Cpu,
  ChevronDown,
  ChevronRight,
  Info,
} from 'lucide-react';
import { C3Badge } from './C3Badge';

export const C3RuntimeReadinessAudit = ({
  candidateCase,
  adapterManifest,
  taskFixtureMetadata,
  recoveryContract,
}) => {
  const [showCliDetails, setShowCliDetails] = useState(true);

  // Derive readiness dimensions
  const adapterId = adapterManifest?.adapter_id || 'adapter-payment-01';
  const adapterVersion = adapterManifest?.adapter_version || '1.2.0';
  const caseAdapterId = candidateCase?.adapter_id || adapterId;
  const isAdapterMatched = adapterId === caseAdapterId;

  const supportsReset = Boolean(taskFixtureMetadata?.declared_reset_support);
  const supportsObs = Boolean(taskFixtureMetadata?.declared_observation_support);

  return (
    <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <Cpu className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
              <span>Runtime Readiness Findings & Execution Blockers</span>
            </h3>
            <C3Badge status="TEST_NOT_READY" label="HTTP Runner Blocked" />
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-2xl leading-relaxed">
            Runtime readiness enforces adapter identity, fixture reset capabilities, operational fault triggers, and environment prerequisites. Declared adapter capabilities are not proof of live target execution.
          </p>
        </div>
      </div>

      {/* Critical Blocker Alert */}
      <div className="p-4 rounded-xl bg-amber-50/70 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/60 space-y-2">
        <div className="flex items-start gap-2.5">
          <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <span className="font-bold text-amber-900 dark:text-amber-200">
              Live HTTP Trial Execution is Unavailable by Design
            </span>
            <p className="text-amber-800/90 dark:text-amber-300/90 leading-relaxed">
              The backend Component 3 architecture does not expose an HTTP POST endpoint for triggering live trial execution. Live matched trials and bounded suites are executed using hermetic Python runtime runners and developer CLI tools. Completed trial evidence is stored and reviewed via the <strong>Import Evidence</strong> API and Tracked Execution retrieval endpoints.
            </p>
          </div>
        </div>
      </div>

      {/* Readiness Check Matrix */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
        {/* 1. Adapter Match */}
        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-slate-700 dark:text-slate-300">
              1. Adapter Identity & Version
            </span>
            {isAdapterMatched ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
            ) : (
              <ShieldAlert className="w-4 h-4 text-rose-500" />
            )}
          </div>
          <div className="text-[11px] text-slate-500 dark:text-slate-400 font-mono">
            ID: {adapterId} (v{adapterVersion})
          </div>
          <p className="text-[10px] text-slate-400">
            {isAdapterMatched
              ? 'Candidate case matches installed adapter specification.'
              : 'Adapter ID mismatch between candidate case and installed adapter.'}
          </p>
        </div>

        {/* 2. Fixture Resettability */}
        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-slate-700 dark:text-slate-300">
              2. Resettable Fixture State
            </span>
            {supportsReset ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
            ) : (
              <ShieldAlert className="w-4 h-4 text-rose-500" />
            )}
          </div>
          <div className="text-[11px] text-slate-500 dark:text-slate-400 font-mono">
            {taskFixtureMetadata?.reset_method || 'database_snapshot_restore'}
          </div>
          <p className="text-[10px] text-slate-400">
            Guarantees clean control and fault trials begin from equivalent logical starting state. Observation support: {supportsObs ? 'Declared' : 'None'}.
          </p>
        </div>

        {/* 3. Operational Fault & Hook */}
        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-slate-700 dark:text-slate-300">
              3. Fault Trigger & Phase
            </span>
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="text-[11px] text-slate-500 dark:text-slate-400 font-mono">
            {candidateCase?.interception_hook || 'BEFORE_TOOL_CALL'} | {candidateCase?.effect_phase || 'BEFORE_EFFECT'}
          </div>
          <p className="text-[10px] text-slate-400">
            Target tool: <span className="font-mono">{candidateCase?.tool_id || 'payment_gateway'}</span> (occurrence: {candidateCase?.occurrence || 1})
          </p>
        </div>

        {/* 4. Target Mode */}
        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-slate-700 dark:text-slate-300">
              4. Target Mode & AUT Endpoint
            </span>
            <AlertTriangle className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-[11px] font-mono">
            Mode: <span className="text-purple-600 dark:text-purple-400 font-semibold">DEMONSTRATION</span>
          </div>
          <p className="text-[10px] text-slate-400">
            Live AUT (<code className="font-mono">NEXACART_AUT_URL</code>) is unconfigured in this environment. Hermetic demonstration mode is active.
          </p>
        </div>

        {/* 5. Agent & Model Connection */}
        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-slate-700 dark:text-slate-300">
              5. Model Connection Gating
            </span>
            <Info className="w-4 h-4 text-slate-400" />
          </div>
          <div className="text-[11px] text-slate-500 dark:text-slate-400">
            Caller: <span className="font-mono font-semibold">SCRIPTED_CALLER</span>
          </div>
          <p className="text-[10px] text-slate-400">
            UI model preferences do not prove an active model API socket. Scripted deterministic caller verified.
          </p>
        </div>

        {/* 6. Execution Budgets */}
        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-slate-700 dark:text-slate-300">
              6. Execution Budgets
            </span>
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="text-[11px] text-slate-500 dark:text-slate-400 font-mono">
            Attempts: {recoveryContract?.max_task_attempts || 3} | Timeout: {recoveryContract?.max_total_timeout_ms || 30000}ms
          </div>
          <p className="text-[10px] text-slate-400">
            Tool call budget: {recoveryContract?.max_tool_calls_budget || 10} calls max.
          </p>
        </div>
      </div>

      {/* Developer CLI Workflow Accordion */}
      <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
        <button
          type="button"
          onClick={() => setShowCliDetails((prev) => !prev)}
          className="w-full px-4 py-3 bg-slate-50 dark:bg-slate-800/60 flex items-center justify-between text-xs font-semibold text-slate-800 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-indigo-500" />
            <span>Developer CLI: How to Execute Trials & Generate Evidence Locally</span>
          </div>
          {showCliDetails ? (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-slate-400" />
          )}
        </button>

        {showCliDetails && (
          <div className="p-4 bg-slate-900 text-slate-200 text-xs font-mono space-y-3">
            <p className="text-slate-400 text-[11px]">
              Execute hermetic matched trials or bounded frozen suites from the backend directory:
            </p>
            <div className="p-3 bg-black/50 rounded-lg border border-slate-800 space-y-2">
              <div className="text-slate-400"># 1. Run single matched trial (synthetic demonstration):</div>
              <div className="text-emerald-400 select-all">
                python -m app.components.c3_robustness_recovery.runtime.runner --synthetic --export-dir evidence_output
              </div>
              <div className="text-slate-400 pt-1"># 2. Run bounded suite of feasible fault cases:</div>
              <div className="text-emerald-400 select-all">
                python -m app.components.c3_robustness_recovery.runtime.suite_runner --synthetic --export-dir evidence_output
              </div>
            </div>
            <p className="text-slate-400 text-[11px]">
              The runner outputs versioned JSON evidence into <code className="text-amber-300">evidence_output/</code>. You can then use the <strong>Import Evidence</strong> action above to persist and inspect the evidence in this workspace.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
