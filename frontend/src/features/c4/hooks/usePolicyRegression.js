/**
 * Component 4 (C4) - Policy-Change Regression & Diffing Hook
 * Manages contract version comparisons, impact analysis plans, selective regeneration,
 * plan freezing, controlled execution (fresh vs historical re-evaluation), and report generation.
 */

import { useState, useCallback } from 'react';
import { c4Api } from '../api/c4Api.js';
import { REGRESSION_EXECUTION_MODES } from '../api/types.js';

function generateUUID() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'reg-idem-' + Math.random().toString(36).substring(2, 15) + '-' + Date.now();
}

export function usePolicyRegression(projectId, isCurrentGeneration, getGeneration) {
  // Form parameters
  const [baselineContractId, setBaselineContractId] = useState('');
  const [baselineContractVersion, setBaselineContractVersion] = useState(1);
  const [candidateContractId, setCandidateContractId] = useState('');
  const [candidateContractVersion, setCandidateContractVersion] = useState(2);
  const [bindingId, setBindingId] = useState('binding-ecommerce-c4');
  const [bindingVersion, setBindingVersion] = useState(1);
  const [executionMode, setExecutionMode] = useState(REGRESSION_EXECUTION_MODES.FRESH_EXECUTION);
  const [idempotencyKey, setIdempotencyKey] = useState(generateUUID());

  // Active records
  const [activeComparison, setActiveComparison] = useState(null);
  const [activePlan, setActivePlan] = useState(null);
  const [activeReport, setActiveReport] = useState(null);

  // Loading states
  const [isComparing, setIsComparing] = useState(false);
  const [isCreatingPlan, setIsCreatingPlan] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [isFreezing, setIsFreezing] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [isLoadingReport, setIsLoadingReport] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  const resetState = useCallback(() => {
    setActiveComparison(null);
    setActivePlan(null);
    setActiveReport(null);
    setIdempotencyKey(generateUUID());
    setIsComparing(false);
    setIsCreatingPlan(false);
    setIsRegenerating(false);
    setIsFreezing(false);
    setIsExecuting(false);
    setIsLoadingReport(false);
    setError(null);
    setSuccessMessage(null);
  }, []);

  const regenerateIdempotencyKey = useCallback(() => {
    setIdempotencyKey(generateUUID());
  }, []);

  /**
   * Compare baseline and candidate policy contracts to produce rule diff.
   */
  const compareContracts = useCallback(
    async (params = {}) => {
      if (!projectId) return null;

      const baseId = params.baselineContractId || baselineContractId;
      const baseVer = Number(params.baselineContractVersion ?? baselineContractVersion);
      const candId = params.candidateContractId || candidateContractId;
      const candVer = Number(params.candidateContractVersion ?? candidateContractVersion);

      if (!baseId || !candId) {
        setError('Please specify both baseline and candidate policy contract identifiers.');
        return null;
      }

      setIsComparing(true);
      setError(null);
      setSuccessMessage(null);
      const currentGen = getGeneration();

      try {
        const payload = {
          project_id: projectId,
          baseline_contract_id: baseId,
          baseline_contract_version: baseVer,
          candidate_contract_id: candId,
          candidate_contract_version: candVer,
          binding_id: params.bindingId || bindingId,
          binding_version: Number(params.bindingVersion ?? bindingVersion),
        };

        const comparison = await c4Api.comparePolicyContracts(projectId, payload);
        if (!isCurrentGeneration(currentGen)) return null;

        setActiveComparison(comparison);
        setSuccessMessage(
          `Contracts compared successfully: ${comparison.rule_diffs?.length || 0} rule diff(s) detected.`
        );
        return comparison;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Failed to compare policy contracts.');
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsComparing(false);
        }
      }
    },
    [
      projectId,
      baselineContractId,
      baselineContractVersion,
      candidateContractId,
      candidateContractVersion,
      bindingId,
      bindingVersion,
      getGeneration,
      isCurrentGeneration,
    ]
  );

  /**
   * Build typed regression plan from an active comparison.
   */
  const createPlan = useCallback(
    async (comparisonId = null, targetBindingId = null, targetBindingVersion = null) => {
      if (!projectId) return null;

      const compId = comparisonId || activeComparison?.comparison_id;
      if (!compId) {
        setError('Comparison ID required to generate regression plan.');
        return null;
      }

      setIsCreatingPlan(true);
      setError(null);
      setSuccessMessage(null);
      const currentGen = getGeneration();

      try {
        const payload = {
          comparison_id: compId,
          binding_id: targetBindingId || bindingId,
          binding_version: Number(targetBindingVersion ?? bindingVersion),
        };

        const plan = await c4Api.createRegressionPlan(projectId, payload);
        if (!isCurrentGeneration(currentGen)) return null;

        setActivePlan(plan);
        setSuccessMessage(`Regression plan '${plan.plan_id}' drafted with ${plan.case_decisions?.length || 0} case decisions.`);
        return plan;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Failed to create regression plan.');
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsCreatingPlan(false);
        }
      }
    },
    [projectId, activeComparison, bindingId, bindingVersion, getGeneration, isCurrentGeneration]
  );

  /**
   * Selectively regenerate affected cases for a plan.
   */
  const regeneratePlan = useCallback(
    async (planId = null) => {
      if (!projectId) return null;

      const pId = planId || activePlan?.plan_id;
      if (!pId) {
        setError('No active regression plan to regenerate.');
        return null;
      }

      setIsRegenerating(true);
      setError(null);
      setSuccessMessage(null);
      const currentGen = getGeneration();

      try {
        const updatedPlan = await c4Api.regenerateRegressionPlan(projectId, pId);
        if (!isCurrentGeneration(currentGen)) return null;

        setActivePlan(updatedPlan);
        setSuccessMessage('Affected test cases selectively regenerated and validated.');
        return updatedPlan;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Failed to regenerate regression plan cases.');
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsRegenerating(false);
        }
      }
    },
    [projectId, activePlan, getGeneration, isCurrentGeneration]
  );

  /**
   * Freeze regression plan into an immutable snapshot.
   */
  const freezePlan = useCallback(
    async (planId = null) => {
      if (!projectId) return null;

      const pId = planId || activePlan?.plan_id;
      if (!pId) {
        setError('No active regression plan to freeze.');
        return null;
      }

      setIsFreezing(true);
      setError(null);
      setSuccessMessage(null);
      const currentGen = getGeneration();

      try {
        const frozenPlan = await c4Api.freezeRegressionPlan(projectId, pId);
        if (!isCurrentGeneration(currentGen)) return null;

        setActivePlan(frozenPlan);
        setSuccessMessage(`Regression plan '${frozenPlan.plan_id}' is now FROZEN (read-only snapshot).`);
        return frozenPlan;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Failed to freeze regression plan.');
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsFreezing(false);
        }
      }
    },
    [projectId, activePlan, getGeneration, isCurrentGeneration]
  );

  /**
   * Execute selective regression plan (FRESH_EXECUTION mode).
   */
  const executePlan = useCallback(
    async (planId = null, mode = null) => {
      if (!projectId) return null;

      const pId = planId || activePlan?.plan_id;
      if (!pId) {
        setError('No plan selected for execution.');
        return null;
      }

      const execMode = mode || executionMode;

      setIsExecuting(true);
      setError(null);
      setSuccessMessage(null);
      const currentGen = getGeneration();

      try {
        const payload = {
          execution_mode: execMode,
          idempotency_key: idempotencyKey,
        };

        const batchRecord = await c4Api.executeRegressionPlan(projectId, pId, payload);
        if (!isCurrentGeneration(currentGen)) return null;

        setSuccessMessage(`Selective regression executed: ${batchRecord.runs?.length || 0} run(s) recorded.`);

        // Automatically fetch regression report
        try {
          const report = await c4Api.getRegressionReport(projectId, pId);
          if (isCurrentGeneration(currentGen)) {
            setActiveReport(report);
          }
        } catch {
          // Report will be fetched on-demand if not immediately available
        }

        return batchRecord;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          if (err.status === 409 || err.message?.includes('Idempotency conflict')) {
            setError('Idempotency conflict: this key was submitted with different parameters. Click "New Key" to retry.');
          } else {
            setError(err.message || 'Failed to execute regression plan.');
          }
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsExecuting(false);
        }
      }
    },
    [projectId, activePlan, executionMode, idempotencyKey, getGeneration, isCurrentGeneration]
  );

  /**
   * Re-evaluate historical run evidence under candidate policy without fresh agent execution.
   */
  const reEvaluateHistorical = useCallback(
    async (planId = null) => {
      if (!projectId) return null;

      const pId = planId || activePlan?.plan_id;
      if (!pId) {
        setError('No plan selected for historical re-evaluation.');
        return null;
      }

      setIsExecuting(true);
      setError(null);
      setSuccessMessage(null);
      const currentGen = getGeneration();

      try {
        const batchRecord = await c4Api.reEvaluateHistorical(projectId, pId);
        if (!isCurrentGeneration(currentGen)) return null;

        setSuccessMessage(
          `Historical evidence re-evaluated under candidate policy: ${batchRecord.runs?.length || 0} run(s) re-evaluated.`
        );

        // Fetch report
        try {
          const report = await c4Api.getRegressionReport(projectId, pId);
          if (isCurrentGeneration(currentGen)) {
            setActiveReport(report);
          }
        } catch {
          // Ignore
        }

        return batchRecord;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Failed to re-evaluate historical run evidence.');
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsExecuting(false);
        }
      }
    },
    [projectId, activePlan, getGeneration, isCurrentGeneration]
  );

  /**
   * Load existing regression report.
   */
  const loadReport = useCallback(
    async (planId = null) => {
      if (!projectId) return null;

      const pId = planId || activePlan?.plan_id;
      if (!pId) return null;

      setIsLoadingReport(true);
      setError(null);
      const currentGen = getGeneration();

      try {
        const report = await c4Api.getRegressionReport(projectId, pId);
        if (!isCurrentGeneration(currentGen)) return null;

        setActiveReport(report);
        return report;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Failed to load regression report.');
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsLoadingReport(false);
        }
      }
    },
    [projectId, activePlan, getGeneration, isCurrentGeneration]
  );

  return {
    // Form state
    baselineContractId,
    setBaselineContractId,
    baselineContractVersion,
    setBaselineContractVersion,
    candidateContractId,
    setCandidateContractId,
    candidateContractVersion,
    setCandidateContractVersion,
    bindingId,
    setBindingId,
    bindingVersion,
    setBindingVersion,
    executionMode,
    setExecutionMode,
    idempotencyKey,
    regenerateIdempotencyKey,

    // Active records
    activeComparison,
    activePlan,
    activeReport,
    setActiveComparison,
    setActivePlan,
    setActiveReport,

    // Loading & messaging
    isComparing,
    isCreatingPlan,
    isRegenerating,
    isFreezing,
    isExecuting,
    isLoadingReport,
    error,
    successMessage,
    setError,
    setSuccessMessage,
    resetState,

    // Actions
    compareContracts,
    createPlan,
    regeneratePlan,
    freezePlan,
    executePlan,
    reEvaluateHistorical,
    loadReport,
  };
}
