import { useState, useEffect, useCallback, useRef } from 'react';
import { c3Api } from '../api.js';

export const useC3Executions = (projectId) => {
  const [executions, setExecutions] = useState([]);
  const [totalExecutions, setTotalExecutions] = useState(null);
  const [latestExecution, setLatestExecution] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isDbUnavailable, setIsDbUnavailable] = useState(false);

  const reqCounterRef = useRef(0);
  const abortControllerRef = useRef(null);

  const fetchExecutions = useCallback(
    async (targetProjectId) => {
      if (!targetProjectId) {
        setExecutions([]);
        setTotalExecutions(null);
        setLatestExecution(null);
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
        const res = await c3Api.listExecutions(
          targetProjectId,
          { limit: 50, offset: 0 },
          controller.signal
        );

        if (thisReq === reqCounterRef.current) {
          const items = res.items || [];
          setExecutions(items);
          setTotalExecutions(res.total ?? items.length);
          setLatestExecution(items.length > 0 ? items[0] : null);
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
            setError('Database service unavailable. Tracked executions could not be queried.');
          } else {
            setError(msg || 'Failed to load tracked executions.');
          }
          setExecutions([]);
          setTotalExecutions(null);
          setLatestExecution(null);
          setIsLoading(false);
        }
      }
    },
    []
  );

  useEffect(() => {
    setExecutions([]);
    setTotalExecutions(null);
    setLatestExecution(null);
    setError(null);
    setIsDbUnavailable(false);

    if (projectId) {
      fetchExecutions(projectId);
    } else {
      setIsLoading(false);
    }

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [projectId, fetchExecutions]);

  const refreshExecutions = () => {
    if (projectId) {
      fetchExecutions(projectId);
    }
  };

  return {
    executions,
    totalExecutions,
    latestExecution,
    isLoading,
    error,
    isDbUnavailable,
    refreshExecutions,
  };
};
