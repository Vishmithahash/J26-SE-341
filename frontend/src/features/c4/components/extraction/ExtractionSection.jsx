/**
 * Component 4 (C4) - Extraction & Readiness Section
 * Displays extraction provider readiness, job execution, and derivation triggers.
 */

import React, { useState } from 'react';
import {
  Cpu,
  CheckCircle,
  AlertTriangle,
  Play,
  RotateCw,
  Info,
  FileText,
  Terminal,
} from 'lucide-react';

export function ExtractionSection({
  selectedArtifact,
  providerReadiness,
  selectedProvider = 'shared_llm',
  onSelectProvider,
  onCheckReadiness,
  isLoadingReadiness,
  onDeriveCandidates,
  onStartExtractionJob,
  isExtracting,
  activeJob,
  error,
  successMessage,
  isProjectReady,
}) {
  const [derivationMode, setDerivationMode] = useState('controlled_language');
  const isReady = providerReadiness?.ready;

  const handleRunDerivation = () => {
    if (!selectedArtifact) return;

    if (derivationMode === 'extraction_job') {
      onStartExtractionJob({
        artifactId: selectedArtifact.artifact_id,
        artifactVersion: selectedArtifact.version,
        providerId: selectedProvider,
      });
    } else {
      onDeriveCandidates({
        artifactId: selectedArtifact.artifact_id,
        artifactVersion: selectedArtifact.version,
        mode: derivationMode,
      });
    }
  };

  return (
    <div className="space-y-6">
      {/* Section Header & Provider Readiness */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded-lg bg-indigo-100 dark:bg-indigo-950/70 text-indigo-600 dark:text-indigo-400 font-bold text-xs flex items-center justify-center">
                2
              </span>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                Policy Extraction & Engine Readiness
              </h3>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Verify extraction provider operational status and derive candidate rules across the three core security families.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => onCheckReadiness(selectedProvider)}
              disabled={isLoadingReadiness || !isProjectReady}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
              title="Refresh provider readiness"
            >
              <RotateCw className={`w-3.5 h-3.5 ${isLoadingReadiness ? 'animate-spin' : ''}`} />
              <span>Check Status</span>
            </button>
          </div>
        </div>

        {/* Provider Source Selection Toggle */}
        <div className="mt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800">
          <div>
            <span className="text-xs font-bold text-slate-800 dark:text-slate-200 block">
              Extraction Engine Provider
            </span>
            <span className="text-[11px] text-slate-500 dark:text-slate-400">
              Choose between the deterministic scripted engine or your active saved QA model (Ollama / Gemini).
            </span>
          </div>
          <div className="inline-flex p-1 rounded-xl bg-slate-200/70 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
            <button
              type="button"
              onClick={() => onSelectProvider?.('offline_mock')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                selectedProvider === 'offline_mock'
                  ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-sm'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              Offline Mock Engine
            </button>
            <button
              type="button"
              onClick={() => onSelectProvider?.('shared_llm')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                selectedProvider === 'shared_llm'
                  ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-sm'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              Use Selected QA Model
            </button>
          </div>
        </div>

        {/* Feedback notices */}
        {error && (
          <div className="mt-4 p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-300 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {successMessage && (
          <div className="mt-4 p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900 text-emerald-700 dark:text-emerald-300 text-xs flex items-center gap-2">
            <CheckCircle className="w-4 h-4 shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Provider Readiness Card */}
        <div className="mt-6 grid md:grid-cols-3 gap-4">
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Provider Identifier
              </span>
              <span
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold ${
                  isReady
                    ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300'
                    : 'bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300'
                }`}
              >
                {isReady ? <CheckCircle className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
                {providerReadiness?.status || 'CHECKING'}
              </span>
            </div>
            <div className="font-mono text-sm font-bold text-slate-900 dark:text-white">
              {providerReadiness?.provider_id || selectedProvider}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              Mode: {selectedProvider === 'offline_mock' ? 'Deterministic Scripted Engine' : 'Shared Selected QA Model'}
            </div>
          </div>

          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-2">
              Model Identifier
            </span>
            <div className="font-mono text-sm font-bold text-slate-900 dark:text-white truncate">
              {providerReadiness?.model_identifier || (selectedProvider === 'shared_llm' ? 'qa-model-selected' : 'offline-deterministic-regex')}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              {selectedProvider === 'shared_llm' ? 'Configured provider model instance' : 'Deterministic parsing & bounded regex extractor'}
            </div>
          </div>

          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-2">
              Policy Families Supported
            </span>
            <div className="flex flex-wrap gap-1">
              {(providerReadiness?.supported_policy_families || [
                'AUTHORIZATION',
                'CONFIDENTIALITY',
                'INSTRUCTION_AUTHORITY',
              ]).map((fam) => (
                <span
                  key={fam}
                  className="px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300"
                >
                  {fam}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Honest Architecture Notice regarding Model Selection */}
        <div className="mt-4 p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 flex items-start gap-2.5">
          <Info className="w-4 h-4 text-indigo-500 shrink-0 mt-0.5" />
          <p className="text-xs text-slate-600 dark:text-slate-400 leading-normal">
            <strong>Extraction Engine:</strong> Operating under{' '}
            <code className="px-1 py-0.5 bg-slate-200 dark:bg-slate-800 rounded font-mono text-[11px]">
              {selectedProvider}
            </code>
            .{' '}
            {selectedProvider === 'shared_llm'
              ? 'Invoking the authenticated user’s confirmed model selection via the shared LLM provider layer.'
              : 'Using the deterministic controlled-language engine for bounded regex extraction and testing.'}
          </p>
        </div>

        {/* Provider Blockers if any */}
        {providerReadiness?.blockers && providerReadiness.blockers.length > 0 && (
          <div className="mt-4 p-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900">
            <h5 className="text-xs font-bold text-amber-900 dark:text-amber-200 mb-2 flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-amber-600" />
              Extraction Provider Blockers ({providerReadiness.blockers.length})
            </h5>
            <ul className="space-y-1">
              {providerReadiness.blockers.map((blk, idx) => (
                <li key={idx} className="text-xs text-amber-800 dark:text-amber-300 font-mono">
                  • {blk}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Derivation Trigger Box */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <h4 className="text-sm font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
          <Terminal className="w-4 h-4 text-indigo-500" />
          <span>Execute Candidate Rule Derivation</span>
        </h4>

        {selectedArtifact ? (
          <div className="space-y-4">
            <div className="p-3.5 rounded-xl bg-indigo-50/50 dark:bg-indigo-950/30 border border-indigo-100 dark:border-indigo-900/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <FileText className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0" />
                <div>
                  <span className="text-xs font-semibold text-slate-900 dark:text-white">
                    Target Artifact: {selectedArtifact.artifact_id}
                  </span>
                  <span className="text-[11px] text-slate-500 dark:text-slate-400 block">
                    Version: v{selectedArtifact.version} • {selectedArtifact.character_count} characters • {selectedArtifact.artifact_kind}
                  </span>
                </div>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 shrink-0">
                Hash: {selectedArtifact.content_hash?.slice(0, 10)}...
              </span>
            </div>

            {/* Mode Selector */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                Derivation Engine Mode
              </label>
              <div className="grid sm:grid-cols-3 gap-3">
                <label
                  className={`p-3 rounded-xl border text-xs cursor-pointer transition-all ${
                    derivationMode === 'controlled_language'
                      ? 'border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/40 text-indigo-900 dark:text-indigo-200 font-semibold'
                      : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 text-slate-600 dark:text-slate-400'
                  }`}
                >
                  <input
                    type="radio"
                    name="mode"
                    value="controlled_language"
                    checked={derivationMode === 'controlled_language'}
                    onChange={() => setDerivationMode('controlled_language')}
                    className="hidden"
                  />
                  <div className="font-bold mb-0.5">Controlled Language</div>
                  <div className="text-[11px] font-normal text-slate-500">
                    Deterministic regex rules parser
                  </div>
                </label>

                <label
                  className={`p-3 rounded-xl border text-xs cursor-pointer transition-all ${
                    derivationMode === 'structured_import'
                      ? 'border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/40 text-indigo-900 dark:text-indigo-200 font-semibold'
                      : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 text-slate-600 dark:text-slate-400'
                  }`}
                >
                  <input
                    type="radio"
                    name="mode"
                    value="structured_import"
                    checked={derivationMode === 'structured_import'}
                    onChange={() => setDerivationMode('structured_import')}
                    className="hidden"
                  />
                  <div className="font-bold mb-0.5">Structured Import</div>
                  <div className="text-[11px] font-normal text-slate-500">
                    Schema-validated JSON import
                  </div>
                </label>

                <label
                  className={`p-3 rounded-xl border text-xs cursor-pointer transition-all ${
                    derivationMode === 'extraction_job'
                      ? 'border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/40 text-indigo-900 dark:text-indigo-200 font-semibold'
                      : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 text-slate-600 dark:text-slate-400'
                  }`}
                >
                  <input
                    type="radio"
                    name="mode"
                    value="extraction_job"
                    checked={derivationMode === 'extraction_job'}
                    onChange={() => setDerivationMode('extraction_job')}
                    className="hidden"
                  />
                  <div className="font-bold mb-0.5">Extraction Job Pipeline</div>
                  <div className="text-[11px] font-normal text-slate-500">
                    Bounded onboarding job tracker
                  </div>
                </label>
              </div>
            </div>

            {/* Submit Button */}
            <div className="flex items-center justify-between pt-2">
              <span className="text-xs text-slate-400">
                Extracted candidates require explicit human review before contract inclusion.
              </span>
              <button
                type="button"
                onClick={handleRunDerivation}
                disabled={isExtracting || !isProjectReady}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 dark:disabled:bg-slate-800 text-white font-medium text-xs shadow-sm transition-colors"
              >
                {isExtracting ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Extracting Rules...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-current" />
                    <span>Run Candidate Derivation</span>
                  </>
                )}
              </button>
            </div>
          </div>
        ) : (
          <div className="text-center py-8 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl text-slate-500 dark:text-slate-400 text-xs">
            <FileText className="w-8 h-8 mx-auto text-slate-300 dark:text-slate-600 mb-2" />
            <span>No artifact selected. Register or select an artifact version in Step 1 to extract rules.</span>
          </div>
        )}
      </div>

      {/* Active Job Status Banner if present */}
      {activeJob && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-indigo-500" />
              <span className="text-xs font-bold text-slate-900 dark:text-white">
                Extraction Job: {activeJob.job_id}
              </span>
            </div>
            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300">
              {activeJob.status}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono text-slate-500">
            <div>Provider: {activeJob.provider_id}</div>
            <div>Model: {activeJob.model_identifier}</div>
            <div>Candidates: {activeJob.candidates_extracted?.length || 0}</div>
            <div>Issues: {activeJob.validation_issues?.length || 0}</div>
          </div>
        </div>
      )}
    </div>
  );
}
