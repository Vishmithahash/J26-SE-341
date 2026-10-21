import React, { useState } from 'react';
import {
  Workflow,
  FileText,
  Sparkles,
  Shield,
  FolderGit2,
} from 'lucide-react';
import { C3EvaluationsViewer } from './C3EvaluationsViewer';
import { C3ExecutionReportViewer } from './C3ExecutionReportViewer';
import { C3ResearchView } from './C3ResearchView';
import { useC3Executions } from '../hooks/useC3Executions';

export const C3ResultsWorkspace = ({ projectId, role = 'USER' }) => {
  const [activeTab, setActiveTab] = useState('evaluations'); // 'evaluations' | 'reports' | 'research'
  const isAdmin = role === 'ADMIN';

  const { executions, latestExecution } = useC3Executions(projectId);
  const [selectedExecutionId, setSelectedExecutionId] = useState('');

  const currentExecId = selectedExecutionId || latestExecution?.execution_id || 'exec-demo-001';

  return (
    <div className="space-y-6">
      {/* Top Banner & Scope Disclosure */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-[11px] font-bold uppercase tracking-wider bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
              <Workflow className="w-3.5 h-3.5" />
              Phase 3 Results & Reporting
            </span>
            {isAdmin && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-bold uppercase tracking-wider bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
                <Shield className="w-3 h-3" />
                Administrative Oversight
              </span>
            )}
          </div>
          <h2 className="text-lg font-bold text-slate-900 dark:text-white">
            Recovery Results, Causal Findings & Reports
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Inspect deterministic recovery verdicts (Pass: Completed, Pass: Graceful, Fail, Inconclusive), causal rule explanations, trusted C2 facts, and structured execution reports.
          </p>
        </div>

        {/* Project Scope Indicator */}
        <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 text-xs shrink-0 max-w-xs">
          <div className="flex items-center gap-1.5 text-slate-500 font-semibold text-[11px] uppercase tracking-wider">
            <FolderGit2 className="w-3.5 h-3.5 text-indigo-500" />
            <span>{isAdmin ? 'Selected Admin Project' : 'Active Project Scope'}</span>
          </div>
          <code className="text-indigo-600 dark:text-indigo-400 font-mono font-bold block truncate mt-0.5">
            {projectId || 'No project selected'}
          </code>
          {isAdmin && (
            <span className="text-[10px] text-slate-400 mt-0.5 block leading-tight">
              Scope: Authorized project records.
            </span>
          )}
        </div>
      </div>

      {/* Workspace Tabs Navigation */}
      <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2 overflow-x-auto">
        <button
          type="button"
          onClick={() => setActiveTab('evaluations')}
          className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-colors whitespace-nowrap ${
            activeTab === 'evaluations'
              ? 'bg-indigo-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <Workflow className="w-4 h-4" />
          <span>1. Recovery Evaluations & Explanations</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('reports')}
          className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-colors whitespace-nowrap ${
            activeTab === 'reports'
              ? 'bg-indigo-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>2. Execution Reports & CSV Export</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('research')}
          className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 transition-colors whitespace-nowrap ${
            activeTab === 'research'
              ? 'bg-purple-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <Sparkles className="w-4 h-4" />
          <span>3. Research Protocols & Ablations (CLI)</span>
        </button>
      </div>

      {/* Tab 1: Evaluations Viewer */}
      {activeTab === 'evaluations' && (
        <C3EvaluationsViewer projectId={projectId} />
      )}

      {/* Tab 2: Reports Viewer */}
      {activeTab === 'reports' && (
        <div className="space-y-4">
          {executions.length > 0 && (
            <div className="flex items-center gap-2 p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs">
              <span className="font-semibold text-slate-700 dark:text-slate-300">
                Select Tracked Execution:
              </span>
              <select
                value={selectedExecutionId}
                onChange={(e) => setSelectedExecutionId(e.target.value)}
                className="px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800 font-mono text-xs focus:outline-hidden"
              >
                {executions.map((x) => (
                  <option key={x.execution_id} value={x.execution_id}>
                    {x.execution_id} ({x.status}, {x.target_mode === 'LIVE_AUT' ? 'Live' : 'Demo'})
                  </option>
                ))}
              </select>
            </div>
          )}

          <C3ExecutionReportViewer
            projectId={projectId}
            executionId={currentExecId}
          />
        </div>
      )}

      {/* Tab 3: Advanced Research Protocols & Ablations */}
      {activeTab === 'research' && (
        <C3ResearchView />
      )}
    </div>
  );
};
