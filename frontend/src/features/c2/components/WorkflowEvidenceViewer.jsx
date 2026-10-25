import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  XCircle,
  CheckCircle2,
  ArrowRight,
  Database,
  Layers,
  Fingerprint,
} from 'lucide-react';

export const WorkflowEvidenceViewer = ({
  evaluation,
  evidence,
  isLoadingEvidence,
  plannedCase = null,
}) => {
  const [expandedEvents, setExpandedEvents] = useState({});
  const [activeTab, setActiveTab] = useState('events'); // 'events' | 'divergence' | 'completeness'

  if (!evaluation) {
    return (
      <div className="p-8 text-center text-xs text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl bg-white/40 dark:bg-slate-900/20">
        Select an evaluation result to view expected and observed workflow evidence.
      </div>
    );
  }

  const toggleEvent = (index) => {
    setExpandedEvents((prev) => ({ ...prev, [index]: !prev[index] }));
  };

  const expandAllEvents = () => {
    const all = {};
    evidence?.ordered_events?.forEach((_, i) => {
      all[i] = true;
    });
    setExpandedEvents(all);
  };

  const collapseAllEvents = () => {
    setExpandedEvents({});
  };

  const firstDivergence = evaluation.first_divergence || null;
  const uncertainty = evaluation.divergence_localisation_uncertainty || null;
  const expectedStates = evaluation.expected_states || [];
  const isMutant = plannedCase?.category === 'mutated';
  const plannedPath = isMutant ? [] : plannedCase?.private_reference_paths?.[0] || [];
  const observedStates = evaluation.observed_states || [];
  const acceptedAlternatives = evaluation.accepted_alternatives || [];
  const violations = evaluation.violations || [];
  const completeness = evidence?.completeness || null;
  const orderedEvents = evidence?.ordered_events || [];
  const stateObservations = evidence?.state_observations || [];

  // Map state observations by event_index for quick lookup
  const observationsByIndex = {};
  stateObservations.forEach((obs) => {
    observationsByIndex[obs.event_index] = obs;
  });

  return (
    <div className="space-y-4">
      {/* 1. First Proven Divergence Callout OR Uncertainty Explanation */}
      {firstDivergence ? (
        <div className="p-4 rounded-xl border border-rose-200 dark:border-rose-900/60 bg-rose-50/60 dark:bg-rose-950/30 text-xs space-y-3 shadow-2xs">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <XCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span className="font-bold text-rose-900 dark:text-rose-200 uppercase tracking-wide">
                First Proven Divergence Localized
              </span>
            </div>
            <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-rose-100 dark:bg-rose-900/60 text-rose-800 dark:text-rose-300 self-start sm:self-auto">
              Event Index: {firstDivergence.event_index} (Step {firstDivergence.event_index + 1})
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 pt-1 text-[11px]">
            <div>
              <span className="text-slate-500 uppercase font-semibold">State at Divergence:</span>
              <div className="font-mono font-bold text-slate-800 dark:text-slate-200 mt-0.5">
                {firstDivergence.state_at_divergence || 'Unknown'}
              </div>
            </div>
            <div>
              <span className="text-slate-500 uppercase font-semibold">Attempted Action:</span>
              <div className="font-mono font-bold text-rose-700 dark:text-rose-300 mt-0.5">
                {firstDivergence.attempted_event}
              </div>
            </div>
            <div>
              <span className="text-slate-500 uppercase font-semibold">Violation Type:</span>
              <div className="font-mono text-purple-700 dark:text-purple-300 mt-0.5">
                {firstDivergence.violation_type || 'CONFORMANCE_FAILURE'}
              </div>
            </div>
            <div>
              <span className="text-slate-500 uppercase font-semibold">Event ID:</span>
              <div className="font-mono text-slate-600 dark:text-slate-400 mt-0.5 truncate" title={firstDivergence.event_id}>
                {firstDivergence.event_id || `event_${firstDivergence.event_index}`}
              </div>
            </div>
          </div>

          {/* Divergence Description */}
          <div className="p-2.5 rounded-lg bg-white/70 dark:bg-slate-900/60 border border-rose-100 dark:border-rose-900/40 text-[11px] text-slate-800 dark:text-slate-200">
            <span className="font-semibold text-rose-800 dark:text-rose-300">Failure Cause: </span>
            {firstDivergence.reason}
          </div>

          {/* Expected Alternatives */}
          {firstDivergence.expected_alternatives?.length > 0 && (
            <div className="text-[11px] space-y-1">
              <span className="font-semibold text-slate-600 dark:text-slate-400">
                Permitted Transition Alternatives at this State:
              </span>
              <div className="flex flex-wrap gap-1.5 pt-0.5">
                {firstDivergence.expected_alternatives.map((alt, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 font-mono text-[10px]"
                  >
                    {alt}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Supporting Evidence Excerpt */}
          {firstDivergence.evidence_excerpt && Object.keys(firstDivergence.evidence_excerpt).length > 0 && (
            <div className="space-y-1 pt-1 border-t border-rose-100 dark:border-rose-900/40">
              <span className="text-[10px] text-slate-500 uppercase font-semibold">Supporting Evidence Excerpt:</span>
              <pre className="p-2 rounded bg-slate-900 text-slate-200 font-mono text-[10px] overflow-x-auto max-h-32">
                {JSON.stringify(firstDivergence.evidence_excerpt, null, 2)}
              </pre>
            </div>
          )}
        </div>
      ) : uncertainty ? (
        <div className="p-4 rounded-xl border border-amber-200 dark:border-amber-900/60 bg-amber-50/60 dark:bg-amber-950/30 text-xs text-amber-900 dark:text-amber-200 space-y-1">
          <div className="font-semibold flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>First Divergence Localization Uncertainty</span>
          </div>
          <p className="text-[11px] leading-relaxed text-amber-800 dark:text-amber-300">
            {uncertainty}
          </p>
        </div>
      ) : evaluation.verdict === 'PASS' || evaluation.verdict === 'EXPECTED REJECTION PASS' ? (
        <div className="p-4 rounded-xl border border-emerald-200 dark:border-emerald-900/60 bg-emerald-50/60 dark:bg-emerald-950/30 text-xs text-emerald-900 dark:text-emerald-200 flex items-center gap-2.5">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>
            No divergence detected. Complete trace strictly conformed to Extended Finite State Machine model paths.
          </span>
        </div>
      ) : null}

      {/* 2. Expected vs Observed States & Alternatives */}
      <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider flex items-center gap-2">
            <Layers className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            Workflow State Trajectory & Alternative Branches
          </h3>
          <span className="text-[10px] text-slate-400 font-mono">
            Model: {evaluation.model_id} v{evaluation.model_version}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          {/* Expected States */}
          <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 space-y-2">
            <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
              Planned Reference Path:
            </span>
            <div className="flex flex-wrap items-center gap-1.5 font-mono text-[11px]">
              {isMutant ? (
                <span className="text-slate-500 italic">
                  Controlled mutant of its parent's live trace: the oracle is expected to reject it (FAIL = mutation detected).
                </span>
              ) : plannedPath.length === 0 ? (
                <span className="text-slate-400 italic">Not available</span>
              ) : (
                plannedPath.map((st, i) => (
                  <React.Fragment key={i}>
                    <span className="px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                      {st}
                    </span>
                    {i < plannedPath.length - 1 && <ArrowRight className="w-3 h-3 text-slate-400" />}
                  </React.Fragment>
                ))
              )}
            </div>
            {!isMutant && plannedPath.length > 0 && (
              <p className="text-[10px] text-slate-400">
                One planned path; the trace is aligned with every path the model permits, so another permitted route also conforms.
              </p>
            )}

            <div className="pt-2 border-t border-slate-200 dark:border-slate-800 space-y-1">
              <span className="text-[10px] font-semibold text-slate-400 uppercase">
                Expected Outcome State(s):
              </span>
              <div className="flex flex-wrap gap-1">
                {expectedStates.length === 0 ? (
                  <span className="text-slate-400 italic text-[10px]">None recorded</span>
                ) : (
                  expectedStates.map((st, i) => (
                    <span key={i} className="px-1.5 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 font-mono text-[10px]">
                      {st}
                    </span>
                  ))
                )}
              </div>
            </div>

            {/* Accepted Alternatives */}
            {acceptedAlternatives.length > 0 && (
              <div className="pt-2 border-t border-slate-200 dark:border-slate-800 space-y-1">
                <span className="text-[10px] font-semibold text-slate-400 uppercase">
                  Accepted Alternative Branch Targets:
                </span>
                <div className="flex flex-wrap gap-1">
                  {acceptedAlternatives.map((alt, i) => (
                    <span key={i} className="px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 font-mono text-[10px]">
                      {alt}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Observed States */}
          <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 space-y-2">
            <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
              Observed Runtime State Sequence:
            </span>
            <div className="flex flex-wrap items-center gap-1.5 font-mono text-[11px]">
              {observedStates.length === 0 ? (
                <span className="text-slate-400 italic">No state snapshots captured</span>
              ) : (
                observedStates.map((st, i) => {
                  const isDivergent = firstDivergence && i >= firstDivergence.event_index;
                  return (
                    <React.Fragment key={i}>
                      <span
                        className={`px-2 py-0.5 rounded border font-mono ${
                          isDivergent
                            ? 'bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border-rose-300 dark:border-rose-800'
                            : 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800'
                        }`}
                      >
                        {st}
                      </span>
                      {i < observedStates.length - 1 && <ArrowRight className="w-3 h-3 text-slate-400" />}
                    </React.Fragment>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 3. Navigation Bar for Evidence Subsections */}
      <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-2">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setActiveTab('events')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
              activeTab === 'events'
                ? 'bg-indigo-600 text-white'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            Chronological Events & State Diffs ({orderedEvents.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('violations')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
              activeTab === 'violations'
                ? 'bg-indigo-600 text-white'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            Violations ({violations.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('completeness')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
              activeTab === 'completeness'
                ? 'bg-indigo-600 text-white'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            Evidence Completeness Audit
          </button>
        </div>

        {activeTab === 'events' && orderedEvents.length > 0 && (
          <div className="flex items-center gap-2 text-xs">
            <button
              type="button"
              onClick={expandAllEvents}
              className="text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 text-[11px]"
            >
              Expand All
            </button>
            <span className="text-slate-300">|</span>
            <button
              type="button"
              onClick={collapseAllEvents}
              className="text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 text-[11px]"
            >
              Collapse All
            </button>
          </div>
        )}
      </div>

      {/* 4. Tab 1: Ordered Events & Before/After State Diffs */}
      {activeTab === 'events' && (
        <div className="space-y-2">
          {isLoadingEvidence ? (
            <div className="p-8 text-center text-xs text-slate-500">
              <div className="w-5 h-5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
              Loading retained trace evidence...
            </div>
          ) : orderedEvents.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
              No runtime events captured in evidence packet.
            </div>
          ) : (
            orderedEvents.map((evt, idx) => {
              const isExpanded = Boolean(expandedEvents[idx]);
              const obs = observationsByIndex[evt.event_index];
              const isDivergenceEvent = firstDivergence && evt.event_index === firstDivergence.event_index;

              return (
                <div
                  key={evt.event_id || idx}
                  className={`rounded-xl border transition-all ${
                    isDivergenceEvent
                      ? 'border-rose-400 dark:border-rose-800 bg-rose-50/20 dark:bg-rose-950/10'
                      : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900'
                  }`}
                >
                  {/* Event Summary Header */}
                  <div
                    onClick={() => toggleEvent(idx)}
                    className="p-3 flex items-center justify-between cursor-pointer hover:bg-slate-50/80 dark:hover:bg-slate-800/50 rounded-xl transition-colors text-xs"
                  >
                    <div className="flex items-center gap-3">
                      <span className="w-6 h-6 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-mono text-[10px] font-bold flex items-center justify-center shrink-0">
                        {evt.event_index}
                      </span>

                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-slate-900 dark:text-white">
                            {evt.tool_name}
                          </span>
                          <span className="text-[10px] font-mono text-slate-400">
                            ID: {evt.event_id}
                          </span>
                          {isDivergenceEvent && (
                            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300 uppercase">
                              First Divergence
                            </span>
                          )}
                          {evt.error && (
                            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                              Error
                            </span>
                          )}
                        </div>

                        {/* Entity Identifiers Continuity */}
                        {evt.entity_identifiers && Object.keys(evt.entity_identifiers).length > 0 && (
                          <div className="flex items-center gap-2 mt-0.5 text-[10px] text-slate-500 font-mono">
                            <Fingerprint className="w-3 h-3 text-indigo-500" />
                            {Object.entries(evt.entity_identifiers).map(([k, v]) => (
                              <span key={k}>
                                {k}={String(v)}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 text-slate-400">
                      <span className="text-[10px] font-mono">
                        {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : ''}
                      </span>
                      {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                    </div>
                  </div>

                  {/* Expanded Detail: Arguments, Results, Before/After Snapshots, State Diffs */}
                  {isExpanded && (
                    <div className="p-4 border-t border-slate-100 dark:border-slate-800 space-y-3 text-xs bg-slate-50/50 dark:bg-slate-900/40">
                      {/* Arguments and Observable Result */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                          <span className="text-[10px] font-semibold text-slate-400 uppercase">
                            Tool Arguments:
                          </span>
                          <pre className="p-2.5 rounded-lg bg-slate-900 text-slate-200 font-mono text-[11px] overflow-x-auto max-h-36 mt-1">
                            {JSON.stringify(evt.arguments || {}, null, 2)}
                          </pre>
                        </div>
                        <div>
                          <span className="text-[10px] font-semibold text-slate-400 uppercase">
                            Observable Result:
                          </span>
                          <pre className="p-2.5 rounded-lg bg-slate-900 text-emerald-400 font-mono text-[11px] overflow-x-auto max-h-36 mt-1">
                            {evt.observable_result != null
                              ? JSON.stringify(evt.observable_result, null, 2)
                              : evt.error || 'null'}
                          </pre>
                        </div>
                      </div>

                      {/* State Observations & DB Diff */}
                      {obs && (
                        <div className="pt-2 border-t border-slate-200 dark:border-slate-800 space-y-2">
                          <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 dark:text-slate-200">
                            <Database className="w-3.5 h-3.5 text-indigo-500" />
                            <span>State Snapshot & Database Delta</span>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-[11px]">
                            {/* Before State */}
                            <div>
                              <span className="text-[10px] text-slate-400 uppercase font-semibold">
                                Before State:
                              </span>
                              <pre className="p-2 rounded bg-slate-900 text-slate-300 font-mono text-[10px] overflow-x-auto max-h-32 mt-0.5">
                                {JSON.stringify(obs.before_state || {}, null, 2)}
                              </pre>
                            </div>

                            {/* State Diff (Delta) */}
                            <div>
                              <span className="text-[10px] text-amber-500 uppercase font-semibold">
                                Observed State Diff (&Delta;):
                              </span>
                              <pre className="p-2 rounded bg-slate-900 text-amber-300 font-mono text-[10px] overflow-x-auto max-h-32 mt-0.5">
                                {JSON.stringify(obs.state_diff || {}, null, 2)}
                              </pre>
                            </div>

                            {/* After State */}
                            <div>
                              <span className="text-[10px] text-slate-400 uppercase font-semibold">
                                After State:
                              </span>
                              <pre className="p-2 rounded bg-slate-900 text-slate-300 font-mono text-[10px] overflow-x-auto max-h-32 mt-0.5">
                                {JSON.stringify(obs.after_state || {}, null, 2)}
                              </pre>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}

      {/* 5. Tab 2: Detected Rule Violations */}
      {activeTab === 'violations' && (
        <div className="space-y-2">
          {violations.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
              No rule violations recorded for this evaluation run.
            </div>
          ) : (
            violations.map((v, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded-xl border border-rose-200 dark:border-rose-900/60 bg-white dark:bg-slate-900 text-xs space-y-1.5"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-rose-600 dark:text-rose-400">
                      {v.violation_type}
                    </span>
                    {v.event_index != null && (
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                        Event Index: {v.event_index}
                      </span>
                    )}
                    {v.source_state && (
                      <span className="text-[10px] font-mono text-slate-500">
                        Source State: {v.source_state}
                      </span>
                    )}
                  </div>
                  {v.rule_reference && (
                    <span className="text-[10px] text-slate-400 font-mono">
                      Rule: {v.rule_reference}
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-slate-700 dark:text-slate-300">
                  {v.message}
                </p>
                {(v.expected != null || v.observed != null) && (
                  <div className="grid grid-cols-2 gap-2 text-[10px] font-mono pt-1 border-t border-slate-100 dark:border-slate-800">
                    <div>
                      <span className="text-slate-400">Expected: </span>
                      <span className="text-emerald-600 dark:text-emerald-400">{JSON.stringify(v.expected)}</span>
                    </div>
                    <div>
                      <span className="text-slate-400">Observed: </span>
                      <span className="text-rose-600 dark:text-rose-400">{JSON.stringify(v.observed)}</span>
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* 6. Tab 3: Evidence Completeness Audit */}
      {activeTab === 'completeness' && (
        <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-4 text-xs">
          <div className="flex items-center gap-2 font-bold text-slate-900 dark:text-white uppercase tracking-wider">
            <CheckCircle2 className="w-4 h-4 text-indigo-600" />
            <span>Trace Completeness & Observation Audit</span>
          </div>

          {completeness ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40">
                <span className="text-[10px] text-slate-400 uppercase font-semibold">Events Present:</span>
                <div className="font-semibold text-slate-800 dark:text-slate-200 mt-1 flex items-center gap-1.5">
                  {completeness.has_all_events ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                  ) : (
                    <XCircle className="w-3.5 h-3.5 text-rose-500" />
                  )}
                  <span>{completeness.has_all_events ? 'Complete' : 'Missing'}</span>
                </div>
              </div>

              <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40">
                <span className="text-[10px] text-slate-400 uppercase font-semibold">State Snapshots:</span>
                <div className="font-semibold text-slate-800 dark:text-slate-200 mt-1 flex items-center gap-1.5">
                  {completeness.has_state_snapshots ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                  ) : (
                    <XCircle className="w-3.5 h-3.5 text-rose-500" />
                  )}
                  <span>{completeness.has_state_snapshots ? 'Captured' : 'Missing'}</span>
                </div>
              </div>

              <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40">
                <span className="text-[10px] text-slate-400 uppercase font-semibold">DB Diffs:</span>
                <div className="font-semibold text-slate-800 dark:text-slate-200 mt-1 flex items-center gap-1.5">
                  {completeness.has_db_diffs ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                  ) : (
                    <XCircle className="w-3.5 h-3.5 text-rose-500" />
                  )}
                  <span>{completeness.has_db_diffs ? 'Recorded' : 'Missing'}</span>
                </div>
              </div>

              <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40">
                <span className="text-[10px] text-slate-400 uppercase font-semibold">Truncated:</span>
                <div className="font-semibold text-slate-800 dark:text-slate-200 mt-1 flex items-center gap-1.5">
                  {completeness.is_truncated ? (
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                  ) : (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                  )}
                  <span>{completeness.is_truncated ? 'Yes (Truncated)' : 'No'}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-slate-400 italic">No completeness audit available in trace.</div>
          )}

          {completeness?.anomalies?.length > 0 && (
            <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/60 text-[11px] text-amber-800 dark:text-amber-200 space-y-1">
              <span className="font-semibold">Observation Anomalies Detected:</span>
              <ul className="list-disc pl-5">
                {completeness.anomalies.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
