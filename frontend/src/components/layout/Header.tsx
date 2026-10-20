import React, { useState, useRef, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  Menu,
  Sun,
  Moon,
  Monitor,
  User as UserIcon,
  Settings,
  LogOut,
  ChevronDown,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';

interface HeaderProps {
  onOpenMobileNav: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onOpenMobileNav }) => {
  const { user, logout } = useAuth();
  const { mode, setMode } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();

  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isThemeOpen, setIsThemeOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const themeRef = useRef<HTMLDivElement>(null);

  const isAdmin = user?.role === 'ADMIN';
  const basePath = isAdmin ? '/admin' : '/app';

  // Close dropdowns on outside click or Escape key
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsMenuOpen(false);
      }
      if (themeRef.current && !themeRef.current.contains(event.target as Node)) {
        setIsThemeOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsMenuOpen(false);
        setIsThemeOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  const handleLogout = () => {
    setIsMenuOpen(false);
    logout();
    navigate('/sign-in', { replace: true });
  };

  // Derive readable breadcrumb and page title from location
  const getPageInfo = () => {
    const path = location.pathname;
    if (path.includes('/dashboard')) return { title: 'Dashboard', crumb: 'Overview' };
    if (path.includes('/users')) return { title: 'Registered Users', crumb: 'Administration' };
    if (path.includes('/tool-call-correctness'))
      return { title: 'Explainable Tool-Call Correctness Testing', crumb: 'Components' };
    if (path.includes('/workflow-testing'))
      return { title: 'State-Aware Multi-Step Workflow Testing', crumb: 'Components' };
    if (path.includes('/robustness-recovery'))
      return { title: 'Robustness and Failure Recovery Testing', crumb: 'Components' };
    if (path.includes('/policy-safety'))
      return { title: 'Policy-Aware Safety and Prompt-Injection Testing', crumb: 'Components' };
    if (path.includes('/model-selection'))
      return { title: 'Model Selection', crumb: 'Preferences' };
    if (path.includes('/profile')) return { title: 'User Profile', crumb: 'Account' };
    if (path.includes('/settings')) return { title: 'Settings', crumb: 'Preferences' };
    return { title: 'Workspace', crumb: 'QA Framework' };
  };

  const pageInfo = getPageInfo();

  // Get user initials
  const initials = user?.name
    ? user.name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : 'QA';

  return (
    <header className="sticky top-0 z-10 flex items-center justify-between h-16 px-4 md:px-6 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 transition-colors">
      {/* Left: Mobile hamburger & breadcrumbs */}
      <div className="flex items-center gap-3">
        <button
          onClick={onOpenMobileNav}
          className="p-2 -ml-2 rounded-lg md:hidden text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
          aria-label="Open navigation menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="flex flex-col">
          <div className="flex items-center gap-1.5 text-xs font-medium text-slate-400 dark:text-slate-400">
            <span>{isAdmin ? 'Admin Portal' : 'User Workspace'}</span>
            <span>/</span>
            <span className="text-slate-600 dark:text-slate-300">{pageInfo.crumb}</span>
          </div>
          <h2 className="text-sm md:text-base font-semibold text-slate-900 dark:text-white truncate max-w-[220px] sm:max-w-md lg:max-w-xl">
            {pageInfo.title}
          </h2>
        </div>
      </div>

      {/* Right: Theme Toggle and Account Menu */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Theme mode dropdown */}
        <div className="relative" ref={themeRef}>
          <button
            onClick={() => setIsThemeOpen(!isThemeOpen)}
            className="flex items-center justify-center w-9 h-9 rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700/60 transition-colors"
            title="Appearance mode"
            aria-label="Appearance mode"
          >
            {mode === 'light' ? (
              <Sun className="w-4 h-4 text-amber-500" />
            ) : mode === 'dark' ? (
              <Moon className="w-4 h-4 text-indigo-400" />
            ) : (
              <Monitor className="w-4 h-4 text-teal-500" />
            )}
          </button>

          {isThemeOpen && (
            <div className="absolute right-0 mt-2 w-36 py-1 bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 text-sm z-30">
              <button
                onClick={() => {
                  setMode('light');
                  setIsThemeOpen(false);
                }}
                className={`w-full flex items-center gap-2.5 px-3 py-2 text-left hover:bg-slate-50 dark:hover:bg-slate-700/50 ${
                  mode === 'light' ? 'text-indigo-600 dark:text-indigo-400 font-semibold' : 'text-slate-700 dark:text-slate-200'
                }`}
              >
                <Sun className="w-4 h-4 text-amber-500" />
                <span>Light</span>
              </button>
              <button
                onClick={() => {
                  setMode('dark');
                  setIsThemeOpen(false);
                }}
                className={`w-full flex items-center gap-2.5 px-3 py-2 text-left hover:bg-slate-50 dark:hover:bg-slate-700/50 ${
                  mode === 'dark' ? 'text-indigo-600 dark:text-indigo-400 font-semibold' : 'text-slate-700 dark:text-slate-200'
                }`}
              >
                <Moon className="w-4 h-4 text-indigo-400" />
                <span>Dark</span>
              </button>
              <button
                onClick={() => {
                  setMode('system');
                  setIsThemeOpen(false);
                }}
                className={`w-full flex items-center gap-2.5 px-3 py-2 text-left hover:bg-slate-50 dark:hover:bg-slate-700/50 ${
                  mode === 'system' ? 'text-indigo-600 dark:text-indigo-400 font-semibold' : 'text-slate-700 dark:text-slate-200'
                }`}
              >
                <Monitor className="w-4 h-4 text-teal-500" />
                <span>System</span>
              </button>
            </div>
          )}
        </div>

        {/* Account Menu */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            className="flex items-center gap-2.5 p-1 sm:px-2.5 sm:py-1.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 border border-transparent hover:border-slate-200 dark:hover:border-slate-700 transition-colors"
            aria-label="User account menu"
            aria-expanded={isMenuOpen}
          >
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-indigo-600 text-white font-semibold text-xs shadow-sm">
              {initials}
            </div>
            <div className="hidden sm:flex flex-col text-left">
              <span className="text-xs font-semibold text-slate-900 dark:text-slate-100 leading-tight">
                {user?.name || 'User'}
              </span>
              <span className="text-[10px] text-slate-400 leading-tight truncate max-w-[120px]">
                {user?.email}
              </span>
            </div>
            <ChevronDown className="hidden sm:block w-3.5 h-3.5 text-slate-400" />
          </button>

          {isMenuOpen && (
            <div className="absolute right-0 mt-2 w-56 py-1.5 bg-white dark:bg-slate-800 rounded-xl shadow-xl border border-slate-200 dark:border-slate-700 text-sm z-30">
              <div className="px-4 py-2 border-b border-slate-100 dark:border-slate-700">
                <p className="text-xs font-semibold text-slate-900 dark:text-white truncate">
                  {user?.name}
                </p>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                  {user?.email}
                </p>
                <div className="mt-1.5">
                  <span
                    className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${
                      isAdmin
                        ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/50 dark:text-indigo-300'
                        : 'bg-teal-100 text-teal-700 dark:bg-teal-900/50 dark:text-teal-300'
                    }`}
                  >
                    {user?.role}
                  </span>
                </div>
              </div>

              <div className="py-1">
                <Link
                  to={`${basePath}/profile`}
                  onClick={() => setIsMenuOpen(false)}
                  className="flex items-center gap-2 px-4 py-2 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700/50"
                >
                  <UserIcon className="w-4 h-4 text-slate-400" />
                  <span>Profile</span>
                </Link>
                <Link
                  to={`${basePath}/settings`}
                  onClick={() => setIsMenuOpen(false)}
                  className="flex items-center gap-2 px-4 py-2 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700/50"
                >
                  <Settings className="w-4 h-4 text-slate-400" />
                  <span>Settings</span>
                </Link>
              </div>

              <div className="pt-1 border-t border-slate-100 dark:border-slate-700">
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 px-4 py-2 text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 text-left font-medium"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Sign out</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
