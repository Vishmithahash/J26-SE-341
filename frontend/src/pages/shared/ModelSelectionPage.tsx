import React, { useState, useEffect } from 'react';
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
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import {
  getModelPreference,
  saveModelPreference,
  clearModelPreference,
} from '../../services/modelPreference';
import type { ModelPreference } from '../../types/auth';

export const ModelSelectionPage: React.FC = () => {
  const { user } = useAuth();
  const userId = user?.id || 0;

  const [connectionType, setConnectionType] = useState<'local' | 'hosted'>('local');
  const [provider, setProvider] = useState<'ollama' | 'openai-compatible' | 'custom'>('ollama');
  const [modelId, setModelId] = useState('');
  const [feedback, setFeedback] = useState<{ type: 'success' | 'info'; message: string } | null>(null);

  // Load existing preference scoped to current authenticated user
  useEffect(() => {
    if (userId) {
      const saved = getModelPreference(userId);
      if (saved) {
        setConnectionType(saved.connectionType);
        setProvider(saved.provider);
        setModelId(saved.modelId);
      } else {
        setConnectionType('local');
        setProvider('ollama');
        setModelId('');
      }
    }
  }, [userId]);

  // Adjust provider default when switching connection type
  const handleConnectionTypeChange = (type: 'local' | 'hosted') => {
    setConnectionType(type);
    if (type === 'local') {
      setProvider('ollama');
    } else {
      setProvider('openai-compatible');
    }
    setFeedback(null);
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!userId) return;

    if (!modelId.trim()) {
      setFeedback({ type: 'info', message: 'Please enter a model identifier to save preference.' });
      return;
    }

    const pref: ModelPreference = {
      connectionType,
      provider,
      modelId: modelId.trim(),
    };

    saveModelPreference(userId, pref);
    setFeedback({
      type: 'success',
      message: 'Preference saved. Connection not configured.',
    });
  };

  const handleReset = () => {
    if (!userId) return;
    clearModelPreference(userId);
    setConnectionType('local');
    setProvider('ollama');
    setModelId('');
    setFeedback({
      type: 'info',
      message: 'Model preferences reset to default (No model selected).',
    });
  };

  const currentSaved = userId ? getModelPreference(userId) : null;
  const statusState = currentSaved && currentSaved.modelId ? 'Preference saved' : 'No model selected';

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
              Choose the model you prefer for test preparation and explanations.
            </p>
          </div>
        </div>
      </div>

      {/* Helper Note Banner */}
      <div className="p-4 rounded-xl bg-slate-100 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 text-xs sm:text-sm text-slate-600 dark:text-slate-300 flex items-start gap-3">
        <Info className="w-5 h-5 text-teal-600 dark:text-teal-400 shrink-0 mt-0.5" />
        <div className="leading-relaxed">
          <p className="font-semibold text-slate-800 dark:text-slate-200">
            Non-Secret Framework Preference
          </p>
          <p className="mt-0.5 text-slate-500 dark:text-slate-400 text-xs">
            Saving a preference does not establish a connection. This configuration is stored locally for your account to designate preferred models for test preparation and diagnostic explanations.
          </p>
        </div>
      </div>

      {/* Current Truthful Status Card */}
      <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Current Status
          </span>
          <div className="flex items-center gap-2 mt-1">
            <span
              className={`inline-block w-2.5 h-2.5 rounded-full ${
                currentSaved && currentSaved.modelId ? 'bg-teal-500' : 'bg-slate-400'
              }`}
            />
            <span className="text-sm font-bold text-slate-900 dark:text-white">
              {statusState}
            </span>
            <span className="text-xs text-slate-400">
              — Connection not configured
            </span>
          </div>
        </div>

        {currentSaved && currentSaved.modelId && (
          <div className="text-xs text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 font-mono">
            {currentSaved.provider} : {currentSaved.modelId}
          </div>
        )}
      </div>

      {feedback && (
        <div
          role="status"
          className={`p-4 rounded-xl text-sm flex items-start gap-3 border ${
            feedback.type === 'success'
              ? 'bg-teal-50 dark:bg-teal-950/40 border-teal-200 dark:border-teal-800 text-teal-800 dark:text-teal-200'
              : 'bg-indigo-50 dark:bg-indigo-950/40 border-indigo-200 dark:border-indigo-800 text-indigo-800 dark:text-indigo-200'
          }`}
        >
          {feedback.type === 'success' ? (
            <CheckCircle className="w-5 h-5 shrink-0 mt-0.5 text-teal-600 dark:text-teal-400" />
          ) : (
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-indigo-600 dark:text-indigo-400" />
          )}
          <span>{feedback.message}</span>
        </div>
      )}

      {/* Model Preferences Form */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
        <form onSubmit={handleSave} className="space-y-6">
          {/* Connection Type */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-3">
              Connection Type
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-lg">
              <button
                type="button"
                onClick={() => handleConnectionTypeChange('local')}
                className={`flex items-start gap-3 p-4 rounded-xl border text-left transition-all ${
                  connectionType === 'local'
                    ? 'border-teal-600 bg-teal-50/40 dark:bg-teal-950/30 ring-2 ring-teal-600/20'
                    : 'border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/50'
                }`}
              >
                <Server className="w-5 h-5 text-teal-600 dark:text-teal-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-slate-900 dark:text-white">Local</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Self-hosted or desktop inference runtimes (e.g., Ollama)
                  </p>
                </div>
              </button>

              <button
                type="button"
                onClick={() => handleConnectionTypeChange('hosted')}
                className={`flex items-start gap-3 p-4 rounded-xl border text-left transition-all ${
                  connectionType === 'hosted'
                    ? 'border-teal-600 bg-teal-50/40 dark:bg-teal-950/30 ring-2 ring-teal-600/20'
                    : 'border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/50'
                }`}
              >
                <Cloud className="w-5 h-5 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-slate-900 dark:text-white">Hosted</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Cloud or external endpoints with OpenAI-compatible API
                  </p>
                </div>
              </button>
            </div>
          </div>

          {/* Provider Preference */}
          <div>
            <label
              htmlFor="provider-select"
              className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-2"
            >
              Provider Preference
            </label>
            <div className="max-w-md">
              <select
                id="provider-select"
                value={provider}
                onChange={(e) => setProvider(e.target.value as any)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 shadow-sm"
              >
                {connectionType === 'local' ? (
                  <>
                    <option value="ollama">Ollama (Local)</option>
                    <option value="custom">Custom Local Endpoint</option>
                  </>
                ) : (
                  <>
                    <option value="openai-compatible">OpenAI-compatible (Hosted)</option>
                    <option value="custom">Custom Hosted Endpoint</option>
                  </>
                )}
              </select>
            </div>
          </div>

          {/* Model Identifier Free-Text Input */}
          <div>
            <div className="flex items-center justify-between max-w-md mb-1.5">
              <label
                htmlFor="model-id-input"
                className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300"
              >
                Model Identifier
              </label>
              <span className="text-[11px] text-slate-400">e.g. llama3:8b, mistral</span>
            </div>
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
                  connectionType === 'local' ? 'e.g. llama3.1:8b' : 'e.g. gpt-4o-mini'
                }
                className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-teal-600 shadow-sm font-mono"
              />
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1.5">
              Enter the exact model name or tag used by your framework runtime.
            </p>
          </div>

          {/* Action buttons */}
          <div className="pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center gap-3">
            <button
              type="submit"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-semibold text-sm transition-colors shadow-sm"
            >
              <Save className="w-4 h-4" />
              <span>Save Preference</span>
            </button>

            <button
              type="button"
              onClick={handleReset}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 font-semibold text-sm transition-colors"
            >
              <RotateCcw className="w-4 h-4" />
              <span>Reset</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
