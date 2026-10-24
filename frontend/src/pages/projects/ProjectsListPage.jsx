import React, { useState, useEffect, useCallback } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  FolderKanban,
  Plus,
  Search,
  RefreshCw,
  Check,
  ArrowRight,
  User as UserIcon,
  AlertCircle,
  Clock,
  Edit3,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useProject } from '../../context/ProjectContext';
import { projectsApi, CONNECTION_STATES, DOMAINS } from '../../services/projects';
import { ConnectionStatusBadge } from '../../components/projects/ConnectionStatusBadge';

export const ProjectsListPage = () => {
  const { user } = useAuth();
  const { activeProjectId, selectActiveProject, clearActiveProject } = useProject();
  const location = useLocation();
  const isAdmin = user?.role === 'ADMIN';
  const basePath = location.pathname.startsWith('/admin') ? '/admin' : '/app';

  const [projects, setProjects] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const pageSize = 12;

  const [search, setSearch] = useState('');
  const [connectionStateFilter, setConnectionStateFilter] = useState('');
  const [lifecycleFilter, setLifecycleFilter] = useState('active');

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [checkingId, setCheckingId] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  const fetchProjects = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const offset = (page - 1) * pageSize;
      const res = await projectsApi.listProjects({
        limit: pageSize,
        offset,
        search,
        connectionState: connectionStateFilter,
        lifecycle: lifecycleFilter === 'all' ? '' : lifecycleFilter,
      });
      setProjects(res.items || []);
      setTotal(res.total || 0);
    } catch (err) {
      setError(err.message || 'Failed to load projects.');
    } finally {
      setIsLoading(false);
    }
  }, [page, search, connectionStateFilter, lifecycleFilter]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const handleQuickCheck = async (projectId) => {
    setCheckingId(projectId);
    setActionSuccess(null);
    try {
      const res = await projectsApi.checkConnection(projectId);
      setActionSuccess(
        `Connection check completed for ${res.project?.name || 'application'}: ${res.connection_state}`
      );
      // Refresh list to update status and timestamps
      await fetchProjects();
    } catch (err) {
      setError(err.message || 'Connection check failed.');
    } finally {
      setCheckingId(null);
    }
  };

  const handleToggleActive = async (projectId) => {
    try {
      if (activeProjectId === projectId) {
        clearActiveProject();
        setActionSuccess('Project deactivated from current workspace.');
        return;
      }
      await selectActiveProject(projectId);
      setActionSuccess('Active project updated successfully.');
    } catch (err) {
      setError(err.message || 'Failed to update active project.');
    }
  };

  const totalPages = Math.ceil(total / pageSize) || 1;

  const getDomainLabel = (val) => {
    const found = DOMAINS.find((d) => d.value === val);
    return found ? found.label : val;
  };

  const formatTimestamp = (iso) => {
    if (!iso) return 'Never';
    try {
      return new Date(iso).toLocaleString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return 'Invalid date';
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header & Action */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
              Projects Workspace
            </h1>
            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
              {total}
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Register connected applications, configure health check endpoints, and manage versioned inputs.
          </p>
        </div>

        <Link
          to={`${basePath}/projects/new`}
          className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 text-white font-medium text-sm hover:bg-indigo-700 active:bg-indigo-800 shadow-sm shadow-indigo-500/20 transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>Register Application</span>
        </Link>
      </div>

      {/* Success banner if any */}
      {actionSuccess && (
        <div className="flex items-center justify-between p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200 text-sm animate-in fade-in">
          <div className="flex items-center gap-2">
            <Check className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            <span>{actionSuccess}</span>
          </div>
          <button
            onClick={() => setActionSuccess(null)}
            className="text-xs font-semibold text-emerald-700 dark:text-emerald-300 hover:underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Error banner if any */}
      {error && (
        <div className="flex items-center justify-between p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-sm">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400" />
            <span>{error}</span>
          </div>
          <button
            onClick={fetchProjects}
            className="text-xs font-semibold text-rose-700 dark:text-rose-300 hover:underline flex items-center gap-1"
          >
            <RefreshCw className="w-3 h-3" /> Retry
          </button>
        </div>
      )}

      {/* Search and Filters Bar */}
      <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search by name, ID, or description..."
            className="w-full pl-10 pr-4 py-2 rounded-xl text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-indigo-500"
          />
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Connection state filter */}
          <select
            value={connectionStateFilter}
            onChange={(e) => {
              setConnectionStateFilter(e.target.value);
              setPage(1);
            }}
            className="px-3 py-2 rounded-xl text-xs font-medium bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
          >
            <option value="">All Statuses</option>
            <option value={CONNECTION_STATES.CONNECTED}>Connected</option>
            <option value={CONNECTION_STATES.PARTIAL}>Partial</option>
            <option value={CONNECTION_STATES.UNREACHABLE}>Unreachable</option>
            <option value={CONNECTION_STATES.AUTH_REQUIRED}>Auth Required</option>
            <option value={CONNECTION_STATES.INVALID_CONFIGURATION}>Invalid Config</option>
            <option value={CONNECTION_STATES.DISCONNECTED}>Disconnected</option>
            <option value={CONNECTION_STATES.NOT_CHECKED}>Not Checked</option>
          </select>

          {/* Lifecycle filter */}
          <div className="inline-flex rounded-xl p-0.5 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
            <button
              onClick={() => {
                setLifecycleFilter('active');
                setPage(1);
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                lifecycleFilter === 'active'
                  ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-xs font-semibold'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              Active
            </button>
            <button
              onClick={() => {
                setLifecycleFilter('archived');
                setPage(1);
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                lifecycleFilter === 'archived'
                  ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-xs font-semibold'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              Archived
            </button>
            <button
              onClick={() => {
                setLifecycleFilter('all');
                setPage(1);
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                lifecycleFilter === 'all'
                  ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-xs font-semibold'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              All
            </button>
          </div>

          <button
            onClick={fetchProjects}
            className="p-2 rounded-xl text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700 transition-colors"
            title="Refresh projects list"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Projects List View */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm animate-pulse space-y-4"
            >
              <div className="h-5 bg-slate-200 dark:bg-slate-800 rounded w-2/3" />
              <div className="h-4 bg-slate-100 dark:bg-slate-800 rounded w-1/2" />
              <div className="h-16 bg-slate-50 dark:bg-slate-800/50 rounded-xl" />
              <div className="h-8 bg-slate-100 dark:bg-slate-800 rounded" />
            </div>
          ))}
        </div>
      ) : projects.length === 0 ? (
        <div className="p-12 text-center rounded-2xl bg-white dark:bg-slate-900 border border-dashed border-slate-300 dark:border-slate-800 shadow-sm">
          <div className="w-12 h-12 rounded-2xl bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 flex items-center justify-center mx-auto mb-3">
            <FolderKanban className="w-6 h-6" />
          </div>
          <h3 className="text-base font-semibold text-slate-900 dark:text-white">
            No registered applications found
          </h3>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400 max-w-sm mx-auto">
            {search || connectionStateFilter || lifecycleFilter !== 'active'
              ? 'No projects match your current filters. Try resetting search criteria.'
              : 'Get started by registering an application with its backend and agent health check endpoints.'}
          </p>
          <div className="mt-5">
            <Link
              to={`${basePath}/projects/new`}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-700 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" /> Register Application
            </Link>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {projects.map((proj) => {
            const isActive = activeProjectId === proj.project_id;
            const isArchived = proj.lifecycle === 'archived';

            return (
              <div
                key={proj.project_id}
                className={`relative flex flex-col justify-between p-5 rounded-2xl bg-white dark:bg-slate-900 border transition-all shadow-sm ${
                  isActive
                    ? 'border-indigo-500 ring-2 ring-indigo-500/20'
                    : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700'
                }`}
              >
                {/* Card Top: Badges & Active Pill */}
                <div>
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <ConnectionStatusBadge state={proj.connection_state} size="sm" />
                      {isArchived && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 border border-slate-300 dark:border-slate-700">
                          Archived
                        </span>
                      )}
                    </div>

                    {isActive && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-indigo-50 text-indigo-700 dark:bg-indigo-950/70 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                        <Check className="w-3 h-3" /> Active
                      </span>
                    )}
                  </div>

                  {/* Title and ID */}
                  <h3 className="text-base font-bold text-slate-900 dark:text-white truncate">
                    <Link
                      to={`${basePath}/projects/${proj.project_id}`}
                      className="hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
                    >
                      {proj.name}
                    </Link>
                  </h3>
                  <div className="flex items-center gap-2 mt-1 text-xs text-slate-400">
                    <span className="font-mono">{proj.project_id}</span>
                    <span>•</span>
                    <span className="capitalize">{getDomainLabel(proj.domain)}</span>
                    <span>•</span>
                    <span className="capitalize font-mono text-[11px] px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                      {proj.environment}
                    </span>
                  </div>

                  {proj.description && (
                    <p className="mt-2 text-xs text-slate-600 dark:text-slate-300 line-clamp-2 leading-relaxed">
                      {proj.description}
                    </p>
                  )}

                  {/* Admin info: Owner */}
                  {isAdmin && proj.owner && (
                    <div className="mt-3 flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400 pt-2 border-t border-slate-100 dark:border-slate-800">
                      <UserIcon className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      <span className="truncate">
                        Owner: <strong className="text-slate-700 dark:text-slate-300">{proj.owner.name}</strong> ({proj.owner.email})
                      </span>
                    </div>
                  )}

                  {/* Timestamps */}
                  <div className="mt-4 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800/80 text-xs space-y-1.5">
                    <div className="flex items-center justify-between text-slate-600 dark:text-slate-300">
                      <span className="text-slate-400 flex items-center gap-1">
                        <Clock className="w-3 h-3" /> Last checked:
                      </span>
                      <span className="font-medium">{formatTimestamp(proj.last_check_timestamp)}</span>
                    </div>
                    <div className="flex items-center justify-between text-slate-600 dark:text-slate-300">
                      <span className="text-slate-400">Last successful:</span>
                      <span className="font-medium text-emerald-600 dark:text-emerald-400">
                        {formatTimestamp(proj.last_successful_check_timestamp)}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Card Bottom: Actions */}
                <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    {!isArchived && (
                      <button
                        onClick={() => handleToggleActive(proj.project_id)}
                        className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                          isActive
                            ? 'bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800 hover:bg-amber-100 dark:hover:bg-amber-900/50'
                            : 'bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 dark:hover:bg-indigo-900/50'
                        }`}
                        title={isActive ? 'Deactivate project from workspace' : 'Select as active project'}
                      >
                        {isActive ? 'Deactivate' : 'Set Active'}
                      </button>
                    )}

                    {!isArchived && (
                      <button
                        onClick={() => handleQuickCheck(proj.project_id)}
                        disabled={checkingId === proj.project_id}
                        className="p-1.5 rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700 transition-colors"
                        title="Check connection endpoints"
                      >
                        <RefreshCw
                          className={`w-3.5 h-3.5 ${
                            checkingId === proj.project_id ? 'animate-spin text-indigo-600' : ''
                          }`}
                        />
                      </button>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {!isArchived && (
                      <Link
                        to={`${basePath}/projects/${proj.project_id}/edit`}
                        className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold text-slate-700 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-indigo-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                        title="Edit project URLs and details"
                      >
                        <Edit3 className="w-3.5 h-3.5" />
                        <span>Edit</span>
                      </Link>
                    )}
                    <Link
                      to={`${basePath}/projects/${proj.project_id}`}
                      className="inline-flex items-center gap-1 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:text-indigo-600 dark:hover:text-indigo-400"
                    >
                      <span>Details</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-4 border-t border-slate-200 dark:border-slate-800 text-xs text-slate-500">
          <div>
            Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, total)} of {total} applications
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 disabled:opacity-40 disabled:cursor-not-allowed font-medium text-slate-700 dark:text-slate-300"
            >
              Previous
            </button>
            <span className="font-semibold text-slate-700 dark:text-slate-300">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 disabled:opacity-40 disabled:cursor-not-allowed font-medium text-slate-700 dark:text-slate-300"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
