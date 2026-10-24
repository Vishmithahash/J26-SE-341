import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link, useLocation } from 'react-router-dom';
import {
  ArrowLeft,
  RefreshCw,
  Edit3,
  PowerOff,
  Archive,
  ArchiveRestore,
  Check,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  Server,
  Bot,
  FileCode,
  History,
  Plus,
  Info,
  Layers,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useProject } from '../../context/ProjectContext';
import {
  projectsApi,
  INPUT_CATEGORIES,
} from '../../services/projects';
import { ConnectionStatusBadge } from '../../components/projects/ConnectionStatusBadge';

export const ProjectDetailPage = () => {
  const { projectId } = useParams();
  const location = useLocation();
  const { user } = useAuth();
  const { activeProjectId, selectActiveProject, clearActiveProject } = useProject();

  const isAdmin = user?.role === 'ADMIN';
  const basePath = location.pathname.startsWith('/admin') ? '/admin' : '/app';

  // Data State
  const [project, setProject] = useState(null);
  const [backendOutcome, setBackendOutcome] = useState(null);
  const [agentOutcome, setAgentOutcome] = useState(null);
  const [inputs, setInputs] = useState([]);
  const [historyItems, setHistoryItems] = useState([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyPage, setHistoryPage] = useState(1);
  const historyPageSize = 10;

  // UI state
  const [isLoading, setIsLoading] = useState(true);
  const [isChecking, setIsChecking] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Modal States
  const [showDisconnectModal, setShowDisconnectModal] = useState(false);
  const [showArchiveModal, setShowArchiveModal] = useState(false);
  const [showRestoreModal, setShowRestoreModal] = useState(false);
  const [showInputModal, setShowInputModal] = useState(false);

  // New Input Form State
  const [newInputCategory, setNewInputCategory] = useState('requirements');
  const [newInputLabel, setNewInputLabel] = useState('');
  const [newInputLocation, setNewInputLocation] = useState('');
  const [newInputVersion, setNewInputVersion] = useState('1.0.0');
  const [isSubmittingInput, setIsSubmittingInput] = useState(false);
  const [inputError, setInputError] = useState(null);

  const loadProjectData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await projectsApi.getProject(projectId);
      setProject(res.project);
      setBackendOutcome(res.backend_check || null);
      setAgentOutcome(res.agent_check || null);

      // Load inputs and history concurrently
      const [inputsRes, historyRes] = await Promise.all([
        projectsApi.getProjectInputs(projectId),
        projectsApi.getProjectHistory(projectId, {
          limit: historyPageSize,
          offset: (historyPage - 1) * historyPageSize,
        }),
      ]);
      setInputs(inputsRes || []);
      setHistoryItems(historyRes.items || []);
      setHistoryTotal(historyRes.total || 0);
    } catch (err) {
      setError(err.message || 'Failed to load project details.');
    } finally {
      setIsLoading(false);
    }
  }, [projectId, historyPage]);

  useEffect(() => {
    loadProjectData();
  }, [loadProjectData]);

  // Handle Triggering Connection Check
  const handleCheckConnection = async () => {
    setIsChecking(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await projectsApi.checkConnection(projectId);
      setProject(res.project);
      setBackendOutcome(res.backend_outcome);
      setAgentOutcome(res.agent_outcome);
      setSuccessMsg(`Connection check completed: ${res.connection_state}. ${res.summary}`);
      // Refresh history to include new check event
      const hist = await projectsApi.getProjectHistory(projectId, {
        limit: historyPageSize,
        offset: (historyPage - 1) * historyPageSize,
      });
      setHistoryItems(hist.items || []);
      setHistoryTotal(hist.total || 0);
    } catch (err) {
      setError(err.message || 'Connection check failed.');
    } finally {
      setIsChecking(false);
    }
  };

  // Handle Disconnect
  const handleDisconnect = async () => {
    try {
      const res = await projectsApi.disconnectProject(projectId);
      setProject(res);
      setShowDisconnectModal(false);
      setSuccessMsg('Application disconnected successfully.');
      loadProjectData();
    } catch (err) {
      setError(err.message || 'Failed to disconnect project.');
      setShowDisconnectModal(false);
    }
  };

  // Handle Archive
  const handleArchive = async () => {
    try {
      const res = await projectsApi.archiveProject(projectId);
      setProject(res);
      setShowArchiveModal(false);
      if (activeProjectId === projectId) {
        clearActiveProject();
      }
      setSuccessMsg('Application archived successfully.');
      loadProjectData();
    } catch (err) {
      setError(err.message || 'Failed to archive project.');
      setShowArchiveModal(false);
    }
  };

  // Handle Restore
  const handleRestore = async () => {
    try {
      const res = await projectsApi.restoreProject(projectId);
      setProject(res);
      setShowRestoreModal(false);
      setSuccessMsg('Application restored to active lifecycle.');
      loadProjectData();
    } catch (err) {
      setError(err.message || 'Failed to restore project.');
      setShowRestoreModal(false);
    }
  };

  // Handle Set Active
  const handleToggleActive = async () => {
    try {
      if (activeProjectId === projectId) {
        clearActiveProject();
        setSuccessMsg('Active project deselected.');
      } else {
        await selectActiveProject(projectId);
        setSuccessMsg(`${project.name} is now the active project.`);
      }
    } catch (err) {
      setError(err.message || 'Failed to update active project.');
    }
  };

  // Handle Add Input Reference
  const handleCreateInput = async (e) => {
    e.preventDefault();
    setInputError(null);
    if (!newInputLabel.trim() || !newInputLocation.trim()) {
      setInputError('Label and Reference Location are required.');
      return;
    }

    setIsSubmittingInput(true);
    try {
      await projectsApi.createProjectInput(projectId, {
        category: newInputCategory,
        label: newInputLabel.trim(),
        reference_location: newInputLocation.trim(),
        version: newInputVersion.trim() || '1.0.0',
      });
      setShowInputModal(false);
      setNewInputLabel('');
      setNewInputLocation('');
      setNewInputVersion('1.0.0');
      setSuccessMsg('Input reference registered successfully.');
      // Reload inputs & history
      const [inputsRes, histRes] = await Promise.all([
        projectsApi.getProjectInputs(projectId),
        projectsApi.getProjectHistory(projectId, {
          limit: historyPageSize,
          offset: (historyPage - 1) * historyPageSize,
        }),
      ]);
      setInputs(inputsRes || []);
      setHistoryItems(histRes.items || []);
      setHistoryTotal(histRes.total || 0);
    } catch (err) {
      setInputError(err.message || 'Failed to register input reference.');
    } finally {
      setIsSubmittingInput(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="p-12 text-center rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
        <h2 className="text-lg font-bold text-slate-900 dark:text-white">Project not found</h2>
        <p className="mt-1 text-xs text-slate-500">The requested application does not exist or access is restricted.</p>
        <Link
          to={`${basePath}/projects`}
          className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Projects
        </Link>
      </div>
    );
  }

  const isActiveProject = activeProjectId === project.project_id;
  const isArchived = project.lifecycle === 'archived';
  const totalHistoryPages = Math.ceil(historyTotal / historyPageSize) || 1;

  const formatDateTime = (iso) => {
    if (!iso) return 'Never';
    try {
      return new Date(iso).toLocaleString(undefined, {
        dateStyle: 'medium',
        timeStyle: 'medium',
      });
    } catch {
      return 'Invalid date';
    }
  };

  return (
    <div className="space-y-6">
      {/* Back Link */}
      <div>
        <Link
          to={`${basePath}/projects`}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Projects Workspace</span>
        </Link>
      </div>

      {/* Notifications */}
      {successMsg && (
        <div className="p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Check className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            <span>{successMsg}</span>
          </div>
          <button
            onClick={() => setSuccessMsg(null)}
            className="text-xs font-semibold hover:underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {error && (
        <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600 dark:text-rose-400" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            className="text-xs font-semibold hover:underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Top Header Card */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col lg:flex-row lg:items-center lg:justify-between gap-5">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <ConnectionStatusBadge state={project.connection_state} />
            {isArchived ? (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wide bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 border border-slate-300 dark:border-slate-700">
                Archived
              </span>
            ) : (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wide bg-teal-50 text-teal-700 dark:bg-teal-950/40 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
                Active Lifecycle
              </span>
            )}
            <span className="px-2 py-0.5 rounded-md text-xs font-mono bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
              v{project.configuration_version}
            </span>
          </div>

          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
            {project.name}
          </h1>

          <div className="flex flex-wrap items-center gap-2 mt-1 text-xs text-slate-400">
            <span className="font-mono text-slate-500 dark:text-slate-400">{project.project_id}</span>
            <span>•</span>
            <span className="capitalize">{project.domain}</span>
            <span>•</span>
            <span className="capitalize font-mono px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
              {project.environment}
            </span>
            {isAdmin && project.owner && (
              <>
                <span>•</span>
                <span>
                  Owner: <strong>{project.owner.name}</strong> ({project.owner.email})
                </span>
              </>
            )}
          </div>

          {project.description && (
            <p className="mt-2 text-xs text-slate-600 dark:text-slate-300 max-w-2xl leading-relaxed">
              {project.description}
            </p>
          )}
        </div>

        {/* Action Buttons Toolbar */}
        <div className="flex flex-wrap items-center gap-2.5">
          {!isArchived && (
            <button
              onClick={handleCheckConnection}
              disabled={isChecking}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-700 active:bg-indigo-800 shadow-sm shadow-indigo-500/20 disabled:opacity-50 transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isChecking ? 'animate-spin' : ''}`} />
              <span>{isChecking ? 'Checking Endpoints...' : 'Check Connection'}</span>
            </button>
          )}

          {!isArchived && (
            <button
              onClick={handleToggleActive}
              className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold border transition-colors ${
                isActiveProject
                  ? 'bg-amber-50 text-amber-700 border-amber-300 dark:bg-amber-950/50 dark:text-amber-300 dark:border-amber-800 hover:bg-amber-100 dark:hover:bg-amber-900/50'
                  : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/50'
              }`}
            >
              {isActiveProject ? <PowerOff className="w-3.5 h-3.5" /> : <Check className="w-3.5 h-3.5" />}
              <span>{isActiveProject ? 'Deactivate Project' : 'Select as Active'}</span>
            </button>
          )}

          {/* Cross-Component Combined Results */}
          <Link
            to={`${basePath}/projects/${projectId}/results`}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 text-xs font-semibold transition-colors"
            title="Inspect cross-component integration results and combined QA reports"
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Combined results</span>
          </Link>

          {!isArchived && (
            <Link
              to={`${basePath}/projects/${projectId}/edit`}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 text-xs font-semibold hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors"
            >
              <Edit3 className="w-3.5 h-3.5 text-slate-400" />
              <span>Edit</span>
            </Link>
          )}

          {!isArchived && (
            <button
              onClick={() => setShowDisconnectModal(true)}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-slate-600 dark:text-slate-400 hover:text-amber-600 dark:hover:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-950/30 text-xs font-semibold transition-colors"
              title="Explicitly set status to DISCONNECTED"
            >
              <PowerOff className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Disconnect</span>
            </button>
          )}

          {isArchived ? (
            <button
              onClick={() => setShowRestoreModal(true)}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-teal-600 text-white text-xs font-semibold hover:bg-teal-700 transition-colors"
            >
              <ArchiveRestore className="w-3.5 h-3.5" />
              <span>Restore Project</span>
            </button>
          ) : (
            <button
              onClick={() => setShowArchiveModal(true)}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-slate-600 dark:text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 text-xs font-semibold transition-colors"
              title="Archive project"
            >
              <Archive className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Archive</span>
            </button>
          )}
        </div>
      </div>

      {/* Connection State Card & Endpoint Probes */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-5">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <Server className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            <h2 className="text-base font-bold text-slate-900 dark:text-white">
              Connection Verification Results
            </h2>
          </div>
          <span className="text-xs text-slate-400">
            Checked Configuration Version: <strong>v{project.configuration_version}</strong>
          </span>
        </div>

        {/* Honest Status Policy Callout */}
        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-xs text-slate-600 dark:text-slate-300 leading-relaxed flex items-start gap-2.5">
          <Info className="w-4 h-4 text-indigo-500 shrink-0 mt-0.5" />
          <div>
            <strong>Honest Endpoint Availability:</strong> A successful connection check establishes health endpoint availability only. It does not prove agent task execution, tool correctness, database correctness, or readiness for all research components. Old check results do not imply continuous live monitoring.
          </div>
        </div>

        {/* Timestamps Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
            <span className="text-slate-400 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5" /> Last Checked:
            </span>
            <span className="font-semibold text-slate-800 dark:text-slate-200">
              {formatDateTime(project.last_check_timestamp)}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
            <span className="text-slate-400 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> Last Successful Check:
            </span>
            <span className="font-semibold text-emerald-600 dark:text-emerald-400">
              {formatDateTime(project.last_successful_check_timestamp)}
            </span>
          </div>
        </div>

        {/* Probes: Backend and Agent */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Backend Probe Result */}
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Server className="w-4 h-4 text-slate-500" />
                <span className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                  Backend Health Endpoint
                </span>
              </div>
              {backendOutcome ? (
                backendOutcome.reachable ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
                    <CheckCircle2 className="w-3 h-3" /> Reachable
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300">
                    <XCircle className="w-3 h-3" /> Unreachable
                  </span>
                )
              ) : (
                <span className="text-[11px] text-slate-400 font-mono">Not Probed Yet</span>
              )}
            </div>

            <div className="space-y-1.5 text-xs">
              <div className="font-mono text-[11px] text-slate-600 dark:text-slate-300 bg-white dark:bg-slate-900 p-2 rounded-lg border border-slate-200 dark:border-slate-700/60 break-all">
                {project.backend_health_url}
              </div>

              {backendOutcome && (
                <div className="pt-2 border-t border-slate-200 dark:border-slate-700/60 space-y-1 text-slate-500 dark:text-slate-400">
                  <div className="flex justify-between">
                    <span>HTTP Status Code:</span>
                    <strong className="text-slate-800 dark:text-slate-200 font-mono">
                      {backendOutcome.status_code || 'N/A'}
                    </strong>
                  </div>
                  <div className="flex justify-between">
                    <span>Round-trip Latency:</span>
                    <strong className="text-slate-800 dark:text-slate-200 font-mono">
                      {backendOutcome.latency_ms ? `${backendOutcome.latency_ms} ms` : 'N/A'}
                    </strong>
                  </div>
                  {backendOutcome.sanitized_error && (
                    <div className="mt-1 p-2 rounded bg-rose-50 dark:bg-rose-950/50 text-rose-700 dark:text-rose-300 text-[11px]">
                      Outcome: {backendOutcome.sanitized_error}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Agent Probe Result */}
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Bot className="w-4 h-4 text-slate-500" />
                <span className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                  Agent Health Endpoint
                </span>
              </div>
              {project.agent_health_url ? (
                agentOutcome ? (
                  agentOutcome.reachable ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
                      <CheckCircle2 className="w-3 h-3" /> Reachable
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300">
                      <XCircle className="w-3 h-3" /> Unreachable
                    </span>
                  )
                ) : (
                  <span className="text-[11px] text-slate-400 font-mono">Not Probed Yet</span>
                )
              ) : (
                <span className="text-[11px] text-slate-400 italic">Not Configured</span>
              )}
            </div>

            <div className="space-y-1.5 text-xs">
              <div className="font-mono text-[11px] text-slate-600 dark:text-slate-300 bg-white dark:bg-slate-900 p-2 rounded-lg border border-slate-200 dark:border-slate-700/60 break-all">
                {project.agent_health_url || 'No separate agent health URL registered.'}
              </div>

              {agentOutcome && (
                <div className="pt-2 border-t border-slate-200 dark:border-slate-700/60 space-y-1 text-slate-500 dark:text-slate-400">
                  <div className="flex justify-between">
                    <span>HTTP Status Code:</span>
                    <strong className="text-slate-800 dark:text-slate-200 font-mono">
                      {agentOutcome.status_code || 'N/A'}
                    </strong>
                  </div>
                  <div className="flex justify-between">
                    <span>Round-trip Latency:</span>
                    <strong className="text-slate-800 dark:text-slate-200 font-mono">
                      {agentOutcome.latency_ms ? `${agentOutcome.latency_ms} ms` : 'N/A'}
                    </strong>
                  </div>
                  {agentOutcome.sanitized_error && (
                    <div className="mt-1 p-2 rounded bg-rose-50 dark:bg-rose-950/50 text-rose-700 dark:text-rose-300 text-[11px]">
                      Outcome: {agentOutcome.sanitized_error}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Input References Section */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <FileCode className="w-5 h-5 text-amber-600 dark:text-amber-400" />
            <div>
              <h2 className="text-base font-bold text-slate-900 dark:text-white">
                Versioned Input References
              </h2>
              <p className="text-xs text-slate-400">
                Registered references to specifications, repositories, schemas, and policies ({inputs.length})
              </p>
            </div>
          </div>

          {!isArchived && (
            <button
              onClick={() => setShowInputModal(true)}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 text-xs font-semibold transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Register Input Reference</span>
            </button>
          )}
        </div>

        {inputs.length === 0 ? (
          <div className="p-8 text-center rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-dashed border-slate-200 dark:border-slate-800">
            <p className="text-xs text-slate-500 dark:text-slate-400">
              No input references registered yet. Register versioned references to OpenAPI specs, requirements, or schemas to track project inputs.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-400 font-semibold uppercase tracking-wider">
                  <th className="py-2.5 px-3">Category</th>
                  <th className="py-2.5 px-3">Label</th>
                  <th className="py-2.5 px-3">Reference Location</th>
                  <th className="py-2.5 px-3">Version</th>
                  <th className="py-2.5 px-3">Registered (UTC)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {inputs.map((inp) => (
                  <tr key={inp.reference_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                    <td className="py-3 px-3 font-medium">
                      <span className="inline-block px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-200 dark:border-amber-800/60">
                        {inp.category}
                      </span>
                    </td>
                    <td className="py-3 px-3 font-semibold text-slate-800 dark:text-slate-200">
                      {inp.label}
                    </td>
                    <td className="py-3 px-3 font-mono text-[11px] text-slate-600 dark:text-slate-400 break-all">
                      {inp.reference_location}
                    </td>
                    <td className="py-3 px-3 font-mono text-slate-700 dark:text-slate-300">
                      v{inp.version}
                    </td>
                    <td className="py-3 px-3 text-slate-400 whitespace-nowrap">
                      {formatDateTime(inp.registered_at_utc)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Append-Only Event History Section */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <History className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            <div>
              <h2 className="text-base font-bold text-slate-900 dark:text-white">
                Append-Only Audit History
              </h2>
              <p className="text-xs text-slate-400">
                Permanent event log tracking configuration changes, checks, and lifecycle events ({historyTotal})
              </p>
            </div>
          </div>
        </div>

        {historyItems.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-400">
            No history recorded yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800 text-slate-400 font-semibold uppercase tracking-wider">
                  <th className="py-2.5 px-3">Timestamp (UTC)</th>
                  <th className="py-2.5 px-3">Event Type</th>
                  <th className="py-2.5 px-3">Version</th>
                  <th className="py-2.5 px-3">Acting User</th>
                  <th className="py-2.5 px-3">State Transition</th>
                  <th className="py-2.5 px-3">Safe Outcome / Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {historyItems.map((item) => (
                  <tr key={item.event_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                    <td className="py-3 px-3 text-slate-500 whitespace-nowrap font-mono text-[11px]">
                      {formatDateTime(item.timestamp_utc)}
                    </td>
                    <td className="py-3 px-3 font-semibold text-slate-800 dark:text-slate-200">
                      <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                        {item.event_type}
                      </span>
                    </td>
                    <td className="py-3 px-3 font-mono text-slate-500">
                      v{item.configuration_version}
                    </td>
                    <td className="py-3 px-3 text-slate-600 dark:text-slate-400">
                      {item.acting_account_email || `User #${item.acting_account_id}`}
                    </td>
                    <td className="py-3 px-3 text-slate-600 dark:text-slate-400">
                      {item.previous_state && item.resulting_state ? (
                        <span className="flex items-center gap-1 font-mono text-[11px]">
                          <span>{item.previous_state.connection_state || item.previous_state.lifecycle || 'Init'}</span>
                          <span>→</span>
                          <strong className="text-slate-900 dark:text-white">
                            {item.resulting_state.connection_state || item.resulting_state.lifecycle}
                          </strong>
                        </span>
                      ) : (
                        <span className="text-slate-400 font-mono text-[11px]">None</span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-slate-500 max-w-xs truncate text-[11px]">
                      {item.safe_details ? JSON.stringify(item.safe_details) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* History Pagination */}
        {totalHistoryPages > 1 && (
          <div className="flex items-center justify-between pt-3 border-t border-slate-100 dark:border-slate-800 text-xs text-slate-500">
            <div>
              Showing {(historyPage - 1) * historyPageSize + 1} to{' '}
              {Math.min(historyPage * historyPageSize, historyTotal)} of {historyTotal} events
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setHistoryPage((p) => Math.max(1, p - 1))}
                disabled={historyPage <= 1}
                className="px-2.5 py-1 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 disabled:opacity-40"
              >
                Previous
              </button>
              <span>
                Page {historyPage} of {totalHistoryPages}
              </span>
              <button
                onClick={() => setHistoryPage((p) => Math.min(totalHistoryPages, p + 1))}
                disabled={historyPage >= totalHistoryPages}
                className="px-2.5 py-1 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Disconnect Confirmation Modal */}
      {showDisconnectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-xs">
          <div className="w-full max-w-md p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400">
                <PowerOff className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white">
                  Disconnect Application
                </h3>
                <p className="text-xs text-slate-500">Set connection state to DISCONNECTED</p>
              </div>
            </div>

            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
              Disconnecting sets the framework status to <strong>DISCONNECTED</strong> and appends an audit event. It does not stop, shut down, or mutate the external application.
            </p>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setShowDisconnectModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                onClick={handleDisconnect}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-amber-600 text-white hover:bg-amber-700"
              >
                Confirm Disconnect
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Archive Confirmation Modal */}
      {showArchiveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-xs">
          <div className="w-full max-w-md p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400">
                <Archive className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white">
                  Archive Project Record
                </h3>
                <p className="text-xs text-slate-500">Move application to archived lifecycle</p>
              </div>
            </div>

            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
              Archived applications cannot be checked for connection or selected as active. Historical audit logs and input references are preserved and the project can be restored at any time.
            </p>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setShowArchiveModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                onClick={handleArchive}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-rose-600 text-white hover:bg-rose-700"
              >
                Confirm Archive
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Restore Confirmation Modal */}
      {showRestoreModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-xs">
          <div className="w-full max-w-md p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-teal-50 dark:bg-teal-950/60 text-teal-600 dark:text-teal-400">
                <ArchiveRestore className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white">
                  Restore Project Record
                </h3>
                <p className="text-xs text-slate-500">Restore application to active lifecycle</p>
              </div>
            </div>

            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
              Restoring this application will re-enable connection health checking and active project selection.
            </p>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setShowRestoreModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                onClick={handleRestore}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-teal-600 text-white hover:bg-teal-700"
              >
                Confirm Restore
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Register Input Reference Modal */}
      {showInputModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-xs">
          <div className="w-full max-w-lg p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl space-y-4">
            <div className="flex items-center gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
              <div className="p-2.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
                <FileCode className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white">
                  Register Input Reference
                </h3>
                <p className="text-xs text-slate-500">Add versioned reference to project inputs</p>
              </div>
            </div>

            {inputError && (
              <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 text-xs">
                {inputError}
              </div>
            )}

            <form onSubmit={handleCreateInput} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Reference Category
                </label>
                <select
                  value={newInputCategory}
                  onChange={(e) => setNewInputCategory(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200"
                >
                  {INPUT_CATEGORIES.map((cat) => (
                    <option key={cat.value} value={cat.value}>
                      {cat.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Descriptive Label <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  value={newInputLabel}
                  onChange={(e) => setNewInputLabel(e.target.value)}
                  placeholder="e.g., OpenAPI 3.1 Spec or Checkout Workflow Model"
                  className="w-full px-3 py-2 rounded-xl text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Reference Location / Identifier <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  value={newInputLocation}
                  onChange={(e) => setNewInputLocation(e.target.value)}
                  placeholder="e.g., docs/openapi.json or https://github.com/org/repo/blob/main/spec.yaml"
                  className="w-full px-3 py-2 rounded-xl text-xs font-mono bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Version
                </label>
                <input
                  type="text"
                  value={newInputVersion}
                  onChange={(e) => setNewInputVersion(e.target.value)}
                  placeholder="1.0.0"
                  className="w-full px-3 py-2 rounded-xl text-xs font-mono bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowInputModal(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingInput}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                  {isSubmittingInput ? 'Registering...' : 'Save Reference'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
