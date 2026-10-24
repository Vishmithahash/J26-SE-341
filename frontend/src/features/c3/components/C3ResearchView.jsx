import React from 'react';
import {
  Sparkles,
  Layers,
  Info,
  GitBranch,
  Split,
} from 'lucide-react';
import { DEMO_RESEARCH_PROTOCOL } from '../fixtures';

export const C3ResearchView = () => {
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
          Component 3 enforces research rigor through a planned 40/20/40 family-partitioned split, comparative evaluation baselines (B1 fixed suite, B2 outcome-only, Full C3 proposed method, and matched clean control), and method ablations (A1–A4). Research evaluation findings are stored and reviewed through verified evidence records.
        </p>

        {/* Governance Notice */}
        <div className="p-3 rounded-xl bg-purple-950/50 border border-purple-800 text-purple-200 text-xs flex items-start gap-2.5">
          <Info className="w-4 h-4 text-purple-400 shrink-0 mt-0.5" />
          <div className="leading-relaxed">
            <span className="font-bold">Evaluation Governance:</span> Recovery evaluations and research metrics reflect verified test evidence. Live execution is not connected in this standalone view; evaluations are imported from verified runs or coordinated through shared integration execution services.
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

      {/* Research Protocol Governance Summary */}
      <div className="p-6 rounded-2xl bg-slate-950 text-slate-200 border border-slate-800 shadow-xs space-y-2">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-purple-400" />
          <span>Research Protocol Governance</span>
        </h3>
        <p className="text-xs text-slate-400 leading-relaxed">
          Experimental splits, comparative baselines, and ablation models evaluate robustness across isolated fault families. All reported metrics derive from stored execution evidence and verified test records.
        </p>
      </div>
    </div>
  );
};

