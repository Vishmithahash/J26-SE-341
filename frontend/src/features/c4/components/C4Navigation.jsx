/**
 * Component 4 (C4) - Navigation Sub-tab Bar
 * Navigation across all C4 lifecycle phases, clearly distinguishing implemented from pending phases.
 */

import React from 'react';
import {
  FileText,
  Boxes,
  CheckSquare,
  PlayCircle,
  GitCompare,
  BarChart3,
} from 'lucide-react';
import { C4_WORKSPACE_TABS } from '../api/types.js';

export function C4Navigation({ activeTab, onSelectTab }) {
  const tabs = [
    {
      id: C4_WORKSPACE_TABS.POLICY_PREPARATION,
      label: 'Policy Preparation',
      phase: 'Phase 1',
      icon: FileText,
      status: 'Implemented',
      isImplemented: true,
    },
    {
      id: C4_WORKSPACE_TABS.DOMAIN_BINDINGS,
      label: 'Domain Bindings & Onboarding',
      phase: 'Phase 1',
      icon: Boxes,
      status: 'Implemented',
      isImplemented: true,
    },
    {
      id: C4_WORKSPACE_TABS.TEST_CASES,
      label: 'Test Cases',
      phase: 'Phase 2',
      icon: CheckSquare,
      status: 'Implemented',
      isImplemented: true,
    },
    {
      id: C4_WORKSPACE_TABS.RUNS_AND_FINDINGS,
      label: 'Runs & Findings',
      phase: 'Phase 2',
      icon: PlayCircle,
      status: 'Implemented',
      isImplemented: true,
    },
    {
      id: C4_WORKSPACE_TABS.POLICY_CHANGES,
      label: 'Policy Changes',
      phase: 'Phase 3',
      icon: GitCompare,
      status: 'Implemented',
      isImplemented: true,
    },
    {
      id: C4_WORKSPACE_TABS.EVALUATION_AND_REPORTS,
      label: 'Evaluation & Reports',
      phase: 'Phase 3',
      icon: BarChart3,
      status: 'Implemented',
      isImplemented: true,
    },
  ];

  return (
    <div className="border-b border-slate-200 dark:border-slate-800 mb-6 overflow-x-auto scrollbar-none">
      <nav className="flex space-x-2 min-w-max pb-1" aria-label="Component 4 Lifecycle Tabs">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => onSelectTab(tab.id)}
              className={`group flex items-center gap-2.5 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-150 relative ${
                isActive
                  ? 'bg-indigo-600 text-white shadow-sm font-semibold'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800/60'
              }`}
              aria-current={isActive ? 'page' : undefined}
            >
              <Icon
                className={`w-4 h-4 shrink-0 ${
                  isActive
                    ? 'text-white'
                    : 'text-slate-400 dark:text-slate-500 group-hover:text-slate-600 dark:group-hover:text-slate-300'
                }`}
              />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </nav>
    </div>
  );
}
