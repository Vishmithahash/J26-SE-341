import React, { useState } from 'react';
import {
  Workflow,
  CheckCircle2,
  Clock,
  ShieldCheck,
  ShieldAlert,
  GitBranch,
  Play,
  FileCheck,
  Layers,
  ArrowRight,
  Shield,
  Milestone,
  Lock,
  Code2,
  Copy,
  Check,
  Database,
  RefreshCw,
} from 'lucide-react';
import { PredicateViewer } from './PredicateViewer';

export const ModelDetailView = ({
  model,
  readiness,
  validationReport,
  _validationHistory = [],
  onValidate,
  onOpenApproval,
  onOpenNewDraft,
  onOpenReport,
  onRefresh,
  isValidating = false,
  allVersions = [],
  onSelectVersion,
}) => {
  const [activeTab, setActiveTab] = useState('transitions');
  const [copiedHash, setCopiedHash] = useState(false);
  const [expandedTransitionId, setExpandedTransitionId] = useState(null);

  if (!model) {
    return (
      <div className="p-8 text-center text-xs text-slate-400 bg-white dark:bg-[#131A26] rounded-2xl border border-slate-200 dark:border-slate-800">
        Select a reference model from the list above to view full Extended Finite State Machine (EFSM) definitions.
      </div>
    );
  }

  const def = model.definition || {};
  const states = def.states || [];
  const transitions = def.transitions || [];
  const invariants = def.invariants || [];
  const continuityRules = def.entity_continuity_rules || [];
  const milestones = def.milestones || [];
  const finalOutcomes = def.final_outcomes || [];
  const variables = def.variables || [];
  const protectedFields = def.protected_fields || [];
  const eventMappings = def.event_mappings || [];

  const isApproved = model.lifecycle_status === 'APPROVED';
  const isValidated = model.lifecycle_status === 'VALIDATED';
  const isModelReady = readiness?.readiness === 'READY';

  const copyContentHash = () => {
    if (model.content_hash) {
      navigator.clipboard.writeText(model.content_hash);
      setCopiedHash(true);
      setTimeout(() => setCopiedHash(false), 2000);
    }
  };

  return (
    <div className="bg-white dark:bg-[#131A26] rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden flex flex-col space-y-0">
      {/* Top Banner & Metadata */}
      <div className="p-6 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40 space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="p-1.5 rounded-lg bg-indigo-100 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-400">
                <Workflow className="w-5 h-5" />
              </span>
              <h2 className="text-lg font-bold text-slate-900 dark:text-white">
                {model.name}
              </h2>
              {/* Version Selector */}
              {allVersions.length > 1 ? (
                <select
                  value={model.version}
                  onChange={(e) => onSelectVersion && onSelectVersion(model.model_id, e.target.value)}
                  className="px-2.5 py-1 text-xs font-mono font-semibold rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200"
                >
                  {allVersions.map((v) => (
                    <option key={v.version} value={v.version}>
                      v{v.version} ({v.lifecycle_status})
                    </option>
                  ))}
                </select>
              ) : (
                <span className="px-2 py-0.5 font-mono text-xs font-semibold rounded-md bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-200">
                  v{model.version}
                </span>
              )}
              {/* Lifecycle Badge */}
              <span
                className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                  isApproved
                    ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
                    : isValidated
                    ? 'bg-blue-100 text-blue-800 dark:bg-blue-950/70 dark:text-blue-300 border border-blue-200 dark:border-blue-800'
                    : 'bg-amber-100 text-amber-800 dark:bg-amber-950/70 dark:text-amber-300 border border-amber-200 dark:border-amber-800'
                }`}
              >
                {isApproved ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                ) : isValidated ? (
                  <ShieldCheck className="w-3.5 h-3.5 text-blue-600" />
                ) : (
                  <Clock className="w-3.5 h-3.5 text-amber-600" />
                )}
                {model.lifecycle_status}
              </span>
              {/* Readiness Badge */}
              <span
                className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                  isModelReady
                    ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-700'
                    : 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400 border border-rose-300 dark:border-rose-700'
                }`}
              >
                {isModelReady ? (
                  <CheckCircle2 className="w-3.5 h-3.5" />
                ) : (
                  <ShieldAlert className="w-3.5 h-3.5" />
                )}
                {readiness?.readiness || (isApproved ? 'READY' : 'MODEL NOT READY')}
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Model ID: <code className="font-mono text-slate-700 dark:text-slate-300">{model.model_id}</code>
              {def.schema_version && (
                <span className="ml-2">Schema: <code className="font-mono">{def.schema_version}</code></span>
              )}
            </p>
          </div>

          {/* Quick Actions Bar */}
          <div className="flex items-center gap-2 flex-wrap">
            {/* Run Validation */}
            <button
              type="button"
              onClick={onValidate}
              disabled={isValidating}
              className="px-3 py-1.5 text-xs font-semibold rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white flex items-center gap-1.5 transition-colors disabled:opacity-50 shadow-sm"
              title="Run structural and bounded semantic validation"
            >
              {isValidating ? (
                <>
                  <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Validating...
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" />
                  Validate
                </>
              )}
            </button>

            {/* Review & Approve Button */}
            {!isApproved && (
              <button
                type="button"
                onClick={onOpenApproval}
                disabled={!isValidated && readiness?.validation_passed !== true}
                className="px-3 py-1.5 text-xs font-semibold rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white flex items-center gap-1.5 transition-colors disabled:opacity-40 disabled:hover:bg-emerald-600 shadow-sm"
                title={
                  isValidated || readiness?.validation_passed
                    ? 'Review model and record formal approval'
                    : 'Model must pass validation prior to approval'
                }
              >
                <ShieldCheck className="w-3.5 h-3.5" />
                Review & Approve
              </button>
            )}

            {/* New Draft Version */}
            <button
              type="button"
              onClick={onOpenNewDraft}
              className="px-3 py-1.5 text-xs font-medium rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 flex items-center gap-1.5 transition-colors"
              title="Branch a new editable draft from this model version"
            >
              <GitBranch className="w-3.5 h-3.5" />
              New Version
            </button>

            {/* Validation History Modal Trigger */}
            {validationReport && (
              <button
                type="button"
                onClick={onOpenReport}
                className="px-3 py-1.5 text-xs font-medium rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 flex items-center gap-1.5 transition-colors"
              >
                <FileCheck className="w-3.5 h-3.5" />
                Validation Report
              </button>
            )}

            {/* Refresh */}
            {onRefresh && (
              <button
                type="button"
                onClick={onRefresh}
                className="p-1.5 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 transition-colors"
                title="Refresh model details"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Content Hash and Timestamp strip */}
        <div className="flex flex-wrap items-center gap-y-2 gap-x-6 text-[11px] text-slate-500 dark:text-slate-400 pt-2 border-t border-slate-200 dark:border-slate-800/80">
          <div className="flex items-center gap-1.5 font-mono">
            <span>Content Hash:</span>
            <code className="text-slate-800 dark:text-slate-200 bg-slate-200/60 dark:bg-slate-800 px-1.5 py-0.5 rounded">
              {model.content_hash || '-'}
            </code>
            <button
              type="button"
              onClick={copyContentHash}
              className="p-1 hover:text-indigo-600 transition-colors"
              title="Copy content hash"
            >
              {copiedHash ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
            </button>
          </div>

          <div>
            <span>Created:</span>{' '}
            <span className="text-slate-700 dark:text-slate-300">
              {model.created_at ? new Date(model.created_at).toLocaleString() : '-'}
            </span>
          </div>

          <div>
            <span>Updated:</span>{' '}
            <span className="text-slate-700 dark:text-slate-300">
              {model.updated_at ? new Date(model.updated_at).toLocaleString() : '-'}
            </span>
          </div>

          {isApproved && (
            <div className="flex items-center gap-1 text-emerald-700 dark:text-emerald-400 font-medium">
              <Lock className="w-3 h-3" />
              <span>Approved & Immutable</span>
            </div>
          )}
        </div>
      </div>

      {/* Authoritative Readiness & Approval Banner */}
      <div className="p-4 bg-slate-50/80 dark:bg-slate-900/20 border-b border-slate-200 dark:border-slate-800 space-y-3">
        {readiness && (
          <div
            className={`p-3.5 rounded-xl border flex items-start gap-3 ${
              isModelReady
                ? 'bg-emerald-50/60 border-emerald-200 dark:bg-emerald-950/20 dark:border-emerald-900/60'
                : 'bg-amber-50/60 border-amber-200 dark:bg-amber-950/20 dark:border-amber-900/60'
            }`}
          >
            {isModelReady ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
            ) : (
              <ShieldAlert className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            )}
            <div className="text-xs space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-slate-900 dark:text-white">
                  Authoritative Readiness: {readiness.readiness}
                </span>
                <span className="text-[11px] text-slate-500">
                  (Validation: {readiness.validation_passed ? 'PASSED' : 'PENDING/FAILED'} | Approved:{' '}
                  {readiness.is_approved ? 'YES' : 'NO'})
                </span>
              </div>
              {readiness.reasons && readiness.reasons.length > 0 && (
                <ul className="list-disc list-inside space-y-0.5 text-slate-600 dark:text-slate-400 text-[11px]">
                  {readiness.reasons.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        {/* Approval Provenance Details (if approved) */}
        {isApproved && (
          <div className="p-3.5 rounded-xl bg-slate-100 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 text-xs text-slate-700 dark:text-slate-300 space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                Recorded Approval Provenance
              </div>
              {/* Provenance Badge */}
              {model.approved_by?.includes('[SELF_REPORTED_DEVELOPMENT]') ? (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300 dark:border-amber-800">
                  Self-Reported Development Review (Non-independent)
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300 border border-blue-300 dark:border-blue-800">
                  Claimed Review (Unverified by Backend)
                </span>
              )}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
              <div>
                <span className="text-slate-500">Recorded Reviewer:</span>{' '}
                <span className="font-medium text-slate-800 dark:text-slate-200">
                  {model.approved_by || 'Unknown'}
                </span>
              </div>
              <div>
                <span className="text-slate-500">Approved Date:</span>{' '}
                <span className="text-slate-700 dark:text-slate-300">
                  {model.approved_at ? new Date(model.approved_at).toLocaleString() : '-'}
                </span>
              </div>
              {model.review_basis && (
                <div className="sm:col-span-2">
                  <span className="text-slate-500">Review Basis:</span>{' '}
                  <span className="text-slate-700 dark:text-slate-300">{model.review_basis}</span>
                </div>
              )}
              {model.review_notes && (
                <div className="sm:col-span-2">
                  <span className="text-slate-500">Review Notes:</span>{' '}
                  <span className="text-slate-700 dark:text-slate-300">{model.review_notes}</span>
                </div>
              )}
            </div>
            <div className="text-[10px] text-slate-400 dark:text-slate-500 italic pt-1.5 border-t border-slate-200 dark:border-slate-800/80">
              * Audit Disclosure: Provenance reflects client-submitted review records. The backend does not independently authenticate reviewer credentials or perform multi-party cryptographic verification.
            </div>
          </div>
        )}
      </div>

      {/* Tabs Navigation */}
      <div className="flex items-center overflow-x-auto border-b border-slate-200 dark:border-slate-800 px-6 bg-white dark:bg-[#131A26]">
        <button
          type="button"
          onClick={() => setActiveTab('transitions')}
          className={`py-3 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors mr-5 flex items-center gap-1.5 ${
            activeTab === 'transitions'
              ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
              : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
          }`}
        >
          <ArrowRight className="w-3.5 h-3.5" />
          Transitions ({transitions.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('states')}
          className={`py-3 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors mr-5 flex items-center gap-1.5 ${
            activeTab === 'states'
              ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
              : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          States ({states.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('invariants')}
          className={`py-3 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors mr-5 flex items-center gap-1.5 ${
            activeTab === 'invariants'
              ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
              : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
          }`}
        >
          <Shield className="w-3.5 h-3.5" />
          Invariants ({invariants.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('continuity')}
          className={`py-3 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors mr-5 flex items-center gap-1.5 ${
            activeTab === 'continuity'
              ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
              : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
          }`}
        >
          <Database className="w-3.5 h-3.5" />
          Entity Continuity ({continuityRules.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('milestones')}
          className={`py-3 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors mr-5 flex items-center gap-1.5 ${
            activeTab === 'milestones'
              ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
              : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
          }`}
        >
          <Milestone className="w-3.5 h-3.5" />
          Milestones & Outcomes ({milestones.length + finalOutcomes.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('variables')}
          className={`py-3 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors mr-5 flex items-center gap-1.5 ${
            activeTab === 'variables'
              ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
              : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
          }`}
        >
          <Lock className="w-3.5 h-3.5" />
          Protected State & Variables
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('raw')}
          className={`py-3 text-xs font-semibold border-b-2 whitespace-nowrap transition-colors flex items-center gap-1.5 ${
            activeTab === 'raw'
              ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
              : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
          }`}
        >
          <Code2 className="w-3.5 h-3.5" />
          Raw JSON
        </button>
      </div>

      {/* Tab Panels */}
      <div className="p-6">
        {/* Tab: Transitions */}
        {activeTab === 'transitions' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
              <span>Extended Finite State Machine transitions triggered by tool events.</span>
              <span>Guard predicates are evaluated strictly as declarative data trees.</span>
            </div>

            <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 dark:bg-slate-900/50 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3 font-medium">Transition ID</th>
                    <th className="py-2.5 px-3 font-medium">Source → Target State</th>
                    <th className="py-2.5 px-3 font-medium">Trigger Event / Tool</th>
                    <th className="py-2.5 px-3 font-medium">Guard Expression</th>
                    <th className="py-2.5 px-3 font-medium">State Updates</th>
                    <th className="py-2.5 px-3 font-medium">Expected Effects</th>
                    <th className="py-2.5 px-3 font-medium">Rules</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                  {transitions.map((t) => {
                    const isExpanded = expandedTransitionId === t.id;
                    return (
                      <React.Fragment key={t.id}>
                        <tr
                          onClick={() => setExpandedTransitionId(isExpanded ? null : t.id)}
                          className="hover:bg-slate-50 dark:hover:bg-slate-900/30 cursor-pointer transition-colors"
                        >
                          <td className="py-3 px-3 font-mono font-medium text-slate-900 dark:text-white">
                            {t.id}
                          </td>
                          <td className="py-3 px-3">
                            <div className="flex items-center gap-1.5 font-mono text-[11px]">
                              <span className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                                {t.source_state}
                              </span>
                              <ArrowRight className="w-3 h-3 text-slate-400" />
                              <span className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                                {t.target_state}
                              </span>
                            </div>
                          </td>
                          <td className="py-3 px-3">
                            <span className="px-2 py-0.5 rounded font-mono text-[11px] bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                              {t.trigger_event}
                            </span>
                          </td>
                          <td className="py-3 px-3 max-w-xs">
                            <PredicateViewer predicate={t.guard} label={`Guard (${t.id})`} />
                          </td>
                          <td className="py-3 px-3 text-[11px] font-mono text-slate-600 dark:text-slate-300">
                            {t.actions && t.actions.length > 0 ? (
                              <span>{t.actions.length} update(s)</span>
                            ) : (
                              <span className="text-slate-400 italic">None</span>
                            )}
                          </td>
                          <td className="py-3 px-3 text-[11px]">
                            {t.expected_effects && t.expected_effects.length > 0 ? (
                              <span className="text-emerald-700 dark:text-emerald-400 font-medium">
                                {t.expected_effects.length} assertion(s)
                              </span>
                            ) : (
                              <span className="text-slate-400 italic">None</span>
                            )}
                          </td>
                          <td className="py-3 px-3 text-[10px] text-slate-400 font-mono">
                            {t.source_rules && t.source_rules.length > 0
                              ? t.source_rules.join(', ')
                              : '-'}
                          </td>
                        </tr>

                        {/* Expanded details row */}
                        {isExpanded && (
                          <tr className="bg-slate-50/80 dark:bg-slate-900/40">
                            <td colSpan={7} className="p-4 space-y-3">
                              {t.description && (
                                <p className="text-xs text-slate-700 dark:text-slate-300">
                                  <span className="font-semibold">Description:</span> {t.description}
                                </p>
                              )}

                              {t.actions && t.actions.length > 0 && (
                                <div className="space-y-1">
                                  <div className="text-[11px] font-semibold text-slate-800 dark:text-slate-200">
                                    Variable Updates:
                                  </div>
                                  <div className="flex flex-wrap gap-2">
                                    {t.actions.map((act, i) => (
                                      <code
                                        key={i}
                                        className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-200"
                                      >
                                        {act.variable_name} = {typeof act.expression === 'object' ? JSON.stringify(act.expression) : String(act.expression)}
                                      </code>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {t.expected_effects && t.expected_effects.length > 0 && (
                                <div className="space-y-1">
                                  <div className="text-[11px] font-semibold text-slate-800 dark:text-slate-200">
                                    Post-Transition State Effects:
                                  </div>
                                  <div className="space-y-1">
                                    {t.expected_effects.map((eff, i) => (
                                      <PredicateViewer key={i} predicate={eff} label={`Effect #${i + 1}`} />
                                    ))}
                                  </div>
                                </div>
                              )}

                              {t.deferred_effects && t.deferred_effects.length > 0 && (
                                <div className="space-y-1">
                                  <div className="text-[11px] font-semibold text-amber-700 dark:text-amber-400">
                                    Deferred Checkpoint Obligations:
                                  </div>
                                  <div className="space-y-1 text-xs">
                                    {t.deferred_effects.map((de, i) => (
                                      <div key={i} className="p-2 rounded bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/60">
                                        <div className="font-medium text-[11px]">
                                          Checkpoint State: <code className="font-mono">{de.checkpoint_state_id}</code>
                                        </div>
                                        <PredicateViewer predicate={de.predicate} label={`Deferred Check #${i + 1}`} />
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tab: States */}
        {activeTab === 'states' && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
                <span className="text-[11px] text-slate-500 font-medium">Initial State</span>
                <div className="font-mono font-semibold text-slate-900 dark:text-white mt-1">
                  {def.initial_state_id || '-'}
                </div>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
                <span className="text-[11px] text-slate-500 font-medium">Accepting States</span>
                <div className="font-mono font-semibold text-emerald-600 dark:text-emerald-400 mt-1">
                  {def.accepting_state_ids ? def.accepting_state_ids.join(', ') : '-'}
                </div>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
                <span className="text-[11px] text-slate-500 font-medium">Rejection States</span>
                <div className="font-mono font-semibold text-rose-600 dark:text-rose-400 mt-1">
                  {def.rejection_state_ids && def.rejection_state_ids.length > 0
                    ? def.rejection_state_ids.join(', ')
                    : 'None'}
                </div>
              </div>
            </div>

            <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 dark:bg-slate-900/50 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3 font-medium">State ID</th>
                    <th className="py-2.5 px-3 font-medium">State Name</th>
                    <th className="py-2.5 px-3 font-medium">Type</th>
                    <th className="py-2.5 px-3 font-medium">Milestone Achieved</th>
                    <th className="py-2.5 px-3 font-medium">Description</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                  {states.map((st) => (
                    <tr key={st.id} className="hover:bg-slate-50 dark:hover:bg-slate-900/30">
                      <td className="py-3 px-3 font-mono font-semibold text-slate-900 dark:text-white">
                        {st.id}
                      </td>
                      <td className="py-3 px-3 font-medium text-slate-800 dark:text-slate-200">
                        {st.name}
                      </td>
                      <td className="py-3 px-3">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                            st.type === 'initial'
                              ? 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300'
                              : st.type === 'terminal_accepting'
                              ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                              : st.type === 'terminal_rejection'
                              ? 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                              : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                          }`}
                        >
                          {st.type}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-[11px] font-mono text-indigo-600 dark:text-indigo-400">
                        {st.milestone || '-'}
                      </td>
                      <td className="py-3 px-3 text-slate-600 dark:text-slate-400">
                        {st.description || '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tab: Invariants */}
        {activeTab === 'invariants' && (
          <div className="space-y-4">
            <div className="text-xs text-slate-500 dark:text-slate-400">
              Workflow safety invariants that must strictly hold across all states or during execution.
            </div>

            {invariants.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">No invariants declared for this model.</div>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 dark:bg-slate-900/50 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      <th className="py-2.5 px-3 font-medium">Invariant ID</th>
                      <th className="py-2.5 px-3 font-medium">Invariant Name</th>
                      <th className="py-2.5 px-3 font-medium">Safety Predicate</th>
                      <th className="py-2.5 px-3 font-medium">Source Rule</th>
                      <th className="py-2.5 px-3 font-medium">Description</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                    {invariants.map((inv) => (
                      <tr key={inv.id} className="hover:bg-slate-50 dark:hover:bg-slate-900/30">
                        <td className="py-3 px-3 font-mono font-semibold text-slate-900 dark:text-white">
                          {inv.id}
                        </td>
                        <td className="py-3 px-3 font-medium text-slate-800 dark:text-slate-200">
                          {inv.name}
                        </td>
                        <td className="py-3 px-3 max-w-sm">
                          <PredicateViewer predicate={inv.predicate} label={`Invariant (${inv.id})`} />
                        </td>
                        <td className="py-3 px-3 font-mono text-[11px] text-slate-500">
                          {inv.source_rule || '-'}
                        </td>
                        <td className="py-3 px-3 text-slate-600 dark:text-slate-400">
                          {inv.description || '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Tab: Continuity */}
        {activeTab === 'continuity' && (
          <div className="space-y-4">
            <div className="text-xs text-slate-500 dark:text-slate-400">
              Entity continuity rules enforce that primary identifiers selected early in the multi-step transaction remain consistent through downstream actions.
            </div>

            {continuityRules.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">No continuity rules declared.</div>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 dark:bg-slate-900/50 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      <th className="py-2.5 px-3 font-medium">Rule ID</th>
                      <th className="py-2.5 px-3 font-medium">Entity Type</th>
                      <th className="py-2.5 px-3 font-medium">Key Field</th>
                      <th className="py-2.5 px-3 font-medium">Bound State Variable</th>
                      <th className="py-2.5 px-3 font-medium">Description</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                    {continuityRules.map((cr) => (
                      <tr key={cr.id} className="hover:bg-slate-50 dark:hover:bg-slate-900/30">
                        <td className="py-3 px-3 font-mono font-semibold text-slate-900 dark:text-white">
                          {cr.id}
                        </td>
                        <td className="py-3 px-3 font-medium text-slate-800 dark:text-slate-200">
                          {cr.entity_type}
                        </td>
                        <td className="py-3 px-3 font-mono text-[11px] text-slate-600 dark:text-slate-300">
                          {cr.key_field}
                        </td>
                        <td className="py-3 px-3">
                          <code className="text-xs font-mono px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                            {cr.bound_variable}
                          </code>
                        </td>
                        <td className="py-3 px-3 text-slate-600 dark:text-slate-400">
                          {cr.description || '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Tab: Milestones & Final Outcomes */}
        {activeTab === 'milestones' && (
          <div className="space-y-6">
            {/* Milestones */}
            <div className="space-y-3">
              <h3 className="text-xs font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                <Milestone className="w-4 h-4 text-indigo-500" />
                Workflow Milestones ({milestones.length})
              </h3>
              <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 dark:bg-slate-900/50 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      <th className="py-2.5 px-3 font-medium">Milestone ID</th>
                      <th className="py-2.5 px-3 font-medium">Name</th>
                      <th className="py-2.5 px-3 font-medium">Target State</th>
                      <th className="py-2.5 px-3 font-medium">Required</th>
                      <th className="py-2.5 px-3 font-medium">Description</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                    {milestones.map((m) => (
                      <tr key={m.id} className="hover:bg-slate-50 dark:hover:bg-slate-900/30">
                        <td className="py-3 px-3 font-mono font-semibold text-slate-900 dark:text-white">
                          {m.id}
                        </td>
                        <td className="py-3 px-3 font-medium text-slate-800 dark:text-slate-200">
                          {m.name}
                        </td>
                        <td className="py-3 px-3 font-mono text-[11px] text-indigo-600 dark:text-indigo-400">
                          {m.state_id}
                        </td>
                        <td className="py-3 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                              m.required
                                ? 'bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300'
                                : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
                            }`}
                          >
                            {m.required ? 'Required' : 'Optional'}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-slate-600 dark:text-slate-400">
                          {m.description || '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Final Outcomes */}
            <div className="space-y-3">
              <h3 className="text-xs font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                Permitted Final Outcomes ({finalOutcomes.length})
              </h3>
              <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 dark:bg-slate-900/50 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      <th className="py-2.5 px-3 font-medium">Outcome ID</th>
                      <th className="py-2.5 px-3 font-medium">Outcome Type</th>
                      <th className="py-2.5 px-3 font-medium">Terminal State</th>
                      <th className="py-2.5 px-3 font-medium">Description</th>
                      <th className="py-2.5 px-3 font-medium">Task Prompt</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                    {finalOutcomes.map((fo) => (
                      <tr key={fo.outcome_id} className="hover:bg-slate-50 dark:hover:bg-slate-900/30">
                        <td className="py-3 px-3 font-mono font-semibold text-slate-900 dark:text-white">
                          {fo.outcome_id}
                        </td>
                        <td className="py-3 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                              fo.type === 'ACCEPTING'
                                ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300'
                                : 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300'
                            }`}
                          >
                            {fo.type}
                          </span>
                        </td>
                        <td className="py-3 px-3 font-mono text-[11px] text-slate-700 dark:text-slate-300">
                          {fo.terminal_state_id}
                        </td>
                        <td className="py-3 px-3 text-slate-600 dark:text-slate-400">
                          {fo.description}
                        </td>
                        <td className="py-3 px-3 text-[11px] text-slate-500">
                          {fo.task_prompt || '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Tab: Variables & Protected State */}
        {activeTab === 'variables' && (
          <div className="space-y-6">
            {/* Protected State Fields */}
            <div className="space-y-3">
              <h3 className="text-xs font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                <Lock className="w-4 h-4 text-rose-500" />
                Protected State Fields ({protectedFields.length})
              </h3>
              <p className="text-[11px] text-slate-500">
                Application state fields that must remain untouched under failure or rejection paths.
              </p>
              {protectedFields.length === 0 ? (
                <div className="p-4 text-center text-xs text-slate-400">No protected fields declared.</div>
              ) : (
                <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 dark:bg-slate-900/50 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                      <tr>
                        <th className="py-2.5 px-3 font-medium">Entity Type</th>
                        <th className="py-2.5 px-3 font-medium">Field Path</th>
                        <th className="py-2.5 px-3 font-medium">Strict Unchanged on Rejection</th>
                        <th className="py-2.5 px-3 font-medium">Allowed Mutation States</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                      {protectedFields.map((pf, i) => (
                        <tr key={i} className="hover:bg-slate-50 dark:hover:bg-slate-900/30">
                          <td className="py-3 px-3 font-medium text-slate-800 dark:text-slate-200">
                            {pf.entity_type}
                          </td>
                          <td className="py-3 px-3 font-mono text-[11px] text-rose-700 dark:text-rose-400">
                            {pf.field_path}
                          </td>
                          <td className="py-3 px-3">
                            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300">
                              {pf.strict_unchanged_on_rejection ? 'TRUE (Strict)' : 'FALSE'}
                            </span>
                          </td>
                          <td className="py-3 px-3 font-mono text-[11px] text-slate-500">
                            {pf.allowed_mutations && pf.allowed_mutations.length > 0
                              ? pf.allowed_mutations.join(', ')
                              : 'None (Immutable across all states)'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Declared State Variables */}
            <div className="space-y-3">
              <h3 className="text-xs font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                <Database className="w-4 h-4 text-indigo-500" />
                Declared Extended State Variables ({variables.length})
              </h3>
              {variables.length === 0 ? (
                <div className="p-4 text-center text-xs text-slate-400">No variables declared.</div>
              ) : (
                <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 dark:bg-slate-900/50 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                      <tr>
                        <th className="py-2.5 px-3 font-medium">Variable Name</th>
                        <th className="py-2.5 px-3 font-medium">Type</th>
                        <th className="py-2.5 px-3 font-medium">Initial Value</th>
                        <th className="py-2.5 px-3 font-medium">Finite Domain</th>
                        <th className="py-2.5 px-3 font-medium">Description</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                      {variables.map((v) => (
                        <tr key={v.name} className="hover:bg-slate-50 dark:hover:bg-slate-900/30">
                          <td className="py-3 px-3 font-mono font-semibold text-slate-900 dark:text-white">
                            {v.name}
                          </td>
                          <td className="py-3 px-3 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                            {v.type}
                          </td>
                          <td className="py-3 px-3 font-mono text-[11px] text-slate-500">
                            {v.initial_value === null ? 'null' : String(v.initial_value)}
                          </td>
                          <td className="py-3 px-3 text-[11px] text-slate-500 font-mono">
                            {v.domain && v.domain.length > 0 ? JSON.stringify(v.domain) : 'Unbounded'}
                          </td>
                          <td className="py-3 px-3 text-slate-600 dark:text-slate-400">
                            {v.description || '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Event to Tool Mappings */}
            {eventMappings.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-xs font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                  <Workflow className="w-4 h-4 text-indigo-500" />
                  Event to Tool Mappings ({eventMappings.length})
                </h3>
                <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 dark:bg-slate-900/50 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                      <tr>
                        <th className="py-2.5 px-3 font-medium">Event ID</th>
                        <th className="py-2.5 px-3 font-medium">Concrete Tool Name</th>
                        <th className="py-2.5 px-3 font-medium">Parameter Mappings</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                      {eventMappings.map((em) => (
                        <tr key={em.event_id} className="hover:bg-slate-50 dark:hover:bg-slate-900/30">
                          <td className="py-3 px-3 font-mono font-semibold text-slate-900 dark:text-white">
                            {em.event_id}
                          </td>
                          <td className="py-3 px-3 font-mono text-indigo-600 dark:text-indigo-400">
                            {em.tool_name}
                          </td>
                          <td className="py-3 px-3 font-mono text-[11px] text-slate-600 dark:text-slate-300">
                            {em.parameter_mappings
                              ? JSON.stringify(em.parameter_mappings)
                              : '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab: Raw Definition JSON */}
        {activeTab === 'raw' && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
              <span>Read-only canonical EFSM JSON definition.</span>
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(JSON.stringify(def, null, 2));
                  setCopiedHash(true);
                  setTimeout(() => setCopiedHash(false), 2000);
                }}
                className="text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-1"
              >
                <Copy className="w-3.5 h-3.5" />
                Copy Full JSON
              </button>
            </div>
            <pre className="p-4 rounded-xl bg-slate-900 text-slate-100 font-mono text-xs overflow-x-auto max-h-[600px] border border-slate-800">
              {JSON.stringify(def, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};
