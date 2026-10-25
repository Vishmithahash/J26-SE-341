import React, { useState, useEffect } from 'react';
import {
  Settings,
  Plus,
  Trash2,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Save,
  RotateCcw,
  Sparkles,
  Lock,
  Code,
  ShieldAlert,
  FileCheck,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { c1Api, EVIDENCE_CHANNELS } from './c1Api';

export const ConfigurationEditor = ({
  projectId,
  activeConfig,
  configList,
  onSelectConfig,
  onSaveSuccess,
}) => {
  const [formData, setFormData] = useState(null);
  const [validationResult, setValidationResult] = useState(null);
  const [isValidating, setIsValidating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('agent'); // 'agent', 'tools', 'requirements', 'constraints', 'fixtures', 'trace'
  const [errorMsg, setErrorMsg] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [rawJsonMode, setRawJsonMode] = useState(false);
  const [rawJsonText, setRawJsonText] = useState('');
  const [rawJsonError, setRawJsonError] = useState(null);
  const [isImportingLive, setIsImportingLive] = useState(false);

  // Initialize form state
  useEffect(() => {
    if (activeConfig) {
      setFormData({
        version: activeConfig.version || 1,
        agent_connection_ref: activeConfig.agent_connection_ref || 'agent-connection-default',
        tools: activeConfig.tools ? JSON.parse(JSON.stringify(activeConfig.tools)) : [],
        requirements: activeConfig.requirements ? JSON.parse(JSON.stringify(activeConfig.requirements)) : [],
        tool_constraints: activeConfig.tool_constraints
          ? JSON.parse(JSON.stringify(activeConfig.tool_constraints))
          : { permitted_tools: [], required_tools: [], forbidden_tools: [], max_invocations: {} },
        expectations: activeConfig.expectations ? JSON.parse(JSON.stringify(activeConfig.expectations)) : {},
        synthetic_fixture_refs: activeConfig.synthetic_fixture_refs || [],
        reset_capability: activeConfig.reset_capability || null,
        trace_capabilities: activeConfig.trace_capabilities || [
          { channel: 'AGENT_TRACE', description: 'Agent trace log', enabled: true },
          { channel: 'TOOL_CALL_LOG', description: 'Invocation history', enabled: true },
        ],
        is_immutable: !!activeConfig.is_immutable,
      });
      setRawJsonText(JSON.stringify(activeConfig, null, 2));
      setValidationResult(null);
      setErrorMsg(null);
      setSuccessMsg(null);
    } else {
      // Default blank config
      setFormData({
        version: 1,
        agent_connection_ref: 'agent-connection-default',
        tools: [],
        requirements: [],
        tool_constraints: { permitted_tools: [], required_tools: [], forbidden_tools: [], max_invocations: {} },
        expectations: {},
        synthetic_fixture_refs: [],
        reset_capability: null,
        trace_capabilities: [
          { channel: 'AGENT_TRACE', description: 'Agent trace log', enabled: true },
          { channel: 'TOOL_CALL_LOG', description: 'Invocation history', enabled: true },
        ],
        is_immutable: false,
      });
      setRawJsonText('');
      setValidationResult(null);
    }
  }, [activeConfig]);

  if (!formData) {
    return null;
  }

  const isReadOnly = formData.is_immutable;

  // Load NexaCart Example
  const handleLoadExample = async () => {
    try {
      setErrorMsg(null);
      setSuccessMsg(null);
      const ex = await c1Api.getNexaCartExample(projectId);
      if (ex && ex.config) {
        setFormData({
          ...ex.config,
          version: formData.version || 1,
          is_immutable: false,
        });
        setRawJsonText(JSON.stringify(ex.config, null, 2));
        setSuccessMsg('Loaded NexaCart refund example configuration.');
      }
    } catch (err) {
      setErrorMsg(err.message || 'Failed to load example configuration.');
    }
  };

  // Import Live NexaCart configuration (real tool registry + C1 requirements) as a new version
  const handleImportLiveNexaCart = async () => {
    setIsImportingLive(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const created = await c1Api.importNexaCartLiveConfig(projectId);
      if (onSaveSuccess) onSaveSuccess(created);
      setSuccessMsg(
        `Imported live NexaCart configuration v${created.version}: ${created.tools.length} real agent tools, ${created.requirements.length} requirements.`
      );
    } catch (err) {
      setErrorMsg(err.message || 'Live NexaCart is not reachable.');
    } finally {
      setIsImportingLive(false);
    }
  };

  // Validate Specification
  const handleValidate = async () => {
    setIsValidating(true);
    setErrorMsg(null);
    try {
      let currentPayload = formData;
      if (rawJsonMode) {
        try {
          currentPayload = JSON.parse(rawJsonText);
        } catch {
          setRawJsonError('Invalid JSON format.');
          setIsValidating(false);
          return;
        }
      }
      const summary = await c1Api.validateConfigSpec(projectId, currentPayload);
      setValidationResult(summary);
      if (summary.is_valid) {
        setSuccessMsg('Configuration specification is valid.');
      } else {
        setErrorMsg(`Configuration validation failed with ${summary.errors?.length || 0} error(s).`);
      }
    } catch (err) {
      setErrorMsg(err.message || 'Validation request failed.');
    } finally {
      setIsValidating(false);
    }
  };

  // Save Configuration
  const handleSave = async () => {
    if (isReadOnly) return;
    setIsSaving(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      let payload = formData;
      if (rawJsonMode) {
        try {
          payload = JSON.parse(rawJsonText);
        } catch {
          setRawJsonError('Cannot save invalid JSON.');
          setIsSaving(false);
          return;
        }
      }

      let res;
      if (activeConfig && activeConfig.id && !activeConfig.is_immutable) {
        res = await c1Api.updateConfig(projectId, activeConfig.id, payload);
        setSuccessMsg(`Configuration updated successfully (Version ${res.version}).`);
      } else {
        res = await c1Api.createConfig(projectId, payload);
        setSuccessMsg(`Created new configuration version ${res.version}.`);
      }
      if (onSaveSuccess) {
        onSaveSuccess(res);
      }
    } catch (err) {
      if (err.data && err.data.validation_summary) {
        setValidationResult(err.data.validation_summary);
      }
      setErrorMsg(err.message || 'Failed to save configuration.');
    } finally {
      setIsSaving(false);
    }
  };

  // Tool Handlers
  const handleAddTool = () => {
    const newTool = {
      name: `tool_${formData.tools.length + 1}`,
      description: 'Functional tool description',
      parameters_schema: {
        type: 'object',
        properties: {},
        required: [],
        additional_properties: false,
      },
      code_mapping: null,
    };
    setFormData({ ...formData, tools: [...formData.tools, newTool] });
  };

  const handleUpdateTool = (index, field, value) => {
    const updated = [...formData.tools];
    updated[index] = { ...updated[index], [field]: value };
    setFormData({ ...formData, tools: updated });
  };

  const handleRemoveTool = (index) => {
    const updated = formData.tools.filter((_, i) => i !== index);
    setFormData({ ...formData, tools: updated });
  };

  // Requirement Handlers
  const handleAddRequirement = () => {
    const newReq = {
      req_id: `REQ-${String(formData.requirements.length + 1).padStart(3, '0')}`,
      version: '1.0',
      title: 'Task requirement title',
      description: 'Describe expected agent behaviour and tool invocation criteria.',
      category: 'business_logic',
    };
    setFormData({ ...formData, requirements: [...formData.requirements, newReq] });
  };

  const handleUpdateRequirement = (index, field, value) => {
    const updated = [...formData.requirements];
    updated[index] = { ...updated[index], [field]: value };
    setFormData({ ...formData, requirements: updated });
  };

  const handleRemoveRequirement = (index) => {
    const updated = formData.requirements.filter((_, i) => i !== index);
    setFormData({ ...formData, requirements: updated });
  };

  return (
    <div className="space-y-6">
      {/* Configuration Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
            <Settings className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-slate-900 dark:text-white">
                Project Tool-Call Configuration
              </h2>
              {isReadOnly && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
                  <Lock className="w-3 h-3" /> Frozen / Immutable
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Tool definitions, argument schemas, constraints, and versioned requirements
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          {configList && configList.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500 dark:text-slate-400">Version:</span>
              <select
                className="px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200"
                value={activeConfig?.id || ''}
                onChange={(e) => {
                  const selected = configList.find((c) => c.id === e.target.value);
                  if (selected && onSelectConfig) onSelectConfig(selected);
                }}
              >
                {configList.map((c) => (
                  <option key={c.id} value={c.id}>
                    v{c.version} {c.is_immutable ? '(Frozen)' : '(Mutable)'} - {new Date(c.created_at).toLocaleDateString()}
                  </option>
                ))}
              </select>
            </div>
          )}

          <button
            type="button"
            onClick={handleLoadExample}
            disabled={isReadOnly}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-50"
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-500" />
            Load Synthetic NexaCart Example
          </button>

          <button
            type="button"
            onClick={handleImportLiveNexaCart}
            disabled={isImportingLive}
            title="Create a new configuration version from NexaCart's real agent tools (QA harness) and the NexaCart C1 requirements"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-emerald-300 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 hover:bg-emerald-100 dark:hover:bg-emerald-950/70 disabled:opacity-50"
          >
            <Code className="w-3.5 h-3.5" />
            {isImportingLive ? 'Importing...' : 'Import Live NexaCart'}
          </button>

          <button
            type="button"
            onClick={handleValidate}
            disabled={isValidating}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-indigo-200 dark:border-indigo-800 text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/40 hover:bg-indigo-100 dark:hover:bg-indigo-950/70 disabled:opacity-50"
          >
            <FileCheck className="w-3.5 h-3.5" />
            {isValidating ? 'Validating...' : 'Validate'}
          </button>

          <button
            type="button"
            onClick={handleSave}
            disabled={isReadOnly || isSaving}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm disabled:opacity-50"
          >
            <Save className="w-3.5 h-3.5" />
            {isSaving ? 'Saving...' : 'Save Config'}
          </button>
        </div>
      </div>

      {/* Messages */}
      {successMsg && (
        <div className="flex items-center gap-2 p-3 text-xs rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300">
          <CheckCircle className="w-4 h-4 flex-shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div className="flex items-center gap-2 p-3 text-xs rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-300">
          <XCircle className="w-4 h-4 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Validation Result Banner */}
      {validationResult && (
        <div
          className={`p-4 rounded-xl border ${
            validationResult.is_valid
              ? 'border-emerald-200 dark:border-emerald-900/50 bg-emerald-50/50 dark:bg-emerald-950/20'
              : 'border-red-200 dark:border-red-900/50 bg-red-50/50 dark:bg-red-950/20'
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {validationResult.is_valid ? (
                <CheckCircle className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              ) : (
                <ShieldAlert className="w-4 h-4 text-red-600 dark:text-red-400" />
              )}
              <span className="text-xs font-semibold text-slate-900 dark:text-white">
                Validation Summary: {validationResult.is_valid ? 'Pass (Valid)' : 'Fail (Issues Found)'}
              </span>
            </div>
            <span className="text-xs text-slate-500 dark:text-slate-400">
              Checked Rules: {validationResult.checked_rules?.length || 0}
            </span>
          </div>

          {validationResult.errors && validationResult.errors.length > 0 && (
            <div className="mt-2 space-y-1">
              {validationResult.errors.map((err, idx) => (
                <div key={idx} className="flex items-start gap-1.5 text-xs text-red-700 dark:text-red-400">
                  <XCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                  <span>
                    <strong className="font-semibold">{err.rule_id || 'ERROR'}:</strong> {err.message}
                    {err.path && <span className="text-slate-500 dark:text-slate-400"> (at {err.path})</span>}
                  </span>
                </div>
              ))}
            </div>
          )}

          {validationResult.warnings && validationResult.warnings.length > 0 && (
            <div className="mt-2 space-y-1">
              {validationResult.warnings.map((warn, idx) => (
                <div key={idx} className="flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-400">
                  <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                  <span>
                    <strong className="font-semibold">{warn.rule_id || 'WARN'}:</strong> {warn.message}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Editor Sub-Navigation Tabs */}
      <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800">
        <div className="flex space-x-1">
          {[
            { id: 'agent', label: 'Agent Connection' },
            { id: 'tools', label: `Tools (${formData.tools.length})` },
            { id: 'requirements', label: `Requirements (${formData.requirements.length})` },
            { id: 'constraints', label: 'Constraints & Evidence' },
            { id: 'fixtures', label: 'Fixtures & Reset' },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-2 text-xs font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
                  : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={() => setRawJsonMode(!rawJsonMode)}
          className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-indigo-600 dark:hover:text-indigo-400 py-1"
        >
          <Code className="w-3.5 h-3.5" />
          {rawJsonMode ? 'Form View' : 'Raw JSON View'}
        </button>
      </div>

      {/* RAW JSON MODE */}
      {rawJsonMode ? (
        <div className="space-y-2">
          <textarea
            rows={18}
            disabled={isReadOnly}
            value={rawJsonText}
            onChange={(e) => {
              setRawJsonText(e.target.value);
              setRawJsonError(null);
            }}
            className="w-full font-mono text-xs p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-900 text-slate-100 dark:bg-slate-950 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
          {rawJsonError && <p className="text-xs text-red-500">{rawJsonError}</p>}
        </div>
      ) : (
        /* FORM VIEWS */
        <div className="space-y-4">
          {/* TAB: AGENT CONNECTION */}
          {activeTab === 'agent' && (
            <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Agent Connection Reference <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  disabled={isReadOnly}
                  value={formData.agent_connection_ref}
                  onChange={(e) => setFormData({ ...formData, agent_connection_ref: e.target.value })}
                  placeholder="e.g. agent-connection-default or nexacart_refund_agent"
                  className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/60 text-slate-900 dark:text-white"
                />
                <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                  Stable reference to existing agent connection. Never input raw keys or secrets.
                </p>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Configuration Version Number
                </label>
                <input
                  type="number"
                  disabled={isReadOnly}
                  value={formData.version}
                  onChange={(e) => setFormData({ ...formData, version: parseInt(e.target.value, 10) || 1 })}
                  className="w-24 px-3 py-2 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/60 text-slate-900 dark:text-white"
                />
              </div>
            </div>
          )}

          {/* TAB: TOOLS */}
          {activeTab === 'tools' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  Tool definitions with argument JSON schemas and optional code mappings
                </span>
                {!isReadOnly && (
                  <button
                    type="button"
                    onClick={handleAddTool}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100"
                  >
                    <Plus className="w-3.5 h-3.5" /> Add Tool
                  </button>
                )}
              </div>

              {formData.tools.length === 0 ? (
                <div className="p-8 text-center rounded-xl border border-dashed border-slate-200 dark:border-slate-800 text-slate-400 text-xs">
                  No tools declared yet. Click &quot;Add Tool&quot; or load the NexaCart example.
                </div>
              ) : (
                formData.tools.map((tool, idx) => (
                  <div
                    key={idx}
                    className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-slate-900 dark:text-white">
                        Tool #{idx + 1}: {tool.name || 'Unnamed'}
                      </span>
                      {!isReadOnly && (
                        <button
                          type="button"
                          onClick={() => handleRemoveTool(idx)}
                          className="text-red-500 hover:text-red-700 p-1 rounded"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <div>
                        <label className="block text-[11px] font-medium text-slate-700 dark:text-slate-300 mb-1">
                          Tool Name <span className="text-red-500">*</span>
                        </label>
                        <input
                          type="text"
                          disabled={isReadOnly}
                          value={tool.name}
                          onChange={(e) => handleUpdateTool(idx, 'name', e.target.value)}
                          className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-medium text-slate-700 dark:text-slate-300 mb-1">
                          Tool Description
                        </label>
                        <input
                          type="text"
                          disabled={isReadOnly}
                          value={tool.description}
                          onChange={(e) => handleUpdateTool(idx, 'description', e.target.value)}
                          className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                        />
                      </div>
                    </div>

                    {/* Parameter Schema (JSON) */}
                    <div>
                      <label className="block text-[11px] font-medium text-slate-700 dark:text-slate-300 mb-1">
                        Parameters Schema (JSON Schema Object)
                      </label>
                      <textarea
                        rows={3}
                        disabled={isReadOnly}
                        value={
                          typeof tool.parameters_schema === 'object'
                            ? JSON.stringify(tool.parameters_schema, null, 2)
                            : tool.parameters_schema || ''
                        }
                        onChange={(e) => {
                          try {
                            const parsed = JSON.parse(e.target.value);
                            handleUpdateTool(idx, 'parameters_schema', parsed);
                          } catch {
                            // Leave as string if invalid JSON during editing
                            handleUpdateTool(idx, 'parameters_schema', e.target.value);
                          }
                        }}
                        className="w-full font-mono text-[11px] p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-950 text-slate-800 dark:text-slate-200"
                      />
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* TAB: REQUIREMENTS */}
          {activeTab === 'requirements' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  Versioned task requirements governing tool invocations
                </span>
                {!isReadOnly && (
                  <button
                    type="button"
                    onClick={handleAddRequirement}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100"
                  >
                    <Plus className="w-3.5 h-3.5" /> Add Requirement
                  </button>
                )}
              </div>

              {formData.requirements.length === 0 ? (
                <div className="p-8 text-center rounded-xl border border-dashed border-slate-200 dark:border-slate-800 text-slate-400 text-xs">
                  No requirements declared yet.
                </div>
              ) : (
                formData.requirements.map((req, idx) => (
                  <div
                    key={idx}
                    className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-slate-900 dark:text-white">
                        {req.req_id} (v{req.version || '1.0'})
                      </span>
                      {!isReadOnly && (
                        <button
                          type="button"
                          onClick={() => handleRemoveRequirement(idx)}
                          className="text-red-500 hover:text-red-700 p-1 rounded"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      <div>
                        <label className="block text-[11px] font-medium text-slate-700 dark:text-slate-300 mb-1">
                          Requirement ID
                        </label>
                        <input
                          type="text"
                          disabled={isReadOnly}
                          value={req.req_id}
                          onChange={(e) => handleUpdateRequirement(idx, 'req_id', e.target.value)}
                          className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-medium text-slate-700 dark:text-slate-300 mb-1">
                          Title
                        </label>
                        <input
                          type="text"
                          disabled={isReadOnly}
                          value={req.title}
                          onChange={(e) => handleUpdateRequirement(idx, 'title', e.target.value)}
                          className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-medium text-slate-700 dark:text-slate-300 mb-1">
                          Category
                        </label>
                        <select
                          disabled={isReadOnly}
                          value={req.category || 'business_logic'}
                          onChange={(e) => handleUpdateRequirement(idx, 'category', e.target.value)}
                          className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                        >
                          <option value="business_logic">Business Logic</option>
                          <option value="safety">Safety / Policy</option>
                          <option value="schema">Schema & Syntax</option>
                          <option value="recovery">Fault Recovery</option>
                        </select>
                      </div>
                    </div>

                    <div>
                      <label className="block text-[11px] font-medium text-slate-700 dark:text-slate-300 mb-1">
                        Requirement Description
                      </label>
                      <textarea
                        rows={2}
                        disabled={isReadOnly}
                        value={req.description}
                        onChange={(e) => handleUpdateRequirement(idx, 'description', e.target.value)}
                        className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                      />
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* TAB: CONSTRAINTS & EVIDENCE */}
          {activeTab === 'constraints' && (
            <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-4">
              <h3 className="text-xs font-semibold text-slate-900 dark:text-white">
                Tool Constraints & Permitted Invocations
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-[11px] font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Permitted Tools (comma-separated)
                  </label>
                  <input
                    type="text"
                    disabled={isReadOnly}
                    value={(formData.tool_constraints?.permitted_tools || []).join(', ')}
                    onChange={(e) => {
                      const tools = e.target.value.split(',').map((s) => s.trim()).filter(Boolean);
                      setFormData({
                        ...formData,
                        tool_constraints: { ...formData.tool_constraints, permitted_tools: tools },
                      });
                    }}
                    placeholder="lookup_order, process_refund"
                    className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Required Tools (comma-separated)
                  </label>
                  <input
                    type="text"
                    disabled={isReadOnly}
                    value={(formData.tool_constraints?.required_tools || []).join(', ')}
                    onChange={(e) => {
                      const tools = e.target.value.split(',').map((s) => s.trim()).filter(Boolean);
                      setFormData({
                        ...formData,
                        tool_constraints: { ...formData.tool_constraints, required_tools: tools },
                      });
                    }}
                    placeholder="lookup_order"
                    className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Forbidden Tools (comma-separated)
                  </label>
                  <input
                    type="text"
                    disabled={isReadOnly}
                    value={(formData.tool_constraints?.forbidden_tools || []).join(', ')}
                    onChange={(e) => {
                      const tools = e.target.value.split(',').map((s) => s.trim()).filter(Boolean);
                      setFormData({
                        ...formData,
                        tool_constraints: { ...formData.tool_constraints, forbidden_tools: tools },
                      });
                    }}
                    placeholder="delete_customer_account"
                    className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                  />
                </div>
              </div>

              {/* Trace Capabilities */}
              <div className="pt-3 border-t border-slate-200 dark:border-slate-800">
                <h4 className="text-xs font-medium text-slate-800 dark:text-slate-200 mb-2">
                  Enabled Evidence Channels
                </h4>
                <div className="flex flex-wrap gap-3">
                  {EVIDENCE_CHANNELS.map((ch) => {
                    const isEnabled = formData.trace_capabilities?.some((tc) => tc.channel === ch.id && tc.enabled);
                    return (
                      <label key={ch.id} className="inline-flex items-center gap-1.5 text-xs text-slate-700 dark:text-slate-300 cursor-pointer">
                        <input
                          type="checkbox"
                          disabled={isReadOnly}
                          checked={!!isEnabled}
                          onChange={(e) => {
                            const current = formData.trace_capabilities || [];
                            let updated;
                            if (e.target.checked) {
                              updated = [...current.filter((tc) => tc.channel !== ch.id), { channel: ch.id, description: ch.label, enabled: true }];
                            } else {
                              updated = current.filter((tc) => tc.channel !== ch.id);
                            }
                            setFormData({ ...formData, trace_capabilities: updated });
                          }}
                          className="rounded text-indigo-600 focus:ring-indigo-500"
                        />
                        <span>{ch.label}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* TAB: FIXTURES & RESET */}
          {activeTab === 'fixtures' && (
            <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Synthetic Fixture References (comma-separated)
                </label>
                <input
                  type="text"
                  disabled={isReadOnly}
                  value={(formData.synthetic_fixture_refs || []).join(', ')}
                  onChange={(e) => {
                    const refs = e.target.value.split(',').map((s) => s.trim()).filter(Boolean);
                    setFormData({ ...formData, synthetic_fixture_refs: refs });
                  }}
                  placeholder="nexacart_test_fixtures, orders_fixture_v1"
                  className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Environment Reset Hook Capability Ref
                </label>
                <input
                  type="text"
                  disabled={isReadOnly}
                  value={formData.reset_capability?.capability_ref || ''}
                  onChange={(e) => {
                    const ref = e.target.value.trim();
                    if (!ref) {
                      setFormData({ ...formData, reset_capability: null });
                    } else {
                      setFormData({
                        ...formData,
                        reset_capability: {
                          capability_ref: ref,
                          hook_type: formData.reset_capability?.hook_type || 'STATE_RESET',
                          is_idempotent: formData.reset_capability?.is_idempotent ?? true,
                          details: formData.reset_capability?.details || {},
                        },
                      });
                    }
                  }}
                  placeholder="e.g. nexacart_db_reset"
                  className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
