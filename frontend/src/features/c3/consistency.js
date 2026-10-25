/** Per case: how often each verdict (or run status when not evaluated) occurred across repeats. */
export const summarizeConsistency = (caseResults) => {
  const byCase = new Map();
  caseResults.forEach((r) => {
    const outcome = r.recovery_verdict || r.status;
    const counts = byCase.get(r.case_id) || new Map();
    counts.set(outcome, (counts.get(outcome) || 0) + 1);
    byCase.set(r.case_id, counts);
  });
  return [...byCase.entries()].map(([caseId, counts]) => {
    const runs = [...counts.values()].reduce((a, b) => a + b, 0);
    return { caseId, runs, counts: [...counts.entries()], consistent: counts.size === 1 };
  });
};
