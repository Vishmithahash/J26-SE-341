import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  BarChart3,
  CheckCircle,
  XCircle,
  AlertTriangle,
  HelpCircle,
  Search,
  ChevronRight,
  ChevronDown,
  Terminal,
  Database,
  FileText,
  Clock,
  Layers,
  ShieldCheck,
  Eye,
  AlertCircle,
  RefreshCw,
  FileDown,
  Sparkles,
} from 'lucide-react';
import {
  c1Api,
  formatValue,
  escapeText,
  CORRECTNESS_VERDICTS,
  TRACE_COMPLETENESS,
} from './c1Api';
import { DiagnosisPanel } from './DiagnosisPanel';
import { CorrectionReviewPanel } from './CorrectionReviewPanel';
import { ReportingModal } from './ReportingModal';
import { ExecutionProvenanceBadge } from './ExecutionProvenanceBadge';
import { liveAgentRunInfo } from './provenanceUtils';

export const ResultsViewer = ({
  projectId,
  initialRunId,
  onSelectRun,
  currentUser,
  correctionEnabled = true,
}) => {
  const [runsList, setRunsList] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState(initialRunId || '');
  const [runDetail, setRunDetail] = useState(null);
  const [selectedCaseId, setSelectedCaseId] = useState(null);
  const [caseExecutionDetail, setCaseExecutionDetail] = useState(null);
  const [isLoadingRun, setIsLoadingRun] = useState(false);
  const [isLoadingCase, setIsLoadingCase] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  // Filters
  const [verdictFilter, setVerdictFilter] = useState('ALL'); // 'ALL', 'PASS', 'FAIL', 'INCONCLUSIVE'
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedCheckId, setExpandedCheckId] = useState(null);
  const [expandedEventId, setExpandedEventId] = useState(null);

  // Phase 3 Modal / Panel State
  const [showReportingModal, setShowReportingModal] = useState(false);
  const [activeDiagnosis, setActiveDiagnosis] = useState(null);
  const [showCorrectionPanel, setShowCorrectionPanel] = useState(false);

  // Load available runs
  useEffect(() => {
    let isCancelled = false;
    if (!projectId) return;

    const fetchRuns = async () => {
      try {
        const list = await c1Api.listExecutionRuns(projectId, { limit: 30 });
        if (!isCancelled) {
          setRunsList(list || []);
          if (!selectedRunId && list && list.length > 0) {
            setSelectedRunId(list[0].run_id);
          }
        }
      } catch {
        // Handled silently
      }
    };

    fetchRuns();

    return () => {
      isCancelled = true;
    };
  }, [projectId]);

  // Sync initialRunId when prop changes
  useEffect(() => {
    if (initialRunId) {
      setSelectedRunId(initialRunId);
    }
  }, [initialRunId]);

  // Load full run detail
  const loadRunDetail = useCallback(async (runId) => {
    if (!projectId || !runId) return;
    setIsLoadingRun(true);
    setErrorMsg(null);
    try {
      const detail = await c1Api.getExecutionRun(projectId, runId);
      setRunDetail(detail);
      if (detail.case_executions && detail.case_executions.length > 0) {
        setSelectedCaseId(detail.case_executions[0].case_id);
      } else {
        setSelectedCaseId(null);
        setCaseExecutionDetail(null);
      }
    } catch (err) {
      setErrorMsg(err.message || 'Failed to load execution run results.');
    } finally {
      setIsLoadingRun(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (selectedRunId) {
      loadRunDetail(selectedRunId);
    }
  }, [selectedRunId, loadRunDetail]);

  // Lazy load full case execution detail when selected
  useEffect(() => {
    let isCancelled = false;
    if (!projectId || !selectedRunId || !selectedCaseId) {
      setCaseExecutionDetail(null);
      setActiveDiagnosis(null);
      setShowCorrectionPanel(false);
      return;
    }

    const fetchCaseDetail = async () => {
      setIsLoadingCase(true);
      try {
        const caseDetail = await c1Api.getCaseExecution(
          projectId,
          selectedRunId,
          selectedCaseId
        );
        if (!isCancelled) {
          setCaseExecutionDetail(caseDetail);
        }
      } catch {
        // Fallback to inline summary if detailed endpoint unavailable
        if (!isCancelled && runDetail?.case_executions) {
          const fallback = runDetail.case_executions.find(
            (c) => c.case_id === selectedCaseId
          );
          setCaseExecutionDetail(fallback || null);
        }
      } finally {
        if (!isCancelled) {
          setIsLoadingCase(false);
        }
      }
    };

    fetchCaseDetail();

    return () => {
      isCancelled = true;
    };
  }, [projectId, selectedRunId, selectedCaseId, runDetail]);

  // Filter case executions
  const filteredCases = useMemo(() => {
    if (!runDetail?.case_executions) return [];
    return runDetail.case_executions.filter((c) => {
      if (verdictFilter !== 'ALL' && c.verdict !== verdictFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchId = c.case_id.toLowerCase().includes(q);
        const matchPrompt = c.agent_task_sent?.task_prompt?.toLowerCase().includes(q);
        if (!matchId && !matchPrompt) return false;
      }
      return true;
    });
  }, [runDetail, verdictFilter, searchQuery]);

  const summary = runDetail?.summary;
  const liveRun = liveAgentRunInfo(caseExecutionDetail);

  return (
    <div className="space-y-6">
      {/* Run Selector & Header */}
      <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-slate-900 dark:text-white flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            Tool-Call Correctness Results &amp; Evidence Inspector
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Backend-evaluated correctness verdicts, parameter diffs, and evidence-linked explanations
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {runDetail && <ExecutionProvenanceBadge runOrCase={runDetail} compact />}
          {runsList.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500 dark:text-slate-400">Run:</span>
              <select
                value={selectedRunId}
                onChange={(e) => {
                  setSelectedRunId(e.target.value);
                  if (onSelectRun) onSelectRun(e.target.value);
                }}
                className="px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white font-mono"
              >
                {runsList.map((r) => (
                  <option key={r.run_id} value={r.run_id}>
                    {r.run_id.slice(0, 10)}... ({r.suite_id} v{r.suite_version}) — {r.status}
                  </option>
                ))}
              </select>
            </div>
          )}

          <button
            type="button"
            onClick={() => loadRunDetail(selectedRunId)}
            disabled={isLoadingRun || !selectedRunId}
            className="p-1.5 text-slate-500 hover:text-slate-800 dark:hover:text-white rounded-lg border border-slate-300 dark:border-slate-700"
            title="Refresh Run Detail"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoadingRun ? 'animate-spin' : ''}`} />
          </button>

          {/* Reporting & Research Metrics Action */}
          <button
            type="button"
            onClick={() => setShowReportingModal(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-950"
          >
            <FileDown className="w-3.5 h-3.5" />
            <span>Reports &amp; Metrics</span>
          </button>
        </div>
      </div>

      {errorMsg && (
        <div className="p-3 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-xs text-red-800 dark:text-red-300">
          {errorMsg}
        </div>
      )}

      {/* Summary Scorecards */}
      {summary && (
        <div className="space-y-2">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className="p-3 rounded-xl border border-emerald-200 dark:border-emerald-900/50 bg-emerald-50/40 dark:bg-emerald-950/20">
              <div className="text-[11px] font-medium text-emerald-800 dark:text-emerald-400 flex items-center gap-1">
                <CheckCircle className="w-3.5 h-3.5" /> PASS (Compliant)
              </div>
              <div className="text-xl font-bold text-emerald-700 dark:text-emerald-300 mt-1">
                {summary.passed_cases}
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">
                of {summary.total_cases} total cases
              </div>
            </div>

            <div className="p-3 rounded-xl border border-red-200 dark:border-red-900/50 bg-red-50/40 dark:bg-red-950/20">
              <div className="text-[11px] font-medium text-red-800 dark:text-red-400 flex items-center gap-1">
                <XCircle className="w-3.5 h-3.5" /> FAIL (Violations)
              </div>
              <div className="text-xl font-bold text-red-700 dark:text-red-300 mt-1">
                {summary.failed_cases}
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">
                of {summary.total_cases} total cases
              </div>
            </div>

            <div className="p-3 rounded-xl border border-amber-200 dark:border-amber-900/50 bg-amber-50/40 dark:bg-amber-950/20">
              <div className="text-[11px] font-medium text-amber-800 dark:text-amber-400 flex items-center gap-1">
                <HelpCircle className="w-3.5 h-3.5" /> INCONCLUSIVE
              </div>
              <div className="text-xl font-bold text-amber-700 dark:text-amber-300 mt-1">
                {summary.inconclusive_cases}
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">
                insufficient evidence
              </div>
            </div>

            <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
              <div className="text-[11px] font-medium text-slate-600 dark:text-slate-400 flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5 text-slate-500" /> Execution Errors
              </div>
              <div className="text-xl font-bold text-slate-800 dark:text-slate-200 mt-1">
                {summary.error_cases}
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">
                runner/setup faults
              </div>
            </div>

            <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
              <div className="text-[11px] font-medium text-slate-600 dark:text-slate-400 flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-indigo-500" /> Run Status
              </div>
              <div className="text-sm font-bold text-slate-900 dark:text-white mt-1">
                {summary.status}
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">
                v{summary.suite_version} ({summary.suite_id})
              </div>
            </div>
          </div>

          <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-2">
            <span className="font-semibold text-slate-700 dark:text-slate-300">Methodological Note:</span>
            <span>
              Pass counts reflect automated check evaluations. Correctness pass rates are distinct from benchmark accuracy, which requires independently verified reference labels.
            </span>
          </div>
        </div>
      )}

      {/* Per-case outcomes over repetitions (agent variability) */}
      {summary && summary.repetitions > 1 && Object.keys(summary.repetition_summary || {}).length > 0 && (
        <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-2">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
            Repeated runs: {summary.repetitions} per case (outcomes per case, not new cases)
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-slate-500">
                  <th className="py-1 pr-3 font-semibold">Case</th>
                  <th className="py-1 pr-3 font-semibold">Runs</th>
                  <th className="py-1 pr-3 font-semibold">PASS</th>
                  <th className="py-1 pr-3 font-semibold">FAIL</th>
                  <th className="py-1 pr-3 font-semibold">INCONCLUSIVE</th>
                  <th className="py-1 pr-3 font-semibold">Error</th>
                  <th className="py-1 pr-3 font-semibold">Pass rate (definite verdicts)</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(summary.repetition_summary).map(([caseId, r]) => (
                  <tr key={caseId} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="py-1 pr-3 font-mono">{caseId}</td>
                    <td className="py-1 pr-3">{r.runs}</td>
                    <td className="py-1 pr-3">{r.PASS}</td>
                    <td className="py-1 pr-3">{r.FAIL}</td>
                    <td className="py-1 pr-3">{r.INCONCLUSIVE}</td>
                    <td className="py-1 pr-3">{r.ERROR}</td>
                    <td className="py-1 pr-3">
                      {r.pass_rate === null || r.pass_rate === undefined
                        ? 'n/a'
                        : `${Math.round(r.pass_rate * 100)}%`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Filter and Case Details Split View */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left Column: Case List */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              Evaluated Cases ({filteredCases.length})
            </span>
          </div>

          {/* Filter Toolbar */}
          <div className="space-y-2">
            <div className="flex rounded-lg border border-slate-200 dark:border-slate-700 p-0.5 bg-slate-50 dark:bg-slate-800 text-[11px]">
              {['ALL', 'PASS', 'FAIL', 'INCONCLUSIVE'].map((v) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setVerdictFilter(v)}
                  className={`flex-1 py-1 rounded-md font-medium transition-colors ${
                    verdictFilter === v
                      ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs font-semibold'
                      : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                  }`}
                >
                  {v}
                </button>
              ))}
            </div>

            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search case ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
              />
            </div>
          </div>

          {/* Cases Scrollable List */}
          {isLoadingRun ? (
            <div className="p-8 text-center text-slate-500 text-xs">
              <div className="w-5 h-5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
              Loading run results...
            </div>
          ) : filteredCases.length === 0 ? (
            <div className="p-6 text-center text-slate-400 text-xs border border-dashed border-slate-200 dark:border-slate-800 rounded-lg">
              No cases match the selected verdict filter.
            </div>
          ) : (
            <div className="space-y-2 max-h-[580px] overflow-y-auto pr-1">
              {filteredCases.map((c) => {
                const isSelected = selectedCaseId === c.case_id;
                return (
                  <div
                    key={c.case_id}
                    onClick={() => {
                      setSelectedCaseId(c.case_id);
                      setShowCorrectionPanel(false);
                    }}
                    tabIndex={0}
                    role="button"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        setSelectedCaseId(c.case_id);
                        setShowCorrectionPanel(false);
                      }
                    }}
                    className={`p-3 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? 'border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/30 shadow-xs'
                        : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-slate-300'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="font-mono text-xs font-bold text-slate-900 dark:text-white">
                        {c.case_id}
                      </div>
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-bold rounded-full ${
                          c.verdict === CORRECTNESS_VERDICTS.PASS
                            ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-400'
                            : c.verdict === CORRECTNESS_VERDICTS.FAIL
                            ? 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-400'
                            : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-400'
                        }`}
                      >
                        {c.verdict || 'PENDING'}
                      </span>
                    </div>

                    <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-1 flex items-center justify-between">
                      <span>Exec: {c.execution_status}</span>
                      <span>Attempt #{c.attempt_number || 1}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Column: Case Details, Diagnosis, and Correction */}
        <div className="md:col-span-2 space-y-4">
          {isLoadingCase ? (
            <div className="p-12 text-center text-slate-500 text-xs border border-slate-200 dark:border-slate-800 rounded-xl bg-white dark:bg-slate-900">
              <div className="w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
              Loading case execution details and captured trace...
            </div>
          ) : !caseExecutionDetail ? (
            <div className="p-12 text-center text-slate-400 text-xs border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
              Select a case from the left panel to inspect check results, diagnosis, and evidence.
            </div>
          ) : (
            <div className="space-y-4">
              {/* Case Header Card */}
              <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3">
                <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-bold text-slate-900 dark:text-white">
                        {caseExecutionDetail.case_id}
                      </span>
                      <span className="text-xs text-slate-400">
                        (Session: {caseExecutionDetail.session_id?.slice(0, 8)}...)
                      </span>
                    </div>
                    <div className="text-xs text-slate-500 mt-0.5 flex flex-wrap items-center gap-2">
                      <span>Execution Status: <strong className="text-slate-700 dark:text-slate-300">{caseExecutionDetail.execution_status}</strong></span>
                      <ExecutionProvenanceBadge runOrCase={caseExecutionDetail} compact />
                    </div>
                  </div>

                  <div className="text-right">
                    <span
                      className={`inline-flex items-center gap-1.5 px-3 py-1 text-xs font-bold rounded-lg ${
                        caseExecutionDetail.verdict === CORRECTNESS_VERDICTS.PASS
                          ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-400'
                          : caseExecutionDetail.verdict === CORRECTNESS_VERDICTS.FAIL
                          ? 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-400'
                          : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-400'
                      }`}
                    >
                      {caseExecutionDetail.verdict === CORRECTNESS_VERDICTS.PASS && <CheckCircle className="w-4 h-4" />}
                      {caseExecutionDetail.verdict === CORRECTNESS_VERDICTS.FAIL && <XCircle className="w-4 h-4" />}
                      {caseExecutionDetail.verdict === CORRECTNESS_VERDICTS.INCONCLUSIVE && <HelpCircle className="w-4 h-4" />}
                      Verdict: {caseExecutionDetail.verdict}
                    </span>
                    <div className="text-[10px] text-slate-400 mt-1">
                      Trace: {caseExecutionDetail.trace_completeness}
                    </div>
                  </div>
                </div>

                {/* Error Banner if runner/setup fault */}
                {caseExecutionDetail.error_message && (
                  <div className="p-3 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-xs text-red-800 dark:text-red-300">
                    <strong className="font-semibold">Execution Failure:</strong> {caseExecutionDetail.error_message}
                  </div>
                )}

                {/* Sent Agent Task Prompt */}
                {caseExecutionDetail.agent_task_sent && (
                  <div className="space-y-1">
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                      Task Prompt Presented to Agent
                    </div>
                    <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800 text-xs text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700 font-mono">
                      {caseExecutionDetail.agent_task_sent.task_prompt}
                    </div>
                  </div>
                )}

                {/* Live NexaCart agent run (real application evidence) */}
                {liveRun && (
                  <div className="space-y-1">
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                      Live NexaCart Agent Run
                    </div>
                    <div className="p-2.5 rounded-lg bg-emerald-50/60 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-900 text-xs text-slate-700 dark:text-slate-300 space-y-1">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-1">
                        <div>Agent run: <span className="font-mono">{liveRun.agentRunId || 'not reported'}</span></div>
                        <div>Model: <span className="font-mono">{[liveRun.provider, liveRun.model].filter(Boolean).join(' / ') || 'not reported'}</span></div>
                        <div>Agent status: <strong>{liveRun.agentStatus || 'n/a'}</strong> ({liveRun.outcome || 'n/a'})</div>
                        <div>NexaCart fixture: <span className="font-mono">{liveRun.fixtureId || 'n/a'}</span></div>
                        {liveRun.durationMs !== null && (
                          <div>Agent duration: {(liveRun.durationMs / 1000).toFixed(1)} s</div>
                        )}
                        {liveRun.harnessVersion && <div>QA harness: v{liveRun.harnessVersion}</div>}
                      </div>
                      {liveRun.error && (
                        <div className="text-red-700 dark:text-red-400">Error: {liveRun.error}</div>
                      )}
                      {liveRun.finalAnswer && (
                        <div>
                          <span className="font-semibold">Agent final answer:</span>{' '}
                          <span className="whitespace-pre-wrap">{liveRun.finalAnswer}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Phase 3: Root Cause Diagnosis & Code Attribution Panel */}
              <DiagnosisPanel
                correctionEnabled={correctionEnabled}
                projectId={projectId}
                runId={selectedRunId}
                caseId={caseExecutionDetail.case_id}
                caseVerdict={caseExecutionDetail.verdict}
                existingDiagnosis={activeDiagnosis}
                onRequestCorrection={(diag) => {
                  setActiveDiagnosis(diag);
                  setShowCorrectionPanel(true);
                }}
              />

              {/* Phase 3: Sandbox Verification & Developer Review Panel */}
              {correctionEnabled && showCorrectionPanel && activeDiagnosis && (
                <CorrectionReviewPanel
                  projectId={projectId}
                  diagnosisId={activeDiagnosis.diagnosis_id}
                  caseId={caseExecutionDetail.case_id}
                  runId={selectedRunId}
                  currentUser={currentUser}
                  onReviewSubmitted={() => {
                    // Refresh run detail on review
                    loadRunDetail(selectedRunId);
                  }}
                />
              )}

              {/* Check-Level Results */}
              <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-indigo-600" />
                  Declarative Check-Level Evaluations ({caseExecutionDetail.check_results?.length || 0})
                </h4>

                {(!caseExecutionDetail.check_results || caseExecutionDetail.check_results.length === 0) ? (
                  <div className="text-xs text-slate-400 italic">No individual checks recorded for this case.</div>
                ) : (
                  <div className="space-y-2">
                    {caseExecutionDetail.check_results.map((check, idx) => {
                      const isExpanded = expandedCheckId === check.check_id;
                      return (
                        <div
                          key={check.check_id || idx}
                          className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40 text-xs"
                        >
                          <div
                            onClick={() => setExpandedCheckId(isExpanded ? null : check.check_id)}
                            className="flex items-center justify-between p-2.5 cursor-pointer select-none"
                          >
                            <div className="flex items-center gap-2">
                              {isExpanded ? <ChevronDown className="w-3.5 h-3.5 text-slate-400" /> : <ChevronRight className="w-3.5 h-3.5 text-slate-400" />}
                              <strong className="text-slate-900 dark:text-white font-mono">
                                {check.rule_name}
                              </strong>
                              {check.target_tool && (
                                <span className="text-[11px] text-slate-500">
                                  tool: <strong>{check.target_tool}</strong>
                                </span>
                              )}
                              {check.target_argument && (
                                <span className="text-[11px] text-slate-500">
                                  arg: <strong>{check.target_argument}</strong>
                                </span>
                              )}
                            </div>

                            <span
                              className={`px-2 py-0.5 text-[10px] font-bold rounded-full ${
                                check.verdict === 'PASS'
                                  ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-400'
                                  : check.verdict === 'FAIL'
                                  ? 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-400'
                                  : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-400'
                              }`}
                            >
                              {check.verdict} ({check.reason_code})
                            </span>
                          </div>

                          {isExpanded && (
                            <div className="p-3 border-t border-slate-200 dark:border-slate-800 space-y-2 bg-white dark:bg-slate-900 rounded-b-lg">
                              <p className="text-xs text-slate-700 dark:text-slate-300">
                                {check.explanation}
                              </p>

                              {/* Parameter Diff: Expected vs Actual */}
                              <div className="grid grid-cols-2 gap-2 text-[11px] pt-1">
                                <div className="p-2 rounded bg-slate-50 dark:bg-slate-800">
                                  <span className="text-slate-500 font-semibold block mb-0.5">Expected:</span>
                                  <code className="text-slate-800 dark:text-slate-200 font-mono">
                                    {formatValue(check.expected_value)}
                                  </code>
                                </div>
                                <div className="p-2 rounded bg-slate-50 dark:bg-slate-800">
                                  <span className="text-slate-500 font-semibold block mb-0.5">Actual Observed:</span>
                                  <code className="text-slate-800 dark:text-slate-200 font-mono">
                                    {formatValue(check.actual_value)}
                                  </code>
                                </div>
                              </div>

                              {check.evidence_refs && check.evidence_refs.length > 0 && (
                                <div className="text-[10px] text-slate-400 pt-1">
                                  Corroborating Evidence IDs: {check.evidence_refs.join(', ')}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Ordered Tool-Call Timeline */}
              <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                  <Terminal className="w-4 h-4 text-indigo-600" />
                  Captured Tool-Call Timeline ({caseExecutionDetail.captured_events?.length || 0})
                </h4>

                {(!caseExecutionDetail.captured_events || caseExecutionDetail.captured_events.length === 0) ? (
                  <div className="text-xs text-slate-400 italic">No tool calls were invoked by the agent in this session.</div>
                ) : (
                  <div className="space-y-3">
                    {caseExecutionDetail.captured_events
                      .sort((a, b) => (a.call_index ?? 0) - (b.call_index ?? 0))
                      .map((evt, idx) => {
                        const isExpanded = expandedEventId === evt.event_id;
                        return (
                          <div
                            key={evt.event_id || idx}
                            className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/40 dark:bg-slate-800/40 space-y-2 text-xs"
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <span className="w-5 h-5 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 flex items-center justify-center text-[10px] font-bold">
                                  {evt.call_index ?? idx + 1}
                                </span>
                                <strong className="font-mono text-slate-900 dark:text-white">
                                  {evt.tool_name}
                                </strong>
                                <span
                                  className={`px-1.5 py-0.5 text-[10px] font-semibold rounded ${
                                    evt.status === 'SUCCESS'
                                      ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-400'
                                      : 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-400'
                                  }`}
                                >
                                  {evt.status}
                                </span>
                              </div>
                              <span className="text-[10px] text-slate-400">
                                {new Date(evt.timestamp).toLocaleTimeString()}
                              </span>
                            </div>

                            {/* Tool Arguments */}
                            <div>
                              <div className="text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-0.5">
                                Arguments:
                              </div>
                              <pre className="p-2 rounded bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-slate-100 font-mono text-[11px] overflow-x-auto whitespace-pre-wrap">
                                {escapeText(JSON.stringify(evt.arguments || {}, null, 2))}
                              </pre>
                            </div>

                            {/* Tool Response or Error */}
                            {evt.tool_error ? (
                              <div className="p-2 rounded bg-red-50 dark:bg-red-950/60 text-red-800 dark:text-red-300 font-mono text-[11px]">
                                Error: {escapeText(evt.tool_error)}
                              </div>
                            ) : evt.tool_response !== undefined && evt.tool_response !== null && (
                              <div>
                                <button
                                  type="button"
                                  onClick={() => setExpandedEventId(isExpanded ? null : evt.event_id)}
                                  className="text-[11px] font-semibold text-indigo-600 dark:text-indigo-400 hover:underline inline-flex items-center gap-1"
                                >
                                  {isExpanded ? 'Hide Tool Response' : 'Show Tool Response'}
                                  {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                                </button>
                                {isExpanded && (
                                  <pre className="mt-1 p-2 rounded bg-slate-100 dark:bg-slate-950 text-slate-900 dark:text-slate-100 font-mono text-[11px] overflow-x-auto whitespace-pre-wrap">
                                    {escapeText(
                                      typeof evt.tool_response === 'object'
                                        ? JSON.stringify(evt.tool_response, null, 2)
                                        : String(evt.tool_response)
                                    )}
                                  </pre>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Phase 3 Reporting & Research Metrics Modal */}
      {showReportingModal && (
        <ReportingModal
          projectId={projectId}
          activeRunId={selectedRunId}
          correctionEnabled={correctionEnabled}
          onClose={() => setShowReportingModal(false)}
        />
      )}
    </div>
  );
};
