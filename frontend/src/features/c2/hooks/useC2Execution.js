import { useState, useEffect, useRef, useCallback } from 'react';
import { c2Api } from '../api/c2Api.js';

export const LOCAL_RUNNER_CAPABILITIES = {
  runnerId: 'local_synthetic_runner_v1',
  runnerVersion: '2026.1',
  isLiveExecution: false,
  liveCapabilitiesAvailable: false,
  unavailableLiveCapabilities: [
    'live_llm_runner',
    'shared_intake_service',
    'unified_report_aggregator',
  ],
  observationCapabilities: [
    'state_snapshots',
    'before_after_diffs',
    'event_logs',
  ],
  name: 'Local Synthetic Runner (Scripted Demonstrations)',
  disclosure:
    'A live LLM agent runner adapter is currently unavailable on the server. Execution uses the backend’s reproducible local synthetic demonstration runner with strict oracle isolation.',
};

/**
 * Custom hook managing C2 Execution Controls:
 * - Single-case execution
 * - Bounded-suite execution
 * - Synthetic demonstration execution
 * - Reproducible re-evaluation and verification
 * - Duplicate submission prevention
 * - Stale response protection
 */
export const useC2Execution = (projectId, userId) => {
  const [evaluations, setEvaluations] = useState([]);
  const [latestEvaluation, setLatestEvaluation] = useState(null);
  const [suiteReport, setSuiteReport] = useState(null);
  const [retainedEvidence, setRetainedEvidence] = useState(null);
  const [reproductionResult, setReproductionResult] = useState(null);

  // In-flight loading flags
  const [isExecutingCase, setIsExecutingCase] = useState(false);
  const [isExecutingSuite, setIsExecutingSuite] = useState(false);
  const [isExecutingDemo, setIsExecutingDemo] = useState(false);
  const [isReEvaluating, setIsReEvaluating] = useState(false);
  const [isLoadingEvaluations, setIsLoadingEvaluations] = useState(false);

  // Errors
  const [executionError, setExecutionError] = useState(null);

  // In-flight ref to guarantee synchronous duplicate click prevention
  const inFlightRef = useRef(false);
  const generationRef = useRef(0);

  /**
   * Load evaluation history for the project
   */
  const loadEvaluations = useCallback(async (filters = {}) => {
    if (!projectId) return;
    const currentGen = ++generationRef.current;
    setIsLoadingEvaluations(true);

    try {
      const data = await c2Api.listEvaluations(projectId, filters);
      if (currentGen !== generationRef.current) return;
      setEvaluations(data || []);
    } catch {
      if (currentGen !== generationRef.current) return;
      setEvaluations([]);
    } finally {
      if (currentGen === generationRef.current) {
        setIsLoadingEvaluations(false);
      }
    }
  }, [projectId]);

  // Reset state when project or user changes
  useEffect(() => {
    generationRef.current += 1;
    inFlightRef.current = false;
    setEvaluations([]);
    setLatestEvaluation(null);
    setSuiteReport(null);
    setRetainedEvidence(null);
    setReproductionResult(null);
    setExecutionError(null);
    setIsExecutingCase(false);
    setIsExecutingSuite(false);
    setIsExecutingDemo(false);
    setIsReEvaluating(false);

    if (projectId && userId) {
      loadEvaluations();
    }
  }, [projectId, userId, loadEvaluations]);

  /**
   * Execute single test case with duplicate submission prevention
   */
  const executeCase = useCallback(
    async (suiteId, testId) => {
      if (!projectId) throw new Error('No active project selected.');
      if (inFlightRef.current) {
        throw new Error('An execution request is already in progress. Duplicate submissions are prevented.');
      }

      inFlightRef.current = true;
      setIsExecutingCase(true);
      setExecutionError(null);
      setReproductionResult(null);

      try {
        const result = await c2Api.runCase(projectId, suiteId, testId);
        setLatestEvaluation(result);
        // Prepend to evaluations list
        setEvaluations((prev) => [result, ...prev.filter((e) => e.evaluation_id !== result.evaluation_id)]);
        return result;
      } catch (err) {
        const msg = err.message || 'Test case execution failed.';
        setExecutionError(msg);
        throw err;
      } finally {
        inFlightRef.current = false;
        setIsExecutingCase(false);
      }
    },
    [projectId]
  );

  /**
   * Execute bounded test suite with max_cases budget
   */
  const executeBoundedSuite = useCallback(
    async (suiteId, maxCases = 20) => {
      if (!projectId) throw new Error('No active project selected.');
      if (inFlightRef.current) {
        throw new Error('An execution request is already in progress. Duplicate submissions are prevented.');
      }

      inFlightRef.current = true;
      setIsExecutingSuite(true);
      setExecutionError(null);

      try {
        const report = await c2Api.runSuite(projectId, suiteId, maxCases);
        setSuiteReport(report);
        // Reload evaluations
        await loadEvaluations({ suiteId });
        return report;
      } catch (err) {
        const msg = err.message || 'Bounded suite execution failed.';
        setExecutionError(msg);
        throw err;
      } finally {
        inFlightRef.current = false;
        setIsExecutingSuite(false);
      }
    },
    [projectId, loadEvaluations]
  );

  /**
   * Execute offline synthetic demonstration with chosen flaw/scenario
   */
  const executeDemonstration = useCallback(
    async (requestData) => {
      if (!projectId) throw new Error('No active project selected.');
      if (inFlightRef.current) {
        throw new Error('An execution request is already in progress. Duplicate submissions are prevented.');
      }

      inFlightRef.current = true;
      setIsExecutingDemo(true);
      setExecutionError(null);
      setReproductionResult(null);

      try {
        const result = await c2Api.runSyntheticDemonstration(projectId, requestData);
        setLatestEvaluation(result);
        setEvaluations((prev) => [result, ...prev.filter((e) => e.evaluation_id !== result.evaluation_id)]);
        return result;
      } catch (err) {
        const msg = err.message || 'Synthetic demonstration execution failed.';
        setExecutionError(msg);
        throw err;
      } finally {
        inFlightRef.current = false;
        setIsExecutingDemo(false);
      }
    },
    [projectId]
  );

  /**
   * Load retained evidence for a run
   */
  const fetchEvidence = useCallback(
    async (runId) => {
      if (!projectId || !runId) return null;
      try {
        const data = await c2Api.getRetainedEvidence(projectId, runId);
        setRetainedEvidence(data);
        return data;
      } catch {
        setRetainedEvidence(null);
        return null;
      }
    },
    [projectId]
  );

  /**
   * Re-evaluate execution from retained evidence
   */
  const reEvaluate = useCallback(
    async (evaluationId, options = {}) => {
      if (!projectId || !evaluationId) return;
      setIsReEvaluating(true);
      setExecutionError(null);

      try {
        const result = await c2Api.reEvaluateExecution(projectId, evaluationId, options);
        setLatestEvaluation(result);
        setEvaluations((prev) => [result, ...prev.filter((e) => e.evaluation_id !== result.evaluation_id)]);
        return result;
      } catch (err) {
        setExecutionError(err.message || 'Re-evaluation failed.');
        throw err;
      } finally {
        setIsReEvaluating(false);
      }
    },
    [projectId]
  );

  /**
   * Verify independent replay reproduction
   */
  const verifyEvaluationReproduction = useCallback(
    async (evaluationId) => {
      if (!projectId || !evaluationId) return;
      setIsReEvaluating(true);
      setExecutionError(null);

      try {
        const result = await c2Api.verifyReproduction(projectId, evaluationId);
        setReproductionResult(result);
        return result;
      } catch (err) {
        setExecutionError(err.message || 'Verification of reproduction failed.');
        throw err;
      } finally {
        setIsReEvaluating(false);
      }
    },
    [projectId]
  );

  const clearExecutionError = useCallback(() => {
    setExecutionError(null);
  }, []);

  return {
    evaluations,
    latestEvaluation,
    suiteReport,
    retainedEvidence,
    reproductionResult,
    isExecutingCase,
    isExecutingSuite,
    isExecutingDemo,
    isReEvaluating,
    isLoadingEvaluations,
    executionError,
    runnerCapabilities: LOCAL_RUNNER_CAPABILITIES,
    executeCase,
    executeBoundedSuite,
    executeDemonstration,
    fetchEvidence,
    reEvaluate,
    verifyEvaluationReproduction,
    refreshEvaluations: loadEvaluations,
    setLatestEvaluation,
    clearExecutionError,
  };
};
