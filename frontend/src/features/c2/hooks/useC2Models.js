import { useState, useEffect, useRef, useCallback } from 'react';
import { c2Api } from '../api/c2Api';

/**
 * Custom hook managing C2 workflow models, active version selection,
 * validation reports, readiness checks, and stale response protection.
 */
export const useC2Models = (projectId, userId) => {
  const [models, setModels] = useState([]);
  const [selectedModelSummary, setSelectedModelSummary] = useState(null);
  const [selectedModelDetail, setSelectedModelDetail] = useState(null);
  const [validationReport, setValidationReport] = useState(null);
  const [validationHistory, setValidationHistory] = useState([]);
  const [readiness, setReadiness] = useState(null);

  // Loading states
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [isCreatingDraft, setIsCreatingDraft] = useState(false);
  const [isBuildingCandidate, setIsBuildingCandidate] = useState(false);

  // Errors
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);

  // Generation counter to discard stale responses from previous projects or accounts
  const generationRef = useRef(0);

  /**
   * Load all models for the active project
   */
  const loadModels = useCallback(async () => {
    if (!projectId) return;
    const currentGen = ++generationRef.current;
    setIsLoadingModels(true);
    setError(null);

    try {
      const data = await c2Api.listModels(projectId);
      if (currentGen !== generationRef.current) return; // Discard stale response
      setModels(data || []);

      setSelectedModelSummary((prev) => {
        if (!prev) return data?.[0] || null;
        const matching = data.find((m) => m.model_id === prev.model_id && m.version === prev.version);
        return matching || data?.[0] || null;
      });
    } catch (err) {
      if (currentGen !== generationRef.current) return;
      setError(err.message || 'Failed to load workflow models.');
      setModels([]);
    } finally {
      if (currentGen === generationRef.current) {
        setIsLoadingModels(false);
      }
    }
  }, [projectId]);

  // Reset all state when projectId or userId changes
  useEffect(() => {
    generationRef.current += 1;
    setModels([]);
    setSelectedModelSummary(null);
    setSelectedModelDetail(null);
    setValidationReport(null);
    setValidationHistory([]);
    setReadiness(null);
    setError(null);
    setActionError(null);
    setIsLoadingModels(false);
    setIsLoadingDetail(false);
    setIsValidating(false);
    setIsApproving(false);
    setIsCreatingDraft(false);
    setIsBuildingCandidate(false);

    if (projectId && userId) {
      loadModels();
    }
  }, [projectId, userId, loadModels]);

  /**
   * Select a specific model and version, loading full definition, readiness, and latest validation
   */
  const selectModel = useCallback(
    async (modelId, version) => {
      if (!projectId || !modelId || !version) return;
      const currentGen = ++generationRef.current;
      setIsLoadingDetail(true);
      setActionError(null);

      try {
        const [detailData, readinessData, reportsData] = await Promise.all([
          c2Api.getModel(projectId, modelId, version),
          c2Api.getModelReadiness(projectId, modelId, version).catch(() => null),
          c2Api.getValidationReports(projectId, modelId, version).catch(() => []),
        ]);

        if (currentGen !== generationRef.current) return; // Discard stale response

        setSelectedModelDetail(detailData);
        setSelectedModelSummary({
          id: detailData.id,
          project_id: detailData.project_id,
          model_id: detailData.model_id,
          version: detailData.version,
          schema_version: detailData.schema_version,
          name: detailData.name,
          description: detailData.description,
          content_hash: detailData.content_hash,
          lifecycle_status: detailData.lifecycle_status,
          approved_by: detailData.approved_by,
          approved_at: detailData.approved_at,
          created_at: detailData.created_at,
          updated_at: detailData.updated_at,
        });
        setReadiness(readinessData);
        setValidationHistory(reportsData || []);
        setValidationReport(reportsData?.[0] || null);
      } catch (err) {
        if (currentGen !== generationRef.current) return;
        setActionError(err.message || `Failed to load details for model ${modelId} (${version}).`);
      } finally {
        if (currentGen === generationRef.current) {
          setIsLoadingDetail(false);
        }
      }
    },
    [projectId]
  );

  // Automatically fetch detail when selectedModelSummary changes
  const summaryModelId = selectedModelSummary?.model_id;
  const summaryVersion = selectedModelSummary?.version;
  const currentDetailModelId = selectedModelDetail?.model_id;
  const currentDetailVersion = selectedModelDetail?.version;

  useEffect(() => {
    if (summaryModelId && summaryVersion) {
      if (currentDetailModelId !== summaryModelId || currentDetailVersion !== summaryVersion) {
        selectModel(summaryModelId, summaryVersion);
      }
    } else {
      setSelectedModelDetail(null);
      setReadiness(null);
      setValidationReport(null);
      setValidationHistory([]);
    }
  }, [summaryModelId, summaryVersion, currentDetailModelId, currentDetailVersion, selectModel]);

  /**
   * Run structural and semantic validation on currently selected model
   */
  const validateCurrentModel = useCallback(async () => {
    if (!projectId || !selectedModelDetail) return;
    setIsValidating(true);
    setActionError(null);

    try {
      const report = await c2Api.validateModel(
        projectId,
        selectedModelDetail.model_id,
        selectedModelDetail.version
      );
      setValidationReport(report);
      setValidationHistory((prev) => [report, ...prev]);

      // Refresh readiness and model record (lifecycle may have changed to VALIDATED)
      const [updatedDetail, updatedReadiness] = await Promise.all([
        c2Api.getModel(projectId, selectedModelDetail.model_id, selectedModelDetail.version),
        c2Api.getModelReadiness(projectId, selectedModelDetail.model_id, selectedModelDetail.version),
      ]);
      setSelectedModelDetail(updatedDetail);
      setReadiness(updatedReadiness);

      // Also refresh summary in models list
      setModels((prev) =>
        prev.map((m) =>
          m.model_id === updatedDetail.model_id && m.version === updatedDetail.version
            ? { ...m, lifecycle_status: updatedDetail.lifecycle_status }
            : m
        )
      );

      return report;
    } catch (err) {
      setActionError(err.message || 'Validation request failed.');
      throw err;
    } finally {
      setIsValidating(false);
    }
  }, [projectId, selectedModelDetail]);

  /**
   * Explicitly review and approve currently selected model
   */
  const approveCurrentModel = useCallback(
    async ({ reviewerId, reviewBasis, reviewNotes, reviewType }) => {
      if (!projectId || !selectedModelDetail) return;
      setIsApproving(true);
      setActionError(null);

      try {
        const approvedModel = await c2Api.approveModel(
          projectId,
          selectedModelDetail.model_id,
          selectedModelDetail.version,
          { reviewerId, reviewBasis, reviewNotes, reviewType }
        );
        setSelectedModelDetail(approvedModel);

        // Update readiness
        const updatedReadiness = await c2Api.getModelReadiness(
          projectId,
          selectedModelDetail.model_id,
          selectedModelDetail.version
        );
        setReadiness(updatedReadiness);

        // Update list
        setModels((prev) =>
          prev.map((m) =>
            m.model_id === approvedModel.model_id && m.version === approvedModel.version
              ? {
                  ...m,
                  lifecycle_status: approvedModel.lifecycle_status,
                  approved_by: approvedModel.approved_by,
                  approved_at: approvedModel.approved_at,
                }
              : m
          )
        );

        return approvedModel;
      } catch (err) {
        setActionError(err.message || 'Approval blocked or failed.');
        throw err;
      } finally {
        setIsApproving(false);
      }
    },
    [projectId, selectedModelDetail]
  );

  /**
   * Create a new draft version from current version
   */
  const createNewDraft = useCallback(
    async ({ newVersion, description }) => {
      if (!projectId || !selectedModelDetail) return;
      setIsCreatingDraft(true);
      setActionError(null);

      try {
        const newModel = await c2Api.createNewDraftVersion(
          projectId,
          selectedModelDetail.model_id,
          selectedModelDetail.version,
          { newVersion, description }
        );

        // Refresh model list and select new draft
        await loadModels();
        await selectModel(newModel.model_id, newModel.version);
        return newModel;
      } catch (err) {
        setActionError(err.message || 'Failed to create new draft version.');
        throw err;
      } finally {
        setIsCreatingDraft(false);
      }
    },
    [projectId, selectedModelDetail, loadModels, selectModel]
  );

  /**
   * Propose and build candidate model from workflow input
   */
  const buildCandidateModel = useCallback(
    async (workflowInput, autoValidate = true) => {
      if (!projectId) return;
      setIsBuildingCandidate(true);
      setActionError(null);

      try {
        const builtModel = await c2Api.buildCandidateModel(projectId, workflowInput, autoValidate);
        await loadModels();
        await selectModel(builtModel.model_id, builtModel.version);
        return builtModel;
      } catch (err) {
        setActionError(err.message || 'Failed to build candidate model.');
        throw err;
      } finally {
        setIsBuildingCandidate(false);
      }
    },
    [projectId, loadModels, selectModel]
  );

  /**
   * Create direct draft model definition
   */
  const createDraftModel = useCallback(
    async (modelDefinition) => {
      if (!projectId) return;
      setIsBuildingCandidate(true);
      setActionError(null);

      try {
        const createdModel = await c2Api.createDraftModel(projectId, modelDefinition);
        await loadModels();
        await selectModel(createdModel.model_id, createdModel.version);
        return createdModel;
      } catch (err) {
        setActionError(err.message || 'Failed to create draft model.');
        throw err;
      } finally {
        setIsBuildingCandidate(false);
      }
    },
    [projectId, loadModels, selectModel]
  );

  return {
    models,
    selectedModelSummary,
    selectedModelDetail,
    validationReport,
    validationHistory,
    readiness,
    isLoadingModels,
    isLoadingDetail,
    isValidating,
    isApproving,
    isCreatingDraft,
    isBuildingCandidate,
    error,
    actionError,
    loadModels,
    selectModel,
    setSelectedModelSummary,
    validateCurrentModel,
    approveCurrentModel,
    createNewDraft,
    buildCandidateModel,
    createDraftModel,
    clearActionError: () => setActionError(null),
  };
};
