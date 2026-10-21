import React, { useState, useEffect } from 'react';
import {
  Shield,
  Compass,
  Layers,
  Sparkles,
  ShieldCheck,
  Archive,
  GitCompare,
  UserCheck,
  Building,
  Workflow,
} from 'lucide-react';
import { useAuth } from '../../../context/AuthContext';
import { useProject } from '../../../context/ProjectContext';
import { projectsApi } from '../../../services/projects';
import { C3ProjectBanner } from '../components/C3ProjectBanner';
import { C3AuthGapNotice } from '../components/C3AuthGapNotice';
import { C3FaultCatalogViewer } from '../components/C3FaultCatalogViewer';
import { C3InputPreparation } from '../components/C3InputPreparation';
import { C3ValidationPanel } from '../components/C3ValidationPanel';
import { C3GenerationPanel } from '../components/C3GenerationPanel';
import { C3StoredSuitesViewer } from '../components/C3StoredSuitesViewer';
import { C3TrialsWorkspace } from '../components/C3TrialsWorkspace';
import { C3ResultsWorkspace } from '../components/C3ResultsWorkspace';
import { useC3ValidationGeneration } from '../hooks/useC3ValidationGeneration';
import {
  DEMO_CANDIDATE_CASE_VALID,
  DEMO_ADAPTER_MANIFEST,
  DEMO_TASK_FIXTURE_METADATA,
  DEMO_RECOVERY_CONTRACT,
  DEMO_GENERATION_POLICY,
} from '../fixtures';

