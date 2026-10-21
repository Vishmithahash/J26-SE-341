import { useState, useEffect, useRef, useCallback } from 'react';
import { c2Api } from '../api/c2Api.js';

/**
 * Custom hook managing C2 Test Suites, Case listing with category/readiness filters,
 * detailed case inspection, generation diagnostics, and stale response protection.
 */
export const useC2Suites = (projectId, userId) => {
  const [suites, setSuites] = useState([]);
  const [selectedSuiteSummary, setSelectedSuiteSummary] = useState(null);
  const [selectedSuiteDetail, setSelectedSuiteDetail] = useState(null);
  const [suiteReadiness, setSuiteReadiness] = useState(null);

  // Cases inside selected suite
  const [cases, setCases] = useState([]);
  const [selectedCaseSummary, setSelectedCaseSummary] = useState(null);
  const [selectedCaseDetail, setSelectedCaseDetail] = useState(null);

  // Filters
  const [categoryFilter, setCategoryFilter] = useState('');
  const [readinessFilter, setReadinessFilter] = useState('');

  // Loading states
  const [isLoadingSuites, setIsLoadingSuites] = useState(false);
  const [isLoadingSuiteDetail, setIsLoadingSuiteDetail] = useState(false);
  const [isLoadingCases, setIsLoadingCases] = useState(false);
  const [isLoadingCaseDetail, setIsLoadingCaseDetail] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  // Errors
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);

  // Generation counter to protect against stale asynchronous responses
  const generationRef = useRef(0);

  /**
   * Load all test suites for the active project
   */
  const loadSuites = useCallback(async () => {
    if (!projectId) return;
    const currentGen = ++generationRef.current;
    setIsLoadingSuites(true);
    setError(null);

    try {
      const data = await c2Api.listTestSuites(projectId);
      if (currentGen !== generationRef.current) return;
      setSuites(data || []);

      setSelectedSuiteSummary((prev) => {
        if (!prev) return data?.[0] || null;
        const matching = data.find((s) => s.suite_id === prev.suite_id);
        return matching || data?.[0] || null;
      });
    } catch (err) {
      if (currentGen !== generationRef.current) return;
      setError(err.message || 'Failed to load test suites.');
      setSuites([]);
    } finally {
      if (currentGen === generationRef.current) {
        setIsLoadingSuites(false);
      }
    }
  }, [projectId]);

  // Reset all state when projectId or userId changes
  useEffect(() => {
    generationRef.current += 1;
    setSuites([]);
    setSelectedSuiteSummary(null);
    setSelectedSuiteDetail(null);
    setSuiteReadiness(null);
    setCases([]);
    setSelectedCaseSummary(null);
    setSelectedCaseDetail(null);
    setCategoryFilter('');
    setReadinessFilter('');
    setError(null);
    setActionError(null);

    if (projectId && userId) {
      loadSuites();
    }
  }, [projectId, userId, loadSuites]);

  /**
   * Load details and readiness for the selected suite
   */
  useEffect(() => {
    if (!projectId || !selectedSuiteSummary?.suite_id) {
      setSelectedSuiteDetail(null);
      setSuiteReadiness(null);
      return;
    }

    const currentGen = ++generationRef.current;
    const suiteId = selectedSuiteSummary.suite_id;
    setIsLoadingSuiteDetail(true);

    Promise.allSettled([
      c2Api.getTestSuite(projectId, suiteId),
      c2Api.getSuiteReadiness(projectId, suiteId),
    ]).then(([detailResult, readinessResult]) => {
      if (currentGen !== generationRef.current) return;

      if (detailResult.status === 'fulfilled') {
        setSelectedSuiteDetail(detailResult.value);
      } else {
        setSelectedSuiteDetail(null);
      }

      if (readinessResult.status === 'fulfilled') {
        setSuiteReadiness(readinessResult.value);
      } else {
        setSuiteReadiness(null);
      }

      setIsLoadingSuiteDetail(false);
    });
  }, [projectId, selectedSuiteSummary?.suite_id]);

  /**
   * Load cases for selected suite whenever suite or filters change
   */
  useEffect(() => {
    if (!projectId || !selectedSuiteSummary?.suite_id) {
      setCases([]);
      setSelectedCaseSummary(null);
      return;
    }

    const currentGen = ++generationRef.current;
    const suiteId = selectedSuiteSummary.suite_id;
    setIsLoadingCases(true);

    c2Api
      .listTestCases(projectId, suiteId, {
        category: categoryFilter || undefined,
        readiness: readinessFilter || undefined,
      })
      .then((data) => {
        if (currentGen !== generationRef.current) return;
        setCases(data || []);

        setSelectedCaseSummary((prev) => {
          if (!prev) return data?.[0] || null;
          const matching = data.find((c) => c.test_id === prev.test_id);
          return matching || data?.[0] || null;
        });
      })
      .catch((err) => {
        if (currentGen !== generationRef.current) return;
        setActionError(err.message || 'Failed to load test cases.');
        setCases([]);
      })
      .finally(() => {
        if (currentGen === generationRef.current) {
          setIsLoadingCases(false);
        }
      });
  }, [projectId, selectedSuiteSummary?.suite_id, categoryFilter, readinessFilter]);

  /**
   * Load detail for selected test case
   */
  useEffect(() => {
    if (!projectId || !selectedSuiteSummary?.suite_id || !selectedCaseSummary?.test_id) {
      setSelectedCaseDetail(null);
      return;
    }

    const currentGen = ++generationRef.current;
    const suiteId = selectedSuiteSummary.suite_id;
    const testId = selectedCaseSummary.test_id;
    setIsLoadingCaseDetail(true);

    c2Api
      .getTestCaseDetail(projectId, suiteId, testId)
      .then((data) => {
        if (currentGen !== generationRef.current) return;
        setSelectedCaseDetail(data);
      })
      .catch((err) => {
        if (currentGen !== generationRef.current) return;
        setActionError(err.message || 'Failed to load test case definition.');
        setSelectedCaseDetail(null);
      })
      .finally(() => {
        if (currentGen === generationRef.current) {
          setIsLoadingCaseDetail(false);
        }
      });
  }, [projectId, selectedSuiteSummary?.suite_id, selectedCaseSummary?.test_id]);

  /**
   * Generate automatic test suite for an approved model
   */
  const generateSuite = useCallback(
    async (requestPayload) => {
      if (!projectId) throw new Error('No active project selected.');
      setIsGenerating(true);
      setActionError(null);

      try {
        const createdSuite = await c2Api.generateTestSuite(projectId, requestPayload);
        // Refresh suite list and select newly generated suite
        const updatedList = await c2Api.listTestSuites(projectId);
        setSuites(updatedList || []);
        const matching = updatedList?.find((s) => s.suite_id === createdSuite.suite_id);
        setSelectedSuiteSummary(matching || createdSuite);
        return createdSuite;
      } catch (err) {
        setActionError(err.message || 'Automatic test suite generation failed.');
        throw err;
      } finally {
        setIsGenerating(false);
      }
    },
    [projectId]
  );

  const clearActionError = useCallback(() => {
    setActionError(null);
  }, []);

  return {
    suites,
    selectedSuiteSummary,
    selectedSuiteDetail,
    suiteReadiness,
    cases,
    selectedCaseSummary,
    selectedCaseDetail,
    categoryFilter,
    readinessFilter,
    isLoadingSuites,
    isLoadingSuiteDetail,
    isLoadingCases,
    isLoadingCaseDetail,
    isGenerating,
    error,
    actionError,
    setSelectedSuiteSummary,
    setSelectedCaseSummary,
    setCategoryFilter,
    setReadinessFilter,
    generateSuite,
    refreshSuites: loadSuites,
    clearActionError,
  };
};
