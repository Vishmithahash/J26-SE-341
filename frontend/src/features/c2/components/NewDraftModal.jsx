import React, { useState } from 'react';
import { X, GitBranch, ArrowRight } from 'lucide-react';

export const NewDraftModal = ({
  isOpen,
  onClose,
  model,
  onCreateDraft,
  isCreating = false,
}) => {
  const [newVersion, setNewVersion] = useState('');
  const [description, setDescription] = useState('');
  const [validationError, setValidationError] = useState('');

  if (!isOpen || !model) return null;

  // Compute a default suggested next version (e.g. 1.0.0 -> 1.1.0)
  const suggestNextVersion = (ver) => {
    try {
      const parts = ver.split('.');
      if (parts.length === 3) {
        return `${parts[0]}.${parseInt(parts[1], 10) + 1}.0`;
      }
    } catch {
      // fallback
    }
    return `${ver}-draft`;
  };

  const initialSuggestion = suggestNextVersion(model.version);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setValidationError('');

    const targetVersion = (newVersion || initialSuggestion).trim();
    if (!targetVersion) {
      setValidationError('New version string is required.');
      return;
    }

    if (targetVersion === model.version) {
      setValidationError('New version must differ from the source version.');
      return;
    }

    try {
      await onCreateDraft({
        newVersion: targetVersion,
        description: description.trim() || null,
      });
      onClose();
    } catch {
      // Handled by parent hook
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="new-draft-modal-title"
    >
      <div className="bg-white dark:bg-[#131A26] rounded-2xl border border-slate-200 dark:border-slate-800 shadow-2xl max-w-lg w-full flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-indigo-100 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-400">
              <GitBranch className="w-5 h-5" />
            </div>
            <div>
              <h2 id="new-draft-modal-title" className="text-base font-semibold text-slate-900 dark:text-white">
                Create New Draft Version
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Branched from: <code className="font-mono">{model.model_id}</code> (v{model.version})
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 text-xs text-slate-600 dark:text-slate-400 flex items-center justify-between">
            <div>
              <span className="font-medium text-slate-900 dark:text-white">Source Version:</span> v{model.version}
              <div className="text-[11px] text-slate-500">Status: {model.lifecycle_status}</div>
            </div>
            <ArrowRight className="w-4 h-4 text-slate-400" />
            <div>
              <span className="font-medium text-slate-900 dark:text-white">New Status:</span> DRAFT
              <div className="text-[11px] text-indigo-500 font-medium">Editable Reference</div>
            </div>
          </div>

          {validationError && (
            <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-800 dark:text-rose-200">
              {validationError}
            </div>
          )}

          {/* New Version Input */}
          <div className="space-y-1.5">
            <label htmlFor="new-version-input" className="block text-xs font-medium text-slate-700 dark:text-slate-300">
              New Version Identifier <span className="text-rose-500">*</span>
            </label>
            <input
              id="new-version-input"
              type="text"
              defaultValue={initialSuggestion}
              value={newVersion || undefined}
              onChange={(e) => setNewVersion(e.target.value)}
              placeholder="e.g. 1.1.0 or 2.0.0"
              required
              className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500 font-mono"
            />
          </div>

          {/* Version Description */}
          <div className="space-y-1.5">
            <label htmlFor="version-description" className="block text-xs font-medium text-slate-700 dark:text-slate-300">
              Change Summary or Changelog Note (Optional)
            </label>
            <textarea
              id="version-description"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe modifications, new transitions, or guard refinements..."
              className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Actions */}
          <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={onClose}
              disabled={isCreating}
              className="px-4 py-2 text-xs font-medium rounded-xl border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isCreating}
              className="px-4 py-2 text-xs font-medium rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white flex items-center gap-1.5 transition-colors disabled:opacity-50"
            >
              {isCreating ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Creating Draft...
                </>
              ) : (
                <>
                  <GitBranch className="w-4 h-4" />
                  Create Draft Version
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
