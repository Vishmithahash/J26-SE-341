import React, { useState, useEffect } from 'react';
import { useNavigate, useParams, Link, useLocation } from 'react-router-dom';
import {
  ArrowLeft,
  Server,
  Bot,
  FileCode,
  AlertCircle,
  Check,
  Plus,
  Trash2,
  Info,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { projectsApi, DOMAINS, ENVIRONMENTS, INPUT_CATEGORIES } from '../../services/projects';

export const ProjectFormPage = () => {
  const { projectId } = useParams();
  const isEdit = Boolean(projectId);
  const navigate = useNavigate();
  const location = useLocation();
  const basePath = location.pathname.startsWith('/admin') ? '/admin' : '/app';

  // Form State
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [domain, setDomain] = useState('custom');
  const [environment, setEnvironment] = useState('development');
  const [backendBaseUrl, setBackendBaseUrl] = useState('');
  const [backendHealthUrl, setBackendHealthUrl] = useState('');
  const [agentEndpoint, setAgentEndpoint] = useState('');
  const [agentHealthUrl, setAgentHealthUrl] = useState('');
  const [repositoryUrl, setRepositoryUrl] = useState('');
  const [expectedVersion, setExpectedVersion] = useState(null);

  // Progressive Disclosure Toggles
  const [showAgentConfig, setShowAgentConfig] = useState(false);
  const [showInitialInputs, setShowInitialInputs] = useState(false);

  // Initial inputs (only for create)
  const [initialInputs, setInitialInputs] = useState([]);

  // Loading & Error states
  const [isLoading, setIsLoading] = useState(isEdit);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [validationErrors, setValidationErrors] = useState({});

  useEffect(() => {
    if (isEdit) {
      const loadProject = async () => {
        setIsLoading(true);
        setError(null);
        try {
          const res = await projectsApi.getProject(projectId);
          const p = res.project;
          setName(p.name || '');
          setDescription(p.description || '');
          setDomain(p.domain || 'custom');
          setEnvironment(p.environment || 'development');
          setBackendBaseUrl(p.backend_base_url || '');
          setBackendHealthUrl(p.backend_health_url || '');
          setAgentEndpoint(p.agent_endpoint || '');
          setAgentHealthUrl(p.agent_health_url || '');
          setRepositoryUrl(p.repository_url || '');
          setExpectedVersion(p.configuration_version);

          if (p.agent_endpoint || p.agent_health_url) {
            setShowAgentConfig(true);
          }
        } catch (err) {
          setError(err.message || 'Failed to load project details.');
        } finally {
          setIsLoading(false);
        }
      };
      loadProject();
    }
  }, [isEdit, projectId]);

  const validateUrl = (url, fieldName, required = false) => {
    if (!url || !url.trim()) {
      if (required) return `${fieldName} is required.`;
      return null;
    }
    const trimmed = url.trim();
    if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
      return `${fieldName} must start with http:// or https://`;
    }
    try {
      const parsed = new URL(trimmed);
      if (parsed.username || parsed.password) {
        return `${fieldName} must not contain embedded credentials (username:password).`;
      }
    } catch {
      return `${fieldName} is not a valid URL.`;
    }
    return null;
  };

  const handleAddInputRow = () => {
    setInitialInputs((prev) => [
      ...prev,
      {
        category: 'requirements',
        label: '',
        reference_location: '',
        version: '1.0.0',
      },
    ]);
  };

  const handleRemoveInputRow = (index) => {
    setInitialInputs((prev) => prev.filter((_, idx) => idx !== index));
  };

  const handleInputRowChange = (index, field, value) => {
    setInitialInputs((prev) =>
      prev.map((row, idx) => (idx === index ? { ...row, [field]: value } : row))
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setValidationErrors({});

    // Client-side validations
    const errors = {};
    if (!name.trim()) errors.name = 'Application name is required.';

    const backendBaseErr = validateUrl(backendBaseUrl, 'Backend Base URL', true);
    if (backendBaseErr) errors.backendBaseUrl = backendBaseErr;

    const backendHealthErr = validateUrl(backendHealthUrl, 'Backend Health Check URL', true);
    if (backendHealthErr) errors.backendHealthUrl = backendHealthErr;

    if (agentEndpoint) {
      const agentErr = validateUrl(agentEndpoint, 'Agent Endpoint URL', false);
      if (agentErr) errors.agentEndpoint = agentErr;
    }
    if (agentHealthUrl) {
      const agentHealthErr = validateUrl(agentHealthUrl, 'Agent Health Check URL', false);
      if (agentHealthErr) errors.agentHealthUrl = agentHealthErr;
    }

    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      return;
    }

    setIsSubmitting(true);
    try {
      if (isEdit) {
        const payload = {
          name: name.trim(),
          description: description.trim() || null,
          domain,
          environment,
          backend_base_url: backendBaseUrl.trim(),
          backend_health_url: backendHealthUrl.trim(),
          agent_endpoint: agentEndpoint.trim() || null,
          agent_health_url: agentHealthUrl.trim() || null,
          repository_url: repositoryUrl.trim() || null,
          expected_version: expectedVersion,
        };
        await projectsApi.updateProject(projectId, payload);
        navigate(`${basePath}/projects/${projectId}`);
      } else {
        const payload = {
          name: name.trim(),
          description: description.trim() || null,
          domain,
          environment,
          backend_base_url: backendBaseUrl.trim(),
          backend_health_url: backendHealthUrl.trim(),
          agent_endpoint: agentEndpoint.trim() || null,
          agent_health_url: agentHealthUrl.trim() || null,
          repository_url: repositoryUrl.trim() || null,
          initial_inputs: initialInputs.filter((i) => i.label.trim() && i.reference_location.trim()),
        };
        const res = await projectsApi.createProject(payload);
        navigate(`${basePath}/projects/${res.project_id}`);
      }
    } catch (err) {
      setError(err.message || 'Failed to save project.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Back button and page title */}
      <div>
        <Link
          to={`${basePath}/projects`}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 mb-3"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Projects Workspace</span>
        </Link>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
          {isEdit ? 'Edit Application Configuration' : 'Register New Application'}
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Save application identity, documented non-mutating health endpoints, and versioned input references.
        </p>
      </div>

      {/* Global Error Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-sm flex items-start gap-3">
          <AlertCircle className="w-5 h-5 shrink-0 text-rose-600 dark:text-rose-400 mt-0.5" />
          <div>
            <p className="font-semibold">Unable to save application</p>
            <p className="mt-0.5 text-xs">{error}</p>
          </div>
        </div>
      )}

      {/* Main Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Section 1: Basic Information */}
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
          <h2 className="text-base font-bold text-slate-900 dark:text-white pb-3 border-b border-slate-100 dark:border-slate-800">
            1. Application Identity
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Application Name <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., E-Commerce Platform Core"
                className={`w-full px-3.5 py-2 rounded-xl text-sm bg-slate-50 dark:bg-slate-800 border ${
                  validationErrors.name ? 'border-rose-500 ring-1 ring-rose-500' : 'border-slate-200 dark:border-slate-700'
                } text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/30`}
              />
              {validationErrors.name && (
                <p className="mt-1 text-xs text-rose-600">{validationErrors.name}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Domain
              </label>
              <select
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
              >
                {DOMAINS.map((d) => (
                  <option key={d.value} value={d.value}>
                    {d.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Target Environment
              </label>
              <select
                value={environment}
                onChange={(e) => setEnvironment(e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
              >
                {ENVIRONMENTS.map((env) => (
                  <option key={env.value} value={env.value}>
                    {env.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Description (Optional)
              </label>
              <textarea
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief summary of application purpose, scope, or testing goals..."
                className="w-full px-3.5 py-2 rounded-xl text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
              />
            </div>

            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Source Repository URL (Optional)
              </label>
              <input
                type="text"
                value={repositoryUrl}
                onChange={(e) => setRepositoryUrl(e.target.value)}
                placeholder="https://github.com/org/repo"
                className="w-full px-3.5 py-2 rounded-xl text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
              />
            </div>
          </div>
        </div>

        {/* Section 2: Backend Connection Configuration */}
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
            <Server className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            <h2 className="text-base font-bold text-slate-900 dark:text-white">
              2. Backend Connection Endpoints
            </h2>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 text-xs text-slate-600 dark:text-slate-300 leading-relaxed flex items-start gap-2.5">
            <Info className="w-4 h-4 text-indigo-500 shrink-0 mt-0.5" />
            <div>
              <strong>Safe Outbound Connection Policy:</strong> Localhost refers to the machine running the QA framework backend. Outbound probes use non-mutating HTTP GET with bounded timeouts and SSRF destination filtering. Embedded credentials in URLs are blocked.
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Backend Base URL <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                value={backendBaseUrl}
                onChange={(e) => setBackendBaseUrl(e.target.value)}
                placeholder="http://localhost:8000"
                className={`w-full px-3.5 py-2 rounded-xl text-sm font-mono bg-slate-50 dark:bg-slate-800 border ${
                  validationErrors.backendBaseUrl ? 'border-rose-500 ring-1 ring-rose-500' : 'border-slate-200 dark:border-slate-700'
                } text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/30`}
              />
              {validationErrors.backendBaseUrl && (
                <p className="mt-1 text-xs text-rose-600">{validationErrors.backendBaseUrl}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Documented Backend Health Check URL <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                value={backendHealthUrl}
                onChange={(e) => setBackendHealthUrl(e.target.value)}
                placeholder="http://localhost:8000/health"
                className={`w-full px-3.5 py-2 rounded-xl text-sm font-mono bg-slate-50 dark:bg-slate-800 border ${
                  validationErrors.backendHealthUrl ? 'border-rose-500 ring-1 ring-rose-500' : 'border-slate-200 dark:border-slate-700'
                } text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/30`}
              />
              {validationErrors.backendHealthUrl && (
                <p className="mt-1 text-xs text-rose-600">{validationErrors.backendHealthUrl}</p>
              )}
            </div>
          </div>
        </div>

        {/* Section 3: Agent Connection Configuration (Progressive Disclosure) */}
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
            <div className="flex items-center gap-2">
              <Bot className="w-5 h-5 text-teal-600 dark:text-teal-400" />
              <h2 className="text-base font-bold text-slate-900 dark:text-white">
                3. Agent Connection Endpoints (Optional)
              </h2>
            </div>
            <button
              type="button"
              onClick={() => setShowAgentConfig(!showAgentConfig)}
              className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
            >
              <span>{showAgentConfig ? 'Hide Agent Config' : 'Configure Agent Endpoint'}</span>
              {showAgentConfig ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          </div>

          {showAgentConfig ? (
            <div className="space-y-4 animate-in fade-in">
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Register documented endpoints for an agent service. Do not assume an agent endpoint accepts GET requests; specify its actual documented health endpoint separately.
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Agent Base / Service Endpoint
                  </label>
                  <input
                    type="text"
                    value={agentEndpoint}
                    onChange={(e) => setAgentEndpoint(e.target.value)}
                    placeholder="http://localhost:8001/agent"
                    className="w-full px-3.5 py-2 rounded-xl text-sm font-mono bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                  />
                  {validationErrors.agentEndpoint && (
                    <p className="mt-1 text-xs text-rose-600">{validationErrors.agentEndpoint}</p>
                  )}
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Documented Agent Health Check URL
                  </label>
                  <input
                    type="text"
                    value={agentHealthUrl}
                    onChange={(e) => setAgentHealthUrl(e.target.value)}
                    placeholder="http://localhost:8001/health"
                    className="w-full px-3.5 py-2 rounded-xl text-sm font-mono bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                  />
                  {validationErrors.agentHealthUrl && (
                    <p className="mt-1 text-xs text-rose-600">{validationErrors.agentHealthUrl}</p>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <p className="text-xs text-slate-400">
              Agent connection is currently unconfigured. Click above to add agent URLs if testing an application with a dedicated agent service.
            </p>
          )}
        </div>

        {/* Section 4: Initial Input References (Only for Create) */}
        {!isEdit && (
          <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <FileCode className="w-5 h-5 text-amber-600 dark:text-amber-400" />
                <h2 className="text-base font-bold text-slate-900 dark:text-white">
                  4. Initial Input References (Optional)
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setShowInitialInputs(!showInitialInputs)}
                className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
              >
                <span>{showInitialInputs ? 'Hide References' : 'Add References'}</span>
                {showInitialInputs ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>
            </div>

            {showInitialInputs ? (
              <div className="space-y-4 animate-in fade-in">
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Input references are registration records only (e.g., paths, URLs, or manifests). They are never cloned, executed, or automatically parsed.
                </p>

                {initialInputs.map((row, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 grid grid-cols-1 sm:grid-cols-12 gap-3 items-center"
                  >
                    <div className="sm:col-span-3">
                      <select
                        value={row.category}
                        onChange={(e) => handleInputRowChange(idx, 'category', e.target.value)}
                        className="w-full px-2.5 py-1.5 rounded-lg text-xs bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200"
                      >
                        {INPUT_CATEGORIES.map((c) => (
                          <option key={c.value} value={c.value}>
                            {c.label}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="sm:col-span-3">
                      <input
                        type="text"
                        value={row.label}
                        onChange={(e) => handleInputRowChange(idx, 'label', e.target.value)}
                        placeholder="Label (e.g., OpenAPI Spec)"
                        className="w-full px-2.5 py-1.5 rounded-lg text-xs bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200"
                      />
                    </div>

                    <div className="sm:col-span-4">
                      <input
                        type="text"
                        value={row.reference_location}
                        onChange={(e) => handleInputRowChange(idx, 'reference_location', e.target.value)}
                        placeholder="Location / path / URL"
                        className="w-full px-2.5 py-1.5 rounded-lg text-xs font-mono bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200"
                      />
                    </div>

                    <div className="sm:col-span-1">
                      <input
                        type="text"
                        value={row.version}
                        onChange={(e) => handleInputRowChange(idx, 'version', e.target.value)}
                        placeholder="1.0.0"
                        className="w-full px-2 py-1.5 rounded-lg text-xs font-mono bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 text-center"
                      />
                    </div>

                    <div className="sm:col-span-1 text-right">
                      <button
                        type="button"
                        onClick={() => handleRemoveInputRow(idx)}
                        className="p-1.5 rounded-lg text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}

                <button
                  type="button"
                  onClick={handleAddInputRow}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/50 hover:bg-indigo-100"
                >
                  <Plus className="w-3.5 h-3.5" /> Add Reference Row
                </button>
              </div>
            ) : (
              <p className="text-xs text-slate-400">
                No initial input references added. References can also be registered at any time from the project details view.
              </p>
            )}
          </div>
        )}

        {/* Form Submit & Cancel Controls */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200 dark:border-slate-800">
          <Link
            to={isEdit ? `${basePath}/projects/${projectId}` : `${basePath}/projects`}
            className="px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 font-medium text-sm hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
          >
            Cancel
          </Link>

          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 text-white font-medium text-sm hover:bg-indigo-700 active:bg-indigo-800 shadow-sm shadow-indigo-500/20 disabled:opacity-50 transition-colors"
          >
            {isSubmitting ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Saving...</span>
              </>
            ) : (
              <>
                <Check className="w-4 h-4" />
                <span>{isEdit ? 'Save Application Changes' : 'Register Application'}</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
