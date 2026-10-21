import React, { useState } from 'react';
import { X, CheckCircle, ShieldCheck, AlertCircle } from 'lucide-react';

export const ApprovalModal = ({
  isOpen,
  onClose,
  model,
  onApprove,
  isApproving = false,
  currentUserEmail = '',
}) => {
  const [reviewerId, setReviewerId] = useState(currentUserEmail || '');
  const [reviewType, setReviewType] = useState('SELF_REPORTED_DEVELOPMENT');
  const [reviewerAffiliation, setReviewerAffiliation] = useState('');
  const [reviewBasis, setReviewBasis] = useState('');
  const [reviewNotes, setReviewNotes] = useState('');
  const [validationError, setValidationError] = useState('');

  if (!isOpen || !model) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setValidationError('');

    if (!reviewerId.trim()) {
      setValidationError('Reviewer ID is required.');
      return;
    }

    if (reviewType !== 'SELF_REPORTED_DEVELOPMENT' && !reviewerAffiliation.trim()) {
      setValidationError(
        'Reviewer affiliation/organization is required for claimed independent review.'
      );
      return;
    }

    if (!reviewBasis.trim()) {
      setValidationError('Review basis is required (e.g. specification or test checklist).');
      return;
    }

    if (reviewType !== 'SELF_REPORTED_DEVELOPMENT' && !reviewNotes.trim()) {
      setValidationError(
        'Detailed review notes and observations are required for claimed independent review.'
      );
      return;
    }

    try {
      const formattedReviewer =
        reviewType === 'SELF_REPORTED_DEVELOPMENT'
          ? reviewerId.trim()
          : `${reviewerId.trim()} (${reviewerAffiliation.trim()})`;

      await onApprove({
        reviewerId: formattedReviewer,
        reviewType,
        reviewBasis: reviewBasis.trim(),
        reviewNotes: reviewNotes.trim() || null,
      });
      onClose();
    } catch {
      // Error handled by parent hook
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="approval-modal-title"
    >
      <div className="bg-white dark:bg-[#131A26] rounded-2xl border border-slate-200 dark:border-slate-800 shadow-2xl max-w-xl w-full flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-indigo-100 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h2 id="approval-modal-title" className="text-base font-semibold text-slate-900 dark:text-white">
                Review & Approve Model
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Model: <code className="font-mono">{model.model_id}</code> (v{model.version})
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            aria-label="Close approval modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto">
          {/* Truthful Provenance Notice */}
          <div className="p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/60 text-xs text-amber-900 dark:text-amber-200 space-y-1">
            <div className="font-semibold flex items-center gap-1.5">
              <AlertCircle className="w-4 h-4 text-amber-600 dark:text-amber-400" />
              Truthful Review Provenance Policy
            </div>
            <p className="leading-relaxed">
              Approval permanently freezes this reference model version. Development self-reviews are transparently
              recorded with <code className="font-mono">[SELF_REPORTED_DEVELOPMENT]</code> provenance in accordance
              with audit integrity and must not be presented as independent QA verification.
            </p>
            <p className="text-[11px] text-amber-800/80 dark:text-amber-300/80 pt-1 border-t border-amber-200/60 dark:border-amber-900/40">
              * The backend does not verify reviewer identity or cryptographic signatures. Any selection other than self-review
              represents an unverified client claim and is displayed as unverified by backend.
            </p>
          </div>

          {validationError && (
            <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-800 dark:text-rose-200">
              {validationError}
            </div>
          )}

          {/* Review Type */}
          <div className="space-y-1.5">
            <label htmlFor="review-type" className="block text-xs font-medium text-slate-700 dark:text-slate-300">
              Review Provenance Classification <span className="text-rose-500">*</span>
            </label>
            <select
              id="review-type"
              value={reviewType}
              onChange={(e) => setReviewType(e.target.value)}
              className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:ring-2 focus:ring-indigo-500"
            >
              <option value="SELF_REPORTED_DEVELOPMENT">
                Self-Reported Development Review (Non-independent, Default)
              </option>
              <option value="INDEPENDENT_PEER_REVIEW">
                Claimed Independent Peer Review (Self-Asserted)
              </option>
              <option value="FORMAL_QA_SIGNOFF">
                Claimed Formal QA Sign-off (Self-Asserted)
              </option>
            </select>
          </div>

          {/* Reviewer ID */}
          <div className="space-y-1.5">
            <label htmlFor="reviewer-id" className="block text-xs font-medium text-slate-700 dark:text-slate-300">
              Reviewer Identifier <span className="text-rose-500">*</span>
            </label>
            <input
              id="reviewer-id"
              type="text"
              value={reviewerId}
              onChange={(e) => setReviewerId(e.target.value)}
              placeholder="e.g. reviewer@organization.org or dev-team-lead"
              required
              className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Reviewer Affiliation (Required for claimed independent review) */}
          {reviewType !== 'SELF_REPORTED_DEVELOPMENT' && (
            <div className="space-y-1.5">
              <label htmlFor="reviewer-affiliation" className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                Reviewer Organization / Department <span className="text-rose-500">*</span>
              </label>
              <input
                id="reviewer-affiliation"
                type="text"
                value={reviewerAffiliation}
                onChange={(e) => setReviewerAffiliation(e.target.value)}
                placeholder="e.g. Independent QA Dept / Audit Division"
                required
                className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          )}

          {/* Review Basis */}
          <div className="space-y-1.5">
            <label htmlFor="review-basis" className="block text-xs font-medium text-slate-700 dark:text-slate-300">
              Specification or Test Basis <span className="text-rose-500">*</span>
            </label>
            <input
              id="review-basis"
              type="text"
              value={reviewBasis}
              onChange={(e) => setReviewBasis(e.target.value)}
              placeholder="e.g. Verified against E-Commerce Business Requirements v2026.1 and SUT trace 503"
              required
              className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Review Notes */}
          <div className="space-y-1.5">
            <label htmlFor="review-notes" className="block text-xs font-medium text-slate-700 dark:text-slate-300">
              Review Observations & Rationale {reviewType === 'SELF_REPORTED_DEVELOPMENT' ? '(Optional)' : <span className="text-rose-500">*</span>}
            </label>
            <textarea
              id="review-notes"
              rows={3}
              value={reviewNotes}
              onChange={(e) => setReviewNotes(e.target.value)}
              placeholder="Record any notable guard constraints, invariants checked, or assumptions validated..."
              required={reviewType !== 'SELF_REPORTED_DEVELOPMENT'}
              className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Footer Actions */}
          <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={onClose}
              disabled={isApproving}
              className="px-4 py-2 text-xs font-medium rounded-xl border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isApproving}
              className="px-4 py-2 text-xs font-medium rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white flex items-center gap-1.5 transition-colors disabled:opacity-50"
            >
              {isApproving ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Recording Approval...
                </>
              ) : (
                <>
                  <CheckCircle className="w-4 h-4" />
                  Approve and Freeze Version
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
