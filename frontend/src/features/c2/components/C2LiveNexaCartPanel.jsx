import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  GitBranch,
  Play,
  RotateCw,
  Server,
  ShieldCheck,
} from 'lucide-react';
import { c2Api } from '../api/c2Api.js';
import { VERDICT_CONFIG } from '../constants/resultsConfig.js';

const POLL_INTERVAL_MS = 5000;
const TERMINAL_STATUSES = ['COMPLETED', 'ERROR', 'CANCELLED'];

const STATUS_STYLES = {
  APPROVED: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800',
  DRAFT: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800',
  RUNNING: 'bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/60 dark:text-indigo-300 dark:border-indigo-800',
  COMPLETED: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800',
  ERROR: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-800',
  CANCELLED: 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700',
  NONE: 'bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700',
};

const Badge = ({ text, style }) => (
  <span className={`inline-flex items-center px-2 py-0.5 rounded-md border text-[10px] font-bold uppercase tracking-wide ${style}`}>
    {text}
  </span>
);

const VerdictBadge = ({ verdict, status }) => {
  if (!verdict) {
    return <Badge text={status || 'NO VERDICT'} style={STATUS_STYLES[status] || STATUS_STYLES.NONE} />;
  }
  const cfg = VERDICT_CONFIG[verdict] || VERDICT_CONFIG.INCONCLUSIVE;
  return <Badge text={cfg.badgeText} style={cfg.badge} />;
};

