import React, { useState, useEffect } from 'react';
import {
  Lock,
  Layers,
  ShieldCheck,
  Eye,
  Calendar,
  CheckCircle,
  FileCode,
  Terminal,
} from 'lucide-react';
import { c1Api } from './c1Api';

export const SuiteViewer = ({ projectId, activeSuite, onSelectSuite }) => {
  const [suites, setSuites] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedSuite, setSelectedSuite] = useState(activeSuite || null);
  const [agentTaskPreview, setAgentTaskPreview] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  useEffect(() => {
    let isCancelled = false;
    if (!projectId) return;

    const fetchSuites = async () => {
      setIsLoading(true);
      setErrorMsg(null);
      try {
        const list = await c1Api.listSuites(projectId);
        if (!isCancelled) {
          setSuites(list || []);
          if (!selectedSuite && list && list.length > 0) {
            setSelectedSuite(list[0]);
          }
        }
      } catch (err) {
        if (!isCancelled) {
          setErrorMsg(err.message || 'Failed to load test suites.');
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    };

    fetchSuites();

    return () => {
      isCancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    if (activeSuite) {
      setSelectedSuite(activeSuite);
    }
  }, [activeSuite]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-slate-900 dark:text-white flex items-center gap-2">
            <Lock className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
            Accepted &amp; Frozen Test Suites
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Immutable, cryptographically hashed test suites ready for reproducible execution
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500 dark:text-slate-400">
            Total Accepted Suites: <strong className="text-slate-900 dark:text-white font-semibold">{suites.length}</strong>
          </span>
        </div>
      </div>

      {errorMsg && (
        <div className="p-3 text-xs rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-300">
          {errorMsg}
        </div>
      )}

      {isLoading ? (
        <div className="p-12 text-center text-slate-500 text-xs">
          <div className="w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          Loading accepted suites...
        </div>
      ) : suites.length === 0 ? (
        <div className="p-8 text-center rounded-xl border border-dashed border-slate-200 dark:border-slate-800 text-slate-400 text-xs space-y-2">
          <Layers className="w-8 h-8 mx-auto text-slate-300 dark:text-slate-600" />
          <div>No accepted test suites created yet.</div>
          <p className="text-[11px] text-slate-400">
            Generate candidates in the &quot;Test Cases&quot; tab and promote valid candidates to create an immutable suite.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Suite List */}
          <div className="space-y-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Suite Versions
            </span>
            <div className="space-y-2">
              {suites.map((s) => {
                const isSelected = selectedSuite?.suite_id === s.suite_id;
                return (
                  <div
                    key={`${s.suite_id}-${s.version}`}
                    onClick={() => {
                      setSelectedSuite(s);
                      if (onSelectSuite) onSelectSuite(s);
                    }}
                    className={`p-3 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? 'border-emerald-500 bg-emerald-50/40 dark:bg-emerald-950/20 shadow-xs'
                        : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-slate-300'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="font-mono text-xs font-bold text-slate-900 dark:text-white">
                        {s.suite_id}
                      </div>
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-semibold rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-400">
                        <Lock className="w-2.5 h-2.5" /> v{s.version}
                      </span>
                    </div>
                    <div className="text-xs font-medium text-slate-700 dark:text-slate-300 mt-1">
                      {s.name}
                    </div>
                    <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-2 flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {new Date(s.created_at).toLocaleDateString()}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Selected Suite Detail & Isolated Agent View */}
          <div className="md:col-span-2 space-y-4">
            {selectedSuite ? (
              <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-emerald-600" />
                      {selectedSuite.name}
                    </h3>
                    <div className="text-xs font-mono text-slate-500 dark:text-slate-400 mt-0.5">
                      Suite ID: {selectedSuite.suite_id} (Version {selectedSuite.version})
                    </div>
                  </div>
                  <span className="px-2 py-1 text-xs font-semibold rounded-md bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                    Immutable &amp; Frozen
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-slate-500 dark:text-slate-400">Linked Config ID:</span>
                    <div className="font-mono text-slate-800 dark:text-slate-200 mt-0.5">
                      {selectedSuite.config_id || 'N/A'}
                    </div>
                  </div>
                  <div>
                    <span className="text-slate-500 dark:text-slate-400">Locked At:</span>
                    <div className="text-slate-800 dark:text-slate-200 mt-0.5">
                      {new Date(selectedSuite.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>

                {/* Agent-Facing Task Isolation Verification Banner */}
                <div className="p-3.5 rounded-lg border border-indigo-200 dark:border-indigo-900/60 bg-indigo-50/50 dark:bg-indigo-950/30 text-xs space-y-2">
                  <div className="flex items-center gap-1.5 font-semibold text-indigo-900 dark:text-indigo-300">
                    <Terminal className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                    Agent-Facing Task Isolation
                  </div>
                  <p className="text-[11px] text-indigo-800/80 dark:text-indigo-300/80">
                    In accordance with QA isolation principles, the tested agent only receives the task prompt, context inputs, and declared permitted tools. QA oracle expectations, argument assertions, and evaluation rules are strictly quarantined within this workspace.
                  </p>
                </div>
              </div>
            ) : (
              <div className="p-8 text-center text-slate-400 text-xs border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
                Select a suite from the list to view frozen details.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
