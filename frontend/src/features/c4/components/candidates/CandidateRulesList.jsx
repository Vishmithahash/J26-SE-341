/**
 * Component 4 (C4) - Candidate Rules List Component
 * Filterable, selectable list of extracted candidate rules with summary metrics and bulk actions.
 */

import React, { useState, useMemo } from 'react';
import {
  Search,
  CheckSquare,
  Square,
  Shield,
  FilePlus,
  ArrowRight,
} from 'lucide-react';
import { CandidateRuleCard } from './CandidateRuleCard';
import { ReviewModal } from './ReviewModal';
import { POLICY_FAMILIES, RULE_REVIEW_STATUSES } from '../../api/types';

export function CandidateRulesList({
  candidates,
  selectedRuleIds,
  onToggleSelectRule,
  onSelectAll,
  onDeselectAll,
  onReviewRule,
  onProceedToContracts,
  isReviewing,
}) {
  const [familyFilter, setFamilyFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');

  // Modal review state
  const [reviewModalState, setReviewModalState] = useState({
    isOpen: false,
    rule: null,
    decision: 'ACCEPTED',
  });

  const handleOpenReview = (rule, decision) => {
    setReviewModalState({
      isOpen: true,
      rule,
      decision,
    });
  };

  const handleCloseReview = () => {
    setReviewModalState({
      isOpen: false,
      rule: null,
      decision: 'ACCEPTED',
    });
  };

  const handleSubmitReview = async (payload) => {
    await onReviewRule(payload);
    handleCloseReview();
  };

  // Metrics
  const metrics = useMemo(() => {
    const total = candidates.length;
    const accepted = candidates.filter((c) => c.review_status === RULE_REVIEW_STATUSES.ACCEPTED).length;
    const rejected = candidates.filter((c) => c.review_status === RULE_REVIEW_STATUSES.REJECTED).length;
    const draft = total - accepted - rejected;
    return { total, accepted, rejected, draft };
  }, [candidates]);

  // Filtered rules
  const filteredRules = useMemo(() => {
    return candidates.filter((rule) => {
      if (familyFilter !== 'ALL' && rule.policy_family !== familyFilter) return false;
      if (statusFilter !== 'ALL' && (rule.review_status || 'DRAFT') !== statusFilter) return false;
      if (searchTerm.trim()) {
        const query = searchTerm.toLowerCase();
        const ruleId = rule.rule_id.toLowerCase();
        const principal = (rule.principal_selector || '').toLowerCase();
        const action = (rule.action_selector || '').toLowerCase();
        const resource = (rule.resource_selector || '').toLowerCase();
        return (
          ruleId.includes(query) ||
          principal.includes(query) ||
          action.includes(query) ||
          resource.includes(query)
        );
      }
      return true;
    });
  }, [candidates, familyFilter, statusFilter, searchTerm]);

  return (
    <div className="space-y-6">
      {/* List Header and Metrics */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded-lg bg-indigo-100 dark:bg-indigo-950/70 text-indigo-600 dark:text-indigo-400 font-bold text-xs flex items-center justify-center">
                3
              </span>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                Candidate Rule Inspection & Review Gate
              </h3>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Inspect derived policy candidates, examine provenance excerpts, and explicitly review before contract inclusion.
            </p>
          </div>

          {/* Quick Metrics */}
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
              Total: {metrics.total}
            </span>
            <span className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300">
              Accepted: {metrics.accepted}
            </span>
            <span className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400">
              Draft: {metrics.draft}
            </span>
            {metrics.rejected > 0 && (
              <span className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300">
                Rejected: {metrics.rejected}
              </span>
            )}
          </div>
        </div>

        {/* Filter controls */}
        <div className="mt-4 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative min-w-[200px]">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search rule ID, selector..."
                className="w-full pl-8 pr-3 py-1.5 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {/* Policy Family Filter */}
            <select
              value={familyFilter}
              onChange={(e) => setFamilyFilter(e.target.value)}
              className="px-3 py-1.5 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="ALL">All Families</option>
              <option value={POLICY_FAMILIES.AUTHORIZATION}>Authorization</option>
              <option value={POLICY_FAMILIES.CONFIDENTIALITY}>Confidentiality</option>
              <option value={POLICY_FAMILIES.INSTRUCTION_AUTHORITY}>Instruction Authority</option>
            </select>

            {/* Review Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-1.5 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="ALL">All Review Statuses</option>
              <option value={RULE_REVIEW_STATUSES.DRAFT}>Draft</option>
              <option value={RULE_REVIEW_STATUSES.ACCEPTED}>Accepted</option>
              <option value={RULE_REVIEW_STATUSES.REJECTED}>Rejected</option>
            </select>
          </div>

          {/* Bulk Selection Actions */}
          {candidates.length > 0 && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onSelectAll}
                className="inline-flex items-center gap-1 text-xs text-slate-600 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 font-medium"
              >
                <CheckSquare className="w-3.5 h-3.5" />
                Select All
              </button>
              <span className="text-slate-300 dark:text-slate-700">|</span>
              <button
                type="button"
                onClick={onDeselectAll}
                className="inline-flex items-center gap-1 text-xs text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white font-medium"
              >
                <Square className="w-3.5 h-3.5" />
                Deselect
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Rules list */}
      {filteredRules.length > 0 ? (
        <div className="space-y-4">
          {filteredRules.map((rule) => (
            <CandidateRuleCard
              key={rule.rule_id}
              rule={rule}
              isSelected={selectedRuleIds.includes(rule.rule_id)}
              onToggleSelect={onToggleSelectRule}
              onOpenReview={handleOpenReview}
              isReviewing={isReviewing}
            />
          ))}

          {/* Bottom Bar: Selected rules summary and Proceed to Contracts */}
          <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-3 shadow-sm">
            <span className="text-xs text-slate-600 dark:text-slate-400">
              <strong>{selectedRuleIds.length}</strong> rule{selectedRuleIds.length === 1 ? '' : 's'} selected for contract drafting.
            </span>
            <button
              type="button"
              onClick={onProceedToContracts}
              disabled={selectedRuleIds.length === 0}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 dark:disabled:bg-slate-800 text-white font-medium text-xs shadow-sm transition-colors"
            >
              <FilePlus className="w-4 h-4" />
              <span>Draft Policy Contract ({selectedRuleIds.length})</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      ) : (
        <div className="text-center py-12 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
          <Shield className="w-10 h-10 mx-auto text-slate-300 dark:text-slate-600 mb-3" />
          <h4 className="text-sm font-bold text-slate-900 dark:text-white mb-1">
            No Candidate Rules Found
          </h4>
          <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm mx-auto">
            {candidates.length === 0
              ? 'Complete Step 1 (Artifact Intake) and Step 2 (Policy Extraction) to derive candidate rules for inspection.'
              : 'No candidate rules match the current family or review filters. Try clearing your search or filter criteria.'}
          </p>
        </div>
      )}

      {/* Review Modal Dialog */}
      <ReviewModal
        isOpen={reviewModalState.isOpen}
        rule={reviewModalState.rule}
        decision={reviewModalState.decision}
        onClose={handleCloseReview}
        onSubmitReview={handleSubmitReview}
        isReviewing={isReviewing}
      />
    </div>
  );
}
