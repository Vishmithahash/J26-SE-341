/**
 * Component 4 (C4) - Research Evaluation Hook
 * Connects versioned evaluation datasets, split assignments, independent review packets,
 * inter-rater agreement (Cohen's Kappa), baseline strategies, ablations, and reproducible experiments.
 */

import { useState, useCallback } from 'react';
import { c4Api } from '../api/c4Api.js';
import {
  RESEARCH_STRATEGIES,
  RESEARCH_ABLATIONS,
  DATASET_SPLITS,
} from '../api/types.js';

export function useResearchEvaluation(projectId, isCurrentGeneration, getGeneration) {
  // Datasets
  const [datasets, setDatasets] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState(null);

  // Experiment Configuration
  const [selectedStrategy, setSelectedStrategy] = useState(RESEARCH_STRATEGIES.C4_POLICY_AWARE);
  const [selectedAblation, setSelectedAblation] = useState(RESEARCH_ABLATIONS.NONE);
  const [selectedSplit, setSelectedSplit] = useState(DATASET_SPLITS.DEV);
  const [repeatCount, setRepeatCount] = useState(1);
  const [seed, setSeed] = useState(42);
  const [activeExperiment, setActiveExperiment] = useState(null);
  const [experimentReport, setExperimentReport] = useState(null);

  // Independent Review & Inter-Rater Agreement
  const [reviewer1, setReviewer1] = useState('REVIEWER_1');
  const [reviewer2, setReviewer2] = useState('REVIEWER_2');
  const [agreementResult, setAgreementResult] = useState(null);

  // Loading states
  const [isLoadingDatasets, setIsLoadingDatasets] = useState(false);
  const [isRegisteringDataset, setIsRegisteringDataset] = useState(false);
  const [isFreezingDataset, setIsFreezingDataset] = useState(false);
  const [isCreatingExperiment, setIsCreatingExperiment] = useState(false);
  const [isExecutingExperiment, setIsExecutingExperiment] = useState(false);
  const [isCalculatingAgreement, setIsCalculatingAgreement] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  const resetState = useCallback(() => {
    setDatasets([]);
    setSelectedDataset(null);
    setActiveExperiment(null);
    setExperimentReport(null);
    setAgreementResult(null);
    setIsLoadingDatasets(false);
    setIsRegisteringDataset(false);
    setIsFreezingDataset(false);
    setIsCreatingExperiment(false);
    setIsExecutingExperiment(false);
    setIsCalculatingAgreement(false);
    setError(null);
    setSuccessMessage(null);
  }, []);

  /**
   * List evaluation datasets for current project.
   */
  const loadDatasets = useCallback(async () => {
    if (!projectId) return [];

    setIsLoadingDatasets(true);
    setError(null);
    const currentGen = getGeneration();

    try {
      const list = await c4Api.listEvaluationDatasets(projectId);
      if (!isCurrentGeneration(currentGen)) return [];

      setDatasets(list);
      if (list.length > 0 && !selectedDataset) {
        setSelectedDataset(list[0]);
      }
      return list;
    } catch (err) {
      if (isCurrentGeneration(currentGen)) {
        setError(err.message || 'Failed to list evaluation datasets.');
      }
      return [];
    } finally {
      if (isCurrentGeneration(currentGen)) {
        setIsLoadingDatasets(false);
      }
    }
  }, [projectId, selectedDataset, getGeneration, isCurrentGeneration]);

  /**
   * Register a new versioned evaluation dataset.
   */
  const registerDataset = useCallback(
    async (datasetPayload) => {
      if (!projectId) return null;

      setIsRegisteringDataset(true);
      setError(null);
      setSuccessMessage(null);
      const currentGen = getGeneration();

      try {
        const registered = await c4Api.registerEvaluationDataset(projectId, datasetPayload);
        if (!isCurrentGeneration(currentGen)) return null;

        setDatasets((prev) => [registered, ...prev]);
        setSelectedDataset(registered);
        setSuccessMessage(`Evaluation dataset '${registered.dataset_id}' registered successfully.`);
        return registered;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Failed to register evaluation dataset.');
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsRegisteringDataset(false);
        }
      }
    },
    [projectId, getGeneration, isCurrentGeneration]
  );

  /**
   * Freeze an evaluation dataset to guarantee immutability for final benchmarks.
   */
  const freezeDataset = useCallback(
    async (datasetId, version = 1) => {
      if (!projectId || !datasetId) return null;

      setIsFreezingDataset(true);
      setError(null);
      setSuccessMessage(null);
      const currentGen = getGeneration();

      try {
        const frozen = await c4Api.freezeEvaluationDataset(projectId, datasetId, version);
        if (!isCurrentGeneration(currentGen)) return null;

        setDatasets((prev) => prev.map((d) => (d.dataset_id === datasetId ? frozen : d)));
        if (selectedDataset?.dataset_id === datasetId) {
          setSelectedDataset(frozen);
        }
        setSuccessMessage(`Evaluation dataset '${datasetId}' is now FROZEN.`);
        return frozen;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Failed to freeze evaluation dataset.');
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsFreezingDataset(false);
        }
      }
    },
    [projectId, selectedDataset, getGeneration, isCurrentGeneration]
  );

  /**
   * Calculate Cohen's Kappa agreement between two reviewers.
   */
  const calculateAgreement = useCallback(
    async (r1 = null, r2 = null) => {
      if (!projectId) return null;

      const reviewerA = r1 || reviewer1;
      const reviewerB = r2 || reviewer2;

      setIsCalculatingAgreement(true);
      setError(null);
      const currentGen = getGeneration();

      try {
        const res = await c4Api.getReviewerAgreement(projectId, reviewerA, reviewerB);
        if (!isCurrentGeneration(currentGen)) return null;

        setAgreementResult(res);
        setSuccessMessage(
          `Agreement calculated: Cohen's Kappa = ${res.cohens_kappa !== null ? res.cohens_kappa.toFixed(3) : 'N/A'} (${res.interpretation})`
        );
        return res;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Failed to calculate inter-rater agreement.');
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsCalculatingAgreement(false);
        }
      }
    },
    [projectId, reviewer1, reviewer2, getGeneration, isCurrentGeneration]
  );

  /**
   * Create and immediately run a reproducible evaluation experiment.
   */
  const runExperiment = useCallback(
    async (overrides = {}) => {
      if (!projectId) return null;

      const dataset = overrides.dataset || selectedDataset;
      if (!dataset) {
        setError('Please select or register an evaluation dataset first.');
        return null;
      }

      setIsCreatingExperiment(true);
      setError(null);
      setSuccessMessage(null);
      const currentGen = getGeneration();

      const expId = `exp-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
      const config = {
        experiment_id: expId,
        project_id: projectId,
        domain_id: dataset.domain_id || 'domain-ecommerce-c4',
        dataset_id: dataset.dataset_id,
        dataset_version: dataset.version || 1,
        split: overrides.split || selectedSplit,
        strategy_type: overrides.strategy || selectedStrategy,
        ablation_type: overrides.ablation || selectedAblation,
        repeat_count: Number(overrides.repeatCount ?? repeatCount),
        seed: Number(overrides.seed ?? seed),
        budget_limit: 100,
      };

      try {
        const createdExp = await c4Api.createExperiment(projectId, config);
        if (!isCurrentGeneration(currentGen)) return null;
        setActiveExperiment(createdExp);
        setIsCreatingExperiment(false);

        // Execute experiment
        setIsExecutingExperiment(true);
        const report = await c4Api.executeExperiment(projectId, expId);
        if (!isCurrentGeneration(currentGen)) return null;

        setExperimentReport(report);
        setSuccessMessage(`Experiment '${expId}' completed. Consolidated report generated.`);
        return report;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Failed to configure or execute evaluation experiment.');
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsCreatingExperiment(false);
          setIsExecutingExperiment(false);
        }
      }
    },
    [
      projectId,
      selectedDataset,
      selectedSplit,
      selectedStrategy,
      selectedAblation,
      repeatCount,
      seed,
      getGeneration,
      isCurrentGeneration,
    ]
  );

  return {
    // Datasets
    datasets,
    selectedDataset,
    setSelectedDataset,
    loadDatasets,
    registerDataset,
    freezeDataset,

    // Experiment state
    selectedStrategy,
    setSelectedStrategy,
    selectedAblation,
    setSelectedAblation,
    selectedSplit,
    setSelectedSplit,
    repeatCount,
    setRepeatCount,
    seed,
    setSeed,
    activeExperiment,
    experimentReport,
    runExperiment,

    // Reviewer Agreement
    reviewer1,
    setReviewer1,
    reviewer2,
    setReviewer2,
    agreementResult,
    calculateAgreement,

    // Loading & messages
    isLoadingDatasets,
    isRegisteringDataset,
    isFreezingDataset,
    isCreatingExperiment,
    isExecutingExperiment,
    isCalculatingAgreement,
    error,
    successMessage,
    setError,
    setSuccessMessage,
    resetState,
  };
}
