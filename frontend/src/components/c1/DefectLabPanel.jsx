import React, { useState, useEffect, useRef, useCallback } from 'react';
import { FlaskConical, Play, Square, Download, AlertCircle, CheckCircle } from 'lucide-react';
import { c1Api } from './c1Api';

/**
 * Controlled-defect lab (proposal: controlled defects in permitted code areas).
 * Builds a disposable NexaCart copy with one seeded defect, runs it on a local port, and imports
 * a C1 configuration that targets it. The developer's NexaCart tree is never changed.
 */
export const DefectLabPanel = ({ projectId, onConfigImported }) => {
  const [lab, setLab] = useState(null);
  const [defects, setDefects] = useState([]);
  const [selectedDefect, setSelectedDefect] = useState('');
  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const timerRef = useRef(null);

  const load = useCallback(async () => {
    if (!projectId) return;
    try {
      const res = await c1Api.getDefectLab(projectId);
      setLab(res.lab);
      setDefects(res.defects || []);
      if (!selectedDefect && res.defects?.length) setSelectedDefect(res.defects[0].defect_id);
      if (res.lab?.status === 'BUILDING') {
        timerRef.current = setTimeout(load, 3000);
      }
    } catch (err) {
      setErrorMsg(err.message || 'Defect lab status unavailable.');
    }
  }, [projectId, selectedDefect]);

  useEffect(() => {
    load();
    return () => clearTimeout(timerRef.current);
  }, [load]);

  const handleStart = async () => {
    setBusy(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const res = await c1Api.startDefectLab(projectId, selectedDefect);
      setLab(res.lab);
      timerRef.current = setTimeout(load, 3000);
    } catch (err) {
      setErrorMsg(err.message || 'Could not start the defect lab.');
    } finally {
      setBusy(false);
    }
  };

  const handleStop = async () => {
    setBusy(true);
    try {
      const res = await c1Api.stopDefectLab(projectId);
      setLab(res.lab);
      setSuccessMsg('Defect lab stopped; its disposable copy was removed.');
    } catch (err) {
      setErrorMsg(err.message || 'Could not stop the defect lab.');
    } finally {
      setBusy(false);
    }
  };

  const handleImport = async () => {
    setBusy(true);
    setErrorMsg(null);
    try {
      const created = await c1Api.importNexaCartLiveConfig(projectId, 'lab');
      if (onConfigImported) onConfigImported(created);
      setSuccessMsg(
        `Imported lab configuration v${created.version} (targets ${lab?.base_url}). Generate and run a suite from it.`
      );
    } catch (err) {
      setErrorMsg(err.message || 'Could not import the lab configuration.');
    } finally {
      setBusy(false);
    }
  };

  const status = lab?.status;
  const active = status === 'BUILDING' || status === 'RUNNING';

  return (
    <div className="p-4 rounded-xl border border-violet-200 dark:border-violet-900 bg-white dark:bg-slate-900 space-y-3">
      <div className="flex items-center gap-2">
        <FlaskConical className="w-4 h-4 text-violet-600 dark:text-violet-400" />
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
          Controlled-Defect Lab (code diagnosis &amp; correction)
        </h3>
      </div>
      <p className="text-xs text-slate-600 dark:text-slate-400">
        Seeds one controlled defect into a disposable NexaCart copy with its own database and runs it
        as a separate local process, so code-level diagnosis, the candidate patch and sandbox
        verification can be evaluated on a known defect. Results from this lab are controlled-defect
        evidence, kept apart from natural agent behaviour. Your NexaCart source and database are never
        changed, and a running lab survives a QA backend restart.
      </p>

      <div className="flex flex-wrap items-end gap-2">
        <div className="flex-1 min-w-[16rem]">
          <label htmlFor="c1-defect" className="block text-[11px] font-medium text-slate-700 dark:text-slate-300 mb-1">
            Controlled defect
          </label>
          <select
            id="c1-defect"
            value={selectedDefect}
            disabled={active || busy}
            onChange={(e) => setSelectedDefect(e.target.value)}
            className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
          >
            {defects.map((d) => (
              <option key={d.defect_id} value={d.defect_id}>
                {d.defect_id} ({d.tool_name})
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          onClick={handleStart}
          disabled={active || busy || !selectedDefect}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-violet-600 hover:bg-violet-700 text-white disabled:opacity-50"
        >
          <Play className="w-3.5 h-3.5" />
          Start Lab
        </button>
        <button
          type="button"
          onClick={handleImport}
          disabled={status !== 'RUNNING' || busy}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-violet-300 dark:border-violet-800 text-violet-700 dark:text-violet-300 disabled:opacity-50"
        >
          <Download className="w-3.5 h-3.5" />
          Import Lab Configuration
        </button>
        <button
          type="button"
          onClick={handleStop}
          disabled={!active || busy}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 disabled:opacity-50"
        >
          <Square className="w-3.5 h-3.5" />
          Stop Lab
        </button>
      </div>

      {selectedDefect && (
        <div className="text-[11px] text-slate-500">
          {defects.find((d) => d.defect_id === selectedDefect)?.description}
        </div>
      )}

      {lab && (
        <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800 text-xs text-slate-700 dark:text-slate-300 space-y-1">
          <div>
            Status: <strong>{lab.status}</strong>
            {lab.base_url ? ` — ${lab.base_url}` : ''}
          </div>
          <div>{lab.message}</div>
          {lab.sandbox_database && (
            <div>
              Isolated database: <span className="font-mono">{lab.sandbox_database}</span> (your
              NexaCart database is not used)
            </div>
          )}
          {lab.recovered_at && (
            <div>Recovered after a QA backend restart at {new Date(lab.recovered_at).toLocaleString()}.</div>
          )}
          {lab.seeding_diff && (
            <details>
              <summary className="cursor-pointer text-[11px] text-slate-500">Seeded change (controlled defect)</summary>
              <pre className="mt-1 p-2 text-[10px] overflow-x-auto bg-white dark:bg-slate-900 rounded">{lab.seeding_diff}</pre>
            </details>
          )}
        </div>
      )}

      {errorMsg && (
        <div className="flex items-center gap-2 p-2 text-xs rounded-lg bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-300">
          <AlertCircle className="w-3.5 h-3.5" /> {errorMsg}
        </div>
      )}
      {successMsg && (
        <div className="flex items-center gap-2 p-2 text-xs rounded-lg bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300">
          <CheckCircle className="w-3.5 h-3.5" /> {successMsg}
        </div>
      )}
    </div>
  );
};

export default DefectLabPanel;
