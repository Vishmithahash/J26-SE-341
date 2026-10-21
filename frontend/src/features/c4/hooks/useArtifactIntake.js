/**
 * Component 4 (C4) - Artifact Intake Hook
 * Manages intake form, plain-text/JSON file uploads, registered artifact versions, and ID/version lookup.
 */

import { useState, useCallback } from 'react';
import { c4Api } from '../api/c4Api.js';
import { ARTIFACT_KINDS } from '../api/types.js';

export function useArtifactIntake(projectId, isCurrentGeneration, getGeneration) {
  const [artifacts, setArtifacts] = useState([]);
  const [selectedArtifact, setSelectedArtifact] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isFetching, setIsFetching] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  const resetState = useCallback(() => {
    setArtifacts([]);
    setSelectedArtifact(null);
    setIsSubmitting(false);
    setIsFetching(false);
    setError(null);
    setSuccessMessage(null);
  }, []);

  const registerArtifact = useCallback(
    async ({ artifactId, artifactKind, rawContent, metadata = {} }) => {
      if (!projectId) {
        setError('No active project selected.');
        return null;
      }

      if (!artifactId || !artifactId.trim()) {
        setError('Artifact ID is required.');
        return null;
      }

      if (!rawContent || !rawContent.trim()) {
        setError('Artifact content cannot be empty.');
        return null;
      }

      setIsSubmitting(true);
      setError(null);
      setSuccessMessage(null);
      const currentGen = getGeneration();

      try {
        const payload = {
          artifact_id: artifactId.trim(),
          artifact_kind: artifactKind || ARTIFACT_KINDS.POLICY_DOCUMENT,
          raw_content: rawContent,
          metadata: {
            ...metadata,
            source_format: 'text/plain',
          },
        };

        const record = await c4Api.registerArtifact(projectId, payload);

        if (!isCurrentGeneration(currentGen)) {
          return null; // Stale response discarded
        }

        setArtifacts((prev) => {
          const filtered = prev.filter(
            (a) => !(a.artifact_id === record.artifact_id && a.version === record.version)
          );
          return [record, ...filtered];
        });
        setSelectedArtifact(record);
        setSuccessMessage(`Artifact "${record.artifact_id}" (v${record.version}) successfully registered.`);
        return record;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || 'Failed to register artifact.');
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsSubmitting(false);
        }
      }
    },
    [projectId, getGeneration, isCurrentGeneration]
  );

  const fetchArtifactVersion = useCallback(
    async (artifactId, version) => {
      if (!projectId || !artifactId || !version) return null;

      setIsFetching(true);
      setError(null);
      const currentGen = getGeneration();

      try {
        const record = await c4Api.getArtifact(projectId, artifactId.trim(), Number(version));
        if (!isCurrentGeneration(currentGen)) return null;

        setArtifacts((prev) => {
          const filtered = prev.filter(
            (a) => !(a.artifact_id === record.artifact_id && a.version === record.version)
          );
          return [record, ...filtered];
        });
        setSelectedArtifact(record);
        setSuccessMessage(`Retrieved artifact "${record.artifact_id}" (v${record.version}).`);
        return record;
      } catch (err) {
        if (isCurrentGeneration(currentGen)) {
          setError(err.message || `Artifact "${artifactId}" v${version} not found.`);
        }
        return null;
      } finally {
        if (isCurrentGeneration(currentGen)) {
          setIsFetching(false);
        }
      }
    },
    [projectId, getGeneration, isCurrentGeneration]
  );

  return {
    artifacts,
    selectedArtifact,
    setSelectedArtifact,
    isSubmitting,
    isFetching,
    error,
    setError,
    successMessage,
    setSuccessMessage,
    registerArtifact,
    fetchArtifactVersion,
    resetState,
  };
}
