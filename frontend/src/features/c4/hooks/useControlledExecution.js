/**
 * Component 4 (C4) - Controlled Execution Hook
 * Manages runtime readiness checks, idempotent trial execution, run history, and explainable findings exports.
 */

import { useState, useCallback, useEffect } from 'react';
import { c4Api, ApiError } from '../api/c4Api.js';
import { TARGET_EXECUTION_MODES, SIMULATED_AGENT_BEHAVIORS } from '../api/types.js';

function generateUUID() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'idem-' + Math.random().toString(36).substring(2, 15) + '-' + Date.now();
}

export function useControlledExecution(projectId, isCurrentGeneration, getGeneration) {
  const [readinessReport, setReadinessReport] = useState(null);
  const [activeRun, setActiveRun] = useState(null);
  const [runsList, setRunsList] = useState([]);
  const [runReport, setRunReport] = useState(null);

  // Form states
  const [executionMode, setExecutionMode] = useState(TARGET_EXECUTION_MODES.SIMULATED);
  const [simulatedBehavior, setSimulatedBehavior] = useState(SIMULATED_AGENT_BEHAVIORS.COMPLIANT);
  const [idempotencyKey, setIdempotencyKey] = useState(generateUUID());

  // Loading states
  const [isCheckingReadiness, setIsCheckingReadiness] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [isLoadingRuns, setIsLoadingRuns] = useState(false);
  const [isLoadingReport, setIsLoadingReport] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  const resetState = useCallback(() => {
    setReadinessReport(null);
    setActiveRun(null);
    setRunsList([]);
    setRunReport(null);
    setIdempotencyKey(generateUUID());
    setIsCheckingReadiness(false);
    setIsExecuting(false);
    setIsLoadingRuns(false);
    setIsLoadingReport(false);
    setError(null);
    setSuccessMessage(null);
  }, []);

  const regenerateIdempotencyKey = useCallback(() => {
    setIdempotencyKey(generateUUID());
  }, []);

  const loadRuns = useCallback(
    async (params = {}) => {
      if (!projectId) return [];

      setIsLoadingRuns(true);
      setError(null);
      const currentGen = getGeneration();

      try {
        const runs = await c4Api.listExecutionRuns(projectId, params);
        if (!isCurrentGeneration(currentGen)) return [];

        setRunsList(runs);
        return runs;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Failed to load execution runs.');
        }
        return [];
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsLoadingRuns(false);
        }
      }
    },
    [projectId, getGeneration, isCurrentGeneration]
  );

  useEffect(() => {
    if (projectId) {
      loadRuns({ limit: 50, offset: 0 });
    }
  }, [projectId, loadRuns]);

  const checkReadiness = useCallback(
    async ({
      caseId,
      caseVersion = 1,
      contractId,
      contractVersion = 1,
      bindingId,
      bindingVersion = 1,
      mode = executionMode,
      behavior = simulatedBehavior,
    }) => {
      if (!projectId || !caseId || !contractId || !bindingId) return null;

      setIsCheckingReadiness(true);
      setError(null);
      const currentGen = getGeneration();

      try {
        const payload = {
          case_id: caseId,
          case_version: Number(caseVersion),
          contract_id: contractId,
          contract_version: Number(contractVersion),
          binding_id: bindingId,
          binding_version: Number(bindingVersion),
          execution_mode: mode,
          simulated_behavior: behavior,
        };

        const report = await c4Api.checkExecutionReadiness(projectId, payload);
        if (!isCurrentGeneration(currentGen)) return null;

        setReadinessReport(report);
        return report;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Runtime readiness check failed.');
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsCheckingReadiness(false);
        }
      }
    },
    [projectId, executionMode, simulatedBehavior, getGeneration, isCurrentGeneration]
  );

  const executeCase = useCallback(
    async ({
      caseId,
      caseVersion = 1,
      contractId,
      contractVersion = 1,
      bindingId,
      bindingVersion = 1,
      mode = executionMode,
      behavior = simulatedBehavior,
      key = idempotencyKey,
    }) => {
      if (!projectId || !caseId || !contractId || !bindingId) {
        setError('Missing required case or pinned dependency parameters.');
        return null;
      }

      setIsExecuting(true);
      setError(null);
      setSuccessMessage(null);
      const currentGen = getGeneration();

      try {
        const payload = {
          case_id: caseId,
          case_version: Number(caseVersion),
          contract_id: contractId,
          contract_version: Number(contractVersion),
          binding_id: bindingId,
          binding_version: Number(bindingVersion),
          execution_mode: mode,
          simulated_behavior: behavior,
          idempotency_key: key || null,
        };

        const runRecord = await c4Api.executeTestCase(projectId, payload);
        if (!isCurrentGeneration(currentGen)) return null;

        setActiveRun(runRecord);
        setRunsList((prev) => [runRecord, ...prev.filter((r) => r.run_id !== runRecord.run_id)]);
        setSuccessMessage(
          `Run ${runRecord.run_id} completed with status: ${runRecord.status} (Policy: ${runRecord.policy_verdict}, Exposure: ${runRecord.exposure_status}).`
        );
        return runRecord;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          if (err instanceof ApiError && err.status === 409) {
            setError(
              'Idempotency conflict: this idempotency key was previously submitted with different parameters. Click "Generate New Key" to create an independent execution attempt.'
            );
          } else {
            setError(err.message || 'Test execution invocation failed.');
          }
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsExecuting(false);
        }
      }
    },
    [projectId, executionMode, simulatedBehavior, idempotencyKey, getGeneration, isCurrentGeneration]
  );

  const fetchRun = useCallback(
    async (runId) => {
      if (!projectId || !runId) return null;

      setError(null);
      const currentGen = getGeneration();

      try {
        const runRecord = await c4Api.getExecutionRun(projectId, runId.trim());
        if (!isCurrentGeneration(currentGen)) return null;

        setActiveRun(runRecord);
        return runRecord;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || `Execution run "${runId}" not found.`);
        }
        return null;
      }
    },
    [projectId, getGeneration, isCurrentGeneration]
  );

  const fetchRunReport = useCallback(
    async (runId) => {
      if (!projectId || !runId) return null;

      setIsLoadingReport(true);
      setError(null);
      const currentGen = getGeneration();

      try {
        const report = await c4Api.exportRunReport(projectId, runId.trim());
        if (!isCurrentGeneration(currentGen)) return null;

        setRunReport(report);
        return report;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || `Failed to export report for run "${runId}".`);
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsLoadingReport(false);
        }
      }
    },
    [projectId, getGeneration, isCurrentGeneration]
  );

  return {
    readinessReport,
    setReadinessReport,
    activeRun,
    setActiveRun,
    runsList,
    setRunsList,
    runReport,
    setRunReport,
    executionMode,
    setExecutionMode,
    simulatedBehavior,
    setSimulatedBehavior,
    idempotencyKey,
    setIdempotencyKey,
    regenerateIdempotencyKey,
    isCheckingReadiness,
    isExecuting,
    isLoadingRuns,
    isLoadingReport,
    error,
    setError,
    successMessage,
    setSuccessMessage,
    checkReadiness,
    executeCase,
    loadRuns,
    fetchRun,
    fetchRunReport,
    resetState,
  };
}
