import { useCallback, useEffect, useState } from 'react';
import { ClipboardCheck } from 'lucide-react';
import { c3Api, RECOVERY_VERDICT } from '../api.js';
import { C3Badge } from './C3Badge.jsx';

/**
 * Reviewer labels for one stored evaluation. The deterministic verdict is never changed;
 * each review is stored next to it (append-only, several reviewers allowed).
 */
export const C3ReviewPanel = ({ projectId, evaluationRecord, onReviewSaved }) => {
  const evaluationId = evaluationRecord?.evaluation_id;
  const evaluatorVerdict = evaluationRecord?.recovery_verdict || null;

  const [reviews, setReviews] = useState([]);
  const [verdict, setVerdict] = useState(
    evaluatorVerdict === RECOVERY_VERDICT.INCONCLUSIVE ? RECOVERY_VERDICT.FAIL : evaluatorVerdict || RECOVERY_VERDICT.FAIL
  );
  const [sufficient, setSufficient] = useState(true);
  const [rationale, setRationale] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    if (!projectId || !evaluationId) return;
    try {
      setReviews(await c3Api.listReviews(projectId, evaluationId));
    } catch (err) {
      setError(err.message || 'Failed to load reviews.');
    }
  }, [projectId, evaluationId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    setError(null);
    try {
      await c3Api.createReview(evaluationId, {
        project_id: projectId,
        reviewer_verdict: verdict,
        evidence_sufficient: sufficient,
        rationale,
      });
      setRationale('');
      await load();
      onReviewSaved?.();
    } catch (err) {
      setError(err.message || 'Failed to save the review.');
    } finally {
      setIsSaving(false);
    }
  };

  if (!evaluationId) return null;

  return (
    <section
      aria-labelledby="c3-review-heading"
      className={`p-4 rounded-xl border space-y-3 text-xs ${
        evaluatorVerdict === RECOVERY_VERDICT.INCONCLUSIVE
          ? 'border-amber-300 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20'
          : 'border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30'
      }`}
    >
      <h4 id="c3-review-heading" className="font-bold text-slate-900 dark:text-white flex items-center gap-2">
        <ClipboardCheck className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
        <span>Reviewer Verdict</span>
      </h4>
      <p className="text-slate-600 dark:text-slate-400">
        {evaluatorVerdict === RECOVERY_VERDICT.INCONCLUSIVE
          ? 'The evaluator could not decide this trial from the evidence. Read the agent answer and state facts, then record your verdict.'
          : 'Record an independent reviewer verdict. The evaluator verdict below is kept unchanged.'}{' '}
        Evaluator verdict: {evaluatorVerdict ? <C3Badge status={evaluatorVerdict} /> : 'not evaluated'}
      </p>

      {reviews.length > 0 && (
        <ul className="space-y-2">
          {reviews.map((r) => (
            <li key={r.review_id} className="p-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700">
              <div className="flex items-center gap-2 flex-wrap">
                <C3Badge status={r.reviewer_verdict} />
                <span className="text-slate-500">
                  {r.agrees_with_evaluator ? 'agrees with evaluator' : 'differs from evaluator'} ·{' '}
                  evidence {r.evidence_sufficient ? 'sufficient' : 'insufficient'} ·{' '}
                  {r.reviewer_name ? `${r.reviewer_name} (${r.reviewer_email})` : r.reviewer_email} ·{' '}
                  {new Date(r.created_at_utc).toLocaleString()}
                </span>
              </div>
              <p className="mt-1 text-slate-700 dark:text-slate-300">{r.rationale}</p>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={handleSubmit} className="space-y-2">
        <div className="flex items-center gap-3 flex-wrap">
          <label htmlFor="c3-review-verdict" className="font-semibold text-slate-700 dark:text-slate-300">
            Your verdict
          </label>
          <select
            id="c3-review-verdict"
            value={verdict}
            onChange={(e) => setVerdict(e.target.value)}
            className="px-2 py-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800"
          >
            {Object.values(RECOVERY_VERDICT).map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
          <label className="inline-flex items-center gap-1.5 text-slate-700 dark:text-slate-300">
            <input type="checkbox" checked={sufficient} onChange={(e) => setSufficient(e.target.checked)} />
            Evidence sufficient
          </label>
        </div>
        <label htmlFor="c3-review-rationale" className="block font-semibold text-slate-700 dark:text-slate-300">
          Rationale (required, at least 10 characters)
        </label>
        <textarea
          id="c3-review-rationale"
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          rows={3}
          required
          minLength={10}
          className="w-full px-2 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800"
          placeholder="Why this verdict? Refer to the agent answer, tool calls and state facts."
        />
        {error && <p className="text-rose-700 dark:text-rose-300">{error}</p>}
        <button
          type="submit"
          disabled={isSaving || rationale.trim().length < 10}
          className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold disabled:opacity-50"
        >
          {isSaving ? 'Saving…' : 'Save Review'}
        </button>
      </form>
    </section>
  );
};
