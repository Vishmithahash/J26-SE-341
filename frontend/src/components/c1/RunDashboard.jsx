import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Play,
  RotateCcw,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Clock,
  Square,
  Lock,
  Layers,
  History,
  ShieldCheck,
  ChevronRight,
  ExternalLink,
  Cpu,
} from 'lucide-react';
import { c1Api, RUN_STATUSES } from './c1Api';

export const RunDashboard = ({
  projectId,
  suitesList,
  onRunSelected,
  onViewResults,
}) => {
  const [selectedSuiteId, setSelectedSuiteId] = useState('');
  const [deadlineSeconds, setDeadlineSeconds] = useState(60);
  const [codeVersion, setCodeVersion] = useState('');
  const [adapterOverride, setAdapterOverride] = useState('');
  const [activeRun, setActiveRun] = useState(null);
  const [pastRuns, setPastRuns] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isRerunning, setIsRerunning] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [adapterReadiness, setAdapterReadiness] = useState(null);
  const [isCheckingAdapter, setIsCheckingAdapter] = useState(false);

  // Polling ref to guarantee cleanup
  const pollingTimerRef = useRef(null);
  const isMountedRef = useRef(true);

  // Set initial selected suite
  useEffect(() => {
    if (suitesList && suitesList.length > 0 && !selectedSuiteId) {
      setSelectedSuiteId(suitesList[0].suite_id);
    }
  }, [suitesList, selectedSuiteId]);

  // Load past execution runs
  const loadPastRuns = useCallback(async () => {
    if (!projectId) return;
    try {
      const runs = await c1Api.listExecutionRuns(projectId, { limit: 20 });
      if (isMountedRef.current) {
        setPastRuns(runs || []);
      }
    } catch {
      // Non-blocking history load
    }
  }, [projectId]);

  useEffect(() => {
    isMountedRef.current = true;
    loadPastRuns();

    return () => {
      isMountedRef.current = false;
      if (pollingTimerRef.current) {
        clearTimeout(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }
    };
  }, [loadPastRuns]);

  // Adapter readiness check
  const handleCheckAdapter = async () => {
    setIsCheckingAdapter(true);
    setErrorMsg(null);
    try {
      const res = await c1Api.checkAdapterReadiness(projectId);
      if (isMountedRef.current) {
        setAdapterReadiness(res);
      }
    } catch (err) {
      if (isMountedRef.current) {
        setErrorMsg(err.message || 'Adapter connection check failed.');
      }
    } finally {
      if (isMountedRef.current) {
        setIsCheckingAdapter(false);
      }
    }
  };

  // Poll active run until terminal state
  const pollRunStatus = useCallback(
    async (runId, attempt = 1) => {
      if (!isMountedRef.current || !projectId || !runId) return;

      try {
        const detail = await c1Api.getExecutionRun(projectId, runId);
        if (!isMountedRef.current) return;

        setActiveRun(detail);
        if (onRunSelected) {
          onRunSelected(detail);
        }

        const status = detail.summary?.status;
        const isTerminal =
          status === RUN_STATUSES.COMPLETED ||
          status === RUN_STATUSES.FAILED ||
          status === RUN_STATUSES.ABORTED;

        if (!isTerminal) {
          // Bounded polling interval: 1500ms
          pollingTimerRef.current = setTimeout(() => {
            pollRunStatus(runId, attempt + 1);
          }, 1500);
        } else {
          // Terminal reached - refresh history list
          loadPastRuns();
        }
      } catch (err) {
        // Back off on network glitch up to 5s
        if (attempt < 10 && isMountedRef.current) {
          pollingTimerRef.current = setTimeout(() => {
            pollRunStatus(runId, attempt + 1);
          }, 3000);
        } else if (isMountedRef.current) {
          setErrorMsg(err.message || 'Lost connection while tracking execution run.');
        }
      }
    },
    [projectId, onRunSelected, loadPastRuns]
  );

  // Submit test run
  const handleStartRun = async (e) => {
    if (e) e.preventDefault();
    if (!selectedSuiteId) {
      setErrorMsg('Please select an accepted test suite to execute.');
      return;
    }

    // Clear previous polling
    if (pollingTimerRef.current) {
      clearTimeout(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }

    setIsSubmitting(true);
    setErrorMsg(null);

    // Generate unique idempotency key
    const idempotencyKey = `c1_run_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;

    const payload = {
      suite_id: selectedSuiteId.trim(),
      idempotency_key: idempotencyKey,
      deadline_seconds: Number(deadlineSeconds) || 60,
      evaluator_version: 'c1-evaluator-v1.0',
      code_version: codeVersion.trim() || null,
      adapter_override: adapterOverride.trim() || null,
    };

    try {
      const initialDetail = await c1Api.startExecutionRun(projectId, payload);
      setActiveRun(initialDetail);
      if (onRunSelected) {
        onRunSelected(initialDetail);
      }

      const status = initialDetail.summary?.status;
      const isTerminal =
        status === RUN_STATUSES.COMPLETED ||
        status === RUN_STATUSES.FAILED ||
        status === RUN_STATUSES.ABORTED;

      if (!isTerminal) {
        pollingTimerRef.current = setTimeout(() => {
          pollRunStatus(initialDetail.summary.run_id, 1);
        }, 1200);
      } else {
        loadPastRuns();
      }
    } catch (err) {
      setErrorMsg(err.message || 'Failed to start execution run.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Cancel execution run
  const handleCancelRun = async () => {
    if (!activeRun?.summary?.run_id) return;
    setIsCancelling(true);
    try {
      const updated = await c1Api.cancelExecutionRun(projectId, activeRun.summary.run_id);
      setActiveRun(updated);
      if (onRunSelected) onRunSelected(updated);
      loadPastRuns();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to cancel execution run.');
    } finally {
      setIsCancelling(false);
    }
  };

  // Rerun execution
  const handleRerun = async (runId) => {
    if (!runId) return;
    if (pollingTimerRef.current) {
      clearTimeout(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }

    setIsRerunning(true);
    setErrorMsg(null);
    try {
      const rerunDetail = await c1Api.rerunExecution(projectId, runId);
      setActiveRun(rerunDetail);
      if (onRunSelected) onRunSelected(rerunDetail);
      loadPastRuns();
      // Start polling the new run
      pollingTimerRef.current = setTimeout(() => {
        pollRunStatus(rerunDetail.summary.run_id, 1);
      }, 1200);
    } catch (err) {
      setErrorMsg(err.message || 'Failed to rerun test suite.');
    } finally {
      setIsRerunning(false);
    }
  };

  const selectedSuite = (suitesList || []).find((s) => s.suite_id === selectedSuiteId);
  const isRunActive =
    activeRun?.summary?.status === RUN_STATUSES.PENDING ||
    activeRun?.summary?.status === RUN_STATUSES.INITIALIZING ||
    activeRun?.summary?.status === RUN_STATUSES.RUNNING;

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-slate-900 dark:text-white flex items-center gap-2">
            <Play className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            Tool-Call Test Suite Execution Sandbox
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Execute accepted, frozen suites in isolated sessions and capture evidence without leaking QA expectations to the agent
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleCheckAdapter}
            disabled={isCheckingAdapter}
            className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-50"
          >
            <Cpu className="w-3.5 h-3.5" />
            {isCheckingAdapter ? 'Checking...' : 'Check Agent Adapter'}
          </button>
        </div>
      </div>

      {/* Adapter Readiness Result */}
      {adapterReadiness && (
        <div className="p-3 rounded-lg bg-indigo-50/60 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-800 text-xs text-indigo-900 dark:text-indigo-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-600" />
            <span>
              Adapter Status: <strong>{adapterReadiness.status || 'READY'}</strong> (Ref: {adapterReadiness.agent_connection_ref})
            </span>
          </div>
          <span className="text-[11px] text-slate-500">
            Transport: {adapterReadiness.transport || 'HTTP/SSE'}
          </span>
        </div>
      )}

      {/* Error Banner */}
      {errorMsg && (
        <div className="flex items-center gap-2 p-3 text-xs rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-300">
          <XCircle className="w-4 h-4 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Suite Selection & Launch Parameters */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
            <Lock className="w-4 h-4 text-emerald-600" />
            1. Select Accepted Test Suite
          </h3>

          {suitesList.length === 0 ? (
            <div className="p-6 text-center rounded-lg border border-dashed border-slate-200 dark:border-slate-800 text-slate-400 text-xs">
              No accepted test suites found. Promote valid candidate cases from the &quot;Test Cases&quot; tab first.
            </div>
          ) : (
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Target Frozen Suite <span className="text-red-500">*</span>
                </label>
                <select
                  value={selectedSuiteId}
                  onChange={(e) => setSelectedSuiteId(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white font-mono"
                >
                  {suitesList.map((s) => (
                    <option key={s.suite_id} value={s.suite_id}>
                      {s.suite_id} (v{s.version}) — {s.name}
                    </option>
                  ))}
                </select>
              </div>

              {selectedSuite && (
                <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 text-xs space-y-1">
                  <div className="font-semibold text-slate-900 dark:text-white">
                    {selectedSuite.name}
                  </div>
                  <div className="text-[11px] text-slate-500 dark:text-slate-400">
                    Configuration ID: {selectedSuite.config_id || 'Active'} | Version: v{selectedSuite.version} | Frozen: Yes
                  </div>
                </div>
              )}

              {/* Execution Options */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
                <div>
                  <label className="block text-[11px] font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Per-Case Timeout (Seconds)
                  </label>
                  <input
                    type="number"
                    min="5"
                    max="600"
                    value={deadlineSeconds}
                    onChange={(e) => setDeadlineSeconds(e.target.value)}
                    className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Code Commit / Version (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. git:main#a8b3f2"
                    value={codeVersion}
                    onChange={(e) => setCodeVersion(e.target.value)}
                    className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white font-mono"
                  />
                </div>
              </div>

              <div className="pt-2">
                <button
                  type="button"
                  onClick={handleStartRun}
                  disabled={isSubmitting || isRunActive || !selectedSuiteId}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm disabled:opacity-50 transition-all"
                >
                  {isSubmitting ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Initiating Execution Run...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-3.5 h-3.5 fill-current" />
                      <span>Launch Test Suite Run</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Active Run Status Card */}
        <div className="p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              Active Run Progress
            </h3>
            {isRunActive && (
              <button
                type="button"
                onClick={handleCancelRun}
                disabled={isCancelling}
                className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-medium rounded text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40"
              >
                <Square className="w-3 h-3" />
                {isCancelling ? 'Cancelling...' : 'Cancel'}
              </button>
            )}
          </div>

          {!activeRun ? (
            <div className="p-6 text-center text-slate-400 text-xs border border-dashed border-slate-200 dark:border-slate-800 rounded-lg">
              No run in progress. Launch a suite run to follow real-time execution.
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono font-bold text-slate-900 dark:text-white">
                  {activeRun.summary.run_id.slice(0, 12)}...
                </span>
                <span
                  className={`inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-semibold rounded-full ${
                    activeRun.summary.status === RUN_STATUSES.COMPLETED
                      ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400'
                      : activeRun.summary.status === RUN_STATUSES.FAILED
                      ? 'bg-red-50 text-red-700 dark:bg-red-950/60 dark:text-red-400'
                      : activeRun.summary.status === RUN_STATUSES.ABORTED
                      ? 'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-400'
                      : 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-400'
                  }`}
                >
                  <Clock className="w-3 h-3" />
                  {activeRun.summary.status}
                </span>
              </div>

              {/* Progress Counters */}
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="p-2 rounded bg-slate-50 dark:bg-slate-800/60">
                  <div className="text-[10px] text-slate-500">Total Cases</div>
                  <div className="font-bold text-slate-900 dark:text-white">
                    {activeRun.summary.total_cases}
                  </div>
                </div>
                <div className="p-2 rounded bg-slate-50 dark:bg-slate-800/60">
                  <div className="text-[10px] text-slate-500">Passed</div>
                  <div className="font-bold text-emerald-600">
                    {activeRun.summary.passed_cases}
                  </div>
                </div>
                <div className="p-2 rounded bg-slate-50 dark:bg-slate-800/60">
                  <div className="text-[10px] text-slate-500">Failed</div>
                  <div className="font-bold text-red-600">
                    {activeRun.summary.failed_cases}
                  </div>
                </div>
                <div className="p-2 rounded bg-slate-50 dark:bg-slate-800/60">
                  <div className="text-[10px] text-slate-500">Inconclusive</div>
                  <div className="font-bold text-amber-600">
                    {activeRun.summary.inconclusive_cases}
                  </div>
                </div>
              </div>

              {/* View Results CTA */}
              {onViewResults && (
                <button
                  type="button"
                  onClick={() => onViewResults(activeRun.summary.run_id)}
                  className="w-full inline-flex items-center justify-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100"
                >
                  <span>Inspect Results &amp; Evidence</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Execution Runs History */}
      <div className="p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-2">
          <History className="w-4 h-4 text-slate-500" />
          Execution Runs History
        </h3>

        {pastRuns.length === 0 ? (
          <div className="p-6 text-center text-slate-400 text-xs">
            No previous execution runs recorded for this project.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 text-[11px] font-semibold text-slate-500 dark:text-slate-400">
                  <th className="py-2 px-3">Run ID</th>
                  <th className="py-2 px-3">Suite</th>
                  <th className="py-2 px-3">Status</th>
                  <th className="py-2 px-3">Cases</th>
                  <th className="py-2 px-3">Outcomes</th>
                  <th className="py-2 px-3">Date</th>
                  <th className="py-2 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                {pastRuns.map((r) => (
                  <tr key={r.run_id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40">
                    <td className="py-2 px-3 font-mono font-medium text-slate-900 dark:text-white">
                      {r.run_id.slice(0, 10)}...
                    </td>
                    <td className="py-2 px-3 font-mono text-slate-600 dark:text-slate-400">
                      {r.suite_id} (v{r.suite_version})
                    </td>
                    <td className="py-2 px-3">
                      <span
                        className={`inline-flex px-2 py-0.5 text-[10px] font-semibold rounded-full ${
                          r.status === 'COMPLETED'
                            ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400'
                            : r.status === 'FAILED'
                            ? 'bg-red-50 text-red-700 dark:bg-red-950/60 dark:text-red-400'
                            : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                        }`}
                      >
                        {r.status}
                      </span>
                    </td>
                    <td className="py-2 px-3 font-medium text-slate-700 dark:text-slate-300">
                      {r.total_cases}
                    </td>
                    <td className="py-2 px-3">
                      <span className="text-emerald-600 font-semibold">{r.passed_cases} P</span>
                      {' / '}
                      <span className="text-red-600 font-semibold">{r.failed_cases} F</span>
                      {' / '}
                      <span className="text-amber-600 font-semibold">{r.inconclusive_cases} Inc</span>
                    </td>
                    <td className="py-2 px-3 text-slate-500 text-[11px]">
                      {new Date(r.created_at).toLocaleString()}
                    </td>
                    <td className="py-2 px-3 text-right space-x-2">
                      <button
                        type="button"
                        onClick={() => handleRerun(r.run_id)}
                        disabled={isRerunning}
                        className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-600 dark:text-slate-400 hover:text-indigo-600"
                      >
                        <RotateCcw className="w-3 h-3" />
                        Rerun
                      </button>
                      {onViewResults && (
                        <button
                          type="button"
                          onClick={() => onViewResults(r.run_id)}
                          className="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
                        >
                          Results
                          <ChevronRight className="w-3 h-3" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
