import { useState, useEffect, useRef, useCallback } from 'react';
import { c2Api } from '../api/c2Api.js';

/**
 * Custom hook managing C2 Results, Evidence, Observed Coverage,
 * Report contributions, and Replay Reproduction verification.
 */
export const useC2Results = (projectId, userId) => {
  const [evaluations, setEvaluations] = useState([]);
  const [selectedEvaluation, setSelectedEvaluation] = useState(null);
  const [retainedEvidence, setRetainedEvidence] = useState(null);
  const [observedCoverage, setObservedCoverage] = useState(null);
  const [suiteCoverage, setSuiteCoverage] = useState(null);
  const [runReport, setRunReport] = useState(null);
  const [suiteReport, setSuiteReport] = useState(null);
  const [exportStatus, setExportStatus] = useState(null);
  const [exportError, setExportError] = useState(null);
  const [lastConfirmedReceipt, setLastConfirmedReceipt] = useState(null);
  const [reproductionResult, setReproductionResult] = useState(null);

  // Filters
  const [suiteFilter, setSuiteFilter] = useState('');
  const [testFilter, setTestFilter] = useState('');
  const [verdictFilter, setVerdictFilter] = useState('');
  const [originFilter, setOriginFilter] = useState(''); // 'live_agent_run' | 'scripted_synthetic_demonstration' | 'controlled_trace_fixture'
  const [modelVersionFilter, setModelVersionFilter] = useState('');

  // Loading states
  const [isLoadingEvaluations, setIsLoadingEvaluations] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isLoadingEvidence, setIsLoadingEvidence] = useState(false);
  const [isLoadingCoverage, setIsLoadingCoverage] = useState(false);
  const [isLoadingReport, setIsLoadingReport] = useState(false);
  const [isExportingReport, setIsExportingReport] = useState(false);
  const [isReEvaluating, setIsReEvaluating] = useState(false);

  // Errors
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);

  // Stale-response protection and evaluation receipt scoping
  const generationRef = useRef(0);
  const inFlightRef = useRef(false);
  const selectedEvalIdRef = useRef(null);
  const receiptsByEvalRef = useRef({});

  /**
   * Load all evaluation records for the active project
   */
  const loadEvaluations = useCallback(async () => {
    if (!projectId) return;
    const currentGen = ++generationRef.current;
    setIsLoadingEvaluations(true);
    setError(null);

    try {
      const filters = {};
      if (suiteFilter) filters.suiteId = suiteFilter;
      if (testFilter) filters.testId = testFilter;
      if (verdictFilter) filters.verdict = verdictFilter;

      const data = await c2Api.listEvaluations(projectId, filters);
      if (currentGen !== generationRef.current) return;

      // Filter by origin and model version if selected
      let filtered = data || [];
      if (originFilter) {
        filtered = filtered.filter((ev) => {
          const origin = ev.collector_provenance?.actual_execution_origin ||
            (ev.is_live_execution ? 'live_agent_run' : 'scripted_synthetic_demonstration');
          return origin === originFilter;
        });
      }
      if (modelVersionFilter) {
        filtered = filtered.filter((ev) => ev.model_version === modelVersionFilter);
      }

      setEvaluations(filtered);

      // Auto-select first evaluation if none selected
      setSelectedEvaluation((prev) => {
        if (!prev) {
          const first = filtered[0] || null;
          selectedEvalIdRef.current = first?.evaluation_id || null;
          return first;
        }
        const matching = filtered.find((e) => e.evaluation_id === prev.evaluation_id);
        const next = matching || filtered[0] || null;
        selectedEvalIdRef.current = next?.evaluation_id || null;
        return next;
      });
    } catch (err) {
      if (currentGen !== generationRef.current) return;
      setError(err.message || 'Failed to load evaluation results.');
      setEvaluations([]);
    } finally {
      if (currentGen === generationRef.current) {
        setIsLoadingEvaluations(false);
      }
    }
  }, [projectId, suiteFilter, testFilter, verdictFilter, originFilter, modelVersionFilter]);

  // Reset when project or user changes
  useEffect(() => {
    generationRef.current += 1;
    selectedEvalIdRef.current = null;
    receiptsByEvalRef.current = {};
    setEvaluations([]);
    setSelectedEvaluation(null);
    setRetainedEvidence(null);
    setObservedCoverage(null);
    setSuiteCoverage(null);
    setRunReport(null);
    setSuiteReport(null);
    setExportStatus(null);
    setExportError(null);
    setLastConfirmedReceipt(null);
    setReproductionResult(null);
    setError(null);
    setActionError(null);

    if (projectId && userId) {
      loadEvaluations();
    }
  }, [projectId, userId, loadEvaluations]);

  /**
   * Select an evaluation and load its evidence, coverage, and report
   */
  const selectEvaluation = useCallback(
    async (evaluation) => {
      const evaluationId = evaluation?.evaluation_id || null;
      selectedEvalIdRef.current = evaluationId;

      setSelectedEvaluation(evaluation);
      setRetainedEvidence(null);
      setObservedCoverage(null);
      setRunReport(null);
      setExportStatus(null);
      setExportError(null);
      setReproductionResult(null);

      // Preserve confirmed receipt only if scoped to this exact evaluation
      const existingReceipt = evaluationId ? receiptsByEvalRef.current[evaluationId] || null : null;
      setLastConfirmedReceipt(existingReceipt);

      if (!evaluation || !projectId) return;

      const currentGen = ++generationRef.current;
      setIsLoadingDetail(true);
      const runId = evaluation.run_id;

      // 1. Fetch Retained Evidence (if runId available)
      if (runId) {
        setIsLoadingEvidence(true);
        c2Api
          .getRetainedEvidence(projectId, runId)
          .then((data) => {
            if (currentGen !== generationRef.current) return;
            // The API nests the evidence packet under evidence_payload next to retention metadata.
            setRetainedEvidence(data?.evidence_payload ? { ...data, ...data.evidence_payload } : data);
          })
          .catch(() => {
            if (currentGen !== generationRef.current) return;
            setRetainedEvidence(null);
          })
          .finally(() => {
            if (currentGen === generationRef.current) {
              setIsLoadingEvidence(false);
            }
          });
      }

      // 2. Fetch Detailed Observed Coverage
      if (evaluationId) {
        setIsLoadingCoverage(true);
        c2Api
          .getEvaluationCoverage(projectId, evaluationId)
          .then((data) => {
            if (currentGen !== generationRef.current) return;
            setObservedCoverage(data);
          })
          .catch(() => {
            if (currentGen !== generationRef.current) return;
            // Fall back to coverage already embedded in evaluation record if available
            setObservedCoverage(evaluation.detailed_coverage || null);
          })
          .finally(() => {
            if (currentGen === generationRef.current) {
              setIsLoadingCoverage(false);
            }
          });

        // 3. Fetch Run Report Contribution
        setIsLoadingReport(true);
        c2Api
          .getRunReport(projectId, evaluationId)
          .then((data) => {
            if (currentGen !== generationRef.current) return;
            setRunReport(data);
          })
          .catch(() => {
            if (currentGen !== generationRef.current) return;
            setRunReport(null);
          })
          .finally(() => {
            if (currentGen === generationRef.current) {
              setIsLoadingReport(false);
              setIsLoadingDetail(false);
            }
          });
      }
    },
    [projectId]
  );

  /**
   * Fetch aggregate suite coverage
   */
  const fetchSuiteCoverage = useCallback(
    async (suiteId) => {
      if (!projectId || !suiteId) return null;
      try {
        const data = await c2Api.getSuiteCoverage(projectId, suiteId);
        setSuiteCoverage(data);
        return data;
      } catch {
        setSuiteCoverage(null);
        return null;
      }
    },
    [projectId]
  );

  /**
   * Fetch aggregate suite report
   */
  const fetchSuiteReport = useCallback(
    async (suiteId) => {
      if (!projectId || !suiteId) return null;
      try {
        const data = await c2Api.getSuiteReport(projectId, suiteId);
        setSuiteReport(data);
        return data;
      } catch {
        setSuiteReport(null);
        return null;
      }
    },
    [projectId]
  );

  /**
   * Export C2 report contribution JSON and check publishing status
   */
  const exportReport = useCallback(
    async (evaluationId) => {
      if (!projectId || !evaluationId) return;
      if (inFlightRef.current) return;
      inFlightRef.current = true;
      setIsExportingReport(true);
      const targetEvalId = evaluationId;

      if (selectedEvalIdRef.current === targetEvalId) {
        setExportError(null);
        setActionError(null);
      }

      try {
        const result = await c2Api.exportC2ReportContribution(projectId, targetEvalId);
        if (result?.published_to_shared_aggregator) {
          receiptsByEvalRef.current[targetEvalId] = result;
        }

        // Only update visible status if user has not switched to another evaluation
        if (selectedEvalIdRef.current === targetEvalId) {
          setExportStatus(result);
          if (result?.published_to_shared_aggregator) {
            setLastConfirmedReceipt(result);
          }
        }
        return result;
      } catch (err) {
        const isConflict = err.status === 409 || String(err.message || '').includes('409') || String(err.message || '').toLowerCase().includes('conflict');
        const errDetail = {
          status: err.status || (isConflict ? 409 : 500),
          isConflict,
          message: isConflict
            ? 'Publication conflict: an export contribution already exists for this execution in the shared integration service.'
            : (err.message || 'Failed to export C2 report contribution.'),
        };
        if (selectedEvalIdRef.current === targetEvalId) {
          setExportError(errDetail);
          setActionError(errDetail.message);
        }
        throw err;
      } finally {
        inFlightRef.current = false;
        setIsExportingReport(false);
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
      if (inFlightRef.current) return;
      inFlightRef.current = true;
      setIsReEvaluating(true);
      setActionError(null);

      try {
        const result = await c2Api.reEvaluateExecution(projectId, evaluationId, options);
        setSelectedEvaluation(result);
        setEvaluations((prev) => [
          result,
          ...prev.filter((e) => e.evaluation_id !== result.evaluation_id),
        ]);
        return result;
      } catch (err) {
        setActionError(err.message || 'Re-evaluation failed.');
        throw err;
      } finally {
        inFlightRef.current = false;
        setIsReEvaluating(false);
      }
    },
    [projectId]
  );

  /**
   * Verify independent replay reproduction
   */
  const verifyReproduction = useCallback(
    async (evaluationId) => {
      if (!projectId || !evaluationId) return;
      if (inFlightRef.current) return;
      inFlightRef.current = true;
      setIsReEvaluating(true);
      setActionError(null);

      try {
        const result = await c2Api.verifyReproduction(projectId, evaluationId);
        setReproductionResult(result);
        return result;
      } catch (err) {
        setActionError(err.message || 'Independent replay reproduction failed.');
        throw err;
      } finally {
        inFlightRef.current = false;
        setIsReEvaluating(false);
      }
    },
    [projectId]
  );

  const clearActionError = useCallback(() => {
    setActionError(null);
  }, []);

  return {
    evaluations,
    selectedEvaluation,
    retainedEvidence,
    observedCoverage,
    suiteCoverage,
    runReport,
    suiteReport,
    exportStatus,
    exportError,
    lastConfirmedReceipt,
    reproductionResult,
    suiteFilter,
    testFilter,
    verdictFilter,
    originFilter,
    modelVersionFilter,
    isLoadingEvaluations,
    isLoadingDetail,
    isLoadingEvidence,
    isLoadingCoverage,
    isLoadingReport,
    isExportingReport,
    isReEvaluating,
    error,
    actionError,
    setSuiteFilter,
    setTestFilter,
    setVerdictFilter,
    setOriginFilter,
    setModelVersionFilter,
    selectEvaluation,
    fetchSuiteCoverage,
    fetchSuiteReport,
    exportReport,
    reEvaluate,
    verifyReproduction,
    refreshEvaluations: loadEvaluations,
    clearActionError,
  };
};
