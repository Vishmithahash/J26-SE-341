import { useState, useEffect, useRef, useCallback } from 'react';
import { c2Api } from '../api/c2Api.js';

/**
 * Custom hook managing C2 Dashboard summaries.
 *
 * Responsibilities:
 * 1. Fetches models, test suites, and evaluations independently for the active project.
 * 2. Distinguishes unique models, total versions, and approved versions.
 * 3. Extracts the latest evaluation, verdict, provenance, and timestamp.
 * 4. Ensures failures display as 'Unavailable' rather than 0.
 * 5. Handles partial availability so one failed endpoint does not erase successful ones.
 * 6. Guards against stale responses across project switches and unmounts.
 * 7. Never issues network requests when no project is selected.
 */
export const useC2Dashboard = (projectId, userId) => {
  const [data, setData] = useState({
    modelsCount: null,
    uniqueModelsCount: null,
    approvedModelsCount: null,
    suitesCount: null,
    latestEvaluation: null,
  });

  const [errors, setErrors] = useState({
    modelsError: null,
    suitesError: null,
    evaluationsError: null,
  });

  const [isLoading, setIsLoading] = useState(false);

  const generationRef = useRef(0);
  const inFlightRef = useRef(false);

  const fetchSummary = useCallback(async () => {
    if (!projectId) {
      setData({
        modelsCount: null,
        uniqueModelsCount: null,
        approvedModelsCount: null,
        suitesCount: null,
        latestEvaluation: null,
      });
      setErrors({
        modelsError: null,
        suitesError: null,
        evaluationsError: null,
      });
      setIsLoading(false);
      return;
    }

    const currentGen = ++generationRef.current;
    inFlightRef.current = true;
    setIsLoading(true);

    // Reset previous errors before fresh read
    setErrors({
      modelsError: null,
      suitesError: null,
      evaluationsError: null,
    });

    try {
      // Execute all three reads independently with Promise.allSettled
      const [modelsResult, suitesResult, evaluationsResult] = await Promise.allSettled([
        c2Api.listModels(projectId),
        c2Api.listTestSuites(projectId),
        c2Api.listEvaluations(projectId),
      ]);

      if (currentGen !== generationRef.current) return;

      let nextModelsCount = null;
      let nextUniqueModelsCount = null;
      let nextApprovedModelsCount = null;
      let nextModelsError = null;

      if (modelsResult.status === 'fulfilled') {
        const rawModels = modelsResult.value;
        const modelsList = Array.isArray(rawModels)
          ? rawModels
          : Array.isArray(rawModels?.items)
          ? rawModels.items
          : [];
        nextModelsCount = modelsList.length;
        nextUniqueModelsCount = new Set(modelsList.map((m) => m.model_id)).size;
        nextApprovedModelsCount = modelsList.filter((m) => m.lifecycle_status === 'APPROVED').length;
      } else {
        nextModelsError = modelsResult.reason?.message || 'Failed to load models';
      }

      let nextSuitesCount = null;
      let nextSuitesError = null;

      if (suitesResult.status === 'fulfilled') {
        const rawSuites = suitesResult.value;
        const suitesList = Array.isArray(rawSuites)
          ? rawSuites
          : Array.isArray(rawSuites?.items)
          ? rawSuites.items
          : [];
        nextSuitesCount = suitesList.length;
      } else {
        nextSuitesError = suitesResult.reason?.message || 'Failed to load test suites';
      }

      let nextLatestEvaluation = null;
      let nextEvaluationsError = null;

      if (evaluationsResult.status === 'fulfilled') {
        const rawEvaluations = evaluationsResult.value;
        const evaluationsList = Array.isArray(rawEvaluations)
          ? rawEvaluations
          : Array.isArray(rawEvaluations?.items)
          ? rawEvaluations.items
          : [];

        if (evaluationsList.length > 0) {
          // Sort chronologically descending to get the latest evaluation
          const sorted = [...evaluationsList].sort((a, b) => {
            const timeA = new Date(a.evaluated_at || a.created_at || 0).getTime();
            const timeB = new Date(b.evaluated_at || b.created_at || 0).getTime();
            return timeB - timeA;
          });
          nextLatestEvaluation = sorted[0];
        }
      } else {
        nextEvaluationsError = evaluationsResult.reason?.message || 'Failed to load evaluations';
      }

      setData({
        modelsCount: nextModelsCount,
        uniqueModelsCount: nextUniqueModelsCount,
        approvedModelsCount: nextApprovedModelsCount,
        suitesCount: nextSuitesCount,
        latestEvaluation: nextLatestEvaluation,
      });

      setErrors({
        modelsError: nextModelsError,
        suitesError: nextSuitesError,
        evaluationsError: nextEvaluationsError,
      });
    } catch {
      // Unhandled outer failure
      if (currentGen !== generationRef.current) return;
    } finally {
      if (currentGen === generationRef.current) {
        setIsLoading(false);
        inFlightRef.current = false;
      }
    }
  }, [projectId]);

  useEffect(() => {
    // Clear data immediately when project changes
    setData({
      modelsCount: null,
      uniqueModelsCount: null,
      approvedModelsCount: null,
      suitesCount: null,
      latestEvaluation: null,
    });
    setErrors({
      modelsError: null,
      suitesError: null,
      evaluationsError: null,
    });

    if (projectId) {
      fetchSummary();
    } else {
      setIsLoading(false);
    }

    const gen = generationRef;
    const inFlight = inFlightRef;
    return () => {
      // Invalidate current generation on unmount or dependency change
      gen.current++;
      inFlight.current = false;
    };
  }, [projectId, userId, fetchSummary]);

  return {
    ...data,
    ...errors,
    isLoading,
    refresh: fetchSummary,
    hasPartialErrors: Boolean(errors.modelsError || errors.suitesError || errors.evaluationsError),
  };
};
