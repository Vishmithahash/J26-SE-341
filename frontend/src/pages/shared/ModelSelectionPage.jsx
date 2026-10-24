import React, { useState, useEffect, useRef } from 'react';
import {
  Sliders,
  Server,
  Cloud,
  Cpu,
  Save,
  RotateCcw,
  CheckCircle,
  AlertCircle,
  Info,
  Activity,
  Check,
  RefreshCw,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import {
  getModelPreference,
  saveModelPreference,
  clearModelPreference,
  fetchProviders,
  fetchModelSelection,
  saveModelSelection,
  testLLMConnection,
} from '../../services/modelPreference';

export const ModelSelectionPage = () => {
  const { user } = useAuth();
  const userId = user?.id || 0;

  // Active server-confirmed selection
  const [activeSelection, setActiveSelection] = useState(null);

  // Form edit state
  const [connectionType, setConnectionType] = useState('local');
  const [provider, setProvider] = useState('ollama');
  const [modelId, setModelId] = useState('');

  // Providers availability from server
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [feedback, setFeedback] = useState(null);

  // Guard against stale asynchronous responses
  const activeReqIdRef = useRef(0);

  // Load from backend on mount or when user changes
  useEffect(() => {
    if (!userId) {
      setActiveSelection(null);
      clearModelPreference(userId);
      return;
    }

    const currentReqId = ++activeReqIdRef.current;
    setLoading(true);

    // Initial cache restore from localStorage for instant render
    const cached = getModelPreference(userId);
    if (cached) {
      setConnectionType(cached.connectionType || 'local');
      setProvider(cached.provider || 'ollama');
      setModelId(cached.modelId || '');
    }

    // Load server providers and authoritative user selection in parallel
    Promise.all([
      fetchProviders().catch((err) => {
        console.warn('Failed to fetch providers:', err);
        return [];
      }),
      fetchModelSelection().catch((err) => {
        console.warn('Failed to fetch model selection:', err);
        return null;
      }),
    ]).then(([providersList, userSelection]) => {
      if (currentReqId !== activeReqIdRef.current) return;

      if (Array.isArray(providersList)) {
        setProviders(providersList);
      }

      if (userSelection) {
        setActiveSelection(userSelection);
        setConnectionType(userSelection.connection_type);
        setProvider(userSelection.provider);
        setModelId(userSelection.model);

        // Update local cache
        saveModelPreference(userId, {
          connectionType: userSelection.connection_type,
          provider: userSelection.provider,
          modelId: userSelection.model,
        });
      } else if (cached) {
        setActiveSelection({
          connection_type: cached.connectionType,
          provider: cached.provider,
          model: cached.modelId,
        });
      }

      setLoading(false);
    });
  }, [userId]);

  // Provider helper finders
  const ollamaProvider = providers.find((p) => p.provider === 'ollama');
  const geminiProvider = providers.find((p) => p.provider === 'gemini');

  // Handle clicking Local / Hosted card
  const handleSelectConnectionType = async (type) => {
    if (!userId || saving) return;

    const targetProvider = type === 'local' ? 'ollama' : 'gemini';
    const providerInfo = targetProvider === 'ollama' ? ollamaProvider : geminiProvider;
    const defaultModel =
      providerInfo?.default_model || (type === 'local' ? 'qwen3:4b' : 'gemini-3.5-flash-lite');

    // Optimistically update form state
    setConnectionType(type);
    setProvider(targetProvider);
    setModelId(defaultModel);
    setFeedback(null);
    setTestResult(null);

    // Persist choice immediately to backend as authoritative default
    setSaving(true);
    try {
      const updated = await saveModelSelection({
        connection_type: type,
        provider: targetProvider,
        model: defaultModel,
      });

      setActiveSelection(updated);
      saveModelPreference(userId, {
        connectionType: updated.connection_type,
        provider: updated.provider,
        modelId: updated.model,
      });

      setFeedback({
        type: 'success',
        message: `Active provider updated to ${type === 'local' ? 'Ollama' : 'Google Gemini'} (${updated.model}).`,
      });
    } catch (err) {
      // Retain last confirmed active selection on failure
      if (activeSelection) {
        setConnectionType(activeSelection.connection_type);
        setProvider(activeSelection.provider);
        setModelId(activeSelection.model);
      }
      setFeedback({
        type: 'error',
        message: `Failed to activate ${type}: ${err.message || 'Server error'}`,
      });
    } finally {
      setSaving(false);
    }
  };

  // Explicit Save / Use for custom model or setting changes
  const handleSave = async (e) => {
    e.preventDefault();
    if (!userId || saving) return;

    if (!modelId.trim()) {
      setFeedback({ type: 'error', message: 'Please enter or select a model identifier.' });
      return;
    }

    setSaving(true);
    setFeedback(null);
    try {
      const updated = await saveModelSelection({
        connection_type: connectionType,
        provider,
        model: modelId.trim(),
      });

      setActiveSelection(updated);
      saveModelPreference(userId, {
        connectionType: updated.connection_type,
        provider: updated.provider,
        modelId: updated.model,
      });

      setFeedback({
        type: 'success',
        message: `Selection saved: ${updated.provider} / ${updated.model}`,
      });
    } catch (err) {
      setFeedback({
        type: 'error',
        message: `Failed to save selection: ${err.message || 'Server error'}`,
      });
    } finally {
      setSaving(false);
    }
  };

  // Reset to default local Ollama/Qwen
  const handleReset = async () => {
    if (!userId || saving) return;
    setSaving(true);
    setFeedback(null);
    setTestResult(null);

    const defaultModel = ollamaProvider?.default_model || 'qwen3:4b';
    try {
      const updated = await saveModelSelection({
        connection_type: 'local',
        provider: 'ollama',
        model: defaultModel,
      });
      setActiveSelection(updated);
      setConnectionType('local');
      setProvider('ollama');
      setModelId(defaultModel);

      saveModelPreference(userId, {
        connectionType: 'local',
        provider: 'ollama',
        modelId: defaultModel,
      });

      setFeedback({
        type: 'info',
        message: `Model selection reset to default: Ollama / ${defaultModel}.`,
      });
    } catch (err) {
      setFeedback({
        type: 'error',
        message: `Failed to reset selection: ${err.message || 'Server error'}`,
      });
    } finally {
      setSaving(false);
    }
  };

  // Explicit bounded connection and inference test
  const handleTestConnection = async () => {
    if (testing) return;
    setTesting(true);
    setTestResult(null);

    try {
      const result = await testLLMConnection({
        provider,
        model: modelId.trim() || undefined,
      });

      setTestResult(result);
      if (result.success) {
        setFeedback({
          type: 'success',
          message: `Inference test succeeded for ${result.provider} / ${result.model} (${result.latency_ms}ms).`,
        });
      } else {
        setFeedback({
          type: 'error',
          message: `Connection test failed: ${result.message}`,
        });
      }
    } catch (err) {
      setTestResult({
        success: false,
        message: err.message || 'Connection test failed',
      });
      setFeedback({
        type: 'error',
        message: `Connection test failed: ${err.message || 'Network error'}`,
      });
    } finally {
      setTesting(false);
    }
  };

  // Determine concise state description
  const getProviderStateText = () => {
    if (!activeSelection) return 'No model selected';

    const prov = activeSelection.provider === 'ollama' ? ollamaProvider : geminiProvider;
    const modelTag = activeSelection.model || 'unspecified';

    if (activeSelection.provider === 'ollama') {
      if (!prov) return `Selected: Ollama / ${modelTag}`;
      if (!prov.available) {
        if (prov.error && prov.error.toLowerCase().includes('not installed')) {
          return `Selected: Ollama / ${modelTag} — Qwen model is not installed`;
        }
        return `Selected: Ollama / ${modelTag} — Ollama is not running`;
      }
      return `Selected: Ollama / ${modelTag}`;
    }

    if (activeSelection.provider === 'gemini') {
      if (!prov) return `Selected: Gemini / ${modelTag}`;
      if (!prov.configured) {
        return `Selected: Gemini / ${modelTag} — Gemini API key is not configured`;
      }
      if (!prov.available) {
        return `Selected: Gemini / ${modelTag} — Model unavailable`;
      }
      return `Selected: Gemini / ${modelTag}`;
    }

    return `Selected: ${activeSelection.provider} / ${modelTag}`;
  };

  const isCurrentSelectionActive =
    activeSelection &&
    activeSelection.connection_type === connectionType &&
    activeSelection.provider === provider &&
    activeSelection.model === modelId;

  return (
    <div className="max-w-4xl space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-teal-50 dark:bg-teal-950/50 text-teal-600 dark:text-teal-400">
            <Sliders className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white leading-tight">
              Model Selection
            </h1>
            <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-0.5">
              Choose the model used by the QA framework's model-assisted operations (Local Ollama/Qwen or Hosted Gemini).
            </p>
          </div>
        </div>
      </div>

      {/* Helper Note Banner */}
      <div className="p-4 rounded-xl bg-slate-100 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 text-xs sm:text-sm text-slate-600 dark:text-slate-300 flex items-start gap-3">
        <Info className="w-5 h-5 text-teal-600 dark:text-teal-400 shrink-0 mt-0.5" />
        <div className="leading-relaxed">
          <p className="font-semibold text-slate-800 dark:text-slate-200">
            Authoritative Framework Model Selection
          </p>
          <p className="mt-0.5 text-slate-500 dark:text-slate-400 text-xs">
            Your saved selection determines which provider is called for candidate input drafting, EFSM workflow proposals, policy extraction, and diagnostic explanations. Tested AUT execution (NexaCart) is kept strictly separate.
          </p>
        </div>
      </div>

      {/* Current Truthful Status Card */}
      <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Current Active Selection
          </span>
          <div className="flex items-center gap-2 mt-1">
            <span
              className={`inline-block w-2.5 h-2.5 rounded-full ${
                activeSelection && activeSelection.model ? 'bg-teal-500' : 'bg-slate-400'
              }`}
            />
            <span className="text-sm font-bold text-slate-900 dark:text-white">
              {getProviderStateText()}
            </span>
          </div>
          {activeSelection?.updated_at && (
            <span className="text-[11px] text-slate-400 mt-0.5 block">
              Last saved: {new Date(activeSelection.updated_at).toLocaleString()}
            </span>
          )}
        </div>

        {activeSelection && (
          <div className="flex items-center gap-2">
            <div className="text-xs text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 font-mono">
              {activeSelection.provider} : {activeSelection.model}
            </div>
            <button
              type="button"
              onClick={handleTestConnection}
              disabled={testing}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-teal-600/30 bg-teal-50 dark:bg-teal-950/40 hover:bg-teal-100 dark:hover:bg-teal-900/50 text-teal-700 dark:text-teal-300 text-xs font-semibold transition-colors disabled:opacity-50"
            >
              {testing ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Activity className="w-3.5 h-3.5" />
              )}
              <span>{testing ? 'Testing...' : 'Test Connection'}</span>
            </button>
          </div>
        )}
      </div>

      {/* Test Result / Feedback */}
      {feedback && (
        <div
          role="status"
          className={`p-4 rounded-xl text-sm flex items-start gap-3 border ${
            feedback.type === 'success'
              ? 'bg-teal-50 dark:bg-teal-950/40 border-teal-200 dark:border-teal-800 text-teal-800 dark:text-teal-200'
              : feedback.type === 'error'
              ? 'bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-800 text-red-800 dark:text-red-200'
              : 'bg-indigo-50 dark:bg-indigo-950/40 border-indigo-200 dark:border-indigo-800 text-indigo-800 dark:text-indigo-200'
          }`}
        >
          {feedback.type === 'success' ? (
            <CheckCircle className="w-5 h-5 shrink-0 mt-0.5 text-teal-600 dark:text-teal-400" />
          ) : (
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-red-600 dark:text-red-400" />
          )}
          <span className="flex-1">{feedback.message}</span>
        </div>
      )}

      {/* Model Preferences Form */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
        <form onSubmit={handleSave} className="space-y-6">
          {/* Connection Type Primary Cards */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-3">
              Provider Mode
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-xl">
              {/* Local Card */}
              <button
                type="button"
                onClick={() => handleSelectConnectionType('local')}
                disabled={saving}
                className={`flex items-start gap-3 p-4 rounded-xl border text-left transition-all ${
                  connectionType === 'local'
                    ? 'border-teal-600 bg-teal-50/40 dark:bg-teal-950/30 ring-2 ring-teal-600/20'
                    : 'border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/50'
                }`}
              >
                <Server className="w-5 h-5 text-teal-600 dark:text-teal-400 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold text-slate-900 dark:text-white">Local</p>
                    {ollamaProvider && (
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded font-medium ${
                          ollamaProvider.available
                            ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300'
                            : 'bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300'
                        }`}
                      >
                        {ollamaProvider.available ? 'Ready' : 'Not Running'}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Ollama runtime with Qwen model (Default: {ollamaProvider?.default_model || 'qwen3:4b'})
                  </p>
                </div>
              </button>

              {/* Hosted Card */}
              <button
                type="button"
                onClick={() => handleSelectConnectionType('hosted')}
                disabled={saving}
                className={`flex items-start gap-3 p-4 rounded-xl border text-left transition-all ${
                  connectionType === 'hosted'
                    ? 'border-teal-600 bg-teal-50/40 dark:bg-teal-950/30 ring-2 ring-teal-600/20'
                    : 'border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/50'
                }`}
              >
                <Cloud className="w-5 h-5 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold text-slate-900 dark:text-white">Hosted</p>
                    {geminiProvider && (
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded font-medium ${
                          geminiProvider.available
                            ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300'
                            : geminiProvider.configured
                            ? 'bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300'
                            : 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                        }`}
                      >
                        {geminiProvider.available
                          ? 'Available'
                          : geminiProvider.configured
                          ? 'Key Configured'
                          : 'No API Key'}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Google Gemini Developer API (Default: {geminiProvider?.default_model || 'gemini-3.5-flash-lite'})
                  </p>
                </div>
              </button>
            </div>
          </div>

          {/* Model Identifier Selection */}
          <div>
            <div className="flex items-center justify-between max-w-md mb-1.5">
              <label
                htmlFor="model-id-input"
                className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300"
              >
                Model Identifier
              </label>
              <span className="text-[11px] text-slate-400">
                {connectionType === 'local' ? 'Installed Qwen tag' : 'Configured Gemini model'}
              </span>
            </div>

            {/* Quick picker if server provided available models */}
            {connectionType === 'local' && ollamaProvider?.available_models?.length > 0 && (
              <div className="max-w-md mb-2">
                <select
                  value={modelId}
                  onChange={(e) => setModelId(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-xs mb-1.5"
                >
                  {ollamaProvider.available_models.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {connectionType === 'hosted' && geminiProvider?.available_models?.length > 0 && (
              <div className="max-w-md mb-2">
                <select
                  value={modelId}
                  onChange={(e) => setModelId(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-xs mb-1.5"
                >
                  {geminiProvider.available_models.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="max-w-md relative">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                <Cpu className="w-4 h-4" />
              </div>
              <input
                id="model-id-input"
                type="text"
                value={modelId}
                onChange={(e) => setModelId(e.target.value)}
                placeholder={
                  connectionType === 'local' ? 'qwen3:4b' : 'gemini-3.5-flash-lite'
                }
                className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 shadow-sm font-mono"
              />
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1.5">
              Exact model tag passed to {provider}. Administrator can configure defaults via backend environment.
            </p>
          </div>

          {/* Action buttons */}
          <div className="pt-4 border-t border-slate-100 dark:border-slate-800 flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-semibold text-sm transition-colors shadow-sm disabled:opacity-50"
            >
              {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              <span>{saving ? 'Saving...' : 'Save Selection'}</span>
            </button>

            <button
              type="button"
              onClick={handleTestConnection}
              disabled={testing || saving || !modelId.trim()}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 font-semibold text-sm transition-colors disabled:opacity-50"
            >
              {testing ? (
                <RefreshCw className="w-4 h-4 animate-spin text-teal-600" />
              ) : (
                <Activity className="w-4 h-4 text-teal-600" />
              )}
              <span>{testing ? 'Testing...' : 'Test Connection'}</span>
            </button>

            <button
              type="button"
              onClick={handleReset}
              disabled={saving}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 font-semibold text-sm transition-colors disabled:opacity-50"
            >
              <RotateCcw className="w-4 h-4" />
              <span>Reset to Default</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
