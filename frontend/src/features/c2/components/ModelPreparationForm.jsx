import React, { useState } from 'react';
import {
  FileCode,
  Sparkles,
  Layers,
  Plus,
  Trash2,
  AlertCircle,
  FileCheck,
  CheckCircle2,
  RotateCcw,
} from 'lucide-react';
import { getRefundWorkflowInputTemplate } from '../templates/refundWorkflowTemplate';

const DOMAIN_OPTIONS = [
  { value: 'ecommerce', label: 'E-Commerce' },
  { value: 'booking', label: 'Booking & Reservations' },
  { value: 'flight_booking', label: 'Airlines & Flight Booking' },
  { value: 'lms', label: 'Learning Management System (LMS)' },
  { value: 'custom', label: 'Custom Domain' },
];

const RULE_CATEGORIES = [
  'eligibility',
  'ordering',
  'rejection',
  'effect',
  'invariant',
  'milestone',
];

export const ModelPreparationForm = ({
  projectId,
  onBuildCandidate,
  onCreateDraft,
  isSubmitting = false,
  onCancel,
}) => {
  const [activeTab, setActiveTab] = useState('candidate'); // 'candidate' | 'direct'
  const [jsonMode, setJsonMode] = useState(false);

  // WorkflowInput form state
  const [domain, setDomain] = useState('ecommerce');
  const [workflowId, setWorkflowId] = useState('order_refund_workflow');
  const [name, setName] = useState('Latest Paid Order Refund Workflow');
  const [version, setVersion] = useState('1.0.0');
  const [task, setTask] = useState('Refund my latest paid order.');
  const [autoValidate, setAutoValidate] = useState(true);

  // Business Rules
  const [businessRules, setBusinessRules] = useState([
    {
      rule_id: 'RULE_OWNERSHIP',
      name: 'Customer Ownership',
      description: 'Orders must belong to the requesting customer.',
      category: 'eligibility',
      priority: 1,
    },
    {
      rule_id: 'RULE_ELIGIBILITY_PAID',
      name: 'Paid Order Eligibility',
      description: "Only orders with payment_status == 'PAID' are eligible for refund.",
      category: 'eligibility',
      priority: 1,
    },
  ]);

  // Tool Specifications
  const [toolSpecs, setToolSpecs] = useState([
    {
      tool_name: 'get_customer_orders',
      description: 'Retrieve customer orders with payment status.',
      parameters: [{ name: 'customer_id', type: 'integer', required: true, default: null }],
      return_type: 'list',
      has_side_effects: false,
    },
    {
      tool_name: 'request_refund',
      description: 'Submit a refund request for an eligible order.',
      parameters: [{ name: 'order_id', type: 'integer', required: true, default: null }],
      return_type: 'dict',
      has_side_effects: true,
    },
  ]);

  // Observable State Mappings
  const [stateMappings, setStateMappings] = useState([
    {
      entity_type: 'orders',
      primary_key: 'id',
      observable_fields: ['id', 'customer_id', 'payment_status', 'amount'],
      description: 'Order records observed before/after tool events.',
    },
  ]);

  // Fixture
  const [fixtureId, setFixtureId] = useState('fixture_customer_42_refund');
  const [fixtureDesc, setFixtureDesc] = useState('Fictional customer 42 with orders 501, 502, and 503.');
  const [initialEntitiesJson, setInitialEntitiesJson] = useState(
    JSON.stringify(
      {
        customer: { id: 42, name: 'Alice Smith' },
        orders: {
          501: { id: 501, customer_id: 42, payment_status: 'PAID', amount: 55.0 },
          502: { id: 502, customer_id: 42, payment_status: 'UNPAID', amount: 120.0 },
        },
      },
      null,
      2
    )
  );
  const [protectedStateJson, setProtectedStateJson] = useState(
    JSON.stringify({ order_502_payment_status: 'UNPAID' }, null, 2)
  );

  // Assumptions
  const [assumptionsText, setAssumptionsText] = useState(
    'Synthetic timestamps are ISO8601 strings.\nAbstract tool names represent simulated domain operations.'
  );

  // Raw JSON state for Candidate Tab
  const [candidateRawJson, setCandidateRawJson] = useState('');

  // Direct Draft Tab State
  const [directEfsmJson, setDirectEfsmJson] = useState('');

  const [formError, setFormError] = useState('');
  const [diagnosticsList, setDiagnosticsList] = useState([]);

  // Load canonical refund workflow reference template
  const handleLoadTemplate = () => {
    const template = getRefundWorkflowInputTemplate(projectId);
    setDomain(template.domain);
    setWorkflowId(template.workflow_id);
    setName(template.name);
    setVersion(template.version);
    setTask(template.task);
    setBusinessRules(template.business_rules);
    setToolSpecs(template.tool_specifications);
    setStateMappings(template.observable_state_mappings);
    setFixtureId(template.synthetic_fixture.fixture_id);
    setFixtureDesc(template.synthetic_fixture.description);
    setInitialEntitiesJson(JSON.stringify(template.synthetic_fixture.initial_entities, null, 2));
    setProtectedStateJson(JSON.stringify(template.synthetic_fixture.protected_state, null, 2));
    setAssumptionsText(template.assumptions.join('\n'));
    setCandidateRawJson(JSON.stringify(template, null, 2));
    setFormError('');
    setDiagnosticsList([]);
  };

  // Build the complete WorkflowInputContract object
  const constructWorkflowInputPayload = () => {
    let initialEntities = {};
    let protectedState = {};

    try {
      initialEntities = JSON.parse(initialEntitiesJson);
    } catch {
      throw new Error('Initial Entities must be valid JSON.');
    }

    try {
      protectedState = JSON.parse(protectedStateJson);
    } catch {
      throw new Error('Protected State must be valid JSON.');
    }

    const assumptions = assumptionsText
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean);

    return {
      schema_version: '2026.1',
      project_id: projectId,
      domain,
      workflow_id: workflowId.trim(),
      name: name.trim(),
      version: version.trim() || '1.0.0',
      task: task.trim(),
      business_rules: businessRules,
      tool_specifications: toolSpecs,
      observable_state_mappings: stateMappings,
      synthetic_fixture: {
        fixture_id: fixtureId.trim(),
        description: fixtureDesc.trim(),
        initial_entities: initialEntities,
        protected_state: protectedState,
      },
      assumptions,
    };
  };

  const handleCandidateSubmit = async (e) => {
    e.preventDefault();
    setFormError('');
    setDiagnosticsList([]);

    let payload;
    try {
      if (jsonMode) {
        payload = JSON.parse(candidateRawJson);
        if (!payload.project_id) {
          payload.project_id = projectId;
        }
      } else {
        payload = constructWorkflowInputPayload();
      }
    } catch (err) {
      setFormError(err.message || 'Invalid form or JSON payload.');
      return;
    }

    try {
      await onBuildCandidate(payload, autoValidate);
    } catch (err) {
      if (err.data?.detail?.diagnostics) {
        setDiagnosticsList(err.data.detail.diagnostics);
        setFormError(err.data.detail.message || 'Input validation failed.');
      } else {
        setFormError(err.message || 'Failed to propose and build candidate model.');
      }
    }
  };

  const handleDirectSubmit = async (e) => {
    e.preventDefault();
    setFormError('');
    setDiagnosticsList([]);

    let payload;
    try {
      payload = JSON.parse(directEfsmJson);
      if (!payload.project_id) {
        payload.project_id = projectId;
      }
    } catch (err) {
      setFormError(`Invalid EFSM JSON: ${err.message}`);
      return;
    }

    try {
      await onCreateDraft(payload);
    } catch (err) {
      setFormError(err.message || 'Failed to create draft EFSM model.');
    }
  };

  return (
    <div className="bg-white dark:bg-[#131A26] rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="p-6 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-indigo-100 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-400">
              <Sparkles className="w-4 h-4" />
            </span>
            <h2 className="text-base font-semibold text-slate-900 dark:text-white">
              Model Preparation & Candidate Builder
            </h2>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Construct formal EFSM models via backend deterministic synthesis or direct draft authoring.
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={handleLoadTemplate}
            className="px-3 py-1.5 text-xs font-medium rounded-xl border border-indigo-200 dark:border-indigo-800/80 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 transition-colors flex items-center gap-1.5"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Load Reference Template (E-Commerce Refund)
          </button>
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="px-3 py-1.5 text-xs font-medium rounded-xl border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
          )}
        </div>
      </div>

      {/* Mode Selector Tabs */}
      <div className="flex items-center border-b border-slate-200 dark:border-slate-800 px-6 gap-6 bg-white dark:bg-[#131A26]">
        <button
          type="button"
          onClick={() => {
            setActiveTab('candidate');
            setFormError('');
          }}
          className={`py-3 text-xs font-semibold border-b-2 flex items-center gap-2 transition-colors ${
            activeTab === 'candidate'
              ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
              : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
          }`}
        >
          <Layers className="w-4 h-4" />
          Propose Candidate Model (Workflow Input Contract)
        </button>
        <button
          type="button"
          onClick={() => {
            setActiveTab('direct');
            setFormError('');
          }}
          className={`py-3 text-xs font-semibold border-b-2 flex items-center gap-2 transition-colors ${
            activeTab === 'direct'
              ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
              : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
          }`}
        >
          <FileCode className="w-4 h-4" />
          Direct Draft EFSM Definition (Advanced JSON)
        </button>
      </div>

      {/* Disclaimers & Errors */}
      <div className="p-6 space-y-4">
        {formError && (
          <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-800 dark:text-rose-200 space-y-2">
            <div className="font-semibold flex items-center gap-1.5">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              {formError}
            </div>
            {diagnosticsList.length > 0 && (
              <ul className="list-disc list-inside space-y-1 pl-1 text-[11px] text-rose-700 dark:text-rose-300">
                {diagnosticsList.map((d, i) => (
                  <li key={i}>{d}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* Tab 1: Candidate Builder */}
        {activeTab === 'candidate' && (
          <form onSubmit={handleCandidateSubmit} className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="text-xs text-slate-500 dark:text-slate-400">
                Constructs candidate states, guards, and invariants deterministically without hallucination.
              </div>
              <button
                type="button"
                onClick={() => {
                  if (!jsonMode) {
                    try {
                      const payload = constructWorkflowInputPayload();
                      setCandidateRawJson(JSON.stringify(payload, null, 2));
                    } catch {
                      // leave raw as is
                    }
                  }
                  setJsonMode(!jsonMode);
                }}
                className="text-xs font-medium text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-1"
              >
                {jsonMode ? 'Switch to Structured Form' : 'Switch to Validated Raw JSON View'}
              </button>
            </div>

            {jsonMode ? (
              <div className="space-y-2">
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                  WorkflowInputContract JSON
                </label>
                <textarea
                  rows={18}
                  value={candidateRawJson}
                  onChange={(e) => setCandidateRawJson(e.target.value)}
                  className="w-full p-3 font-mono text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-900 text-slate-100 placeholder-slate-500 focus:ring-2 focus:ring-indigo-500"
                  placeholder="Paste or edit WorkflowInputContract JSON here..."
                  required
                />
              </div>
            ) : (
              <div className="space-y-6">
                {/* Basic Details */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                      Domain <span className="text-rose-500">*</span>
                    </label>
                    <select
                      value={domain}
                      onChange={(e) => setDomain(e.target.value)}
                      className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:ring-2 focus:ring-indigo-500"
                    >
                      {DOMAIN_OPTIONS.map((d) => (
                        <option key={d.value} value={d.value}>
                          {d.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                      Workflow ID <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={workflowId}
                      onChange={(e) => setWorkflowId(e.target.value)}
                      className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white font-mono focus:ring-2 focus:ring-indigo-500"
                      required
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                      Workflow Name <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:ring-2 focus:ring-indigo-500"
                      required
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                      Version <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={version}
                      onChange={(e) => setVersion(e.target.value)}
                      className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white font-mono focus:ring-2 focus:ring-indigo-500"
                      required
                    />
                  </div>
                </div>

                {/* Natural Language Task */}
                <div className="space-y-1.5">
                  <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                    Natural Language Agent Task Prompt <span className="text-rose-500">*</span>
                  </label>
                  <textarea
                    rows={2}
                    value={task}
                    onChange={(e) => setTask(e.target.value)}
                    placeholder="e.g. Refund my latest paid order."
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:ring-2 focus:ring-indigo-500"
                    required
                  />
                </div>

                {/* Business Rules Section */}
                <div className="space-y-3 pt-2 border-t border-slate-200 dark:border-slate-800">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-xs font-semibold text-slate-900 dark:text-white">
                        Domain Business Rules ({businessRules.length})
                      </h3>
                      <p className="text-[11px] text-slate-500">
                        Eligibility, ordering, rejection, and invariant specifications governing state transitions.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() =>
                        setBusinessRules((prev) => [
                          ...prev,
                          {
                            rule_id: `RULE_${Date.now().toString().slice(-4)}`,
                            name: 'New Rule',
                            description: '',
                            category: 'eligibility',
                            priority: 1,
                          },
                        ])
                      }
                      className="px-2.5 py-1 text-xs font-medium rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 flex items-center gap-1"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      Add Rule
                    </button>
                  </div>

                  <div className="space-y-2">
                    {businessRules.map((rule, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40 grid grid-cols-1 sm:grid-cols-12 gap-3 items-start"
                      >
                        <div className="sm:col-span-3 space-y-1">
                          <label className="text-[10px] text-slate-500 font-mono">Rule ID</label>
                          <input
                            type="text"
                            value={rule.rule_id}
                            onChange={(e) => {
                              const updated = [...businessRules];
                              updated[idx].rule_id = e.target.value;
                              setBusinessRules(updated);
                            }}
                            className="w-full px-2 py-1 text-xs rounded border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 font-mono"
                          />
                        </div>
                        <div className="sm:col-span-3 space-y-1">
                          <label className="text-[10px] text-slate-500">Category</label>
                          <select
                            value={rule.category}
                            onChange={(e) => {
                              const updated = [...businessRules];
                              updated[idx].category = e.target.value;
                              setBusinessRules(updated);
                            }}
                            className="w-full px-2 py-1 text-xs rounded border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                          >
                            {RULE_CATEGORIES.map((c) => (
                              <option key={c} value={c}>
                                {c}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="sm:col-span-5 space-y-1">
                          <label className="text-[10px] text-slate-500">Name & Description</label>
                          <input
                            type="text"
                            value={rule.name}
                            placeholder="Rule Name"
                            onChange={(e) => {
                              const updated = [...businessRules];
                              updated[idx].name = e.target.value;
                              setBusinessRules(updated);
                            }}
                            className="w-full px-2 py-1 text-xs rounded border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 mb-1"
                          />
                          <input
                            type="text"
                            value={rule.description}
                            placeholder="Rule Description"
                            onChange={(e) => {
                              const updated = [...businessRules];
                              updated[idx].description = e.target.value;
                              setBusinessRules(updated);
                            }}
                            className="w-full px-2 py-1 text-xs rounded border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                          />
                        </div>
                        <div className="sm:col-span-1 pt-4 text-right">
                          <button
                            type="button"
                            onClick={() =>
                              setBusinessRules((prev) => prev.filter((_, i) => i !== idx))
                            }
                            className="p-1 rounded text-slate-400 hover:text-rose-600 transition-colors"
                            title="Remove rule"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Synthetic Fixture Reference */}
                <div className="space-y-3 pt-2 border-t border-slate-200 dark:border-slate-800">
                  <h3 className="text-xs font-semibold text-slate-900 dark:text-white">
                    Synthetic Fixture Reference & State Isolation
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                        Fixture ID <span className="text-rose-500">*</span>
                      </label>
                      <input
                        type="text"
                        value={fixtureId}
                        onChange={(e) => setFixtureId(e.target.value)}
                        className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white font-mono"
                        required
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                        Fixture Description
                      </label>
                      <input
                        type="text"
                        value={fixtureDesc}
                        onChange={(e) => setFixtureDesc(e.target.value)}
                        className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                        Initial Entities (JSON)
                      </label>
                      <textarea
                        rows={5}
                        value={initialEntitiesJson}
                        onChange={(e) => setInitialEntitiesJson(e.target.value)}
                        className="w-full p-2.5 font-mono text-[11px] rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:ring-2 focus:ring-indigo-500"
                        required
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                        Protected State (JSON)
                      </label>
                      <textarea
                        rows={5}
                        value={protectedStateJson}
                        onChange={(e) => setProtectedStateJson(e.target.value)}
                        className="w-full p-2.5 font-mono text-[11px] rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white focus:ring-2 focus:ring-indigo-500"
                        required
                      />
                    </div>
                  </div>
                </div>

                {/* Assumptions */}
                <div className="space-y-1.5 pt-2 border-t border-slate-200 dark:border-slate-800">
                  <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                    Workflow Assumptions (one per line)
                  </label>
                  <textarea
                    rows={2}
                    value={assumptionsText}
                    onChange={(e) => setAssumptionsText(e.target.value)}
                    className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-900 dark:text-white"
                  />
                </div>
              </div>
            )}

            {/* Auto Validate Checkbox & Submit */}
            <div className="pt-4 border-t border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-700 dark:text-slate-300">
                <input
                  type="checkbox"
                  checked={autoValidate}
                  onChange={(e) => setAutoValidate(e.target.checked)}
                  className="rounded text-indigo-600 focus:ring-indigo-500 dark:bg-slate-900 border-slate-300 dark:border-slate-700"
                />
                Automatically execute structural & bounded semantic validation after candidate construction
              </label>

              <button
                type="submit"
                disabled={isSubmitting}
                className="px-5 py-2.5 text-xs font-semibold rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white flex items-center justify-center gap-2 transition-colors disabled:opacity-50 shadow-sm"
              >
                {isSubmitting ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Synthesizing Candidate Model...
                  </>
                ) : (
                  <>
                    <FileCheck className="w-4 h-4" />
                    Propose & Build Candidate Model
                  </>
                )}
              </button>
            </div>
          </form>
        )}

        {/* Tab 2: Direct Draft EFSM Definition */}
        {activeTab === 'direct' && (
          <form onSubmit={handleDirectSubmit} className="space-y-4">
            <div className="text-xs text-slate-500 dark:text-slate-400">
              Paste or submit a formal, complete <code className="font-mono">EFSMModelDefinition</code> JSON payload directly into the project repository.
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                EFSMModelDefinition JSON
              </label>
              <textarea
                rows={18}
                value={directEfsmJson}
                onChange={(e) => setDirectEfsmJson(e.target.value)}
                placeholder='{ "schema_version": "2026.1", "model_id": "...", "states": [...], "transitions": [...] }'
                required
                className="w-full p-3 font-mono text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-900 text-slate-100 placeholder-slate-500 focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex justify-end">
              <button
                type="submit"
                disabled={isSubmitting}
                className="px-5 py-2.5 text-xs font-semibold rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white flex items-center gap-2 transition-colors disabled:opacity-50"
              >
                {isSubmitting ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Creating Draft...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    Create Draft EFSM Model
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
