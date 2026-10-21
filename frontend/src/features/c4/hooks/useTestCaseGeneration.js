/**
 * Component 4 (C4) - Test Case Generation Hook
 * Manages bounded test generation request configuration, execution, and batch reports.
 */

import { useState, useCallback } from 'react';
import { c4Api } from '../api/c4Api.js';
import { TEST_CASE_KINDS } from '../api/types.js';

export function useTestCaseGeneration(projectId, isCurrentGeneration, getGeneration) {
  const [latestReport, setLatestReport] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isFetchingBatch, setIsFetchingBatch] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  const resetState = useCallback(() => {
    setLatestReport(null);
    setIsGenerating(false);
    setIsFetchingBatch(false);
    setError(null);
    setSuccessMessage(null);
  }, []);

  const generateCases = useCallback(
    async ({
      contractId,
      contractVersion,
      bindingId,
      bindingVersion,
      categories = [
        TEST_CASE_KINDS.BENIGN,
        TEST_CASE_KINDS.DIRECT_POLICY_CHALLENGE,
        TEST_CASE_KINDS.INDIRECT_PROMPT_INJECTION,
      ],
      targetRuleIds = null,
      seed = 42,
      maxCasesPerRule = 10,
      includeBenignControls = true,
      includeBoundaryValues = true,
      autoValidate = true,
      autoFreeze = false,
    }) => {
      if (!projectId) {
        setError('No active project selected.');
        return null;
      }

      if (!contractId || !contractVersion) {
        setError('Accepted policy contract and version are required for test generation.');
        return null;
      }

      if (!bindingId || !bindingVersion) {
        setError('Domain binding and version are required for test generation.');
        return null;
      }

      setIsGenerating(true);
      setError(null);
      setSuccessMessage(null);
      const currentGen = getGeneration();

      try {
        const payload = {
          contract_id: contractId,
          contract_version: Number(contractVersion),
          binding_id: bindingId,
          binding_version: Number(bindingVersion),
          config: {
            categories,
            target_rule_ids: targetRuleIds && targetRuleIds.length > 0 ? targetRuleIds : null,
            seed: Number(seed),
            max_cases_per_rule: Math.min(Math.max(Number(maxCasesPerRule) || 10, 1), 50),
            include_benign_controls: Boolean(includeBenignControls),
            include_boundary_values: Boolean(includeBoundaryValues),
          },
          auto_validate: Boolean(autoValidate),
          auto_freeze: Boolean(autoFreeze),
        };

        const report = await c4Api.generateTestCases(projectId, payload);
        if (!isCurrentGeneration(currentGen)) return null;

        setLatestReport(report);
        setSuccessMessage(
          `Batch ${report.batch_id} generated ${report.generated_count} test cases (${report.validated_count} validated, ${report.frozen_count} frozen).`
        );
        return report;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Automatic test generation failed.');
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsGenerating(false);
        }
      }
    },
    [projectId, getGeneration, isCurrentGeneration]
  );

  const fetchBatchReport = useCallback(
    async (batchId) => {
      if (!projectId || !batchId) return null;

      setIsFetchingBatch(true);
      setError(null);
      const currentGen = getGeneration();

      try {
        const report = await c4Api.getGenerationBatch(projectId, batchId.trim());
        if (!isCurrentGeneration(currentGen)) return null;

        setLatestReport(report);
        setSuccessMessage(`Retrieved generation batch "${batchId}".`);
        return report;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || `Generation batch "${batchId}" not found.`);
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsFetchingBatch(false);
        }
      }
    },
    [projectId, getGeneration, isCurrentGeneration]
  );

  return {
    latestReport,
    setLatestReport,
    isGenerating,
    isFetchingBatch,
    error,
    setError,
    successMessage,
    setSuccessMessage,
    generateCases,
    fetchBatchReport,
    resetState,
  };
}
