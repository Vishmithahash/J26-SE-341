/**
 * Component 4 (C4) - Research Evaluation & Proposal Benchmarks Section
 * Complete interface for:
 * 1. Versioned evaluation datasets (DEV, PILOT, HELD_OUT splits) & benchmark freezing.
 * 2. Baseline strategies (C4 vs Manual, Generic Model, Text-Only) & reduced-evidence ablations.
 * 3. Independent reviewer judgments and Cohen's Kappa inter-rater agreement calculation.
 * 4. Experiment orchestration and consolidated metrics reporting across all 6 proposal categories.
 */

import React, { useState } from 'react';
import {
  FlaskConical,
  Database,
  Users,
  CheckCircle2,
  AlertTriangle,
  Play,
  Lock,
  Scale,
  ShieldCheck,
  TrendingUp,
  Clock,
  FileText,
} from 'lucide-react';
import {
  RESEARCH_STRATEGIES,
  RESEARCH_ABLATIONS,
  DATASET_SPLITS,
} from '../../api/types.js';

export function ResearchEvaluationSection({ evaluation, projectId }) {
  const {
    datasets,
    selectedDataset,
    setSelectedDataset,
    registerDataset,
    freezeDataset,
    selectedStrategy,
    setSelectedStrategy,
    selectedAblation,
    setSelectedAblation,
    selectedSplit,
    setSelectedSplit,
    repeatCount,
    setRepeatCount,
    seed,
    setSeed,
    activeExperiment,
    experimentReport,
    runExperiment,
    reviewer1,
    setReviewer1,
    reviewer2,
    setReviewer2,
    agreementResult,
    calculateAgreement,
    isRegisteringDataset,
    isFreezingDataset,
    isCreatingExperiment,
    isExecutingExperiment,
    isCalculatingAgreement,
    error,
    successMessage,
  } = evaluation;

  const [datasetIdInput, setDatasetIdInput] = useState('c4-benchmark-ecommerce-v1');

  const handleQuickRegisterDataset = () => {
    const payload = {
      dataset_id: datasetIdInput,
      version: 1,
      dataset_hash: 'hash-synthetic-dataset-' + Date.now().toString(16),
      project_id: projectId,
      domain_id: 'domain-ecommerce-c4',
      cases: [
        {
          case_id: 'case-eval-001',
          project_id: projectId,
          domain_id: 'domain-ecommerce-c4',
          policy_family: 'AUTHORIZATION',
          case_category: 'DIRECT_POLICY_CHALLENGE',
          scenario_group_id: 'refund_escalation',
          source_type: 'USER_PROMPT',
          contract_id: 'contract-ecommerce-v1',
          contract_version: 1,
          expected_applicability: true,
          expected_verdict: 'FAIL',
          split: 'DEV',
        },
        {
          case_id: 'case-eval-002',
          project_id: projectId,
          domain_id: 'domain-ecommerce-c4',
          policy_family: 'INSTRUCTION_AUTHORITY',
          case_category: 'INDIRECT_PROMPT_INJECTION',
          scenario_group_id: 'ticket_injection',
          source_type: 'SUPPORT_TICKET',
          contract_id: 'contract-ecommerce-v1',
          contract_version: 1,
          expected_applicability: true,
          expected_verdict: 'FAIL',
          split: 'PILOT',
        },
        {
          case_id: 'case-eval-003',
          project_id: projectId,
          domain_id: 'domain-ecommerce-c4',
          policy_family: 'CONFIDENTIALITY',
          case_category: 'BENIGN',
          scenario_group_id: 'order_lookup',
          source_type: 'USER_PROMPT',
          contract_id: 'contract-ecommerce-v1',
          contract_version: 1,
          expected_applicability: true,
          expected_verdict: 'PASS',
          split: 'HELD_OUT',
        },
      ],
      split_counts: { DEV: 1, PILOT: 1, HELD_OUT: 1 },
      is_frozen: false,
    };
    registerDataset(payload);
  };

  const renderMetricCard = (title, metric, suffix = '%', isCount = false) => {
    if (!metric) {
      return (
        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800">
          <span className="text-[11px] text-slate-400 block">{title}</span>
          <span className="text-sm font-bold text-slate-500">N/A</span>
        </div>
      );
    }

    const value = metric.value !== null && metric.value !== undefined ? (isCount ? metric.value : (metric.value * 100).toFixed(1) + suffix) : 'N/A';
    const sample = metric.denominator !== undefined && metric.numerator !== undefined ? `${metric.numerator}/${metric.denominator}` : null;

    return (
      <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-1">
        <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 block">{title}</span>
        <div className="flex items-baseline justify-between">
          <span className="text-base font-extrabold text-slate-900 dark:text-white font-mono">{value}</span>
          {sample && <span className="text-[10px] text-slate-400 font-mono">({sample})</span>}
        </div>
        {metric.status && metric.status !== 'COMPUTED' && (
          <span className="text-[10px] text-amber-600 dark:text-amber-400 block">{metric.status}</span>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-150">
      {/* Header Banner */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-indigo-100 dark:bg-indigo-950/80 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                PHASE 3 ACTIVE
              </span>
              <h2 className="text-xl font-extrabold text-slate-900 dark:text-white tracking-tight">
                Research Evaluation & Proposal Benchmarks
              </h2>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-400 max-w-3xl leading-relaxed">
              Empirical evaluation suite supporting versioned dataset partitions (DEV / PILOT / HELD_OUT), Cohen's Kappa inter-rater agreement for independent review packets, baseline strategy comparisons, and authentic backend-computed metrics across all 6 proposal research categories.
            </p>
          </div>
        </div>

        {/* Banners */}
        {error && (
          <div className="mt-4 p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-800 dark:text-rose-200 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {successMessage && (
          <div className="mt-4 p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-200 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}
      </div>

      {/* Grid: 1. Evaluation Datasets & 2. Inter-Rater Agreement */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Card 1: Datasets */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-indigo-50 dark:bg-indigo-950/70 border border-indigo-200 dark:border-indigo-800 flex items-center justify-center text-indigo-600 dark:text-indigo-400">
                <Database className="w-4 h-4" />
              </div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                1. Versioned Evaluation Datasets
              </h3>
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex gap-2">
              <input
                type="text"
                value={datasetIdInput}
                onChange={(e) => setDatasetIdInput(e.target.value)}
                placeholder="Dataset identifier..."
                className="flex-1 px-3 py-1.5 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-800 dark:text-slate-200"
              />
              <button
                onClick={handleQuickRegisterDataset}
                disabled={isRegisteringDataset || !projectId}
                className="px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs transition-colors shrink-0 disabled:opacity-50"
              >
                {isRegisteringDataset ? 'Registering...' : 'Register Split Dataset'}
              </button>
            </div>

            {/* Datasets List */}
            <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
              {datasets.length === 0 ? (
                <p className="text-xs text-slate-400 py-3 text-center">
                  No evaluation datasets registered yet. Click above to register a benchmark split dataset.
                </p>
              ) : (
                datasets.map((d) => (
                  <div
                    key={d.dataset_id}
                    onClick={() => setSelectedDataset(d)}
                    className={`p-3 rounded-xl border cursor-pointer transition-all ${
                      selectedDataset?.dataset_id === d.dataset_id
                        ? 'bg-indigo-50/60 dark:bg-indigo-950/40 border-indigo-300 dark:border-indigo-700'
                        : 'bg-slate-50/50 dark:bg-slate-950 border-slate-200 dark:border-slate-800 hover:border-slate-300'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-xs text-slate-900 dark:text-white">
                          {d.dataset_id}
                        </span>
                        <span className="text-[10px] text-slate-400">v{d.version}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        {d.is_frozen ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300">
                            <Lock className="w-3 h-3" /> FROZEN
                          </span>
                        ) : (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              freezeDataset(d.dataset_id, d.version);
                            }}
                            disabled={isFreezingDataset}
                            className="px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-200 transition-colors"
                          >
                            Freeze
                          </button>
                        )}
                      </div>
                    </div>
                    <div className="mt-2 flex items-center gap-2 text-[10px] text-slate-500 font-mono">
                      <span>Splits:</span>
                      <span className="text-indigo-600 dark:text-indigo-400">DEV: {d.split_counts?.DEV || 0}</span>
                      <span>•</span>
                      <span className="text-amber-600 dark:text-amber-400">PILOT: {d.split_counts?.PILOT || 0}</span>
                      <span>•</span>
                      <span className="text-emerald-600 dark:text-emerald-400">HELD_OUT: {d.split_counts?.HELD_OUT || 0}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Card 2: Inter-Rater Agreement */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-indigo-50 dark:bg-indigo-950/70 border border-indigo-200 dark:border-indigo-800 flex items-center justify-center text-indigo-600 dark:text-indigo-400">
                <Users className="w-4 h-4" />
              </div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                2. Reviewer Agreement (Cohen's Kappa)
              </h3>
            </div>
          </div>

          <p className="text-xs text-slate-500 leading-relaxed">
            Measures inter-rater reliability between independent reviewers on blinded review packets to establish reference label validity.
          </p>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Reviewer 1 Identity
              </label>
              <input
                type="text"
                value={reviewer1}
                onChange={(e) => setReviewer1(e.target.value)}
                className="w-full px-3 py-1.5 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-800 dark:text-slate-200"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Reviewer 2 Identity
              </label>
              <input
                type="text"
                value={reviewer2}
                onChange={(e) => setReviewer2(e.target.value)}
                className="w-full px-3 py-1.5 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-800 dark:text-slate-200"
              />
            </div>
          </div>

          <div className="flex justify-end pt-1">
            <button
              onClick={() => calculateAgreement()}
              disabled={isCalculatingAgreement || !reviewer1 || !reviewer2}
              className="px-4 py-2 rounded-xl bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-950/70 dark:hover:bg-indigo-900/70 text-indigo-600 dark:text-indigo-400 text-xs font-semibold border border-indigo-200 dark:border-indigo-800 transition-colors"
            >
              {isCalculatingAgreement ? 'Calculating...' : "Compute Cohen's Kappa"}
            </button>
          </div>

          {agreementResult && (
            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-600 dark:text-slate-400">Cohen's Kappa (κ):</span>
                <span className="font-mono font-extrabold text-sm text-indigo-600 dark:text-indigo-400">
                  {agreementResult.cohens_kappa !== null ? agreementResult.cohens_kappa.toFixed(3) : 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between text-[11px] text-slate-500">
                <span>Observed Agreement (Po):</span>
                <span className="font-mono">{(agreementResult.observed_agreement_po * 100).toFixed(1)}%</span>
              </div>
              <div className="flex items-center justify-between text-[11px] text-slate-500">
                <span>Chance Agreement (Pe):</span>
                <span className="font-mono">{(agreementResult.chance_agreement_pe * 100).toFixed(1)}%</span>
              </div>
              <div className="pt-1 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between text-xs">
                <span className="text-slate-500">Interpretation:</span>
                <span className="font-bold text-slate-800 dark:text-slate-200">{agreementResult.interpretation}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Step 3: Experiment Configuration & Baseline Strategy */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 dark:bg-indigo-950/70 border border-indigo-200 dark:border-indigo-800 flex items-center justify-center text-indigo-600 dark:text-indigo-400">
              <FlaskConical className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                3. Configure Experiment & Baseline Strategy
              </h3>
              <p className="text-xs text-slate-500">
                Compare C4 policy-aware approach against baseline security strategies and reduced-evidence ablations.
              </p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 text-xs">
          {/* Strategy */}
          <div>
            <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Baseline Strategy
            </label>
            <select
              value={selectedStrategy}
              onChange={(e) => setSelectedStrategy(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs font-medium text-slate-800 dark:text-slate-200"
            >
              <option value={RESEARCH_STRATEGIES.C4_POLICY_AWARE}>C4 Policy-Aware (Proposed)</option>
              <option value={RESEARCH_STRATEGIES.MANUAL_SUITE}>Manual Security Suite</option>
              <option value={RESEARCH_STRATEGIES.GENERIC_MODEL_GENERATOR}>Generic Model Generator</option>
              <option value={RESEARCH_STRATEGIES.TEXT_ONLY_EVALUATOR}>Text-Only Evaluator</option>
            </select>
          </div>

          {/* Ablation */}
          <div>
            <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Ablation Variant
            </label>
            <select
              value={selectedAblation}
              onChange={(e) => setSelectedAblation(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs font-medium text-slate-800 dark:text-slate-200"
            >
              <option value={RESEARCH_ABLATIONS.NONE}>None (Full Evidence Package)</option>
              <option value={RESEARCH_ABLATIONS.NO_GROUNDING}>No Structured Policy Grounding</option>
              <option value={RESEARCH_ABLATIONS.NO_PROVENANCE}>No Source Authority Provenance</option>
              <option value={RESEARCH_ABLATIONS.NO_EFFECTS}>No Persistent Action/Effect Evidence</option>
            </select>
          </div>

          {/* Split */}
          <div>
            <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Dataset Partition Split
            </label>
            <select
              value={selectedSplit}
              onChange={(e) => setSelectedSplit(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs font-medium text-slate-800 dark:text-slate-200"
            >
              <option value={DATASET_SPLITS.DEV}>DEV Partition (Exploratory)</option>
              <option value={DATASET_SPLITS.PILOT}>PILOT Partition (Calibration)</option>
              <option value={DATASET_SPLITS.HELD_OUT}>HELD_OUT Partition (Strict Benchmark)</option>
            </select>
          </div>

          {/* Seed */}
          <div>
            <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
              PRNG Seed
            </label>
            <input
              type="number"
              value={seed}
              onChange={(e) => setSeed(parseInt(e.target.value, 10) || 42)}
              className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-800 dark:text-slate-200"
            />
          </div>

          {/* Trial Repeats */}
          <div>
            <label className="block font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Trial Repeats
            </label>
            <input
              type="number"
              min="1"
              max="10"
              value={repeatCount}
              onChange={(e) => setRepeatCount(Math.max(1, parseInt(e.target.value, 10) || 1))}
              className="w-full px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs font-mono text-slate-800 dark:text-slate-200"
            />
          </div>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-2">
          <div className="flex flex-col gap-0.5">
            {activeExperiment && (
              <span className="font-mono text-[11px] text-indigo-600 dark:text-indigo-400 font-semibold">
                Experiment ID: {activeExperiment.experiment_id}
              </span>
            )}
            <p className="text-[11px] text-slate-400 italic">
              Strategy names identify evaluation logic; backend executions use configured local adapters.
            </p>
          </div>
          <button
            onClick={() => runExperiment()}
            disabled={isCreatingExperiment || isExecutingExperiment || !selectedDataset}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs shadow-sm shadow-indigo-500/20 transition-all shrink-0 disabled:opacity-50"
          >
            {isCreatingExperiment || isExecutingExperiment ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Running Experiment Trials...</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                <span>Run Evaluation Experiment</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Step 4: Consolidated Metrics Dashboard across all 6 proposal categories */}
      {experimentReport && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-6 animate-in fade-in">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-200 dark:border-slate-800 pb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <span>4. Experiment Evaluation Report & Proposal Metrics</span>
                <span className="font-mono text-xs text-indigo-600 dark:text-indigo-400 font-normal">
                  ({experimentReport.experiment_id})
                </span>
              </h3>
              <p className="text-xs text-slate-500">
                Stratified metrics computed by backend evaluator across trials.
              </p>
            </div>
            <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
              Status: {experimentReport.status}
            </span>
          </div>

          {/* 6 Proposal Metric Categories */}
          <div className="space-y-6">
            {/* Category 1: Policy Extraction */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-indigo-500" />
                Category 1: Policy Extraction Quality
              </h4>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {renderMetricCard('Extraction Precision', experimentReport.aggregated_metrics?.extraction_precision)}
                {renderMetricCard('Extraction Recall', experimentReport.aggregated_metrics?.extraction_recall)}
                {renderMetricCard('Extraction F1 Score', experimentReport.aggregated_metrics?.extraction_f1)}
                {renderMetricCard('Rule-Source Provenance Acc.', experimentReport.aggregated_metrics?.provenance_accuracy)}
              </div>
            </div>

            {/* Category 2: Generated Tests */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3 flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-indigo-500" />
                Category 2: Generated Policy Tests & Coverage
              </h4>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {renderMetricCard('Case Validity Rate', experimentReport.aggregated_metrics?.case_validity_rate)}
                {renderMetricCard('Planned Coverage', experimentReport.aggregated_metrics?.planned_coverage)}
                {renderMetricCard('Observed Policy Coverage', experimentReport.aggregated_metrics?.observed_coverage)}
                {renderMetricCard('Unexercised Rules', { value: experimentReport.aggregated_metrics?.accepted_unexercised_count || 0 }, '', true)}
              </div>
            </div>

            {/* Category 3: Violation Detection */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3 flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-rose-500" />
                Category 3: Violation Detection & Reliability
              </h4>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {renderMetricCard('Detection Precision', experimentReport.aggregated_metrics?.detection_precision)}
                {renderMetricCard('Detection Recall', experimentReport.aggregated_metrics?.detection_recall)}
                {renderMetricCard('Detection F1 Score', experimentReport.aggregated_metrics?.detection_f1)}
                {renderMetricCard('False-PASS Rate', experimentReport.aggregated_metrics?.false_pass_rate)}
              </div>
            </div>

            {/* Category 4: Attacks & Exposure */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3 flex items-center gap-1.5">
                <Scale className="w-3.5 h-3.5 text-amber-500" />
                Category 4: Attacks & Exposure Verification
              </h4>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {renderMetricCard('Injection Exposure Rate', experimentReport.aggregated_metrics?.exposure_rate)}
                {renderMetricCard('Attack Success Rate', experimentReport.aggregated_metrics?.attack_success_rate)}
                {renderMetricCard('Attempt Goal Rate', experimentReport.aggregated_metrics?.attempt_goal_rate)}
                {renderMetricCard('Commit Goal Rate', experimentReport.aggregated_metrics?.commit_goal_rate)}
              </div>
            </div>

            {/* Category 5: Utility & Attribution */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3 flex items-center gap-1.5">
                <TrendingUp className="w-3.5 h-3.5 text-emerald-500" />
                Category 5: Legitimate Utility & Attribution Accuracy
              </h4>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {renderMetricCard('Benign Task Utility Rate', experimentReport.aggregated_metrics?.benign_utility_rate)}
                {renderMetricCard('False Refusal Rate', experimentReport.aggregated_metrics?.false_refusal_rate)}
                {renderMetricCard('Rule Attribution Accuracy', experimentReport.aggregated_metrics?.rule_attribution_accuracy)}
                {renderMetricCard('Source Attribution Accuracy', experimentReport.aggregated_metrics?.source_attribution_accuracy)}
              </div>
            </div>

            {/* Category 6: Policy Regression Adaptation */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-indigo-500" />
                Category 6: Policy-Change Regression & Overhead
              </h4>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {renderMetricCard('Affected ID Precision', experimentReport.aggregated_metrics?.affected_identification_precision)}
                {renderMetricCard('Affected ID Recall', experimentReport.aggregated_metrics?.affected_identification_recall)}
                {renderMetricCard('Adaptation Success Rate', experimentReport.aggregated_metrics?.adaptation_success_rate)}
                {renderMetricCard('Average Latency (ms)', { value: experimentReport.aggregated_metrics?.average_latency_ms || 0 }, 'ms', true)}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
