import React, { useState } from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  HelpCircle,
  MinusCircle,
  Info,
  Layers,
  Workflow,
  Terminal,
} from 'lucide-react';
import { C3Badge } from './C3Badge';

export const C3ExplanationEvidenceView = ({ evaluationRecord, onClose }) => {
  const [showRawJson, setShowRawJson] = useState(false);
  const [activeTab, setActiveTab] = useState('rules'); // 'rules' | 'c2facts' | 'budgets' | 'limitations'

  if (!evaluationRecord) {
    return (
      <div className="p-6 text-center text-slate-500">
        No evaluation record selected.
      </div>
    );
  }

  const ev = evaluationRecord.evaluation || evaluationRecord;
  const verdict = evaluationRecord.recovery_verdict || ev.recovery_verdict;
  const evaluationStatus = evaluationRecord.evaluation_status || ev.evaluation_status;
  const firstViolation = evaluationRecord.first_violated_rule || ev.first_violated_rule;
  const ruleResults = ev.rule_results || [];
  const nonEvalReasons = ev.non_evaluation_reasons || [];
  const cleanLimitations = ev.clean_control_limitations || [];
  const demoLimitations = ev.demonstration_limitations || [];
  const actor = evaluationRecord.actor_attribution || ev.actor_attribution || 'UNKNOWN';

  // Extract C2 assertion facts if present in snapshot or evaluation
  const c2Facts = evaluationRecord.c2_facts_provenance_snapshot || ev.c2_facts || [];

  return (
    <div className="space-y-6 text-slate-900 dark:text-slate-100">
      {/* Header Banner */}
      <div className="p-5 rounded-2xl bg-slate-900 text-white border border-slate-800 space-y-3">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="inline-flex items-center gap-2 px-2.5 py-0.5 rounded-md bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-[11px] font-semibold uppercase tracking-wider mb-2">
              <Workflow className="w-3.5 h-3.5" />
              Recovery Evaluation & Causal Findings
            </div>
            <h2 className="text-xl font-bold tracking-tight">
              Evaluation Record: <span className="font-mono text-indigo-300">{evaluationRecord.evaluation_id || ev.pair_id}</span>
            </h2>
            <div className="flex items-center gap-3 text-xs text-slate-400 mt-1 flex-wrap font-mono">
              <span>Case: {evaluationRecord.case_id || ev.case_id}</span>
              <span>•</span>
              <span>Pair: {evaluationRecord.pair_id || ev.pair_id}</span>
              <span>•</span>
              <span>Actor: {actor}</span>
              <span>•</span>
              <span>Engine v{ev.evaluator_version || '1.1.0'} (Ruleset v{ev.rule_set_version || '1.1.0'})</span>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {verdict ? (
              <C3Badge status={verdict} className="text-sm px-3 py-1 font-bold" />
            ) : (
              <C3Badge status={evaluationStatus || 'NOT_EVALUATED'} className="text-sm px-3 py-1 font-bold" />
            )}
          </div>
        </div>

        {/* First Observable Violation Highlight Banner */}
        {firstViolation ? (
          <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-800/80 text-rose-200 text-xs flex items-start gap-2.5">
            <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold text-rose-300">First Observable Rule Violation:</span>{' '}
              <code className="font-mono bg-rose-900/60 px-1.5 py-0.5 rounded text-rose-200 font-bold">
                {firstViolation}
              </code>
              <p className="mt-1 text-rose-300/90 leading-relaxed">
                The evaluation engine chronologically ordered rule violations by runtime event timestamps. This rule was the earliest causal violation detected in the fault trial.
              </p>
            </div>
          </div>
        ) : verdict === 'FAIL' ? (
          <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-800/60 text-rose-200 text-xs flex items-start gap-2.5">
            <Info className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">Final-Outcome Recovery Failure:</span>
              <p className="mt-0.5 text-rose-300/90 leading-relaxed">
                No early intermediate rule was violated during tool calls, but the terminal task condition or final state check failed.
              </p>
            </div>
          </div>
        ) : verdict === 'PASS_COMPLETED' ? (
          <div className="p-3 rounded-xl bg-emerald-950/40 border border-emerald-800/60 text-emerald-200 text-xs flex items-start gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">Verified Recovery Success:</span>
              <p className="mt-0.5 text-emerald-300/90 leading-relaxed">
                All applicable recovery rules were satisfied. Task completed cleanly within attempt budgets with verified state assertions.
              </p>
            </div>
          </div>
        ) : verdict === 'PASS_GRACEFUL' ? (
          <div className="p-3 rounded-xl bg-sky-950/40 border border-sky-800/60 text-sky-200 text-xs flex items-start gap-2.5">
            <ShieldCheck className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">Permitted Graceful Halt:</span>
              <p className="mt-0.5 text-sky-300/90 leading-relaxed">
                The agent stopped safely without exceeding attempt/retry budgets under an unrecoverable fault and notified the user honestly under the recovery contract.
              </p>
            </div>
          </div>
        ) : verdict === 'INCONCLUSIVE' ? (
          <div className="p-3 rounded-xl bg-amber-950/40 border border-amber-800/60 text-amber-200 text-xs flex items-start gap-2.5">
            <HelpCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">Inconclusive Recovery Outcome:</span>
              <p className="mt-0.5 text-amber-300/90 leading-relaxed">
                Evaluation uncertainty due to missing observation facts or uncertain post-execution fixture settling. The verdict cannot be certified as Pass or Fail.
              </p>
            </div>
          </div>
        ) : null}

        {/* Non-evaluation reasons if trial was ineligible */}
        {nonEvalReasons.length > 0 && (
          <div className="p-3 rounded-xl bg-amber-950/60 border border-amber-800 text-amber-200 text-xs space-y-1.5">
            <div className="font-bold flex items-center gap-1.5 text-amber-300">
              <Info className="w-4 h-4 text-amber-400" />
              <span>Trial Ineligible for Recovery Scoring</span>
            </div>
            <ul className="list-disc list-inside space-y-1 pl-1 text-amber-200/90">
              {nonEvalReasons.map((reason, idx) => (
                <li key={idx}>{reason}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
        <button
          type="button"
          onClick={() => setActiveTab('rules')}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors ${
            activeTab === 'rules'
              ? 'bg-indigo-600 text-white'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Recovery Rules Breakdown ({ruleResults.length})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('c2facts')}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors ${
            activeTab === 'c2facts'
              ? 'bg-indigo-600 text-white'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <Workflow className="w-3.5 h-3.5" />
          <span>C2 Assertion Facts ({c2Facts.length})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('limitations')}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors ${
            activeTab === 'limitations'
              ? 'bg-indigo-600 text-white'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <Info className="w-3.5 h-3.5" />
          <span>Limitations & Governance</span>
        </button>

        <button
          type="button"
          onClick={() => setShowRawJson(!showRawJson)}
          className="ml-auto px-2.5 py-1 text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 flex items-center gap-1"
        >
          <Terminal className="w-3.5 h-3.5" />
          <span>{showRawJson ? 'Hide Raw JSON' : 'Raw JSON'}</span>
        </button>
      </div>

      {/* Tab 1: Rules Breakdown Table */}
      {activeTab === 'rules' && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 font-semibold text-slate-500 uppercase tracking-wider text-[10px]">
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Rule Identifier & Name</th>
                    <th className="py-2.5 px-3">Reason Code</th>
                    <th className="py-2.5 px-3">Evaluation Message</th>
                    <th className="py-2.5 px-3">Supporting Facts / Events</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {ruleResults.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-6 text-center text-slate-400 italic">
                        No rules were evaluated for this trial (ineligible or unscored).
                      </td>
                    </tr>
                  ) : (
                    ruleResults.map((r, idx) => {
                      const isViolated = r.status === 'VIOLATED';
                      const isFirst = r.rule_id === firstViolation;
                      return (
                        <tr
                          key={r.rule_id || idx}
                          className={`transition-colors ${
                            isFirst
                              ? 'bg-rose-50/70 dark:bg-rose-950/30'
                              : isViolated
                              ? 'bg-rose-50/30 dark:bg-rose-950/15'
                              : 'hover:bg-slate-50/50 dark:hover:bg-slate-800/30'
                          }`}
                        >
                          <td className="py-3 px-3 shrink-0">
                            <div className="flex items-center gap-1.5">
                              {r.status === 'SATISFIED' && (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800">
                                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                                  SATISFIED
                                </span>
                              )}
                              {r.status === 'VIOLATED' && (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800">
                                  <XCircle className="w-3 h-3 text-rose-600" />
                                  VIOLATED
                                </span>
                              )}
                              {r.status === 'UNKNOWN' && (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800">
                                  <HelpCircle className="w-3 h-3 text-amber-600" />
                                  UNKNOWN
                                </span>
                              )}
                              {r.status === 'NOT_APPLICABLE' && (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-600 border border-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700">
                                  <MinusCircle className="w-3 h-3 text-slate-400" />
                                  NOT APPLICABLE
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="py-3 px-3">
                            <div className="font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                              <span>{r.rule_name || r.rule_id}</span>
                              {isFirst && (
                                <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-rose-600 text-white uppercase">
                                  1st Violation
                                </span>
                              )}
                            </div>
                            <code className="text-[10px] text-slate-400 font-mono block">
                              {r.rule_id}
                            </code>
                          </td>
                          <td className="py-3 px-3 font-mono text-[11px] text-slate-500">
                            {r.reason_code ? (
                              <span className="bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">
                                {r.reason_code}
                              </span>
                            ) : (
                              <span className="text-slate-400 italic">—</span>
                            )}
                          </td>
                          <td className="py-3 px-3 max-w-md">
                            <p className="text-slate-700 dark:text-slate-300 leading-relaxed text-xs">
                              {r.message}
                            </p>
                          </td>
                          <td className="py-3 px-3 font-mono text-[10px] text-slate-500">
                            {r.supporting_fact_ids?.length > 0 && (
                              <div className="space-y-0.5">
                                <span className="text-[9px] uppercase font-bold text-indigo-500 block">Facts:</span>
                                {r.supporting_fact_ids.map((id) => (
                                  <span key={id} className="block bg-indigo-50/60 dark:bg-indigo-950/40 px-1 rounded text-indigo-700 dark:text-indigo-300 truncate max-w-[140px]">
                                    {id}
                                  </span>
                                ))}
                              </div>
                            )}
                            {r.supporting_event_ids?.length > 0 && (
                              <div className="mt-1 space-y-0.5">
                                <span className="text-[9px] uppercase font-bold text-slate-400 block">Events:</span>
                                {r.supporting_event_ids.map((id) => (
                                  <span key={id} className="block bg-slate-100 dark:bg-slate-800 px-1 rounded text-slate-600 dark:text-slate-400 truncate max-w-[140px]">
                                    {id}
                                  </span>
                                ))}
                              </div>
                            )}
                            {(!r.supporting_fact_ids || r.supporting_fact_ids.length === 0) &&
                              (!r.supporting_event_ids || r.supporting_event_ids.length === 0) && (
                                <span className="text-slate-400 italic">—</span>
                              )}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Trusted C2 Assertion Facts Table */}
      {activeTab === 'c2facts' && (
        <div className="space-y-4">
          <div className="p-3 rounded-xl bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-200 dark:border-indigo-900/50 text-xs text-indigo-900 dark:text-indigo-300 leading-relaxed flex items-start gap-2.5">
            <Workflow className="w-4 h-4 text-indigo-500 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">Component 2 Workflow Facts Integration:</span>
              <p className="mt-0.5 text-indigo-800/80 dark:text-indigo-300/80">
                Component 3 strictly consumes discrete assertion facts from Component 2 without redefining workflow rules or re-evaluating domain state machines. Assertion values are displayed exactly as received (<code className="font-mono">TRUE</code>, <code className="font-mono">FALSE</code>, or <code className="font-mono">UNKNOWN</code>).
              </p>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 font-semibold text-slate-500 uppercase tracking-wider text-[10px]">
                    <th className="py-2.5 px-3">Assertion ID</th>
                    <th className="py-2.5 px-3">Value</th>
                    <th className="py-2.5 px-3">Provenance</th>
                    <th className="py-2.5 px-3">Entity & Scope</th>
                    <th className="py-2.5 px-3">Supporting Evidence</th>
                    <th className="py-2.5 px-3">Context Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {c2Facts.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-6 text-center text-slate-400 italic">
                        No Component 2 assertion facts recorded for this trial.
                      </td>
                    </tr>
                  ) : (
                    c2Facts.map((fact, idx) => (
                      <tr key={fact.assertion_id || idx} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                        <td className="py-3 px-3 font-semibold text-slate-900 dark:text-white font-mono text-[11px]">
                          {fact.assertion_id}
                          <span className="text-[10px] text-slate-400 font-normal block font-sans">
                            v{fact.assertion_version || '1.0.0'}
                          </span>
                        </td>
                        <td className="py-3 px-3">
                          <C3Badge status={fact.value} />
                        </td>
                        <td className="py-3 px-3 font-mono text-[10px] text-slate-500">
                          <span className="bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">
                            {fact.provenance || 'C2_FIXTURE'}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-slate-600 dark:text-slate-300 text-[11px]">
                          <div>{fact.entity_id || 'N/A'}</div>
                          {fact.time_scope && (
                            <span className="text-[10px] text-slate-400">
                              scope: {fact.time_scope}
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-3 font-mono text-[10px] text-slate-500">
                          {fact.supporting_evidence_refs?.length > 0 ? (
                            <div className="space-y-0.5">
                              {fact.supporting_evidence_refs.map((ref) => (
                                <span key={ref} className="block truncate max-w-[120px]">
                                  {ref}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-slate-400 italic">—</span>
                          )}
                        </td>
                        <td className="py-3 px-3 font-mono text-[10px] text-slate-500 max-w-[150px] truncate">
                          {fact.details && Object.keys(fact.details).length > 0 ? (
                            JSON.stringify(fact.details)
                          ) : (
                            <span className="text-slate-400 italic">—</span>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Limitations & Governance */}
      {activeTab === 'limitations' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-2">
              <span className="font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                <Info className="w-4 h-4 text-indigo-500" />
                Demonstration & Target Limitations
              </span>
              {demoLimitations.length > 0 ? (
                <ul className="list-disc list-inside space-y-1 text-slate-600 dark:text-slate-400 pl-1">
                  {demoLimitations.map((lim, idx) => (
                    <li key={idx}>{lim}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-slate-500 italic">No demonstration limitations reported.</p>
              )}
            </div>

            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-2">
              <span className="font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                <Info className="w-4 h-4 text-teal-500" />
                Clean Control Baseline Comparison
              </span>
              {cleanLimitations.length > 0 ? (
                <ul className="list-disc list-inside space-y-1 text-slate-600 dark:text-slate-400 pl-1">
                  {cleanLimitations.map((lim, idx) => (
                    <li key={idx}>{lim}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-slate-500 italic">Clean baseline control qualified normally without limitations.</p>
              )}
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-400 space-y-1.5 leading-relaxed">
            <span className="font-bold text-slate-800 dark:text-slate-200 block">
              Governance & Evaluator Contract Integrity
            </span>
            <p>
              This component strictly evaluates existing recovery behavior from retained trial evidence and Component 2 assertion facts. It does not perform agent self-repair, insert automatic retry middleware, modify agent prompts, or edit source code.
            </p>
          </div>
        </div>
      )}

      {/* Raw JSON Viewer */}
      {showRawJson && (
        <div className="p-4 rounded-xl bg-slate-950 text-slate-200 font-mono text-[11px] overflow-x-auto border border-slate-800">
          <pre>{JSON.stringify(evaluationRecord, null, 2)}</pre>
        </div>
      )}

      {onClose && (
        <div className="flex justify-end pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 transition-colors"
          >
            Close Details
          </button>
        </div>
      )}
    </div>
  );
};
