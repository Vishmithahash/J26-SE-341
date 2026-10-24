import React, { useState, useEffect } from 'react';
import {
  Settings2,
  FileCode,
  RotateCcw,
  Sparkles,
  AlertCircle,
  Check,
  Layers,
  Wrench,
  ShieldCheck,
  Compass,
  RefreshCw,
} from 'lucide-react';
import { c3Api } from '../api.js';
import {
  DEMO_ADAPTER_MANIFEST,
  DEMO_TASK_FIXTURE_METADATA,
  DEMO_RECOVERY_CONTRACT,
  DEMO_GENERATION_POLICY,
  DEMO_CANDIDATE_CASE_VALID,
  DEMO_CANDIDATE_CASE_REJECTED,
} from '../fixtures.js';
import { useProject } from '../../../context/ProjectContext';

export const C3InputPreparation = ({
  candidateCase,
  setCandidateCase,
  adapterManifest,
  setAdapterManifest,
  taskFixtureMetadata,
  setTaskFixtureMetadata,
  recoveryContract,
  setRecoveryContract,
  generationPolicy,
  setGenerationPolicy,
  onReset,
}) => {
  const { activeProject } = useProject();
  const [activeTab, setActiveTab] = useState('structured'); // 'structured' | 'json'
  const [jsonText, setJsonText] = useState('');
  const [jsonError, setJsonError] = useState(null);
  const [presetLoaded, setPresetLoaded] = useState('ecommerce');
  const [draftLoading, setDraftLoading] = useState(false);
  const [draftFeedback, setDraftFeedback] = useState(null);
  const [proposedDraft, setProposedDraft] = useState(null);

  // Keep JSON string in sync when entering JSON tab
  useEffect(() => {
    if (activeTab === 'json') {
      const fullConfig = {
        candidate_case: candidateCase,
        adapter_manifest: adapterManifest,
        task_fixture_metadata: taskFixtureMetadata,
        recovery_contract: recoveryContract,
        policy: generationPolicy,
      };
      setJsonText(JSON.stringify(fullConfig, null, 2));
      setJsonError(null);
    }
  }, [
    activeTab,
    candidateCase,
    adapterManifest,
    taskFixtureMetadata,
    recoveryContract,
    generationPolicy,
  ]);

  const handleJsonChange = (e) => {
    const val = e.target.value;
    setJsonText(val);
    try {
      const parsed = JSON.parse(val);
      setJsonError(null);
      if (parsed.candidate_case) setCandidateCase(parsed.candidate_case);
      if (parsed.adapter_manifest) setAdapterManifest(parsed.adapter_manifest);
      if (parsed.task_fixture_metadata) setTaskFixtureMetadata(parsed.task_fixture_metadata);
      if (parsed.recovery_contract) setRecoveryContract(parsed.recovery_contract);
      if (parsed.policy) setGenerationPolicy(parsed.policy);
    } catch (err) {
      setJsonError(err.message);
    }
  };

  const applyPreset = (presetKey) => {
    setPresetLoaded(presetKey);
    const targetProjId = activeProject?.project_id || 'proj-qa-001';

    if (presetKey === 'ecommerce') {
      setCandidateCase({
        ...DEMO_CANDIDATE_CASE_VALID,
        project_id: targetProjId,
      });
      setAdapterManifest(DEMO_ADAPTER_MANIFEST);
      setTaskFixtureMetadata(DEMO_TASK_FIXTURE_METADATA);
      setRecoveryContract(DEMO_RECOVERY_CONTRACT);
      setGenerationPolicy(DEMO_GENERATION_POLICY);
    } else if (presetKey === 'rejected_read_only') {
      setCandidateCase({
        ...DEMO_CANDIDATE_CASE_REJECTED,
        project_id: targetProjId,
      });
      setAdapterManifest(DEMO_ADAPTER_MANIFEST);
      setTaskFixtureMetadata(DEMO_TASK_FIXTURE_METADATA);
      setRecoveryContract(DEMO_RECOVERY_CONTRACT);
      setGenerationPolicy(DEMO_GENERATION_POLICY);
    } else if (presetKey === 'banking') {
      // Second domain preset
      const bankingManifest = {
        adapter_id: 'adapter-banking-01',
        adapter_version: '1.0.0',
        schema_version: '1.0.0',
        tools: [
          { tool_id: 'wire_transfer', tool_version: '1.0.0', mutability: 'SIDE_EFFECTING' },
          { tool_id: 'balance_inquiry', tool_version: '1.0.0', mutability: 'READ_ONLY' },
        ],
        supported_combinations: [
          {
            tool_id: 'wire_transfer',
            fault_family: 'TIMEOUT_DISCONNECTION',
            effect_phase: 'BEFORE_EFFECT',
            interception_hook: 'BEFORE_TOOL_CALL',
            supported_occurrence_bounds: { min_occurrence: 1, max_occurrence: 3 },
            allowed_release_rule_types: ['ATTEMPT_BOUNDED'],
            supported_payload_modes: ['CALLER_TIMEOUT_EXCEEDED'],
            required_observation_capabilities: ['network_latency_ms'],
          },
          {
            tool_id: 'wire_transfer',
            fault_family: 'TIMEOUT_DISCONNECTION',
            effect_phase: 'AFTER_COMMIT',
            interception_hook: 'APPLICATION_AWARE_HOOK',
            supported_occurrence_bounds: { min_occurrence: 1, max_occurrence: 2 },
            allowed_release_rule_types: ['ATTEMPT_BOUNDED'],
            supported_payload_modes: ['CALLER_TIMEOUT_EXCEEDED'],
            required_observation_capabilities: ['verify_committed_transfer'],
          },
          {
            tool_id: 'wire_transfer',
            fault_family: 'TRANSIENT_5XX',
            effect_phase: 'BEFORE_EFFECT',
            interception_hook: 'BEFORE_TOOL_CALL',
            supported_occurrence_bounds: { min_occurrence: 1, max_occurrence: 3 },
            allowed_release_rule_types: ['ATTEMPT_BOUNDED'],
            supported_payload_modes: ['HTTP_500', 'HTTP_503'],
            required_observation_capabilities: ['transient_5xx_observed'],
          },
        ],
      };

      const bankingFixture = {
        task_id: 'task-wire-transfer-01',
        task_version: '1.0.0',
        fixture_id: 'fix-banking-ledger',
        fixture_version: '1.0.0',
        domain: 'banking',
        associated_tool_ids: ['wire_transfer', 'balance_inquiry'],
        associated_recovery_contract_ids: ['rec-banking-01'],
        declared_reset_support: true,
        reset_method: 'ledger_snapshot_revert',
        declared_observation_support: true,
        supported_observations: ['network_latency_ms', 'verify_committed_transfer', 'transient_5xx_observed'],
        supports_committed_effect_observation: true,
        supports_partial_effect_observation: false,
      };

      const bankingContract = {
        contract_id: 'rec-banking-01',
        contract_version: '1.0.0',
        permitted_terminal_outcomes: ['SUCCESS_CLEAN_RECOVERY'],
        graceful_stopping_conditions: ['degraded_balance_hold'],
        initial_invocation_counts_as_attempt: true,
        max_task_attempts: 2,
        max_retries: 1,
        max_tool_calls_budget: 6,
        max_total_timeout_ms: 15000,
        required_state_assertions: ['state_transfer_committed', 'balance_double_entry_balanced'],
        allow_duplicate_side_effects: false,
        allow_retry_on_unverified_commit: false,
        require_truthful_completion_reporting: true,
        future_finding_rules: [],
      };

      setCandidateCase({
        schema_version: '1.0.0',
        project_id: targetProjId,
        case_id: 'case-wire-001',
        case_family_id: 'fam-banking-timeout',
        domain: 'banking',
        task_id: 'task-wire-transfer-01',
        task_version: '1.0.0',
        tool_id: 'wire_transfer',
        tool_version: '1.0.0',
        fixture_id: 'fix-banking-ledger',
        fixture_version: '1.0.0',
        adapter_id: 'adapter-banking-01',
        adapter_version: '1.0.0',
        recovery_contract_id: 'rec-banking-01',
        recovery_contract_version: '1.0.0',
        occurrence: 1,
        interception_hook: 'BEFORE_TOOL_CALL',
        fault_family: 'TIMEOUT_DISCONNECTION',
        effect_phase: 'BEFORE_EFFECT',
        payload: {
          family: 'TIMEOUT_DISCONNECTION',
          mode: 'CALLER_TIMEOUT_EXCEEDED',
          timing_ms: 4000,
        },
        release_rule: {
          rule_type: 'ATTEMPT_BOUNDED',
          max_fault_count: 1,
          release_after_ms: null,
        },
        required_assertions: ['state_transfer_committed'],
        required_observations: ['network_latency_ms'],
        caller_timeout_ms: 2500,
        reproducibility_seed: 777,
      });
      setAdapterManifest(bankingManifest);
      setTaskFixtureMetadata(bankingFixture);
      setRecoveryContract(bankingContract);
      setGenerationPolicy({ ...DEMO_GENERATION_POLICY, seed: 777 });
    }
  };

  const handleModelDraft = async () => {
    setDraftLoading(true);
    setDraftFeedback(null);
    setProposedDraft(null);
    try {
      const res = await c3Api.prepareDraftInputs({
        project_id: activeProject?.project_id || 'proj-demo-qa',
        task_id: candidateCase?.task_id || taskFixtureMetadata?.task_id || undefined,
        tool_id: candidateCase?.tool_id || adapterManifest?.tools?.[0]?.tool_id || undefined,
        domain: candidateCase?.domain || 'ecommerce',
        existing_task_fixture: taskFixtureMetadata || null,
        existing_adapter_manifest: adapterManifest || null,
        existing_recovery_contract: recoveryContract || null,
      });

      const meta = res.provider_metadata || {};
      const modelInfo = meta.provider ? ` (${meta.provider} / ${meta.actual_model})` : '';

      if (res.status === 'SUCCESS') {
        setProposedDraft({
          taskFixture: res.draft_task_fixture,
          recoveryContract: res.draft_recovery_contract,
        });
        setDraftFeedback({
          type: 'success',
          message: `AI draft inputs prepared successfully${modelInfo}. Review proposed parameters and click 'Apply Proposed Draft' below.`,
          unresolved: [],
        });
      } else if (res.status === 'UNRESOLVED_REFERENCES') {
        setProposedDraft(null);
        setDraftFeedback({
          type: 'warning',
          message: `AI draft produced with unresolved references${modelInfo}: ${res.explanation || ''}. Configuration was not altered.`,
          unresolved: res.unresolved_references || [],
        });
      } else {
        setProposedDraft(null);
        setDraftFeedback({
          type: 'error',
          message: res.explanation || 'Draft generation failed. Configuration was preserved.',
          unresolved: res.unresolved_references || [],
        });
      }
    } catch (err) {
      setProposedDraft(null);
      setDraftFeedback({
        type: 'error',
        message: `Model assistance failed: ${err.message || 'Network error'}`,
        unresolved: [],
      });
    } finally {
      setDraftLoading(false);
    }
  };

  return (
    <div id="prepare" className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
      {/* Header and Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Settings2 className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <span>Candidate Case & Generation Input Preparation</span>
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Configure declarative contracts, manifests, and generation budgets matching Pydantic schemas.
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center gap-2">
          <div className="inline-flex p-1 rounded-xl bg-slate-100 dark:bg-slate-800 text-xs font-semibold">
            <button
              type="button"
              onClick={() => setActiveTab('structured')}
              className={`px-3 py-1 rounded-lg transition-colors flex items-center gap-1.5 ${
                activeTab === 'structured'
                  ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-xs'
                  : 'text-slate-500 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              <Compass className="w-3.5 h-3.5" />
              <span>Structured Form</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('json')}
              className={`px-3 py-1 rounded-lg transition-colors flex items-center gap-1.5 ${
                activeTab === 'json'
                  ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-xs'
                  : 'text-slate-500 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              <FileCode className="w-3.5 h-3.5" />
              <span>JSON Editor</span>
            </button>
          </div>
        </div>
      </div>

      {/* Presets Bar */}
      <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-slate-500 dark:text-slate-400 flex items-center gap-1">
            <Sparkles className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
            <span>Load Preset:</span>
          </span>
          <button
            type="button"
            onClick={() => applyPreset('ecommerce')}
            className={`px-2.5 py-1 rounded-lg font-medium transition-colors ${
              presetLoaded === 'ecommerce'
                ? 'bg-indigo-600 text-white shadow-xs'
                : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700'
            }`}
          >
            E-Commerce (Valid Baseline)
          </button>
          <button
            type="button"
            onClick={() => applyPreset('banking')}
            className={`px-2.5 py-1 rounded-lg font-medium transition-colors ${
              presetLoaded === 'banking'
                ? 'bg-indigo-600 text-white shadow-xs'
                : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700'
            }`}
          >
            Banking Wire Transfer (Domain 2)
          </button>
          <button
            type="button"
            onClick={() => applyPreset('rejected_read_only')}
            className={`px-2.5 py-1 rounded-lg font-medium transition-colors ${
              presetLoaded === 'rejected_read_only'
                ? 'bg-amber-600 text-white shadow-xs'
                : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700'
            }`}
          >
            Read-Only AFTER_COMMIT (Trigger TEST_NOT_READY)
          </button>

          <span className="text-slate-300 dark:text-slate-700">|</span>

          <button
            type="button"
            onClick={handleModelDraft}
            disabled={draftLoading}
            className="px-2.5 py-1 rounded-lg font-medium transition-colors bg-teal-600 hover:bg-teal-700 text-white flex items-center gap-1.5 shadow-xs disabled:opacity-50"
          >
            {draftLoading ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Sparkles className="w-3.5 h-3.5" />
            )}
            <span>{draftLoading ? 'Drafting...' : 'AI Model Draft'}</span>
          </button>
        </div>

        <button
          type="button"
          onClick={() => {
            applyPreset('ecommerce');
            setDraftFeedback(null);
            if (onReset) onReset();
          }}
          className="inline-flex items-center gap-1 text-slate-500 hover:text-slate-900 dark:hover:text-white"
        >
          <RotateCcw className="w-3 h-3" />
          <span>Reset Form</span>
        </button>
      </div>

      {/* Model-Assisted Draft Feedback Banner */}
      {draftFeedback && (
        <div
          role="status"
          className={`p-3.5 rounded-xl text-xs flex items-start gap-2.5 border ${
            draftFeedback.type === 'success'
              ? 'bg-teal-50 dark:bg-teal-950/40 border-teal-200 dark:border-teal-800 text-teal-800 dark:text-teal-200'
              : draftFeedback.type === 'warning'
              ? 'bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-200'
              : 'bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-800 text-red-800 dark:text-red-200'
          }`}
        >
          {draftFeedback.type === 'success' ? (
            <Check className="w-4 h-4 shrink-0 mt-0.5 text-teal-600 dark:text-teal-400" />
          ) : (
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-amber-600 dark:text-amber-400" />
          )}
          <div className="space-y-1">
            <p className="font-semibold">{draftFeedback.message}</p>
            {draftFeedback.unresolved?.length > 0 && (
              <ul className="list-disc list-inside text-[11px] opacity-90">
                {draftFeedback.unresolved.map((u, i) => (
                  <li key={i}>{u}</li>
                ))}
              </ul>
            )}
            {proposedDraft && (
              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => {
                    if (proposedDraft.taskFixture) setTaskFixtureMetadata(proposedDraft.taskFixture);
                    if (proposedDraft.recoveryContract) setRecoveryContract(proposedDraft.recoveryContract);
                    setProposedDraft(null);
                    setDraftFeedback({
                      type: 'success',
                      message: 'Proposed draft successfully accepted and applied to form configuration.',
                      unresolved: [],
                    });
                  }}
                  className="px-2.5 py-1 rounded-lg bg-teal-700 hover:bg-teal-800 text-white font-medium text-[11px] transition-colors shadow-xs"
                >
                  Apply Proposed Draft
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Shared Project Input References (if available) */}
      {activeProject?.input_references && activeProject.input_references.length > 0 && (
        <div className="p-3.5 rounded-xl bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-200/60 dark:border-indigo-900/40 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-indigo-900 dark:text-indigo-200">
              Registered Project Input References ({activeProject.input_references.length})
            </span>
            <span className="text-[11px] text-indigo-700 dark:text-indigo-300 italic">
              Reference only; unverified content is not loaded
            </span>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {activeProject.input_references.map((ref, idx) => (
              <span
                key={idx}
                className="px-2 py-0.5 rounded text-[11px] font-mono bg-white dark:bg-slate-900 border border-indigo-200 dark:border-indigo-800 text-indigo-800 dark:text-indigo-300"
              >
                {ref.category || 'reference'}: {ref.name || `Ref #${idx + 1}`}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Main Tab Content */}
      {activeTab === 'structured' ? (
        <div className="space-y-6">
          {/* Section 1: Candidate Fault Case Parameters */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
              <span>Candidate Case Declared Metadata</span>
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              <div>
                <label className="block text-slate-600 dark:text-slate-400 font-semibold mb-1">
                  Case ID
                </label>
                <input
                  type="text"
                  value={candidateCase.case_id || ''}
                  onChange={(e) =>
                    setCandidateCase({ ...candidateCase, case_id: e.target.value })
                  }
                  className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 font-mono text-slate-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block text-slate-600 dark:text-slate-400 font-semibold mb-1">
                  Target Tool ID
                </label>
                <input
                  type="text"
                  value={candidateCase.tool_id || ''}
                  onChange={(e) =>
                    setCandidateCase({ ...candidateCase, tool_id: e.target.value })
                  }
                  className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 font-mono text-slate-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block text-slate-600 dark:text-slate-400 font-semibold mb-1">
                  Fault Family
                </label>
                <select
                  value={candidateCase.fault_family || ''}
                  onChange={(e) => {
                    const fam = e.target.value;
                    let payload = { family: fam };
                    if (fam === 'TIMEOUT_DISCONNECTION') {
                      payload = { family: fam, mode: 'CALLER_TIMEOUT_EXCEEDED', timing_ms: 5000 };
                    } else if (fam === 'TRANSIENT_5XX') {
                      payload = { family: fam, http_status: 503, error_code: 'SERVICE_UNAVAILABLE' };
                    } else if (fam === 'RATE_LIMIT_429') {
                      payload = { family: fam, http_status: 429, retry_after_seconds: 2 };
                    } else if (fam === 'TOOL_UNAVAILABILITY') {
                      payload = { family: fam, mode: 'CIRCUIT_BROKEN', retryable: true };
                    } else if (fam === 'MALFORMED_RESPONSE') {
                      payload = { family: fam, mode: 'INVALID_JSON', raw_fragment: '{unclosed' };
                    }
                    setCandidateCase({
                      ...candidateCase,
                      fault_family: fam,
                      payload,
                    });
                  }}
                  className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 font-mono text-slate-900 dark:text-white"
                >
                  <option value="TIMEOUT_DISCONNECTION">TIMEOUT_DISCONNECTION</option>
                  <option value="TRANSIENT_5XX">TRANSIENT_5XX</option>
                  <option value="RATE_LIMIT_429">RATE_LIMIT_429</option>
                  <option value="TOOL_UNAVAILABILITY">TOOL_UNAVAILABILITY</option>
                  <option value="MALFORMED_RESPONSE">MALFORMED_RESPONSE</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-600 dark:text-slate-400 font-semibold mb-1">
                  Effect Phase
                </label>
                <select
                  value={candidateCase.effect_phase || ''}
                  onChange={(e) =>
                    setCandidateCase({ ...candidateCase, effect_phase: e.target.value })
                  }
                  className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 font-mono text-slate-900 dark:text-white"
                >
                  <option value="BEFORE_EFFECT">BEFORE_EFFECT</option>
                  <option value="AFTER_COMMIT">AFTER_COMMIT</option>
                  <option value="PARTIAL_EFFECT">PARTIAL_EFFECT</option>
                  <option value="NOT_APPLICABLE">NOT_APPLICABLE</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs pt-1">
              <div>
                <label className="block text-slate-600 dark:text-slate-400 font-semibold mb-1">
                  Interception Hook
                </label>
                <select
                  value={candidateCase.interception_hook || ''}
                  onChange={(e) =>
                    setCandidateCase({ ...candidateCase, interception_hook: e.target.value })
                  }
                  className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 font-mono text-slate-900 dark:text-white"
                >
                  <option value="BEFORE_TOOL_CALL">BEFORE_TOOL_CALL</option>
                  <option value="APPLICATION_AWARE_HOOK">APPLICATION_AWARE_HOOK</option>
                  <option value="AFTER_TOOL_CALL">AFTER_TOOL_CALL</option>
                  <option value="AROUND_TOOL_CALL">AROUND_TOOL_CALL</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-600 dark:text-slate-400 font-semibold mb-1">
                  Occurrence Number
                </label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={candidateCase.occurrence || 1}
                  onChange={(e) =>
                    setCandidateCase({ ...candidateCase, occurrence: parseInt(e.target.value, 10) || 1 })
                  }
                  className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 font-mono text-slate-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block text-slate-600 dark:text-slate-400 font-semibold mb-1">
                  Caller Timeout (ms)
                </label>
                <input
                  type="number"
                  min="0"
                  max="600000"
                  value={candidateCase.caller_timeout_ms || ''}
                  onChange={(e) =>
                    setCandidateCase({
                      ...candidateCase,
                      caller_timeout_ms: e.target.value ? parseInt(e.target.value, 10) : null,
                    })
                  }
                  className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 font-mono text-slate-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block text-slate-600 dark:text-slate-400 font-semibold mb-1">
                  Reproducibility Seed
                </label>
                <input
                  type="number"
                  value={candidateCase.reproducibility_seed || 42}
                  onChange={(e) =>
                    setCandidateCase({
                      ...candidateCase,
                      reproducibility_seed: parseInt(e.target.value, 10) || 0,
                    })
                  }
                  className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 font-mono text-slate-900 dark:text-white"
                />
              </div>
            </div>
          </div>

          {/* Section 2: Recovery Contract Constraints */}
          <div className="pt-4 border-t border-slate-100 dark:border-slate-800 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
              <span>Recovery Contract Budgets & Defect Rules</span>
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              <div>
                <label className="block text-slate-600 dark:text-slate-400 font-semibold mb-1">
                  Max Task Attempts
                </label>
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={recoveryContract.max_task_attempts}
                  onChange={(e) => {
                    const attempts = parseInt(e.target.value, 10) || 1;
                    setRecoveryContract({
                      ...recoveryContract,
                      max_task_attempts: attempts,
                      max_retries: Math.max(0, attempts - 1),
                    });
                  }}
                  className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 font-mono text-slate-900 dark:text-white"
                />
                <span className="text-[10px] text-slate-400 mt-0.5 block">
                  Enforces: attempts = 1 + retries ({recoveryContract.max_retries})
                </span>
              </div>

              <div>
                <label className="block text-slate-600 dark:text-slate-400 font-semibold mb-1">
                  Max Tool Calls Budget
                </label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={recoveryContract.max_tool_calls_budget}
                  onChange={(e) =>
                    setRecoveryContract({
                      ...recoveryContract,
                      max_tool_calls_budget: parseInt(e.target.value, 10) || 1,
                    })
                  }
                  className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 font-mono text-slate-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block text-slate-600 dark:text-slate-400 font-semibold mb-1">
                  Total Trial Timeout (ms)
                </label>
                <input
                  type="number"
                  min="1000"
                  max="300000"
                  value={recoveryContract.max_total_timeout_ms}
                  onChange={(e) =>
                    setRecoveryContract({
                      ...recoveryContract,
                      max_total_timeout_ms: parseInt(e.target.value, 10) || 1000,
                    })
                  }
                  className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 font-mono text-slate-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block text-slate-600 dark:text-slate-400 font-semibold mb-1">
                  Contract ID
                </label>
                <input
                  type="text"
                  value={recoveryContract.contract_id}
                  onChange={(e) =>
                    setRecoveryContract({ ...recoveryContract, contract_id: e.target.value })
                  }
                  className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 font-mono text-slate-900 dark:text-white"
                />
              </div>
            </div>

            {/* Checkbox Constraints */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2 text-xs">
              <label className="flex items-center gap-2 p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40">
                <input
                  type="checkbox"
                  checked={recoveryContract.allow_duplicate_side_effects}
                  onChange={(e) =>
                    setRecoveryContract({
                      ...recoveryContract,
                      allow_duplicate_side_effects: e.target.checked,
                    })
                  }
                  className="rounded border-slate-300 text-indigo-600"
                />
                <span className="text-slate-700 dark:text-slate-300">
                  Allow Duplicate Side Effects (Defect Flag)
                </span>
              </label>

              <label className="flex items-center gap-2 p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40">
                <input
                  type="checkbox"
                  checked={recoveryContract.allow_retry_on_unverified_commit}
                  onChange={(e) =>
                    setRecoveryContract({
                      ...recoveryContract,
                      allow_retry_on_unverified_commit: e.target.checked,
                    })
                  }
                  className="rounded border-slate-300 text-indigo-600"
                />
                <span className="text-slate-700 dark:text-slate-300">
                  Allow Retry on Unverified Commit
                </span>
              </label>

              <label className="flex items-center gap-2 p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40">
                <input
                  type="checkbox"
                  checked={recoveryContract.require_truthful_completion_reporting}
                  onChange={(e) =>
                    setRecoveryContract({
                      ...recoveryContract,
                      require_truthful_completion_reporting: e.target.checked,
                    })
                  }
                  className="rounded border-slate-300 text-indigo-600"
                />
                <span className="text-slate-700 dark:text-slate-300">
                  Require Truthful Completion Reporting
                </span>
              </label>
            </div>
          </div>

          {/* Section 3: Generation Policy & Execution Budget */}
          <div className="pt-4 border-t border-slate-100 dark:border-slate-800 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
              <Wrench className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
              <span>Generation Policy & Permutation Search Limit</span>
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              <div>
                <label className="block text-slate-600 dark:text-slate-400 font-semibold mb-1">
                  Case Budget (<code className="font-mono">max_cases</code>)
                </label>
                <input
                  type="number"
                  min="1"
                  max="50"
                  value={generationPolicy.max_cases}
                  onChange={(e) =>
                    setGenerationPolicy({
                      ...generationPolicy,
                      max_cases: parseInt(e.target.value, 10) || 1,
                    })
                  }
                  className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 font-mono text-slate-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block text-slate-600 dark:text-slate-400 font-semibold mb-1">
                  Candidate Search Limit (<code className="font-mono">max_candidates</code>)
                </label>
                <input
                  type="number"
                  min="1"
                  max="1000"
                  value={generationPolicy.max_candidates_examined}
                  onChange={(e) =>
                    setGenerationPolicy({
                      ...generationPolicy,
                      max_candidates_examined: parseInt(e.target.value, 10) || 50,
                    })
                  }
                  className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 font-mono text-slate-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block text-slate-600 dark:text-slate-400 font-semibold mb-1">
                  Deterministic Seed
                </label>
                <input
                  type="number"
                  min="0"
                  value={generationPolicy.seed}
                  onChange={(e) =>
                    setGenerationPolicy({
                      ...generationPolicy,
                      seed: parseInt(e.target.value, 10) || 0,
                    })
                  }
                  className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 font-mono text-slate-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block text-slate-600 dark:text-slate-400 font-semibold mb-1">
                  Coverage Strategy
                </label>
                <select
                  value={generationPolicy.coverage_strategy || 'ROUND_ROBIN'}
                  onChange={(e) =>
                    setGenerationPolicy({
                      ...generationPolicy,
                      coverage_strategy: e.target.value,
                    })
                  }
                  className="w-full px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 font-mono text-slate-900 dark:text-white"
                >
                  <option value="ROUND_ROBIN">ROUND_ROBIN (Family Diversity)</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Advanced JSON Editor */
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-500 dark:text-slate-400">
              Paste or modify raw JSON contract payload. Structural errors are validated dynamically.
            </span>
            {jsonError ? (
              <span className="text-xs text-rose-600 dark:text-rose-400 flex items-center gap-1 font-semibold">
                <AlertCircle className="w-3.5 h-3.5" />
                <span>Invalid JSON: {jsonError}</span>
              </span>
            ) : (
              <span className="text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-1 font-semibold">
                <Check className="w-3.5 h-3.5" />
                <span>JSON Validated</span>
              </span>
            )}
          </div>

          <textarea
            rows={18}
            value={jsonText}
            onChange={handleJsonChange}
            className="w-full p-4 rounded-xl font-mono text-xs bg-slate-900 text-slate-100 border border-slate-700 focus:ring-2 focus:ring-indigo-500 focus:outline-hidden leading-relaxed"
            placeholder="Paste JSON configuration payload here..."
          />
        </div>
      )}
    </div>
  );
};