export const C3AdminWorkspace = () => {
  const { user } = useAuth();
  const { activeProject, activeProjectId } = useProject();

  const [projectOwnerInfo, setProjectOwnerInfo] = useState(null);
  const [isLoadingOwner, setIsLoadingOwner] = useState(false);
  const [activeSection, setActiveSection] = useState('prepare'); // 'prepare' | 'catalog' | 'validate' | 'generate' | 'suites' | 'trials' | 'results'

  useEffect(() => {
    const handleHash = () => {
      const h = window.location.hash.replace('#', '');
      if (['prepare', 'validate', 'generate', 'suites', 'trials', 'results', 'catalog'].includes(h)) {
        setActiveSection(h);
      }
    };
    handleHash();
    window.addEventListener('hashchange', handleHash);
    return () => window.removeEventListener('hashchange', handleHash);
  }, []);

  // Load project & owner info strictly through authorized projects API
  useEffect(() => {
    let mounted = true;
    if (activeProjectId) {
      setIsLoadingOwner(true);
      projectsApi
        .getProject(activeProjectId)
        .then((res) => {
          if (mounted) {
            setProjectOwnerInfo(res.project?.owner || null);
            setIsLoadingOwner(false);
          }
        })
        .catch(() => {
          if (mounted) {
            setProjectOwnerInfo(null);
            setIsLoadingOwner(false);
          }
        });
    } else {
      setProjectOwnerInfo(null);
      setIsLoadingOwner(false);
    }
    return () => {
      mounted = false;
    };
  }, [activeProjectId]);

  // Shared contract state
  const [candidateCase, setCandidateCase] = useState({
    ...DEMO_CANDIDATE_CASE_VALID,
    project_id: activeProjectId || 'proj-qa-001',
  });
  const [adapterManifest, setAdapterManifest] = useState(DEMO_ADAPTER_MANIFEST);
  const [taskFixtureMetadata, setTaskFixtureMetadata] = useState(DEMO_TASK_FIXTURE_METADATA);
  const [recoveryContract, setRecoveryContract] = useState(DEMO_RECOVERY_CONTRACT);
  const [generationPolicy, setGenerationPolicy] = useState(DEMO_GENERATION_POLICY);

  const {
    isValidating,
    validationResult,
    validationError,
    validateCase,
    isGenerating,
    generationResult,
    generationError,
    generateCases,
    isSaving,
    saveStatus,
    savedSuite,
    saveError,
    saveSuite,
    resetAll,
  } = useC3ValidationGeneration();

  return (
    <div className="space-y-8 pb-12">
      {/* Admin Welcome Banner */}
      <div className="p-6 sm:p-8 rounded-2xl bg-gradient-to-r from-slate-900 to-indigo-950 text-white shadow-sm border border-slate-800">
        <div className="max-w-4xl">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-semibold uppercase tracking-wider mb-3">
            <Shield className="w-3.5 h-3.5" />
            Administrator Workspace
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
            Robustness and Failure Recovery Testing
          </h1>
          <p className="mt-2 text-sm text-slate-300 leading-relaxed">
            Administrative inspection and governance console for Component 3. Audit project configurations, review backend authorization status, inspect operational fault catalogues, and oversee deterministic suite generation within authorized project boundaries.
          </p>
        </div>
      </div>

      {/* Project Banner & Security Notice */}
      <div className="space-y-4">
        <C3ProjectBanner />
        <C3AuthGapNotice />
      </div>

      {/* Administrator Scope & Server Permission Audit Card */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
              <span>Administrative Project Scope & Authorized Owner Details</span>
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Project and owner records are displayed strictly when returned by the authorized backend Projects API.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">Authenticated Role:</span>
            <span className="px-2 py-0.5 rounded text-[11px] font-bold uppercase bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300">
              {user?.role || 'ADMIN'}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2 text-xs">
          {/* Owner details */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-1.5">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
              Authorized Project Owner
            </span>
            {isLoadingOwner ? (
              <div className="h-5 bg-slate-200 dark:bg-slate-700 rounded animate-pulse w-32" />
            ) : projectOwnerInfo ? (
              <div>
                <div className="font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                  <UserCheck className="w-3.5 h-3.5 text-emerald-500" />
                  <span>{projectOwnerInfo.name}</span>
                </div>
                <span className="text-[11px] text-slate-500 dark:text-slate-400 block mt-0.5">
                  {projectOwnerInfo.email}
                </span>
                <code className="text-[10px] text-slate-400 font-mono block mt-1">
                  Owner ID: {projectOwnerInfo.id}
                </code>
              </div>
            ) : activeProject ? (
              <span className="text-slate-500 italic">Owner summary not returned by API</span>
            ) : (
              <span className="text-slate-400">No project selected</span>
            )}
          </div>

          {/* Project Environment */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-1.5">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
              Target Application Metadata
            </span>
            {activeProject ? (
              <div>
                <div className="font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                  <Building className="w-3.5 h-3.5 text-indigo-500" />
                  <span>{activeProject.name}</span>
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  Domain: {activeProject.domain || 'custom'} • Env: {activeProject.environment || 'development'}
                </div>
                <div className="text-[11px] text-slate-400 mt-1 font-mono truncate">
                  Target URL: {activeProject.backend_base_url || 'Unconfigured'}
                </div>
              </div>
            ) : (
              <span className="text-slate-400">No project selected</span>
            )}
          </div>

          {/* Governance & Backend Barriers */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-1.5">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
              Server Permissions & Boundaries
            </span>
            <div className="space-y-1 text-slate-600 dark:text-slate-400">
              <p>
                Server-side role enforcement is operational on <code className="font-mono text-[10px]">/projects</code> and <code className="font-mono text-[10px]">/admin/users</code>.
              </p>
              <p className="text-[11px] text-amber-700 dark:text-amber-400 font-medium">
                C3 persistence endpoints currently do not provide privileged global cross-tenant override. Operations remain scoped to authorized project records.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Section Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2 overflow-x-auto">
        <button
          type="button"
          onClick={() => setActiveSection('prepare')}
          className={`px-3.5 py-2 rounded-xl text-xs font-semibold transition-colors flex items-center gap-2 whitespace-nowrap ${
            activeSection === 'prepare'
              ? 'bg-indigo-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <Compass className="w-3.5 h-3.5" />
          <span>1. Contract Preparation</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveSection('validate')}
          className={`px-3.5 py-2 rounded-xl text-xs font-semibold transition-colors flex items-center gap-2 whitespace-nowrap ${
            activeSection === 'validate'
              ? 'bg-indigo-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>2. Static Validation</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveSection('generate')}
          className={`px-3.5 py-2 rounded-xl text-xs font-semibold transition-colors flex items-center gap-2 whitespace-nowrap ${
            activeSection === 'generate'
              ? 'bg-indigo-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>3. Feasible Generation</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveSection('suites')}
          className={`px-3.5 py-2 rounded-xl text-xs font-semibold transition-colors flex items-center gap-2 whitespace-nowrap ${
            activeSection === 'suites'
              ? 'bg-indigo-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <Archive className="w-3.5 h-3.5" />
          <span>4. Stored Suites</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveSection('trials')}
          className={`px-3.5 py-2 rounded-xl text-xs font-semibold transition-colors flex items-center gap-2 whitespace-nowrap ${
            activeSection === 'trials'
              ? 'bg-teal-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <GitCompare className="w-3.5 h-3.5" />
          <span>5. Matched Trials & Evidence</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveSection('results')}
          className={`px-3.5 py-2 rounded-xl text-xs font-semibold transition-colors flex items-center gap-2 whitespace-nowrap ${
            activeSection === 'results'
              ? 'bg-indigo-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <Workflow className="w-3.5 h-3.5" />
          <span>6. Recovery Results & Reports</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveSection('catalog')}
          className={`px-3.5 py-2 rounded-xl text-xs font-semibold transition-colors flex items-center gap-2 whitespace-nowrap ${
            activeSection === 'catalog'
              ? 'bg-indigo-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Fault Catalogue</span>
        </button>
      </div>

      {/* Main Section Content */}
      {activeSection === 'prepare' && (
        <div className="space-y-6">
          <C3InputPreparation
            candidateCase={candidateCase}
            setCandidateCase={setCandidateCase}
            adapterManifest={adapterManifest}
            setAdapterManifest={setAdapterManifest}
            taskFixtureMetadata={taskFixtureMetadata}
            setTaskFixtureMetadata={setTaskFixtureMetadata}
            recoveryContract={recoveryContract}
            setRecoveryContract={setRecoveryContract}
            generationPolicy={generationPolicy}
            setGenerationPolicy={setGenerationPolicy}
            onReset={resetAll}
          />
        </div>
      )}

      {activeSection === 'validate' && (
        <div className="space-y-6">
          <C3ValidationPanel
            candidateCase={candidateCase}
            adapterManifest={adapterManifest}
            taskFixtureMetadata={taskFixtureMetadata}
            recoveryContract={recoveryContract}
            onValidate={validateCase}
            isValidating={isValidating}
            validationResult={validationResult}
            validationError={validationError}
          />
        </div>
      )}

      {activeSection === 'generate' && (
        <div className="space-y-6">
          <C3GenerationPanel
            taskFixtureMetadata={taskFixtureMetadata}
            adapterManifest={adapterManifest}
            recoveryContract={recoveryContract}
            generationPolicy={generationPolicy}
            onGenerate={generateCases}
            isGenerating={isGenerating}
            generationResult={generationResult}
            generationError={generationError}
            onSaveSuite={saveSuite}
            isSaving={isSaving}
            saveStatus={saveStatus}
            savedSuite={savedSuite}
            saveError={saveError}
          />
        </div>
      )}

      {activeSection === 'suites' && (
        <div className="space-y-6">
          <C3StoredSuitesViewer projectId={activeProjectId} />
        </div>
      )}

      {activeSection === 'trials' && (
        <div className="space-y-6">
          <C3TrialsWorkspace
            projectId={activeProjectId}
            candidateCase={candidateCase}
            adapterManifest={adapterManifest}
            taskFixtureMetadata={taskFixtureMetadata}
            recoveryContract={recoveryContract}
          />
        </div>
      )}

      {activeSection === 'results' && (
        <div className="space-y-6">
          <C3ResultsWorkspace
            projectId={activeProjectId}
            role="ADMIN"
          />
        </div>
      )}

      {activeSection === 'catalog' && (
        <div className="space-y-6">
          <C3FaultCatalogViewer />
        </div>
      )}
    </div>
  );
};
