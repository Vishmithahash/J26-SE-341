import React, { useEffect, useState } from 'react';
import {
  Users,
  Shield,
  Calendar,
  CheckCircle,
  XCircle,
  ChevronLeft,
  ChevronRight,
  RotateCw,
  AlertCircle,
} from 'lucide-react';
import { api } from '../../services/api';
import type { User } from '../../types/auth';

const PAGE_SIZE = 10;

export const UsersPage: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [offset, setOffset] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchUsers = async (currentOffset: number) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await api.getAdminUsers(PAGE_SIZE, currentOffset);
      setUsers(res.items);
      setTotal(res.total);
      setOffset(res.offset);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to load user accounts.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers(offset);
  }, [offset]);

  const totalPages = Math.ceil(total / PAGE_SIZE) || 1;
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  const handlePrevPage = () => {
    if (offset - PAGE_SIZE >= 0) {
      setOffset(offset - PAGE_SIZE);
    }
  };

  const handleNextPage = () => {
    if (offset + PAGE_SIZE < total) {
      setOffset(offset + PAGE_SIZE);
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white leading-tight">
            Registered Users
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
            Read-only registry of framework user accounts ({total} total)
          </p>
        </div>

        <button
          onClick={() => fetchUsers(offset)}
          disabled={isLoading}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-300 transition-colors shadow-sm disabled:opacity-50"
        >
          <RotateCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Error state with retry */}
      {errorMessage && (
        <div
          role="alert"
          className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-sm flex items-start justify-between gap-3"
        >
          <div className="flex items-start gap-2.5">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={() => fetchUsers(offset)}
            className="text-xs font-bold underline hover:no-underline shrink-0"
          >
            Retry
          </button>
        </div>
      )}

      {/* Table Container */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center space-y-3">
            <div className="w-8 h-8 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-xs text-slate-500">Loading user registry...</p>
          </div>
        ) : users.length === 0 ? (
          <div className="p-12 text-center space-y-2">
            <Users className="w-10 h-10 text-slate-400 mx-auto" />
            <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
              No registered accounts found
            </p>
            <p className="text-xs text-slate-400">
              Accounts will appear here once registered.
            </p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="bg-slate-50/75 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-800 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    <th className="py-3 px-4">Name</th>
                    <th className="py-3 px-4">Email</th>
                    <th className="py-3 px-4">Role</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Registration Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {users.map((u) => (
                    <tr
                      key={u.id}
                      className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 text-slate-700 dark:text-slate-300 transition-colors"
                    >
                      <td className="py-3 px-4 font-semibold text-slate-900 dark:text-white">
                        {u.name}
                      </td>
                      <td className="py-3 px-4 text-slate-500 dark:text-slate-400 font-mono text-xs">
                        {u.email}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wide ${
                            u.role === 'ADMIN'
                              ? 'bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300'
                              : 'bg-teal-100 dark:bg-teal-900/50 text-teal-700 dark:text-teal-300'
                          }`}
                        >
                          <Shield className="w-3 h-3" />
                          {u.role}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                            u.is_active
                              ? 'text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40'
                              : 'text-slate-500 bg-slate-100 dark:bg-slate-800'
                          }`}
                        >
                          {u.is_active ? (
                            <>
                              <CheckCircle className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                              Active
                            </>
                          ) : (
                            <>
                              <XCircle className="w-3 h-3" />
                              Inactive
                            </>
                          )}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-xs text-slate-500 dark:text-slate-400">
                        <span className="inline-flex items-center gap-1.5">
                          <Calendar className="w-3.5 h-3.5 text-slate-400" />
                          {new Date(u.created_at_utc).toLocaleString(undefined, {
                            year: 'numeric',
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200 dark:border-slate-800 text-xs text-slate-500 dark:text-slate-400 bg-slate-50/50 dark:bg-slate-800/30">
              <span>
                Showing {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total} users
              </span>

              <div className="flex items-center gap-2">
                <button
                  onClick={handlePrevPage}
                  disabled={offset === 0}
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                  aria-label="Previous page"
                >
                  <ChevronLeft className="w-4 h-4" />
                  <span>Prev</span>
                </button>
                <span className="px-2 font-medium">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  onClick={handleNextPage}
                  disabled={offset + PAGE_SIZE >= total}
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                  aria-label="Next page"
                >
                  <span>Next</span>
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
