import React, { useState } from 'react';
import {
  Play,
  FlaskConical,
  CheckCircle2,
  AlertCircle,
  XCircle,
  RotateCw,
  ShieldCheck,
  Info,
  Layers,
  Activity,
  FileCode,
  CheckCheck,
  AlertTriangle,
  ChevronRight,
  RefreshCw,
} from 'lucide-react';

const VERDICT_STYLES = {
  PASS: {
    bg: 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800',
    icon: CheckCircle2,
    badgeText: 'PASS',
    desc: 'All state transitions, guards, and invariant checks conformed to the model specification.',
  },
  EXPECTED_REJECTION_PASS: {
    bg: 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800',
    icon: CheckCircle2,
    badgeText: 'EXPECTED REJECTION PASS',
    desc: 'Negative test correctly rejected by SUT; workflow appropriately terminated or rejected.',
  },
  FAIL: {
    bg: 'bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800',
    icon: XCircle,
    badgeText: 'FAIL',
    desc: 'Conformance violation detected: invalid transition, missed effect, or wrong entity.',
  },
  INCONCLUSIVE: {
    bg: 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800',
    icon: AlertTriangle,
    badgeText: 'INCONCLUSIVE',
    desc: 'Trace evidence was incomplete, observer missed snapshots, or execution was truncated.',
  },
  'MODEL NOT READY': {
    bg: 'bg-purple-50 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800',
    icon: AlertCircle,
    badgeText: 'MODEL NOT READY',
    desc: 'Model definition is not approved or validation report is missing/stale. Not a test failure.',
  },
  'TEST NOT READY': {
    bg: 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700',
    icon: AlertCircle,
    badgeText: 'TEST NOT READY',
    desc: 'Test case prerequisites or fixture bindings are unresolved. Not executed.',
  },
};

