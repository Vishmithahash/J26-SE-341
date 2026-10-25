/**
 * Component 4 (C4) - Domain Bindings & Onboarding Section
 * Inspects application roles, tools, resources, units, approval states, canary markers, instruction channels,
 * domain runtime readiness, and onboarding workflow pipeline.
 */

import React, { useState } from 'react';
import {
  Boxes,
  Shield,
  Wrench,
  Database,
  Radio,
  CheckCircle,
  AlertTriangle,
  Play,
  RotateCw,
  Search,
  Sparkles,
} from 'lucide-react';

export function DomainBindingsSection({
  domainProfiles,
  selectedDomainId,
  onSelectDomainId,
  domainReadiness,
  domainBindings: _domainBindings,
  selectedBinding,
  onSelectBinding: _onSelectBinding,
  activeOnboardingJob,
  isLoadingDomains: _isLoadingDomains,
  isLoadingReadiness,
  isSubmittingJob,
  onCheckReadiness,
  onFetchBindingVersion,
  onStartOnboarding,
  selectedArtifact,
  error,
  successMessage,
  isProjectReady,
}) {
  const [activeInspectorSubTab, setActiveInspectorSubTab] = useState('roles');
  const [lookupBindingId, setLookupBindingId] = useState('');
  const [lookupBindingVersion, setLookupBindingVersion] = useState('1');

  // Find currently selected profile
  const currentProfile = domainProfiles.find((p) => p.domain_id === selectedDomainId) || domainProfiles[0];
  // Backend readiness report: { is_ready, status, execution_mode, blockers }.
  const readinessIsReady = Boolean(domainReadiness?.is_ready ?? domainReadiness?.ready);
  const readinessMode = domainReadiness?.execution_mode || 'SIMULATED';
  const readinessBlockers = domainReadiness?.blockers || domainReadiness?.live_blockers || [];
  const binding = selectedBinding || currentProfile?.binding;

  const handleLookup = (e) => {
    e.preventDefault();
    if (!lookupBindingId.trim() || !lookupBindingVersion || !isProjectReady) return;
    onFetchBindingVersion(lookupBindingId.trim(), lookupBindingVersion);
  };

  const handleStartOnboarding = () => {
    if (!currentProfile || !selectedArtifact || !isProjectReady || isSubmittingJob) return;

    onStartOnboarding({
      domainId: currentProfile.domain_id,
      artifactId: selectedArtifact.artifact_id,
      artifactVersion: selectedArtifact.version,
      bindingId: currentProfile.binding.binding_id,
      bindingVersion: currentProfile.binding.version,
      providerId: 'shared_llm',
      reviewer: 'dev_reviewer',
    });
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Domain Profile Selector */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded-lg bg-indigo-100 dark:bg-indigo-950/70 text-indigo-600 dark:text-indigo-400 font-bold text-xs flex items-center justify-center">
                <Boxes className="w-3.5 h-3.5" />
              </span>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                Domain Bindings & Application Onboarding
              </h3>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Inspect application roles, tool parameters, approval states, canary markers, and declared untrusted injection channels.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => onCheckReadiness(selectedDomainId, currentProfile?.is_live_available ? 'LIVE' : 'SIMULATED')}
              disabled={isLoadingReadiness || !isProjectReady}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
            >
              <RotateCw className={`w-3.5 h-3.5 ${isLoadingReadiness ? 'animate-spin' : ''}`} />
              <span>Check Readiness</span>
            </button>
          </div>
        </div>

        {/* Feedback messages */}
        {error && (
          <div className="mt-4 p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-300 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {successMessage && (
          <div className="mt-4 p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900 text-emerald-700 dark:text-emerald-300 text-xs flex items-center gap-2">
            <CheckCircle className="w-4 h-4 shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Domain Profile Cards */}
        <div className="mt-6">
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-2">
            Target Domain Profile
          </label>
          <div className="grid sm:grid-cols-2 gap-4">
            {domainProfiles.map((prof) => {
              const isSelected = prof.domain_id === selectedDomainId;
              return (
                <div
                  key={prof.domain_id}
                  onClick={() => onSelectDomainId(prof.domain_id)}
                  className={`p-4 rounded-xl border cursor-pointer transition-all ${
                    isSelected
                      ? 'border-indigo-500 bg-indigo-50/30 dark:bg-indigo-950/30 ring-1 ring-indigo-500'
                      : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-slate-50/50 dark:bg-slate-950/50'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span className="font-bold text-xs text-slate-900 dark:text-white">
                      {prof.name}
                    </span>
                    <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300">
                      {prof.domain_id}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 dark:text-slate-400 mb-3">
                    {prof.description}
                  </p>
                  <div className="text-[11px] font-mono text-slate-500 space-y-0.5">
                    <div>Default Adapter: {prof.adapter_id} ({prof.adapter_version})</div>
                    <div>Live Connection: {prof.is_live_available ? 'Connected' : 'Disconnected (Simulated Mode)'}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Domain Runtime Readiness Report */}
        {domainReadiness && (
          <div className="mt-6 p-4 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                <Shield className="w-4 h-4 text-indigo-500" />
                Domain Readiness: {domainReadiness.domain_id}
              </span>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                  readinessIsReady
                    ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300'
                    : 'bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300'
                }`}
              >
                {readinessIsReady ? `READY (${readinessMode === 'LIVE' ? 'Live' : 'Simulated'})` : 'BLOCKED'}
              </span>
            </div>

            <div className="text-xs text-slate-600 dark:text-slate-400 space-y-1">
              <div>
                Mode: {readinessMode}{' '}
                {readinessMode === 'LIVE'
                  ? `(adapter ${currentProfile?.adapter_id || 'live'})`
                  : '(Deterministic Simulation Engine)'}
              </div>
              {readinessBlockers.length > 0 && (
                <div className="mt-2 pt-2 border-t border-slate-200 dark:border-slate-800">
                  <span className="text-[11px] font-semibold text-amber-700 dark:text-amber-400 block mb-1">
                    Live AUT Execution Blockers:
                  </span>
                  <ul className="space-y-0.5 text-[11px] font-mono text-amber-800 dark:text-amber-300 pl-3 list-disc">
                    {readinessBlockers.map((blk, idx) => (
                      <li key={idx}>{blk}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Binding Version Lookup */}
        <div className="mt-6 pt-6 border-t border-slate-100 dark:border-slate-800">
          <form onSubmit={handleLookup} className="flex flex-col sm:flex-row items-end gap-3">
            <div className="flex-1">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Lookup Domain Binding Version by ID
              </label>
              <div className="grid grid-cols-3 gap-2">
                <input
                  type="text"
                  value={lookupBindingId}
                  onChange={(e) => setLookupBindingId(e.target.value)}
                  placeholder="e.g. domain-ecommerce-refund"
                  disabled={!isProjectReady}
                  className="col-span-2 px-3 py-1.5 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <input
                  type="number"
                  min="1"
                  value={lookupBindingVersion}
                  onChange={(e) => setLookupBindingVersion(e.target.value)}
                  placeholder="v1"
                  disabled={!isProjectReady}
                  className="px-3 py-1.5 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={!isProjectReady || !lookupBindingId.trim()}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 font-medium text-xs transition-colors shrink-0"
            >
              <Search className="w-3.5 h-3.5" />
              <span>Lookup Binding</span>
            </button>
          </form>
        </div>
      </div>

      {/* Domain Binding Full Inspector */}
      {binding && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-200 dark:border-slate-800 mb-4">
            <div>
              <div className="flex items-center gap-2">
                <h4 className="text-base font-bold text-slate-900 dark:text-white">
                  Domain Binding: {binding.binding_id}
                </h4>
                <span className="px-2 py-0.5 rounded text-xs font-mono bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300">
                  v{binding.version}
                </span>
              </div>
              <p className="text-xs text-slate-500 font-mono mt-0.5 truncate max-w-xl">
                Hash: {binding.content_hash || 'computed-upon-registration'}
              </p>
            </div>

            {/* Inspector Sub-tabs */}
            <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800/80 p-1 rounded-xl text-xs overflow-x-auto">
              {[
                { id: 'roles', label: `Roles (${binding.roles?.length || 0})` },
                { id: 'tools', label: `Tools (${binding.tools?.length || 0})` },
                { id: 'resources', label: `Resources (${binding.resources?.length || 0})` },
                { id: 'approvals', label: 'Approvals' },
                { id: 'data', label: `Protected Data (${binding.protected_data?.length || 0})` },
                { id: 'sources', label: `Injection Sources (${binding.untrusted_sources?.length || 0})` },
              ].map((subTab) => (
                <button
                  key={subTab.id}
                  onClick={() => setActiveInspectorSubTab(subTab.id)}
                  className={`px-3 py-1.5 rounded-lg font-medium transition-colors shrink-0 ${
                    activeInspectorSubTab === subTab.id
                      ? 'bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-sm'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  {subTab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Sub-tab 1: Application Roles */}
          {activeInspectorSubTab === 'roles' && (
            <div className="space-y-3">
              <h5 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                Declared Application Principal Roles
              </h5>
              <div className="grid sm:grid-cols-2 gap-3">
                {binding.roles?.map((role) => (
                  <div
                    key={role.role_name}
                    className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-xs"
                  >
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="font-mono font-bold text-slate-900 dark:text-white">
                        {role.role_name}
                      </span>
                      <span className="px-1.5 py-0.2 rounded text-[10px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                        Tier {role.hierarchy_level}
                      </span>
                    </div>
                    <p className="text-slate-600 dark:text-slate-400 text-xs mb-2">
                      {role.description}
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {role.permitted_actions?.map((act) => (
                        <span
                          key={act}
                          className="px-2 py-0.5 rounded text-[10px] font-mono bg-indigo-50 dark:bg-indigo-950/80 text-indigo-700 dark:text-indigo-300"
                        >
                          {act}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Sub-tab 2: Tools & Parameter Bounds */}
          {activeInspectorSubTab === 'tools' && (
            <div className="space-y-3">
              <h5 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                Declared Tools & Parameter Bound Schemas
              </h5>
              <div className="space-y-3">
                {binding.tools?.map((tool) => (
                  <div
                    key={tool.tool_name}
                    className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-xs"
                  >
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <span className="font-mono font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                        <Wrench className="w-3.5 h-3.5 text-indigo-500" />
                        {tool.tool_name}
                      </span>
                      <div className="flex items-center gap-1.5">
                        {tool.mutates_state && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300">
                            Mutates State
                          </span>
                        )}
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                          Target: {tool.target_resource || '*'}
                        </span>
                      </div>
                    </div>
                    <p className="text-slate-600 dark:text-slate-400 mb-3">
                      {tool.description}
                    </p>

                    {/* Parameters Table */}
                    {tool.parameters && tool.parameters.length > 0 && (
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-[11px] font-mono border-t border-slate-200 dark:border-slate-800 pt-2">
                          <thead>
                            <tr className="text-slate-400">
                              <th className="py-1">Param</th>
                              <th className="py-1">Type</th>
                              <th className="py-1">Unit</th>
                              <th className="py-1">Bounds</th>
                              <th className="py-1">Required</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                            {tool.parameters.map((p) => (
                              <tr key={p.name} className="text-slate-700 dark:text-slate-300">
                                <td className="py-1.5 font-bold">{p.name}</td>
                                <td className="py-1.5 text-indigo-600 dark:text-indigo-400">{p.param_type}</td>
                                <td className="py-1.5">{p.unit || '-'}</td>
                                <td className="py-1.5">
                                  {p.min_value != null || p.max_value != null
                                    ? `[${p.min_value ?? '0'} .. ${p.max_value ?? '∞'}]`
                                    : '-'}
                                </td>
                                <td className="py-1.5">{p.required ? 'Yes' : 'No'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Sub-tab 3: Resources */}
          {activeInspectorSubTab === 'resources' && (
            <div className="space-y-3">
              <h5 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                Declared Resources & State Fields
              </h5>
              <div className="grid sm:grid-cols-2 gap-3">
                {binding.resources?.map((res) => (
                  <div
                    key={res.resource_type}
                    className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-xs"
                  >
                    <div className="font-mono font-bold text-slate-900 dark:text-white mb-1.5 flex items-center gap-1.5">
                      <Database className="w-3.5 h-3.5 text-indigo-500" />
                      {res.resource_type}
                    </div>
                    <div className="text-[11px] font-mono text-slate-500 space-y-1">
                      <div>ID Field: <span className="text-slate-800 dark:text-slate-200">{res.identifier_field}</span></div>
                      <div>Owner Field: <span className="text-slate-800 dark:text-slate-200">{res.owner_field || 'N/A'}</span></div>
                      <div className="flex items-center gap-1 flex-wrap mt-1">
                        <span>State Fields:</span>
                        {res.state_fields?.map((sf) => (
                          <span key={sf} className="px-1.5 py-0.2 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                            {sf}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Sub-tab 4: Approvals */}
          {activeInspectorSubTab === 'approvals' && (
            <div className="space-y-3">
              <h5 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                Approval Representation Schema
              </h5>
              <div className="space-y-2">
                {binding.approval_states?.map((app, idx) => (
                  <div
                    key={idx}
                    className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-xs space-y-1 font-mono"
                  >
                    <div>Status Field: <strong>{app.approval_status_field}</strong></div>
                    <div>Approver Role Field: <strong>{app.approver_role_field}</strong></div>
                    <div className="flex items-center gap-1.5 mt-2">
                      <span>Valid Statuses:</span>
                      {app.valid_statuses?.map((st) => (
                        <span key={st} className="px-2 py-0.5 rounded text-[10px] bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 font-bold">
                          {st}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Sub-tab 5: Protected Data */}
          {activeInspectorSubTab === 'data' && (
            <div className="space-y-3">
              <h5 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                Protected Data Classifications & Synthetic Canaries
              </h5>
              <div className="grid sm:grid-cols-2 gap-3">
                {binding.protected_data?.map((pd, idx) => (
                  <div
                    key={idx}
                    className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-xs"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono font-bold text-slate-900 dark:text-white">
                        {pd.marker}
                      </span>
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300">
                        {pd.classification_label}
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 dark:text-slate-400 mb-2">{pd.description}</p>
                    <div className="text-[11px] font-mono text-slate-500 space-y-0.5">
                      <div>Permitted Roles: {pd.permitted_roles?.join(', ') || 'NONE'}</div>
                      <div>Permitted Recipients: {pd.permitted_recipients?.join(', ') || 'NONE'}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Sub-tab 6: Untrusted Injection Sources */}
          {activeInspectorSubTab === 'sources' && (
            <div className="space-y-3">
              <h5 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                Declared Untrusted Injection Surfaces
              </h5>
              <div className="grid sm:grid-cols-2 gap-3">
                {binding.untrusted_sources?.map((src) => (
                  <div
                    key={src.source_id}
                    className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 text-xs"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                        <Radio className="w-3.5 h-3.5 text-amber-500" />
                        {src.source_id}
                      </span>
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300">
                        {src.source_type}
                      </span>
                    </div>
                    <div className="text-[11px] font-mono text-slate-500 space-y-0.5 mt-2">
                      <div>Injection Field: <strong className="text-slate-800 dark:text-slate-200">{src.injection_field}</strong></div>
                      <div>Default Channel: {src.default_channel}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Onboarding Workflow Pipeline Launcher */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800 mb-4">
          <div>
            <h4 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-500" />
              <span>Domain Onboarding Pipeline Launcher</span>
            </h4>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Initiates bounded onboarding workflow connecting policy artifact intake with target domain bindings.
            </p>
          </div>

          <button
            type="button"
            onClick={handleStartOnboarding}
            disabled={!selectedArtifact || !isProjectReady || isSubmittingJob}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 dark:disabled:bg-slate-800 text-white font-medium text-xs shadow-sm transition-colors shrink-0"
          >
            {isSubmittingJob ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Starting Pipeline...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Start Domain Onboarding</span>
              </>
            )}
          </button>
        </div>

        {/* Active Onboarding Job Status */}
        {activeOnboardingJob ? (
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold font-mono text-slate-900 dark:text-white">
                Job ID: {activeOnboardingJob.job_id}
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300">
                {activeOnboardingJob.status}
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono text-slate-500">
              <div>Domain: {activeOnboardingJob.domain_id}</div>
              <div>Current Step: {activeOnboardingJob.current_step}</div>
              <div>Extraction Job: {activeOnboardingJob.extraction_job_id || 'N/A'}</div>
              <div>Draft Contract: {activeOnboardingJob.draft_contract_id || 'N/A'}</div>
            </div>

            {/* Gaps / Unsupported Rules */}
            {activeOnboardingJob.gaps && activeOnboardingJob.gaps.length > 0 && (
              <div className="mt-3 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900">
                <span className="text-[11px] font-bold text-amber-900 dark:text-amber-200 block mb-1">
                  Onboarding Coverage Gaps Detected ({activeOnboardingJob.gaps.length})
                </span>
                <ul className="text-xs text-amber-800 dark:text-amber-300 space-y-1">
                  {activeOnboardingJob.gaps.map((g, idx) => (
                    <li key={idx}>• {typeof g === 'string' ? g : JSON.stringify(g)}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <div className="text-xs text-slate-500 dark:text-slate-400 italic">
            Select an artifact in Policy Preparation and click "Start Domain Onboarding" to run the onboarding pipeline.
          </div>
        )}
      </div>
    </div>
  );
}
