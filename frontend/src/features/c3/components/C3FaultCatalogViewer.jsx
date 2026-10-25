import React, { useState } from 'react';
import {
  Clock,
  ServerCrash,
  Gauge,
  WifiOff,
  FileWarning,
  AlertCircle,
  Layers,
  Info,
} from 'lucide-react';
import { useC3Catalog } from '../hooks/useC3Catalog.js';
import { C3Badge } from './C3Badge.jsx';

const FAMILY_ICONS = {
  TIMEOUT_DISCONNECTION: Clock,
  TRANSIENT_5XX: ServerCrash,
  RATE_LIMIT_429: Gauge,
  TOOL_UNAVAILABILITY: WifiOff,
  MALFORMED_RESPONSE: FileWarning,
};

export const C3FaultCatalogViewer = () => {
  const { catalog, isLoading, error } = useC3Catalog();
  const [selectedFamily, setSelectedFamily] = useState(null);

  const families = catalog?.families || [];

  return (
    <div className="space-y-6">
      {/* Header & Concept Notice */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Layers className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <span>Authoritative Fault Families Catalogue</span>
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Operational fault catalogue defining failure semantics, effect phases, and supported modes.
          </p>
          {catalog?.note && (
            <p className="text-xs text-slate-600 dark:text-slate-300 mt-1 max-w-3xl">{catalog.note}</p>
          )}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-slate-500 dark:text-slate-400">
            Catalogue Version: <code className="font-mono font-semibold">{catalog?.schema_version || '1.0.0'}</code>
          </span>
          <C3Badge status="CATALOGUE" label="Fault Catalogue" />
        </div>
      </div>

      {/* Crucial Concept Callout: Duplicate effects are NOT a fault family */}
      <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs">
        <div className="flex items-start gap-2.5">
          <Info className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-bold text-slate-900 dark:text-white">
              Core Architectural Distinction: Duplicate Effects vs. Injected Faults
            </span>
            <p className="text-slate-600 dark:text-slate-300 leading-relaxed">
              <strong>Duplicate side effects are NOT an operational fault family.</strong> Duplicate actions (such as placing redundant orders or issuing double charges) represent a <em>recovery defect</em> evaluated under recovery contract rule <code className="font-mono bg-slate-200 dark:bg-slate-800 px-1 py-0.5 rounded">RULE_DUPLICATE_EFFECTS</code>. In contrast, the five fault families below represent genuine transport and service-level faults.
            </p>
          </div>
        </div>
      </div>

      {/* Catalog Cards Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 animate-pulse h-48" />
          ))}
        </div>
      ) : error ? (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-700 dark:text-rose-300 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>Error loading fault catalogue: {error}</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {families.map((fam) => {
            const Icon = FAMILY_ICONS[fam.family] || Layers;
            const isSelected = selectedFamily === fam.family;

            return (
              <div
                key={fam.family}
                onClick={() => setSelectedFamily(isSelected ? null : fam.family)}
                className={`p-5 rounded-2xl bg-white dark:bg-slate-900 border transition-all cursor-pointer flex flex-col justify-between ${
                  isSelected
                    ? 'border-indigo-500 ring-2 ring-indigo-500/20 shadow-md'
                    : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 shadow-sm'
                }`}
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div className="p-2.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 shrink-0">
                      <Icon className="w-5 h-5" />
                    </div>
                    <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                      {fam.family}
                    </span>
                  </div>

                  <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                    {fam.name}
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 line-clamp-3 leading-relaxed">
                    {fam.description}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 space-y-2 text-xs">
                  <div>
                    <span className="text-[11px] font-semibold text-slate-400 block mb-1">
                      Supported Modes ({fam.supported_modes?.length || 0}):
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {fam.supported_modes?.map((mode) => (
                        <span
                          key={mode}
                          className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300"
                        >
                          {mode}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div>
                    <span className="text-[11px] font-semibold text-slate-400 block mb-1">
                      Effect Phases:
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {fam.effect_phases?.map((phase) => (
                        <span
                          key={phase}
                          className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold ${
                            phase === 'AFTER_COMMIT'
                              ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300'
                              : phase === 'BEFORE_EFFECT'
                              ? 'bg-teal-100 dark:bg-teal-900/40 text-teal-800 dark:text-teal-300'
                              : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
                          }`}
                        >
                          {phase}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="pt-2 text-[11px] text-slate-400 space-y-1">
                    <div className="flex items-center justify-between">
                      <span>Runtime Injection:</span>
                      <span className={`font-semibold ${
                        fam.injection_implemented === true
                          ? 'text-emerald-600 dark:text-emerald-400'
                          : fam.injection_implemented === false
                          ? 'text-amber-600 dark:text-amber-400'
                          : 'text-slate-500 dark:text-slate-400'
                      }`}>
                        {fam.injection_implemented === true
                          ? 'Implemented'
                          : fam.injection_implemented === false
                          ? 'Not implemented'
                          : 'Not checked'}
                      </span>
                    </div>
                    {fam.runtime_support?.length > 0 && (
                      <ul className="list-disc list-inside space-y-0.5 text-slate-500 dark:text-slate-400">
                        {fam.runtime_support.map((s) => (
                          <li key={s}>{s}</li>
                        ))}
                      </ul>
                    )}
                    {fam.note && <p className="text-slate-500 dark:text-slate-400">{fam.note}</p>}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Effect Phase Reference Guide */}
      <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          Effect Phases Semantic Reference
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
          <div className="p-3 rounded-xl bg-teal-50/60 dark:bg-teal-950/20 border border-teal-200/60 dark:border-teal-900/40">
            <div className="font-bold text-teal-800 dark:text-teal-300 font-mono text-[11px]">BEFORE_EFFECT</div>
            <p className="text-slate-600 dark:text-slate-400 mt-1 text-[11px] leading-relaxed">
              Fault is injected prior to tool execution. Domain side-effect is prevented from forwarding to target.
            </p>
          </div>
          <div className="p-3 rounded-xl bg-amber-50/60 dark:bg-amber-950/20 border border-amber-200/60 dark:border-amber-900/40">
            <div className="font-bold text-amber-800 dark:text-amber-300 font-mono text-[11px]">AFTER_COMMIT</div>
            <p className="text-slate-600 dark:text-slate-400 mt-1 text-[11px] leading-relaxed">
              Domain operation commits on target, but reply is lost at network boundary. Tests idempotent retry vs duplicate defect.
            </p>
          </div>
          <div className="p-3 rounded-xl bg-indigo-50/60 dark:bg-indigo-950/20 border border-indigo-200/60 dark:border-indigo-900/40">
            <div className="font-bold text-indigo-800 dark:text-indigo-300 font-mono text-[11px]">PARTIAL_EFFECT</div>
            <p className="text-slate-600 dark:text-slate-400 mt-1 text-[11px] leading-relaxed">
              Fault is injected mid-batch where target capabilities support multi-step transaction observation.
            </p>
          </div>
          <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700">
            <div className="font-bold text-slate-700 dark:text-slate-300 font-mono text-[11px]">NOT_APPLICABLE</div>
            <p className="text-slate-600 dark:text-slate-400 mt-1 text-[11px] leading-relaxed">
              Applied for read-only tools or query operations where side-effect phase distinction does not alter target state.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
