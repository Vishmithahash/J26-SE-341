import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Users,
  Shield,
  Sliders,
  UserCheck,
  Settings,
  ArrowRight,
  ListChecks,
  Workflow,
  RotateCcw,
  ShieldCheck,
  ExternalLink,
  Calendar,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import { getModelPreference } from '../../services/modelPreference';
import { C4DashboardCard } from '../../features/c4/components/dashboard/C4DashboardCard';

export const AdminDashboard = () => {
  const { user } = useAuth();
  const [userTotal, setUserTotal] = useState(null);
  const [recentUsers, setRecentUsers] = useState([]);
  const [isLoadingUsers, setIsLoadingUsers] = useState(true);

  const modelPref = user ? getModelPreference(user.id) : null;

  useEffect(() => {
    let mounted = true;
    api
      .getAdminUsers(5, 0)
      .then((res) => {
        if (mounted) {
          setUserTotal(res.total);
          setRecentUsers(res.items);
          setIsLoadingUsers(false);
        }
      })
      .catch(() => {
        if (mounted) {
          setIsLoadingUsers(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, []);

  const components = [
    {
      name: 'Explainable Tool-Call Correctness Testing',
      icon: ListChecks,
      path: '/admin/tool-call-correctness',
    },
    {
      name: 'State-Aware Multi-Step Workflow Testing',
      icon: Workflow,
      path: '/admin/workflow-testing',
    },
    {
      name: 'Robustness and Failure Recovery Testing',
      icon: RotateCcw,
      path: '/admin/robustness-recovery',
    },
    {
      name: 'Policy-Aware Safety and Prompt-Injection Testing',
      icon: ShieldCheck,
      path: '/admin/policy-safety',
    },
  ];

  return (
    <div className="space-y-8">
      {/* Welcome Banner */}
      <div className="p-6 sm:p-8 rounded-2xl bg-gradient-to-r from-slate-900 to-indigo-950 text-white shadow-sm border border-slate-800">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-semibold uppercase tracking-wider mb-3">
            <Shield className="w-3.5 h-3.5" />
            Administrator Console
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
            Welcome, {user?.name || 'Administrator'}
          </h1>
          <p className="mt-2 text-sm text-slate-300 leading-relaxed">
            System overview and administration workspace for the QA Framework. Manage user accounts, configure workspace preferences, and access framework testing domains.
          </p>
        </div>
      </div>

      {/* Overview Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Card 1: Registered Accounts */}
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-2">
              <span className="text-xs font-semibold uppercase tracking-wider">Registered Accounts</span>
              <div className="p-2 rounded-xl bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400">
                <Users className="w-5 h-5" />
              </div>
            </div>
            <div className="text-3xl font-bold text-slate-900 dark:text-white mt-1">
              {isLoadingUsers ? (
                <div className="h-9 w-16 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
              ) : userTotal !== null ? (
                userTotal
              ) : (
                <span className="text-base text-slate-400 font-normal">Unavailable</span>
              )}
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Total active users in database
            </p>
          </div>
          <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800">
            <Link
              to="/admin/users"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
            >
              <span>Manage all accounts</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>

        {/* Card 2: Model Preference */}
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-2">
              <span className="text-xs font-semibold uppercase tracking-wider">Model Preference</span>
              <div className="p-2 rounded-xl bg-teal-50 dark:bg-teal-950/50 text-teal-600 dark:text-teal-400">
                <Sliders className="w-5 h-5" />
              </div>
            </div>
            <div className="text-base font-semibold text-slate-900 dark:text-white mt-2 truncate">
              {modelPref && modelPref.modelId ? (
                <span>{modelPref.modelId}</span>
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
              to="/admin/model-selection"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-teal-600 dark:text-teal-400 hover:underline"
            >
              <span>Model Selection</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>

        {/* Card 3: Account & Quick Navigation */}
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-2">
              <span className="text-xs font-semibold uppercase tracking-wider">Account Overview</span>
              <div className="p-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                <UserCheck className="w-5 h-5" />
              </div>
            </div>
            <div className="text-base font-semibold text-slate-900 dark:text-white truncate">
              {user?.name}
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 truncate mt-0.5">
              {user?.email}
            </p>
          </div>
          <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
            <Link
              to="/admin/profile"
              className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
            >
              <span>Profile</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
            <Link
              to="/admin/settings"
              className="inline-flex items-center gap-1 text-xs font-semibold text-slate-600 dark:text-slate-400 hover:underline"
            >
              <Settings className="w-3.5 h-3.5" />
              <span>Settings</span>
            </Link>
          </div>
        </div>
      </div>

      {/* Compact Account List Preview */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="flex items-center justify-between pb-4 mb-4 border-b border-slate-100 dark:border-slate-800">
          <div>
            <h2 className="text-base font-bold text-slate-900 dark:text-white">
              Recent Accounts Preview
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Latest registrations from system user catalogue
            </p>
          </div>
          <Link
            to="/admin/users"
            className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline inline-flex items-center gap-1"
          >
            <span>View all users</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {isLoadingUsers ? (
          <div className="space-y-3 py-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-10 bg-slate-100 dark:bg-slate-800 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : recentUsers.length === 0 ? (
          <p className="text-xs text-slate-400 py-4 text-center">No accounts found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-100 dark:border-slate-800 text-slate-500 dark:text-slate-400">
                  <th className="pb-2.5 font-semibold">User</th>
                  <th className="pb-2.5 font-semibold">Email</th>
                  <th className="pb-2.5 font-semibold">Role</th>
                  <th className="pb-2.5 font-semibold">Registration Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {recentUsers.map((u) => (
                  <tr key={u.id} className="text-slate-700 dark:text-slate-300">
                    <td className="py-2.5 font-medium text-slate-900 dark:text-white">{u.name}</td>
                    <td className="py-2.5 text-slate-500 dark:text-slate-400">{u.email}</td>
                    <td className="py-2.5">
                      <span
                        className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${
                          u.role === 'ADMIN'
                            ? 'bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300'
                            : 'bg-teal-100 dark:bg-teal-900/50 text-teal-700 dark:text-teal-300'
                        }`}
                      >
                        {u.role}
                      </span>
                    </td>
                    <td className="py-2.5 text-slate-500 dark:text-slate-400">
                      <span className="inline-flex items-center gap-1">
                        <Calendar className="w-3 h-3 text-slate-400" />
                        {new Date(u.created_at_utc).toLocaleDateString()}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
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
            if (comp.name === 'Policy-Aware Safety and Prompt-Injection Testing') {
              return <C4DashboardCard key={comp.name} basePath="/admin" />;
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
