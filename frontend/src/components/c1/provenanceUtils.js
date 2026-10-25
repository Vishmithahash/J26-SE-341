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
 * Live NexaCart agent-run details recorded for a case execution, or null for other adapters.
 *
 * @param {Object} caseDetail - CaseExecutionDetail
 * @returns {Object|null}
 */
export function liveAgentRunInfo(caseDetail) {
  const rawTrace = caseDetail?.raw_trace || {};
  if (rawTrace.adapter !== 'NEXACART_LIVE_AGENT_ADAPTER') {
    return null;
  }
  return {
    agentRunId: rawTrace.agent_run_id || null,
    provider: rawTrace.agent_provider || null,
    model: rawTrace.agent_model || null,
    agentStatus: rawTrace.agent_status || null,
    outcome: rawTrace.caller_outcome || null,
    fixtureId: rawTrace.nexacart_fixture_id || null,
    durationMs: typeof rawTrace.duration_ms === 'number' ? rawTrace.duration_ms : null,
    finalAnswer: rawTrace.final_answer || null,
    harnessVersion: rawTrace.harness_version || null,
    error: rawTrace.error || rawTrace.agent_error?.message || null,
  };
}

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

  // Run summaries carry the provenance the backend corroborated from the recorded case traces
  const recorded = item.execution_provenance || item.summary?.execution_provenance;
  if (recorded && PROVENANCE_TYPES[recorded]) {
    return recorded;
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
    // Requires a live adapter AND actual execution status EXECUTED without simulation
    if (adapter === 'NEXACART_LIVE_AGENT_ADAPTER') {
      // Real NexaCart agent run: the backend records NexaCart's own agent run identifier.
      // A run that ended with an infrastructure error (e.g. an Ollama timeout) after NexaCart
      // started its agent is still live evidence; without an agent run nothing was executed.
      if (
        (c.execution_status === 'EXECUTED' || c.execution_status === 'EXECUTION_ERROR') &&
        rawTrace.is_live_execution === true &&
        !rawTrace.simulated &&
        rawTrace.agent_run_id
      ) {
        return PROVENANCE_TYPES.LIVE_EXECUTION;
      }
      continue; // an errored live case proves nothing; inspect the other cases
    }
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
