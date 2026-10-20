import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Sun,
  Moon,
  Monitor,
  Lock,
  Eye,
  EyeOff,
  AlertCircle,
  CheckCircle2,
  Sliders,
  UserCheck,
  ArrowRight,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';
import { api } from '../../services/api';

// Count Unicode code points (matching Python string length for supplementary characters/emojis)
const countCodePoints = (str: string): number => Array.from(str).length;

export const SettingsPage: React.FC = () => {
  const { user, logout } = useAuth();
  const { mode, setMode, density, setDensity } = useTheme();
  const navigate = useNavigate();

  const isAdmin = user?.role === 'ADMIN';
  const basePath = isAdmin ? '/admin' : '/app';

  // Password change state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isChangingPassword) return;
    setPasswordError(null);

    if (!currentPassword) {
      setPasswordError('Please provide your current password.');
      return;
    }

    const newPasswordLength = countCodePoints(newPassword);

    if (newPasswordLength < 8) {
      setPasswordError('New password must be at least 8 characters.');
      return;
    }

    if (newPasswordLength > 128) {
      setPasswordError('New password cannot exceed 128 characters.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setPasswordError('New passwords do not match.');
      return;
    }

    setIsChangingPassword(true);
    try {
      await api.changePassword(currentPassword, newPassword);

      // Clear password fields immediately
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');

      // Clear the current frontend session after success and require sign-in again
      logout();
      navigate('/sign-in', {
        state: { message: 'Password updated successfully. Please sign in with your new password.' },
        replace: true,
      });
    } catch (err: any) {
      setPasswordError(err.message || 'Failed to update password. Please check your current password.');
    } finally {
      setIsChangingPassword(false);
    }
  };

  return (
    <div className="max-w-4xl space-y-8">
      {/* Page Header */}
      <div className="pb-4 border-b border-slate-200 dark:border-slate-800">
        <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white leading-tight">
          Settings
        </h1>
        <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
          Manage local display preferences and server-backed account security credentials.
        </p>
      </div>

      {/* Section 1: Appearance & Display (Browser-Saved) */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-bold text-slate-900 dark:text-white">
              Interface Appearance
            </h2>
            <span className="text-[11px] font-medium text-slate-500 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded">
              Browser Storage
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            These styling preferences are stored locally in your browser.
          </p>
        </div>

        {/* Theme mode selection */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-3">
            Theme Mode
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-lg">
            <button
              type="button"
              onClick={() => setMode('light')}
              className={`flex items-center justify-center gap-2 p-3 rounded-xl border text-sm font-semibold transition-all ${
                mode === 'light'
                  ? 'border-indigo-600 bg-indigo-50/50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 ring-2 ring-indigo-600/20'
                  : 'border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/60 text-slate-700 dark:text-slate-300'
              }`}
            >
              <Sun className="w-4 h-4 text-amber-500" />
              <span>Light</span>
            </button>

            <button
              type="button"
              onClick={() => setMode('dark')}
              className={`flex items-center justify-center gap-2 p-3 rounded-xl border text-sm font-semibold transition-all ${
                mode === 'dark'
                  ? 'border-indigo-600 bg-indigo-50/50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 ring-2 ring-indigo-600/20'
                  : 'border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/60 text-slate-700 dark:text-slate-300'
              }`}
            >
              <Moon className="w-4 h-4 text-indigo-400" />
              <span>Dark</span>
            </button>

            <button
              type="button"
              onClick={() => setMode('system')}
              className={`flex items-center justify-center gap-2 p-3 rounded-xl border text-sm font-semibold transition-all ${
                mode === 'system'
                  ? 'border-indigo-600 bg-indigo-50/50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 ring-2 ring-indigo-600/20'
                  : 'border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/60 text-slate-700 dark:text-slate-300'
              }`}
            >
              <Monitor className="w-4 h-4 text-teal-500" />
              <span>System</span>
            </button>
          </div>
        </div>

        {/* Display Density */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-3">
            Display Density
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg">
            <button
              type="button"
              onClick={() => setDensity('comfortable')}
              className={`flex items-center justify-between p-3.5 rounded-xl border text-left transition-all ${
                density === 'comfortable'
                  ? 'border-indigo-600 bg-indigo-50/50 dark:bg-indigo-950/40 text-indigo-900 dark:text-indigo-200 ring-2 ring-indigo-600/20'
                  : 'border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/60 text-slate-700 dark:text-slate-300'
              }`}
            >
              <div>
                <p className="text-sm font-semibold">Comfortable</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">Generous padding and spacing</p>
              </div>
              {density === 'comfortable' && <CheckCircle2 className="w-4 h-4 text-indigo-600 shrink-0" />}
            </button>

            <button
              type="button"
              onClick={() => setDensity('compact')}
              className={`flex items-center justify-between p-3.5 rounded-xl border text-left transition-all ${
                density === 'compact'
                  ? 'border-indigo-600 bg-indigo-50/50 dark:bg-indigo-950/40 text-indigo-900 dark:text-indigo-200 ring-2 ring-indigo-600/20'
                  : 'border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/60 text-slate-700 dark:text-slate-300'
              }`}
            >
              <div>
                <p className="text-sm font-semibold">Compact</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">Dense layout for compact viewports</p>
              </div>
              {density === 'compact' && <CheckCircle2 className="w-4 h-4 text-indigo-600 shrink-0" />}
            </button>
          </div>
        </div>
      </div>

      {/* Section 2: Account Security (Server-Saved Password Change) */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-bold text-slate-900 dark:text-white">
              Account Security
            </h2>
            <span className="text-[11px] font-medium text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/60 px-2 py-0.5 rounded border border-indigo-200 dark:border-indigo-800">
              Server Verified
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Update your account password. Requires verification of your current password. Passwords must be 15–128 characters.
          </p>
        </div>

        {passwordError && (
          <div
            id="password-change-error"
            role="alert"
            className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-sm flex items-start gap-3"
          >
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-rose-600 dark:text-rose-400" />
            <span>{passwordError}</span>
          </div>
        )}

        <form onSubmit={handlePasswordChange} className="space-y-4 max-w-lg" noValidate>
          <div>
            <label
              htmlFor="current-password"
              className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5"
            >
              Current Password
            </label>
            <div className="relative">
              <input
                id="current-password"
                type={showCurrent ? 'text' : 'password'}
                name="currentPassword"
                autoComplete="current-password"
                required
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Enter current password"
                aria-describedby={passwordError ? 'password-change-error' : undefined}
                className="w-full pl-3.5 pr-11 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-transparent text-sm transition-all shadow-sm"
              />
              <button
                type="button"
                onClick={() => setShowCurrent(!showCurrent)}
                className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 focus:outline-none"
                aria-label={showCurrent ? 'Hide current password' : 'Show current password'}
              >
                {showCurrent ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label
                htmlFor="new-password"
                className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300"
              >
                New Password
              </label>
              <span className="text-[11px] text-slate-500 dark:text-slate-400">
                Min 8 characters
              </span>
            </div>
            <div className="relative">
              <input
                id="new-password"
                type={showNew ? 'text' : 'password'}
                name="newPassword"
                autoComplete="new-password"
                required
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Minimum 8 characters"
                className="w-full pl-3.5 pr-11 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-transparent text-sm transition-all shadow-sm"
              />
              <button
                type="button"
                onClick={() => setShowNew(!showNew)}
                className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 focus:outline-none"
                aria-label={showNew ? 'Hide new password' : 'Show new password'}
              >
                {showNew ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <div>
            <label
              htmlFor="confirm-new-password"
              className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5"
            >
              Confirm New Password
            </label>
            <div className="relative">
              <input
                id="confirm-new-password"
                type={showConfirm ? 'text' : 'password'}
                name="confirmPassword"
                autoComplete="new-password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter new password"
                className="w-full pl-3.5 pr-11 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-transparent text-sm transition-all shadow-sm"
              />
              <button
                type="button"
                onClick={() => setShowConfirm(!showConfirm)}
                className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 focus:outline-none"
                aria-label={showConfirm ? 'Hide confirm password' : 'Show confirm password'}
              >
                {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <div className="pt-2">
            <button
              type="submit"
              disabled={isChangingPassword}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-semibold text-sm transition-colors shadow-sm"
            >
              {isChangingPassword ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Updating password...</span>
                </>
              ) : (
                <>
                  <Lock className="w-4 h-4" />
                  <span>Update Password</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Section 3: Related Navigation Links */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
        <h2 className="text-base font-bold text-slate-900 dark:text-white mb-1">
          Related Preferences & Details
        </h2>
        <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
          Quick links to profile identity and framework model settings.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Link
            to={`${basePath}/profile`}
            className="flex items-center justify-between p-4 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/60 transition-colors group"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400">
                <UserCheck className="w-5 h-5" />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-900 dark:text-white">Profile Identity</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">View role and display name</p>
              </div>
            </div>
            <ArrowRight className="w-4 h-4 text-slate-400 group-hover:translate-x-0.5 transition-transform" />
          </Link>

          <Link
            to={`${basePath}/model-selection`}
            className="flex items-center justify-between p-4 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/60 transition-colors group"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-teal-50 dark:bg-teal-950/50 text-teal-600 dark:text-teal-400">
                <Sliders className="w-5 h-5" />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-900 dark:text-white">Model Selection</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">Configure framework-side model preference</p>
              </div>
            </div>
            <ArrowRight className="w-4 h-4 text-slate-400 group-hover:translate-x-0.5 transition-transform" />
          </Link>
        </div>
      </div>
    </div>
  );
};
