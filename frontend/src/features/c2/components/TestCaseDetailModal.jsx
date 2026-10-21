import React, { useState, useEffect } from 'react';
import {
  X,
  Play,
  Download,
  Shield,
  ShieldAlert,
  Bot,
  CheckCircle2,
  AlertCircle,
  Layers,
  ArrowRight,
  Lock,
  Info,
} from 'lucide-react';
import { c2Api } from '../api/c2Api';

const CATEGORY_STYLES = {
  valid: {
    bg: 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800',
    label: 'Valid Path',
  },
  alternative: {
    bg: 'bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800',
    label: 'Alternative Path',
  },
  negative: {
    bg: 'bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800',
    label: 'Negative Rejection',
  },
  mutated: {
    bg: 'bg-purple-50 dark:bg-purple-950/50 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800',
    label: 'Workflow Mutant',
  },
};

export const TestCaseDetailModal = ({
  isOpen,
  onClose,
  testCase,
  projectId,
  suiteId,
  onRunCase,
  isExecutingCase,
}) => {
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'oracle' | 'agent_payload'
  const [agentPayload, setAgentPayload] = useState(null);
  const [isLoadingPayload, setIsLoadingPayload] = useState(false);
  const [payloadError, setPayloadError] = useState(null);

  useEffect(() => {
    if (!isOpen || !testCase || !projectId || !suiteId) {
      setAgentPayload(null);
      setPayloadError(null);
      return;
    }

    if (testCase.execution_mode === 'LIVE_AGENT' || testCase.category !== 'mutated') {
      setIsLoadingPayload(true);
      setPayloadError(null);
      c2Api
        .getCaseAgentPayload(projectId, suiteId, testCase.test_id)
        .then((data) => {
          setAgentPayload(data);
        })
        .catch((err) => {
          setPayloadError(err.message || 'Agent payload not available for this case.');
          setAgentPayload(null);
        })
        .finally(() => {
          setIsLoadingPayload(false);
        });
    } else {
      setAgentPayload(null);
      setPayloadError(
        'Mutated evaluator test cases are private to the QA framework. The backend strictly excludes them from agent task exports.'
      );
    }
  }, [isOpen, testCase, projectId, suiteId]);

  if (!isOpen || !testCase) return null;

  const definition = testCase.definition || {};
  const mutation = definition.mutation || null;
  const category = (testCase.category || 'valid').toLowerCase();
  const categoryStyle = CATEGORY_STYLES[category] || CATEGORY_STYLES.valid;
  const isReady = testCase.is_ready || testCase.readiness === 'TEST_READY';

  const downloadJSON = (data, filename) => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs overflow-y-auto">
      <div className="relative w-full max-w-4xl max-h-[90vh] flex flex-col rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-slate-900 dark:text-white font-mono">
                  {testCase.test_id}
                </h2>
                <span
                  className={`px-2.5 py-0.5 rounded-full text-[10px] font-semibold border ${categoryStyle.bg}`}
                >
                  {categoryStyle.label}
                </span>
                <span
                  className={`px-2 py-0.5 rounded-full text-[10px] font-semibold flex items-center gap-1 ${
                    isReady
                      ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300'
                      : 'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300'
                  }`}
                >
                  {isReady ? (
                    <CheckCircle2 className="w-3 h-3" />
                  ) : (
                    <AlertCircle className="w-3 h-3" />
                  )}
                  {testCase.readiness || (isReady ? 'TEST_READY' : 'TEST_NOT_READY')}
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Suite: <span className="font-mono">{suiteId}</span> • Planned Mode:{' '}
                <span className="font-mono">{testCase.execution_mode}</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={isExecutingCase}
              onClick={() => onRunCase && onRunCase(suiteId, testCase.test_id)}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-semibold shadow-xs transition-colors"
              title="Execute this test case via backend demonstration runner"
            >
              <Play className="w-3.5 h-3.5" />
              <span>{isExecutingCase ? 'Executing...' : 'Run Case (Synthetic)'}</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex items-center px-6 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 gap-4 text-xs font-semibold">
          <button
            type="button"
            onClick={() => setActiveTab('overview')}
            className={`py-3 border-b-2 transition-colors ${
              activeTab === 'overview'
                ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400'
                : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
            }`}
          >
            Overview & Metadata
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('oracle')}
            className={`py-3 border-b-2 flex items-center gap-1.5 transition-colors ${
              activeTab === 'oracle'
                ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400'
                : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
            }`}
          >
            <Shield className="w-3.5 h-3.5 text-indigo-500" />
            Private QA Oracle (Tester View)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('agent_payload')}
            className={`py-3 border-b-2 flex items-center gap-1.5 transition-colors ${
              activeTab === 'agent_payload'
                ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400'
                : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
            }`}
          >
            <Bot className="w-3.5 h-3.5 text-emerald-500" />
            Allowlisted Agent Payload (Tested Agent View)
          </button>
        </div>

        {/* Tab Body */}
        <div className="p-6 overflow-y-auto space-y-6 max-h-[calc(90vh-140px)]">
          {/* TAB 1: OVERVIEW */}
          {activeTab === 'overview' && (
            <div className="space-y-5">
              {/* Task Description */}
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 space-y-1.5">
                <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  Agent Task Prompt:
                </span>
                <p className="text-sm font-medium text-slate-900 dark:text-white leading-relaxed">
                  "{testCase.task || definition.task}"
                </p>
              </div>

              {/* Core Metadata Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="p-3 rounded-xl bg-white dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800">
                  <div className="text-[10px] font-semibold text-slate-400 uppercase">
                    Fixture Reference
                  </div>
                  <div className="text-xs font-mono font-medium text-slate-800 dark:text-slate-200 truncate mt-1">
                    {testCase.fixture_ref || definition.fixture_ref || 'None'}
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-white dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800">
                  <div className="text-[10px] font-semibold text-slate-400 uppercase">
                    Pinned Model
                  </div>
                  <div className="text-xs font-mono font-medium text-slate-800 dark:text-slate-200 truncate mt-1">
                    {definition.pinned_model_id || testCase.model_id} v
                    {definition.pinned_model_version || testCase.model_version}
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-white dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800">
                  <div className="text-[10px] font-semibold text-slate-400 uppercase">
                    Expected Outcome
                  </div>
                  <div className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 truncate mt-1">
                    {definition.expected_outcome || 'PASS'}
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-white dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800">
                  <div className="text-[10px] font-semibold text-slate-400 uppercase">
                    Model Content Hash
                  </div>
                  <div
                    className="text-xs font-mono text-slate-600 dark:text-slate-400 truncate mt-1"
                    title={definition.model_content_hash}
                  >
                    {definition.model_content_hash?.substring(0, 16) || 'Unknown'}...
                  </div>
                </div>
              </div>

              {/* Readiness reasons if unready */}
              {definition.readiness_reasons?.length > 0 && (
                <div className="p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/60 text-xs text-amber-800 dark:text-amber-200 space-y-1">
                  <div className="font-semibold flex items-center gap-1.5">
                    <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                    <span>Readiness Diagnosed Issues</span>
                  </div>
                  <ul className="list-disc pl-5 space-y-0.5 text-[11px]">
                    {definition.readiness_reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Mutation Provenance Box (if mutated case) */}
              {mutation && (
                <div className="p-4 rounded-xl bg-purple-50/60 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-900/50 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <ShieldAlert className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                      <span className="text-xs font-bold text-purple-900 dark:text-purple-200 uppercase tracking-wider">
                        Workflow Mutation Provenance
                      </span>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-100 dark:bg-purple-900/60 text-purple-700 dark:text-purple-300">
                      Type: {mutation.mutation_type}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    <div>
                      <span className="text-[10px] text-slate-500 dark:text-slate-400 font-semibold uppercase">
                        Target Transition / Step:
                      </span>
                      <div className="font-mono text-purple-700 dark:text-purple-300 font-medium">
                        {mutation.target_transition_id || mutation.target_step || 'N/A'}
                      </div>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500 dark:text-slate-400 font-semibold uppercase">
                        Flaw Classification:
                      </span>
                      <div className="text-slate-800 dark:text-slate-200 font-medium">
                        {mutation.description || 'Controlled workflow deviation'}
                      </div>
                    </div>
                  </div>

                  {/* Mutated Path vs Original Path */}
                  {mutation.mutated_path && (
                    <div className="pt-2 border-t border-purple-100 dark:border-purple-900/40 space-y-1">
                      <span className="text-[10px] text-slate-500 font-semibold uppercase">
                        Mutated Transition Sequence:
                      </span>
                      <div className="flex flex-wrap items-center gap-1.5 font-mono text-[11px] p-2 rounded-lg bg-white/80 dark:bg-slate-900/80">
                        {mutation.mutated_path.map((step, idx) => (
                          <React.Fragment key={idx}>
                            <span className="px-1.5 py-0.5 rounded bg-purple-100 dark:bg-purple-900/60 text-purple-800 dark:text-purple-200">
                              {step}
                            </span>
                            {idx < mutation.mutated_path.length - 1 && (
                              <ArrowRight className="w-3 h-3 text-slate-400" />
                            )}
                          </React.Fragment>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="p-2.5 rounded-lg bg-purple-100/50 dark:bg-purple-900/20 text-[11px] text-purple-800 dark:text-purple-300 flex items-start gap-2">
                    <Info className="w-3.5 h-3.5 shrink-0 mt-0.5 text-purple-600" />
                    <span>
                      Component 2 workflow mutations govern sequence conformance (omitted, swapped,
                      repeated, illegal, wrong-entity, missing-effect transitions). Operational
                      timeouts and service faults are strictly isolated in Component 3.
                    </span>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: PRIVATE QA ORACLE */}
          {activeTab === 'oracle' && (
            <div className="space-y-4">
              <div className="p-3.5 rounded-xl bg-indigo-50/70 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-900/50 flex items-start gap-2.5 text-xs text-indigo-900 dark:text-indigo-200">
                <Lock className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold">Private QA Oracle (Strictly Isolated):</span> This
                  specification contains the authoritative reference path, expected state
                  transitions, assertions, and mutation metadata used by the evaluation engine. To
                  prevent data leakage, none of these fields are ever transmitted to the tested
                  agent.
                </div>
              </div>

              {/* Reference Path */}
              {definition.reference_path?.length > 0 && (
                <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800/40 space-y-2">
                  <div className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                    Authoritative Reference Path ({definition.reference_path.length} steps)
                  </div>
                  <div className="space-y-2">
                    {definition.reference_path.map((step, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 dark:bg-slate-900/60 border border-slate-100 dark:border-slate-800 text-xs font-mono"
                      >
                        <div className="flex items-center gap-2">
                          <span className="w-5 h-5 rounded-full bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 flex items-center justify-center text-[10px] font-bold">
                            {idx + 1}
                          </span>
                          <span className="font-semibold text-slate-800 dark:text-slate-200">
                            {step.transition_id || step.action || `step_${idx}`}
                          </span>
                        </div>
                        <div className="text-slate-500 text-[11px]">
                          {step.from_state} &rarr; {step.to_state}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Assertions */}
              {definition.assertions?.length > 0 && (
                <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800/40 space-y-2">
                  <div className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                    Verification Assertions ({definition.assertions.length})
                  </div>
                  <div className="space-y-1.5">
                    {definition.assertions.map((a, idx) => (
                      <div
                        key={idx}
                        className="p-2 rounded bg-slate-50 dark:bg-slate-900 text-xs font-mono text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-800"
                      >
                        {typeof a === 'string' ? a : JSON.stringify(a)}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Complete Raw QA Definition JSON */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Complete Frozen Definition (JSON)
                  </span>
                  <button
                    type="button"
                    onClick={() => downloadJSON(testCase, `${testCase.test_id}_qa_definition.json`)}
                    className="inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-medium"
                  >
                    <Download className="w-3 h-3" />
                    Download JSON
                  </button>
                </div>
                <pre className="p-3 rounded-xl bg-slate-900 text-slate-200 font-mono text-[11px] overflow-x-auto max-h-60">
                  {JSON.stringify(testCase, null, 2)}
                </pre>
              </div>
            </div>
          )}

          {/* TAB 3: ALLOWLISTED AGENT PAYLOAD */}
          {activeTab === 'agent_payload' && (
            <div className="space-y-4">
              <div className="p-3.5 rounded-xl bg-emerald-50/70 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/50 flex items-start gap-2.5 text-xs text-emerald-900 dark:text-emerald-200">
                <Bot className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold">Strictly Allowlisted Agent View:</span> This is the
                  exact payload served to tested agents. All private reference paths, intermediate
                  guards, expected outcomes, assertions, and mutation labels are strictly excluded
                  by the C2 backend.
                </div>
              </div>

              {isLoadingPayload ? (
                <div className="p-8 text-center text-xs text-slate-400">
                  <div className="w-5 h-5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                  Fetching allowlisted agent payload from backend...
                </div>
              ) : payloadError ? (
                <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-xs text-rose-800 dark:text-rose-200 space-y-1">
                  <div className="font-semibold flex items-center gap-1.5">
                    <ShieldAlert className="w-4 h-4 text-rose-600 shrink-0" />
                    <span>Agent Payload Isolation Enforced</span>
                  </div>
                  <p className="text-[11px] leading-relaxed">{payloadError}</p>
                </div>
              ) : agentPayload ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800/40">
                      <span className="text-[10px] text-slate-400 uppercase font-semibold">
                        Allowlisted Test ID:
                      </span>
                      <div className="font-mono text-slate-900 dark:text-white font-medium mt-1">
                        {agentPayload.test_id}
                      </div>
                    </div>
                    <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800/40">
                      <span className="text-[10px] text-slate-400 uppercase font-semibold">
                        Fixture Reference:
                      </span>
                      <div className="font-mono text-slate-900 dark:text-white font-medium mt-1">
                        {agentPayload.fixture_ref}
                      </div>
                    </div>
                  </div>

                  <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-800/40 space-y-1">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold">
                      Allowed Task Instruction:
                    </span>
                    <p className="text-xs font-medium text-slate-900 dark:text-white leading-relaxed">
                      "{agentPayload.task}"
                    </p>
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Exact Agent Task Payload (JSON)
                      </span>
                      <button
                        type="button"
                        onClick={() =>
                          downloadJSON(agentPayload, `${agentPayload.test_id}_agent_payload.json`)
                        }
                        className="inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-medium"
                      >
                        <Download className="w-3 h-3" />
                        Download JSON
                      </button>
                    </div>
                    <pre className="p-3 rounded-xl bg-slate-900 text-emerald-400 font-mono text-[11px] overflow-x-auto max-h-60">
                      {JSON.stringify(agentPayload, null, 2)}
                    </pre>
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/60">
          <div className="text-[11px] text-slate-500">
            Authoritative definition frozen by backend generator. Read-only tester interface.
          </div>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-200 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
