import React from 'react';
import { Link } from 'react-router-dom';
import {
  UserCheck,
  Calendar,
  Sliders,
  Settings,
  ArrowRight,
  ListChecks,
  Workflow,
  RotateCcw,
  ShieldCheck,
  ExternalLink,
  CheckCircle,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { getModelPreference } from '../../services/modelPreference';
import { C3DashboardCard } from '../../features/c3/components/C3DashboardCard';

export const UserDashboard = () => {
  const { user } = useAuth();
  const modelPref = user ? getModelPreference(user.id) : null;

  const components = [
    {
      name: 'Explainable Tool-Call Correctness Testing',
      icon: ListChecks,
      path: '/app/tool-call-correctness',
    },
    {
      name: 'State-Aware Multi-Step Workflow Testing',
      icon: Workflow,
      path: '/app/workflow-testing',
    },
    {
      name: 'Robustness and Failure Recovery Testing',
      icon: RotateCcw,
      path: '/app/robustness-recovery',
    },
    {
      name: 'Policy-Aware Safety and Prompt-Injection Testing',
      icon: ShieldCheck,
      path: '/app/policy-safety',
    },
  ];

  const joinedDate = user?.created_at_utc
    ? new Date(user.created_at_utc).toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : 'Unknown';

  return (
    <div className="space-y-8">
      {/* Welcome Banner */}
      <div className="p-6 sm:p-8 rounded-2xl bg-gradient-to-r from-slate-900 to-teal-950 text-white shadow-sm border border-slate-800">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-teal-500/20 text-teal-300 border border-teal-500/30 text-xs font-semibold uppercase tracking-wider mb-3">
            <UserCheck className="w-3.5 h-3.5" />
            Standard User Workspace
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
            Welcome, {user?.name || 'User'}
          </h1>
          <p className="mt-2 text-sm text-slate-300 leading-relaxed">
            Your personal Quality Assurance Workspace. Review authenticated account details, set model preferences, and access framework testing domains.
          </p>
        </div>
      </div>

      {/* Account Overview & Preferences Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Card 1: Real Account Overview */}
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-2">
              <span className="text-xs font-semibold uppercase tracking-wider">Account Identity</span>
              <div className="p-2 rounded-xl bg-teal-50 dark:bg-teal-950/50 text-teal-600 dark:text-teal-400">
                <UserCheck className="w-5 h-5" />
              </div>
            </div>
            <div className="text-lg font-bold text-slate-900 dark:text-white truncate">
              {user?.name}
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 truncate mt-0.5">
              {user?.email}
            </p>
            <div className="mt-3 flex items-center gap-2">
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-teal-100 dark:bg-teal-900/50 text-teal-800 dark:text-teal-300">
                <CheckCircle className="w-3 h-3" />
                {user?.is_active ? 'Active Status' : 'Inactive'}
              </span>
              <span className="text-xs text-slate-400">Role: {user?.role}</span>
            </div>
          </div>
          <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800">
            <Link
              to="/app/profile"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-teal-600 dark:text-teal-400 hover:underline"
            >
              <span>Manage profile</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>

        {/* Card 2: Membership Date */}
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-2">
              <span className="text-xs font-semibold uppercase tracking-wider">Membership Date</span>
              <div className="p-2 rounded-xl bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400">
                <Calendar className="w-5 h-5" />
              </div>
            </div>
            <div className="text-base font-semibold text-slate-900 dark:text-white mt-1">
              {joinedDate}
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Initial account registration timestamp
            </p>
          </div>
          <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800">
            <Link
              to="/app/settings"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
            >
              <Settings className="w-3.5 h-3.5" />
              <span>Account settings</span>
            </Link>
          </div>
        </div>

        {/* Card 3: Model Preference */}
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-2">
              <span className="text-xs font-semibold uppercase tracking-wider">Model Preference</span>
              <div className="p-2 rounded-xl bg-teal-50 dark:bg-teal-950/50 text-teal-600 dark:text-teal-400">
                <Sliders className="w-5 h-5" />
              </div>
            </div>
            <div className="text-base font-semibold text-slate-900 dark:text-white mt-1 truncate">
              {modelPref && modelPref.modelId ? (
                modelPref.modelId
              ) : (
                <span className="text-slate-400 font-normal">No model selected</span>
              )}
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              {modelPref
                ? `Provider: ${modelPref.provider} (${modelPref.connectionType})`
                : 'Configure preferred framework model'}
            </p>
          </div>
          <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800">
            <Link
              to="/app/model-selection"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-teal-600 dark:text-teal-400 hover:underline"
            >
              <span>Model Selection</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </div>

      {/* Reserved Testing Components Section */}
      <div>
        <div className="mb-4">
          <h2 className="text-base font-bold text-slate-900 dark:text-white">
            Component Workspaces
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Testing components partition boundaries
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {components.map((comp) => {
            if (comp.name === 'Robustness and Failure Recovery Testing') {
              return <C3DashboardCard key={comp.name} role="USER" />;
            }
            const Icon = comp.icon;
            return (
              <div
                key={comp.name}
                className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 shrink-0">
                      <Icon className="w-5 h-5" />
                    </div>
                    <span className="text-[11px] font-medium text-slate-400 dark:text-slate-500 bg-slate-50 dark:bg-slate-800/60 px-2 py-0.5 rounded">
                      Reserved
                    </span>
                  </div>
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white leading-snug">
                    {comp.name}
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">
                    No content yet
                  </p>
                </div>

                <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800">
                  <Link
                    to={comp.path}
                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
                  >
                    <span>Open page</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
