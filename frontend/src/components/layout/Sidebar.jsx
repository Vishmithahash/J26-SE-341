import React, { useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  ListChecks,
  Workflow,
  RotateCcw,
  ShieldCheck,
  Sliders,
  UserCheck,
  Settings,
  ChevronLeft,
  ChevronRight,
  Shield,
  Layers,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export const Sidebar = ({
  isCollapsed,
  setIsCollapsed,
  isMobileOpen,
  setIsMobileOpen,
}) => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'ADMIN';
  const basePath = isAdmin ? '/admin' : '/app';

  // Close mobile drawer on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isMobileOpen) {
        setIsMobileOpen(false);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isMobileOpen, setIsMobileOpen]);

  const navItems = [
    {
      label: 'Dashboard',
      path: `${basePath}/dashboard`,
      icon: LayoutDashboard,
    },
    ...(isAdmin
      ? [
          {
            label: 'Users',
            path: '/admin/users',
            icon: Users,
          },
        ]
      : []),
    {
      section: 'Testing Components',
    },
    {
      label: 'Explainable Tool-Call Correctness Testing',
      path: `${basePath}/tool-call-correctness`,
      icon: ListChecks,
    },
    {
      label: 'State-Aware Multi-Step Workflow Testing',
      path: `${basePath}/workflow-testing`,
      icon: Workflow,
    },
    {
      label: 'Robustness and Failure Recovery Testing',
      path: `${basePath}/robustness-recovery`,
      icon: RotateCcw,
    },
    {
      label: 'Policy-Aware Safety and Prompt-Injection Testing',
      path: `${basePath}/policy-safety`,
      icon: ShieldCheck,
    },
    {
      section: 'Workspace & System',
    },
    {
      label: 'Model Selection',
      path: `${basePath}/model-selection`,
      icon: Sliders,
    },
    {
      label: 'Profile',
      path: `${basePath}/profile`,
      icon: UserCheck,
    },
    {
      label: 'Settings',
      path: `${basePath}/settings`,
      icon: Settings,
    },
  ];

  const sidebarContent = (
    <div className="flex flex-col h-full bg-[#0F172A] text-slate-100 select-none">
      {/* Brand Header */}
      <div className="flex items-center justify-between px-4 py-5 border-b border-slate-800">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-600 text-white shrink-0 shadow-sm shadow-indigo-500/20">
            <Layers className="w-5 h-5 text-white" />
          </div>
          {!isCollapsed && (
            <div className="min-w-0">
              <h1 className="text-base font-semibold tracking-tight text-white leading-tight truncate">
                QA Framework
              </h1>
              <p className="text-xs text-slate-400 truncate">
                Quality Assurance Workspace
              </p>
            </div>
          )}
        </div>

        {/* Desktop collapse toggle */}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="hidden md:flex items-center justify-center w-7 h-7 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Role Indicator Badge */}
      {!isCollapsed && (
        <div className="px-4 py-2.5 mx-3 my-2 rounded-lg bg-slate-800/60 border border-slate-700/50 flex items-center justify-between">
          <span className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
            Active Role
          </span>
          <span
            className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-semibold tracking-wide ${
              isAdmin
                ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
                : 'bg-teal-500/20 text-teal-300 border border-teal-500/30'
            }`}
          >
            <Shield className="w-3 h-3" />
            {isAdmin ? 'Administrator' : 'Standard User'}
          </span>
        </div>
      )}

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-3 space-y-1.5 overflow-y-auto overflow-x-hidden" aria-label="Main Navigation">
        {navItems.map((item, idx) => {
          if ('section' in item) {
            if (isCollapsed) {
              return <div key={idx} className="my-2 border-t border-slate-800" />;
            }
            return (
              <div
                key={idx}
                className="px-3 pt-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400"
              >
                {item.section}
              </div>
            );
          }

          const IconComponent = item.icon;

          return (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={() => setIsMobileOpen(false)}
              className={({ isActive }) =>
                `group relative flex items-start gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30 font-semibold'
                    : 'text-slate-300 hover:text-white hover:bg-slate-800/80'
                } ${isCollapsed ? 'justify-center px-2' : ''}`
              }
              title={isCollapsed ? item.label : undefined}
            >
              <IconComponent
                className={`w-5 h-5 shrink-0 mt-0.5 transition-colors ${
                  isCollapsed ? '' : ''
                }`}
              />
              {!isCollapsed && (
                <span className="leading-snug break-words text-left flex-1">
                  {item.label}
                </span>
              )}

              {/* Accessible tooltip for collapsed state */}
              {isCollapsed && (
                <div className="absolute left-full ml-3 px-3 py-1.5 bg-slate-900 text-white text-xs rounded-md shadow-lg opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto transition-opacity z-50 whitespace-nowrap border border-slate-700">
                  {item.label}
                </div>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Bottom info section */}
      {!isCollapsed && (
        <div className="px-4 py-3 border-t border-slate-800 text-[11px] text-slate-400 flex items-center justify-between">
          <span>Framework Shell v0.1</span>
          <span className="inline-block w-2 h-2 rounded-full bg-teal-400 animate-pulse" title="System operational" />
        </div>
      )}
    </div>
  );

  return (
    <>
      {/* Desktop Persistent Sidebar */}
      <aside
        className={`hidden md:flex flex-col shrink-0 border-r border-slate-800 transition-all duration-200 z-20 ${
          isCollapsed ? 'w-20' : 'w-64 lg:w-72'
        }`}
      >
        {sidebarContent}
      </aside>

      {/* Mobile Backdrop & Drawer */}
      {isMobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          <div
            className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm transition-opacity"
            onClick={() => setIsMobileOpen(false)}
            aria-hidden="true"
          />
          <div className="relative flex flex-col w-72 max-w-[85vw] h-full shadow-2xl z-10 animate-in slide-in-from-left duration-200">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  );
};
