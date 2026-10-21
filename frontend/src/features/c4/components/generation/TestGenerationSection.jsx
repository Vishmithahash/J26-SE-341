/**
 * Component 4 (C4) - Automatic Test Generation Section
 * Generates bounded policy test cases across benign controls, direct challenges, and indirect injections.
 */

import React, { useState } from 'react';
import {
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Play,
  FileCheck,
  Layers,
  Check,
  Info,
} from 'lucide-react';
import { TEST_CASE_KINDS, CONTRACT_LIFECYCLE_STATES } from '../../api/types.js';

export function TestGenerationSection({
  acceptedContract,
  domainBinding,
  onGenerateCases,
  isGenerating,
  generationReport,
  error,
  successMessage,
  isProjectReady,
  onViewGeneratedCases,
}) {
  const [selectedCategories, setSelectedCategories] = useState([
    TEST_CASE_KINDS.BENIGN,
    TEST_CASE_KINDS.DIRECT_POLICY_CHALLENGE,
    TEST_CASE_KINDS.INDIRECT_PROMPT_INJECTION,
  ]);
  const [seed, setSeed] = useState(42);
  const [maxCasesPerRule, setMaxCasesPerRule] = useState(10);
  const [includeBenignControls, setIncludeBenignControls] = useState(true);
  const [includeBoundaryValues, setIncludeBoundaryValues] = useState(true);
  const [autoValidate, setAutoValidate] = useState(true);
  const [autoFreeze, setAutoFreeze] = useState(false);

  const isContractReady =
    acceptedContract && acceptedContract.lifecycle_state === CONTRACT_LIFECYCLE_STATES.ACCEPTED;
  const isBindingReady = Boolean(domainBinding);

  const toggleCategory = (cat) => {
    setSelectedCategories((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    );
  };

  const handleTriggerGeneration = (e) => {
    e.preventDefault();
    if (!isContractReady || !isBindingReady || !isProjectReady || isGenerating) return;

    onGenerateCases({
      contractId: acceptedContract.contract_id,
      contractVersion: acceptedContract.version,
      bindingId: domainBinding.binding_id,
      bindingVersion: domainBinding.version,
      categories: selectedCategories,
      seed: Number(seed),
      maxCasesPerRule: Number(maxCasesPerRule),
      includeBenignControls,
      includeBoundaryValues,
      autoValidate,
      autoFreeze,
    });
  };

  return (
    <div className="space-y-6">
      {/* Prerequisites Notice Banner */}
      {(!isContractReady || !isBindingReady) && (
        <div className="p-4 rounded-2xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div className="text-xs text-amber-900 dark:text-amber-200 space-y-1">
            <p className="font-bold">Generation Prerequisites Required</p>
            <p className="text-amber-800 dark:text-amber-300">
              Automatic policy-test synthesis requires an <strong>ACCEPTED</strong> policy contract and a registered <strong>Domain Binding</strong>.
            </p>
            <div className="flex flex-wrap gap-2 pt-1 font-mono text-[11px]">
              <span className={`px-2 py-0.5 rounded border ${isContractReady ? 'bg-emerald-100 text-emerald-800 border-emerald-300' : 'bg-rose-100 text-rose-800 border-rose-300'}`}>
                Contract: {isContractReady ? `${acceptedContract.contract_id} (v${acceptedContract.version} ACCEPTED)` : 'Missing or unaccepted'}
              </span>
              <span className={`px-2 py-0.5 rounded border ${isBindingReady ? 'bg-emerald-100 text-emerald-800 border-emerald-300' : 'bg-rose-100 text-rose-800 border-rose-300'}`}>
                Binding: {isBindingReady ? `${domainBinding.binding_id} (v${domainBinding.version})` : 'Default profile needed'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Main Generation Configuration Card */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-5 border-b border-slate-200 dark:border-slate-800">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded-lg bg-indigo-100 dark:bg-indigo-950/70 text-indigo-600 dark:text-indigo-400 font-bold text-xs flex items-center justify-center">
                1
              </span>
              <h3 className="text-base font-bold text-slate-900 dark:text-white">
                Automatic Policy Test Generation
              </h3>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Synthesize benign controls, direct policy challenges, and indirect prompt injections derived from your accepted contract.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold px-2.5 py-1 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
              Deterministic Generator v2.0
            </span>
          </div>
        </div>

        {/* Form Options */}
        <form onSubmit={handleTriggerGeneration} className="mt-5 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Pinned Dependencies */}
            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-700/70 space-y-3">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                <FileCheck className="w-4 h-4 text-indigo-500" />
                Target Policy Contract
              </span>
              <div className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">Contract ID:</span>
                  <span className="font-mono font-medium text-slate-800 dark:text-slate-200">
                    {acceptedContract?.contract_id || 'None (Requires Acceptance)'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Contract Version:</span>
                  <span className="font-mono font-medium text-slate-800 dark:text-slate-200">
                    v{acceptedContract?.version || 1}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Lifecycle State:</span>
                  <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                    {acceptedContract?.lifecycle_state || 'NOT_ACCEPTED'}
                  </span>
                </div>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-700/70 space-y-3">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-teal-500" />
                Domain Capability Binding
              </span>
              <div className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">Binding ID:</span>
                  <span className="font-mono font-medium text-slate-800 dark:text-slate-200">
                    {domainBinding?.binding_id || 'domain-ecommerce-c4'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Binding Version:</span>
                  <span className="font-mono font-medium text-slate-800 dark:text-slate-200">
                    v{domainBinding?.version || 1}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Tools / Resources:</span>
                  <span className="font-mono text-slate-800 dark:text-slate-200">
                    {domainBinding?.tools?.length || 5} tools • {domainBinding?.resources?.length || 3} resources
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Test Case Categories */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-2">
              Case Categories to Synthesize
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[
                {
                  id: TEST_CASE_KINDS.BENIGN,
                  title: 'Benign Control',
                  desc: 'Legitimate authorized requests within safety thresholds.',
                  color: 'indigo',
                },
                {
                  id: TEST_CASE_KINDS.DIRECT_POLICY_CHALLENGE,
                  title: 'Direct Challenge',
                  desc: 'Adversarial user prompts attempting prohibited tool calls or overrides.',
                  color: 'amber',
                },
                {
                  id: TEST_CASE_KINDS.INDIRECT_PROMPT_INJECTION,
                  title: 'Indirect Injection',
                  desc: 'Untrusted content embedded in support tickets or tool outputs.',
                  color: 'rose',
                },
              ].map((cat) => {
                const isSelected = selectedCategories.includes(cat.id);
                return (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => toggleCategory(cat.id)}
                    className={`p-3.5 rounded-xl border text-left transition-all ${
                      isSelected
                        ? 'border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/40 ring-1 ring-indigo-500/20'
                        : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 opacity-60'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-bold text-slate-900 dark:text-white">
                        {cat.title}
                      </span>
                      <div
                        className={`w-4 h-4 rounded border flex items-center justify-center ${
                          isSelected
                            ? 'bg-indigo-600 border-indigo-600 text-white'
                            : 'border-slate-300 dark:border-slate-700'
                        }`}
                      >
                        {isSelected && <Check className="w-3 h-3" />}
                      </div>
                    </div>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-snug">
                      {cat.desc}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Budget & Parameter Controls */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-1">
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Per-Rule Budget Cap (1–50)
              </label>
              <input
                type="number"
                min={1}
                max={50}
                value={maxCasesPerRule}
                onChange={(e) => setMaxCasesPerRule(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Deterministic RNG Seed
              </label>
              <input
                type="number"
                value={seed}
                onChange={(e) => setSeed(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white"
              />
            </div>

            <div className="flex flex-col justify-end">
              <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-700 dark:text-slate-300 py-2">
                <input
                  type="checkbox"
                  checked={includeBenignControls}
                  onChange={(e) => setIncludeBenignControls(e.target.checked)}
                  className="rounded text-indigo-600 focus:ring-indigo-500"
                />
                <span>Include Benign Controls</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-700 dark:text-slate-300">
                <input
                  type="checkbox"
                  checked={includeBoundaryValues}
                  onChange={(e) => setIncludeBoundaryValues(e.target.checked)}
                  className="rounded text-indigo-600 focus:ring-indigo-500"
                />
                <span>Threshold Equality Boundaries</span>
              </label>
            </div>

            <div className="flex flex-col justify-end">
              <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-700 dark:text-slate-300 py-2">
                <input
                  type="checkbox"
                  checked={autoValidate}
                  onChange={(e) => setAutoValidate(e.target.checked)}
                  className="rounded text-indigo-600 focus:ring-indigo-500"
                />
                <span>Auto-validate Batch</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-700 dark:text-slate-300">
                <input
                  type="checkbox"
                  checked={autoFreeze}
                  onChange={(e) => setAutoFreeze(e.target.checked)}
                  className="rounded text-indigo-600 focus:ring-indigo-500"
                />
                <span>Auto-freeze Validated Cases</span>
              </label>
            </div>
          </div>

          {/* Submission Button and Feedback */}
          {error && (
            <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-800 dark:text-rose-300 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {successMessage && (
            <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-300 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}

          <div className="pt-2 flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <Info className="w-3.5 h-3.5" />
              <span>Planned test generation isolates oracle assertions from agent task inputs.</span>
            </div>

            <button
              type="submit"
              disabled={isGenerating || !isContractReady || !isBindingReady || !isProjectReady}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 dark:disabled:bg-slate-800 text-white font-semibold text-xs transition-colors shadow-sm cursor-pointer disabled:cursor-not-allowed"
            >
              {isGenerating ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Generating Policy Test Cases...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Generate Test Cases Batch</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Generation Report Card (when batch is returned) */}
      {generationReport && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-5 animate-in fade-in duration-200">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-100 dark:border-slate-800">
            <div>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 px-2 py-0.5 rounded">
                Generation Batch Report
              </span>
              <h4 className="text-sm font-bold text-slate-900 dark:text-white font-mono mt-1">
                Batch ID: {generationReport.batch_id}
              </h4>
              <p className="text-xs text-slate-400 font-mono">
                Config Digest: {generationReport.config_digest?.substring(0, 16)}... • Seed: {generationReport.seed}
              </p>
            </div>

            {onViewGeneratedCases && (
              <button
                type="button"
                onClick={onViewGeneratedCases}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 hover:bg-indigo-100 rounded-xl transition-colors"
              >
                <span>View {generationReport.generated_count} Generated Cases</span>
                <Play className="w-3 h-3" />
              </button>
            )}
          </div>

          {/* Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-700/60 text-center">
              <span className="text-xl font-bold text-slate-900 dark:text-white">
                {generationReport.generated_count}
              </span>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5 font-medium">Generated</p>
            </div>
            <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200/60 dark:border-emerald-800/60 text-center">
              <span className="text-xl font-bold text-emerald-600 dark:text-emerald-400">
                {generationReport.validated_count}
              </span>
              <p className="text-[11px] text-emerald-700 dark:text-emerald-300 mt-0.5 font-medium">Validated</p>
            </div>
            <div className="p-3 rounded-xl bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-200/60 dark:border-indigo-800/60 text-center">
              <span className="text-xl font-bold text-indigo-600 dark:text-indigo-400">
                {generationReport.frozen_count}
              </span>
              <p className="text-[11px] text-indigo-700 dark:text-indigo-300 mt-0.5 font-medium">Frozen</p>
            </div>
            <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200/60 dark:border-rose-800/60 text-center">
              <span className="text-xl font-bold text-rose-600 dark:text-rose-400">
                {generationReport.rejected_count}
              </span>
              <p className="text-[11px] text-rose-700 dark:text-rose-300 mt-0.5 font-medium">Rejected</p>
            </div>
            <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200/60 dark:border-amber-800/60 text-center">
              <span className="text-xl font-bold text-amber-600 dark:text-amber-400">
                {generationReport.review_needed_count}
              </span>
              <p className="text-[11px] text-amber-700 dark:text-amber-300 mt-0.5 font-medium">Needs Review</p>
            </div>
            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-700/60 text-center">
              <span className="text-xl font-bold text-slate-500 dark:text-slate-400">
                {generationReport.duplicate_count}
              </span>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5 font-medium">Duplicates</p>
            </div>
          </div>

          {/* Gaps, Omissions, and Planned Coverage Details */}
          {(generationReport.unsupported_rules?.length > 0 ||
            generationReport.readiness_gaps?.length > 0 ||
            generationReport.budget_omissions?.length > 0) && (
            <div className="p-4 rounded-xl bg-amber-50/60 dark:bg-amber-950/20 border border-amber-200/60 dark:border-amber-900/40 space-y-2 text-xs">
              <p className="font-bold text-amber-900 dark:text-amber-300 flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                Generation Gaps and Budget Omissions
              </p>
              {generationReport.unsupported_rules?.length > 0 && (
                <div className="text-amber-800 dark:text-amber-400">
                  <span className="font-semibold">Unsupported Rules: </span>
                  {generationReport.unsupported_rules.join(', ')}
                </div>
              )}
              {generationReport.readiness_gaps?.length > 0 && (
                <div className="text-amber-800 dark:text-amber-400">
                  <span className="font-semibold">Readiness Gaps: </span>
                  {generationReport.readiness_gaps.join(', ')}
                </div>
              )}
              {generationReport.budget_omissions?.length > 0 && (
                <div className="text-amber-800 dark:text-amber-400">
                  <span className="font-semibold">Budget Omissions: </span>
                  {generationReport.budget_omissions.join(', ')}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
