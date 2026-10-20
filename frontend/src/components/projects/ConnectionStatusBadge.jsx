import React from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
  Lock,
  PowerOff,
  AlertOctagon,
} from 'lucide-react';
import { CONNECTION_STATES } from '../../services/projects';

export const ConnectionStatusBadge = ({ state, size = 'md' }) => {
  const configs = {
    [CONNECTION_STATES.CONNECTED]: {
      label: 'Connected',
      icon: CheckCircle2,
      style: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/50',
      dot: 'bg-emerald-500',
    },
    [CONNECTION_STATES.PARTIAL]: {
      label: 'Partial',
      icon: AlertTriangle,
      style: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/50',
      dot: 'bg-amber-500',
    },
    [CONNECTION_STATES.AUTH_REQUIRED]: {
      label: 'Auth Required',
      icon: Lock,
      style: 'bg-violet-50 text-violet-700 border-violet-200 dark:bg-violet-950/40 dark:text-violet-300 dark:border-violet-800/50',
      dot: 'bg-violet-500',
    },
    [CONNECTION_STATES.UNREACHABLE]: {
      label: 'Unreachable',
      icon: XCircle,
      style: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800/50',
      dot: 'bg-rose-500',
    },
    [CONNECTION_STATES.INVALID_CONFIGURATION]: {
      label: 'Invalid Configuration',
      icon: AlertOctagon,
      style: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-800/50',
      dot: 'bg-red-500',
    },
    [CONNECTION_STATES.DISCONNECTED]: {
      label: 'Disconnected',
      icon: PowerOff,
      style: 'bg-slate-100 text-slate-600 border-slate-300 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700',
      dot: 'bg-slate-400',
    },
    [CONNECTION_STATES.NOT_CHECKED]: {
      label: 'Not Checked',
      icon: HelpCircle,
      style: 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700',
      dot: 'bg-slate-400',
    },
  };

  const conf = configs[state] || configs[CONNECTION_STATES.NOT_CHECKED];
  const Icon = conf.icon;

  const isSmall = size === 'sm';

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium border rounded-full ${conf.style} ${
        isSmall ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-1 text-xs'
      }`}
    >
      <Icon className={isSmall ? 'w-3 h-3' : 'w-3.5 h-3.5'} />
      <span>{conf.label}</span>
    </span>
  );
};
