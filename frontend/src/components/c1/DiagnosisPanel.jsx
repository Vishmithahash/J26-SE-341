import React, { useState, useEffect } from 'react';
import {
  FileSearch,
  CheckCircle,
  XCircle,
  AlertTriangle,
  HelpCircle,
  Code2,
  FileCode,
  ShieldAlert,
  Sparkles,
  ArrowRight,
  ExternalLink,
  Layers,
  Wrench,
  Clock,
  Info,
} from 'lucide-react';
import {
  c1Api,
  escapeText,
  CAUSE_CATEGORIES,
  DIAGNOSIS_STATUS,
  SOURCE_RELATIONSHIP_STATUS,
  EVIDENCE_AVAILABILITY,
} from './c1Api';

export const DiagnosisPanel = ({
  projectId,
  runId,
  caseId,
  caseVerdict,
  existingDiagnosis,
  onRequestCorrection,
  correctionEnabled = true,
}) => {
  const [diagnosis, setDiagnosis] = useState(existingDiagnosis || null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [codeLocations, setCodeLocations] = useState([]);
  const [isLoadingLocations, setIsLoadingLocations] = useState(false);
  const [useModelAssisted, setUseModelAssisted] = useState(false);

  // Load existing diagnosis for this case if not passed in
  useEffect(() => {
    let isCancelled = false;
    if (existingDiagnosis) {
      setDiagnosis(existingDiagnosis);
      setCodeLocations(existingDiagnosis.candidate_code_locations || []);
      return;
    }

    if (!projectId || !runId || !caseId) {
      setDiagnosis(null);
      return;
    }

    const fetchCaseDiag = async () => {
      try {
        const diag = await c1Api.getCaseDiagnosis(projectId, runId, caseId);
        if (!isCancelled && diag) {
          setDiagnosis(diag);
          setCodeLocations(diag.candidate_code_locations || []);
        }
      } catch {
        // Diagnosis not yet generated for this case
        if (!isCancelled) {
          setDiagnosis(null);
          setCodeLocations([]);
        }
      }
    };

    fetchCaseDiag();

    return () => {
      isCancelled = true;
    };
  }, [projectId, runId, caseId, existingDiagnosis]);

  // Request diagnosis from backend
  const handleRunDiagnosis = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const records = await c1Api.diagnoseRun(projectId, runId, {
        case_id: caseId,
        use_model_assisted: useModelAssisted,
        idempotency_key: `diag_${caseId}_${Date.now()}`,
      });

      if (records && records.length > 0) {
        const matching = records.find((r) => r.case_id === caseId) || records[0];
        setDiagnosis(matching);
        setCodeLocations(matching.candidate_code_locations || []);
      }
    } catch (err) {
      setErrorMsg(err.message || 'Diagnosis generation failed.');
    } finally {
      setIsLoading(false);
    }
  };

  const isEligibleForCorrection =
    diagnosis?.cause_category === CAUSE_CATEGORIES.SUPPORTED_APPLICATION_CODE_DEFECT &&
    codeLocations.length > 0;

  return (
    <div className="space-y-4 p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
      <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <FileSearch className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-white">
            Root Cause Diagnosis &amp; Source Attribution
          </h4>
        </div>

        {diagnosis && (
          <span
            className={`px-2 py-0.5 text-[10px] font-bold rounded-full ${
              diagnosis.cause_category === CAUSE_CATEGORIES.SUPPORTED_APPLICATION_CODE_DEFECT
                ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-400'
                : diagnosis.cause_category === CAUSE_CATEGORIES.AGENT_BEHAVIOUR
                ? 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-400'
                : 'bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-400'
            }`}
          >
            {diagnosis.cause_category}
          </span>
        )}
      </div>

      {errorMsg && (
        <div className="p-3 text-xs rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-300">
          {errorMsg}
        </div>
      )}

      {!diagnosis ? (
        <div className="p-6 text-center rounded-lg border border-dashed border-slate-200 dark:border-slate-800 text-xs space-y-3">
          <p className="text-slate-500 dark:text-slate-400 max-w-md mx-auto">
            No root cause diagnosis generated for case <strong>{caseId}</strong>. Request deterministic AST analysis to identify whether failure was caused by application code, agent behavior, or expectation misconfiguration.
          </p>

          <div className="flex items-center justify-center gap-3">
            <label className="inline-flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-400 cursor-pointer">
              <input
                type="checkbox"
                checked={useModelAssisted}
                onChange={(e) => setUseModelAssisted(e.target.checked)}
                className="rounded text-indigo-600 focus:ring-indigo-500"
              />
              <span>Model-Assisted Presentation</span>
            </label>

            <button
              type="button"
              onClick={handleRunDiagnosis}
              disabled={isLoading}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm disabled:opacity-50"
            >
              <Sparkles className="w-3.5 h-3.5" />
              {isLoading ? 'Diagnosing...' : 'Generate Failure Diagnosis'}
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-4 text-xs">
          {/* Explanation Summary */}
          <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 space-y-1">
            <span className="text-[11px] font-semibold text-slate-500 block">Explanation Summary:</span>
            <p className="text-slate-800 dark:text-slate-200 font-medium">
              {diagnosis.explanation_summary}
            </p>
            <div className="text-[10px] text-slate-400 pt-1 flex items-center justify-between">
              <span>Engine: {diagnosis.explanation_version} ({diagnosis.explanation_method})</span>
              <span>Req Version: {diagnosis.requirement_version}</span>
            </div>
            {/* Regenerate, e.g. to compare the deterministic and model-assisted presentations */}
            <div className="pt-2 flex items-center justify-end gap-3">
              <label className="inline-flex items-center gap-1.5 text-[11px] text-slate-600 dark:text-slate-400 cursor-pointer">
                <input
                  type="checkbox"
                  checked={useModelAssisted}
                  onChange={(e) => setUseModelAssisted(e.target.checked)}
                  className="rounded text-indigo-600 focus:ring-indigo-500"
                />
                <span>Model-Assisted Presentation</span>
              </label>
              <button
                type="button"
                onClick={handleRunDiagnosis}
                disabled={isLoading}
                className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold rounded-md border border-indigo-300 dark:border-indigo-700 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 disabled:opacity-50"
              >
                <Sparkles className="w-3 h-3" />
                {isLoading ? 'Diagnosing...' : 'Regenerate Diagnosis'}
              </button>
            </div>
          </div>

          {/* Detailed Check Explanations */}
          {diagnosis.check_explanations && diagnosis.check_explanations.length > 0 && (
            <div className="space-y-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
                Evidence-Backed Check Breakdown
              </span>

              <div className="space-y-2">
                {diagnosis.check_explanations.map((exp, idx) => (
                  <div
                    key={exp.check_id || idx}
                    className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-semibold text-slate-900 dark:text-white">
                        Check: {exp.check_id} {exp.tool_name && `(${exp.tool_name})`}
                      </span>
                      <div className="flex items-center gap-1.5">
                        <span className="px-1.5 py-0.5 text-[10px] font-medium rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                          Source: {exp.source_relationship_status}
                        </span>
                        <span className="px-1.5 py-0.5 text-[10px] font-medium rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                          Evidence: {exp.evidence_availability}
                        </span>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-[11px]">
                      <div className="p-2 rounded bg-slate-50 dark:bg-slate-800">
                        <span className="text-slate-500 block mb-0.5">Expected:</span>
                        <span className="text-slate-800 dark:text-slate-200">{exp.expected_behavior}</span>
                      </div>
                      <div className="p-2 rounded bg-slate-50 dark:bg-slate-800">
                        <span className="text-slate-500 block mb-0.5">Observed:</span>
                        <span className="text-slate-800 dark:text-slate-200">{exp.observed_behavior}</span>
                      </div>
                    </div>

                    <div className="text-[11px] text-slate-600 dark:text-slate-400">
                      <strong>Violated Requirement:</strong> {exp.violated_requirement}
                    </div>

                    {exp.requirements && exp.requirements.length > 0 && (
                      <div className="text-[11px] text-slate-700 dark:text-slate-300 space-y-0.5">
                        <strong>Relevant requirement{exp.requirements.length > 1 ? 's' : ''}:</strong>
                        {exp.requirements.map((r) => (
                          <div key={r.req_id} className="pl-2">
                            <span className="font-mono">{r.req_id}</span>
                            {r.version ? ` v${r.version}` : ''} — <strong>{r.title}</strong>
                            {r.description ? `: ${r.description}` : ''}
                          </div>
                        ))}
                      </div>
                    )}

                    {exp.expected_value_source && (
                      <div className="text-[11px] text-slate-700 dark:text-slate-300">
                        <strong>Expected value source:</strong>{' '}
                        <span className="font-mono">{exp.expected_value_source}</span>
                      </div>
                    )}

                    {exp.argument_provenance && (
                      <div className="text-[11px] text-indigo-700 dark:text-indigo-300">
                        <strong>Argument provenance ({exp.source_relationship_status}):</strong>{' '}
                        {exp.argument_provenance}
                      </div>
                    )}

                    {exp.evidence_supported_findings && exp.evidence_supported_findings.length > 0 && (
                      <div className="text-[11px] text-emerald-700 dark:text-emerald-400">
                        <strong>Supported Findings:</strong> {exp.evidence_supported_findings.join('; ')}
                      </div>
                    )}

                    {exp.uncertainties && exp.uncertainties.length > 0 && (
                      <div className="text-[11px] text-amber-700 dark:text-amber-400">
                        <strong>Uncertainties:</strong> {exp.uncertainties.join('; ')}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Candidate Code Locations */}
          {codeLocations.length > 0 && (
            <div className="space-y-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
                Ranked Candidate Code Locations ({codeLocations.length})
              </span>

              <div className="space-y-2">
                {codeLocations.map((loc, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-lg border border-indigo-200 dark:border-indigo-900/60 bg-indigo-50/30 dark:bg-indigo-950/20 space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-400">
                          #{loc.ranking_score || idx + 1}
                        </span>
                        <code className="font-mono text-slate-900 dark:text-white font-bold text-xs">
                          {loc.file_path}:{loc.line_start}-{loc.line_end}
                        </code>
                      </div>
                      <span className="text-[11px] text-slate-500 font-mono">
                        {loc.function_name}()
                      </span>
                    </div>

                    <div className="text-[11px] text-slate-600 dark:text-slate-400">
                      <strong>Ranking Justification:</strong> {loc.ranking_criteria}
                    </div>

                    {loc.supporting_evidence && loc.supporting_evidence.length > 0 && (
                      <div className="text-[10px] text-slate-500">
                        Corroborating Evidence: {loc.supporting_evidence.join(', ')}
                      </div>
                    )}

                    {loc.uncertainties && loc.uncertainties.length > 0 && (
                      <div className="text-[10px] text-amber-600 dark:text-amber-400">
                        Limitations: {loc.uncertainties.join('; ')}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Correction Request Section (code correction + sandbox: enabled per build) */}
          {correctionEnabled && (
          <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between">
            <div>
              {isEligibleForCorrection ? (
                <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">
                  <CheckCircle className="w-3.5 h-3.5" /> Eligible for Automated Candidate Fix &amp; Sandbox Verification
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-[11px] text-slate-500 dark:text-slate-400">
                  <Info className="w-3.5 h-3.5" />
                  {diagnosis.cause_category !== CAUSE_CATEGORIES.SUPPORTED_APPLICATION_CODE_DEFECT
                    ? 'Ineligible for code correction: failure is classified as non-code defect.'
                    : 'Ineligible for code correction: no mapped source code locations identified.'}
                </span>
              )}
            </div>

            {isEligibleForCorrection && onRequestCorrection && (
              <button
                type="button"
                onClick={() => onRequestCorrection(diagnosis)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm"
              >
                <span>Request Candidate Fix</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
          )}
        </div>
      )}
    </div>
  );
};
