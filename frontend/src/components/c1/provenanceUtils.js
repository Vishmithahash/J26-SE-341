/**
 * Execution Provenance Utility for Component 1 (Explainable Tool-Call Correctness Testing)
 *
 * Explicitly distinguishes:
 * 1. LIVE_EXECUTION: Live application or agent container execution.
 * 2. SYNTHETIC_DEMO: Synthetic or demonstration execution (simulated adapter, mock fixtures).
 * 3. IMPORTED_REPLAY: Imported or replayed evidence from recorded traces or benchmark datasets.
 * 4. UNKNOWN_ORIGIN: Unknown or unverified origin (missing or uncorroborated provenance).
 *
 * Rules:
 * - Never infer live execution from a successful health check, a stored model preference,
 *   or the requested execution mode alone.
 * - Do not silently substitute a demonstration when live execution is unavailable.
 * - Keep demonstration results separate from live performance summaries.
 */

export const PROVENANCE_TYPES = {
  LIVE_EXECUTION: 'LIVE_EXECUTION',
  SYNTHETIC_DEMO: 'SYNTHETIC_DEMO',
  IMPORTED_REPLAY: 'IMPORTED_REPLAY',
  UNKNOWN_ORIGIN: 'UNKNOWN_ORIGIN',
};

export const PROVENANCE_METADATA = {
  [PROVENANCE_TYPES.LIVE_EXECUTION]: {
    label: 'Live Application Execution',
    shortLabel: 'Live Execution',
    badgeVariant: 'live',
    description: 'Executed against a real running agent endpoint or deployed container.',
    isLive: true,
    isSynthetic: false,
  },
  [PROVENANCE_TYPES.SYNTHETIC_DEMO]: {
    label: 'Synthetic / Demonstration Execution',
    shortLabel: 'Synthetic Demo',
    badgeVariant: 'synthetic',
    description: 'Executed using a simulated deterministic adapter or synthetic test fixtures.',
    isLive: false,
    isSynthetic: true,
  },
  [PROVENANCE_TYPES.IMPORTED_REPLAY]: {
    label: 'Imported / Replayed Evidence',
    shortLabel: 'Imported Replay',
    badgeVariant: 'replay',
    description: 'Historical or imported trace evidence replayed without live agent invocation.',
    isLive: false,
    isSynthetic: false,
  },
  [PROVENANCE_TYPES.UNKNOWN_ORIGIN]: {
    label: 'Unknown / Unverified Origin',
    shortLabel: 'Unknown Origin',
    badgeVariant: 'unknown',
    description: 'Execution provenance could not be corroborated from backend evidence records.',
    isLive: false,
    isSynthetic: false,
  },
};

/**
 * Determine the execution provenance of a run or case execution record.
 *
 * @param {Object} item - RunDetailResponse, RunSummary, or CaseExecutionDetail
 * @returns {string} Key in PROVENANCE_TYPES
 */
export function getExecutionProvenance(item) {
  if (!item || typeof item !== 'object') {
    return PROVENANCE_TYPES.UNKNOWN_ORIGIN;
  }

  // Check effective_config from RunDetailResponse or RunSummary
  const config = item.effective_config || item.summary?.effective_config || {};
  const adapterOverride = String(config.adapter_override || item.adapter_override || '').toUpperCase();
  const connRef = String(config.agent_connection_ref || '').toLowerCase();

  // If adapter_override or connection ref indicates simulated/mock
  if (
    adapterOverride.includes('SIMULATED') ||
    adapterOverride.includes('MOCK') ||
    adapterOverride.includes('FAKE') ||
    connRef.startsWith('urn:conn:mock') ||
    connRef.startsWith('simulated:')
  ) {
    return PROVENANCE_TYPES.SYNTHETIC_DEMO;
  }

  // Check case executions or raw trace
  const caseList = Array.isArray(item.case_executions)
    ? item.case_executions
    : Array.isArray(item.captured_events)
    ? [item]
    : [];

  // Inspect raw traces across available cases
  for (const c of caseList) {
    const rawTrace = c.raw_trace || {};
    const adapter = String(rawTrace.adapter || c.adapter || '').toUpperCase();

    // Check for replayed or imported evidence channels
    const evidenceList = Array.isArray(c.evidence_records) ? c.evidence_records : [];
    const hasReplayEvidence = evidenceList.some((e) => {
      const ch = String(e.channel || '').toUpperCase();
      const uri = String(e.uri_or_pointer || '').toLowerCase();
      return (
        ch === 'REPLAYED' ||
        ch === 'IMPORTED' ||
        uri.startsWith('replay://') ||
        uri.startsWith('import://')
      );
    });

    if (hasReplayEvidence) {
      return PROVENANCE_TYPES.IMPORTED_REPLAY;
    }

    if (
      adapter === 'SIMULATED_FAKE_ADAPTER' ||
      rawTrace.simulated === true ||
      adapter.includes('FAKE')
    ) {
      return PROVENANCE_TYPES.SYNTHETIC_DEMO;
    }

    // Live adapter verification:
    // Requires adapter to be LIVE_AGENT_ADAPTER AND actual execution status EXECUTED without simulation
    if (adapter === 'LIVE_AGENT_ADAPTER') {
      if (
        c.execution_status === 'EXECUTED' &&
        !rawTrace.simulated &&
        !rawTrace.error
      ) {
        return PROVENANCE_TYPES.LIVE_EXECUTION;
      }
      // If live adapter failed with unreachable error or not ready, it is NOT verified live execution
      return PROVENANCE_TYPES.UNKNOWN_ORIGIN;
    }
  }

  // Fallback to synthetic if run was executed with simulated mode in summary
  if (item.status === 'COMPLETED' && (adapterOverride || connRef)) {
    return PROVENANCE_TYPES.SYNTHETIC_DEMO;
  }

  return PROVENANCE_TYPES.UNKNOWN_ORIGIN;
}
