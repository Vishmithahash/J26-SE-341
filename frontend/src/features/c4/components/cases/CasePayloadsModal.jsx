/**
 * Component 4 (C4) - Three Payload Boundaries Inspector Modal
 * Inspects strictly separated Agent Task, Harness Orchestration, and Evaluator Oracle payloads.
 */

import React, { useState, useEffect } from 'react';
import {
  X,
  Shield,
  Layers,
  Terminal,
  FileCheck,
  Lock,
} from 'lucide-react';

export function CasePayloadsModal({
  isOpen,
  testCase,
  payloads,
  isLoading,
  onClose,
  onLoadPayloads,
}) {
  const [activeTab, setActiveTab] = useState('agent'); // 'agent' | 'harness' | 'evaluator'

  useEffect(() => {
    if (isOpen && testCase && onLoadPayloads) {
      onLoadPayloads(testCase.case_id, testCase.case_version);
    }
  }, [isOpen, testCase, onLoadPayloads]);

  if (!isOpen || !testCase) return null;

  const { agent, harness, evaluator } = payloads || {};

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="payload-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm animate-in fade-in duration-150"
    >
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl w-full max-w-3xl shadow-2xl p-6 relative flex flex-col max-h-[90vh]">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1 rounded-lg transition-colors"
          aria-label="Close dialog"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="pb-4 border-b border-slate-100 dark:border-slate-800">
          <div className="flex flex-wrap items-center gap-2 mb-1.5">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 px-2 py-0.5 rounded">
              Three Payload Boundaries
            </span>
            <span className="text-xs font-mono font-medium text-slate-500">
              {testCase.case_id} (v{testCase.case_version})
            </span>
          </div>
          <h3 id="payload-modal-title" className="text-base font-bold text-slate-900 dark:text-white">
            Separated Payload Inspection & Provenance
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Strict isolation ensures the tested agent sees only legitimate task context; hidden goals and oracle assertions remain sealed.
          </p>
        </div>

        {/* Tab Selection */}
        <div className="flex border-b border-slate-200 dark:border-slate-800 mt-4 space-x-2">
          {[
            { id: 'agent', label: '1. Agent Task Payload', icon: Terminal },
            { id: 'harness', label: '2. Harness Payload', icon: Layers },
            { id: 'evaluator', label: '3. Evaluator Oracle', icon: FileCheck },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold rounded-t-xl border-b-2 transition-all cursor-pointer ${
                  isActive
                    ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 bg-indigo-50/50 dark:bg-indigo-950/30'
                    : 'border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Scrollable Payload Body */}
        <div className="flex-1 overflow-y-auto py-4 space-y-4">
          {isLoading ? (
            <div className="py-12 flex flex-col items-center justify-center space-y-3">
              <div className="w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
              <span className="text-xs text-slate-500">Exporting separated payloads from backend...</span>
            </div>
          ) : (
            <>
              {/* TAB 1: Agent Task Payload */}
              {activeTab === 'agent' && (
                <div className="space-y-4 animate-in fade-in duration-100">
                  <div className="p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 flex items-start gap-2.5 text-xs text-emerald-900 dark:text-emerald-200">
                    <Shield className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-bold">Agent Task Isolation Guarantee:</p>
                      <p className="text-emerald-800 dark:text-emerald-300 text-[11px] mt-0.5">
                        This view contains strictly what the tested agent receives. Hidden attacker goals, internal policy rules, and evaluation verdicts are strictly excluded.
                      </p>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      User / Agent Task Prompt
                    </label>
                    <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-900 dark:text-slate-100 leading-relaxed whitespace-pre-wrap select-text">
                      {agent?.agent_task_prompt || testCase.agent_task_prompt}
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Available Target Tools
                    </label>
                    <div className="flex flex-wrap gap-1.5">
                      {agent?.available_tools?.length > 0 ? (
                        agent.available_tools.map((tool) => (
                          <span
                            key={tool}
                            className="px-2.5 py-1 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 font-mono text-xs border border-indigo-200 dark:border-indigo-800"
                          >
                            {tool}
                          </span>
                        ))
                      ) : (
                        <span className="text-xs text-slate-400 italic">All bound domain tools</span>
                      )}
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Visible Application Context
                    </label>
                    <pre className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-[11px] font-mono text-slate-700 dark:text-slate-300 overflow-x-auto">
                      {JSON.stringify(agent?.visible_context || {}, null, 2)}
                    </pre>
                  </div>
                </div>
              )}

              {/* TAB 2: Harness Orchestration Payload */}
              {activeTab === 'harness' && (
                <div className="space-y-4 animate-in fade-in duration-100">
                  <div className="p-3.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-800 flex items-start gap-2.5 text-xs text-indigo-900 dark:text-indigo-200">
                    <Layers className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-bold">Harness Placement Ownership:</p>
                      <p className="text-indigo-800 dark:text-indigo-300 text-[11px] mt-0.5">
                        The test harness manages delivery of untrusted content into declared channels (support tickets, tool returns). It is never promoted into system instructions.
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800">
                      <span className="text-slate-400 block text-[11px]">Injection Channel:</span>
                      <span className="font-mono font-bold text-slate-800 dark:text-slate-200">
                        {harness?.injection_placement_channel || testCase.injection_placement_channel || 'None (Benign Control)'}
                      </span>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800">
                      <span className="text-slate-400 block text-[11px]">Untrusted Source ID:</span>
                      <span className="font-mono font-bold text-slate-800 dark:text-slate-200">
                        {harness?.untrusted_source_id || 'untrusted_document_source'}
                      </span>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Adversarial Injection Payload (Safe Data View)
                    </label>
                    <div className="p-3 rounded-xl bg-rose-50/50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900 text-xs font-mono text-rose-900 dark:text-rose-200 leading-relaxed whitespace-pre-wrap select-text">
                      {harness?.injection_payload || testCase.injection_payload || '(None: Benign test case)'}
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Required Preconditions
                    </label>
                    <ul className="list-disc pl-5 text-xs text-slate-600 dark:text-slate-400 space-y-1 font-mono">
                      {(harness?.preconditions || testCase.preconditions || ['Domain fixtures initialized']).map((pre, i) => (
                        <li key={i}>{pre}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {/* TAB 3: Evaluator Oracle Payload */}
              {activeTab === 'evaluator' && (
                <div className="space-y-4 animate-in fade-in duration-100">
                  <div className="p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 flex items-start gap-2.5 text-xs text-amber-900 dark:text-amber-200">
                    <Lock className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-bold">Confidential Evaluator Oracle:</p>
                      <p className="text-amber-800 dark:text-amber-300 text-[11px] mt-0.5">
                        These assertions and attacker goals are reserved strictly for the policy verification engine to determine PASS/FAIL verdicts.
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                    <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800">
                      <span className="text-[10px] text-slate-400 uppercase font-semibold">Boundary</span>
                      <p className="font-mono font-bold text-slate-800 dark:text-slate-200">
                        {evaluator?.expected_boundary || testCase.expected_boundary}
                      </p>
                    </div>
                    <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800">
                      <span className="text-[10px] text-slate-400 uppercase font-semibold">Expected Verdict</span>
                      <p className="font-mono font-bold text-emerald-600 dark:text-emerald-400">
                        {evaluator?.expected_policy_verdict || testCase.expected_policy_verdict}
                      </p>
                    </div>
                    <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800">
                      <span className="text-[10px] text-slate-400 uppercase font-semibold">Action Legality</span>
                      <p className="font-mono font-bold text-slate-800 dark:text-slate-200">
                        {evaluator?.requested_action_legality || testCase.requested_action_legality}
                      </p>
                    </div>
                    <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800">
                      <span className="text-[10px] text-slate-400 uppercase font-semibold">Safe Behavior</span>
                      <p className="font-mono font-bold text-indigo-600 dark:text-indigo-400">
                        {evaluator?.expected_safe_behavior || testCase.expected_safe_behavior}
                      </p>
                    </div>
                  </div>

                  {/* Hidden Attacker Goal */}
                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Hidden Attacker Objective (Ground Truth)
                    </label>
                    <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-800 dark:text-slate-200">
                      {evaluator?.hidden_attacker_goal || testCase.hidden_attacker_goal || 'None (Benign non-adversarial task)'}
                    </div>
                  </div>

                  {/* Expected Assertions Table */}
                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Per-Rule Expected Assertions
                    </label>
                    <div className="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-xl">
                      <table className="w-full text-xs text-left">
                        <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 font-semibold border-b border-slate-200 dark:border-slate-800">
                          <tr>
                            <th className="px-3 py-2">Rule ID</th>
                            <th className="px-3 py-2">Expected Applicability</th>
                            <th className="px-3 py-2">Expected Compliance</th>
                            <th className="px-3 py-2">On Compromise</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono text-[11px]">
                          {(evaluator?.expected_assertions || testCase.expected_assertions || []).map((ast, i) => (
                            <tr key={i}>
                              <td className="px-3 py-2 font-bold text-slate-800 dark:text-slate-200">{ast.rule_id}</td>
                              <td className="px-3 py-2">{ast.expected_applicability}</td>
                              <td className="px-3 py-2 text-emerald-600 dark:text-emerald-400 font-bold">{ast.expected_compliance}</td>
                              <td className="px-3 py-2 text-rose-600 dark:text-rose-400">{ast.expected_violation_on_compromise || 'FAIL'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <span className="text-[11px] text-slate-400">
            Adversarial payload safely rendered as pure string data.
          </span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-300 transition-colors"
          >
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
}
