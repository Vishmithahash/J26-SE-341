import React, { useState, useEffect, useRef } from 'react';
import {
  ListChecks,
  Settings,
  Layers,
  PlayCircle,
  BarChart3,
  AlertCircle,
  FolderOpen,
  Lock,
  CheckCircle,
  Info,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useProject } from '../../context/ProjectContext';
import { c1Api } from '../../components/c1/c1Api';
import { ConfigurationEditor } from '../../components/c1/ConfigurationEditor';
import { GenerationPanel } from '../../components/c1/GenerationPanel';
import { CandidateInspector } from '../../components/c1/CandidateInspector';
import { SuiteViewer } from '../../components/c1/SuiteViewer';

export const ToolCallCorrectnessPage = () => {
  const { user } = useAuth();
  const { activeProjectId, activeProject, isLoading: isProjectLoading } = useProject();

  // Navigation state within Component 1 workspace
  const [activeSection, setActiveSection] = useState('setup'); // 'setup', 'test_cases', 'runs', 'results'
  const [testCaseSubTab, setTestCaseSubTab] = useState('generation'); // 'generation', 'candidates', 'suites'

  // Component Data State
  const [configList, setConfigList] = useState([]);
  const [activeConfig, setActiveConfig] = useState(null);
  const [activeJob, setActiveJob] = useState(null);
  const [activeSuite, setActiveSuite] = useState(null);
  const [suitesList, setSuitesList] = useState([]);

  const [isLoadingConfigs, setIsLoadingConfigs] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  // Counter to guard against stale responses from previous project
  const requestCounter = useRef(0);

  // Clear component-local selections when active project changes
  useEffect(() => {
    requestCounter.current += 1;
    const currentToken = requestCounter.current;

    // Reset local states
    setConfigList([]);
    setActiveConfig(null);
    setActiveJob(null);
    setActiveSuite(null);
    setSuitesList([]);
    setErrorMsg(null);
    setActiveSection('setup');

    if (!activeProjectId) {
      return;
    }

    const loadInitialData = async () => {
      setIsLoadingConfigs(true);
      try {
        const [configs, suites] = await Promise.all([
          c1Api.listConfigs(activeProjectId),
          c1Api.listSuites(activeProjectId).catch(() => []),
        ]);

        // Discard late response if project changed in the meantime
        if (currentToken !== requestCounter.current) {
          return;
        }

        setConfigList(configs || []);
        setSuitesList(suites || []);
        if (configs && configs.length > 0) {
          setActiveConfig(configs[0]);
        }
        if (suites && suites.length > 0) {
          setActiveSuite(suites[0]);
        }
      } catch (err) {
        if (currentToken === requestCounter.current) {
          setErrorMsg(err.message || 'Failed to load component configuration.');
        }
      } finally {
        if (currentToken === requestCounter.current) {
          setIsLoadingConfigs(false);
        }
      }
    };

    loadInitialData();
  }, [activeProjectId]);

  // Handle configuration saved/updated
  const handleConfigSaved = (newConfig) => {
    setActiveConfig(newConfig);
    setConfigList((prev) => {
      const idx = prev.findIndex((c) => c.id === newConfig.id);
      if (idx >= 0) {
        const updated = [...prev];
        updated[idx] = newConfig;
        return updated;
      }
      return [newConfig, ...prev];
    });
  };

  // Handle generation job completed
  const handleJobCreated = (job) => {
    setActiveJob(job);
    setTestCaseSubTab('candidates');
  };

  // Handle suite promoted
  const handleSuitePromoted = (suite) => {
    setActiveSuite(suite);
    setSuitesList((prev) => [suite, ...prev]);
    setTestCaseSubTab('suites');
  };

  // Check prerequisites
  const hasConfig = !!activeConfig;
  const hasSuites = suitesList && suitesList.length > 0;

  // Render project unselected empty state
  if (!activeProjectId) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
            <ListChecks className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-white leading-tight">
              Explainable Tool-Call Correctness Testing
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Component 1 Workspace
            </p>
          </div>
        </div>

        <div className="min-h-[380px] flex flex-col items-center justify-center text-center p-8 rounded-2xl border border-dashed border-slate-200 dark:border-slate-800 bg-white/40 dark:bg-slate-900/40 space-y-3">
          <div className="flex items-center justify-center w-12 h-12 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500">
            <FolderOpen className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
              No Active Project Selected
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm">
              Please select a project from the top navigation dropdown or create a project in the Projects workspace before accessing tool-call correctness testing.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Workspace Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
            <ListChecks className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-white leading-tight">
              Explainable Tool-Call Correctness Testing
            </h1>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-xs text-slate-500 dark:text-slate-400">
                Active Project:
              </span>
              <span className="px-2 py-0.5 text-xs font-semibold rounded-md bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200">
                {activeProject?.name || activeProjectId}
              </span>
              {hasConfig && (
                <span className="text-[11px] font-mono text-slate-400">
                  (Config v{activeConfig.version})
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Global Section Tabs */}
        <div className="flex rounded-xl p-1 bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700/60 text-xs">
          <button
            type="button"
            onClick={() => setActiveSection('setup')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
              activeSection === 'setup'
                ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <Settings className="w-3.5 h-3.5" />
            <span>Setup</span>
          </button>

          <button
            type="button"
            onClick={() => {
              if (hasConfig) setActiveSection('test_cases');
            }}
            disabled={!hasConfig}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
              activeSection === 'test_cases'
                ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-xs'
                : !hasConfig
                ? 'opacity-40 cursor-not-allowed text-slate-400'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Test Cases</span>
            {!hasConfig && <Lock className="w-2.5 h-2.5" />}
          </button>

          <button
            type="button"
            onClick={() => {
              if (hasSuites) setActiveSection('runs');
            }}
            disabled={!hasSuites}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
              activeSection === 'runs'
                ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-xs'
                : !hasSuites
                ? 'opacity-40 cursor-not-allowed text-slate-400'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <PlayCircle className="w-3.5 h-3.5" />
            <span>Runs</span>
            {!hasSuites && <Lock className="w-2.5 h-2.5" />}
          </button>

          <button
            type="button"
            onClick={() => {
              if (hasSuites) setActiveSection('results');
            }}
            disabled={!hasSuites}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
              activeSection === 'results'
                ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-xs'
                : !hasSuites
                ? 'opacity-40 cursor-not-allowed text-slate-400'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span>Results</span>
            {!hasSuites && <Lock className="w-2.5 h-2.5" />}
          </button>
        </div>
      </div>

      {/* Global Error Banner */}
      {errorMsg && (
        <div className="flex items-center gap-2 p-3 text-xs rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-300">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* SECTION 1: SETUP (Configuration) */}
      {activeSection === 'setup' && (
        <div className="space-y-4">
          <ConfigurationEditor
            projectId={activeProjectId}
            activeConfig={activeConfig}
            configList={configList}
            onSelectConfig={(config) => setActiveConfig(config)}
            onSaveSuccess={handleConfigSaved}
          />
        </div>
      )}

      {/* SECTION 2: TEST CASES (Generation, Candidate Inspection, Suites) */}
      {activeSection === 'test_cases' && (
        <div className="space-y-6">
          {/* Sub-tab Navigation */}
          <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-2">
            <div className="flex space-x-2">
              <button
                type="button"
                onClick={() => setTestCaseSubTab('generation')}
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                  testCaseSubTab === 'generation'
                    ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                1. Test Case Generation
              </button>
              <button
                type="button"
                onClick={() => setTestCaseSubTab('candidates')}
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                  testCaseSubTab === 'candidates'
                    ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                2. Candidate Inspection {activeJob && '•'}
              </button>
              <button
                type="button"
                onClick={() => setTestCaseSubTab('suites')}
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                  testCaseSubTab === 'suites'
                    ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                3. Accepted Suites ({suitesList.length})
              </button>
            </div>
          </div>

          {testCaseSubTab === 'generation' && (
            <GenerationPanel
              projectId={activeProjectId}
              activeConfig={activeConfig}
              onJobSuccess={handleJobCreated}
            />
          )}

          {testCaseSubTab === 'candidates' && (
            <>
              {activeJob ? (
                <CandidateInspector
                  projectId={activeProjectId}
                  jobId={activeJob.job_id}
                  generationSummary={activeJob.summary}
                  onSuitePromoted={handleSuitePromoted}
                />
              ) : (
                <div className="p-8 text-center rounded-xl border border-dashed border-slate-200 dark:border-slate-800 text-slate-400 text-xs space-y-2">
                  <div>No generation run active in this session.</div>
                  <button
                    type="button"
                    onClick={() => setTestCaseSubTab('generation')}
                    className="text-indigo-600 dark:text-indigo-400 font-semibold hover:underline"
                  >
                    Go to Generation Panel to generate candidate cases
                  </button>
                </div>
              )}
            </>
          )}

          {testCaseSubTab === 'suites' && (
            <SuiteViewer
              projectId={activeProjectId}
              activeSuite={activeSuite}
              onSelectSuite={(suite) => setActiveSuite(suite)}
            />
          )}
        </div>
      )}

      {/* SECTION 3: RUNS (Execution) */}
      {activeSection === 'runs' && (
        <div className="p-8 text-center rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3">
          <div className="flex items-center justify-center w-12 h-12 rounded-full bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 mx-auto">
            <PlayCircle className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">
              Suite Execution Sandbox
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 max-w-md mx-auto">
              Test execution runs require an accepted frozen suite ({suitesList.length} suite(s) available). In Phase 1, test generation and suite locking are verified. Live agent execution and trace capture will execute in Phase 2.
            </p>
          </div>
        </div>
      )}

      {/* SECTION 4: RESULTS (Correctness Evaluation) */}
      {activeSection === 'results' && (
        <div className="p-8 text-center rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3">
          <div className="flex items-center justify-center w-12 h-12 rounded-full bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 mx-auto">
            <BarChart3 className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-bold text-slate-900 dark:text-white">
              Tool-Call Correctness Results &amp; Explanations
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 max-w-md mx-auto">
              Correctness evaluation results, evidence-linked explanations, and diagnosis reports will be populated after executing test suites in the Runs section.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default ToolCallCorrectnessPage;
