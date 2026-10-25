import { useEffect, useState } from 'react';
import { Gauge, RotateCw } from 'lucide-react';
import { c3Api } from '../api.js';
import { C3Badge } from './C3Badge.jsx';

const fmtSeconds = (ms) => (ms === null || ms === undefined ? '—' : `${(ms / 1000).toFixed(1)} s`);
const fmtNumber = (v) => (v === null || v === undefined ? '—' : v);
const fmtSigned = (v, format = fmtNumber) =>
  v === null || v === undefined ? '—' : `${v > 0 ? '+' : ''}${format(v)}`;

/**
 * Recovery cost (proposal RQ4): what each fault trial cost compared with its clean control.
 */
export const C3RecoveryCostPanel = ({ projectId, executions = [] }) => {
  const [executionId, setExecutionId] = useState('');
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const liveExecutions = executions.filter((x) => x.target_mode === 'LIVE_AUT');

  useEffect(() => {
    if (!projectId) return undefined;
    const controller = new AbortController();
    setIsLoading(true);
    setError(null);
    c3Api
      .getLiveRecoveryCost(projectId, executionId || undefined, controller.signal)
      .then(setData)
      .catch((err) => {
        if (err.name !== 'AbortError') setError(err.message || 'Failed to load recovery cost.');
      })
      .finally(() => setIsLoading(false));
    return () => controller.abort();
  }, [projectId, executionId, reloadKey]);

  const overall = data?.overall;

  return (
    <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4 text-xs">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Gauge className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <span>Recovery Cost (Live Runs)</span>
          </h3>
          <p className="text-slate-500 dark:text-slate-400 mt-0.5">
            Extra cost of each fault trial compared with its clean control, from stored evidence only.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="c3-cost-exec" className="text-slate-600 dark:text-slate-400">
            Execution
          </label>
          <select
            id="c3-cost-exec"
            value={executionId}
            onChange={(e) => setExecutionId(e.target.value)}
            className="px-2 py-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 font-mono"
          >
            <option value="">All live executions</option>
            {liveExecutions.map((x) => (
              <option key={x.execution_id} value={x.execution_id}>
                {x.execution_id} ({x.status})
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setReloadKey((k) => k + 1)}
            aria-label="Refresh recovery cost"
            className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300">{error}</div>
      )}

      {overall && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            ['Live pairs', overall.pairs],
            ['Avg extra time', fmtSigned(overall.avg_extra_duration_ms, fmtSeconds)],
            ['Avg extra tool calls', fmtSigned(overall.avg_extra_tool_calls)],
            [
              'Avg extra tokens',
              overall.pairs_with_tokens
                ? `${fmtSigned(overall.avg_extra_tokens)} (${overall.pairs_with_tokens} pairs)`
                : 'not recorded',
            ],
          ].map(([label, value]) => (
            <div key={label} className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
              <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block">{label}</span>
              <span className="text-base font-bold text-slate-900 dark:text-white">{value}</span>
            </div>
          ))}
        </div>
      )}

      {data?.groups?.length > 0 && (
        <div className="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-lg">
          <table className="w-full text-left">
            <caption className="sr-only">Average recovery cost per fault family and effect phase</caption>
            <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500">
              <tr>
                <th className="p-2">Fault family</th>
                <th className="p-2">Effect phase</th>
                <th className="p-2">Pairs</th>
                <th className="p-2">Avg extra time</th>
                <th className="p-2">Avg extra tool calls</th>
                <th className="p-2">Avg retries</th>
                <th className="p-2">Avg extra tokens</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono">
              {data.groups.map((g) => (
                <tr key={`${g.fault_family}-${g.effect_phase}`}>
                  <td className="p-2 text-indigo-600 dark:text-indigo-400">{g.fault_family}</td>
                  <td className="p-2">{g.effect_phase}</td>
                  <td className="p-2">{g.pairs}</td>
                  <td className="p-2">{fmtSigned(g.avg_extra_duration_ms, fmtSeconds)}</td>
                  <td className="p-2">{fmtSigned(g.avg_extra_tool_calls)}</td>
                  <td className="p-2">{fmtNumber(g.avg_retries)}</td>
                  <td className="p-2">{fmtSigned(g.avg_extra_tokens)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data?.pairs?.length > 0 && (
        <details className="border border-slate-200 dark:border-slate-800 rounded-lg">
          <summary className="p-2 cursor-pointer font-semibold text-slate-700 dark:text-slate-300">
            Per-pair cost ({data.pairs.length})
          </summary>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500">
                <tr>
                  <th className="p-2">Pair</th>
                  <th className="p-2">Fault</th>
                  <th className="p-2">Verdict</th>
                  <th className="p-2">Time (clean → fault)</th>
                  <th className="p-2">Tool calls</th>
                  <th className="p-2">Retries</th>
                  <th className="p-2">Tokens</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-mono">
                {data.pairs.map((p) => (
                  <tr key={p.pair_id}>
                    <td className="p-2">{p.pair_id}</td>
                    <td className="p-2">
                      {p.fault_family} / {p.effect_phase}
                    </td>
                    <td className="p-2">{p.recovery_verdict ? <C3Badge status={p.recovery_verdict} /> : '—'}</td>
                    <td className="p-2">
                      {fmtSeconds(p.clean_duration_ms)} → {fmtSeconds(p.fault_duration_ms)}
                    </td>
                    <td className="p-2">
                      {p.clean_tool_calls} → {p.fault_tool_calls}
                    </td>
                    <td className="p-2">{p.retries}</td>
                    <td className="p-2">
                      {p.clean_tokens ?? '—'} → {p.fault_tokens ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}

      {data && data.pairs?.length === 0 && (
        <p className="text-slate-500">No live pairs yet. Run cases from the Live NexaCart Runs tab.</p>
      )}
      {data?.notes?.map((n) => (
        <p key={n} className="text-[11px] text-slate-500 dark:text-slate-400">
          {n}
        </p>
      ))}
    </div>
  );
};
