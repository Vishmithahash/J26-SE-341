import { useState, useCallback, useRef } from 'react';
import { c3Api } from '../api.js';

export const useC3ValidationGeneration = () => {
  const [isValidating, setIsValidating] = useState(false);
  const [validationResult, setValidationResult] = useState(null);
  const [validationError, setValidationError] = useState(null);

  const [isGenerating, setIsGenerating] = useState(false);
  const [generationResult, setGenerationResult] = useState(null);
  const [generationError, setGenerationError] = useState(null);

  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState('UNSAVED'); // 'UNSAVED' | 'SAVING' | 'SAVED' | 'FAILED'
  const [savedSuite, setSavedSuite] = useState(null);
  const [saveError, setSaveError] = useState(null);

  const validateCounterRef = useRef(0);
  const generateCounterRef = useRef(0);

  const validateCase = useCallback(async (payload) => {
    const thisSeq = ++validateCounterRef.current;
    setIsValidating(true);
    setValidationError(null);

    try {
      const res = await c3Api.validateCase(payload);
      if (thisSeq === validateCounterRef.current) {
        setValidationResult(res);
        setIsValidating(false);
        return res;
      }
    } catch (err) {
      if (thisSeq === validateCounterRef.current) {
        setValidationError(err.message || 'Static validation request failed.');
        setValidationResult(null);
        setIsValidating(false);
        throw err;
      }
    }
  }, []);

  const generateCases = useCallback(async (payload) => {
    const thisSeq = ++generateCounterRef.current;
    setIsGenerating(true);
    setGenerationError(null);
    setSaveStatus('UNSAVED');
    setSavedSuite(null);
    setSaveError(null);

    try {
      const res = await c3Api.generateCases(payload);
      if (thisSeq === generateCounterRef.current) {
        setGenerationResult(res);
        setIsGenerating(false);
        return res;
      }
    } catch (err) {
      if (thisSeq === generateCounterRef.current) {
        setGenerationError(err.message || 'Case generation request failed.');
        setGenerationResult(null);
        setIsGenerating(false);
        throw err;
      }
    }
  }, []);

  const saveSuite = useCallback(async (projectId, frozenSuite) => {
    if (!projectId) {
      setSaveError('Active project is required to save frozen suite.');
      setSaveStatus('FAILED');
      return null;
    }
    if (!frozenSuite) {
      setSaveError('No generated frozen suite to save.');
      setSaveStatus('FAILED');
      return null;
    }

    setIsSaving(true);
    setSaveStatus('SAVING');
    setSaveError(null);

    try {
      const res = await c3Api.importSuite(projectId, frozenSuite);
      setSavedSuite(res);
      setSaveStatus('SAVED');
      setIsSaving(false);
      return res;
    } catch (err) {
      const msg = err.message || 'Failed to save frozen suite.';
      setSaveError(msg);
      setSaveStatus('FAILED');
      setIsSaving(false);
      throw err;
    }
  }, []);

  const resetAll = useCallback(() => {
    setValidationResult(null);
    setValidationError(null);
    setGenerationResult(null);
    setGenerationError(null);
    setSaveStatus('UNSAVED');
    setSavedSuite(null);
    setSaveError(null);
  }, []);

  return {
    // Validation
    isValidating,
    validationResult,
    validationError,
    validateCase,

    // Generation
    isGenerating,
    generationResult,
    generationError,
    generateCases,

    // Saving
    isSaving,
    saveStatus,
    savedSuite,
    saveError,
    saveSuite,

    // Reset
    resetAll,
  };
};
