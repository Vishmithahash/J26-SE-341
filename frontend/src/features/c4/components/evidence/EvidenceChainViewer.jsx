/**
 * Component 4 (C4) - Evidence Chain Viewer
 * Explicitly displays the full causal observation chain:
 * [1. Instruction Source & Trust Classification]
 *   → [2. Applicable Policy Rule & Grounded Excerpt]
 *   → [3. Observed Action Attempt & Application Decision]
 *   → [4. Committed Effect or Protected Disclosure]
 * Separately exposes missing evidence, trace truncations, and observation limitations.
 */

import React from 'react';
import {
  FileText,
  AlertTriangle,
  Layers,
} from 'lucide-react';
import { TRUST_CLASSIFICATIONS } from '../../api/types.js';

export function EvidenceChainViewer({ finding, runRecord = null }) {
  if (!finding && !runRecord) {
    return (
      <div className="p-8 text-center text-xs text-slate-400">
        No evidence chain available.
      </div>
    );
  }

  const ruleRef = finding?.source_policy_reference;
  const violationStage = finding?.violation_stage;
  const missingEvidence = finding?.missing_evidence || [];
  const observedEffect = finding?.observed_effect;
  const explanation = finding?.explanation;

  // Step 1 comes from the instruction sources recorded in the run's evidence (live runs). Untrusted
  // content is shown first because it is what an injection finding is about. Runs without recorded
  // sources fall back to the rule-ID heuristic.
  const recordedSources = runRecord?.evaluation_report_summary?.evidence?.instruction_sources || [];
  const shownSource =
    recordedSources.find((src) => src.trust_classification === 'UNTRUSTED_CONTENT') || recordedSources[0];
  const isUntrustedIndirect = finding?.rule_id?.includes('INDIRECT');
  const source = shownSource
    ? {
        label: shownSource.source_id,
        trust: shownSource.trust_classification,
        untrusted: shownSource.trust_classification === 'UNTRUSTED_CONTENT',
        detail: shownSource.source_type,
      }
    : {
        label: isUntrustedIndirect ? 'untrusted_document_source' : 'user_task_prompt',
        trust: isUntrustedIndirect
          ? TRUST_CLASSIFICATIONS.UNTRUSTED_INDIRECT_CONTENT
          : TRUST_CLASSIFICATIONS.TRUSTED_GOVERNANCE,
        untrusted: isUntrustedIndirect,
        detail: null,
      };
  // Backend SourceReference fields are supporting_excerpt / start_char / end_char.
  const excerpt = ruleRef?.supporting_excerpt ?? ruleRef?.excerpt;
  const offsetStart = ruleRef?.start_char ?? ruleRef?.char_offset_start;
  const offsetEnd = ruleRef?.end_char ?? ruleRef?.char_offset_end;

  return (
    <div className="space-y-6">
      {/* Evidence Chain Flow Header */}
      <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3 flex items-center gap-1.5">
          <Layers className="w-4 h-4 text-indigo-500" />
          Evidence-Linked Causal Observation Chain
        </h4>

        {/* 4-Step Chain Visualization */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          {/* Step 1: Instruction Source */}
          <div className="p-3 rounded-lg bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-1.5">
            <div className="flex items-center justify-between text-[11px] font-bold text-slate-500">
              <span>1. Instruction Source</span>
              <span className="w-2 h-2 rounded-full bg-indigo-500" />
            </div>
            <p className="text-xs font-semibold text-slate-900 dark:text-slate-100 font-mono break-all">
              {source.label}
            </p>
            <div className="flex items-center gap-1">
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  source.untrusted
                    ? 'bg-rose-100 text-rose-800 dark:bg-rose-950/70 dark:text-rose-300'
                    : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300'
                }`}
              >
                {source.trust}
              </span>
            </div>
            <span className="text-[10px] text-slate-400 block">
              Origin: {runRecord?.execution_mode || 'SIMULATED_TEST_RUN'}
              {source.detail ? ` • ${source.detail}` : ''}
              {recordedSources.length > 1 ? ` • ${recordedSources.length} recorded sources` : ''}
            </span>
          </div>

          {/* Step 2: Applicable Rule */}
          <div className="p-3 rounded-lg bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-1.5">
            <div className="flex items-center justify-between text-[11px] font-bold text-slate-500">
              <span>2. Applicable Policy</span>
              <span className="w-2 h-2 rounded-full bg-indigo-500" />
            </div>
            <p className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 font-mono">
              {finding?.rule_id || 'RULE_UNDEFINED'} (v{finding?.rule_version || 1})
            </p>
            <p className="text-[11px] text-slate-600 dark:text-slate-300">
              Contract: {finding?.contract_id || 'default'} v{finding?.contract_version || 1}
            </p>
            <span className="text-[10px] text-slate-400 block">
              Severity: {finding?.severity || 'HIGH'}
            </span>
          </div>

          {/* Step 3: Agent Action & Decision */}
          <div className="p-3 rounded-lg bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-1.5">
            <div className="flex items-center justify-between text-[11px] font-bold text-slate-500">
              <span>3. Observed Action</span>
              <span className="w-2 h-2 rounded-full bg-indigo-500" />
            </div>
            <p className="text-xs font-semibold text-slate-800 dark:text-slate-200 font-mono">
              {violationStage || 'INVOCATION_EVALUATED'}
            </p>
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded font-medium inline-block ${
                finding?.verdict === 'FAIL'
                  ? 'bg-rose-100 text-rose-800 dark:bg-rose-950/70 dark:text-rose-300'
                  : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300'
              }`}
            >
              Verdict: {finding?.verdict || 'NOT_EXERCISED'}
            </span>
          </div>

          {/* Step 4: Committed Effect / Disclosure */}
          <div className="p-3 rounded-lg bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-1.5">
            <div className="flex items-center justify-between text-[11px] font-bold text-slate-500">
              <span>4. Effect / Outcome</span>
              <span className="w-2 h-2 rounded-full bg-indigo-500" />
            </div>
            <p className="text-xs font-medium text-slate-700 dark:text-slate-300">
              {observedEffect || 'No committed effect observed'}
            </p>
            <span className="text-[10px] text-slate-400 block font-mono">
              Attacker: {finding?.attack_outcome || 'NOT_APPLICABLE'}
            </span>
          </div>
        </div>
      </div>

      {/* Human-Readable Explanation */}
      {explanation && (
        <div className="p-4 rounded-xl bg-indigo-50/60 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-800 text-xs">
          <span className="font-bold text-indigo-900 dark:text-indigo-200 block mb-1">
            Evaluator Grounded Finding Explanation:
          </span>
          <p className="text-indigo-800 dark:text-indigo-300 leading-relaxed font-mono whitespace-pre-wrap select-text">
            {explanation}
          </p>
        </div>
      )}

      {/* Grounding Source Policy Excerpt */}
      {ruleRef && (
        <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-2">
          <div className="flex items-center justify-between text-xs font-bold text-slate-700 dark:text-slate-300">
            <span className="flex items-center gap-1.5">
              <FileText className="w-4 h-4 text-indigo-500" />
              Source Policy Excerpt & Coordinates
            </span>
            <span className="font-mono text-slate-400 text-[11px]">
              {ruleRef.artifact_id} (v{ruleRef.artifact_version})
            </span>
          </div>
          <div className="p-3 rounded-lg bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs text-slate-700 dark:text-slate-300 font-serif leading-relaxed whitespace-pre-wrap select-text">
            "{excerpt}"
          </div>
          {offsetStart !== undefined && offsetStart !== null && (
            <span className="text-[10px] text-slate-400 block font-mono">
              Offset: chars [{offsetStart}:{offsetEnd}]
            </span>
          )}
        </div>
      )}

      {/* Observation Limitations & Missing Evidence */}
      {missingEvidence && missingEvidence.length > 0 && (
        <div className="p-4 rounded-xl bg-amber-50/60 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 flex items-start gap-3 text-xs">
          <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-bold text-amber-900 dark:text-amber-200">
              Observation Limitations & Missing Evidence:
            </span>
            <p className="text-amber-800 dark:text-amber-300 text-[11px]">
              The policy evaluator identified the following evidence gaps during evaluation. Conclusions do not claim causal influence beyond what the retained trace supports:
            </p>
            <ul className="list-disc list-inside space-y-0.5 text-amber-900 dark:text-amber-200 font-mono text-[11px] mt-1">
              {missingEvidence.map((gap, i) => (
                <li key={i}>{gap}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
