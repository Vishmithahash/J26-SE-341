import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { c3Api, RECOVERY_VERDICT } from '../api';

export const useC3Evaluations = (projectId, filters = {}) => {
  const [evaluations, setEvaluations] = useState([]);
  const [totalEvaluations, setTotalEvaluations] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isDbUnavailable, setIsDbUnavailable] = useState(false);

  // In-flight compute action state
  const [isComputing, setIsComputing] = useState(false);
  const [computeError, setComputeError] = useState(null);
  const isSubmittingRef = useRef(false);

  const requestSeq = useRef(0);
  const filtersKey = useMemo(() => JSON.stringify(filters), [filters]);

  const fetchEvaluations = useCallback(async () => {
    if (!projectId) {
      setEvaluations([]);
      setTotalEvaluations(0);
      setIsLoading(false);
      setError(null);
      setIsDbUnavailable(false);
      return;
    }

    const currentSeq = ++requestSeq.current;
    setIsLoading(true);
    setError(null);
    setIsDbUnavailable(false);

    const controller = new AbortController();

    try {
      const parsedFilters = JSON.parse(filtersKey || '{}');
      const res = await c3Api.listEvaluations(projectId, parsedFilters, controller.signal);

      if (currentSeq !== requestSeq.current) return;

      const items = res.items || [];
      setEvaluations(items);
      setTotalEvaluations(res.total ?? items.length);
      setIsDbUnavailable(false);
      setError(null);
    } catch (err) {
      if (currentSeq !== requestSeq.current) return;
      if (err.name === 'AbortError') return;

      if (err.status === 503 || (err.message && err.message.includes('503'))) {
        setIsDbUnavailable(true);
        setError('PostgreSQL persistence service unavailable.');
      } else {
        setError(err.message || 'Failed to retrieve recovery evaluations.');
      }
      setEvaluations([]);
      setTotalEvaluations(0);
    } finally {
      if (currentSeq === requestSeq.current) {
        setIsLoading(false);
      }
    }
  }, [projectId, filtersKey]);

  useEffect(() => {
    fetchEvaluations();
  }, [fetchEvaluations]);

  // Compute breakdown of recovery verdicts across retrieved evaluations
  const verdictCounts = useMemo(() => {
    let passCompleted = 0;
    let passGraceful = 0;
    let fail = 0;
    let inconclusive = 0;
    let notEvaluated = 0;

    evaluations.forEach((ev) => {
      const verdict = ev.recovery_verdict;
      if (verdict === RECOVERY_VERDICT.PASS_COMPLETED) {
        passCompleted += 1;
      } else if (verdict === RECOVERY_VERDICT.PASS_GRACEFUL) {
        passGraceful += 1;
      } else if (verdict === RECOVERY_VERDICT.FAIL) {
        fail += 1;
      } else if (verdict === RECOVERY_VERDICT.INCONCLUSIVE) {
        inconclusive += 1;
      } else {
        notEvaluated += 1;
      }
    });

    const eligibleEvaluatedCount = passCompleted + passGraceful + fail + inconclusive;

    return {
      passCompleted,
      passGraceful,
      fail,
      inconclusive,
      notEvaluated,
      eligibleEvaluatedCount,
    };
  }, [evaluations]);

  // Compute and persist an evaluation for a given pair
  const computeAndPersistEvaluation = useCallback(
    async ({ pairId, c2Facts = [] }) => {
      if (!projectId) {
        throw new Error('Project ID is required to compute evaluation.');
      }
      if (!pairId) {
        throw new Error('Pair ID is required to compute evaluation.');
      }
      if (isSubmittingRef.current) {
        throw new Error('Evaluation computation already in flight. Please wait.');
      }

      isSubmittingRef.current = true;
      setIsComputing(true);
      setComputeError(null);

      try {
        const payload = {
          project_id: projectId,
          pair_id: pairId,
          c2_facts: c2Facts,
          evaluator_version: '1.1.0',
          rule_set_version: '1.1.0',
        };

        const res = await c3Api.computeEvaluation(payload);
        // Refresh evaluations list on success
        await fetchEvaluations();
        return res;
      } catch (err) {
        const msg = err.message || 'Evaluation computation failed.';
        setComputeError(msg);
        throw err;
      } finally {
        isSubmittingRef.current = false;
        setIsComputing(false);
      }
    },
    [projectId, fetchEvaluations]
  );

  return {
    evaluations,
    totalEvaluations,
    verdictCounts,
    isLoading,
    error,
    isDbUnavailable,
    refetch: fetchEvaluations,
    isComputing,
    computeError,
    computeAndPersistEvaluation,
  };
};
