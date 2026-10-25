/**
 * Component 4 (C4) - Live NexaCart Target Panels
 * Import panel (Policy Preparation): harness readiness, agent model and one-click import of the
 * NexaCart policy, binding and reference candidate rules.
 * Run panel (Runs & Findings): runs the frozen NexaCart cases of the accepted contract live through
 * the NexaCart LLM agent and shows per-case progress and verdicts.
 * Live evidence block: the real agent run, tool calls and final answer behind a run record.
 */

import React, { useState } from 'react';
import { REPETITION_OPTIONS, formatRate } from '../../hooks/useNexaCartLive.js';
import {
  Plug,
  RotateCw,
  Download,
  PlayCircle,
  CheckCircle2,
  AlertTriangle,
  Wrench,
} from 'lucide-react';

const VERDICT_BADGE = {
  PASS: 'bg-emerald-100 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800',
  FAIL: 'bg-rose-100 dark:bg-rose-950/80 text-rose-700 dark:text-rose-300 border-rose-300 dark:border-rose-800',
  INCONCLUSIVE: 'bg-amber-100 dark:bg-amber-950/80 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-800',
};
const NEUTRAL_BADGE = 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-300 dark:border-slate-700';

export function verdictBadge(verdict) {
  return VERDICT_BADGE[verdict] || NEUTRAL_BADGE;
}

