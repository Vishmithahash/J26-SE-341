import React, { useState } from 'react';
import {
  CheckCircle,
  AlertTriangle,
  Play,
  RotateCw,
  ShieldCheck,
  Code,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  Clock,
} from 'lucide-react';
import { C3Badge } from './C3Badge.jsx';

export const C3ValidationPanel = ({
  candidateCase,
  adapterManifest,
  taskFixtureMetadata,
  recoveryContract,
  onValidate,
  isValidating,
  validationResult,
  validationError,
}) => {
  const [showRaw, setShowRaw] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    const payload = {
      candidate_case: candidateCase,
      adapter_manifest: adapterManifest,
      task_fixture_metadata: taskFixtureMetadata,
      recovery_contract: recoveryContract,
    };
    onValidate(payload);
  };

  const status = validationResult?.validation_status;
  const isStaticValid = status === 'STATIC_VALID';

  return (
    <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-5">
      {/* Header & Submit action */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <span>Deterministic Static Validation</span>
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Deterministic static verification of candidate fault case metadata against adapter capabilities and contracts.
          </p>
        </div>

        <button
          type="button"
          onClick={handleSubmit}
          disabled={isValidating}
          className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white shadow-xs transition-colors shrink-0"
        >
          {isValidating ? (
            <>
              <RotateCw className="w-3.5 h-3.5 animate-spin" />
              <span>Validating Metadata...</span>
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5" />
              <span>Validate Candidate Case</span>
            </>
          )}
        </button>
      </div>

      {/* Error Notice */}
      {validationError && (
        <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-700 dark:text-rose-300 flex items-start gap-2.5">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-semibold">Validation Request Failed</span>
            <p>{validationError}</p>
          </div>
        </div>
      )}

      {/* Result Display */}
      {validationResult && (
        <div className="space-y-4 pt-2">
          {/* Status Banner */}
          <div
            className={`p-4 rounded-xl border flex flex-col md:flex-row md:items-center justify-between gap-3 ${
              isStaticValid
                ? 'bg-emerald-50/70 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-800'
                : 'bg-amber-50/70 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800'
            }`}
          >
            <div className="flex items-start gap-3">
              {isStaticValid ? (
                <CheckCircle className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
              )}
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold text-slate-900 dark:text-white">
                    {isStaticValid ? 'STATIC_VALID' : 'TEST_NOT_READY'}
                  </span>
                  <C3Badge status={status} />
                  <C3Badge status="STATIC_ONLY" label="Scope: STATIC_ONLY" />
                </div>
                <p className="text-xs text-slate-600 dark:text-slate-300 mt-1 leading-relaxed">
                  {isStaticValid
                    ? 'Candidate case declared metadata is fully consistent with declared adapter capabilities, fixture metadata, and recovery contract.'
                    : 'Candidate case metadata is incompatible with declared capabilities or violates static contract constraints.'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 self-start md:self-center text-[11px] font-mono text-slate-500 shrink-0">
              <span>endpoint: /api/v1/c3/cases/validate</span>
            </div>
          </div>

          {/* Critical Distinction Notice: STATIC_VALID != Execution Readiness */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 text-xs space-y-2">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <span className="font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                <span>Runtime Readiness Boundary & Limitations</span>
              </span>
              <div className="flex items-center gap-1.5">
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-rose-100 dark:bg-rose-900/40 text-rose-700 dark:text-rose-300">
                  runtime_verified: false
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-rose-100 dark:bg-rose-900/40 text-rose-700 dark:text-rose-300">
                  execution_ready: false
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300">
                  recovery_verdict: null
                </span>
              </div>
            </div>
            <p className="text-slate-600 dark:text-slate-400 leading-relaxed text-[11px]">
              Static validation confirms structural and type compatibility only. It does <strong>not</strong> verify network reachability, live application-under-test reachability, or injector installation. Recovery scoring is strictly deferred to trial execution evidence.
            </p>
          </div>

          {/* Pending Checks (if STATIC_VALID) */}
          {validationResult.pending_checks && validationResult.pending_checks.length > 0 && (
            <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs space-y-2">
              <span className="font-semibold text-slate-700 dark:text-slate-300">
                Pending Runtime Verification Checks ({validationResult.pending_checks.length}):
              </span>
              <ul className="space-y-1.5 pl-1">
                {validationResult.pending_checks.map((chk, i) => (
                  <li key={i} className="flex items-center gap-2 text-slate-600 dark:text-slate-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
                    <span>{chk}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Validation Reasons (if TEST_NOT_READY) */}
          {validationResult.reasons && validationResult.reasons.length > 0 && (
            <div className="p-4 rounded-xl bg-amber-50/50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/60 text-xs space-y-2">
              <span className="font-semibold text-amber-900 dark:text-amber-200">
                Validation Reason Codes ({validationResult.reasons.length}):
              </span>
              <div className="space-y-2">
                {validationResult.reasons.map((r, i) => (
                  <div key={i} className="p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-800">
                    <div className="flex items-center gap-2">
                      <code className="font-mono font-bold text-amber-700 dark:text-amber-400 text-[11px]">
                        {r.code}
                      </code>
                      {r.field_path && (
                        <span className="text-[10px] font-mono text-slate-400 bg-slate-100 dark:bg-slate-800 px-1 py-0.5 rounded">
                          {r.field_path}
                        </span>
                      )}
                    </div>
                    <p className="text-slate-700 dark:text-slate-300 mt-1">{r.message}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Raw JSON Debug Accordion */}
          <div>
            <button
              type="button"
              onClick={() => setShowRaw(!showRaw)}
              className="text-xs text-slate-500 hover:text-slate-900 dark:hover:text-white flex items-center gap-1"
            >
              <Code className="w-3.5 h-3.5" />
              <span>{showRaw ? 'Hide Raw API Response' : 'Inspect Raw API Response'}</span>
              {showRaw ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
            {showRaw && (
              <pre className="mt-2 p-3 rounded-xl bg-slate-950 text-slate-100 text-[11px] font-mono overflow-x-auto max-h-60">
                {JSON.stringify(validationResult, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
