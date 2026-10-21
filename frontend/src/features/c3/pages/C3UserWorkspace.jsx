import React, { useState } from 'react';
import {
  RotateCcw,
  Compass,
  Layers,
  Sparkles,
  ShieldCheck,
  Archive,
  Info,
} from 'lucide-react';
import { useProject } from '../../../context/ProjectContext';
import { C3ProjectBanner } from '../components/C3ProjectBanner';
import { C3AuthGapNotice } from '../components/C3AuthGapNotice';
import { C3FaultCatalogViewer } from '../components/C3FaultCatalogViewer';
import { C3InputPreparation } from '../components/C3InputPreparation';
import { C3ValidationPanel } from '../components/C3ValidationPanel';
import { C3GenerationPanel } from '../components/C3GenerationPanel';
import { C3StoredSuitesViewer } from '../components/C3StoredSuitesViewer';
import { useC3ValidationGeneration } from '../hooks/useC3ValidationGeneration';
import {
  DEMO_CANDIDATE_CASE_VALID,
  DEMO_ADAPTER_MANIFEST,
  DEMO_TASK_FIXTURE_METADATA,
  DEMO_RECOVERY_CONTRACT,
  DEMO_GENERATION_POLICY,
} from '../fixtures';

export const C3UserWorkspace = () => {
  const { activeProjectId } = useProject();

  // Shared contract state initialized with standard authoritative defaults
  const [candidateCase, setCandidateCase] = useState({
    ...DEMO_CANDIDATE_CASE_VALID,
    project_id: activeProjectId || 'proj-qa-001',
  });
  const [adapterManifest, setAdapterManifest] = useState(DEMO_ADAPTER_MANIFEST);
  const [taskFixtureMetadata, setTaskFixtureMetadata] = useState(DEMO_TASK_FIXTURE_METADATA);
  const [recoveryContract, setRecoveryContract] = useState(DEMO_RECOVERY_CONTRACT);
  const [generationPolicy, setGenerationPolicy] = useState(DEMO_GENERATION_POLICY);

  const [activeSection, setActiveSection] = useState('prepare'); // 'prepare' | 'catalog' | 'validate' | 'generate' | 'suites'

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
      {/* Page Title & Welcome Banner */}
      <div className="p-6 sm:p-8 rounded-2xl bg-gradient-to-r from-slate-900 to-indigo-950 text-white shadow-sm border border-slate-800">
        <div className="max-w-4xl">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-semibold uppercase tracking-wider mb-3">
            <RotateCcw className="w-3.5 h-3.5" />
            Standard User Workspace
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
            Robustness and Failure Recovery Testing
          </h1>
          <p className="mt-2 text-sm text-slate-300 leading-relaxed">
            Phase 1 Quality Assurance foundation. Formulate declarative candidate fault cases, verify static contract validity, deterministically generate Feasible Frozen Suites, and inspect project test archives.
          </p>
        </div>
      </div>

      {/* Project Banner & Security Notice */}
      <div className="space-y-4">
        <C3ProjectBanner />
        <C3AuthGapNotice />
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
          <span>1. Prepare Inputs</span>
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

      {/* Main Active Section View */}
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

      {activeSection === 'catalog' && (
        <div className="space-y-6">
          <C3FaultCatalogViewer />
        </div>
      )}

      {/* Next Steps and Readiness Blockers */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
        <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
          <Info className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
          <span>Next Steps & Runtime Execution Blockers</span>
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-2">
            <span className="font-semibold text-slate-800 dark:text-slate-200 block">
              1. What is Verified in Phase 1:
            </span>
            <ul className="list-disc list-inside space-y-1 text-slate-600 dark:text-slate-400 pl-1">
              <li>Deterministic metadata consistency (<code className="font-mono">STATIC_VALID</code>).</li>
              <li>Pure generation and bounded permutation search (<code className="font-mono">max_candidates_examined</code>).</li>
              <li>Cryptographic suite digest freezing (<code className="font-mono">SHA-256</code>) and semantic case fingerprints.</li>
              <li>Project-scoped persistence and retrieval for valid suites.</li>
            </ul>
          </div>

          <div className="p-4 rounded-xl bg-amber-50/50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/60 space-y-2">
            <span className="font-semibold text-amber-900 dark:text-amber-200 block">
              2. Active Live Execution Blockers:
            </span>
            <ul className="list-disc list-inside space-y-1 text-amber-800/90 dark:text-amber-300/90 pl-1">
              <li>
                <strong>Target AUT URL:</strong> Live target environment endpoint (<code className="font-mono">NEXACART_AUT_URL</code>) is not deployed in this workspace.
              </li>
              <li>
                <strong>Fixture Reset Key:</strong> Out-of-band database reset facility for clean state guarantees is unconfigured.
              </li>
              <li>
                <strong>Runtime Injector:</strong> Live domain proxy/interceptor is in demonstration mode; live execution halts safely with exit code 2.
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
