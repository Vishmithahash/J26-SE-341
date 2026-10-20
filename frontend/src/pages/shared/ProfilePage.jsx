import React, { useState } from 'react';
import { Mail, Shield, Calendar, CheckCircle, Save, AlertCircle, Check } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export const ProfilePage = () => {
  const { user, updateUserDisplay } = useAuth();

  const [name, setName] = useState(user?.name || '');
  const [isLoading, setIsLoading] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const initials = user?.name
    ? user.name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : 'QA';

  const handleUpdateName = async (e) => {
    e.preventDefault();
    setFeedback(null);

    const trimmed = name.trim();
    if (!trimmed) {
      setFeedback({ type: 'error', message: 'Name cannot be empty or whitespace only.' });
      return;
    }

    setIsLoading(true);
    try {
      await updateUserDisplay(trimmed);
      setFeedback({ type: 'success', message: 'Display name updated successfully.' });
    } catch (err) {
      setFeedback({ type: 'error', message: err.message || 'Failed to update name.' });
    } finally {
      setIsLoading(false);
    }
  };

  const formattedDate = user?.created_at_utc
    ? new Date(user.created_at_utc).toLocaleString(undefined, {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    : 'Unknown';

  return (
    <div className="max-w-4xl space-y-6">
      {/* Header */}
      <div className="pb-4 border-b border-slate-200 dark:border-slate-800">
        <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white leading-tight">
          User Profile
        </h1>
        <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
          Review authenticated credentials and manage your account display name.
        </p>
      </div>

      {feedback && (
        <div
          role="alert"
          className={`p-4 rounded-xl text-sm flex items-start gap-3 border ${
            feedback.type === 'success'
              ? 'bg-teal-50 dark:bg-teal-950/40 border-teal-200 dark:border-teal-800 text-teal-800 dark:text-teal-200'
              : 'bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200'
          }`}
        >
          {feedback.type === 'success' ? (
            <Check className="w-5 h-5 shrink-0 mt-0.5 text-teal-600 dark:text-teal-400" />
          ) : (
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-rose-600 dark:text-rose-400" />
          )}
          <span>{feedback.message}</span>
        </div>
      )}

      {/* Profile Overview Card */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col sm:flex-row items-start sm:items-center gap-6">
        <div className="flex items-center justify-center w-20 h-20 rounded-2xl bg-indigo-600 text-white font-bold text-2xl shadow-md shadow-indigo-600/20 shrink-0">
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-white truncate">
              {user?.name}
            </h2>
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold uppercase ${
                user?.role === 'ADMIN'
                  ? 'bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300'
                  : 'bg-teal-100 dark:bg-teal-900/50 text-teal-700 dark:text-teal-300'
              }`}
            >
              <Shield className="w-3 h-3" />
              {user?.role}
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40">
              <CheckCircle className="w-3 h-3" />
              Active
            </span>
          </div>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1 flex items-center gap-1.5 font-mono">
            <Mail className="w-3.5 h-3.5 text-slate-400" />
            {user?.email}
          </p>
          <p className="text-xs text-slate-400 dark:text-slate-500 mt-1 flex items-center gap-1.5">
            <Calendar className="w-3.5 h-3.5 text-slate-400" />
            Registered: {formattedDate}
          </p>
        </div>
      </div>

      {/* Edit Display Name Form */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
        <h3 className="text-base font-bold text-slate-900 dark:text-white mb-1">
          Edit Profile Information
        </h3>
        <p className="text-xs text-slate-500 dark:text-slate-400 mb-5">
          Update the display name associated with your authenticated identity.
        </p>

        <form onSubmit={handleUpdateName} className="space-y-4 max-w-lg">
          <div>
            <label
              htmlFor="profile-name"
              className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5"
            >
              Display Name
            </label>
            <input
              id="profile-name"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-transparent text-sm transition-all shadow-sm"
            />
          </div>

          <div>
            <label
              htmlFor="profile-email-readonly"
              className="block text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5"
            >
              Email Address (Read-only)
            </label>
            <input
              id="profile-email-readonly"
              type="email"
              disabled
              value={user?.email || ''}
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 text-slate-500 dark:text-slate-400 text-sm cursor-not-allowed"
            />
            <span className="block text-[11px] text-slate-400 mt-1">
              Account email is permanently linked to your authentication credentials.
            </span>
          </div>

          <div className="pt-2">
            <button
              type="submit"
              disabled={isLoading || name === user?.name}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-semibold text-sm transition-colors shadow-sm"
            >
              {isLoading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  <span>Save Changes</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
