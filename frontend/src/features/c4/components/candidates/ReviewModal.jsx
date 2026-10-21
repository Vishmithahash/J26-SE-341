/**
 * Component 4 (C4) - Candidate Rule Review Modal
 * Modal dialog for human or dev review gate (ACCEPT / REJECT) with rationale.
 */

import React, { useState } from 'react';
import { CheckCircle, XCircle, X } from 'lucide-react';
import { useAuth } from '../../../../context/AuthContext';

export function ReviewModal({
  isOpen,
  rule,
  decision,
  onClose,
  onSubmitReview,
  isReviewing,
}) {
  const { user } = useAuth();
  const defaultReviewer = user?.name || user?.email || 'dev_reviewer';
  const [reviewer, setReviewer] = useState(defaultReviewer);
  const [reviewNotes, setReviewNotes] = useState('');

  if (!isOpen || !rule) return null;

  const isAccept = decision === 'ACCEPTED';

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!reviewer.trim() || isReviewing) return;

    onSubmitReview({
      ruleId: rule.rule_id,
      decision,
      reviewer: reviewer.trim(),
      reviewNotes: reviewNotes.trim() || null,
    });
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="review-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm animate-in fade-in duration-150"
    >
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl w-full max-w-lg shadow-2xl p-6 relative">
        <button
          onClick={onClose}
          disabled={isReviewing}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1 rounded-lg"
          aria-label="Close dialog"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div
            className={`w-10 h-10 rounded-xl flex items-center justify-center ${
              isAccept
                ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400'
                : 'bg-rose-100 dark:bg-rose-950 text-rose-600 dark:text-rose-400'
            }`}
          >
            {isAccept ? <CheckCircle className="w-5 h-5" /> : <XCircle className="w-5 h-5" />}
          </div>
          <div>
            <h3 id="review-modal-title" className="text-base font-bold text-slate-900 dark:text-white">
              {isAccept ? 'Accept Candidate Rule' : 'Reject Candidate Rule'}
            </h3>
            <p className="text-xs text-slate-500 font-mono">
              Rule ID: {rule.rule_id}
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Reviewer Name / Actor ID <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              value={reviewer}
              onChange={(e) => setReviewer(e.target.value)}
              required
              disabled={isReviewing}
              className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Review Notes / Decision Justification
            </label>
            <textarea
              rows={3}
              value={reviewNotes}
              onChange={(e) => setReviewNotes(e.target.value)}
              placeholder={
                isAccept
                  ? 'e.g. Provenance and condition thresholds verified against policy document.'
                  : 'e.g. Unclear condition boundaries or ungrounded principal selector.'
              }
              disabled={isReviewing}
              className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
            <button
              type="button"
              onClick={onClose}
              disabled={isReviewing}
              className="px-4 py-2 text-xs font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isReviewing || !reviewer.trim()}
              className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-white text-xs font-medium transition-colors shadow-sm ${
                isAccept
                  ? 'bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300'
                  : 'bg-rose-600 hover:bg-rose-700 disabled:bg-slate-300'
              }`}
            >
              {isReviewing ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Recording...</span>
                </>
              ) : (
                <>
                  {isAccept ? <CheckCircle className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                  <span>Confirm {decision}</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
