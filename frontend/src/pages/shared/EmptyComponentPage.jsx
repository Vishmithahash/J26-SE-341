import React from 'react';

export const EmptyComponentPage = ({
  title,
  icon: Icon,
}) => {
  return (
    <div className="space-y-6">
      {/* Component Title Header */}
      <div className="flex items-center gap-3 pb-4 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white leading-tight">
            {title}
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Dedicated component workspace
          </p>
        </div>
      </div>

      {/* Empty content area: strictly empty shell */}
      <div
        className="min-h-[420px] rounded-2xl border border-dashed border-slate-200 dark:border-slate-800 bg-white/40 dark:bg-slate-900/40"
        aria-label={`${title} workspace area`}
      />
    </div>
  );
};