export const ExecutionPanel = ({
  projectId,
  suites = [],
  selectedSuite = null,
  cases = [],
  selectedCase = null,
  approvedModels = [],
  executionState,
  onOpenDemoModal,
}) => {
  const {
    evaluations,
    latestEvaluation,
    retainedEvidence,
    reproductionResult,
    isExecutingCase,
    isExecutingSuite,
    isExecutingDemo,
    isReEvaluating,
    isLoadingEvaluations,
    executionError,
    runnerCapabilities,
    executeCase,
    executeBoundedSuite,
    fetchEvidence,
    reEvaluate,
    verifyEvaluationReproduction,
    refreshEvaluations,
    setLatestEvaluation,
    clearExecutionError,
  } = executionState;

  const [activeSuiteId, setActiveSuiteId] = useState(selectedSuite?.suite_id || suites[0]?.suite_id || '');
  const [activeTestId, setActiveTestId] = useState(selectedCase?.test_id || '');
  const [suiteBudget, setSuiteBudget] = useState(20);
  const [verdictFilter, setVerdictFilter] = useState('');
  const [showEvidenceModal, setShowEvidenceModal] = useState(false);

  // Sync with prop changes
  React.useEffect(() => {
    if (selectedSuite?.suite_id) {
      setActiveSuiteId(selectedSuite.suite_id);
    }
  }, [selectedSuite?.suite_id]);

  React.useEffect(() => {
    if (selectedCase?.test_id) {
      setActiveTestId(selectedCase.test_id);
    }
  }, [selectedCase?.test_id]);

  const currentSuite = suites.find((s) => s.suite_id === activeSuiteId) || selectedSuite || null;
  const currentSuiteCases = cases.filter((c) => c.suite_id === activeSuiteId);
  const currentCase = currentSuiteCases.find((c) => c.test_id === activeTestId) || selectedCase || null;

  // Readiness gating calculations
  const hasApprovedModel = approvedModels.some((m) => m.lifecycle_status === 'APPROVED');
  const isCaseReady = currentCase ? (currentCase.is_ready || currentCase.readiness === 'TEST_READY') : false;
  const isSuiteReady = currentSuite ? (currentSuite.ready_cases_count > 0) : false;

  const anyExecuting = isExecutingCase || isExecutingSuite || isExecutingDemo || isReEvaluating;

  const currentVerdict = latestEvaluation?.verdict ? String(latestEvaluation.verdict).toUpperCase() : null;
  const verdictStyle = currentVerdict && VERDICT_STYLES[currentVerdict] ? VERDICT_STYLES[currentVerdict] : null;

  const handleRunSingleCase = async () => {
    if (!activeSuiteId || !activeTestId || anyExecuting) return;
    try {
      await executeCase(activeSuiteId, activeTestId);
    } catch {
      // error handled inside hook
    }
  };

  const handleRunBoundedSuite = async () => {
    if (!activeSuiteId || anyExecuting) return;
    try {
      await executeBoundedSuite(activeSuiteId, Number(suiteBudget));
    } catch {
      // error handled inside hook
    }
  };

  const handleInspectEvidence = async (runId) => {
    await fetchEvidence(runId);
    setShowEvidenceModal(true);
  };

  return (
    <div className="space-y-6">
      {/* 1. Runner Capability & Honesty Disclosure Banner */}
      <div className="p-4 rounded-xl border border-amber-200 dark:border-amber-900/60 bg-amber-50/70 dark:bg-amber-950/30 text-amber-900 dark:text-amber-200 shadow-2xs space-y-2">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
            <span className="text-xs font-bold uppercase tracking-wide">
              Execution Runner Disclosure: {runnerCapabilities.name}
            </span>
          </div>
          <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-amber-100 dark:bg-amber-900/60 text-amber-800 dark:text-amber-300 self-start sm:self-auto">
            Mode: Synthetic Demonstrations (is_live: false)
          </span>
        </div>
        <p className="text-[11px] leading-relaxed text-amber-800 dark:text-amber-300">
          {runnerCapabilities.disclosure} Execution results reflect scripted synthetic evaluations
          and trace playback against the Extended Finite State Machine. A live LLM agent runner
          adapter is not currently configured.
        </p>
      </div>

      {/* Global Error Banner */}
      {executionError && (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-xs text-rose-800 dark:text-rose-200 flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{executionError}</span>
          </div>
          <button
            type="button"
            onClick={clearExecutionError}
            className="text-xs font-semibold text-rose-700 dark:text-rose-300 hover:underline shrink-0"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* 2. Readiness Evaluation Grid */}
      <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            Pre-Execution Readiness Gating
          </h2>
          <span className="text-[10px] text-slate-500">
            A green Projects connection badge alone does not establish test readiness
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          {/* Check 1: Active Authorized Project */}
          <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-700 dark:text-slate-300">1. Project</span>
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
            </div>
            <div className="text-[11px] text-slate-500 mt-1 truncate">
              {projectId || 'No project'}
            </div>
          </div>

          {/* Check 2: Approved Pinned Model */}
          <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-700 dark:text-slate-300">2. Pinned Model</span>
              {hasApprovedModel ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
              ) : (
                <AlertCircle className="w-3.5 h-3.5 text-amber-500" />
              )}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              {hasApprovedModel ? 'Approved & Validated' : 'No approved version'}
            </div>
          </div>

          {/* Check 3: Ready Test Suite / Case */}
          <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-700 dark:text-slate-300">3. Test Target</span>
              {isCaseReady || isSuiteReady ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
              ) : (
                <AlertCircle className="w-3.5 h-3.5 text-amber-500" />
              )}
            </div>
            <div className="text-[11px] text-slate-500 mt-1 truncate">
              {currentCase ? (isCaseReady ? 'Case Ready' : 'Case Not Ready') : (isSuiteReady ? 'Suite Ready' : 'Select target')}
            </div>
          </div>

          {/* Check 4: Observation & Fixture Capability */}
          <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-slate-700 dark:text-slate-300">4. Runner / Observer</span>
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              Synthetic Observer Ready
            </div>
          </div>
        </div>
      </div>

      {/* 3. Execution Action Controls */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Card 1: Single Case Execution */}
        <div className="p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                <Play className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                Single Test Case Run
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300">
                Budget: 1
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
              Executes the selected test case through fixture reset, synthetic demonstration
              runner, independent state observer, and conformance evaluation.
            </p>

            {/* Target Selectors */}
            <div className="space-y-2 text-xs">
              <div>
                <label className="text-[10px] font-semibold text-slate-400 uppercase">
                  Target Suite:
                </label>
                <select
                  value={activeSuiteId}
                  onChange={(e) => {
                    setActiveSuiteId(e.target.value);
                    setActiveTestId('');
                  }}
                  className="w-full mt-1 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-xs font-mono"
                >
                  <option value="">-- Select Suite --</option>
                  {suites.map((s) => (
                    <option key={s.suite_id} value={s.suite_id}>
                      {s.suite_id} ({s.total_cases} cases)
                    </option>
                  ))}
                </select>
              </div>

              {activeSuiteId && (
                <div>
                  <label className="text-[10px] font-semibold text-slate-400 uppercase">
                    Target Case:
                  </label>
                  <select
                    value={activeTestId}
                    onChange={(e) => setActiveTestId(e.target.value)}
                    className="w-full mt-1 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-xs font-mono"
                  >
                    <option value="">-- Select Test Case --</option>
                    {currentSuiteCases.map((c) => (
                      <option key={c.test_id} value={c.test_id}>
                        {c.test_id} [{c.category}]
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          </div>

          <button
            type="button"
            disabled={!activeSuiteId || !activeTestId || anyExecuting}
            onClick={handleRunSingleCase}
            className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-semibold shadow-xs transition-colors flex items-center justify-center gap-2"
            title="Execute single case with duplicate submission prevention"
          >
            {isExecutingCase ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Synchronous Run in Progress...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5" />
                <span>Run Test Case (Synthetic)</span>
              </>
            )}
          </button>
        </div>

        {/* Card 2: Bounded Suite Execution */}
        <div className="p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                Bounded Suite Run
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300">
                Budget: {suiteBudget}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
              Executes a bounded batch of test cases up to your configured limit. Produces an
              aggregate suite pass/fail report and observed coverage.
            </p>

            <div className="space-y-2 text-xs">
              <div>
                <label className="text-[10px] font-semibold text-slate-400 uppercase">
                  Suite:
                </label>
                <select
                  value={activeSuiteId}
                  onChange={(e) => setActiveSuiteId(e.target.value)}
                  className="w-full mt-1 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-xs font-mono"
                >
                  <option value="">-- Select Suite --</option>
                  {suites.map((s) => (
                    <option key={s.suite_id} value={s.suite_id}>
                      {s.suite_id} ({s.total_cases} cases)
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-[10px] font-semibold text-slate-400 uppercase">
                  Max Case Budget:
                </label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={suiteBudget}
                  onChange={(e) => setSuiteBudget(e.target.value)}
                  className="w-full mt-1 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-xs font-mono"
                />
              </div>
            </div>
          </div>

          <button
            type="button"
            disabled={!activeSuiteId || anyExecuting}
            onClick={handleRunBoundedSuite}
            className="w-full py-2.5 rounded-xl bg-slate-800 dark:bg-slate-800 hover:bg-slate-700 text-white disabled:opacity-50 disabled:cursor-not-allowed text-xs font-semibold shadow-xs transition-colors flex items-center justify-center gap-2"
            title="Execute bounded batch with duplicate submission prevention"
          >
            {isExecutingSuite ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Running Bounded Suite...</span>
              </>
            ) : (
              <>
                <Layers className="w-3.5 h-3.5" />
                <span>Run Bounded Suite</span>
              </>
            )}
          </button>
        </div>

        {/* Card 3: Offline Flaw Demonstrations */}
        <div className="p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                <FlaskConical className="w-4 h-4 text-amber-600 dark:text-amber-400" />
                Synthetic Demonstration
              </span>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-100 dark:bg-amber-900/60 text-amber-800 dark:text-amber-300">
                12 Scenarios
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
              Execute controlled offline demonstrations of known workflow flaws (skipped,
              reordered, repeated actions, wrong entity, missing effects, or truncated traces).
            </p>

            <div className="p-3 rounded-lg bg-amber-50/50 dark:bg-amber-950/20 border border-amber-100 dark:border-amber-900/40 text-[11px] text-amber-800 dark:text-amber-300">
              Demonstrates exact violation reporting, first divergence detection, and replay
              reproduction.
            </div>
          </div>

          <button
            type="button"
            disabled={anyExecuting}
            onClick={onOpenDemoModal}
            className="w-full py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-xs font-semibold shadow-xs transition-colors flex items-center justify-center gap-2"
          >
            <FlaskConical className="w-3.5 h-3.5" />
            <span>Open Demonstration Launcher</span>
          </button>
        </div>
      </div>

      {/* 4. Latest Evaluation Verdict & Details */}
      {latestEvaluation && (
        <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200 dark:border-slate-800">
            <div className="flex items-center gap-3">
              <div
                className={`p-2 rounded-xl border ${
                  verdictStyle ? verdictStyle.bg : 'bg-slate-100'
                }`}
              >
                {verdictStyle && <verdictStyle.icon className="w-5 h-5" />}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                    Execution Verdict:{' '}
                    <span className="font-mono">
                      {verdictStyle ? verdictStyle.badgeText : latestEvaluation.verdict}
                    </span>
                  </h3>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                    Run: {latestEvaluation.run_id}
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                  Test: <span className="font-mono">{latestEvaluation.test_id}</span> • Evaluator:{' '}
                  {latestEvaluation.evaluator_version} • Duration:{' '}
                  {latestEvaluation.evaluator_timing_ms || 0}ms
                </p>
              </div>
            </div>

            {/* Verdict-level actions: Re-evaluate & Verify Reproduction */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={isReEvaluating}
                onClick={() => reEvaluate(latestEvaluation.evaluation_id)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-medium transition-colors"
                title="Reproduce evaluation from retained original evidence"
              >
                <RotateCw className={`w-3.5 h-3.5 ${isReEvaluating ? 'animate-spin' : ''}`} />
                <span>Re-Evaluate</span>
              </button>

              <button
                type="button"
                disabled={isReEvaluating}
                onClick={() => verifyEvaluationReproduction(latestEvaluation.evaluation_id)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-indigo-200 dark:border-indigo-800 bg-indigo-50/50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 text-xs font-medium hover:bg-indigo-100 transition-colors"
                title="Verify replay reproduction semantics against raw retained evidence"
              >
                <CheckCheck className="w-3.5 h-3.5" />
                <span>Verify Reproduction</span>
              </button>

              <button
                type="button"
                onClick={() => handleInspectEvidence(latestEvaluation.run_id)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs font-medium transition-colors"
                title="Inspect retained evidence digest and execution provenance"
              >
                <FileCode className="w-3.5 h-3.5" />
                <span>Evidence Digest</span>
              </button>
            </div>
          </div>

          {/* Verdict Reason */}
          {latestEvaluation.reasons?.length > 0 && (
            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 text-xs space-y-1">
              <span className="font-semibold text-slate-600 dark:text-slate-400 uppercase text-[10px]">
                Verdict Rationale:
              </span>
              <ul className="list-disc pl-5 space-y-0.5 text-slate-800 dark:text-slate-200">
                {latestEvaluation.reasons.map((r, idx) => (
                  <li key={idx}>{r}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Reproduction Verification Result Banner */}
          {reproductionResult && (
            <div className="p-3.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-900 text-xs text-indigo-900 dark:text-indigo-200 flex items-start gap-2.5">
              <CheckCheck className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-bold">Independent Replay Reproduction Verified: </span>
                {reproductionResult.is_reproducible
                  ? 'Replay evaluation produced identical semantic outcome and verdict.'
                  : 'Replay divergence detected during evaluation reproduction.'}
                <div className="text-[11px] font-mono mt-1 text-indigo-700 dark:text-indigo-300">
                  Digest verified: {reproductionResult.evidence_digest?.substring(0, 24)}...
                </div>
              </div>
            </div>
          )}

          {/* First Divergence Detail */}
          {latestEvaluation.first_divergence && (
            <div className="p-4 rounded-xl border border-rose-200 dark:border-rose-900/60 bg-rose-50/50 dark:bg-rose-950/30 text-xs space-y-2">
              <div className="flex items-center gap-2 text-rose-800 dark:text-rose-200 font-bold uppercase text-[11px]">
                <XCircle className="w-4 h-4 text-rose-600 shrink-0" />
                <span>First Observed Divergence</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-[11px]">
                <div>
                  <span className="text-slate-500 uppercase font-semibold">Step Index:</span>
                  <div className="font-mono font-bold text-rose-900 dark:text-rose-200">
                    Step {latestEvaluation.first_divergence.step_index}
                  </div>
                </div>
                <div>
                  <span className="text-slate-500 uppercase font-semibold">Expected State:</span>
                  <div className="font-mono text-emerald-700 dark:text-emerald-400">
                    {latestEvaluation.first_divergence.expected_state || 'N/A'}
                  </div>
                </div>
                <div>
                  <span className="text-slate-500 uppercase font-semibold">Observed State:</span>
                  <div className="font-mono text-rose-700 dark:text-rose-300">
                    {latestEvaluation.first_divergence.observed_state || 'N/A'}
                  </div>
                </div>
              </div>
              <p className="text-[11px] text-slate-700 dark:text-slate-300 italic pt-1 border-t border-rose-100 dark:border-rose-900/40">
                "{latestEvaluation.first_divergence.divergence_description || 'State divergence from reference path'}"
              </p>
            </div>
          )}

          {/* Violations List */}
          {latestEvaluation.violations?.length > 0 && (
            <div className="space-y-2">
              <span className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                Detected Violations ({latestEvaluation.violations.length})
              </span>
              <div className="space-y-1.5">
                {latestEvaluation.violations.map((v, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/60 text-xs flex items-start justify-between gap-2"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-rose-600 dark:text-rose-400">
                          {v.violation_type}
                        </span>
                        <span className="text-slate-400">•</span>
                        <span className="text-slate-600 dark:text-slate-400 font-mono text-[11px]">
                          State: {v.state || 'N/A'}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-700 dark:text-slate-300 mt-1">
                        {v.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 5. Evaluations Run History List */}
      <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <h3 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
              Evaluation History ({evaluations?.length || 0})
            </h3>
          </div>

          <div className="flex items-center gap-2">
            <select
              value={verdictFilter}
              onChange={(e) => setVerdictFilter(e.target.value)}
              className="px-2.5 py-1 text-xs rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-slate-700 dark:text-slate-300"
            >
              <option value="">All Verdicts</option>
              <option value="PASS">PASS</option>
              <option value="EXPECTED_REJECTION_PASS">EXPECTED REJECTION PASS</option>
              <option value="FAIL">FAIL</option>
              <option value="INCONCLUSIVE">INCONCLUSIVE</option>
            </select>

            <button
              type="button"
              onClick={() => refreshEvaluations()}
              className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
              title="Refresh evaluations"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoadingEvaluations ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {evaluations?.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-lg">
            No evaluations recorded yet for this project. Execute a test case or synthetic demonstration above.
          </div>
        ) : (
          <div className="space-y-1.5 max-h-64 overflow-y-auto">
            {evaluations
              .filter((ev) => !verdictFilter || String(ev.verdict).toUpperCase() === verdictFilter)
              .map((ev) => {
                const vStyle = VERDICT_STYLES[String(ev.verdict).toUpperCase()] || VERDICT_STYLES.PASS;
                return (
                  <div
                    key={ev.evaluation_id}
                    onClick={() => setLatestEvaluation(ev)}
                    className="flex items-center justify-between p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:border-indigo-400 bg-white dark:bg-slate-900 cursor-pointer transition-colors text-xs"
                  >
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${vStyle.bg}`}>
                        {vStyle.badgeText}
                      </span>
                      <div>
                        <span className="font-mono font-semibold text-slate-900 dark:text-white">
                          {ev.test_id}
                        </span>
                        <span className="text-[11px] text-slate-400 ml-2 font-mono">
                          ({ev.run_id})
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 text-slate-400 text-[11px]">
                      <span>{ev.evaluated_at ? new Date(ev.evaluated_at).toLocaleTimeString() : ''}</span>
                      <ChevronRight className="w-3.5 h-3.5" />
                    </div>
                  </div>
                );
              })}
          </div>
        )}
      </div>

      {/* Retained Evidence Modal */}
      {showEvidenceModal && retainedEvidence && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="relative w-full max-w-2xl flex flex-col rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <FileCode className="w-5 h-5 text-indigo-600" />
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                  Retained Execution Evidence ({retainedEvidence.run_id})
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowEvidenceModal(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              >
                Close
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <span className="font-semibold text-slate-400 uppercase text-[10px]">
                  Evidence SHA-256 Digest:
                </span>
                <div className="font-mono text-indigo-600 dark:text-indigo-400 mt-0.5 break-all">
                  {retainedEvidence.evidence_digest}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-slate-400 text-[10px] uppercase font-semibold">Runner:</span>
                  <div className="font-mono text-slate-800 dark:text-slate-200">{retainedEvidence.runner_id}</div>
                </div>
                <div>
                  <span className="text-slate-400 text-[10px] uppercase font-semibold">Mode:</span>
                  <div className="font-mono text-slate-800 dark:text-slate-200">{retainedEvidence.execution_mode}</div>
                </div>
              </div>

              <div>
                <span className="font-semibold text-slate-400 uppercase text-[10px]">
                  Execution Provenance Metadata:
                </span>
                <pre className="p-3 rounded-xl bg-slate-900 text-slate-200 font-mono text-[11px] overflow-x-auto max-h-48 mt-1">
                  {JSON.stringify(retainedEvidence.execution_provenance || {}, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
