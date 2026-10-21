/**
 * Component 4 (C4) - Artifact Intake Hook
 * Manages intake form, plain-text/JSON file uploads, and registered artifact versions.
 */

import { useState, useCallback } from 'react';
import { c4Api } from '../api/c4Api';
import { ARTIFACT_KINDS } from '../api/types';

export function useArtifactIntake(projectId, isCurrentGeneration, getGeneration) {
  const [artifacts, setArtifacts] = useState([]);
  const [selectedArtifact, setSelectedArtifact] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  const resetState = useCallback(() => {
    setArtifacts([]);
    setSelectedArtifact(null);
    setIsSubmitting(false);
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
          // Replace if same artifact_id and version exist, else prepend
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

  return {
    artifacts,
    selectedArtifact,
    setSelectedArtifact,
    isSubmitting,
    error,
    setError,
    successMessage,
    setSuccessMessage,
    registerArtifact,
    resetState,
  };
}
