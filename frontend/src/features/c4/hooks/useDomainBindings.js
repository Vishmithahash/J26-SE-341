/**
 * Component 4 (C4) - Domain Bindings and Onboarding Hook
 * Manages domain profiles, domain bindings inspection, readiness checks, and onboarding job tracking.
 */

import { useState, useCallback, useEffect } from 'react';
import { c4Api } from '../api/c4Api.js';

export function useDomainBindings(projectId, isCurrentGeneration, getGeneration) {
  const [domainProfiles, setDomainProfiles] = useState([]);
  const [selectedDomainId, setSelectedDomainId] = useState('domain-ecommerce-c4');
  const [domainReadiness, setDomainReadiness] = useState(null);
  const [domainBindings, setDomainBindings] = useState([]);
  const [selectedBinding, setSelectedBinding] = useState(null);
  const [activeOnboardingJob, setActiveOnboardingJob] = useState(null);
  const [isLoadingDomains, setIsLoadingDomains] = useState(false);
  const [isLoadingReadiness, setIsLoadingReadiness] = useState(false);
  const [isSubmittingJob, setIsSubmittingJob] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  const resetState = useCallback(() => {
    setDomainProfiles([]);
    setDomainReadiness(null);
    setDomainBindings([]);
    setSelectedBinding(null);
    setActiveOnboardingJob(null);
    setIsLoadingDomains(false);
    setIsLoadingReadiness(false);
    setIsSubmittingJob(false);
    setError(null);
    setSuccessMessage(null);
  }, []);

  // Fetch available domain profiles and registered project bindings
  const loadDomainData = useCallback(async () => {
    if (!projectId) return;

    setIsLoadingDomains(true);
    setError(null);
    const currentGen = getGeneration();

    try {
      const [profiles, bindings] = await Promise.all([
        c4Api.listDomains(projectId).catch(() => []),
        c4Api.listDomainBindings(projectId).catch(() => []),
      ]);

      if (!isCurrentGeneration(currentGen)) return;

      setDomainProfiles(profiles);
      setDomainBindings(bindings);

      if (profiles.length > 0) {
        setSelectedDomainId((prevId) => {
          const defaultProfile = profiles.find((p) => p.domain_id === prevId) || profiles[0];
          if (defaultProfile.binding) {
            setSelectedBinding(defaultProfile.binding);
          }
          return defaultProfile.domain_id;
        });
      }
    } catch (err) {
      if (isCurrentGeneration(currentGen)) {
        setError(err.message || 'Failed to load domain profiles.');
      }
    } finally {
      if (isCurrentGeneration(currentGen)) {
        setIsLoadingDomains(false);
      }
    }
  }, [projectId, getGeneration, isCurrentGeneration]);

  // Check domain runtime readiness
  const checkReadiness = useCallback(
    async (domainId, mode = 'SIMULATED') => {
      const targetDomainId = domainId || selectedDomainId;
      if (!projectId || !targetDomainId) return null;

      setIsLoadingReadiness(true);
      setError(null);
      const currentGen = getGeneration();

      try {
        const report = await c4Api.checkDomainReadiness(projectId, targetDomainId, mode);
        if (!isCurrentGeneration(currentGen)) return null;

        setDomainReadiness(report);
        return report;
      } catch (err) {
        if (!isCurrentGeneration(currentGen)) return null;
        setError(err.message || 'Failed to check domain readiness.');
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsLoadingReadiness(false);
        }
      }
    },
    [projectId, selectedDomainId, getGeneration, isCurrentGeneration]
  );

  useEffect(() => {
    if (projectId) {
      loadDomainData();
    }
  }, [projectId, loadDomainData]);

  useEffect(() => {
    if (projectId && selectedDomainId) {
      checkReadiness(selectedDomainId);
    }
  }, [projectId, selectedDomainId, checkReadiness]);

  // Register a new version of a domain binding
  const registerBinding = useCallback(
    async (bindingPayload) => {
      if (!projectId) return null;

      setError(null);
      setSuccessMessage(null);
      const currentGen = getGeneration();

      try {
        const saved = await c4Api.registerDomainBinding(projectId, {
          ...bindingPayload,
          project_id: projectId,
        });

        if (!isCurrentGeneration(currentGen)) return null;

        setDomainBindings((prev) => [saved, ...prev.filter((b) => b.binding_id !== saved.binding_id || b.version !== saved.version)]);
        setSelectedBinding(saved);
        setSuccessMessage(`Domain binding "${saved.binding_id}" (v${saved.version}) registered.`);
        return saved;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Failed to register domain binding.');
        }
        return null;
      }
    },
    [projectId, getGeneration, isCurrentGeneration]
  );

  // Lookup domain binding by ID and version
  const fetchBindingVersion = useCallback(
    async (bindingId, version) => {
      if (!projectId || !bindingId || !version) return null;

      setError(null);
      const currentGen = getGeneration();

      try {
        const binding = await c4Api.getDomainBinding(projectId, bindingId.trim(), Number(version));
        if (!isCurrentGeneration(currentGen)) return null;

        setSelectedBinding(binding);
        setSuccessMessage(`Loaded domain binding "${binding.binding_id}" (v${binding.version}).`);
        return binding;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || `Domain binding "${bindingId}" v${version} not found.`);
        }
        return null;
      }
    },
    [projectId, getGeneration, isCurrentGeneration]
  );

  // Start an onboarding workflow job
  const startOnboarding = useCallback(
    async ({ domainId, artifactId, artifactVersion, bindingId, bindingVersion, providerId, reviewer }) => {
      if (!projectId) return null;

      setIsSubmittingJob(true);
      setError(null);
      setSuccessMessage(null);
      const currentGen = getGeneration();

      try {
        const payload = {
          domain_id: domainId,
          artifact_id: artifactId,
          artifact_version: artifactVersion,
          binding_id: bindingId,
          binding_version: bindingVersion,
          provider_id: providerId || 'offline_mock',
          reviewer: reviewer || 'dev_reviewer',
          is_synthetic_review: false,
        };

        const job = await c4Api.startOnboardingJob(projectId, payload);
        if (!isCurrentGeneration(currentGen)) return null;

        setActiveOnboardingJob(job);
        setSuccessMessage(`Onboarding job ${job.job_id} initiated (${job.status}).`);
        return job;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Failed to start onboarding workflow.');
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsSubmittingJob(false);
        }
      }
    },
    [projectId, getGeneration, isCurrentGeneration]
  );

  // Poll / refresh onboarding job
  const refreshOnboardingJob = useCallback(
    async (jobId) => {
      if (!projectId || !jobId) return null;

      const currentGen = getGeneration();

      try {
        const job = await c4Api.getOnboardingJob(projectId, jobId);
        if (!isCurrentGeneration(currentGen)) return null;

        setActiveOnboardingJob(job);
        return job;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Failed to refresh onboarding job status.');
        }
        return null;
      }
    },
    [projectId, getGeneration, isCurrentGeneration]
  );

  return {
    domainProfiles,
    selectedDomainId,
    setSelectedDomainId,
    domainReadiness,
    domainBindings,
    selectedBinding,
    setSelectedBinding,
    activeOnboardingJob,
    isLoadingDomains,
    isLoadingReadiness,
    isSubmittingJob,
    error,
    setError,
    successMessage,
    setSuccessMessage,
    loadDomainData,
    checkReadiness,
    registerBinding,
    fetchBindingVersion,
    startOnboarding,
    refreshOnboardingJob,
    resetState,
  };
}
