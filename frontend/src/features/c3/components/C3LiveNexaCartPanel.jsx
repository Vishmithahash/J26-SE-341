import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Play,
  RotateCw,
  Server,
  Sparkles,
  XCircle,
} from 'lucide-react';
import { c3Api } from '../api.js';
import { C3Badge } from './C3Badge.jsx';
import { summarizeConsistency } from '../consistency.js';

const POLL_INTERVAL_MS = 5000;
const TERMINAL_STATUSES = ['COMPLETED', 'ERROR', 'CANCELLED', 'INTERRUPTED'];

/**
 * Live C3 workflow on NexaCart: harness readiness, automatic capability-aware suite generation,
 * matched clean/fault trials with NexaCart's own LLM agent, and per-case recovery verdicts.
 */
export const C3LiveNexaCartPanel = ({ projectId, onOpenTrials }) => {
  const [readiness, setReadiness] = useState(null);
  const [readinessError, setReadinessError] = useState(null);
  const [isCheckingReadiness, setIsCheckingReadiness] = useState(false);

  const [maxCases, setMaxCases] = useState(8);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generation, setGeneration] = useState(null);
  const [generationError, setGenerationError] = useState(null);

  const [selectedCaseIds, setSelectedCaseIds] = useState([]);
  const [repetitions, setRepetitions] = useState(1);
  const [isStarting, setIsStarting] = useState(false);
  const [execution, setExecution] = useState(null);
  const [executionError, setExecutionError] = useState(null);
  const pollRef = useRef(null);

  const suite = generation?.generation?.frozen_suite || null;
  const storedSuite = generation?.stored_suite || null;

  const checkReadiness = useCallback(async () => {
    if (!projectId) return;
    setIsCheckingReadiness(true);
    setReadinessError(null);
    try {
      setReadiness(await c3Api.getLiveReadiness(projectId));
    } catch (err) {
      setReadinessError(err.message || 'Failed to check NexaCart readiness.');
    } finally {
      setIsCheckingReadiness(false);
    }
  }, [projectId]);

  useEffect(() => {
    checkReadiness();
  }, [checkReadiness]);

  useEffect(() => () => clearInterval(pollRef.current), []);

  const handleGenerate = async () => {
    setIsGenerating(true);
    setGenerationError(null);
    setGeneration(null);
    // A running execution stays visible (and keeps Run disabled) while a new suite is generated.
    setExecution((current) => (current && !TERMINAL_STATUSES.includes(current.status) ? current : null));
    try {
      const res = await c3Api.generateLiveSuite({
        project_id: projectId,
        max_cases: Number(maxCases) || 8,
      });
      setGeneration(res);
      setSelectedCaseIds((res.generation?.frozen_suite?.selected_cases || []).map((c) => c.case_id));
      if (!res.stored_suite) {
        setGenerationError(
          `No feasible cases generated (${res.generation?.generation_status || 'unknown status'}).`
        );
      }
    } catch (err) {
      setGenerationError(err.message || 'Failed to generate the NexaCart fault suite.');
    } finally {
      setIsGenerating(false);
    }
  };

  const pollExecution = useCallback(
    (executionId) => {
      clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const rec = await c3Api.getExecution(projectId, executionId);
          setExecution(rec);
          if (TERMINAL_STATUSES.includes(rec.status)) {
            clearInterval(pollRef.current);
          }
        } catch (err) {
          setExecutionError(err.message || 'Failed to refresh execution status.');
          clearInterval(pollRef.current);
        }
      }, POLL_INTERVAL_MS);
    },
    [projectId]
  );

  const handleRun = async () => {
    if (!storedSuite || selectedCaseIds.length === 0) return;
    setIsStarting(true);
    setExecutionError(null);
    try {
      const res = await c3Api.startLiveExecution({
        project_id: projectId,
        suite_id_or_digest: storedSuite.suite_digest,
        case_ids: selectedCaseIds,
        repetitions,
      });
      setExecution(res.execution);
      pollExecution(res.execution.execution_id);
    } catch (err) {
      setExecutionError(err.message || 'Failed to start the live execution.');
    } finally {
      setIsStarting(false);
    }
  };

  // Reopening the page reconnects to the latest live execution (running ones keep refreshing).
  useEffect(() => {
    if (!projectId) return undefined;
    const controller = new AbortController();
    c3Api
      .listLiveExecutions(projectId, { limit: 1 }, controller.signal)
      .then((res) => {
        const latest = res.items?.[0];
        if (!latest) return;
        setExecution((current) => current || latest);
        if (!TERMINAL_STATUSES.includes(latest.status)) pollExecution(latest.execution_id);
      })
      .catch(() => {});
    return () => controller.abort();
  }, [projectId, pollExecution]);

  const [isCancelling, setIsCancelling] = useState(false);
  const handleCancel = async () => {
    if (!execution) return;
    setIsCancelling(true);
    setExecutionError(null);
    try {
      const rec = await c3Api.cancelLiveExecution(projectId, execution.execution_id);
      setExecution(rec);
      if (TERMINAL_STATUSES.includes(rec.status)) clearInterval(pollRef.current);
    } catch (err) {
      setExecutionError(err.message || 'Failed to cancel the live execution.');
    } finally {
      setIsCancelling(false);
    }
  };

  const toggleCase = (caseId) => {
    setSelectedCaseIds((ids) =>
      ids.includes(caseId) ? ids.filter((id) => id !== caseId) : [...ids, caseId]
    );
  };

  const caseResults = execution?.manifest_snapshot?.case_results || [];
  const planned = execution?.planned_cases_count ?? selectedCaseIds.length;
  const isRunning = execution && !TERMINAL_STATUSES.includes(execution.status);
  const runRepetitions = execution?.manifest_snapshot?.configuration?.repetitions || 1;
  const consistency = summarizeConsistency(caseResults);

  if (!projectId) {
    return (
      <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 text-xs text-slate-500">
        Select an active project to run live NexaCart robustness tests.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 1. Target readiness */}
      <section className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Server className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <span>1. Live Target: NexaCart QA Harness</span>
          </h2>
          <button
            type="button"
            onClick={checkReadiness}
            disabled={isCheckingReadiness}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 disabled:opacity-50"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isCheckingReadiness ? 'animate-spin' : ''}`} />
            <span>Check Readiness</span>
          </button>
        </div>

        {readinessError && (
          <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 text-xs text-rose-700 dark:text-rose-300">
            {readinessError}
          </div>
        )}

        {readiness && (
          <div className="space-y-2 text-xs">
            <div className="flex items-center gap-2 flex-wrap">
              <C3Badge status={readiness.ready ? 'READY' : 'BLOCKED'} label={readiness.ready ? 'Ready' : 'Blocked'} />
              <span className="font-mono text-slate-500">{readiness.base_url || '—'}</span>
              {readiness.harness_version && (
                <span className="text-slate-500">Harness v{readiness.harness_version}</span>
              )}
              {readiness.agent && (
                <span className="text-slate-500">
                  Agent: {readiness.agent.provider} {readiness.agent.model}
                </span>
              )}
            </div>
            {!readiness.ready && (
              <ul className="list-disc list-inside text-rose-700 dark:text-rose-300">
                {readiness.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            )}
            {readiness.ready && (
              <p className="text-slate-600 dark:text-slate-400">
                {readiness.tools.length} tools ({readiness.tools.filter((t) => t.mutability === 'SIDE_EFFECTING').length}{' '}
                state-changing) and {readiness.supported_combinations_count} tool × fault × phase
                combinations reported by NexaCart's fault gateway.
              </p>
            )}
            {readiness.tasks?.map((t) => (
              <div key={t.task_id} className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
                <div className="font-semibold text-slate-800 dark:text-slate-200">
                  Task <code className="font-mono">{t.task_id}</code> v{t.task_version} · contract{' '}
                  <code className="font-mono">{t.recovery_contract_id}</code> v{t.recovery_contract_version}
                </div>
                <p className="text-slate-600 dark:text-slate-400 mt-1">“{t.instruction}”</p>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* 2. Automatic generation */}
      <section className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <span>2. Generate Capability-Aware Fault Suite</span>
          </h2>
          <div className="flex items-center gap-2">
            <label htmlFor="c3-live-max-cases" className="text-xs text-slate-600 dark:text-slate-400">
              Max cases
            </label>
            <input
              id="c3-live-max-cases"
              type="number"
              min={1}
              max={50}
              value={maxCases}
              onChange={(e) => setMaxCases(e.target.value)}
              className="w-16 px-2 py-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs"
            />
            <button
              type="button"
              onClick={handleGenerate}
              disabled={isGenerating || !readiness?.ready}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white disabled:opacity-50"
            >
              <Sparkles className={`w-3.5 h-3.5 ${isGenerating ? 'animate-spin' : ''}`} />
              <span>{isGenerating ? 'Generating…' : 'Generate & Store Suite'}</span>
            </button>
          </div>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Cases are built from NexaCart's live capability manifest, validated, deduplicated, selected to
          cover each tool × fault family × effect phase cell, and frozen with a SHA-256 digest.
        </p>

        {generationError && (
          <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 text-xs text-rose-700 dark:text-rose-300">
            {generationError}
          </div>
        )}

        {suite && (
          <div className="space-y-2 text-xs">
            <div className="text-slate-600 dark:text-slate-400 font-mono">
              Suite {suite.suite_id} · digest {suite.suite_digest.slice(0, 16)}… · examined{' '}
              {suite.counters.examined_count}, valid {suite.counters.valid_count}, rejected{' '}
              {suite.counters.rejected_count}, selected {suite.counters.selected_count}
            </div>
            <div className="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-lg">
              <table className="w-full text-left font-mono">
                <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500">
                  <tr>
                    <th className="p-2">Run</th>
                    <th className="p-2">Case</th>
                    <th className="p-2">Tool</th>
                    <th className="p-2">Fault family</th>
                    <th className="p-2">Effect phase</th>
                    <th className="p-2">Occurrence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {suite.selected_cases.map((c) => (
                    <tr key={c.case_id}>
                      <td className="p-2">
                        <input
                          type="checkbox"
                          aria-label={`Run case ${c.case_id}`}
                          checked={selectedCaseIds.includes(c.case_id)}
                          onChange={() => toggleCase(c.case_id)}
                          disabled={isRunning}
                        />
                      </td>
                      <td className="p-2 text-slate-900 dark:text-white">{c.case_id}</td>
                      <td className="p-2">{c.tool_id}</td>
                      <td className="p-2 text-indigo-600 dark:text-indigo-400">{c.fault_family}</td>
                      <td className="p-2">{c.effect_phase}</td>
                      <td className="p-2">{c.occurrence}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      {/* 3. Live matched trials */}
      <section className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Activity className="w-4 h-4 text-teal-600 dark:text-teal-400" />
            <span>3. Run Matched Clean / Fault Trials on NexaCart</span>
          </h2>
          <label className="ml-auto inline-flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-400">
            Repeat each case
            <select
              value={repetitions}
              onChange={(e) => setRepetitions(Number(e.target.value))}
              disabled={isStarting || isRunning}
              aria-label="Repetitions per case"
              className="px-2 py-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800"
            >
              {[1, 2, 3].map((n) => (
                <option key={n} value={n}>
                  {n}×
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={handleRun}
            disabled={!storedSuite || selectedCaseIds.length === 0 || isStarting || isRunning}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-teal-600 hover:bg-teal-700 text-white disabled:opacity-50"
          >
            <Play className={`w-3.5 h-3.5 ${isStarting || isRunning ? 'animate-pulse' : ''}`} />
            <span>
              {isRunning
                ? 'Running…'
                : `Run ${selectedCaseIds.length} Case${selectedCaseIds.length === 1 ? '' : 's'}${
                    repetitions > 1 ? ` × ${repetitions}` : ''
                  } Live`}
            </span>
          </button>
          {isRunning && (
            <button
              type="button"
              onClick={handleCancel}
              disabled={isCancelling || Boolean(execution?.manifest_snapshot?.cancel_requested_at)}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-rose-600 hover:bg-rose-700 text-white disabled:opacity-50"
            >
              <XCircle className="w-3.5 h-3.5" />
              <span>
                {execution?.manifest_snapshot?.cancel_requested_at ? 'Cancel requested' : 'Cancel Run'}
              </span>
            </button>
          )}
        </div>
        {isRunning && execution?.manifest_snapshot?.cancel_requested_at && (
          <p className="text-xs text-amber-700 dark:text-amber-300" aria-live="polite">
            Cancel requested by {execution.manifest_snapshot.cancel_requested_by}. The case in progress
            finishes first (an agent run cannot be stopped midway); the remaining cases will not run.
          </p>
        )}
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Each case runs a clean trial and a fault trial on fresh NexaCart fixtures with NexaCart's own
          LLM agent (about 1–3 minutes per case). Repeating a case runs it again as a new matched pair,
          so you can see whether the agent's recovery is consistent. Progress refreshes every{' '}
          {POLL_INTERVAL_MS / 1000} seconds.
        </p>

        {executionError && (
          <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 text-xs text-rose-700 dark:text-rose-300 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{executionError}</span>
          </div>
        )}

        {execution && (
          <div className="space-y-3 text-xs" aria-live="polite">
            <div className="flex items-center gap-2 flex-wrap">
              <C3Badge status={execution.status} label={execution.status} />
              <span className="font-mono text-slate-600 dark:text-slate-400">{execution.execution_id}</span>
              <span className="text-slate-600 dark:text-slate-400">
                {caseResults.length} / {planned} {runRepetitions > 1 ? 'runs' : 'cases'} finished
                {runRepetitions > 1 && ` (each case × ${runRepetitions})`}
              </span>
            </div>
            {execution.halt_reason && (
              <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-950/30 text-amber-800 dark:text-amber-300">
                {execution.halt_reason}
              </div>
            )}
            {runRepetitions > 1 && consistency.length > 0 && (
              <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 space-y-1.5">
                <p className="font-semibold text-slate-700 dark:text-slate-300">Verdict consistency across repeats</p>
                {consistency.map((c) => (
                  <div key={c.caseId} className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-slate-600 dark:text-slate-400">{c.caseId}</span>
                    {c.counts.map(([verdict, n]) => (
                      <span key={verdict} className="inline-flex items-center gap-1">
                        <C3Badge status={verdict} label={verdict} /> {n}/{c.runs}
                      </span>
                    ))}
                    <span className={c.consistent ? 'text-emerald-700 dark:text-emerald-300' : 'text-amber-700 dark:text-amber-300'}>
                      {c.consistent ? 'consistent' : 'varies between runs'}
                    </span>
                  </div>
                ))}
              </div>
            )}
            {caseResults.length > 0 && (
              <div className="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-lg">
                <table className="w-full text-left">
                  <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500">
                    <tr>
                      <th className="p-2">Case</th>
                      <th className="p-2">Repeat</th>
                      <th className="p-2">Run status</th>
                      <th className="p-2">Clean control</th>
                      <th className="p-2">Exposure</th>
                      <th className="p-2">Recovery verdict</th>
                      <th className="p-2">First violated rule / reason</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {caseResults.map((r, i) => (
                      <tr key={`${r.case_id}-${r.repetition || 1}-${i}`}>
                        <td className="p-2 font-mono">{r.case_id}</td>
                        <td className="p-2">{r.repetition || 1}</td>
                        <td className="p-2"><C3Badge status={r.status} label={r.status} /></td>
                        <td className="p-2">{r.clean_qualification ? <C3Badge status={r.clean_qualification} label={r.clean_qualification} /> : '—'}</td>
                        <td className="p-2">{r.exposure_status ? <C3Badge status={r.exposure_status} label={r.exposure_status} /> : '—'}</td>
                        <td className="p-2">
                          {r.recovery_verdict ? (
                            <C3Badge status={r.recovery_verdict} />
                          ) : (
                            <span className="text-slate-500">Not evaluated</span>
                          )}
                        </td>
                        <td className="p-2 text-slate-600 dark:text-slate-400">
                          {r.first_violated_rule || (r.reasons || []).join('; ') || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {execution.status === 'COMPLETED' && (
              <div className="flex items-center justify-between gap-2 flex-wrap p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/30 text-emerald-800 dark:text-emerald-200">
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4" />
                  Pairs and recovery evaluations were stored for this execution.
                </span>
                {onOpenTrials && (
                  <button
                    type="button"
                    onClick={onOpenTrials}
                    className="px-3 py-1 rounded-lg bg-white dark:bg-slate-900 border border-emerald-300 dark:border-emerald-800 font-semibold"
                  >
                    Inspect Matched Trials & Evidence
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
};

