import React, { useState, useEffect, useMemo } from 'react';
import {
  ListFilter,
  CheckCircle,
  XCircle,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  ShieldAlert,
  Database,
  Lock,
  Layers,
  Search,
  ArrowRight,
  Send,
  Eye,
} from 'lucide-react';
import { c1Api } from './c1Api';

export const CandidateInspector = ({
  projectId,
  jobId,
  generationSummary,
  onSuitePromoted,
}) => {
  const [candidates, setCandidates] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  // Filters
  const [validityFilter, setValidityFilter] = useState('ALL'); // 'ALL', 'VALID', 'INVALID'
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedCaseId, setExpandedCaseId] = useState(null);

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 6;

  // Promotion Modal
  const [showPromoteModal, setShowPromoteModal] = useState(false);
  const [suiteId, setSuiteId] = useState('');
  const [suiteName, setSuiteName] = useState('');
  const [isPromoting, setIsPromoting] = useState(false);
  const [promotionResult, setPromotionResult] = useState(null);
  const [promoteError, setPromoteError] = useState(null);

  // Fetch candidates
  useEffect(() => {
    let isCancelled = false;
    if (!jobId || !projectId) return;

    const fetchCandidates = async () => {
      setIsLoading(true);
      setErrorMsg(null);
      try {
        const list = await c1Api.getJobCandidates(projectId, jobId, false);
        if (!isCancelled) {
          setCandidates(list || []);
          if (list && list.length > 0) {
            setExpandedCaseId(list[0].case_id);
          }
        }
      } catch (err) {
        if (!isCancelled) {
          setErrorMsg(err.message || 'Failed to fetch candidate cases.');
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    };

    fetchCandidates();

    return () => {
      isCancelled = true;
    };
  }, [projectId, jobId]);

  // Filtered list
  const filteredCandidates = useMemo(() => {
    return candidates.filter((c) => {
      if (validityFilter === 'VALID' && !c.is_valid) return false;
      if (validityFilter === 'INVALID' && c.is_valid) return false;
      if (categoryFilter !== 'ALL' && c.category !== categoryFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchId = c.case_id.toLowerCase().includes(q);
        const matchPrompt = c.agent_task_prompt.toLowerCase().includes(q);
        if (!matchId && !matchPrompt) return false;
      }
      return true;
    });
  }, [candidates, validityFilter, categoryFilter, searchQuery]);

  // Paginated slice
  const paginatedCandidates = useMemo(() => {
    const startIndex = (currentPage - 1) * pageSize;
    return filteredCandidates.slice(startIndex, startIndex + pageSize);
  }, [filteredCandidates, currentPage]);

  const totalPages = Math.ceil(filteredCandidates.length / pageSize) || 1;

  const validCandidatesCount = useMemo(() => {
    return candidates.filter((c) => c.is_valid && !c.rejection_reason).length;
  }, [candidates]);

  // Handle Suite Promotion
  const handlePromoteSuite = async (e) => {
    e.preventDefault();
    if (!suiteId.trim() || !suiteName.trim()) {
      setPromoteError('Both Suite ID and Suite Name are required.');
      return;
    }

    setIsPromoting(true);
    setPromoteError(null);

    try {
      const suite = await c1Api.promoteJobToSuite(projectId, jobId, {
        suiteId,
        suiteName,
      });
      setPromotionResult(suite);
      setShowPromoteModal(false);
      if (onSuitePromoted) {
        onSuitePromoted(suite);
      }
    } catch (err) {
      setPromoteError(err.message || 'Failed to promote candidates to accepted suite.');
    } finally {
      setIsPromoting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header with Promotion CTA */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
        <div>
          <h2 className="text-base font-semibold text-slate-900 dark:text-white flex items-center gap-2">
            <Layers className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
            Generated Candidate Cases &amp; Validation Inspection
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Inspect generated tasks, fixture preparation plans, expected tool constraints, and rejection reasons
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-600 dark:text-slate-400">
            Valid Candidates: <strong className="text-emerald-600 dark:text-emerald-400 font-semibold">{validCandidatesCount}</strong> / {candidates.length}
          </span>
          <button
            type="button"
            disabled={validCandidatesCount === 0}
            onClick={() => {
              setSuiteId(`suite_${jobId.slice(0, 8)}`);
              setSuiteName('Accepted Tool-Call Test Suite');
              setShowPromoteModal(true);
            }}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm disabled:opacity-50"
          >
            <Lock className="w-3.5 h-3.5" />
            Promote to Accepted Suite
          </button>
        </div>
      </div>

      {/* Promotion Result Alert */}
      {promotionResult && (
        <div className="flex items-center justify-between p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-300">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 flex-shrink-0" />
            <span>
              Successfully created and frozen Accepted Suite: <strong>{promotionResult.suite_id}</strong> (v{promotionResult.version}).
            </span>
          </div>
        </div>
      )}

      {errorMsg && (
        <div className="flex items-center gap-2 p-3 text-xs rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-300">
          <XCircle className="w-4 h-4 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <div className="flex flex-wrap items-center gap-2">
          {/* Validity Filter */}
          <div className="flex rounded-lg border border-slate-200 dark:border-slate-700 p-0.5 bg-slate-50 dark:bg-slate-800 text-xs">
            {['ALL', 'VALID', 'INVALID'].map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => {
                  setValidityFilter(f);
                  setCurrentPage(1);
                }}
                className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                  validityFilter === f
                    ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-xs'
                    : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
                }`}
              >
                {f === 'ALL' ? 'All Candidates' : f === 'VALID' ? 'Valid Only' : 'Invalid / Rejected'}
              </button>
            ))}
          </div>

          {/* Category Filter */}
          <select
            value={categoryFilter}
            onChange={(e) => {
              setCategoryFilter(e.target.value);
              setCurrentPage(1);
            }}
            className="px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200"
          >
            <option value="ALL">All Categories</option>
            <option value="CORRECT_BEHAVIOUR">Correct Behaviour</option>
            <option value="WRONG_TOOL_SELECTION">Wrong Tool Selection</option>
            <option value="MISSING_ARGUMENTS">Missing Arguments</option>
            <option value="MALFORMED_ARGUMENT_NAMES_OR_TYPES">Malformed Arguments</option>
            <option value="INCORRECT_ARGUMENT_VALUES">Incorrect Argument Values</option>
            <option value="CONTEXTUAL_SOURCE_MISMATCH">Contextual Source Mismatch</option>
            <option value="INSUFFICIENT_EVIDENCE">Insufficient Evidence</option>
          </select>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1);
            }}
            placeholder="Search prompt or Case ID..."
            className="w-full md:w-64 pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
          />
        </div>
      </div>

      {/* Candidate List */}
      {isLoading ? (
        <div className="p-12 text-center text-slate-500 text-xs">
          <div className="w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          Loading candidate cases...
        </div>
      ) : filteredCandidates.length === 0 ? (
        <div className="p-8 text-center rounded-xl border border-dashed border-slate-200 dark:border-slate-800 text-slate-400 text-xs">
          No candidates match the selected filters.
        </div>
      ) : (
        <div className="space-y-3">
          {paginatedCandidates.map((candidate) => {
            const isExpanded = expandedCaseId === candidate.case_id;
            return (
              <div
                key={candidate.case_id}
                className={`rounded-xl border transition-all ${
                  isExpanded
                    ? 'border-indigo-300 dark:border-indigo-800/80 bg-white dark:bg-slate-900 shadow-xs'
                    : 'border-slate-200 dark:border-slate-800 bg-white/70 dark:bg-slate-900/60 hover:border-slate-300 dark:hover:border-slate-700'
                }`}
              >
                {/* Collapsible Header */}
                <div
                  onClick={() => setExpandedCaseId(isExpanded ? null : candidate.case_id)}
                  className="flex items-center justify-between p-3.5 cursor-pointer select-none"
                >
                  <div className="flex items-center gap-3">
                    <button type="button" className="text-slate-400">
                      {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                    </button>

                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold font-mono text-slate-900 dark:text-white">
                          {candidate.case_id}
                        </span>
                        <span className="px-2 py-0.5 text-[10px] font-medium rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                          {candidate.category}
                        </span>
                      </div>
                      <p className="text-xs text-slate-600 dark:text-slate-400 line-clamp-1 mt-0.5">
                        {candidate.agent_task_prompt}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {candidate.is_valid && !candidate.rejection_reason ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-semibold rounded-full bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                        <CheckCircle className="w-3 h-3" /> Valid
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-semibold rounded-full bg-red-50 dark:bg-red-950/60 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800">
                        <XCircle className="w-3 h-3" /> Rejected
                      </span>
                    )}
                  </div>
                </div>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="px-4 pb-4 pt-1 border-t border-slate-100 dark:border-slate-800/80 space-y-4">
                    {/* Rejection / Validation Banner if invalid */}
                    {(!candidate.is_valid || candidate.rejection_reason) && (
                      <div className="p-3 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-xs text-red-800 dark:text-red-300 space-y-1">
                        <div className="font-semibold flex items-center gap-1.5">
                          <ShieldAlert className="w-3.5 h-3.5" />
                          Rejection Reason: {candidate.rejection_reason || 'Validation issues detected'}
                        </div>
                        {candidate.validation_issues && candidate.validation_issues.length > 0 && (
                          <ul className="list-disc list-inside text-[11px] space-y-0.5 text-red-700 dark:text-red-400">
                            {candidate.validation_issues.map((iss, i) => (
                              <li key={i}>
                                <strong>{iss.rule_id}:</strong> {iss.message}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}

                    {/* Task Prompt and Requirements */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="md:col-span-2 space-y-1.5">
                        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                          Agent-Facing Task Prompt
                        </span>
                        <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/70 text-xs text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-750">
                          {candidate.agent_task_prompt}
                        </div>
                      </div>

                      <div className="space-y-1.5">
                        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                          Justifying Requirements
                        </span>
                        <div className="flex flex-wrap gap-1">
                          {candidate.requirement_refs && candidate.requirement_refs.length > 0 ? (
                            candidate.requirement_refs.map((ref) => (
                              <span
                                key={ref}
                                className="px-2 py-0.5 text-[11px] font-mono rounded bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800"
                              >
                                {ref}
                              </span>
                            ))
                          ) : (
                            <span className="text-xs text-slate-400">None specified</span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Expected Tool Calls & Constraints */}
                    <div className="space-y-2">
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                        Expected Tool-Call Constraints &amp; Evidence Requirements
                      </span>

                      <div className="space-y-2">
                        {candidate.expected_tool_calls && candidate.expected_tool_calls.length > 0 ? (
                          candidate.expected_tool_calls.map((spec, sIdx) => (
                            <div
                              key={sIdx}
                              className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40 text-xs space-y-2"
                            >
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <strong className="font-mono text-slate-900 dark:text-white">
                                    {spec.tool_name}
                                  </strong>
                                  {spec.is_forbidden ? (
                                    <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-red-100 dark:bg-red-950 text-red-700 dark:text-red-400">
                                      FORBIDDEN
                                    </span>
                                  ) : (
                                    <span className="text-[11px] text-slate-500 dark:text-slate-400">
                                      (Expected Count: {spec.min_count} - {spec.max_count ?? '∞'})
                                    </span>
                                  )}
                                </div>
                              </div>

                              {/* Argument Constraints */}
                              {spec.argument_constraints && spec.argument_constraints.length > 0 && (
                                <div className="pl-3 border-l-2 border-indigo-300 dark:border-indigo-700 space-y-1">
                                  <div className="text-[11px] font-medium text-slate-700 dark:text-slate-300">
                                    Argument Rules:
                                  </div>
                                  {spec.argument_constraints.map((ac, acIdx) => (
                                    <div key={acIdx} className="text-[11px] text-slate-600 dark:text-slate-400 font-mono">
                                      • <strong className="text-slate-800 dark:text-slate-200">{ac.field_path}</strong>: {ac.presence_requirement}
                                      {ac.operator && (
                                        <span> | {ac.operator} ({JSON.stringify(ac.expected_value)})</span>
                                      )}
                                      {ac.source_relationship && (
                                        <span className="text-indigo-600 dark:text-indigo-400">
                                          {' '}
                                          ← source: {ac.source_relationship.source_record_id}.{ac.source_relationship.source_path} ({ac.source_relationship.relationship_type})
                                        </span>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          ))
                        ) : (
                          <div className="text-xs text-slate-400 italic">No specific expected tools required.</div>
                        )}
                      </div>
                    </div>

                    {/* Fixture Preparation Plan */}
                    {candidate.fixture_plan && (
                      <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40 text-xs space-y-1">
                        <div className="flex items-center gap-1.5 font-semibold text-slate-800 dark:text-slate-200">
                          <Database className="w-3.5 h-3.5 text-indigo-500" />
                          Synthetic Fixture Preparation Plan
                        </div>
                        <div className="text-[11px] text-slate-600 dark:text-slate-400">
                          Fixture Ref: <strong>{candidate.fixture_plan.fixture_capability_ref}</strong> | Static Feasibility: {candidate.fixture_plan.static_feasibility ? 'Yes' : 'No'}
                        </div>
                        {candidate.fixture_plan.synthetic_records && candidate.fixture_plan.synthetic_records.length > 0 && (
                          <div className="text-[11px] text-slate-500 dark:text-slate-400 pt-1">
                            Synthetic Records: {candidate.fixture_plan.synthetic_records.map((r) => `${r.record_type} [${r.record_id}]`).join(', ')}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-3 border-t border-slate-200 dark:border-slate-800 text-xs">
              <span className="text-slate-500 dark:text-slate-400">
                Page {currentPage} of {totalPages} ({filteredCandidates.length} total)
              </span>
              <div className="flex gap-1">
                <button
                  type="button"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  className="px-2.5 py-1 rounded border border-slate-300 dark:border-slate-700 disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={currentPage === totalPages}
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  className="px-2.5 py-1 rounded border border-slate-300 dark:border-slate-700 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Promotion Modal */}
      {showPromoteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="w-full max-w-md p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <Lock className="w-4 h-4 text-emerald-600" />
                Promote Valid Candidates to Accepted Suite
              </h3>
              <button
                type="button"
                onClick={() => setShowPromoteModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-500 dark:text-slate-400">
              Only valid candidates ({validCandidatesCount} cases) will be selected. The suite and its configuration will be immutably locked and assigned a cryptographic content hash.
            </p>

            {promoteError && (
              <div className="p-2.5 rounded bg-red-50 text-red-700 dark:bg-red-950/60 dark:text-red-400 text-xs">
                {promoteError}
              </div>
            )}

            <form onSubmit={handlePromoteSuite} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Suite Identifier (Unique) <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={suiteId}
                  onChange={(e) => setSuiteId(e.target.value)}
                  placeholder="e.g. suite_c1_refunds_v1"
                  className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Suite Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={suiteName}
                  onChange={(e) => setSuiteName(e.target.value)}
                  placeholder="e.g. Tool Call Correctness Accepted Suite"
                  className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowPromoteModal(false)}
                  className="px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isPromoting}
                  className="px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-50"
                >
                  {isPromoting ? 'Locking Suite...' : 'Lock and Freeze Suite'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
