import {
  Archive,
  RotateCw,
  FolderOpen,
  Fingerprint,
  AlertTriangle,
  ChevronRight,
  ChevronDown,
  Layers,
  Sparkles,
  Play,
  CheckCircle2,
  ShieldCheck,
} from 'lucide-react';
import { useC3ProjectSuites } from '../hooks/useC3ProjectSuites.js';
import { c3Api } from '../api.js';
import { C3Badge } from './C3Badge.jsx';
import { DEMONSTRATION_FROZEN_SUITE } from '../fixtures.js';

export const C3StoredSuitesViewer = ({ projectId }) => {
  const { suites, totalSuites, isLoading, error, isDbUnavailable, refresh } =
    useC3ProjectSuites(projectId);

  const [selectedSuite, setSelectedSuite] = useState(null);
  const [suiteCases, setSuiteCases] = useState([]);
  const [isLoadingCases, setIsLoadingCases] = useState(false);
  const [caseError, setCaseError] = useState(null);
  const [demoSuiteLoaded, setDemoSuiteLoaded] = useState(false);

  const [isRunningControlled, setIsRunningControlled] = useState(false);
  const [controlledRunResult, setControlledRunResult] = useState(null);
  const [controlledRunError, setControlledRunError] = useState(null);

  const handleRunControlledTrials = async (suiteRecord) => {
    if (!projectId || !suiteRecord) return;
    setIsRunningControlled(true);
    setControlledRunError(null);
    setControlledRunResult(null);

    try {
      const res = await c3Api.runControlledTrials({
        project_id: projectId,
        suite_id_or_digest: suiteRecord.suite_id || suiteRecord.suite_digest,
        execution_mode: 'DEMONSTRATION',
        max_suite_duration_sec: 60.0,
        per_case_timeout_sec: 10.0,
      });
      setControlledRunResult(res);
    } catch (err) {
      setControlledRunError(
        err.message || 'Failed to execute controlled trials for suite.'
      );
    } finally {
      setIsRunningControlled(false);
    }
  };

  const handleSelectSuite = async (suiteRecord) => {
    if (selectedSuite?.suite_id === suiteRecord.suite_id) {
      setSelectedSuite(null);
      setSuiteCases([]);
      return;
    }

    setSelectedSuite(suiteRecord);
    setCaseError(null);

    // If viewing the in-memory demo fixture
    if (suiteRecord.isDemoFixture) {
      setSuiteCases(suiteRecord.frozen_suite?.selected_cases || []);
      return;
    }

    // Otherwise load from backend /cases?project_id=...&suite_digest=...
    setIsLoadingCases(true);
    try {
      const res = await c3Api.listCases(projectId, {
        suiteDigest: suiteRecord.suite_digest,
      });
      setSuiteCases(res.items || []);
    } catch (err) {
      setCaseError(err.message || 'Failed to fetch candidate cases for suite.');
      setSuiteCases([]);
    } finally {
      setIsLoadingCases(false);
    }
  };

  const loadDemoFixture = () => {
    setDemoSuiteLoaded(true);
    const demoRecord = {
      suite_id: DEMONSTRATION_FROZEN_SUITE.suite_id,
      suite_digest: DEMONSTRATION_FROZEN_SUITE.suite_digest,
      domain: 'ecommerce',
      total_cases: DEMONSTRATION_FROZEN_SUITE.selected_cases.length,
      created_at_utc: '2026-10-21T12:00:00Z',
      generator_version: DEMONSTRATION_FROZEN_SUITE.generator_version,
      frozen_suite: DEMONSTRATION_FROZEN_SUITE,
      isDemoFixture: true,
    };
    setSelectedSuite(demoRecord);
    setSuiteCases(DEMONSTRATION_FROZEN_SUITE.selected_cases);
  };

  const displaySuites = demoSuiteLoaded
    ? [
        {
          suite_id: DEMONSTRATION_FROZEN_SUITE.suite_id,
          suite_digest: DEMONSTRATION_FROZEN_SUITE.suite_digest,
          domain: 'ecommerce',
          total_cases: DEMONSTRATION_FROZEN_SUITE.selected_cases.length,
          created_at_utc: '2026-10-21T12:00:00Z',
          isDemoFixture: true,
          frozen_suite: DEMONSTRATION_FROZEN_SUITE,
        },
        ...suites,
      ]
    : suites;

  return (
    <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-5">
      {/* Header and Refresh */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Archive className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <span>Stored Frozen Suites & Candidate Cases</span>
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Retrieve persisted test suites and case snapshots scoped to the active project.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={refresh}
            disabled={isLoading || !projectId}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 disabled:opacity-50 transition-colors"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* No Project Warning */}
      {!projectId && (
        <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 text-xs text-slate-500 dark:text-slate-400">
          Select an active project to view persisted test suites.
        </div>
      )}

      {/* Database Service Unavailable Banner (Honest State) */}
      {isDbUnavailable && (
        <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-xs space-y-2.5">
          <div className="flex items-start gap-2.5 text-amber-800 dark:text-amber-300">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">Database Persistence Service Unavailable (HTTP 503)</span>
              <p className="mt-0.5 leading-relaxed">
                The QA framework PostgreSQL database is temporarily offline or unmigrated in this environment. Existing stored suites cannot be queried. The system will not fabricate false zero counts.
              </p>
            </div>
          </div>

          <div className="pt-2 border-t border-amber-200 dark:border-amber-900/60 flex items-center justify-between flex-wrap gap-2">
            <span className="text-[11px] text-amber-700 dark:text-amber-400">
              Inspect verified offline test double:
            </span>
            <button
              type="button"
              onClick={loadDemoFixture}
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold bg-amber-600 hover:bg-amber-700 text-white shadow-xs transition-colors"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Load Verified Suite Fixture</span>
            </button>
          </div>
        </div>
      )}

      {/* General Error Notice */}
      {error && !isDbUnavailable && (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-700 dark:text-rose-300">
          {error}
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className="p-4 rounded-xl bg-slate-100 dark:bg-slate-800 animate-pulse h-16" />
          ))}
        </div>
      )}

      {/* Empty State (when DB is reachable but 0 suites found) */}
      {!isLoading && !isDbUnavailable && projectId && displaySuites.length === 0 && (
        <div className="p-8 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-dashed border-slate-300 dark:border-slate-700 text-center text-xs space-y-2">
          <FolderOpen className="w-8 h-8 text-slate-400 mx-auto" />
          <span className="font-semibold text-slate-700 dark:text-slate-300 block">
            No Stored Suites in Project Scope
          </span>
          <p className="text-slate-500 dark:text-slate-400 max-w-sm mx-auto">
            No frozen suites have been saved for this project yet. Use the Feasible Generation panel above to create and import a suite.
          </p>
          <div className="pt-2">
            <button
              type="button"
              onClick={loadDemoFixture}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100"
            >
              <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
              <span>Inspect Demonstration Suite Fixture</span>
            </button>
          </div>
        </div>
      )}

      {/* Suites List */}
      {!isLoading && displaySuites.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>Authoritative Suites ({totalSuites ?? displaySuites.length}):</span>
            <span>Click suite to view constituent candidate cases</span>
          </div>

          <div className="space-y-2.5">
            {displaySuites.map((s) => {
              const isSelected = selectedSuite?.suite_id === s.suite_id;

              return (
                <div
                  key={s.suite_id}
                  className={`rounded-xl border transition-all ${
                    isSelected
                      ? 'border-indigo-500 ring-2 ring-indigo-500/20 bg-slate-50/50 dark:bg-slate-800/50'
                      : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-white dark:bg-slate-900'
                  }`}
                >
                  <div
                    onClick={() => handleSelectSuite(s)}
                    className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 cursor-pointer text-xs"
                  >
                    <div className="flex items-start gap-3">
                      <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5">
                        <Layers className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-bold text-slate-900 dark:text-white font-mono text-sm">
                            {s.suite_id}
                          </span>
                          {s.isDemoFixture && (
                            <C3Badge status="STATIC_ONLY" label="Test Fixture" />
                          )}
                          <span className="text-[11px] font-semibold text-slate-500 capitalize bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded">
                            {s.domain || 'ecommerce'}
                          </span>
                        </div>
                        <div className="text-slate-500 dark:text-slate-400 mt-1 flex items-center gap-2 flex-wrap font-mono text-[11px]">
                          <span>Digest: {s.suite_digest?.substring(0, 16)}...</span>
                          <span>•</span>
                          <span>Cases: {s.total_cases ?? s.frozen_suite?.selected_cases?.length ?? 0}</span>
                          <span>•</span>
                          <span>Saved: {s.created_at_utc ? new Date(s.created_at_utc).toLocaleDateString() : 'Active'}</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 self-end sm:self-center">
                      <span className="text-indigo-600 dark:text-indigo-400 font-semibold text-[11px]">
                        {isSelected ? 'Collapse' : 'Inspect Cases'}
                      </span>
                      {isSelected ? (
                        <ChevronDown className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-slate-400" />
                      )}
                    </div>
                  </div>

                  {/* Expanded Suite Cases Drawer */}
                  {isSelected && (
                    <div className="p-4 pt-0 border-t border-slate-100 dark:border-slate-800 space-y-3 mt-1">
                      <div className="flex items-center justify-between pt-3">
                        <span className="text-xs font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                          <Fingerprint className="w-3.5 h-3.5 text-indigo-500" />
                          <span>Candidate Cases in Suite</span>
                        </span>
                        <span className="text-[11px] text-slate-400 font-mono">
                          Full SHA-256 Digest: {s.suite_digest}
                        </span>
                      </div>

                      {/* Controlled Execution Action Bar */}
                      <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                            <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                              Controlled Trial Runner
                            </span>
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 font-semibold font-mono">
                              DEMONSTRATION ADAPTER
                            </span>
                          </div>
                          <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                            Launch native sequential trials with fresh isolated fixtures, occurrence-bounded injection, and full evidence retention.
                          </p>
                        </div>

                        <button
                          type="button"
                          onClick={() => handleRunControlledTrials(s)}
                          disabled={isRunningControlled || s.isDemoFixture || !projectId}
                          className="inline-flex items-center justify-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white disabled:opacity-50 transition-colors shrink-0 shadow-xs cursor-pointer"
                        >
                          <Play className={`w-3.5 h-3.5 ${isRunningControlled ? 'animate-spin' : ''}`} />
                          <span>{isRunningControlled ? 'Running Trials...' : 'Run Controlled Trials'}</span>
                        </button>
                      </div>

                      {/* Controlled Execution Error */}
                      {controlledRunError && (
                        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 text-xs text-rose-700 dark:text-rose-300 flex items-start gap-2">
                          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                          <div>
                            <span className="font-bold">Controlled Trial Execution Failed</span>
                            <p className="mt-0.5">{controlledRunError}</p>
                          </div>
                        </div>
                      )}

                      {/* Controlled Execution Result Banner */}
                      {controlledRunResult && (
                        <div className="p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 text-xs space-y-2">
                          <div className="flex items-center justify-between flex-wrap gap-2 text-emerald-800 dark:text-emerald-200">
                            <span className="font-bold flex items-center gap-1.5">
                              <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                              <span>Controlled Trials Execution Completed ({controlledRunResult.status})</span>
                            </span>
                            <span className="font-mono text-[11px] text-emerald-700 dark:text-emerald-300">
                              Execution ID: {controlledRunResult.execution_id}
                            </span>
                          </div>
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 font-mono text-[11px]">
                            <div className="p-2 rounded bg-white/60 dark:bg-slate-900/40">
                              <span className="text-slate-500 block text-[10px]">EXECUTED CASES</span>
                              <span className="font-bold text-slate-800 dark:text-slate-200">
                                {controlledRunResult.executed_cases} / {controlledRunResult.total_cases}
                              </span>
                            </div>
                            <div className="p-2 rounded bg-white/60 dark:bg-slate-900/40">
                              <span className="text-emerald-600 dark:text-emerald-400 block text-[10px]">CONFIRMED EXPOSURE</span>
                              <span className="font-bold text-slate-800 dark:text-slate-200">
                                {controlledRunResult.confirmed_exposure_count}
                              </span>
                            </div>
                            <div className="p-2 rounded bg-white/60 dark:bg-slate-900/40">
                              <span className="text-amber-600 dark:text-amber-400 block text-[10px]">NOT TRIGGERED</span>
                              <span className="font-bold text-slate-800 dark:text-slate-200">
                                {controlledRunResult.not_triggered_exposure_count}
                              </span>
                            </div>
                            <div className="p-2 rounded bg-white/60 dark:bg-slate-900/40">
                              <span className="text-slate-500 block text-[10px]">RETAINED PAIRS</span>
                              <span className="font-bold text-slate-800 dark:text-slate-200">
                                {controlledRunResult.pair_ids?.length || 0}
                              </span>
                            </div>
                          </div>
                          <p className="text-[11px] text-emerald-700 dark:text-emerald-300 pt-1">
                            Complete evidence was persisted with verified linkage. Switch to tab <strong>5. Matched Trials & Evidence</strong> to inspect matched pairs and compute recovery results.
                          </p>
                        </div>
                      )}

                      {isLoadingCases ? (
                        <div className="py-4 text-center text-xs text-slate-400">
                          Loading candidate cases...
                        </div>
                      ) : caseError ? (
                        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 text-xs text-rose-700 dark:text-rose-300">
                          {caseError}
                        </div>
                      ) : suiteCases.length === 0 ? (
                        <div className="py-3 text-center text-xs text-slate-400">
                          No candidate case records retrieved.
                        </div>
                      ) : (
                        <div className="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-lg">
                          <table className="w-full text-left text-xs font-mono">
                            <thead>
                              <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-500">
                                <th className="p-2">Case ID</th>
                                <th className="p-2">Tool</th>
                                <th className="p-2">Fault Family</th>
                                <th className="p-2">Phase</th>
                                <th className="p-2">Fingerprint (Prefix)</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-slate-700 dark:text-slate-300">
                              {suiteCases.map((c, idx) => {
                                const caseObj = c.candidate_case || c;
                                const fp = c.case_fingerprint || s.frozen_suite?.case_fingerprints?.[caseObj.case_id] || '';
                                return (
                                  <tr key={idx} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40">
                                    <td className="p-2 font-semibold text-slate-900 dark:text-white">
                                      {caseObj.case_id}
                                    </td>
                                    <td className="p-2 text-slate-500">{caseObj.tool_id}</td>
                                    <td className="p-2 text-indigo-600 dark:text-indigo-400 font-semibold">
                                      {caseObj.fault_family}
                                    </td>
                                    <td className="p-2">
                                      <span
                                        className={`px-1 py-0.5 rounded text-[10px] ${
                                          caseObj.effect_phase === 'AFTER_COMMIT'
                                            ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300'
                                            : 'bg-teal-100 dark:bg-teal-900/40 text-teal-800 dark:text-teal-300'
                                        }`}
                                      >
                                        {caseObj.effect_phase}
                                      </span>
                                    </td>
                                    <td className="p-2 text-slate-400 text-[11px]">
                                      {fp ? fp.substring(0, 16) + '...' : 'n/a'}
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
