import React, { useState, useEffect, useCallback } from 'react';
import {
  Wrench,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Clock,
  ShieldCheck,
  FileCode,
  GitCommit,
  Check,
  RotateCcw,
  UserCheck,
  AlertCircle,
  Layers,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import {
  c1Api,
  escapeText,
  CORRECTION_STATUS,
  STEP_EXECUTION_STATUS,
  REVIEW_DECISIONS,
} from './c1Api';

export const CorrectionReviewPanel = ({
  projectId,
  diagnosisId,
  caseId,
  runId,
  currentUser,
  onReviewSubmitted,
}) => {
  const [correction, setCorrection] = useState(null);
  const [diffData, setDiffData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Review Modal State
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [reviewDecision, setReviewDecision] = useState(REVIEW_DECISIONS.ACCEPTED);
  const [reviewReason, setReviewReason] = useState('');
  const [reviewerName, setReviewerName] = useState(currentUser?.name || currentUser?.email || 'developer');

  // Load correction for this diagnosis if one exists
  const loadCorrectionData = useCallback(async () => {
    if (!projectId || !diagnosisId) return;
    setIsLoading(true);
    try {
      const list = await c1Api.listCorrections(projectId, { limit: 20 });
      const matching = (list || []).find((c) => c.diagnosis_id === diagnosisId);
      if (matching) {
        const full = await c1Api.getCorrection(projectId, matching.correction_id);
        setCorrection(full);
        if (full?.candidate_patch) {
          const diff = await c1Api.getCorrectionDiff(projectId, full.correction_id);
          setDiffData(diff);
        }
      } else {
        setCorrection(null);
        setDiffData(null);
      }
    } catch {
      // Ignored if no correction attempts exist yet
    } finally {
      setIsLoading(false);
    }
  }, [projectId, diagnosisId]);

  useEffect(() => {
    loadCorrectionData();
  }, [loadCorrectionData]);

  // NexaCart verification builds and re-runs NexaCart live: follow it step by step.
  useEffect(() => {
    if (correction?.status !== CORRECTION_STATUS.VERIFYING || !correction?.correction_id) {
      return undefined;
    }
    const timer = setTimeout(async () => {
      try {
        const latest = await c1Api.getCorrection(projectId, correction.correction_id);
        setCorrection(latest);
        if (latest.status !== CORRECTION_STATUS.VERIFYING) {
          setSuccessMsg(`Sandbox verification finished: ${latest.status}.`);
        }
      } catch {
        // retry on the next tick
      }
    }, 4000);
    return () => clearTimeout(timer);
  }, [correction, projectId]);

  // Request new candidate fix
  const handleRequestCorrection = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const rec = await c1Api.requestCorrection(projectId, {
        diagnosis_id: diagnosisId,
        idempotency_key: `corr_${diagnosisId}_${Date.now()}`,
      });
      setCorrection(rec);
      setSuccessMsg(
        rec.status === CORRECTION_STATUS.VERIFYING
          ? 'Candidate patch generated. Verifying on a disposable NexaCart copy (build, live rerun, Jest, acceptance): several minutes.'
          : `Candidate correction attempt finished (${rec.status}).`
      );
      if (rec?.candidate_patch) {
        const diff = await c1Api.getCorrectionDiff(projectId, rec.correction_id);
        setDiffData(diff);
      }
    } catch (err) {
      setErrorMsg(err.message || 'Correction attempt failed or was ineligible.');
    } finally {
      setIsLoading(false);
    }
  };

  // Submit developer review
  const handleSubmitReview = async (e) => {
    e.preventDefault();
    if (!correction?.correction_id || !correction?.candidate_patch?.patch_hash) {
      setErrorMsg('No active candidate patch hash available to review.');
      return;
    }

    setIsSubmittingReview(true);
    setErrorMsg(null);
    try {
      const updated = await c1Api.submitReview(projectId, correction.correction_id, {
        decision: reviewDecision,
        reviewer: reviewerName.trim() || 'developer',
        target_patch_hash: correction.candidate_patch.patch_hash,
        reason: reviewReason.trim() || 'Reviewed in Component 1 workspace.',
      });
      setCorrection(updated);
      setShowReviewModal(false);
      setSuccessMsg(`Developer review recorded: ${updated.review?.decision}.`);
      if (onReviewSubmitted) {
        onReviewSubmitted(updated);
      }
    } catch (err) {
      setErrorMsg(err.message || 'Failed to submit review decision. Check for patch hash conflict.');
    } finally {
      setIsSubmittingReview(false);
    }
  };

  return (
    <div className="space-y-4 p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
      <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <Wrench className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-white">
            Sandbox Verification &amp; Developer Decision
          </h4>
        </div>

        {correction && (
          <div className="flex items-center gap-2">
            <span
              className={`px-2 py-0.5 text-[10px] font-bold rounded-full ${
                correction.is_verified
                  ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-400'
                  : 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-400'
              }`}
            >
              {correction.is_verified ? 'VERIFIED (All Checks Passed)' : 'UNVERIFIED / BLOCKED'}
            </span>
            <span className="text-[11px] text-slate-400 font-mono">
              Attempt #{correction.attempt_number || 1}
            </span>
          </div>
        )}
      </div>

      {successMsg && (
        <div className="p-3 text-xs rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300">
          {successMsg}
        </div>
      )}

      {errorMsg && (
        <div className="p-3 text-xs rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-300">
          {errorMsg}
        </div>
      )}

      {!correction ? (
        <div className="p-6 text-center rounded-lg border border-dashed border-slate-200 dark:border-slate-800 text-xs space-y-3">
          <p className="text-slate-500 dark:text-slate-400 max-w-md mx-auto">
            Ready to generate an evidence-bounded candidate patch and verify it against reproduction, build, regression, and independent acceptance checks in an isolated sandbox.
          </p>

          <button
            type="button"
            onClick={handleRequestCorrection}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm disabled:opacity-50"
          >
            <Wrench className="w-3.5 h-3.5" />
            {isLoading ? 'Running Sandbox Verification...' : 'Execute Candidate Correction & Verification'}
          </button>
        </div>
      ) : (
        <div className="space-y-4 text-xs">
          {/* Correction Overview Card */}
          <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold text-slate-500">
                Correction ID: <strong className="font-mono text-slate-800 dark:text-slate-200">{correction.correction_id}</strong>
              </span>
              <span className="text-[10px] text-slate-400">
                Isolation: {correction.isolation_type}
              </span>
            </div>
            {correction.candidate_patch?.rationale && (
              <p className="text-slate-700 dark:text-slate-300 text-[11px] mt-1">
                <strong>Rationale:</strong> {correction.candidate_patch.rationale}
              </p>
            )}
          </div>

          {/* Sandbox Verification Checks Checklist */}
          <div className="space-y-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
              Mandatory Verification Pipeline Checklist
            </span>

            {(!correction.verification_results || correction.verification_results.length === 0) ? (
              <div className="text-xs text-slate-400 italic">No verification checks recorded.</div>
            ) : (
              <div className="space-y-1.5">
                {correction.verification_results.map((step, idx) => (
                  <div
                    key={step.step_type || idx}
                    className="flex items-center justify-between p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-xs"
                  >
                    <div className="flex items-center gap-2">
                      {step.status === 'PASSED' ? (
                        <CheckCircle className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                      ) : step.status === 'FAILED' ? (
                        <XCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
                      ) : (
                        <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
                      )}

                      <div>
                        <span className="font-semibold text-slate-800 dark:text-slate-200 font-mono">
                          {step.step_type}
                        </span>
                        <div className="text-[10px] text-slate-500">
                          {step.observed_outcome}
                        </div>
                      </div>
                    </div>

                    <div className="text-right">
                      <span
                        className={`px-1.5 py-0.5 text-[10px] font-bold rounded ${
                          step.status === 'PASSED'
                            ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-400'
                            : 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-400'
                        }`}
                      >
                        {step.status}
                      </span>
                      <div className="text-[10px] text-slate-400 mt-0.5">
                        {step.duration_ms?.toFixed(1)}ms
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Unified Diff Viewer */}
          {diffData?.diff_content && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
                  <FileCode className="w-3.5 h-3.5" />
                  Candidate Code Patch Unified Diff
                </span>
                <span className="text-[10px] font-mono text-slate-400">
                  Hash: {diffData.patch_hash?.slice(0, 10)}...
                </span>
              </div>

              <div className="p-3 rounded-lg bg-slate-950 text-slate-100 font-mono text-[11px] overflow-x-auto max-h-64 border border-slate-800">
                {diffData.diff_content.split('\n').map((line, lIdx) => {
                  let lineClass = 'text-slate-300';
                  if (line.startsWith('+') && !line.startsWith('+++')) lineClass = 'text-emerald-400 bg-emerald-950/30';
                  if (line.startsWith('-') && !line.startsWith('---')) lineClass = 'text-red-400 bg-red-950/30';
                  if (line.startsWith('@@')) lineClass = 'text-sky-400';

                  return (
                    <div key={lIdx} className={`${lineClass} px-1 rounded`}>
                      {escapeText(line)}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Developer Review Card */}
          <div className="p-3.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-xs font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                  <UserCheck className="w-4 h-4 text-indigo-600" />
                  Developer Review Decision
                </span>
                <p className="text-[11px] text-slate-500">
                  Review decision is bound to patch hash {correction.candidate_patch?.patch_hash?.slice(0, 8)}...
                </p>
              </div>

              <span
                className={`px-2 py-0.5 text-[10px] font-bold rounded-full ${
                  correction.review?.decision === 'ACCEPTED'
                    ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-400'
                    : correction.review?.decision === 'REJECTED'
                    ? 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-400'
                    : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-400'
                }`}
              >
                {correction.review?.decision || 'PENDING'}
              </span>
            </div>

            {correction.review?.reviewed_at ? (
              <div className="text-[11px] text-slate-600 dark:text-slate-300 space-y-0.5 pt-1 border-t border-slate-200 dark:border-slate-700">
                <div>Reviewed by: <strong>{correction.review.reviewer}</strong> on {new Date(correction.review.reviewed_at).toLocaleString()}</div>
                <div>Reason: <em>{correction.review.reason || 'None specified'}</em></div>
              </div>
            ) : (
              <div className="space-y-2 pt-2 border-t border-slate-200 dark:border-slate-700">
                {!correction.is_verified && (
                  <div className="p-2 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/60 text-[11px] text-amber-800 dark:text-amber-300 flex items-start gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                    <span>
                      <strong>Acceptance Ineligible:</strong> Only candidates where every mandatory sandbox verification check passed can be accepted. Rejecting the candidate is permitted.
                    </span>
                  </div>
                )}

                <div className="flex items-center justify-between text-[10px] text-slate-400">
                  <span>Bound to patch hash: <code className="font-mono font-bold text-slate-600 dark:text-slate-300">{correction.candidate_patch?.patch_hash?.slice(0, 10)}...</code></span>
                  <span>Audit Logging Only</span>
                </div>

                <div className="flex items-center justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setReviewDecision(REVIEW_DECISIONS.REJECTED);
                      setShowReviewModal(true);
                    }}
                    className="px-3 py-1.5 text-xs font-semibold rounded-lg border border-red-300 dark:border-red-800 text-red-700 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40"
                  >
                    Reject Candidate
                  </button>
                  <button
                    type="button"
                    disabled={!correction.is_verified}
                    onClick={() => {
                      if (correction.is_verified) {
                        setReviewDecision(REVIEW_DECISIONS.ACCEPTED);
                        setShowReviewModal(true);
                      }
                    }}
                    title={
                      !correction.is_verified
                        ? 'Candidate must pass all mandatory sandbox checks before acceptance'
                        : 'Record developer acceptance decision'
                    }
                    className="px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    Accept Candidate
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Review Submission Modal */}
      {showReviewModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="w-full max-w-md p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <UserCheck className="w-4 h-4 text-indigo-600" />
                Record Developer Decision: {reviewDecision}
              </h3>
              <button
                type="button"
                onClick={() => setShowReviewModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 text-[11px] text-slate-500 dark:text-slate-400 space-y-1">
              <p>
                Decision binds strictly to patch hash: <code className="font-mono font-bold text-slate-800 dark:text-slate-200">{correction?.candidate_patch?.patch_hash?.slice(0, 10)}...</code>.
              </p>
              <p className="text-[10px] text-amber-700 dark:text-amber-400">
                <strong>Authorization Notice:</strong> Reviewer ID is recorded for audit tracking only. The backend does not enforce role-based reviewer authority server-side. Recorded acceptance does not execute direct repository merges or deployments.
              </p>
            </div>

            <form onSubmit={handleSubmitReview} className="space-y-3 text-xs">
              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Reviewer Identifier <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={reviewerName}
                  onChange={(e) => setReviewerName(e.target.value)}
                  className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Review Rationale / Notes
                </label>
                <textarea
                  rows={2}
                  value={reviewReason}
                  onChange={(e) => setReviewReason(e.target.value)}
                  placeholder="Justification for acceptance or rejection..."
                  className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowReviewModal(false)}
                  className="px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingReview || (reviewDecision === REVIEW_DECISIONS.ACCEPTED && !correction.is_verified)}
                  className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg text-white disabled:opacity-40 disabled:cursor-not-allowed ${
                    reviewDecision === 'ACCEPTED'
                      ? 'bg-emerald-600 hover:bg-emerald-700'
                      : 'bg-red-600 hover:bg-red-700'
                  }`}
                >
                  {isSubmittingReview ? 'Recording...' : `Confirm ${reviewDecision}`}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
