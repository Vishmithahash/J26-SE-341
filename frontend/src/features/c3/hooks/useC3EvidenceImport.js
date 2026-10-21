import { useState, useRef } from 'react';
import { c3Api } from '../api.js';

export const useC3EvidenceImport = () => {
  const [isImporting, setIsImporting] = useState(false);
  const [importStatus, setImportStatus] = useState('idle'); // 'idle' | 'importing' | 'success' | 'error'
  const [importedRecord, setImportedRecord] = useState(null);
  const [importError, setImportError] = useState(null);

  // In-flight guard ref to guarantee zero duplicate submissions even if rapid clicking occurs
  const isSubmittingRef = useRef(false);

  /**
   * Import either matched pair evidence or an execution artifact.
   * Type can be 'pair' or 'execution'.
   */
  const importEvidence = async ({ type = 'pair', projectId, jsonContent }) => {
    if (isSubmittingRef.current) {
      return { success: false, error: 'An import operation is already in progress.' };
    }

    if (!projectId) {
      setImportError('Project ID is required. Please select an active authorized project.');
      setImportStatus('error');
      return { success: false, error: 'Project ID is required.' };
    }

    // 1. Basic size validation (< 2MB)
    const byteLength = new Blob([jsonContent]).size;
    if (byteLength > 2 * 1024 * 1024) {
      const err = 'Artifact exceeds maximum allowable size (2MB limit).';
      setImportError(err);
      setImportStatus('error');
      return { success: false, error: err };
    }

    // 2. Syntax validation
    let parsedData;
    try {
      parsedData = typeof jsonContent === 'string' ? JSON.parse(jsonContent) : jsonContent;
    } catch (parseErr) {
      const err = `Invalid JSON format: ${parseErr.message}`;
      setImportError(err);
      setImportStatus('error');
      return { success: false, error: err };
    }

    isSubmittingRef.current = true;
    setIsImporting(true);
    setImportStatus('importing');
    setImportError(null);
    setImportedRecord(null);

    try {
      let response;
      if (type === 'pair') {
        // Build payload matching MatchedPairImportRequest
        // Can accept { project_id, evidence } or direct MatchedPairEvidence
        const payload = {
          project_id: projectId,
          execution_id: parsedData.execution_id || null,
          evidence: parsedData.evidence || parsedData,
        };
        // Guarantee project_id linkage matches selected project
        if (payload.evidence.project_id && payload.evidence.project_id !== projectId) {
          payload.evidence = { ...payload.evidence, project_id: projectId };
        }
        response = await c3Api.importPair(payload);
      } else {
        // Build payload matching ExecutionArtifactImportRequest
        const payload = {
          ...parsedData,
          project_id: projectId,
        };
        response = await c3Api.importExecution(payload);
      }

      setImportedRecord(response);
      setImportStatus('success');
      setIsImporting(false);
      isSubmittingRef.current = false;
      return { success: true, data: response };
    } catch (err) {
      isSubmittingRef.current = false;
      setIsImporting(false);
      setImportStatus('error');
      const msg = err.message || 'Evidence import failed.';
      setImportError(msg);
      // NOTE: Explicit design rule: Do NOT automatically retry an execution/evidence POST after uncertain response
      return { success: false, error: msg };
    }
  };

  const resetImportState = () => {
    isSubmittingRef.current = false;
    setIsImporting(false);
    setImportStatus('idle');
    setImportedRecord(null);
    setImportError(null);
  };

  return {
    isImporting,
    importStatus,
    importedRecord,
    importError,
    importEvidence,
    resetImportState,
  };
};
