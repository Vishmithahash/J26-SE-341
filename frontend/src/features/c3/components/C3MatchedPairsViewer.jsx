import React, { useState } from 'react';
import {
  GitCompare,
  AlertTriangle,
  ChevronRight,
  X,
  ShieldCheck,
  RefreshCw,
  Search,
  Filter,
} from 'lucide-react';
import { C3Badge } from './C3Badge';
import {
  EXPOSURE_STATUS,
  CLEAN_QUALIFICATION,
} from '../api';

const formatCleanup = (trial) => {
  if (!trial) return <span className="font-mono text-slate-400">Unavailable</span>;
  if (trial.cleanup_successful === true) {
    return <span className="font-mono font-medium text-emerald-600 dark:text-emerald-400">Cleaned & verified (true)</span>;
  }
  if (trial.cleanup_successful === false) {
    return <span className="font-mono font-medium text-rose-600 dark:text-rose-400">Cleanup failed (false)</span>;
  }
  if (trial.cleanup_status) {
    return <span className="font-mono">{trial.cleanup_status}</span>;
  }
  return <span className="font-mono text-slate-400 italic">Not assessed (null)</span>;
};

export const C3MatchedPairsViewer = ({
  pairs = [],
  totalPairs = null,
  isLoading = false,
  error = null,
  isDbUnavailable = false,
  onRefresh,
  onLoadOfflineDemo,
  verdictsByPair = {},
}) => {
  const [selectedPair, setSelectedPair] = useState(null);
  const [exposureFilter, setExposureFilter] = useState('ALL');
  const [cleanFilter, setCleanFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  // Apply filters
  const filteredPairs = pairs.filter((p) => {
    const pairExp = p.exposure_status || p.evidence?.exposure_status;
    if (exposureFilter !== 'ALL' && pairExp !== exposureFilter) return false;

    const cleanQual = p.clean_qualification || p.evidence?.clean_qualification;
    if (cleanFilter !== 'ALL' && cleanQual !== cleanFilter) return false;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const pairId = (p.pair_id || '').toLowerCase();
      const caseId = (p.case_id || '').toLowerCase();
      const runId = (p.run_id || '').toLowerCase();
      return pairId.includes(q) || caseId.includes(q) || runId.includes(q);
    }
    return true;
  });

  return (
    <div className="space-y-4">
      {/* Search and Filters Bar */}
      <div className="flex items-center justify-between gap-3 flex-wrap bg-white dark:bg-slate-900 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 text-xs">
        <div className="flex items-center gap-2 flex-1 min-w-[200px]">
          <Search className="w-3.5 h-3.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search by Pair ID, Case ID, or Run ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-transparent border-none text-xs focus:outline-hidden text-slate-900 dark:text-white placeholder:text-slate-400"
          />
          {totalPairs !== null && (
            <span className="text-[10px] text-slate-400 whitespace-nowrap">
              ({filteredPairs.length} of {totalPairs})
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-500 font-medium">Exposure:</span>
            <select
              value={exposureFilter}
              onChange={(e) => setExposureFilter(e.target.value)}
              className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1 text-xs text-slate-800 dark:text-slate-200 focus:outline-hidden"
            >
              <option value="ALL">All Exposures</option>
              <option value={EXPOSURE_STATUS.CONFIRMED}>Confirmed</option>
              <option value={EXPOSURE_STATUS.NOT_TRIGGERED}>Not Triggered</option>
              <option value={EXPOSURE_STATUS.EXPOSURE_UNKNOWN}>Unknown</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-slate-500 font-medium">Clean Control:</span>
            <select
              value={cleanFilter}
              onChange={(e) => setCleanFilter(e.target.value)}
              className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1 text-xs text-slate-800 dark:text-slate-200 focus:outline-hidden"
            >
              <option value="ALL">All Controls</option>
              <option value={CLEAN_QUALIFICATION.QUALIFIED}>Qualified</option>
              <option value={CLEAN_QUALIFICATION.DISQUALIFIED}>Disqualified (Retained)</option>
            </select>
          </div>

          {onRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              disabled={isLoading}
              className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition-colors"
              title="Refresh pairs"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          )}
        </div>
      </div>

      {/* Main Matched Pairs Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-sm">
        {isLoading ? (
          <div className="p-8 text-center space-y-3">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto text-indigo-500" />
            <p className="text-xs text-slate-500">Loading authorized matched trial pairs...</p>
          </div>
        ) : error ? (
          <div className="p-6 text-center space-y-3">
            <AlertTriangle className="w-8 h-8 mx-auto text-amber-500" />
            <div className="text-xs text-slate-600 dark:text-slate-400 max-w-md mx-auto">
              <span className="font-semibold block text-slate-900 dark:text-white">
                {isDbUnavailable ? 'Database Service Offline (HTTP 503)' : 'Failed to Load Matched Pairs'}
              </span>
              <p className="mt-1">{error}</p>
            </div>
            {onLoadOfflineDemo && (
              <button
                type="button"
                onClick={onLoadOfflineDemo}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800 text-xs font-semibold hover:bg-indigo-100"
              >
                <span>Load Offline Demonstration Evidence Fixtures</span>
              </button>
            )}
          </div>
        ) : filteredPairs.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <GitCompare className="w-10 h-10 text-slate-300 dark:text-slate-700 mx-auto" />
            <div className="text-xs text-slate-500">
              <span className="font-bold text-slate-700 dark:text-slate-300 block">
                No matched trial pairs found
              </span>
              <p className="mt-0.5">
                Run trials via the developer CLI or import evidence records using the <strong>Import Evidence</strong> button.
              </p>
            </div>
            {onLoadOfflineDemo && (
              <button
                type="button"
                onClick={onLoadOfflineDemo}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-colors shadow-xs"
              >
                <span>Load Sample Demonstration Pairs</span>
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-500 font-semibold">
                <tr>
                  <th className="py-3 px-4">Pair ID & Case ID</th>
                  <th className="py-3 px-4">Clean Baseline Control</th>
                  <th className="py-3 px-4">Fault Trial Exposure</th>
                  <th className="py-3 px-4">Comparability</th>
                  <th className="py-3 px-4">Recovery Verdict</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filteredPairs.map((pair) => {
                  const evidence = pair.evidence || pair;
                  const pairId = pair.pair_id || evidence.pair_id;
                  const caseId = pair.case_id || evidence.case_id;
                  const runId = pair.run_id || evidence.run_id;

                  const cleanQual = pair.clean_qualification || evidence.clean_qualification || 'UNKNOWN';
                  const exposureStat = pair.exposure_status || evidence.exposure_status || 'EXPOSURE_UNKNOWN';
                  const comparability = evidence.fixture_comparability || 'EQUIVALENT_LOGICAL_STATE';
                  const recoveryVerdict =
                    evidence.recovery_verdict || pair.recovery_verdict || verdictsByPair[pairId] || null;

                  return (
                    <tr
                      key={pairId}
                      className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors"
                    >
                      <td className="py-3 px-4">
                        <div className="font-mono font-bold text-slate-900 dark:text-white">
                          {pairId}
                        </div>
                        <div className="text-[11px] text-slate-400 font-mono">
                          Case: {caseId}
                        </div>
                        <div className="text-[10px] text-slate-400 font-mono">
                          Run: {runId}
                        </div>
                      </td>

                      <td className="py-3 px-4">
                        <div className="space-y-1">
                          <C3Badge
                            status={cleanQual}
                            label={cleanQual === 'QUALIFIED' ? 'Qualified Clean Control' : cleanQual === 'DISQUALIFIED' ? 'Disqualified (Retained)' : cleanQual}
                          />
                          <div className="text-[10px] text-slate-400">
                            Status: <span className="font-mono">{evidence.clean_trial?.execution_status || 'COMPLETED'}</span>
                          </div>
                        </div>
                      </td>

                      <td className="py-3 px-4">
                        <div className="space-y-1">
                          <C3Badge
                            status={exposureStat}
                            label={
                              exposureStat === 'CONFIRMED'
                                ? 'Confirmed Exposure'
                                : exposureStat === 'NOT_TRIGGERED'
                                ? 'Not Triggered (Unreached)'
                                : 'Exposure Unknown'
                            }
                          />
                          <div className="text-[10px] text-slate-400">
                            Fault: <span className="font-mono">{evidence.fault_trial?.episodes?.[0]?.fault_family || 'Unspecified'}</span>
                          </div>
                        </div>
                      </td>

                      <td className="py-3 px-4">
                        <span className="font-mono text-[11px] text-slate-600 dark:text-slate-300">
                          {comparability === 'EQUIVALENT_LOGICAL_STATE'
                            ? 'Equivalent State'
                            : comparability}
                        </span>
                      </td>

                      <td className="py-3 px-4">
                        {recoveryVerdict ? (
                          <C3Badge status={recoveryVerdict} />
                        ) : (
                          <span className="text-[11px] text-slate-400 italic">
                            No evaluation attached
                          </span>
                        )}
                      </td>

                      <td className="py-3 px-4 text-right">
                        <button
                          type="button"
                          onClick={() => setSelectedPair(evidence)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-800 text-xs font-semibold hover:bg-indigo-100 transition-colors"
                        >
                          <span>Inspect Pair</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Matched Pair Detail Modal */}
      {selectedPair && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <GitCompare className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                <div>
                  <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <span>Matched Pair Evidence Record:</span>
                    <code className="font-mono text-indigo-600 dark:text-indigo-400">
                      {selectedPair.pair_id}
                    </code>
                  </h2>
                  <p className="text-[11px] text-slate-400 font-mono">
                    Case: {selectedPair.case_id || '—'} | Run: {selectedPair.run_id || '—'} | Mode: {selectedPair.target_mode || 'Unspecified'}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedPair(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6 text-xs">
              {/* Status Summary Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-1">
                  <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                    Readiness Status
                  </span>
                  <C3Badge status={selectedPair.readiness_status || 'NOT_CHECKED'} />
                </div>

                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-1">
                  <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                    Clean Baseline Control
                  </span>
                  <C3Badge status={selectedPair.clean_qualification || 'UNASSESSED'} />
                </div>

                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-1">
                  <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                    Fault Exposure
                  </span>
                  <C3Badge status={selectedPair.exposure_status || 'EXPOSURE_UNKNOWN'} />
                </div>

                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-1">
                  <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                    Fixture Comparability
                  </span>
                  <span className="font-mono text-slate-800 dark:text-slate-200">
                    {selectedPair.fixture_comparability || 'EQUIVALENT_LOGICAL_STATE'}
                  </span>
                </div>
              </div>

              {/* Side-by-side: Clean Trial vs Fault Trial */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Clean Control Trial */}
                <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40 space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-2">
                    <span className="font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-emerald-500" />
                      Clean Baseline Trial (Control)
                    </span>
                    <C3Badge status="CLEAN" label="Injection Disabled" />
                  </div>

                  <div className="space-y-1.5 text-[11px] text-slate-600 dark:text-slate-400">
                    <div>
                      <strong className="text-slate-700 dark:text-slate-300">Trial ID:</strong>{' '}
                      <code className="font-mono">{selectedPair.clean_trial?.trial_id || '—'}</code>
                    </div>
                    <div>
                      <strong className="text-slate-700 dark:text-slate-300">Execution Status:</strong>{' '}
                      <span className="font-mono">{selectedPair.clean_trial?.execution_status || '—'}</span>
                    </div>
                    <div>
                      <strong className="text-slate-700 dark:text-slate-300">Caller Outcome:</strong>{' '}
                      <span className="font-mono">{selectedPair.clean_trial?.caller_outcome || '—'}</span>
                    </div>
                    <div>
                      <strong className="text-slate-700 dark:text-slate-300">Tool Calls Count:</strong>{' '}
                      <span className="font-mono">{selectedPair.clean_trial?.tool_calls_count ?? '—'}</span>
                    </div>
                    <div>
                      <strong className="text-slate-700 dark:text-slate-300">Fixture Namespace:</strong>{' '}
                      <span className="font-mono">{selectedPair.clean_trial?.fixture_namespace || '—'}</span>
                    </div>
                    <div>
                      <strong className="text-slate-700 dark:text-slate-300">Cleanup:</strong>{' '}
                      {formatCleanup(selectedPair.clean_trial)}
                    </div>
                  </div>

                  {/* Clean Trial Events */}
                  <div className="pt-2 border-t border-slate-200 dark:border-slate-800 space-y-1">
                    <span className="font-semibold text-slate-700 dark:text-slate-300 text-[11px]">
                      Clean Execution Events:
                    </span>
                    <div className="space-y-1 max-h-36 overflow-y-auto">
                      {(selectedPair.clean_trial?.events || []).map((ev) => (
                        <div
                          key={ev.event_id}
                          className="p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 font-mono text-[10px]"
                        >
                          <div className="flex items-center justify-between text-slate-400">
                            <span>{ev.event_type}</span>
                            <span>{ev.timestamp_iso?.slice(11, 23)}</span>
                          </div>
                          <div className="text-slate-700 dark:text-slate-300 mt-0.5">
                            Tool: {ev.tool_id} (occ: {ev.occurrence}) | {ev.forwarding_decision || 'FORWARDED'}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Fault Trial */}
                <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40 space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-2">
                    <span className="font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-rose-500" />
                      Fault Trial (Injected)
                    </span>
                    <C3Badge status="FAULT" label="Single Targeted Fault" />
                  </div>

                  <div className="space-y-1.5 text-[11px] text-slate-600 dark:text-slate-400">
                    <div>
                      <strong className="text-slate-700 dark:text-slate-300">Trial ID:</strong>{' '}
                      <code className="font-mono">{selectedPair.fault_trial?.trial_id || '—'}</code>
                    </div>
                    <div>
                      <strong className="text-slate-700 dark:text-slate-300">Execution Status:</strong>{' '}
                      <span className="font-mono">{selectedPair.fault_trial?.execution_status || '—'}</span>
                    </div>
                    <div>
                      <strong className="text-slate-700 dark:text-slate-300">Recovery Actor:</strong>{' '}
                      <span className="font-mono">{selectedPair.fault_trial?.recovery_actor || '—'}</span>
                    </div>
                    <div>
                      <strong className="text-slate-700 dark:text-slate-300">Subsequent Tool Calls:</strong>{' '}
                      <span className="font-mono">{selectedPair.fault_trial?.subsequent_calls_count ?? '—'}</span>
                    </div>
                    <div>
                      <strong className="text-slate-700 dark:text-slate-300">Caller Outcome:</strong>{' '}
                      <span className="font-mono">{selectedPair.fault_trial?.caller_outcome || '—'}</span>
                    </div>
                    <div>
                      <strong className="text-slate-700 dark:text-slate-300">Cleanup:</strong>{' '}
                      {formatCleanup(selectedPair.fault_trial)}
                    </div>
                  </div>

                  {/* Fault Trial Events */}
                  <div className="pt-2 border-t border-slate-200 dark:border-slate-800 space-y-1">
                    <span className="font-semibold text-slate-700 dark:text-slate-300 text-[11px]">
                      Fault Execution Events & Interceptions:
                    </span>
                    <div className="space-y-1 max-h-36 overflow-y-auto">
                      {(selectedPair.fault_trial?.events || []).map((ev) => (
                        <div
                          key={ev.event_id}
                          className="p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 font-mono text-[10px]"
                        >
                          <div className="flex items-center justify-between text-slate-400">
                            <span>{ev.event_type}</span>
                            <span>{ev.timestamp_iso?.slice(11, 23)}</span>
                          </div>
                          <div className="text-slate-700 dark:text-slate-300 mt-0.5">
                            Tool: {ev.tool_id} | {ev.forwarding_decision}
                          </div>
                          {ev.details?.note && (
                            <div className="text-[9px] text-slate-400 mt-0.5">
                              {ev.details.note}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Exposure Episode Evidence Receipt */}
              {selectedPair.fault_trial?.episodes?.length > 0 && (
                <div className="p-4 rounded-xl border border-indigo-200 dark:border-indigo-900/60 bg-indigo-50/30 dark:bg-indigo-950/20 space-y-2">
                  <span className="font-bold text-indigo-900 dark:text-indigo-200 flex items-center gap-1.5 text-xs">
                    <ShieldCheck className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                    Verified Fault Episode Receipt & Exposure Proof
                  </span>
                  {selectedPair.fault_trial.episodes.map((ep) => (
                    <div key={ep.episode_id} className="grid grid-cols-1 md:grid-cols-3 gap-2 text-[11px]">
                      <div>
                        <strong className="text-slate-700 dark:text-slate-300">Fault Family:</strong>{' '}
                        <code className="font-mono">{ep.fault_family}</code>
                      </div>
                      <div>
                        <strong className="text-slate-700 dark:text-slate-300">Effect Phase:</strong>{' '}
                        <code className="font-mono">{ep.effect_phase}</code>
                      </div>
                      <div>
                        <strong className="text-slate-700 dark:text-slate-300">Target Tool:</strong>{' '}
                        <code className="font-mono">{ep.target_tool_id} (occ: {ep.target_occurrence})</code>
                      </div>
                      <div>
                        <strong className="text-slate-700 dark:text-slate-300">Boundary Type:</strong>{' '}
                        <code className="font-mono">{ep.timeout_boundary_type || 'CALLER_TIMEOUT_EXCEEDED'}</code>
                      </div>
                      <div>
                        <strong className="text-slate-700 dark:text-slate-300">Elapsed Wait:</strong>{' '}
                        <code className="font-mono">{ep.elapsed_wait_ms} ms</code>
                      </div>
                      <div>
                        <strong className="text-slate-700 dark:text-slate-300">Prevented Forwarding:</strong>{' '}
                        <span className="font-mono">{ep.prevented_forwarding ? 'TRUE' : 'FALSE'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Live target evidence (NexaCart agent runs) */}
              {selectedPair.configuration_snapshot?.aut_trials && (
                <div className="p-4 rounded-xl border border-teal-200 dark:border-teal-900/60 bg-teal-50/30 dark:bg-teal-950/20 space-y-3">
                  <span className="font-bold text-teal-900 dark:text-teal-200 block text-xs">
                    Live NexaCart Agent Runs ({selectedPair.configuration_snapshot.agent?.provider || 'agent'}{' '}
                    {selectedPair.configuration_snapshot.agent?.model || ''})
                  </span>
                  {['clean', 'fault'].map((role) => {
                    const t = selectedPair.configuration_snapshot.aut_trials[role] || {};
                    return (
                      <div key={role} className="space-y-1 text-[11px]">
                        <div className="font-semibold text-slate-800 dark:text-slate-200 uppercase">
                          {role} trial
                        </div>
                        <div className="font-mono text-slate-600 dark:text-slate-400 break-all">
                          Agent run: {t.agent_run_id || '—'} | Fixture order: {t.fixture_order_number || '—'} |
                          Outcome: {t.caller_outcome || '—'}
                        </div>
                        <div className="font-mono text-slate-600 dark:text-slate-400">
                          Calls:{' '}
                          {(t.tool_calls || [])
                            .map((c) => `#${c.call_index} ${c.tool_name} ${c.success ? 'ok' : 'failed'}`)
                            .join(' → ') || '—'}
                        </div>
                        {t.outcome_classification && (
                          <div className="text-slate-500 dark:text-slate-400">
                            Classification: {t.outcome_classification.reason}
                          </div>
                        )}
                        <blockquote className="border-l-2 border-teal-400 pl-2 text-slate-700 dark:text-slate-300 whitespace-pre-wrap">
                          {t.final_answer || 'No final answer recorded.'}
                        </blockquote>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Exposure Reasons & Interpretation Limitations */}
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-2">
                <span className="font-semibold text-slate-800 dark:text-slate-200 block">
                  Authoritative Exposure Findings & Limitations:
                </span>
                <ul className="list-disc list-inside space-y-1 text-slate-600 dark:text-slate-400">
                  {(selectedPair.exposure_reasons || []).map((reason, i) => (
                    <li key={i}>{reason}</li>
                  ))}
                  {(selectedPair.interpretation_limitations || []).map((lim, i) => (
                    <li key={`lim-${i}`} className="text-amber-700 dark:text-amber-300 italic">
                      {lim}
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-end">
              <button
                type="button"
                onClick={() => setSelectedPair(null)}
                className="px-4 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-semibold hover:bg-slate-200 text-xs transition-colors"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
