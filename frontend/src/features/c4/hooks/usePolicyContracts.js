/**
 * Component 4 (C4) - Policy Contracts Hook
 * Manages contract draft creation, validation gating, explicit acceptance, and accepted contract inspection.
 */

import { useState, useCallback } from 'react';
import { c4Api } from '../api/c4Api';
import { CONTRACT_LIFECYCLE_STATES } from '../api/types';

export function usePolicyContracts(projectId, isCurrentGeneration, getGeneration) {
  const [currentContract, setCurrentContract] = useState(null);
  const [contractValidation, setContractValidation] = useState(null);
  const [isDrafting, setIsDrafting] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [isAccepting, setIsAccepting] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  const resetState = useCallback(() => {
    setCurrentContract(null);
    setContractValidation(null);
    setIsDrafting(false);
    setIsValidating(false);
    setIsAccepting(false);
    setError(null);
    setSuccessMessage(null);
  }, []);

  // Create contract draft from rule IDs
  const createDraft = useCallback(
    async ({ contractId, ruleIds, description }) => {
      if (!projectId) {
        setError('No active project selected.');
        return null;
      }

      if (!contractId || !contractId.trim()) {
        setError('Contract identifier is required.');
        return null;
      }

      if (!ruleIds || ruleIds.length === 0) {
        setError('At least one candidate rule must be selected to create a contract draft.');
        return null;
      }

      setIsDrafting(true);
      setError(null);
      setSuccessMessage(null);
      const currentGen = getGeneration();

      try {
        const payload = {
          contract_id: contractId.trim(),
          rule_ids: ruleIds,
          ...(description ? { description } : {}),
        };

        const contract = await c4Api.createContractDraft(projectId, payload);
        if (!isCurrentGeneration(currentGen)) return null;

        setCurrentContract(contract);
        setSuccessMessage(`Contract "${contract.contract_id}" (v${contract.version}) draft created in state ${contract.lifecycle_state}.`);

        // Automatically run validation on newly created draft
        try {
          const valRes = await c4Api.validateContract(projectId, contract.contract_id, contract.version);
          if (isCurrentGeneration(currentGen)) {
            setContractValidation(valRes);
          }
        } catch {
          // Validation error handled in manual validate step if needed
        }

        return contract;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Failed to create contract draft.');
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsDrafting(false);
        }
      }
    },
    [projectId, getGeneration, isCurrentGeneration]
  );

  // Validate contract draft
  const validateDraft = useCallback(
    async (contractId, version) => {
      if (!projectId || !contractId || !version) return null;

      setIsValidating(true);
      setError(null);
      const currentGen = getGeneration();

      try {
        const valRes = await c4Api.validateContract(projectId, contractId, version);
        if (!isCurrentGeneration(currentGen)) return null;

        setContractValidation(valRes);
        if (valRes.is_valid) {
          setSuccessMessage(`Contract "${contractId}" v${version} passed all validation checks!`);
        } else {
          setError(
            `Contract "${contractId}" v${version} has ${valRes.issues.length} validation issue${valRes.issues.length === 1 ? '' : 's'}. Review before acceptance.`
          );
        }
        return valRes;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Failed to validate contract draft.');
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsValidating(false);
        }
      }
    },
    [projectId, getGeneration, isCurrentGeneration]
  );

  // Explicitly accept validated contract
  const acceptDraft = useCallback(
    async ({ contractId, version, acceptedBy, rationale }) => {
      if (!projectId) {
        setError('No active project selected.');
        return null;
      }

      if (!acceptedBy || !acceptedBy.trim()) {
        setError('Acceptor name or principal ID is required.');
        return null;
      }

      setIsAccepting(true);
      setError(null);
      setSuccessMessage(null);
      const currentGen = getGeneration();

      try {
        const payload = {
          accepted_by: acceptedBy.trim(),
          rationale: rationale || 'Explicit human review and acceptance gate passed.',
        };

        const accepted = await c4Api.acceptContract(projectId, contractId, version, payload);
        if (!isCurrentGeneration(currentGen)) return null;

        setCurrentContract(accepted);
        setSuccessMessage(
          `Contract "${accepted.contract_id}" (v${accepted.version}) successfully ACCEPTED and frozen with hash ${accepted.content_hash.slice(0, 10)}...`
        );
        return accepted;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Contract acceptance rejected by backend validation gates.');
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsAccepting(false);
        }
      }
    },
    [projectId, getGeneration, isCurrentGeneration]
  );

  // Fetch an existing contract version
  const fetchContract = useCallback(
    async (contractId, version) => {
      if (!projectId || !contractId || !version) return null;

      setError(null);
      const currentGen = getGeneration();

      try {
        const contract = await c4Api.getContract(projectId, contractId, version);
        if (!isCurrentGeneration(currentGen)) return null;

        setCurrentContract(contract);
        return contract;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Failed to fetch contract.');
        }
        return null;
      }
    },
    [projectId, getGeneration, isCurrentGeneration]
  );

  return {
    currentContract,
    setCurrentContract,
    contractValidation,
    setContractValidation,
    isDrafting,
    isValidating,
    isAccepting,
    isAccepted: currentContract?.lifecycle_state === CONTRACT_LIFECYCLE_STATES.ACCEPTED,
    error,
    setError,
    successMessage,
    setSuccessMessage,
    createDraft,
    validateDraft,
    acceptDraft,
    fetchContract,
    resetState,
  };
}
