import React, { useState } from 'react';
import {
  Sparkles,
  Layers,
  Terminal,
  Copy,
  Check,
  Info,
  GitBranch,
  Split,
} from 'lucide-react';
import { DEMO_RESEARCH_PROTOCOL } from '../fixtures';

export const C3ResearchView = () => {
  const [copiedCmd, setCopiedCmd] = useState(null);

  const handleCopy = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedCmd(id);
    setTimeout(() => setCopiedCmd(null), 2000);
  };

  const proto = DEMO_RESEARCH_PROTOCOL;

  return (
    <div className="space-y-6">
      {/* Header & Architectural Transparency Notice */}
      <div className="p-6 rounded-2xl bg-slate-900 text-white border border-slate-800 space-y-3">
        <div className="inline-flex items-center gap-2 px-2.5 py-0.5 rounded-md bg-purple-500/20 text-purple-300 border border-purple-500/30 text-[11px] font-semibold uppercase tracking-wider">
          <Sparkles className="w-3.5 h-3.5" />
          Research Protocol & Ablation Governance
        </div>
        <h2 className="text-xl font-bold tracking-tight">
          Planned 3-Way Protocol, Canonical Baselines & Ablations
        </h2>
        <p className="text-xs text-slate-300 leading-relaxed max-w-3xl">
          Component 3 enforces research rigor through a planned 40/20/40 family-partitioned split, comparative evaluation baselines (B1 fixed suite, B2 outcome-only, Full C3 proposed method, and matched clean control), and method ablations (A1–A4). Research experiments and evaluations are executed strictly via developer CLI entry points without fabricated browser executions.
        </p>

        {/* CLI Architecture Badge */}
        <div className="p-3 rounded-xl bg-purple-950/50 border border-purple-800 text-purple-200 text-xs flex items-start gap-2.5">
          <Info className="w-4 h-4 text-purple-400 shrink-0 mt-0.5" />
          <div className="leading-relaxed">
            <span className="font-bold">Developer CLI Architecture:</span> Real recovery evaluation and runner pipelines operate as offline command-line entry points (<code className="font-mono text-purple-300">runtime.evaluate</code>, <code className="font-mono text-purple-300">runtime.suite_runner</code>, <code className="font-mono text-purple-300">runtime.runner</code>). Shell commands are never executed from the browser, and no pseudo-endpoints or fabricated reviewer labels are created client-side.
          </div>
        </div>
      </div>

      {/* Partitions / Splits (40/20/40) */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-4">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <Split className="w-4 h-4 text-indigo-600" />
              <span>Planned Family-Partitioned Dataset Splits (40 / 20 / 40)</span>
            </h3>
            <p className="text-[11px] text-amber-600 dark:text-amber-400 mt-0.5">
              Labeled as planned split pending frozen dataset manifest confirmation.
            </p>
          </div>
          <span className="text-xs font-mono text-slate-400">
            Protocol: {proto.protocol_id} (v{proto.protocol_version})
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          {proto.partitions.map((part) => (
            <div
              key={part.name}
              className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-900 dark:text-white uppercase font-mono">
                  {part.name.replace(/_/g, ' ')}
                </span>
                <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-indigo-100 dark:bg-indigo-900/60 text-indigo-700 dark:text-indigo-300">
                  {part.percentage}%
                </span>
              </div>
              <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                {part.description}
              </p>
              <span className="text-[10px] text-slate-400 block pt-1 border-t border-slate-200 dark:border-slate-700">
                Partitioning Unit: Case Family ID (<code className="font-mono">case_family_id</code>)
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Comparative Baselines & Ablation Models */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Baselines */}
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-4">
          <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Layers className="w-4 h-4 text-emerald-600" />
            <span>Comparative Evaluation Baselines</span>
          </h3>
          <div className="space-y-3 text-xs">
            {proto.baselines.map((b) => (
              <div
                key={b.baseline_id}
                className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/30 border border-slate-200 dark:border-slate-800 flex items-start gap-3"
              >
                <span className="px-2 py-1 rounded-md bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 font-bold font-mono text-xs shrink-0">
                  {b.baseline_id}
                </span>
                <div className="space-y-0.5">
                  <div className="font-bold text-slate-900 dark:text-white">{b.name}</div>
                  <p className="text-slate-600 dark:text-slate-400 leading-relaxed text-[11px]">
                    {b.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Ablations */}
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-4">
          <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <GitBranch className="w-4 h-4 text-amber-600" />
            <span>Methodological Ablation Models (A1 – A4)</span>
          </h3>
          <div className="space-y-3 text-xs">
            {proto.ablations.map((a) => (
              <div
                key={a.ablation_id}
                className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/30 border border-slate-200 dark:border-slate-800 flex items-start gap-3"
              >
                <span className="px-2 py-1 rounded-md bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 font-bold font-mono text-xs shrink-0">
                  {a.ablation_id}
                </span>
                <div className="space-y-0.5">
                  <div className="font-bold text-slate-900 dark:text-white">{a.name}</div>
                  <p className="text-slate-600 dark:text-slate-400 leading-relaxed text-[11px]">
                    {a.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Developer CLI Terminal Commands */}
      <div className="p-6 rounded-2xl bg-slate-950 text-slate-200 border border-slate-800 shadow-xs space-y-4">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Terminal className="w-4 h-4 text-emerald-400" />
            <span>Developer CLI Commands (Advanced Documentation)</span>
          </h3>
          <p className="text-xs text-slate-400 leading-relaxed mt-1">
            Execute real runtime and evaluation pipelines directly from a Python terminal environment. Shell commands are never executed in the browser; unsupported arguments (<code className="font-mono text-slate-300">--split</code>, <code className="font-mono text-slate-300">--domain</code>) are omitted.
          </p>
        </div>

        <div className="space-y-3 text-xs font-mono">
          {/* Command 1: evaluate */}
          <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between gap-3">
            <div className="truncate">
              <span className="text-slate-500">$ </span>
              <span className="text-emerald-400">
                python -m app.components.c3_robustness_recovery.runtime.evaluate --evidence-file evidence.json --export-dir evidence_output
              </span>
            </div>
            <button
              type="button"
              onClick={() =>
                handleCopy(
                  'python -m app.components.c3_robustness_recovery.runtime.evaluate --evidence-file evidence.json --export-dir evidence_output',
                  'cmd1'
                )
              }
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors shrink-0"
              title="Copy command"
            >
              {copiedCmd === 'cmd1' ? (
                <Check className="w-3.5 h-3.5 text-emerald-400" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>
          </div>

          {/* Command 2: suite_runner */}
          <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between gap-3">
            <div className="truncate">
              <span className="text-slate-500">$ </span>
              <span className="text-emerald-400">
                python -m app.components.c3_robustness_recovery.runtime.suite_runner --synthetic --export-dir evidence_output
              </span>
            </div>
            <button
              type="button"
              onClick={() =>
                handleCopy(
                  'python -m app.components.c3_robustness_recovery.runtime.suite_runner --synthetic --export-dir evidence_output',
                  'cmd2'
                )
              }
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors shrink-0"
              title="Copy command"
            >
              {copiedCmd === 'cmd2' ? (
                <Check className="w-3.5 h-3.5 text-emerald-400" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>
          </div>

          {/* Command 3: runner */}
          <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between gap-3">
            <div className="truncate">
              <span className="text-slate-500">$ </span>
              <span className="text-emerald-400">
                python -m app.components.c3_robustness_recovery.runtime.runner --synthetic --export-dir evidence_output
              </span>
            </div>
            <button
              type="button"
              onClick={() =>
                handleCopy(
                  'python -m app.components.c3_robustness_recovery.runtime.runner --synthetic --export-dir evidence_output',
                  'cmd3'
                )
              }
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors shrink-0"
              title="Copy command"
            >
              {copiedCmd === 'cmd3' ? (
                <Check className="w-3.5 h-3.5 text-emerald-400" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

