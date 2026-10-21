/**
 * Component 4 (C4) - Test Case Inspection, Validation, Freezing & Payloads Hook
 * Manages test case listing, filtering, independent validation, snapshot freezing, and payload boundary exports.
 */

import { useState, useCallback } from 'react';
import { c4Api } from '../api/c4Api.js';

export function useTestCaseInspection(projectId, isCurrentGeneration, getGeneration) {
  const [testCases, setTestCases] = useState([]);
  const [selectedCase, setSelectedCase] = useState(null);
  const [activePayloads, setActivePayloads] = useState({
    agent: null,
    harness: null,
    evaluator: null,
  });

  const [isLoadingCases, setIsLoadingCases] = useState(false);
  const [isValidatingCase, setIsValidatingCase] = useState(false);
  const [isFreezingCase, setIsFreezingCase] = useState(false);
  const [isLoadingPayloads, setIsLoadingPayloads] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  const resetState = useCallback(() => {
    setTestCases([]);
    setSelectedCase(null);
    setActivePayloads({ agent: null, harness: null, evaluator: null });
    setIsLoadingCases(false);
    setIsValidatingCase(false);
    setIsFreezingCase(false);
    setIsLoadingPayloads(false);
    setError(null);
    setSuccessMessage(null);
  }, []);

  const loadTestCases = useCallback(
    async (params = {}) => {
      if (!projectId) return [];

      setIsLoadingCases(true);
      setError(null);
      const currentGen = getGeneration();

      try {
        const cases = await c4Api.listTestCases(projectId, params);
        if (!isCurrentGeneration(currentGen)) return [];

        setTestCases(cases);
        if (cases.length > 0 && !selectedCase) {
          setSelectedCase(cases[0]);
        }
        return cases;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Failed to list test cases.');
        }
        return [];
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsLoadingCases(false);
        }
      }
    },
    [projectId, selectedCase, getGeneration, isCurrentGeneration]
  );

  const fetchCase = useCallback(
    async (caseId, version) => {
      if (!projectId || !caseId || !version) return null;

      setError(null);
      const currentGen = getGeneration();

      try {
        const caseRecord = await c4Api.getTestCase(projectId, caseId.trim(), Number(version));
        if (!isCurrentGeneration(currentGen)) return null;

        setSelectedCase(caseRecord);
        setTestCases((prev) => {
          const filtered = prev.filter(
            (c) => !(c.case_id === caseRecord.case_id && c.case_version === caseRecord.case_version)
          );
          return [caseRecord, ...filtered];
        });
        return caseRecord;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || `Test case "${caseId}" v${version} not found.`);
        }
        return null;
      }
    },
    [projectId, getGeneration, isCurrentGeneration]
  );

  const validateCase = useCallback(
    async (caseId, version) => {
      if (!projectId || !caseId || !version) return null;

      setIsValidatingCase(true);
      setError(null);
      setSuccessMessage(null);
      const currentGen = getGeneration();

      try {
        const validated = await c4Api.validateTestCase(projectId, caseId, Number(version));
        if (!isCurrentGeneration(currentGen)) return null;

        setTestCases((prev) =>
          prev.map((c) => (c.case_id === caseId && c.case_version === version ? validated : c))
        );
        if (selectedCase?.case_id === caseId && selectedCase?.case_version === version) {
          setSelectedCase(validated);
        }

        const issuesCount = validated.validation_issues?.length || 0;
        setSuccessMessage(
          `Case "${caseId}" validated (${validated.lifecycle_state}) with ${issuesCount} issue(s).`
        );
        return validated;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || `Validation failed for case "${caseId}".`);
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsValidatingCase(false);
        }
      }
    },
    [projectId, selectedCase, getGeneration, isCurrentGeneration]
  );

  const freezeCase = useCallback(
    async (caseId, version) => {
      if (!projectId || !caseId || !version) return null;

      setIsFreezingCase(true);
      setError(null);
      setSuccessMessage(null);
      const currentGen = getGeneration();

      try {
        const frozen = await c4Api.freezeTestCase(projectId, caseId, Number(version));
        if (!isCurrentGeneration(currentGen)) return null;

        setTestCases((prev) =>
          prev.map((c) => (c.case_id === caseId && c.case_version === version ? frozen : c))
        );
        if (selectedCase?.case_id === caseId && selectedCase?.case_version === version) {
          setSelectedCase(frozen);
        }

        setSuccessMessage(
          `Case "${caseId}" v${version} successfully frozen (Hash: ${frozen.content_hash?.substring(0, 12)}...).`
        );
        return frozen;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || `Freezing failed for case "${caseId}".`);
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsFreezingCase(false);
        }
      }
    },
    [projectId, selectedCase, getGeneration, isCurrentGeneration]
  );

  const loadAllPayloads = useCallback(
    async (caseId, version) => {
      if (!projectId || !caseId || !version) return;

      setIsLoadingPayloads(true);
      setError(null);
      const currentGen = getGeneration();

      try {
        const [agent, harness, evaluator] = await Promise.all([
          c4Api.exportAgentPayload(projectId, caseId, Number(version)),
          c4Api.exportHarnessPayload(projectId, caseId, Number(version)),
          c4Api.exportEvaluatorPayload(projectId, caseId, Number(version)),
        ]);

        if (!isCurrentGeneration(currentGen)) return;

        setActivePayloads({ agent, harness, evaluator });
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Failed to export separated payload boundaries.');
        }
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsLoadingPayloads(false);
        }
      }
    },
    [projectId, getGeneration, isCurrentGeneration]
  );

  return {
    testCases,
    setTestCases,
    selectedCase,
    setSelectedCase,
    activePayloads,
    setActivePayloads,
    isLoadingCases,
    isValidatingCase,
    isFreezingCase,
    isLoadingPayloads,
    error,
    setError,
    successMessage,
    setSuccessMessage,
    loadTestCases,
    fetchCase,
    validateCase,
    freezeCase,
    loadAllPayloads,
    resetState,
  };
}
