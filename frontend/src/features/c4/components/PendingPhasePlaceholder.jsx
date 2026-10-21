/**
 * Component 4 (C4) - Pending Phase Placeholder
 * Displays clear roadmap information for future phases (Phase 2, 3, 5, 6) without populating fake data.
 */

import React from 'react';
import { Clock, ShieldAlert, Sparkles, Layers } from 'lucide-react';

const PHASE_DETAILS = {
  test_cases: {
    phase: 'Phase 2',
    title: 'Policy Test Case Generation & Freezing',
    description:
      'Automated synthesis of adversarial prompt-injection payloads, boundary-probing tool arguments, and expected security invariant assertions derived from accepted policy contracts.',
    capabilities: [
      'Multi-modal prompt-injection templates (direct override, jailbreak, role-play, base64/rot13 encoding)',
      'Deterministic policy oracle generation linking inputs to expected tool-call allow/deny decisions',
      'Test case integrity hashing and immutable test freezing before execution',
      'Target domain tool-binding parameter fuzzing and semantic boundary probing',
    ],
    plannedEndpoints: [
      'POST /projects/{project_id}/c4/generate',
      'GET /projects/{project_id}/c4/cases',
      'GET /projects/{project_id}/c4/cases/{case_id}/versions/{version}',
    ],
  },
  runs_and_findings: {
    phase: 'Phase 3',
    title: 'Test Execution, Evidence Capture & Policy Invariant Findings',
    description:
      'Execution of frozen policy test cases against target LLM applications (Live AUT or Controlled Simulator), capturing real-time tool calls, outputs, and invariant violation findings.',
    capabilities: [
      'Live AUT and Simulated runtime adapters with safety sandboxing',
      'Real-time attempted action, disclosure, and committed effect evaluation',
      'Automated finding generation with cryptographic evidence package linking',
      'Execution run status tracking, latency recording, and cleanup rollback verification',
    ],
    plannedEndpoints: [
      'POST /projects/{project_id}/c4/execute',
      'GET /projects/{project_id}/c4/runs',
      'GET /projects/{project_id}/c4/runs/{run_id}',
      'GET /projects/{project_id}/c4/findings',
    ],
  },
  policy_changes: {
    phase: 'Phase 5',
    title: 'Policy Version Comparison & Selective Regression Testing',
    description:
      'Differential policy analysis across contract versions, automated impact analysis identifying affected test cases, and selective regression re-execution.',
    capabilities: [
      'Semantic diff between accepted policy contract versions',
      'Dependency analysis mapping changed rules to invalid/affected test cases',
      'Selective test regeneration and regression batch execution',
      'Regression trend reports tracking safety posture improvements or regressions',
    ],
    plannedEndpoints: [
      'POST /projects/{project_id}/c4/regression/compare',
      'POST /projects/{project_id}/c4/regression/batches',
      'GET /projects/{project_id}/c4/regression/reports/{report_id}',
    ],
  },
  evaluation_and_reports: {
    phase: 'Phase 6',
    title: 'Empirical Research Evaluation & Safety Audit Reports',
    description:
      'Comprehensive benchmark evaluations, inter-rater reliability metrics, confusion matrices, and audit-ready compliance reporting.',
    capabilities: [
      'Empirical detection accuracy benchmarking against known vulnerability datasets',
      'Inter-rater agreement (Fleiss kappa / Cohen kappa) on extraction and oracle labels',
      'Formal safety verification certificates and exportable audit trails (JSON/Markdown)',
      'Cross-component vulnerability correlation with C1, C2, and C3 findings',
    ],
    plannedEndpoints: [
      'POST /projects/{project_id}/c4/evaluate',
      'GET /projects/{project_id}/c4/evaluation/reports',
      'GET /projects/{project_id}/c4/evaluation/datasets',
    ],
  },
};

export function PendingPhasePlaceholder({ tabId }) {
  const details = PHASE_DETAILS[tabId] || {
    phase: 'Future Phase',
    title: 'Upcoming Lifecycle Phase',
    description: 'This phase is scheduled for future implementation according to the C4 project proposal.',
    capabilities: [],
    plannedEndpoints: [],
  };

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-8 shadow-sm">
      <div className="max-w-3xl">
        <div className="flex items-center gap-2 mb-3">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-100 dark:bg-indigo-950/80 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
            <Clock className="w-3.5 h-3.5" />
            {details.phase} Pending
          </span>
          <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
            Strict Implementation Scope: Phase 1 (Policy Preparation)
          </span>
        </div>

        <h3 className="text-xl font-bold text-slate-900 dark:text-white tracking-tight mb-2">
          {details.title}
        </h3>
        <p className="text-sm text-slate-600 dark:text-slate-300 mb-6 leading-relaxed">
          {details.description}
        </p>

        <div className="grid md:grid-cols-2 gap-6 pt-4 border-t border-slate-200 dark:border-slate-800">
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-3 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
              Planned Capabilities
            </h4>
            <ul className="space-y-2">
              {details.capabilities.map((cap, idx) => (
                <li key={idx} className="text-xs text-slate-600 dark:text-slate-400 flex items-start gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 mt-1.5 shrink-0" />
                  <span>{cap}</span>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-3 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-slate-500" />
              Backend Endpoints
            </h4>
            <div className="space-y-1.5 font-mono text-[11px] bg-slate-50 dark:bg-slate-950/60 p-3 rounded-xl border border-slate-200 dark:border-slate-800">
              {details.plannedEndpoints.map((ep, idx) => (
                <div key={idx} className="text-slate-700 dark:text-slate-300 truncate">
                  {ep}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-8 p-4 rounded-xl bg-slate-50 dark:bg-slate-950/50 border border-slate-200 dark:border-slate-800 flex items-start gap-3">
          <ShieldAlert className="w-5 h-5 text-indigo-500 shrink-0 mt-0.5" />
          <p className="text-xs text-slate-600 dark:text-slate-400 leading-normal">
            <strong>Honest Implementation Notice:</strong> This section is deliberately pending in Phase 1.
            In accordance with project guidelines, no mock or simulated data is displayed here. Complete Phase 1 Policy Preparation
            to establish accepted, immutable contracts before proceeding to test generation.
          </p>
        </div>
      </div>
    </div>
  );
}
