import { useState, useEffect, useCallback, useRef } from 'react';
import { c3Api, EXPOSURE_STATUS, CLEAN_QUALIFICATION } from '../api.js';

export const useC3MatchedPairs = (projectId, filters = {}) => {
  const [pairs, setPairs] = useState([]);
  const [totalPairs, setTotalPairs] = useState(null);
  const [exposureCounts, setExposureCounts] = useState({
    confirmed: 0,
    notTriggered: 0,
    unknown: 0,
    cleanQualified: 0,
    cleanDisqualified: 0,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isDbUnavailable, setIsDbUnavailable] = useState(false);

  const reqCounterRef = useRef(0);
  const abortControllerRef = useRef(null);

  const fetchPairs = useCallback(
    async (targetProjectId, activeFilters = {}) => {
      if (!targetProjectId) {
        setPairs([]);
        setTotalPairs(null);
        setExposureCounts({
          confirmed: 0,
          notTriggered: 0,
          unknown: 0,
          cleanQualified: 0,
          cleanDisqualified: 0,
        });
        setIsLoading(false);
        setError(null);
        setIsDbUnavailable(false);
        return;
      }

      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      const controller = new AbortController();
      abortControllerRef.current = controller;
      const thisReq = ++reqCounterRef.current;

      setIsLoading(true);
      setError(null);
      setIsDbUnavailable(false);

      try {
        const res = await c3Api.listPairs(
          targetProjectId,
          { limit: 50, offset: 0, ...activeFilters },
          controller.signal
        );

        if (thisReq === reqCounterRef.current) {
          const items = res.items || [];
          setPairs(items);
          setTotalPairs(res.total ?? items.length);

          let confirmed = 0;
          let notTriggered = 0;
          let unknown = 0;
          let cleanQualified = 0;
          let cleanDisqualified = 0;

          for (const p of items) {
            const exp = p.exposure_status || p.evidence?.exposure_status;
            if (exp === EXPOSURE_STATUS.CONFIRMED) confirmed++;
            else if (exp === EXPOSURE_STATUS.NOT_TRIGGERED) notTriggered++;
            else unknown++;

            const clean = p.clean_qualification || p.evidence?.clean_qualification;
            if (clean === CLEAN_QUALIFICATION.QUALIFIED) cleanQualified++;
            else if (clean === CLEAN_QUALIFICATION.DISQUALIFIED) cleanDisqualified++;
          }

          setExposureCounts({
            confirmed,
            notTriggered,
            unknown,
            cleanQualified,
            cleanDisqualified,
          });
          setIsLoading(false);
        }
      } catch (err) {
        if (thisReq === reqCounterRef.current) {
          if (err.name === 'AbortError') return;

          const msg = err.message || '';
          if (
            err.status === 503 ||
            msg.toLowerCase().includes('database') ||
            msg.toLowerCase().includes('unavailable')
          ) {
            setIsDbUnavailable(true);
            setError('Database service unavailable. Matched pairs could not be queried.');
          } else {
            setError(msg || 'Failed to load matched trial pairs.');
          }
          setPairs([]);
          setTotalPairs(null);
          setIsLoading(false);
        }
      }
    },
    []
  );

  const filtersKey = JSON.stringify(filters);

  useEffect(() => {
    setPairs([]);
    setTotalPairs(null);
    setError(null);
    setIsDbUnavailable(false);

    if (projectId) {
      const parsedFilters = filtersKey ? JSON.parse(filtersKey) : {};
      fetchPairs(projectId, parsedFilters);
    } else {
      setIsLoading(false);
    }

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [projectId, filtersKey, fetchPairs]);

  const refreshPairs = () => {
    if (projectId) {
      fetchPairs(projectId, filters);
    }
  };

  return {
    pairs,
    totalPairs,
    exposureCounts,
    isLoading,
    error,
    isDbUnavailable,
    refreshPairs,
  };
};
