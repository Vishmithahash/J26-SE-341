import React, { useState } from 'react';
import {
  FlaskConical,
  Lock,
  Play,
  Download,
  Terminal,
  RefreshCw,
  AlertTriangle,
} from 'lucide-react';

const BASELINE_DESCRIPTIONS = {
  B1_FINAL_STATE_ONLY: {
    name: 'B1: Final-State Only',
    desc: 'Evaluates only the terminal outcome and final database snapshot. Cannot localize earliest divergence or trace violations.',
    projection: 'FINAL_STATE_AND_OUTCOME_ONLY',
  },
  B2_TRACE_ONLY: {
    name: 'B2: Ordered Trace Only',
    desc: 'Checks temporal sequence of tool-call actions without inspecting intermediate state snapshots or database mutations.',
    projection: 'ORDERED_EVENTS_ONLY',
  },
  B3_MILESTONE_BASED: {
    name: 'B3: Milestone Checkpoints',
    desc: 'Monitors explicit milestone events along happy paths without fine-grained EFSM state guards or invariant checking.',
    projection: 'MILESTONE_CHECKPOINTS_ONLY',
  },
  B4_FULL_C2: {
    name: 'B4: Full C2 (State-Aware EFSM)',
    desc: 'Full Extended Finite State Machine conformance evaluation with independent state snapshots, state diffs, first-proven divergence localization, and four-tier coverage.',
    projection: 'FULL_PERMITTED_EVIDENCE',
  },
};

