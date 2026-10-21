import React, { useState } from 'react';
import {
  Workflow,
  Search,
  Plus,
  CheckCircle2,
  Clock,
  ShieldCheck,
  Hash,
  ChevronRight,
} from 'lucide-react';

export const ModelListView = ({
  models = [],
  selectedModelId,
  selectedVersion,
  onSelectModel,
  onOpenPreparation,
  isLoading = false,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');

  const filteredModels = models.filter((m) => {
    const matchesSearch =
      m.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      m.model_id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      m.content_hash?.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStatus =
      statusFilter === 'ALL' || m.lifecycle_status === statusFilter;

    return matchesSearch && matchesStatus;
  });

  return (
    <div className="bg-white dark:bg-[#131A26] rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden flex flex-col">
      {/* Header & Controls */}
      <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-50/50 dark:bg-slate-900/30">
        <div className="flex items-center gap-2">
          <Workflow className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
          <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
            Reference Workflow Models ({models.length})
          </h2>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Search */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search by name, ID, or hash..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500 w-48 sm:w-64"
            />
          </div>

          {/* Lifecycle Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-2.5 py-1.5 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:ring-2 focus:ring-indigo-500"
          >
            <option value="ALL">All Lifecycles</option>
            <option value="DRAFT">DRAFT</option>
            <option value="VALIDATED">VALIDATED</option>
            <option value="APPROVED">APPROVED</option>
          </select>

          {/* New Model Button */}
          {onOpenPreparation && (
            <button
              type="button"
              onClick={onOpenPreparation}
              className="px-3 py-1.5 text-xs font-medium rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white flex items-center gap-1.5 transition-colors shadow-sm"
            >
              <Plus className="w-3.5 h-3.5" />
              Propose Model
            </button>
          )}
        </div>
      </div>

      {/* Models List / Table */}
      {isLoading ? (
        <div className="p-12 text-center text-xs text-slate-400 flex flex-col items-center justify-center gap-2">
          <div className="w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin" />
          <span>Loading project workflow models...</span>
        </div>
      ) : filteredModels.length === 0 ? (
        <div className="p-12 text-center space-y-3">
          <div className="w-12 h-12 mx-auto rounded-2xl bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 flex items-center justify-center">
            <Workflow className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
              {models.length === 0 ? 'No Workflow Models Registered' : 'No Matching Models Found'}
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm mx-auto">
              {models.length === 0
                ? 'Propose a candidate EFSM reference model from structured workflow inputs or submit a direct draft definition.'
                : 'Adjust your search terms or lifecycle status filter to find models.'}
            </p>
          </div>
          {models.length === 0 && onOpenPreparation && (
            <button
              type="button"
              onClick={onOpenPreparation}
              className="mt-2 inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white transition-colors shadow-sm"
            >
              <Plus className="w-4 h-4" />
              Propose First Candidate Model
            </button>
          )}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 dark:bg-slate-900/50 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="py-2.5 px-4 font-medium">Model Name & ID</th>
                <th className="py-2.5 px-3 font-medium">Version</th>
                <th className="py-2.5 px-3 font-medium">Lifecycle</th>
                <th className="py-2.5 px-3 font-medium">Content Hash</th>
                <th className="py-2.5 px-3 font-medium">Approval Status</th>
                <th className="py-2.5 px-3 font-medium">Updated</th>
                <th className="py-2.5 px-4 text-right font-medium">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
              {filteredModels.map((m) => {
                const isSelected =
                  m.model_id === selectedModelId && m.version === selectedVersion;

                const isApproved = m.lifecycle_status === 'APPROVED';
                const isValidated = m.lifecycle_status === 'VALIDATED';

                return (
                  <tr
                    key={`${m.model_id}-${m.version}`}
                    onClick={() => onSelectModel(m.model_id, m.version)}
                    className={`cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-indigo-50/60 dark:bg-indigo-950/30'
                        : 'hover:bg-slate-50 dark:hover:bg-slate-900/30'
                    }`}
                  >
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-900 dark:text-white">
                        {m.name}
                      </div>
                      <div className="text-[11px] font-mono text-slate-400">
                        {m.model_id}
                      </div>
                    </td>
                    <td className="py-3 px-3">
                      <span className="font-mono px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-medium">
                        v{m.version}
                      </span>
                    </td>
                    <td className="py-3 px-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                          isApproved
                            ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300'
                            : isValidated
                            ? 'bg-blue-100 text-blue-800 dark:bg-blue-950/70 dark:text-blue-300'
                            : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                        }`}
                      >
                        {isApproved ? (
                          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                        ) : isValidated ? (
                          <ShieldCheck className="w-3 h-3 text-blue-600" />
                        ) : (
                          <Clock className="w-3 h-3 text-slate-500" />
                        )}
                        {m.lifecycle_status}
                      </span>
                    </td>
                    <td className="py-3 px-3">
                      <div
                        className="font-mono text-[11px] text-slate-500 dark:text-slate-400 max-w-[140px] truncate"
                        title={m.content_hash}
                      >
                        <Hash className="w-3 h-3 inline-block text-slate-400 mr-0.5" />
                        {m.content_hash ? m.content_hash.slice(0, 16) : '-'}...
                      </div>
                    </td>
                    <td className="py-3 px-3 text-slate-600 dark:text-slate-300 text-[11px]">
                      {m.approved_by ? (
                        <div>
                          <div className="font-medium text-emerald-700 dark:text-emerald-400">
                            Approved
                          </div>
                          <div className="text-[10px] text-slate-400 truncate max-w-[150px]">
                            {m.approved_by}
                          </div>
                        </div>
                      ) : (
                        <span className="text-slate-400 italic">Unapproved</span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-[11px] text-slate-400">
                      {m.updated_at ? new Date(m.updated_at).toLocaleDateString() : '-'}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-1 text-indigo-600 dark:text-indigo-400 font-medium text-[11px]">
                        <span>Inspect</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
