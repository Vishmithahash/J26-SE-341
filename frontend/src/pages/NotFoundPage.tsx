import React from 'react';
import { Link } from 'react-router-dom';
import { FileQuestion, Home } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const NotFoundPage: React.FC = () => {
  const { user } = useAuth();
  const returnPath = user
    ? user.role === 'ADMIN'
      ? '/admin/dashboard'
      : '/app/dashboard'
    : '/sign-in';

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-slate-50 dark:bg-slate-950">
      <div className="w-full max-w-md p-8 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm text-center">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 mb-5">
          <FileQuestion className="w-7 h-7" />
        </div>

        <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">
          Page Not Found
        </h1>
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-6 leading-relaxed">
          The requested route does not exist in the QA Framework. Please verify the URL or return to your workspace.
        </p>

        <Link
          to={returnPath}
          className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm transition-colors shadow-sm"
        >
          <Home className="w-4 h-4" />
          <span>Return Home</span>
        </Link>
      </div>
    </div>
  );
};
