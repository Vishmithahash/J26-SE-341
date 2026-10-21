/**
 * Component 4 (C4) - Policy Extraction and Candidate Review Hook
 * Manages extraction provider readiness, rule derivation, candidate inspection, and human review decisions.
 */

import { useState, useCallback, useEffect } from 'react';
import { c4Api } from '../api/c4Api.js';

export function usePolicyExtraction(projectId, isCurrentGeneration, getGeneration) {
  const [providerReadiness, setProviderReadiness] = useState(null);
  const [selectedProvider, setSelectedProvider] = useState('offline_mock');
  const [isLoadingReadiness, setIsLoadingReadiness] = useState(false);
  const [candidates, setCandidates] = useState([]);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [isReviewing, setIsReviewing] = useState(false);
  const [activeJob, setActiveJob] = useState(null);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  const resetState = useCallback(() => {
    setProviderReadiness(null);
    setCandidates([]);
    setSelectedCandidate(null);
    setIsExtracting(false);
    setIsReviewing(false);
    setActiveJob(null);
    setError(null);
    setSuccessMessage(null);
  }, []);

  const checkReadiness = useCallback(
    async (providerId = selectedProvider) => {
      if (!projectId) return null;
      setIsLoadingReadiness(true);
      setError(null);
      const currentGen = getGeneration();

      try {
        const report = await c4Api.getExtractionReadiness(projectId, providerId);
        if (!isCurrentGeneration(currentGen)) return null;
        setProviderReadiness(report);
        return report;
      } catch (err) {
        if (!isCurrentGeneration(currentGen)) return null;
        setProviderReadiness({
          ready: false,
          status: 'ERROR',
          provider_id: providerId,
          model_identifier: null,
          supported_policy_families: [],
          blockers: [err.message || 'Failed to check extraction provider readiness.'],
        });
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsLoadingReadiness(false);
        }
      }
    },
    [projectId, selectedProvider, getGeneration, isCurrentGeneration]
  );

  useEffect(() => {
    if (projectId) {
      checkReadiness();
    }
  }, [projectId, checkReadiness]);

  const deriveCandidates = useCallback(
    async ({ artifactId, artifactVersion, mode = 'controlled_language', structuredPayload = null }) => {
      if (!projectId) {
        setError('No active project selected.');
        return [];
      }

      setIsExtracting(true);
      setError(null);
      setSuccessMessage(null);
      const currentGen = getGeneration();

      try {
        const payload = {
          artifact_id: artifactId,
          artifact_version: artifactVersion,
          mode,
          ...(structuredPayload ? { structured_payload: structuredPayload } : {}),
        };

        const derivedRules = await c4Api.deriveRules(projectId, payload);
        if (!isCurrentGeneration(currentGen)) return [];

        setCandidates((prev) => {
          const newMap = new Map();
          prev.forEach((r) => newMap.set(r.rule_id, r));
          derivedRules.forEach((r) => newMap.set(r.rule_id, r));
          return Array.from(newMap.values());
        });

        if (derivedRules.length > 0) {
          setSelectedCandidate(derivedRules[0]);
          setSuccessMessage(
            `Extracted ${derivedRules.length} candidate rule${derivedRules.length === 1 ? '' : 's'} via ${mode.replace('_', ' ')}.`
          );
        } else {
          setSuccessMessage('Derivation completed. No candidate rules matched the pattern in this artifact version.');
        }

        return derivedRules;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Rule derivation failed.');
        }
        return [];
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsExtracting(false);
        }
      }
    },
    [projectId, getGeneration, isCurrentGeneration]
  );

  const startExtractionJob = useCallback(
    async ({ artifactId, artifactVersion, providerId = selectedProvider }) => {
      if (!projectId) {
        setError('No active project selected.');
        return null;
      }

      setIsExtracting(true);
      setError(null);
      setSuccessMessage(null);
      const currentGen = getGeneration();

      try {
        const payload = {
          artifact_id: artifactId,
          artifact_version: artifactVersion,
          provider_id: providerId,
        };

        const job = await c4Api.startExtractionJob(projectId, payload);
        if (!isCurrentGeneration(currentGen)) return null;

        setActiveJob(job);
        setSuccessMessage(`Extraction job ${job.job_id} initiated (${job.status}).`);
        return job;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Extraction job failed.');
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsExtracting(false);
        }
      }
    },
    [projectId, selectedProvider, getGeneration, isCurrentGeneration]
  );

  const reviewCandidate = useCallback(
    async ({ ruleId, decision, reviewer, reviewNotes }) => {
      if (!projectId) {
        setError('No active project selected.');
        return null;
      }

      setIsReviewing(true);
      setError(null);
      const currentGen = getGeneration();

      try {
        const payload = {
          decision,
          reviewer: reviewer || 'dev_reviewer',
          review_notes: reviewNotes || null,
          is_synthetic_review: false,
        };

        const updated = await c4Api.reviewCandidateRule(projectId, ruleId, payload);
        if (!isCurrentGeneration(currentGen)) return null;

        setCandidates((prev) => prev.map((r) => (r.rule_id === ruleId ? updated : r)));
        if (selectedCandidate?.rule_id === ruleId) {
          setSelectedCandidate(updated);
        }
        setSuccessMessage(`Candidate rule "${ruleId}" marked as ${decision}.`);
        return updated;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Candidate rule review failed.');
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsReviewing(false);
        }
      }
    },
    [projectId, selectedCandidate, getGeneration, isCurrentGeneration]
  );

  return {
    providerReadiness,
    selectedProvider,
    setSelectedProvider,
    isLoadingReadiness,
    candidates,
    setCandidates,
    selectedCandidate,
    setSelectedCandidate,
    isExtracting,
    isReviewing,
    activeJob,
    error,
    setError,
    successMessage,
    setSuccessMessage,
    checkReadiness,
    deriveCandidates,
    startExtractionJob,
    reviewCandidate,
    resetState,
  };
}
