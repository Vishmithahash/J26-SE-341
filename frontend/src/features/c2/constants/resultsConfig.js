/**
 * Component 2 Phase 3: Results, Provenance, Coverage and Research Configurations.
 * Defines authoritative verdict mappings, execution provenance, and metric contracts.
 */

export const C2_VERDICTS = [
  'PASS',
  'EXPECTED REJECTION PASS',
  'FAIL',
  'INCONCLUSIVE',
  'MODEL NOT READY',
  'TEST NOT READY',
];

export const VERDICT_CONFIG = {
  PASS: {
    label: 'PASS',
    badgeText: 'PASS',
    badge: 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800',
    bg: 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800',
    description: 'Execution strictly conformed to model transitions and postconditions.',
  },
  'EXPECTED REJECTION PASS': {
    label: 'EXPECTED REJECTION PASS',
    badgeText: 'EXPECTED REJECTION PASS',
    badge: 'bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 border-teal-200 dark:border-teal-800',
    bg: 'bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 border-teal-200 dark:border-teal-800',
    description: 'Negative test case: Agent correctly rejected invalid action without reaching invalid state.',
  },
  FAIL: {
    label: 'FAIL',
    badgeText: 'FAIL',
    badge: 'bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800',
    bg: 'bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800',
    description: 'Execution diverged from reference model or violated guards/invariants.',
  },
  INCONCLUSIVE: {
    label: 'INCONCLUSIVE',
    badgeText: 'INCONCLUSIVE',
    badge: 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800',
    bg: 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800',
    description: 'Execution trace terminated prematurely or missing observations prevent conclusive verdict.',
  },
  'MODEL NOT READY': {
    label: 'MODEL NOT READY',
    badgeText: 'MODEL NOT READY',
    badge: 'bg-purple-50 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800',
    bg: 'bg-purple-50 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800',
    description: 'Reference model lacks required approval, predicates, or has unvalidated transitions.',
  },
  'TEST NOT READY': {
    label: 'TEST NOT READY',
    badgeText: 'TEST NOT READY',
    badge: 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700',
    bg: 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700',
    description: 'Test case specification is missing preconditions, initial parameters, or assertions.',
  },
};

export const PROVENANCE_CONFIG = {
  live_agent_run: {
    label: 'Live Agent Run',
    badge: 'bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800',
    isLive: true,
    description: 'Real-time execution against live NexaCart application or external agent.',
  },
  live_nexacart_agent: {
    label: 'Live NexaCart Agent',
    badge: 'bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800',
    isLive: true,
    description: "NexaCart's own LLM agent ran the generated task on a fresh harness fixture.",
  },
  live_trace_mutation: {
    label: 'Live-Trace Mutant',
    badge: 'bg-fuchsia-100 dark:bg-fuchsia-950 text-fuchsia-700 dark:text-fuchsia-300 border-fuchsia-200 dark:border-fuchsia-800',
    isLive: false,
    description: 'Controlled mutant of a real NexaCart trace (oracle sensitivity), not an observed agent failure.',
  },
  not_executed: {
    label: 'Not Executed',
    badge: 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700',
    isLive: false,
    description: 'Model or test was not ready, so no agent run took place.',
  },
  scripted_synthetic_demonstration: {
    label: 'Scripted Demonstration',
    badge: 'bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 border-amber-200 dark:border-amber-800',
    isLive: false,
    description: 'Pre-scripted deterministic demonstration verifying conformance logic.',
  },
  controlled_trace_fixture: {
    label: 'Controlled Trace Fixture',
    badge: 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700',
    isLive: false,
    description: 'Captured immutable trace fixture used for regression and reproduction verification.',
  },
};

export const COVERAGE_STATUS = {
  PREFER_SEPARATE: 'UNAVAILABLE_PREFER_SEPARATE_METRICS',
  DEFECT_DISCLAIMER: 'State-effect coverage measures state variable assertion checks; it is not equivalent to defect-detection accuracy without a labelled faulty dataset.',
};
