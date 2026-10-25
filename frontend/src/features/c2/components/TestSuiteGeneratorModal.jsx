import React, { useEffect, useState } from 'react';
import {
  X,
  Play,
  AlertCircle,
  Sliders,
  ShieldCheck,
  Dna,
} from 'lucide-react';

const SUPPORTED_MUTATION_TYPES = [
  { id: 'skipped_step', label: 'Skipped Step', desc: 'Agent omits a required milestone transition' },
  { id: 'reordered_step', label: 'Reordered Step', desc: 'Transitions executed in swapped temporal order' },
  { id: 'repeated_step', label: 'Repeated Step', desc: 'Duplicate execution of a non-idempotent action' },
  { id: 'illegal_transition', label: 'Illegal Transition', desc: 'Invalid state transition bypassing guards' },
  { id: 'wrong_entity', label: 'Wrong Entity Binding', desc: 'Arguments bound to wrong target entity ID' },
  { id: 'missing_effect', label: 'Missing Expected Effect', desc: 'Tool invoked without expected variable mutation' },
  { id: 'unexpected_protected_state_change', label: 'Protected State Mutation', desc: 'Mutation of invariant/protected fields' },
  { id: 'premature_termination', label: 'Premature Termination', desc: 'Trace terminates before reaching accepting state' },
];

