/**
 * Component 4 (C4) - Policy Contracts Section
 * Handles contract draft creation, validation gating, explicit acceptance, version lookup, and immutable accepted inspection.
 */

import React, { useState } from 'react';
import {
  FileCheck,
  CheckCircle2,
  AlertTriangle,
  Lock,
  ShieldCheck,
  RotateCw,
  User,
  Calendar,
  Layers,
  Search,
} from 'lucide-react';
import { useAuth } from '../../../../context/AuthContext';

export function ContractSection({
  selectedRuleIds,
  currentContract,
  contractValidation,
  isDrafting,
  isValidating,
  isAccepting,
  isFetching,
  isAccepted,
  onCreateDraft,
  onValidateDraft,
  onAcceptDraft,
  onFetchContract,
  error,
  successMessage,
  isProjectReady,
}) {
  const { user } = useAuth();
  const [contractId, setContractId] = useState('contract-ecommerce-v1');
  const [description, setDescription] = useState('E-Commerce baseline safety and authorization contract');
  const [isAcceptModalOpen, setIsAcceptModalOpen] = useState(false);
  const [acceptedBy, setAcceptedBy] = useState(user?.name || user?.email || 'security_lead');
  const [rationale, setRationale] = useState('Explicit human verification of all authorization and confidentiality constraints.');

  // Contract version lookup fields
  const [lookupContractId, setLookupContractId] = useState('');
  const [lookupContractVersion, setLookupContractVersion] = useState('1');

  const handleCreateDraft = (e) => {
    e.preventDefault();
    if (!contractId.trim() || selectedRuleIds.length === 0 || !isProjectReady || isDrafting) return;

    onCreateDraft({
      contractId: contractId.trim(),
      ruleIds: selectedRuleIds,
      description: description.trim() || null,
    });
  };

  const handleOpenAcceptModal = () => {
    setIsAcceptModalOpen(true);
  };

  const handleConfirmAccept = async (e) => {
    e.preventDefault();
    if (!currentContract || !acceptedBy.trim() || isAccepting) return;

    await onAcceptDraft({
      contractId: currentContract.contract_id,
      version: currentContract.version,
      acceptedBy: acceptedBy.trim(),
      rationale: rationale.trim() || null,
    });

    setIsAcceptModalOpen(false);
  };

  const handleLookupContract = (e) => {
    e.preventDefault();
    if (!isProjectReady || !lookupContractId.trim() || !lookupContractVersion || isFetching) return;
    onFetchContract(lookupContractId.trim(), lookupContractVersion);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded-lg bg-indigo-100 dark:bg-indigo-950/70 text-indigo-600 dark:text-indigo-400 font-bold text-xs flex items-center justify-center">
                4
              </span>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                Policy Contract Drafting, Validation & Acceptance Gate
              </h3>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Assemble reviewed rules into a versioned policy contract, run contract validation gates, and explicitly accept.
            </p>
          </div>

          {currentContract && (
            <div className="flex items-center gap-2">
              <span
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${
                  isAccepted
                    ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800'
                    : 'bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 border-indigo-300 dark:border-indigo-800'
                }`}
              >
                {isAccepted ? <Lock className="w-3.5 h-3.5" /> : <FileCheck className="w-3.5 h-3.5" />}
                <span>State: {currentContract.lifecycle_state}</span>
              </span>
            </div>
          )}
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
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Step 1: Contract Drafting Form */}
        {!isAccepted && (
          <form onSubmit={handleCreateDraft} className="mt-6 space-y-4">
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Contract Identifier <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  value={contractId}
                  onChange={(e) => setContractId(e.target.value)}
                  placeholder="e.g. contract-ecommerce-v1"
                  required
                  disabled={!isProjectReady || isDrafting}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Description / Purpose
                </label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g. Baseline safety invariants"
                  disabled={!isProjectReady || isDrafting}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
                />
              </div>
            </div>

            {/* Selected candidate rules preview */}
            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                  <Layers className="w-4 h-4 text-indigo-500" />
                  Included Rules ({selectedRuleIds.length})
                </span>
                <span className="text-[11px] text-slate-400">
                  Select rules from Candidate Inspection section above
                </span>
              </div>

              {selectedRuleIds.length > 0 ? (
                <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
                  {selectedRuleIds.map((id) => (
                    <span
                      key={id}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300"
                    >
                      {id}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-amber-600 dark:text-amber-400 italic">
                  No candidate rules currently selected. Please select candidate rules above before drafting.
                </p>
              )}
            </div>

            <div className="flex items-center justify-between pt-2">
              <span className="text-xs text-slate-400">
                Newly created contracts start in DRAFT or VALIDATED state.
              </span>
              <button
                type="submit"
                disabled={!isProjectReady || isDrafting || selectedRuleIds.length === 0 || !contractId.trim()}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 dark:disabled:bg-slate-800 text-white font-medium text-xs shadow-sm transition-colors"
              >
                {isDrafting ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    <span>Creating Draft...</span>
                  </>
                ) : (
                  <>
                    <FileCheck className="w-4 h-4" />
                    <span>Create Policy Contract Draft</span>
                  </>
                )}
              </button>
            </div>
          </form>
        )}

        {/* Contract ID/Version Lookup Panel */}
        <div className="mt-8 pt-6 border-t border-slate-100 dark:border-slate-800">
          <form onSubmit={handleLookupContract} className="flex flex-col sm:flex-row items-end gap-3">
            <div className="flex-1">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Retrieve Specific Policy Contract Version by ID
              </label>
              <div className="grid grid-cols-3 gap-2">
                <input
                  type="text"
                  value={lookupContractId}
                  onChange={(e) => setLookupContractId(e.target.value)}
                  placeholder="e.g. contract-ecommerce-v1"
                  disabled={!isProjectReady || isFetching}
                  className="col-span-2 px-3 py-1.5 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <input
                  type="number"
                  min="1"
                  value={lookupContractVersion}
                  onChange={(e) => setLookupContractVersion(e.target.value)}
                  placeholder="v1"
                  disabled={!isProjectReady || isFetching}
                  className="px-3 py-1.5 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={!isProjectReady || isFetching || !lookupContractId.trim()}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 font-medium text-xs transition-colors shrink-0"
            >
              <Search className="w-3.5 h-3.5" />
              <span>Lookup Contract</span>
            </button>
          </form>
        </div>
      </div>

      {/* Step 2: Contract Validation Report Panel (If draft exists) */}
      {currentContract && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800 mb-4">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-indigo-500" />
              <h4 className="text-sm font-bold text-slate-900 dark:text-white">
                Validation Gate Assessment
              </h4>
              <span className="font-mono text-xs text-slate-500">
                {currentContract.contract_id} (v{currentContract.version})
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => onValidateDraft(currentContract.contract_id, currentContract.version)}
                disabled={isValidating || !isProjectReady}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
              >
                <RotateCw className={`w-3.5 h-3.5 ${isValidating ? 'animate-spin' : ''}`} />
                <span>Re-validate Draft</span>
              </button>
            </div>
          </div>

          {contractValidation ? (
            <div className="space-y-4">
              {contractValidation.is_valid ? (
                <div className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 flex items-start gap-3">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                  <div>
                    <h5 className="text-xs font-bold text-emerald-900 dark:text-emerald-200">
                      Validation Passed ({contractValidation.rules_validated_count} rules checked)
                    </h5>
                    <p className="text-xs text-emerald-700 dark:text-emerald-300 mt-0.5">
                      All candidate rules have verified source provenance, valid syntax, unambiguous conditions, and conformant evaluation boundaries. Contract is eligible for explicit acceptance.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                    <h5 className="text-xs font-bold text-amber-900 dark:text-amber-200">
                      Validation Issues Detected ({contractValidation.issues.length})
                    </h5>
                  </div>
                  <ul className="space-y-2 mt-2">
                    {contractValidation.issues.map((issue, idx) => (
                      <li
                        key={idx}
                        className="text-xs text-amber-800 dark:text-amber-300 flex items-start gap-2 p-2 rounded bg-amber-100/50 dark:bg-amber-900/30"
                      >
                        <span className="font-mono text-[10px] px-1.5 py-0.5 bg-amber-200 dark:bg-amber-950 rounded font-semibold shrink-0">
                          {issue.code}
                        </span>
                        <span>{issue.message}</span>
                        {issue.field && (
                          <span className="text-[10px] text-amber-600 dark:text-amber-400 font-mono">
                            [{issue.field}]
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Explicit Acceptance Gate Button (Disabled if already accepted) */}
              {!isAccepted && (
                <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
                  <span className="text-xs text-slate-500">
                    Acceptance creates an immutable, cryptographically signed policy version.
                  </span>
                  <button
                    type="button"
                    onClick={handleOpenAcceptModal}
                    disabled={isAccepting || !isProjectReady}
                    className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 dark:disabled:bg-slate-800 text-white font-medium text-xs shadow-sm transition-colors"
                  >
                    <Lock className="w-4 h-4" />
                    <span>Explicitly Accept & Freeze Contract</span>
                  </button>
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic">
              Validation status will appear once a draft contract is created or re-validated.
            </p>
          )}
        </div>
      )}

      {/* Step 3: Immutable Accepted Version Inspector */}
      {currentContract && isAccepted && (
        <div className="bg-white dark:bg-slate-900 border border-emerald-300 dark:border-emerald-800/80 rounded-2xl p-6 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-emerald-100 dark:border-emerald-950 mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-100 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
                <Lock className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="text-base font-bold text-slate-900 dark:text-white">
                    {currentContract.contract_id}
                  </h4>
                  <span className="px-2 py-0.5 rounded text-xs font-bold bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300">
                    ACCEPTED (v{currentContract.version})
                  </span>
                </div>
                <p className="text-xs text-slate-500 font-mono mt-0.5">
                  Content Hash: {currentContract.content_hash}
                </p>
              </div>
            </div>

            <div className="text-right text-xs text-slate-500">
              <div className="flex items-center gap-1 justify-end">
                <User className="w-3.5 h-3.5 text-slate-400" />
                <span>Accepted by: <strong>{currentContract.acceptance_metadata?.accepted_by || 'Dev Reviewer'}</strong></span>
              </div>
              <div className="flex items-center gap-1 justify-end mt-0.5">
                <Calendar className="w-3.5 h-3.5 text-slate-400" />
                <span>{currentContract.updated_at ? new Date(currentContract.updated_at).toLocaleString() : 'Accepted'}</span>
              </div>
            </div>
          </div>

          {currentContract.acceptance_metadata?.rationale && (
            <div className="mb-4 p-3 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs">
              <span className="text-[10px] uppercase font-semibold text-slate-400 block mb-0.5">
                Acceptance Rationale
              </span>
              <p className="text-slate-700 dark:text-slate-300 italic">
                "{currentContract.acceptance_metadata.rationale}"
              </p>
            </div>
          )}

          {/* Immutable Policy Rules Inspection (Strictly read-only) */}
          <div className="space-y-3">
            <h5 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
              Immutable Contract Rules ({currentContract.rules?.length || 0})
            </h5>
            <div className="grid gap-2.5">
              {currentContract.rules?.map((rule) => (
                <div
                  key={rule.rule_id}
                  className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-slate-900 dark:text-white">
                        {rule.rule_id}
                      </span>
                      <span className="px-2 py-0.2 rounded text-[10px] font-semibold bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300">
                        {rule.policy_family}
                      </span>
                      <span className="px-2 py-0.2 rounded text-[10px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                        {rule.policy_requirement}
                      </span>
                    </div>
                    <div className="font-mono text-[11px] text-slate-500">
                      Principal: {rule.principal_selector} • Action: {rule.action_selector} • Resource: {rule.resource_selector}
                    </div>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 self-start sm:self-center">
                    Immutable
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Explicit Acceptance Modal */}
      {isAcceptModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm animate-in fade-in duration-150"
        >
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl w-full max-w-lg shadow-2xl p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-emerald-100 dark:bg-emerald-950 text-emerald-600 flex items-center justify-center">
                <Lock className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white">
                  Explicit Contract Acceptance Gate
                </h3>
                <p className="text-xs text-slate-500 font-mono">
                  {currentContract?.contract_id} (v{currentContract?.version})
                </p>
              </div>
            </div>

            <form onSubmit={handleConfirmAccept} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Acceptor Name / Principal ID <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  value={acceptedBy}
                  onChange={(e) => setAcceptedBy(e.target.value)}
                  required
                  disabled={isAccepting}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Acceptance Justification & Audit Rationale
                </label>
                <textarea
                  rows={3}
                  value={rationale}
                  onChange={(e) => setRationale(e.target.value)}
                  placeholder="Explain why this contract draft is validated and approved for adversarial security testing."
                  disabled={isAccepting}
                  className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 text-xs text-amber-800 dark:text-amber-300">
                <strong>Irreversible Action:</strong> Acceptance gates require zero blocking validation issues. Once accepted, this policy contract version becomes read-only and immutable.
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsAcceptModalOpen(false)}
                  disabled={isAccepting}
                  className="px-4 py-2 text-xs font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isAccepting || !acceptedBy.trim()}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white text-xs font-medium transition-colors shadow-sm"
                >
                  {isAccepting ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      <span>Freezing Contract...</span>
                    </>
                  ) : (
                    <>
                      <Lock className="w-3.5 h-3.5" />
                      <span>Accept & Freeze Contract</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
