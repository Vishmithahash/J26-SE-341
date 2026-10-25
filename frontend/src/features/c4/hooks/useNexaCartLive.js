/**
 * Component 4 (C4) - Live NexaCart Target Hook
 * Readiness of the NexaCart QA harness, import of the NexaCart policy domain, and background
 * live execution of frozen policy cases through the NexaCart LLM agent (with progress polling).
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { c4Api } from '../api/c4Api.js';

export const LIVE_POLL_INTERVAL_MS = 3000;
// Live runs per case offered in the UI; the proposal uses 3.
export const REPETITION_OPTIONS = [1, 2, 3, 5];

export function formatRate(rate) {
  return rate === null || rate === undefined ? '—' : `${Math.round(rate * 100)}%`;
}

export function isLiveExecutionFinished(execution) {
  return Boolean(execution) && execution.status !== 'RUNNING';
}

export function useNexaCartLive(projectId, isCurrentGeneration, getGeneration) {
  const [readiness, setReadiness] = useState(null);
  const [importResult, setImportResult] = useState(null);
  const [execution, setExecution] = useState(null);

  const [isCheckingReadiness, setIsCheckingReadiness] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  const pollTimer = useRef(null);

  const stopPolling = useCallback(() => {
    if (pollTimer.current) {
      clearTimeout(pollTimer.current);
      pollTimer.current = null;
    }
  }, []);

  const resetState = useCallback(() => {
    stopPolling();
    setReadiness(null);
    setImportResult(null);
    setExecution(null);
    setIsCheckingReadiness(false);
    setIsImporting(false);
    setIsStarting(false);
    setError(null);
    setSuccessMessage(null);
  }, [stopPolling]);

  useEffect(() => {
    resetState();
  }, [projectId, resetState]);

  useEffect(() => stopPolling, [stopPolling]);

  const checkReadiness = useCallback(async () => {
    if (!projectId) return null;
    setIsCheckingReadiness(true);
    setError(null);
    const currentGen = getGeneration();
    try {
      const report = await c4Api.getNexaCartLiveReadiness(projectId);
      if (!isCurrentGeneration(currentGen)) return null;
      setReadiness(report);
      return report;
    } catch (err) {
      if (isCurrentGeneration(currentGen)) {
        setReadiness(null);
        setError(err.message || 'Failed to check NexaCart readiness.');
      }
      return null;
    } finally {
      if (isCurrentGeneration(currentGen)) setIsCheckingReadiness(false);
    }
  }, [projectId, getGeneration, isCurrentGeneration]);

  const importDomain = useCallback(async () => {
    if (!projectId) return null;
    setIsImporting(true);
    setError(null);
    setSuccessMessage(null);
    const currentGen = getGeneration();
    try {
      const result = await c4Api.importNexaCartLive(projectId);
      if (!isCurrentGeneration(currentGen)) return null;
      setImportResult(result);
      setSuccessMessage(
        `Imported NexaCart policy '${result.artifact_id}' v${result.artifact_version}, ` +
          `binding '${result.binding_id}' v${result.binding_version} and ${result.candidate_rule_ids.length} candidate rules.`
      );
      return result;
    } catch (err) {
      if (isCurrentGeneration(currentGen)) setError(err.message || 'Failed to import the NexaCart domain.');
      return null;
    } finally {
      if (isCurrentGeneration(currentGen)) setIsImporting(false);
    }
  }, [projectId, getGeneration, isCurrentGeneration]);

  const pollExecution = useCallback(
    (executionId, onFinished, currentGen) => {
      stopPolling();
      const tick = async () => {
        try {
          const latest = await c4Api.getNexaCartLiveExecution(projectId, executionId);
          if (!isCurrentGeneration(currentGen)) return;
          setExecution(latest);
          if (isLiveExecutionFinished(latest)) {
            pollTimer.current = null;
            setSuccessMessage(
              `Live NexaCart execution ${latest.status.toLowerCase()}: ${latest.completed_runs}/${latest.total_runs} runs ` +
                `(${latest.total_cases} cases × ${latest.repetitions}).`
            );
            if (onFinished) onFinished(latest);
            return;
          }
        } catch (err) {
          if (!isCurrentGeneration(currentGen)) return;
          setError(err.message || 'Failed to read live execution progress.');
        }
        pollTimer.current = setTimeout(tick, LIVE_POLL_INTERVAL_MS);
      };
      pollTimer.current = setTimeout(tick, LIVE_POLL_INTERVAL_MS);
    },
    [projectId, isCurrentGeneration, stopPolling]
  );

  const startExecution = useCallback(
    async ({ contractId, contractVersion, caseIds = null, repetitions = 1 }, onFinished) => {
      if (!projectId) return null;
      setIsStarting(true);
      setError(null);
      setSuccessMessage(null);
      const currentGen = getGeneration();
      try {
        const started = await c4Api.startNexaCartLiveExecution(projectId, {
          contract_id: contractId,
          contract_version: contractVersion,
          case_ids: caseIds,
          repetitions,
        });
        if (!isCurrentGeneration(currentGen)) return null;
        setExecution(started);
        if (isLiveExecutionFinished(started)) {
          if (onFinished) onFinished(started);
        } else {
          pollExecution(started.execution_id, onFinished, currentGen);
        }
        return started;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) setError(err.message || 'Failed to start the live NexaCart execution.');
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) setIsStarting(false);
      }
    },
    [projectId, getGeneration, isCurrentGeneration, pollExecution]
  );

  return {
    readiness,
    importResult,
    execution,
    isCheckingReadiness,
    isImporting,
    isStarting,
    isRunning: Boolean(execution) && !isLiveExecutionFinished(execution),
    error,
    successMessage,
    checkReadiness,
    importDomain,
    startExecution,
    resetState,
  };
}