export const TestSuiteGeneratorModal = ({
  isOpen,
  onClose,
  approvedModels,
  onGenerate,
  isGenerating,
}) => {
  const defaultModel = approvedModels?.[0] || null;

  const [selectedModelId, setSelectedModelId] = useState(defaultModel?.model_id || '');
  const [selectedVersion, setSelectedVersion] = useState(defaultModel?.version || '');
  const [seed, setSeed] = useState(42);
  const [caseBudget, setCaseBudget] = useState(20);
  const [maxDepth, setMaxDepth] = useState(15);
  const [maxLoopVisits, setMaxLoopVisits] = useState(1);
  const [includeAlternatives, setIncludeAlternatives] = useState(true);
  const [includeNegativeRejections, setIncludeNegativeRejections] = useState(true);
  const [includeMutations, setIncludeMutations] = useState(true);
  const [mutationBudget, setMutationBudget] = useState(8);
  const [enabledMutations, setEnabledMutations] = useState(
    SUPPORTED_MUTATION_TYPES.map((m) => m.id)
  );
  const [fixtureRef, setFixtureRef] = useState('synthetic_ecommerce_customer_42');

  const [localError, setLocalError] = useState(null);

  // The approved models may arrive after the modal mounted: preselect the first one then
  useEffect(() => {
    if (!selectedModelId && defaultModel) {
      setSelectedModelId(defaultModel.model_id);
      setSelectedVersion(defaultModel.version);
    }
  }, [selectedModelId, defaultModel]);

  if (!isOpen) return null;

  const handleToggleMutation = (id) => {
    setEnabledMutations((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleSelectAllMutations = () => {
    setEnabledMutations(SUPPORTED_MUTATION_TYPES.map((m) => m.id));
  };

  const handleClearMutations = () => {
    setEnabledMutations([]);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLocalError(null);

    if (!selectedModelId || !selectedVersion) {
      setLocalError('Please select a validated and approved workflow model version.');
      return;
    }

    // Inputs hold strings once edited: compare numbers ("4" > "10" is true for strings)
    if (Number(caseBudget) < 1 || Number(caseBudget) > 200) {
      setLocalError('Case budget must be between 1 and 200.');
      return;
    }

    if (includeMutations && Number(mutationBudget) > Number(caseBudget)) {
      setLocalError('Mutation budget cannot exceed total case budget.');
      return;
    }

    const payload = {
      model_id: selectedModelId,
      version: selectedVersion,
      generator_version: 'c2_generator_v1',
      seed: Number(seed),
      max_depth: Number(maxDepth),
      max_loop_visits: Number(maxLoopVisits),
      case_budget: Number(caseBudget),
      include_alternatives: Boolean(includeAlternatives),
      include_negative_rejections: Boolean(includeNegativeRejections),
      include_mutations: Boolean(includeMutations),
      mutation_budget: includeMutations ? Number(mutationBudget) : 0,
      enabled_mutation_types: includeMutations ? enabledMutations : [],
      fixture_ref: fixtureRef.trim() || 'synthetic_ecommerce_customer_42',
    };

    try {
      await onGenerate(payload);
      onClose();
    } catch (err) {
      setLocalError(err.message || 'Generation failed.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs overflow-y-auto">
      <div className="w-full max-w-2xl bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 flex items-center justify-center">
              <Sliders className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                Generate Automatic Test Suite
              </h2>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                Coverage-guided symbolic path exploration from an approved EFSM
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isGenerating}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5 max-h-[75vh] overflow-y-auto">
          {localError && (
            <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-800 dark:text-rose-200 flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <div className="text-[11px] leading-relaxed">{localError}</div>
            </div>
          )}

          {/* Target Model Selection */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-indigo-500" />
              Approved Reference Model Version (Required)
            </label>
            {approvedModels?.length === 0 ? (
              <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-xs text-amber-800 dark:text-amber-200">
                No approved models found. Test suites can only be generated from models in{' '}
                <span className="font-semibold">APPROVED</span> status. Please review and approve
                a validated model in the Models Workspace first.
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {approvedModels.map((m) => {
                  const isSelected =
                    selectedModelId === m.model_id && selectedVersion === m.version;
                  return (
                    <button
                      key={`${m.model_id}-${m.version}`}
                      type="button"
                      onClick={() => {
                        setSelectedModelId(m.model_id);
                        setSelectedVersion(m.version);
                      }}
                      className={`p-3 rounded-xl text-left border transition-all ${
                        isSelected
                          ? 'border-indigo-600 dark:border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/30 ring-1 ring-indigo-500'
                          : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 bg-white dark:bg-slate-900'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-900 dark:text-white">
                          {m.name || m.model_id}
                        </span>
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300">
                          v{m.version}
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-400 font-mono truncate mt-1">
                        Hash: {m.content_hash?.slice(0, 16)}...
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Primary Generation Parameters */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2 border-t border-slate-100 dark:border-slate-800">
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">
                Random Seed
              </label>
              <input
                type="number"
                value={seed}
                onChange={(e) => setSeed(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-xs font-mono text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
                placeholder="42"
                required
              />
              <span className="text-[10px] text-slate-400">Deterministic generator seed</span>
            </div>

            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">
                Case Budget (Max 200)
              </label>
              <input
                type="number"
                min="1"
                max="200"
                value={caseBudget}
                onChange={(e) => setCaseBudget(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-xs font-mono text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
                required
              />
              <span className="text-[10px] text-slate-400">Total test cases limit</span>
            </div>

            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">
                Max Path Depth
              </label>
              <input
                type="number"
                min="1"
                max="30"
                value={maxDepth}
                onChange={(e) => setMaxDepth(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-xs font-mono text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
                required
              />
              <span className="text-[10px] text-slate-400">Max transition depth (1-30)</span>
            </div>
          </div>

          {/* Loop Limits & Fixture Reference */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">
                Loop Unroll Limit
              </label>
              <input
                type="number"
                min="0"
                max="5"
                value={maxLoopVisits}
                onChange={(e) => setMaxLoopVisits(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-xs font-mono text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
                required
              />
              <span className="text-[10px] text-slate-400">Cycle revisit threshold (0-5)</span>
            </div>

            <div className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">
                Fixture Reference URI/ID
              </label>
              <input
                type="text"
                value={fixtureRef}
                onChange={(e) => setFixtureRef(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-xs font-mono text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
                placeholder="synthetic_ecommerce_customer_42"
                required
              />
              <span className="text-[10px] text-slate-400">Isolation fixture key</span>
            </div>
          </div>

          {/* Category Inclusions */}
          <div className="space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800">
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Workflow Path Categories to Include:
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              <label className="flex items-center gap-2 p-3 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 cursor-pointer text-xs font-medium text-slate-800 dark:text-slate-200">
                <input
                  type="checkbox"
                  checked={includeAlternatives}
                  onChange={(e) => setIncludeAlternatives(e.target.checked)}
                  className="rounded text-indigo-600 focus:ring-indigo-500"
                />
                <div>
                  <div className="font-semibold">Alternative Paths</div>
                  <div className="text-[10px] text-slate-400">E.g. Inspection before refund</div>
                </div>
              </label>

              <label className="flex items-center gap-2 p-3 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 cursor-pointer text-xs font-medium text-slate-800 dark:text-slate-200">
                <input
                  type="checkbox"
                  checked={includeNegativeRejections}
                  onChange={(e) => setIncludeNegativeRejections(e.target.checked)}
                  className="rounded text-indigo-600 focus:ring-indigo-500"
                />
                <div>
                  <div className="font-semibold">Negative Rejections</div>
                  <div className="text-[10px] text-slate-400">E.g. Unpaid order rejection</div>
                </div>
              </label>

              <label className="flex items-center gap-2 p-3 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 cursor-pointer text-xs font-medium text-slate-800 dark:text-slate-200">
                <input
                  type="checkbox"
                  checked={includeMutations}
                  onChange={(e) => setIncludeMutations(e.target.checked)}
                  className="rounded text-indigo-600 focus:ring-indigo-500"
                />
                <div>
                  <div className="font-semibold">Workflow Mutations</div>
                  <div className="text-[10px] text-slate-400">Evaluator fault sensitivity</div>
                </div>
              </label>
            </div>
          </div>

          {/* Mutation Settings (Expanded when includeMutations is active) */}
          {includeMutations && (
            <div className="space-y-3 p-4 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Dna className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                  <span className="text-xs font-semibold text-slate-900 dark:text-white">
                    Evaluator Mutation Configuration
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[11px]">
                  <button
                    type="button"
                    onClick={handleSelectAllMutations}
                    className="text-indigo-600 dark:text-indigo-400 hover:underline"
                  >
                    Select All
                  </button>
                  <span className="text-slate-300">|</span>
                  <button
                    type="button"
                    onClick={handleClearMutations}
                    className="text-slate-500 hover:underline"
                  >
                    Clear
                  </button>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">
                  Mutation Budget (max cases to mutate)
                </label>
                <input
                  type="number"
                  min="0"
                  max="50"
                  value={mutationBudget}
                  onChange={(e) => setMutationBudget(e.target.value)}
                  className="w-40 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-mono text-slate-900 dark:text-white"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                {SUPPORTED_MUTATION_TYPES.map((type) => {
                  const isChecked = enabledMutations.includes(type.id);
                  return (
                    <label
                      key={type.id}
                      className={`flex items-start gap-2 p-2 rounded-lg border text-xs cursor-pointer transition-colors ${
                        isChecked
                          ? 'border-purple-300 dark:border-purple-900/80 bg-purple-50/40 dark:bg-purple-950/20'
                          : 'border-slate-200 dark:border-slate-800 hover:bg-white dark:hover:bg-slate-800'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => handleToggleMutation(type.id)}
                        className="rounded text-purple-600 focus:ring-purple-500 mt-0.5"
                      />
                      <div>
                        <div className="font-medium text-slate-900 dark:text-white leading-tight">
                          {type.label}
                        </div>
                        <div className="text-[10px] text-slate-500 dark:text-slate-400">
                          {type.desc}
                        </div>
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {/* Footer Action Buttons */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200 dark:border-slate-800">
            <button
              type="button"
              onClick={onClose}
              disabled={isGenerating}
              className="px-4 py-2 rounded-xl text-xs font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isGenerating || approvedModels?.length === 0}
              className="px-5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-semibold shadow-xs flex items-center gap-2 transition-colors"
            >
              {isGenerating ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Exploring Paths & Generating...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Generate Test Suite</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
