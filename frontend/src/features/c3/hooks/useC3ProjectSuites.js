import { useState, useEffect, useCallback, useRef } from 'react';
import { c3Api } from '../api.js';

export const useC3ProjectSuites = (projectId) => {
  const [suites, setSuites] = useState([]);
  const [totalSuites, setTotalSuites] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isDbUnavailable, setIsDbUnavailable] = useState(false);

  // Generation counter to discard stale async responses from earlier project selections
  const reqCounterRef = useRef(0);
  const abortControllerRef = useRef(null);

  const fetchSuites = useCallback(
    async (targetProjectId) => {
      if (!targetProjectId) {
        setSuites([]);
        setTotalSuites(null);
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
        const res = await c3Api.listSuites(
          targetProjectId,
          { limit: 50, offset: 0 },
          controller.signal
        );

        if (thisReq === reqCounterRef.current) {
          setSuites(res.items || []);
          setTotalSuites(res.total ?? (res.items ? res.items.length : 0));
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
            setError('Database service unavailable. Stored suites could not be queried.');
          } else {
            setError(msg || 'Failed to load project test suites.');
          }
          setSuites([]);
          setTotalSuites(null);
          setIsLoading(false);
        }
      }
    },
    []
  );

  useEffect(() => {
    // Clear previous project data immediately when project ID changes
    setSuites([]);
    setTotalSuites(null);
    setError(null);
    setIsDbUnavailable(false);

    if (projectId) {
      fetchSuites(projectId);
    } else {
      setIsLoading(false);
    }

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [projectId, fetchSuites]);

  const refresh = () => {
    if (projectId) {
      fetchSuites(projectId);
    }
  };

  return {
    suites,
    totalSuites,
    isLoading,
    error,
    isDbUnavailable,
    refresh,
  };
};
