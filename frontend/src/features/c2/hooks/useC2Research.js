import { useState, useEffect, useRef, useCallback } from 'react';
import { c2Api } from '../api/c2Api.js';

/**
 * Custom hook managing C2 Research Datasets, Partitions (DEVELOPMENT vs HELD_OUT),
 * Baseline Comparisons (B1-B4), and Empirical Benchmark Reports.
 */
export const useC2Research = (projectId, userId) => {
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetSummary, setSelectedDatasetSummary] = useState(null);
  const [selectedDatasetManifest, setSelectedDatasetManifest] = useState(null);

  const [experiments, setExperiments] = useState([]);
  const [selectedExperimentSummary, setSelectedExperimentSummary] = useState(null);
  const [baselineMetrics, setBaselineMetrics] = useState(null);
  const [casePredictions, setCasePredictions] = useState([]);

  // Partition filter for dataset cases or metrics: 'ALL_CASES' | 'DEVELOPMENT' | 'HELD_OUT'
  const [partitionFilter, setPartitionFilter] = useState('ALL_CASES');
  const [methodFilter, setMethodFilter] = useState(''); // e.g. 'B4_FULL_C2'

  // Loading states
  const [isLoadingDatasets, setIsLoadingDatasets] = useState(false);
  const [isLoadingManifest, setIsLoadingManifest] = useState(false);
  const [isLoadingExperiments, setIsLoadingExperiments] = useState(false);
  const [isLoadingBaselines, setIsLoadingBaselines] = useState(false);
  const [isLoadingCases, setIsLoadingCases] = useState(false);
  const [isExecutingExperiment, setIsExecutingExperiment] = useState(false);
  const [isFreezingDataset, setIsFreezingDataset] = useState(false);

  // Errors
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);

  const generationRef = useRef(0);
  const inFlightRef = useRef(false);

  /**
   * Load datasets for project
   */
  const loadDatasets = useCallback(async () => {
    if (!projectId) return;
    const currentGen = ++generationRef.current;
    setIsLoadingDatasets(true);
    setError(null);

    try {
      const data = await c2Api.listExperimentDatasets(projectId);
      if (currentGen !== generationRef.current) return;
      setDatasets(data || []);

      setSelectedDatasetSummary((prev) => {
        if (!prev) return data?.[0] || null;
        const matching = data.find((d) => d.dataset_id === prev.dataset_id && d.version === prev.version);
        return matching || data?.[0] || null;
      });
    } catch (err) {
      if (currentGen !== generationRef.current) return;
      setError(err.message || 'Failed to load research datasets.');
      setDatasets([]);
    } finally {
      if (currentGen === generationRef.current) {
        setIsLoadingDatasets(false);
      }
    }
  }, [projectId]);

  /**
   * Load experiments for project
   */
  const loadExperiments = useCallback(async () => {
    if (!projectId) return;
    const currentGen = ++generationRef.current;
    setIsLoadingExperiments(true);

    try {
      const data = await c2Api.listExperiments(projectId);
      if (currentGen !== generationRef.current) return;
      setExperiments(data || []);

      setSelectedExperimentSummary((prev) => {
        if (!prev) return data?.[0] || null;
        const matching = data.find((e) => e.experiment_id === prev.experiment_id);
        return matching || data?.[0] || null;
      });
    } catch {
      if (currentGen !== generationRef.current) return;
      setExperiments([]);
    } finally {
      if (currentGen === generationRef.current) {
        setIsLoadingExperiments(false);
      }
    }
  }, [projectId]);

  // Reset when project or user changes
  useEffect(() => {
    generationRef.current += 1;
    setDatasets([]);
    setSelectedDatasetSummary(null);
    setSelectedDatasetManifest(null);
    setExperiments([]);
    setSelectedExperimentSummary(null);
    setBaselineMetrics(null);
    setCasePredictions([]);
    setError(null);
    setActionError(null);

    if (projectId && userId) {
      loadDatasets();
      loadExperiments();
    }
  }, [projectId, userId, loadDatasets, loadExperiments]);

  /**
   * Load manifest when selected dataset changes
   */
  useEffect(() => {
    if (!projectId || !selectedDatasetSummary?.dataset_id || !selectedDatasetSummary?.version) {
      setSelectedDatasetManifest(null);
      return;
    }

    const currentGen = ++generationRef.current;
    setIsLoadingManifest(true);

    c2Api
      .getExperimentDataset(projectId, selectedDatasetSummary.dataset_id, selectedDatasetSummary.version)
      .then((data) => {
        if (currentGen !== generationRef.current) return;
        setSelectedDatasetManifest(data);
      })
      .catch((err) => {
        if (currentGen !== generationRef.current) return;
        setActionError(err.message || 'Failed to load dataset manifest.');
        setSelectedDatasetManifest(null);
      })
      .finally(() => {
        if (currentGen === generationRef.current) {
          setIsLoadingManifest(false);
        }
      });
  }, [projectId, selectedDatasetSummary?.dataset_id, selectedDatasetSummary?.version]);

  /**
   * Load baseline comparisons and case predictions when experiment changes
   */
  useEffect(() => {
    if (!projectId || !selectedExperimentSummary?.experiment_id) {
      setBaselineMetrics(null);
      setCasePredictions([]);
      return;
    }

    const currentGen = ++generationRef.current;
    const expId = selectedExperimentSummary.experiment_id;
    setIsLoadingBaselines(true);
    setIsLoadingCases(true);

    Promise.allSettled([
      c2Api.getExperimentBaselines(projectId, expId),
      c2Api.getExperimentCaseResults(projectId, expId, methodFilter || undefined),
    ]).then(([baselinesResult, casesResult]) => {
      if (currentGen !== generationRef.current) return;

      if (baselinesResult.status === 'fulfilled') {
        setBaselineMetrics(baselinesResult.value);
      } else {
        setBaselineMetrics(null);
      }

      if (casesResult.status === 'fulfilled') {
        setCasePredictions(casesResult.value || []);
      } else {
        setCasePredictions([]);
      }

      setIsLoadingBaselines(false);
      setIsLoadingCases(false);
    });
  }, [projectId, selectedExperimentSummary?.experiment_id, methodFilter]);

  /**
   * Freeze dataset manifest
   */
  const freezeDataset = useCallback(
    async (datasetId, version) => {
      if (!projectId || !datasetId || !version) return;
      setIsFreezingDataset(true);
      setActionError(null);

      try {
        const result = await c2Api.freezeExperimentDataset(projectId, datasetId, version);
        await loadDatasets();
        return result;
      } catch (err) {
        setActionError(err.message || 'Failed to freeze dataset manifest.');
        throw err;
      } finally {
        setIsFreezingDataset(false);
      }
    },
    [projectId, loadDatasets]
  );

  /**
   * Create and run comparative experiment
   */
  const runComparativeExperiment = useCallback(
    async (requestData) => {
      if (!projectId) return;
      if (inFlightRef.current) return;
      inFlightRef.current = true;
      setIsExecutingExperiment(true);
      setActionError(null);

      try {
        const result = await c2Api.createAndRunExperiment(projectId, requestData);
        await loadExperiments();
        const matching = experiments.find((e) => e.experiment_id === result.experiment_id);
        setSelectedExperimentSummary(matching || { experiment_id: result.experiment_id, name: result.name });
        return result;
      } catch (err) {
        setActionError(err.message || 'Comparative baseline experiment failed.');
        throw err;
      } finally {
        inFlightRef.current = false;
        setIsExecutingExperiment(false);
      }
    },
    [projectId, loadExperiments, experiments]
  );

  /**
   * Export metrics in CSV or JSON
   */
  const exportMetrics = useCallback(
    async (experimentId, format = 'json') => {
      if (!projectId || !experimentId) return;
      try {
        const data = await c2Api.exportExperimentMetrics(projectId, experimentId, format);
        const mime = format === 'csv' ? 'text/csv' : 'application/json';
        const content = format === 'csv' ? data : JSON.stringify(data, null, 2);
        const blob = new Blob([content], { type: mime });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `c2_benchmark_${experimentId}.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } catch (err) {
        setActionError(err.message || 'Failed to export experiment metrics.');
      }
    },
    [projectId]
  );

  const clearActionError = useCallback(() => {
    setActionError(null);
  }, []);

  return {
    datasets,
    selectedDatasetSummary,
    selectedDatasetManifest,
    experiments,
    selectedExperimentSummary,
    baselineMetrics,
    casePredictions,
    partitionFilter,
    methodFilter,
    isLoadingDatasets,
    isLoadingManifest,
    isLoadingExperiments,
    isLoadingBaselines,
    isLoadingCases,
    isExecutingExperiment,
    isFreezingDataset,
    error,
    actionError,
    setSelectedDatasetSummary,
    setSelectedExperimentSummary,
    setPartitionFilter,
    setMethodFilter,
    freezeDataset,
    runComparativeExperiment,
    exportMetrics,
    refreshDatasets: loadDatasets,
    refreshExperiments: loadExperiments,
    clearActionError,
  };
};
