import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Workflow,
  FolderKanban,
  AlertCircle,
  Layers,
  ExternalLink,
  Check,
} from 'lucide-react';
import { useAuth } from '../../../context/AuthContext';
import { useProject } from '../../../context/ProjectContext';
import { projectsApi } from '../../../services/projects';
import { useC2Models } from '../hooks/useC2Models';
import { ModelListView } from '../components/ModelListView';
import { ModelDetailView } from '../components/ModelDetailView';
import { ModelPreparationForm } from '../components/ModelPreparationForm';
import { ValidationReportModal } from '../components/ValidationReportModal';
import { ApprovalModal } from '../components/ApprovalModal';
import { NewDraftModal } from '../components/NewDraftModal';

export const StateAwareWorkflowPage = () => {
  const { user } = useAuth();
  const {
    activeProject,
    activeProjectId,
    isLoadingActive,
    selectActiveProject,
  } = useProject();

  // Role-derived navigation route for Projects workspace
  const isAdmin = String(user?.role || '').toUpperCase() === 'ADMIN';
  const projectsPageRoute = isAdmin ? '/admin/projects' : '/app/projects';

  // Available projects for delegation attempt (read-only list)
  const [availableProjects, setAvailableProjects] = useState([]);
  const [isLoadingAvailable, setIsLoadingAvailable] = useState(false);
  const [sharedSelectionError, setSharedSelectionError] = useState(null);
  const [isDelegating, setIsDelegating] = useState(false);

  const [activeWorkspaceTab, setActiveWorkspaceTab] = useState('models');
  const [showPreparationForm, setShowPreparationForm] = useState(false);
  const [showReportModal, setShowReportModal] = useState(false);
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [showDraftModal, setShowDraftModal] = useState(false);

  // Load authorized projects when no active project is resolved
  useEffect(() => {
    if (!activeProject && user?.id) {
      setIsLoadingAvailable(true);
      projectsApi
        .listProjects({ limit: 10, lifecycle: 'active' })
        .then((res) => {
          setAvailableProjects(res.items || []);
        })
        .catch(() => {
          setAvailableProjects([]);
        })
        .finally(() => {
          setIsLoadingAvailable(false);
        });
    } else {
      setAvailableProjects([]);
      setSharedSelectionError(null);
    }
  }, [activeProject, user?.id]);

  // Clear modal and form state when user identity or active project changes
  useEffect(() => {
    setShowPreparationForm(false);
    setShowReportModal(false);
    setShowApprovalModal(false);
    setShowDraftModal(false);
    setSharedSelectionError(null);
  }, [user?.id, activeProjectId]);

  // Delegate project selection strictly to shared ProjectContext
  const handleDelegateSelectProject = async (projectId) => {
    setSharedSelectionError(null);
    setIsDelegating(true);
    try {
      await selectActiveProject(projectId);
    } catch (err) {
      setSharedSelectionError(err.message || 'Failed to set active project.');
    } finally {
      setIsDelegating(false);
    }
  };

  // Initialize C2 Models hook scoped strictly to shared activeProjectId and userId
  const {
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
    selectModel,
    setSelectedModelSummary,
    validateCurrentModel,
    approveCurrentModel,
    createNewDraft,
    buildCandidateModel,
    createDraftModel,
    clearActionError,
  } = useC2Models(activeProjectId, user?.id);

  // If loading shared project context
  if (isLoadingActive) {
    return (
      <div className="min-h-[400px] flex items-center justify-center">
        <div className="flex flex-col items-center gap-2 text-xs text-slate-500">
          <div className="w-7 h-7 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin" />
          <span>Validating active project context...</span>
        </div>
      </div>
    );
  }

  // If no authoritative project is selected in shared ProjectContext
  if (!activeProject || !activeProjectId) {
    return (
      <div className="space-y-6">
        {/* Title Header */}
        <div className="flex items-center gap-3 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
            <Workflow className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-white leading-tight">
              State-Aware Multi-Step Workflow Testing
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Component 2: Multi-step Extended Finite State Machine (EFSM) Conformance
            </p>
          </div>
        </div>

        {/* Clear No Project Alert Card */}
        <div className="p-8 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 bg-white/60 dark:bg-slate-900/40 text-center space-y-4 max-w-xl mx-auto my-8">
          <div className="w-12 h-12 rounded-2xl bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 mx-auto flex items-center justify-center">
            <FolderKanban className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h2 className="text-base font-semibold text-slate-900 dark:text-white">
              No Authoritative Project Selected
            </h2>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              State-aware reference models, transitions, and test generation are strictly scoped
              to an active project. Please select or register a project in the Projects workspace
              to begin.
            </p>
          </div>

          <div className="pt-2">
            <Link
              to={projectsPageRoute}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-sm transition-colors"
            >
              Go to Projects Workspace
              <ExternalLink className="w-3.5 h-3.5" />
            </Link>
          </div>

          {/* Shared Context Error Notification if actual selection attempt fails */}
          {sharedSelectionError && (
            <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-800 dark:text-rose-200 text-left space-y-1">
              <div className="font-semibold flex items-center gap-1.5">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                <span>Project Selection Failed</span>
              </div>
              <p className="text-[11px] leading-relaxed">{sharedSelectionError}</p>
            </div>
          )}

          {/* Quick Select Authorized Project delegating to shared ProjectContext */}
          {availableProjects.length > 0 && (
            <div className="pt-6 border-t border-slate-200 dark:border-slate-800 text-left space-y-2">
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                Select an Authorized Project:
              </span>
              <div className="space-y-1.5">
                {availableProjects.map((proj) => (
                  <div
                    key={proj.project_id}
                    className="flex items-center justify-between p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-indigo-400 transition-colors"
                  >
                    <div>
                      <div className="text-xs font-semibold text-slate-900 dark:text-white">
                        {proj.name}
                      </div>
                      <div className="text-[10px] font-mono text-slate-400">
                        {proj.project_id} ({proj.domain || 'custom'})
                      </div>
                    </div>
                    <button
                      type="button"
                      disabled={isDelegating}
                      onClick={() => handleDelegateSelectProject(proj.project_id)}
                      className="px-3 py-1.5 text-xs font-medium rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-900 transition-colors flex items-center gap-1 disabled:opacity-50"
                      title="Delegate selection to shared ProjectContext"
                    >
                      <Check className="w-3.5 h-3.5" />
                      Set as Active
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
          {isLoadingAvailable && (
            <div className="text-[11px] text-slate-400">Loading authorized projects...</div>
          )}
        </div>
      </div>
    );
  }

  // Versions for currently selected model
  const currentModelVersions = models.filter(
    (m) => m.model_id === selectedModelSummary?.model_id
  );

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 shadow-sm">
            <Workflow className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-white leading-tight">
              State-Aware Multi-Step Workflow Testing
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Component 2: Multi-step Extended Finite State Machine (EFSM) Conformance
            </p>
          </div>
        </div>

        {/* Active Project Scoping Badge */}
        <div className="flex items-center gap-3 self-start md:self-auto">
          <div className="px-3.5 py-1.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-xs flex items-center gap-2 shadow-xs">
            <FolderKanban className="w-3.5 h-3.5 text-indigo-500" />
            <div>
              <span className="font-semibold text-slate-900 dark:text-white">
                {activeProject.name}
              </span>
              <span className="text-[10px] text-slate-400 font-mono ml-1.5">
                ({activeProjectId})
              </span>
            </div>
            <Link
              to={projectsPageRoute}
              className="text-[11px] text-indigo-600 dark:text-indigo-400 hover:underline ml-1"
              title="Change active project"
            >
              Switch
            </Link>
          </div>
        </div>
      </div>

      {/* Global Errors or Action Errors */}
      {(error || actionError) && (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-800 dark:text-rose-200 flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{error || actionError}</span>
          </div>
          <button
            type="button"
            onClick={clearActionError}
            className="text-xs font-semibold text-rose-700 dark:text-rose-300 hover:underline shrink-0"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Workspace Tabs (Models first, with roadmap indicators for subsequent phases) */}
      <div className="flex items-center border-b border-slate-200 dark:border-slate-800 gap-6">
        <button
          type="button"
          onClick={() => setActiveWorkspaceTab('models')}
          className={`py-3 text-xs font-semibold border-b-2 flex items-center gap-1.5 transition-colors ${
            activeWorkspaceTab === 'models'
              ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
              : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
          }`}
        >
          <Layers className="w-4 h-4" />
          Models Workspace
        </button>

        <span
          className="py-3 text-xs text-slate-400 dark:text-slate-600 flex items-center gap-1.5 cursor-not-allowed"
          title="Test Suites Workspace available in Phase 2"
        >
          <span>Test Suites</span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-400">
            Phase 2
          </span>
        </span>

        <span
          className="py-3 text-xs text-slate-400 dark:text-slate-600 flex items-center gap-1.5 cursor-not-allowed"
          title="Trace Observations available in Phase 3"
        >
          <span>Runtime Traces</span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-400">
            Phase 3
          </span>
        </span>

        <span
          className="py-3 text-xs text-slate-400 dark:text-slate-600 flex items-center gap-1.5 cursor-not-allowed"
          title="Conformance Evaluations available in Phase 4"
        >
          <span>Evaluations</span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-400">
            Phase 4
          </span>
        </span>

        <span
          className="py-3 text-xs text-slate-400 dark:text-slate-600 flex items-center gap-1.5 cursor-not-allowed"
          title="Baselines & Benchmarks available in Phase 5"
        >
          <span>Baselines</span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-400">
            Phase 5
          </span>
        </span>
      </div>

      {/* Main Workspace Body */}
      {showPreparationForm ? (
        <ModelPreparationForm
          projectId={activeProjectId}
          onBuildCandidate={async (input, autoVal) => {
            await buildCandidateModel(input, autoVal);
            setShowPreparationForm(false);
          }}
          onCreateDraft={async (def) => {
            await createDraftModel(def);
            setShowPreparationForm(false);
          }}
          isSubmitting={isBuildingCandidate}
          onCancel={() => setShowPreparationForm(false)}
        />
      ) : (
        <div className="space-y-6">
          {/* Models List Table */}
          <ModelListView
            models={models}
            selectedModelId={selectedModelSummary?.model_id}
            selectedVersion={selectedModelSummary?.version}
            onSelectModel={(mId, ver) => {
              const summary = models.find((m) => m.model_id === mId && m.version === ver);
              setSelectedModelSummary(summary || null);
            }}
            onOpenPreparation={() => setShowPreparationForm(true)}
            isLoading={isLoadingModels}
          />

          {/* Model Detail View */}
          {selectedModelSummary && (
            <div className="pt-2">
              {isLoadingDetail ? (
                <div className="p-12 text-center text-xs text-slate-400 bg-white dark:bg-[#131A26] rounded-2xl border border-slate-200 dark:border-slate-800 flex items-center justify-center gap-2">
                  <div className="w-5 h-5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
                  <span>Loading full model specification and predicates...</span>
                </div>
              ) : (
                <ModelDetailView
                  model={selectedModelDetail || selectedModelSummary}
                  readiness={readiness}
                  validationReport={validationReport}
                  validationHistory={validationHistory}
                  onValidate={validateCurrentModel}
                  onOpenApproval={() => setShowApprovalModal(true)}
                  onOpenNewDraft={() => setShowDraftModal(true)}
                  onOpenReport={() => setShowReportModal(true)}
                  onRefresh={() => selectModel(selectedModelSummary.model_id, selectedModelSummary.version)}
                  isValidating={isValidating}
                  allVersions={currentModelVersions}
                  onSelectVersion={(mId, ver) => {
                    const match = models.find((m) => m.model_id === mId && m.version === ver);
                    setSelectedModelSummary(match || null);
                  }}
                />
              )}
            </div>
          )}
        </div>
      )}

      {/* Modals */}
      <ValidationReportModal
        isOpen={showReportModal}
        onClose={() => setShowReportModal(false)}
        report={validationReport}
        history={validationHistory}
      />

      <ApprovalModal
        isOpen={showApprovalModal}
        onClose={() => setShowApprovalModal(false)}
        model={selectedModelDetail || selectedModelSummary}
        onApprove={approveCurrentModel}
        isApproving={isApproving}
        currentUserEmail={user?.email || ''}
      />

      <NewDraftModal
        isOpen={showDraftModal}
        onClose={() => setShowDraftModal(false)}
        model={selectedModelDetail || selectedModelSummary}
        onCreateDraft={createNewDraft}
        isCreating={isCreatingDraft}
      />
    </div>
  );
};

export default StateAwareWorkflowPage;