export const ResearchWorkspace = ({
  projectId: _projectId,
  researchState,
}) => {
  const {
    datasets,
    selectedDatasetSummary,
    selectedDatasetManifest,
    experiments,
    selectedExperimentSummary,
    baselineMetrics,
    casePredictions,
    partitionFilter,
    methodFilter,
    isLoadingDatasets: _isLoadingDatasets,
    isLoadingManifest,
    isLoadingExperiments: _isLoadingExperiments,
    isLoadingBaselines,
    isLoadingCases,
    isExecutingExperiment,
    isFreezingDataset,
    actionError,
    setSelectedDatasetSummary,
    setSelectedExperimentSummary,
    setPartitionFilter,
    setMethodFilter,
    freezeDataset,
    runComparativeExperiment,
    exportMetrics,
    refreshDatasets,
    refreshExperiments,
    clearActionError,
  } = researchState;

  const [activeTab, setActiveTab] = useState('comparisons'); // 'comparisons' | 'dataset' | 'cases' | 'cli'
  const [showRunModal, setShowRunModal] = useState(false);
  const [newExpId, setNewExpId] = useState(() => `exp_${Math.floor(Math.random() * 1000000)}`);
  const [newExpName, setNewExpName] = useState('Comparative Baseline Experiment');
  const [newTargetPartition, setNewTargetPartition] = useState('ALL_CASES');

  // Active dataset manifest cases
  const manifestCases = selectedDatasetManifest?.cases || [];
  const filteredCases = manifestCases.filter((c) => {
    if (partitionFilter === 'ALL_CASES') return true;
    return c.partition === partitionFilter;
  });

  // Baselines report data
  const metricsByMethod = baselineMetrics?.metrics_by_method || {};
  const metricsByPartition = baselineMetrics?.metrics_by_partition || {};
  const partitionMetrics = partitionFilter !== 'ALL_CASES' && metricsByPartition[partitionFilter]
    ? metricsByPartition[partitionFilter]
    : metricsByMethod;

  const handleRunExperimentSubmit = async (e) => {
    e.preventDefault();
    if (!selectedDatasetSummary) return;

    try {
      await runComparativeExperiment({
        experiment_id: newExpId.trim(),
        name: newExpName.trim(),
        dataset_id: selectedDatasetSummary.dataset_id,
        dataset_version: selectedDatasetSummary.version,
        target_partition: newTargetPartition,
      });
      setShowRunModal(false);
    } catch {
      // Handled in hook
    }
  };

  return (
    <div className="space-y-6">
      {/* Action Error Banner */}
      {actionError && (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-xs text-rose-800 dark:text-rose-200 flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{actionError}</span>
          </div>
          <button
            type="button"
            onClick={clearActionError}
            className="text-xs font-semibold text-rose-700 dark:text-rose-300 hover:underline shrink-0"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Top Research Header & Dataset / Experiment Selector */}
      <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-purple-50 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400">
              <FlaskConical className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                  Research Benchmarks & Baseline Comparisons (B1 – B4)
                </h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-purple-100 dark:bg-purple-950 text-purple-700 dark:text-purple-300">
                  Empirical Evaluation
                </span>
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                Evaluates defect detection, first divergence localization accuracy, and overhead across standard evaluation baselines.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start md:self-auto">
            <button
              type="button"
              onClick={() => {
                refreshDatasets();
                refreshExperiments();
              }}
              className="p-2 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition-colors"
              title="Refresh research data"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>

            {selectedDatasetSummary && !selectedDatasetSummary.is_frozen && (
              <button
                type="button"
                disabled={isFreezingDataset}
                onClick={() => freezeDataset(selectedDatasetSummary.dataset_id, selectedDatasetSummary.version)}
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 text-xs font-semibold hover:bg-amber-100 transition-colors"
                title="Freeze dataset manifest to prevent partition or label mutations"
              >
                <Lock className="w-3.5 h-3.5" />
                <span>{isFreezingDataset ? 'Freezing...' : 'Freeze Dataset'}</span>
              </button>
            )}

            <button
              type="button"
              disabled={!selectedDatasetSummary || isExecutingExperiment}
              onClick={() => setShowRunModal(true)}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white text-xs font-semibold shadow-xs transition-colors"
            >
              <Play className="w-3.5 h-3.5" />
              <span>Run Baseline Experiment</span>
            </button>
          </div>
        </div>

        {/* Dataset & Experiment Selectors Bar */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 pt-2 border-t border-slate-100 dark:border-slate-800 text-xs">
          {/* Dataset Selector */}
          <div>
            <label className="text-[10px] font-semibold text-slate-400 uppercase">
              Benchmark Dataset:
            </label>
            <select
              value={selectedDatasetSummary?.dataset_id ? `${selectedDatasetSummary.dataset_id}:${selectedDatasetSummary.version}` : ''}
              onChange={(e) => {
                const [dId, ver] = e.target.value.split(':');
                const match = datasets.find((d) => d.dataset_id === dId && d.version === ver);
                setSelectedDatasetSummary(match || null);
              }}
              className="w-full mt-1 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 font-mono text-xs"
            >
              {datasets.length === 0 ? (
                <option value="">No datasets loaded</option>
              ) : (
                datasets.map((d) => (
                  <option key={`${d.dataset_id}:${d.version}`} value={`${d.dataset_id}:${d.version}`}>
                    {d.name || d.dataset_id} v{d.version} ({d.case_count} cases) {d.is_frozen ? '[FROZEN]' : ''}
                  </option>
                ))
              )}
            </select>
          </div>

          {/* Experiment Selector */}
          <div>
            <label className="text-[10px] font-semibold text-slate-400 uppercase">
              Completed Experiment:
            </label>
            <select
              value={selectedExperimentSummary?.experiment_id || ''}
              onChange={(e) => {
                const match = experiments.find((exp) => exp.experiment_id === e.target.value);
                setSelectedExperimentSummary(match || null);
              }}
              className="w-full mt-1 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 font-mono text-xs"
            >
              {experiments.length === 0 ? (
                <option value="">No experiments run yet</option>
              ) : (
                experiments.map((exp) => (
                  <option key={exp.experiment_id} value={exp.experiment_id}>
                    {exp.name} ({exp.experiment_id})
                  </option>
                ))
              )}
            </select>
          </div>

          {/* Partition Filter */}
          <div>
            <label className="text-[10px] font-semibold text-slate-400 uppercase">
              Partition Split:
            </label>
            <select
              value={partitionFilter}
              onChange={(e) => setPartitionFilter(e.target.value)}
              className="w-full mt-1 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-xs font-semibold"
            >
              <option value="ALL_CASES">All Dataset Partitions</option>
              <option value="DEVELOPMENT">DEVELOPMENT Split Only</option>
              <option value="HELD_OUT">HELD_OUT Split Only (Generalization)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2 text-xs font-semibold">
        <button
          type="button"
          onClick={() => setActiveTab('comparisons')}
          className={`px-3 py-1.5 rounded-lg transition-colors ${
            activeTab === 'comparisons'
              ? 'bg-purple-600 text-white'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          Baseline Comparison Results (B1–B4)
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('dataset')}
          className={`px-3 py-1.5 rounded-lg transition-colors ${
            activeTab === 'dataset'
              ? 'bg-purple-600 text-white'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          Dataset Manifest & Cases ({manifestCases.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('cases')}
          className={`px-3 py-1.5 rounded-lg transition-colors ${
            activeTab === 'cases'
              ? 'bg-purple-600 text-white'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          Per-Case Method Predictions ({casePredictions.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('cli')}
          className={`px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1 ${
            activeTab === 'cli'
              ? 'bg-purple-600 text-white'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <Terminal className="w-3.5 h-3.5" />
          <span>CLI Pipeline Gap</span>
        </button>
      </div>

      {/* TAB 1: COMPARATIVE BASELINE RESULTS TABLE */}
      {activeTab === 'comparisons' && (
        <div className="space-y-4">
          {isLoadingBaselines ? (
            <div className="p-12 text-center text-xs text-slate-500 border border-slate-200 dark:border-slate-800 rounded-xl bg-white dark:bg-slate-900">
              <div className="w-5 h-5 border-2 border-purple-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
              Loading baseline comparative metrics...
            </div>
          ) : Object.keys(partitionMetrics).length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl bg-white/40 dark:bg-slate-900/20 space-y-2">
              <p>No baseline experiment results available for the selected experiment and partition.</p>
              <button
                type="button"
                onClick={() => setShowRunModal(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-600 text-white text-xs font-semibold"
              >
                <Play className="w-3.5 h-3.5" />
                Run Baseline Experiment
              </button>
            </div>
          ) : (
            <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <h3 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                    Comparative Defect Detection & Localization Matrix
                  </h3>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                    Partition: <span className="font-semibold text-slate-700 dark:text-slate-300">{partitionFilter}</span> • Experiment:{' '}
                    <span className="font-mono">{selectedExperimentSummary?.experiment_id}</span>
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => exportMetrics(selectedExperimentSummary?.experiment_id, 'csv')}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-semibold transition-colors"
                  >
                    <Download className="w-3 h-3" />
                    <span>Export CSV</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => exportMetrics(selectedExperimentSummary?.experiment_id, 'json')}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-semibold transition-colors"
                  >
                    <Download className="w-3 h-3" />
                    <span>Export JSON</span>
                  </button>
                </div>
              </div>

              {/* Research Metrics Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-800 text-[10px] text-slate-400 uppercase font-semibold">
                      <th className="py-2.5 px-3">Evaluation Method</th>
                      <th className="py-2.5 px-2">Samples</th>
                      <th className="py-2.5 px-2">Precision</th>
                      <th className="py-2.5 px-2">Recall</th>
                      <th className="py-2.5 px-2">F1 Score</th>
                      <th className="py-2.5 px-2">Localization Acc.</th>
                      <th className="py-2.5 px-2">Mutation Det.</th>
                      <th className="py-2.5 px-2">State-Fault Det.</th>
                      <th className="py-2.5 px-2">Median Overhead</th>
                      <th className="py-2.5 px-2">P95 Overhead</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono text-[11px]">
                    {['B1_FINAL_STATE_ONLY', 'B2_TRACE_ONLY', 'B3_MILESTONE_BASED', 'B4_FULL_C2'].map((mId) => {
                      const mData = partitionMetrics[mId];
                      if (!mData) return null;
                      const det = mData.detection_metrics || {};
                      const loc = mData.localization_metrics || {};
                      const isC2 = mId === 'B4_FULL_C2';

                      const formatPct = (val) => (val != null ? `${(val * 100).toFixed(1)}%` : 'N/A');
                      const formatNum = (val) => (val != null ? val.toFixed(3) : 'N/A');

                      return (
                        <tr
                          key={mId}
                          className={`${
                            isC2
                              ? 'bg-purple-50/50 dark:bg-purple-950/20 font-bold text-purple-900 dark:text-purple-200'
                              : 'text-slate-800 dark:text-slate-200 hover:bg-slate-50/50 dark:hover:bg-slate-800/50'
                          }`}
                        >
                          <td className="py-3 px-3 font-sans font-semibold">
                            <div>{BASELINE_DESCRIPTIONS[mId]?.name || mId}</div>
                            <span className="text-[10px] font-mono text-slate-400 font-normal">
                              {BASELINE_DESCRIPTIONS[mId]?.projection}
                            </span>
                          </td>
                          <td className="py-3 px-2">{mData.sample_count}</td>
                          <td className="py-3 px-2">{formatPct(det.precision)}</td>
                          <td className="py-3 px-2">{formatPct(det.recall)}</td>
                          <td className="py-3 px-2 text-indigo-600 dark:text-indigo-400 font-bold">
                            {formatNum(det.f1_score)}
                          </td>
                          <td className="py-3 px-2">
                            {loc.can_localize ? (
                              <span className="text-emerald-600 dark:text-emerald-400">
                                {formatPct(loc.accuracy)}
                              </span>
                            ) : (
                              <span className="text-slate-400 italic text-[10px]">
                                Unavailable
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-2">{formatPct(det.mutation_detection_score)}</td>
                          <td className="py-3 px-2">{formatPct(det.state_effect_fault_detection_score)}</td>
                          <td className="py-3 px-2">{mData.overhead_median_ms?.toFixed(2)}ms</td>
                          <td className="py-3 px-2">{mData.overhead_p95_ms?.toFixed(2)}ms</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Research Methodology Footnote */}
              <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-slate-800 text-[11px] text-slate-500 space-y-1">
                <span className="font-semibold text-slate-700 dark:text-slate-300">Methodology & Empirical Notes:</span>
                <ul className="list-disc pl-5 space-y-0.5">
                  <li>Binary classification treats workflow conformance violations as the positive class.</li>
                  <li>First-proven divergence localization accuracy is computed strictly over applicable cases with established ground-truth divergence points. B1 and B2 methods cannot localize earliest divergence and display truthfully as Unavailable.</li>
                  <li>All metrics, confidence baselines, and execution overheads are computed by the backend evaluation engine and preserved immutably.</li>
                </ul>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: DATASET MANIFEST AND CASES */}
      {activeTab === 'dataset' && (
        <div className="space-y-4">
          {isLoadingManifest ? (
            <div className="p-8 text-center text-xs text-slate-500">
              <div className="w-5 h-5 border-2 border-purple-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
              Loading dataset manifest...
            </div>
          ) : selectedDatasetManifest ? (
            <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                      {selectedDatasetManifest.name}
                    </h3>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                      v{selectedDatasetManifest.version}
                    </span>
                    {selectedDatasetManifest.is_frozen && (
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 flex items-center gap-1">
                        <Lock className="w-3 h-3" />
                        FROZEN
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Digest: <code className="font-mono">{selectedDatasetManifest.manifest_digest || 'None'}</code>
                  </p>
                </div>

                <div className="flex items-center gap-2 text-xs font-mono">
                  <span className="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                    Dev: {selectedDatasetManifest.development_count}
                  </span>
                  <span className="px-2.5 py-1 rounded-lg bg-purple-50 dark:bg-purple-950 text-purple-700 dark:text-purple-300">
                    Held-Out: {selectedDatasetManifest.held_out_count}
                  </span>
                </div>
              </div>

              {/* Cases Table */}
              <div className="overflow-x-auto max-h-96">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-800 text-[10px] text-slate-400 uppercase font-semibold">
                      <th className="py-2 px-2">Case ID</th>
                      <th className="py-2 px-2">Domain</th>
                      <th className="py-2 px-2">Partition</th>
                      <th className="py-2 px-2">Violation?</th>
                      <th className="py-2 px-2">Mutation Family</th>
                      <th className="py-2 px-2">Review Status</th>
                      <th className="py-2 px-2">Divergence Step</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono text-[11px]">
                    {filteredCases.map((c) => {
                      const gt = c.ground_truth || {};
                      return (
                        <tr key={c.case_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/50">
                          <td className="py-2 px-2 font-bold text-slate-900 dark:text-white">{c.case_id}</td>
                          <td className="py-2 px-2 text-slate-600 dark:text-slate-400 font-sans">{c.domain}</td>
                          <td className="py-2 px-2">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                              c.partition === 'HELD_OUT'
                                ? 'bg-purple-100 dark:bg-purple-950 text-purple-700 dark:text-purple-300 font-semibold'
                                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                            }`}>
                              {c.partition}
                            </span>
                          </td>
                          <td className="py-2 px-2">
                            {gt.is_workflow_violation ? (
                              <span className="text-rose-600 font-semibold">Violation</span>
                            ) : (
                              <span className="text-emerald-600 font-semibold">Conforming</span>
                            )}
                          </td>
                          <td className="py-2 px-2 text-slate-600 dark:text-slate-400">{gt.mutation_family || 'NONE'}</td>
                          <td className="py-2 px-2 text-[10px] text-slate-500 font-sans">{gt.review_status}</td>
                          <td className="py-2 px-2 text-slate-500">
                            {gt.ground_truth_divergence_step != null ? `Step ${gt.ground_truth_divergence_step}` : 'N/A'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-xs text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
              No dataset manifest loaded. Select a dataset above.
            </div>
          )}
        </div>
      )}

      {/* TAB 3: PER-CASE METHOD PREDICTIONS */}
      {activeTab === 'cases' && (
        <div className="space-y-4">
          <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <span className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                Fine-Grained Case Predictions ({casePredictions.length})
              </span>

              {/* Method filter */}
              <div className="flex items-center gap-2 text-xs">
                <span className="text-slate-400 text-[10px] uppercase font-semibold">Filter Method:</span>
                <select
                  value={methodFilter}
                  onChange={(e) => setMethodFilter(e.target.value)}
                  className="px-2.5 py-1 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 font-mono text-xs"
                >
                  <option value="">All Baselines</option>
                  <option value="B1_FINAL_STATE_ONLY">B1_FINAL_STATE_ONLY</option>
                  <option value="B2_TRACE_ONLY">B2_TRACE_ONLY</option>
                  <option value="B3_MILESTONE_BASED">B3_MILESTONE_BASED</option>
                  <option value="B4_FULL_C2">B4_FULL_C2</option>
                </select>
              </div>
            </div>

            {isLoadingCases ? (
              <div className="p-8 text-center text-xs text-slate-500">
                <div className="w-5 h-5 border-2 border-purple-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                Loading case predictions...
              </div>
            ) : casePredictions.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
                No case prediction records available. Select an experiment above.
              </div>
            ) : (
              <div className="overflow-x-auto max-h-96">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-800 text-[10px] text-slate-400 uppercase font-semibold">
                      <th className="py-2 px-2">Case ID</th>
                      <th className="py-2 px-2">Method</th>
                      <th className="py-2 px-2">Partition</th>
                      <th className="py-2 px-2">Verdict</th>
                      <th className="py-2 px-2">Violation?</th>
                      <th className="py-2 px-2">Localize?</th>
                      <th className="py-2 px-2">Predicted Step</th>
                      <th className="py-2 px-2">Overhead</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono text-[11px]">
                    {casePredictions.map((cp, idx) => (
                      <tr key={idx} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/50">
                        <td className="py-2 px-2 font-bold text-slate-900 dark:text-white">{cp.case_id}</td>
                        <td className="py-2 px-2">{cp.method_id}</td>
                        <td className="py-2 px-2 text-[10px]">{cp.partition}</td>
                        <td className="py-2 px-2">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                            cp.verdict === 'PASS' || cp.verdict === 'EXPECTED REJECTION PASS'
                              ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                              : 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                          }`}>
                            {cp.verdict}
                          </span>
                        </td>
                        <td className="py-2 px-2">{cp.is_violation ? 'Yes' : 'No'}</td>
                        <td className="py-2 px-2">{cp.can_localize ? 'Yes' : 'No'}</td>
                        <td className="py-2 px-2">
                          {cp.first_divergence_predicted_step != null ? `Step ${cp.first_divergence_predicted_step}` : 'N/A'}
                        </td>
                        <td className="py-2 px-2">{cp.evaluator_timing_ms?.toFixed(2)}ms</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 4: CLI PIPELINE GAP DOCUMENTATION */}
      {activeTab === 'cli' && (
        <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-4 text-xs">
          <div className="flex items-center gap-2 font-bold text-slate-900 dark:text-white uppercase tracking-wider">
            <Terminal className="w-4 h-4 text-purple-600" />
            <span>Research Benchmark CLI Capabilities</span>
          </div>

          <div className="p-4 rounded-xl bg-slate-900 text-slate-200 font-mono text-xs space-y-2">
            <div className="text-slate-400"># Run the full 125-case multi-domain benchmark via backend CLI:</div>
            <div className="text-emerald-400 font-bold">
              python -m app.components.c2_state_aware_workflow.experiments.cli
            </div>
            <div className="text-slate-400 pt-2"># Generated artifacts are persisted to backend_c2_benchmark_results/:</div>
            <div className="text-slate-300 text-[11px] pl-4 space-y-1">
              <div>- c2_benchmark_manifest.json (125 frozen cases)</div>
              <div>- c2_benchmark_report.json (full research metrics)</div>
              <div>- c2_benchmark_metrics.csv (comparative summary table)</div>
              <div>- c2_benchmark_case_predictions.csv (fine-grained predictions)</div>
            </div>
          </div>

          <p className="text-[11px] text-slate-500 leading-relaxed">
            In compliance with strict security requirements, the frontend does not invoke raw shell commands or launch external CLI subprocesses.
            Instead, research datasets, baseline evaluations, and metrics can be configured, executed, and inspected via the C2 backend's REST APIs above.
          </p>
        </div>
      )}

      {/* Run Experiment Modal */}
      {showRunModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs">
          <div className="relative w-full max-w-lg rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <Play className="w-4 h-4 text-purple-600" />
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                  Execute Comparative Baseline Experiment
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowRunModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleRunExperimentSubmit} className="space-y-4 text-xs">
              <div>
                <label className="font-semibold text-slate-700 dark:text-slate-300">Experiment ID:</label>
                <input
                  type="text"
                  required
                  value={newExpId}
                  onChange={(e) => setNewExpId(e.target.value)}
                  className="w-full mt-1 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 font-mono text-xs"
                />
              </div>

              <div>
                <label className="font-semibold text-slate-700 dark:text-slate-300">Experiment Name:</label>
                <input
                  type="text"
                  required
                  value={newExpName}
                  onChange={(e) => setNewExpName(e.target.value)}
                  className="w-full mt-1 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-xs"
                />
              </div>

              <div>
                <label className="font-semibold text-slate-700 dark:text-slate-300">Target Partition:</label>
                <select
                  value={newTargetPartition}
                  onChange={(e) => setNewTargetPartition(e.target.value)}
                  className="w-full mt-1 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-xs"
                >
                  <option value="ALL_CASES">All Dataset Partitions</option>
                  <option value="DEVELOPMENT">DEVELOPMENT Split Only</option>
                  <option value="HELD_OUT">HELD_OUT Split Only</option>
                </select>
              </div>

              <div className="p-3 rounded-lg bg-purple-50 dark:bg-purple-950/40 text-[11px] text-purple-800 dark:text-purple-300">
                Dataset: <code className="font-mono">{selectedDatasetSummary?.dataset_id} v{selectedDatasetSummary?.version}</code>.
                Evaluates B1 (Final-state), B2 (Trace-only), B3 (Milestone), and B4 (Full C2).
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-200 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowRunModal(false)}
                  className="px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-700 text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isExecutingExperiment}
                  className="px-5 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white text-xs font-semibold shadow-xs"
                >
                  {isExecutingExperiment ? 'Executing Experiment...' : 'Execute Experiment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