function Notice({ error, successMessage }) {
  return (
    <>
      {error && (
        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-700 dark:text-rose-300 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {successMessage && (
        <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-700 dark:text-emerald-300 flex items-start gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}
    </>
  );
}

function ReadinessSummary({ readiness }) {
  if (!readiness) return null;
  const stateChanging = (readiness.tools || []).filter((t) => t.is_state_changing).length;
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
      <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-700">
        <div className="text-slate-500 dark:text-slate-400">Harness</div>
        <div className={`font-bold ${readiness.is_ready ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
          {readiness.status}
        </div>
        <div className="font-mono text-[11px] text-slate-500 break-all">{readiness.base_url}</div>
      </div>
      <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-700">
        <div className="text-slate-500 dark:text-slate-400">Agent under test</div>
        <div className="font-bold text-slate-800 dark:text-slate-200">
          {readiness.agent?.model || 'unknown'}
        </div>
        <div className="text-[11px] text-slate-500">{readiness.agent?.provider}</div>
      </div>
      <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-700">
        <div className="text-slate-500 dark:text-slate-400">Real tools</div>
        <div className="font-bold text-slate-800 dark:text-slate-200">{(readiness.tools || []).length}</div>
        <div className="text-[11px] text-slate-500">{stateChanging} state-changing</div>
      </div>
      {readiness.blockers?.length > 0 && (
        <div className="sm:col-span-3 text-rose-600 dark:text-rose-400">Blockers: {readiness.blockers.join('; ')}</div>
      )}
    </div>
  );
}

export function NexaCartLiveImportPanel({ live, onImported }) {
  const handleImport = async () => {
    const result = await live.importDomain();
    if (result && onImported) onImported(result);
  };

  return (
    <div className="p-5 rounded-2xl border border-indigo-200 dark:border-indigo-900 bg-indigo-50/40 dark:bg-indigo-950/20 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Plug className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <h3 className="text-base font-bold text-slate-900 dark:text-white">Live Target: NexaCart Customer Assistant</h3>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Imports the NexaCart policy document, its domain binding over the 14 real agent tools, and reference candidate
            rules. Continue with review, contract acceptance, case generation and live runs below.
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <button
            type="button"
            onClick={live.checkReadiness}
            disabled={live.isCheckingReadiness}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-200 hover:bg-white dark:hover:bg-slate-800 disabled:opacity-50"
          >
            <RotateCw className={`w-3.5 h-3.5 ${live.isCheckingReadiness ? 'animate-spin' : ''}`} />
            Check NexaCart
          </button>
          <button
            type="button"
            onClick={handleImport}
            disabled={live.isImporting}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            <Download className="w-3.5 h-3.5" />
            {live.isImporting ? 'Importing…' : 'Import NexaCart Policy'}
          </button>
        </div>
      </div>

      <ReadinessSummary readiness={live.readiness} />
      <Notice error={live.error} successMessage={live.successMessage} />

      {live.importResult?.next_steps?.length > 0 && (
        <ol className="list-decimal list-inside text-xs text-slate-600 dark:text-slate-300 space-y-1">
          {live.importResult.next_steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      )}
    </div>
  );
}

function CaseRatesTable({ caseRates }) {
  const cases = caseRates?.cases || [];
  if (cases.length === 0) return null;
  const overall = caseRates.overall || {};
  return (
    <div className="space-y-2">
      <div className="text-xs font-semibold text-slate-700 dark:text-slate-300">Per-case rates over repeated runs</div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-slate-500 dark:text-slate-400">
              <th className="py-1 pr-3">Case</th>
              <th className="py-1 pr-3">Kind</th>
              <th className="py-1 pr-3">Runs</th>
              <th className="py-1 pr-3">PASS</th>
              <th className="py-1 pr-3">FAIL</th>
              <th className="py-1 pr-3">Undetermined</th>
              <th className="py-1 pr-3">Exposed</th>
              <th className="py-1 pr-3">Attacker achieved / blocked</th>
              <th className="py-1 pr-3">Stability</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((c) => (
              <tr key={c.case_id} className="border-t border-slate-200 dark:border-slate-800">
                <td className="py-1.5 pr-3 font-mono">{c.case_id}</td>
                <td className="py-1.5 pr-3">{c.test_kind}</td>
                <td className="py-1.5 pr-3">{c.runs}</td>
                <td className="py-1.5 pr-3">
                  {c.verdict_counts?.PASS || 0} ({formatRate(c.pass_rate)})
                </td>
                <td className={`py-1.5 pr-3 ${c.verdict_counts?.FAIL ? 'font-bold text-rose-600 dark:text-rose-400' : ''}`}>
                  {c.verdict_counts?.FAIL || 0} ({formatRate(c.fail_rate)})
                </td>
                <td className="py-1.5 pr-3">{formatRate(c.undetermined_rate)}</td>
                <td className="py-1.5 pr-3">{formatRate(c.exposure_rate)}</td>
                <td className="py-1.5 pr-3">
                  {formatRate(c.attacker_achieved_rate)} / {formatRate(c.attacker_blocked_rate)}
                </td>
                <td className="py-1.5 pr-3">
                  <span className={`px-2 py-0.5 rounded border ${c.stability === 'STABLE' ? NEUTRAL_BADGE : VERDICT_BADGE.INCONCLUSIVE}`}>
                    {c.stability}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="text-[11px] text-slate-500 dark:text-slate-400">
        {overall.runs} runs • violation rate when the challenge reached the agent:{' '}
        <span className="font-semibold">{formatRate(overall.violation_rate_when_reached)}</span> (
        {overall.challenge_reached_runs} reached) • Undetermined = INCONCLUSIVE, NOT_EXERCISED or ERROR, never counted as PASS.
      </div>
    </div>
  );
}

export function NexaCartLiveRunPanel({ live, acceptedContract, frozenCaseCount, onFinished, onOpenRun }) {
  const isAccepted = acceptedContract?.lifecycle_state === 'ACCEPTED';
  const execution = live.execution;
  const canStart = isAccepted && frozenCaseCount > 0 && !live.isStarting && !live.isRunning;
  const [repetitions, setRepetitions] = useState(3);

  const handleStart = () =>
    live.startExecution(
      { contractId: acceptedContract.contract_id, contractVersion: acceptedContract.version, repetitions },
      onFinished
    );

  return (
    <div className="p-5 rounded-2xl border border-indigo-200 dark:border-indigo-900 bg-indigo-50/40 dark:bg-indigo-950/20 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <PlayCircle className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <h3 className="text-base font-bold text-slate-900 dark:text-white">Live Execution on NexaCart (LIVE_AUT)</h3>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            {isAccepted
              ? `Contract ${acceptedContract.contract_id} v${acceptedContract.version} • ${frozenCaseCount} frozen NexaCart case(s). Each run seeds an isolated NexaCart fixture, runs the real agent, and evaluates captured evidence. LLM behaviour varies between runs, so cases are repeated and reported as rates.`
              : 'Accept a contract and generate + freeze NexaCart cases first.'}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <label className="text-xs text-slate-600 dark:text-slate-300 flex items-center gap-1.5">
            Runs per case
            <select
              aria-label="Runs per case"
              value={repetitions}
              onChange={(e) => setRepetitions(Number(e.target.value))}
              disabled={live.isRunning}
              className="px-2 py-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
            >
              {REPETITION_OPTIONS.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={handleStart}
            disabled={!canStart}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            <PlayCircle className="w-3.5 h-3.5" />
            {live.isRunning ? 'Running…' : 'Run Frozen Cases Live'}
          </button>
        </div>
      </div>

      {/* Import messages belong to the import panel; this panel reports executions only. */}
      <Notice error={live.error} successMessage={execution ? live.successMessage : null} />

      {execution && (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs text-slate-600 dark:text-slate-300">
            <span className="font-mono">{execution.execution_id}</span>
            <span>
              {execution.status} • {execution.completed_runs}/{execution.total_runs} runs ({execution.total_cases} cases ×{' '}
              {execution.repetitions})
              {execution.current_case_id && live.isRunning
                ? ` • run ${execution.current_repetition} of ${execution.current_case_id}`
                : ''}
            </span>
          </div>
          <div className="h-1.5 rounded bg-slate-200 dark:bg-slate-800 overflow-hidden">
            <div
              className="h-full bg-indigo-500 transition-all"
              style={{ width: `${execution.total_runs ? (100 * execution.completed_runs) / execution.total_runs : 0}%` }}
            />
          </div>

          <CaseRatesTable caseRates={execution.case_rates} />

          {execution.case_results?.length > 0 && (
            <details className="text-xs">
              <summary className="cursor-pointer font-semibold text-slate-700 dark:text-slate-300">
                Individual runs ({execution.case_results.length})
              </summary>
              <div className="overflow-x-auto mt-2">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-slate-500 dark:text-slate-400">
                      <th className="py-1 pr-3">Case</th>
                      <th className="py-1 pr-3">Run</th>
                      <th className="py-1 pr-3">Verdict</th>
                      <th className="py-1 pr-3">Exposure</th>
                      <th className="py-1 pr-3">Attacker</th>
                      <th className="py-1 pr-3">Utility</th>
                    </tr>
                  </thead>
                  <tbody>
                    {execution.case_results.map((r) => (
                      <tr key={`${r.case_id}#${r.repetition}`} className="border-t border-slate-200 dark:border-slate-800">
                        <td className="py-1.5 pr-3 font-mono">
                          {r.run_id && onOpenRun ? (
                            <button type="button" className="text-indigo-600 dark:text-indigo-400 hover:underline" onClick={() => onOpenRun(r.run_id)}>
                              {r.case_id}
                            </button>
                          ) : (
                            r.case_id
                          )}
                          {r.error_message && <div className="text-rose-600 dark:text-rose-400">{r.error_message}</div>}
                        </td>
                        <td className="py-1.5 pr-3">#{r.repetition}</td>
                        <td className="py-1.5 pr-3">
                          <span className={`px-2 py-0.5 rounded border ${verdictBadge(r.policy_verdict)}`}>{r.policy_verdict || r.status}</span>
                        </td>
                        <td className="py-1.5 pr-3">{r.exposure_status}</td>
                        <td className="py-1.5 pr-3">{r.attacker_objective_outcome}</td>
                        <td className="py-1.5 pr-3">{r.task_utility_outcome}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

export function LiveNexaCartEvidence({ runRecord }) {
  const live = runRecord?.evaluation_report_summary?.live_nexacart;
  if (!live) return null;
  return (
    <div className="p-4 rounded-xl border border-indigo-200 dark:border-indigo-900 space-y-3 text-xs">
      <h5 className="font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
        <Wrench className="w-3.5 h-3.5" />
        Live NexaCart Agent Run
      </h5>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-slate-600 dark:text-slate-300">
        <div>
          Agent run: <span className="font-mono break-all">{live.nexacart_agent_run_id}</span>
        </div>
        <div>
          Model: <span className="font-mono">{live.agent_model}</span> ({live.agent_status})
        </div>
        <div>Untrusted payload delivered: {live.injection_delivered ? 'yes' : 'no'}</div>
      </div>
      <div>
        <div className="font-semibold text-slate-700 dark:text-slate-300 mb-1">Tool calls ({(live.tool_calls || []).length})</div>
        {(live.tool_calls || []).length === 0 ? (
          <div className="text-slate-500">The agent called no tools.</div>
        ) : (
          <ol className="space-y-1">
            {live.tool_calls.map((c) => (
              <li key={c.call_index} className="font-mono break-all">
                #{c.call_index} {c.tool_name} {JSON.stringify(c.arguments)}{' '}
                <span className={c.success ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}>
                  {c.success ? 'ok' : `error: ${c.error}`}
                </span>
              </li>
            ))}
          </ol>
        )}
      </div>
      {live.final_answer && (
        <div>
          <div className="font-semibold text-slate-700 dark:text-slate-300 mb-1">Final answer</div>
          <p className="whitespace-pre-wrap text-slate-600 dark:text-slate-300 max-h-40 overflow-y-auto">{live.final_answer}</p>
        </div>
      )}
    </div>
  );
}