const Metric = ({ label, value, hint }) => (
  <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
    <div className="text-[10px] font-semibold uppercase text-slate-400">{label}</div>
    <div className="text-lg font-bold text-slate-900 dark:text-slate-100 mt-0.5">{value ?? '—'}</div>
    {hint && <div className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">{hint}</div>}
  </div>
);

const pct = (v) => (v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`);

/**
 * Component 2 on the real NexaCart application: reference EFSMs over NexaCart's tools,
 * automatically generated suites, live runs with NexaCart's own LLM agent, and
 * workflow-conformance verdicts with first-divergence localisation and coverage.
 */
export const C2LiveNexaCartPanel = ({
  projectId,
  suites = [],
  onModelsChanged,
  onSuitesChanged,
  onEvaluationsChanged,
  onOpenModels,
  onOpenSuites,
}) => {
  const [readiness, setReadiness] = useState(null);
  const [readinessError, setReadinessError] = useState(null);
  const [isChecking, setIsChecking] = useState(false);

  const [workflows, setWorkflows] = useState([]);
  const [workflowsError, setWorkflowsError] = useState(null);
  const [importingId, setImportingId] = useState(null);

  const [suiteId, setSuiteId] = useState('');
  const [cases, setCases] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [casesError, setCasesError] = useState(null);

  const [execution, setExecution] = useState(null);
  const [executionError, setExecutionError] = useState(null);
  const [isStarting, setIsStarting] = useState(false);
  const [history, setHistory] = useState([]);
  const [expanded, setExpanded] = useState(null);
  const pollRef = useRef(null);

  const workflowIds = useMemo(() => new Set(workflows.map((w) => w.model_id)), [workflows]);
  const liveSuites = useMemo(
    () => (suites || []).filter((s) => workflowIds.has(s.model_id)),
    [suites, workflowIds]
  );

  const checkReadiness = useCallback(async () => {
    if (!projectId) return;
    setIsChecking(true);
    setReadinessError(null);
    try {
      setReadiness(await c2Api.getLiveReadiness(projectId));
    } catch (err) {
      setReadinessError(err.message || 'Failed to check NexaCart readiness.');
    } finally {
      setIsChecking(false);
    }
  }, [projectId]);

  const loadWorkflows = useCallback(async () => {
    if (!projectId) return;
    setWorkflowsError(null);
    try {
      setWorkflows((await c2Api.listLiveWorkflows(projectId)) || []);
    } catch (err) {
      setWorkflowsError(err.message || 'Failed to load NexaCart reference workflows.');
    }
  }, [projectId]);

  const loadHistory = useCallback(
    async (sid) => {
      if (!projectId) return;
      try {
        setHistory((await c2Api.listLiveExecutions(projectId, sid || null)) || []);
      } catch {
        setHistory([]);
      }
    },
    [projectId]
  );

  useEffect(() => {
    checkReadiness();
    loadWorkflows();
  }, [checkReadiness, loadWorkflows]);

  useEffect(() => () => clearInterval(pollRef.current), []);

  useEffect(() => {
    setCases([]);
    setSelectedIds([]);
    setCasesError(null);
    if (!suiteId || !projectId) return;
    let cancelled = false;
    (async () => {
      try {
        const list = (await c2Api.listTestCases(projectId, suiteId)) || [];
        if (cancelled) return;
        setCases(list);
        // Default selection: the first ready case of each live category plus every mutant.
        const firstPerCategory = {};
        list.forEach((c) => {
          if (c.category !== 'mutated' && (c.readiness || 'TEST_READY') === 'TEST_READY' && !firstPerCategory[c.category]) {
            firstPerCategory[c.category] = c.test_id;
          }
        });
        setSelectedIds([
          ...Object.values(firstPerCategory),
          ...list.filter((c) => c.category === 'mutated').map((c) => c.test_id),
        ]);
      } catch (err) {
        if (!cancelled) setCasesError(err.message || 'Failed to load suite cases.');
      }
    })();
    loadHistory(suiteId);
    return () => {
      cancelled = true;
    };
  }, [suiteId, projectId, loadHistory]);

  const handleImport = async (modelId) => {
    setImportingId(modelId);
    setWorkflowsError(null);
    try {
      await c2Api.importLiveWorkflow(projectId, modelId);
      await loadWorkflows();
      if (onModelsChanged) await onModelsChanged();
    } catch (err) {
      setWorkflowsError(err.message || 'Failed to import the reference workflow.');
    } finally {
      setImportingId(null);
    }
  };

  const poll = useCallback(
    (executionId) => {
      clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const rec = await c2Api.getLiveExecution(projectId, executionId);
          setExecution(rec);
          if (TERMINAL_STATUSES.includes(rec.status)) {
            clearInterval(pollRef.current);
            loadHistory(rec.suite_id);
            if (onEvaluationsChanged) onEvaluationsChanged();
          }
        } catch (err) {
          setExecutionError(err.message || 'Failed to refresh the execution.');
          clearInterval(pollRef.current);
        }
      }, POLL_INTERVAL_MS);
    },
    [projectId, loadHistory, onEvaluationsChanged]
  );

  const handleRun = async () => {
    if (!suiteId || selectedIds.length === 0) return;
    setIsStarting(true);
    setExecutionError(null);
    try {
      const rec = await c2Api.startLiveExecution(projectId, { suiteId, testIds: selectedIds });
      setExecution(rec);
      poll(rec.execution_id);
    } catch (err) {
      setExecutionError(err.message || 'Failed to start the live execution.');
    } finally {
      setIsStarting(false);
    }
  };

  const openExecution = async (executionId) => {
    try {
      const rec = await c2Api.getLiveExecution(projectId, executionId);
      setExecution(rec);
      if (!TERMINAL_STATUSES.includes(rec.status)) poll(executionId);
    } catch (err) {
      setExecutionError(err.message || 'Failed to load the execution.');
    }
  };

  const toggle = (id) =>
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const selectBy = (predicate) => setSelectedIds(cases.filter(predicate).map((c) => c.test_id));

  const exportExecution = () => {
    if (!execution) return;
    const blob = new Blob([JSON.stringify(execution, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${execution.execution_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const summary = execution?.summary || {};
  const results = execution?.case_results || [];
  // Parents of selected mutants run live too, so results can exceed the selected cases.
  const selectedSet = new Set(execution?.planned_test_ids || []);
  const extraParents = results.filter((r) => !selectedSet.has(r.test_id)).length;
  const progress = execution
    ? `${results.length - extraParents} of ${selectedSet.size} selected cases done` +
      (extraParents ? ` · ${extraParents} parent case(s) run live for mutants` : '')
    : null;

  return (
    <div className="space-y-5" aria-label="Live NexaCart workflow testing">
      {/* Readiness */}
      <section className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <Server className="w-5 h-5 text-indigo-600 dark:text-indigo-400 mt-0.5" />
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Live NexaCart target</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Generated workflow tests are executed by NexaCart&apos;s own LLM agent through the external QA
                harness. Only the task text is sent to the agent; reference paths stay in the QA framework.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={checkReadiness}
            disabled={isChecking}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 disabled:opacity-50"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isChecking ? 'animate-spin' : ''}`} /> Recheck
          </button>
        </div>
        {readinessError && <p className="mt-3 text-xs text-rose-600">{readinessError}</p>}
        {readiness && (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
            <Badge
              text={readiness.ready ? 'READY' : 'BLOCKED'}
              style={readiness.ready ? STATUS_STYLES.COMPLETED : STATUS_STYLES.ERROR}
            />
            <span className="font-mono">{readiness.base_url}</span>
            {readiness.ready && (
              <>
                <span>· harness {readiness.harness_version}</span>
                <span>
                  · agent {readiness.agent?.provider} {readiness.agent?.model}
                </span>
                <span>· {readiness.tools?.length || 0} tools</span>
              </>
            )}
            {!readiness.ready &&
              (readiness.reasons || []).map((r) => (
                <span key={r} className="w-full text-rose-600">
                  {r}
                </span>
              ))}
          </div>
        )}
      </section>

      {/* Reference workflows */}
      <section className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <div className="flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">NexaCart reference workflows</h3>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          1. Import a reference EFSM (DRAFT) · 2. Validate and approve it on{' '}
          <button type="button" className="text-indigo-600 hover:underline" onClick={onOpenModels}>
            Workflow Models
          </button>{' '}
          · 3. Generate a suite on{' '}
          <button type="button" className="text-indigo-600 hover:underline" onClick={onOpenSuites}>
            Test Suites
          </button>{' '}
          · 4. Run it live below.
        </p>
        {workflowsError && <p className="mt-2 text-xs text-rose-600">{workflowsError}</p>}
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[10px] uppercase text-slate-400 border-b border-slate-200 dark:border-slate-800">
                <th className="py-2 pr-3">Workflow</th>
                <th className="py-2 pr-3">Model</th>
                <th className="py-2 pr-3">Kind</th>
                <th className="py-2 pr-3">Fixture</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2 pr-3">Suites</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {workflows.map((w) => (
                <tr key={w.model_id} className="border-b border-slate-100 dark:border-slate-800/60 align-top">
                  <td className="py-2 pr-3">
                    <div className="font-semibold text-slate-800 dark:text-slate-100">{w.title}</div>
                    <div className="text-slate-500 dark:text-slate-400 mt-0.5 max-w-md">{w.tasks?.[0]}</div>
                  </td>
                  <td className="py-2 pr-3 font-mono text-slate-600 dark:text-slate-300">
                    {w.model_id}@{w.version}
                    <div className="text-[10px] text-slate-400">
                      {w.states_count} states · {w.transitions_count} transitions
                    </div>
                  </td>
                  <td className="py-2 pr-3">{w.kind}</td>
                  <td className="py-2 pr-3 font-mono text-[10px]">{w.fixture_id}</td>
                  <td className="py-2 pr-3">
                    <Badge
                      text={w.lifecycle_status || 'NOT IMPORTED'}
                      style={STATUS_STYLES[w.lifecycle_status] || STATUS_STYLES.NONE}
                    />
                  </td>
                  <td className="py-2 pr-3">{w.suite_ids?.length || 0}</td>
                  <td className="py-2 text-right">
                    {!w.lifecycle_status && (
                      <button
                        type="button"
                        onClick={() => handleImport(w.model_id)}
                        disabled={importingId === w.model_id}
                        className="px-2.5 py-1 rounded-lg bg-indigo-600 text-white text-[11px] font-semibold hover:bg-indigo-700 disabled:opacity-50"
                      >
                        {importingId === w.model_id ? 'Importing…' : 'Import as draft'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Run live */}
      <section className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <div className="flex items-center gap-2">
          <Play className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Run a generated suite live</h3>
        </div>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <label className="text-xs text-slate-600 dark:text-slate-300">
            <span className="block text-[10px] font-semibold uppercase text-slate-400">Suite</span>
            <select
              aria-label="Live suite"
              value={suiteId}
              onChange={(e) => {
                setSuiteId(e.target.value);
                if (onSuitesChanged) onSuitesChanged();
              }}
              className="mt-1 min-w-[22rem] px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
            >
              <option value="">Select a suite generated from a NexaCart workflow…</option>
              {liveSuites.map((s) => (
                <option key={s.suite_id} value={s.suite_id}>
                  {s.model_id}@{s.model_version} · {s.total_cases} cases · {s.suite_id}
                </option>
              ))}
            </select>
          </label>
          {cases.length > 0 && (
            <div className="flex flex-wrap gap-1.5 text-[11px]">
              <button type="button" className="px-2 py-1 rounded border border-slate-200 dark:border-slate-700" onClick={() => selectBy((c) => c.category !== 'mutated')}>
                All live cases
              </button>
              <button type="button" className="px-2 py-1 rounded border border-slate-200 dark:border-slate-700" onClick={() => selectBy((c) => c.category === 'mutated')}>
                All mutants
              </button>
              <button type="button" className="px-2 py-1 rounded border border-slate-200 dark:border-slate-700" onClick={() => setSelectedIds([])}>
                Clear
              </button>
            </div>
          )}
          <button
            type="button"
            onClick={handleRun}
            disabled={!suiteId || selectedIds.length === 0 || isStarting || !readiness?.ready || execution?.status === 'RUNNING'}
            className="ml-auto inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-700 disabled:opacity-50"
          >
            <Play className="w-3.5 h-3.5" />
            {isStarting ? 'Starting…' : `Run ${selectedIds.length} case(s) live`}
          </button>
        </div>
        {liveSuites.length === 0 && (
          <p className="mt-2 text-xs text-slate-500">
            No suite yet. Approve an imported NexaCart workflow and generate a suite from it first.
          </p>
        )}
        {casesError && <p className="mt-2 text-xs text-rose-600">{casesError}</p>}
        {cases.length > 0 && (
          <div className="mt-3 max-h-64 overflow-y-auto border border-slate-100 dark:border-slate-800 rounded-lg">
            <table className="w-full text-xs">
              <tbody>
                {cases.map((c) => (
                  <tr key={c.test_id} className="border-b border-slate-100 dark:border-slate-800/60">
                    <td className="py-1.5 px-2 w-6">
                      <input
                        type="checkbox"
                        aria-label={`Select ${c.test_id}`}
                        checked={selectedIds.includes(c.test_id)}
                        onChange={() => toggle(c.test_id)}
                      />
                    </td>
                    <td className="py-1.5 px-2 font-mono">{c.test_id}</td>
                    <td className="py-1.5 px-2 uppercase text-[10px] font-semibold text-slate-500">{c.category}</td>
                    <td className="py-1.5 px-2 text-[10px]">{c.readiness}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
          Each live case is one NexaCart agent run on a fresh fixture (about 1–2 minutes with local Ollama).
          Mutants are controlled faults applied to their parent case&apos;s real trace to measure whether the
          oracle detects them; they are not agent failures.
        </p>
        {executionError && <p className="mt-2 text-xs text-rose-600">{executionError}</p>}
      </section>

      {/* Execution */}
      {execution && (
        <section className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-4" aria-label="Live execution results">
          <div className="flex flex-wrap items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Execution {execution.execution_id}</h3>
            <Badge text={execution.status} style={STATUS_STYLES[execution.status] || STATUS_STYLES.NONE} />
            <span className="text-xs text-slate-500">
              {execution.model_id}@{execution.model_version} · {progress}
            </span>
            <button
              type="button"
              onClick={exportExecution}
              className="ml-auto inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border border-slate-200 dark:border-slate-700 text-[11px] font-semibold"
            >
              <Download className="w-3.5 h-3.5" /> Export JSON
            </button>
          </div>
          {execution.halt_reason && (
            <div className="flex items-start gap-2 text-xs text-amber-700 dark:text-amber-300">
              <AlertTriangle className="w-4 h-4 shrink-0" /> {execution.halt_reason}
            </div>
          )}

          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <Metric
              label="Live conformance"
              value={pct(summary.live?.conformance_rate)}
              hint={`${summary.live?.conforming ?? 0} of ${summary.live?.executed ?? 0} live runs`}
            />
            <Metric
              label="Mutation detection"
              value={pct(summary.mutation?.detection_score)}
              hint={`${summary.mutation?.detected ?? 0} of ${summary.mutation?.applied ?? 0} applied`}
            />
            <Metric label="Inconclusive rate" value={pct(summary.live?.inconclusive_rate)} />
            <Metric
              label="Workflow transitions"
              value={pct(summary.coverage?.workflow_transition_ratio)}
              hint={`${summary.coverage?.workflow_transitions_covered ?? 0} of ${summary.coverage?.workflow_transitions_total ?? 0}`}
            />
            <Metric
              label="Median run time"
              value={
                summary.overhead?.live_case_duration_ms_median
                  ? `${Math.round(summary.overhead.live_case_duration_ms_median / 1000)} s`
                  : '—'
              }
              hint={
                summary.overhead?.live_case_duration_ms_p95
                  ? `p95 ${Math.round(summary.overhead.live_case_duration_ms_p95 / 1000)} s`
                  : null
              }
            />
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[10px] uppercase text-slate-400 border-b border-slate-200 dark:border-slate-800">
                  <th className="py-2 pr-3">Case</th>
                  <th className="py-2 pr-3">Verdict</th>
                  <th className="py-2 pr-3">Observed states</th>
                  <th className="py-2 pr-3">First divergence</th>
                  <th className="py-2 pr-3">Evidence</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <React.Fragment key={`${r.test_id}-${r.run_id}`}>
                    <tr
                      className="border-b border-slate-100 dark:border-slate-800/60 align-top cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/40"
                      onClick={() => setExpanded(expanded === r.run_id ? null : r.run_id)}
                    >
                      <td className="py-2 pr-3">
                        <div className="font-mono">{r.test_id}</div>
                        <div className="text-[10px] uppercase text-slate-400">
                          {r.category}
                          {r.mutation_type ? ` · ${r.mutation_type}` : ''}
                        </div>
                      </td>
                      <td className="py-2 pr-3">
                        <VerdictBadge verdict={r.verdict} status={r.status} />
                        {r.mutation_detected !== null && r.mutation_detected !== undefined && (
                          <div className={`mt-1 text-[10px] font-semibold ${r.mutation_detected ? 'text-emerald-600' : 'text-rose-600'}`}>
                            {r.mutation_detected ? 'mutation detected' : 'mutation missed'}
                          </div>
                        )}
                      </td>
                      <td className="py-2 pr-3 font-mono text-[10px]">{(r.observed_states || []).join(' → ') || '—'}</td>
                      <td className="py-2 pr-3 text-[10px]">
                        {r.first_divergence ? (
                          <>
                            <div className="font-semibold text-rose-600">{r.first_divergence.violation_type}</div>
                            <div>
                              event #{r.first_divergence.event_index} · {r.first_divergence.attempted_event} in{' '}
                              {r.first_divergence.state_at_divergence}
                            </div>
                          </>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="py-2 pr-3 text-[10px]">
                        {r.agent_run_id ? (
                          <div className="font-mono">agent run {r.agent_run_id}</div>
                        ) : null}
                        {r.parent_test_id ? <div>parent {r.parent_test_id}</div> : null}
                        <div className="text-slate-500">{(r.tool_sequence || []).join(', ')}</div>
                      </td>
                    </tr>
                    {expanded === r.run_id && (
                      <tr className="bg-slate-50 dark:bg-slate-800/40">
                        <td colSpan={5} className="p-3 text-[11px] space-y-1.5">
                          {r.final_answer && (
                            <div>
                              <span className="font-semibold">Agent final answer: </span>
                              {r.final_answer}
                            </div>
                          )}
                          {(r.reasons || []).map((reason) => (
                            <div key={reason}>• {reason}</div>
                          ))}
                          <div className="text-slate-500">
                            run {r.run_id} · {Math.round((r.duration_ms || 0) / 1000)} s · covered transitions:{' '}
                            {(r.covered_transitions || []).join(', ') || '—'}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
                {execution.status === 'RUNNING' && (
                  <tr>
                    <td colSpan={5} className="py-3 text-xs text-indigo-600">
                      <span className="inline-flex items-center gap-1.5">
                        <RotateCw className="w-3.5 h-3.5 animate-spin" /> NexaCart agent is running the next case…
                      </span>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {history.length > 0 && (
        <section className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Previous live executions</h3>
          <ul className="mt-2 space-y-1 text-xs">
            {history.map((h) => (
              <li key={h.execution_id} className="flex items-center gap-2">
                <button type="button" className="font-mono text-indigo-600 hover:underline" onClick={() => openExecution(h.execution_id)}>
                  {h.execution_id}
                </button>
                <Badge text={h.status} style={STATUS_STYLES[h.status] || STATUS_STYLES.NONE} />
                <span className="text-slate-500">
                  {h.case_results?.length || 0} cases · conformance {pct(h.summary?.live?.conformance_rate)} · mutation
                  detection {pct(h.summary?.mutation?.detection_score)}
                </span>
                {h.status === 'COMPLETED' && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
};

export default C2LiveNexaCartPanel;
