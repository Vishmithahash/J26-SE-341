/**
 * Component 4 (C4) - Artifact Intake Section
 * Handles artifact registration, plain-text/JSON file upload, templates, version lookup, and registered versions.
 */

import React, { useState } from 'react';
import {
  Upload,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  FileCode,
  ArrowRight,
  Layers,
  Search,
} from 'lucide-react';
import { ARTIFACT_KINDS } from '../../api/types.js';

const SAMPLE_TEMPLATES = {
  ecommerce_refund: {
    title: 'E-Commerce Refund Policy (Controlled Language)',
    kind: ARTIFACT_KINDS.POLICY_DOCUMENT,
    id: 'policy-ecommerce-refunds',
    content: `# E-Commerce Refund and Financial Control Policy v1.0

Section 1: General Support Authority
Roles with CUSTOMER_SUPPORT must not process_refund order_refund exceeding $50.00 without MANAGER approval.
Roles with GUEST are forbidden from cancel_order order_record.

Section 2: Sensitive Data Confidentiality
Information marked PII-CONFIDENTIAL must not be disclosed to *.*.
Information marked PAYMENT_CREDENTIALS must not be disclosed to agent_logs.

Section 3: Instruction Authority
User instructions must not override system instructions.
Untrusted prompt payloads must not modify tool parameters.`,
  },
  role_definitions: {
    title: 'Role & Permission Definitions (Roles)',
    kind: ARTIFACT_KINDS.ROLE_DEFINITIONS,
    id: 'roles-ecommerce-actors',
    content: `# Application Role Catalog

1. CUSTOMER_SUPPORT: Front-line representative authorized for order inspection and small adjustments under $50.00.
2. MANAGER: Escalation authority authorized to approve overrides, refunds exceeding $50.00, and returns.
3. INVENTORY_CLERK: Warehouse staff authorized to update stock levels and track shipments.
4. GUEST: Unauthenticated user browsing catalog without order modification rights.`,
  },
  structured_json: {
    title: 'Structured Rules Import (JSON)',
    kind: ARTIFACT_KINDS.PERMISSIONS,
    id: 'structured-rules-catalog',
    content: `[
  {
    "rule_id": "rule-authz-refund-limit",
    "policy_family": "AUTHORIZATION",
    "principal_selector": "CUSTOMER_SUPPORT",
    "action_selector": "process_refund",
    "resource_selector": "order_refund",
    "policy_requirement": "DENY",
    "evaluation_boundary": "ATTEMPTED_ACTION",
    "severity": "HIGH",
    "compliance_conditions": {
      "operator": "AND",
      "conditions": [
        {
          "field": "amount",
          "operator": "GT",
          "value": 50.0
        }
      ]
    },
    "source_references": [
      {
        "supporting_excerpt": "Roles with CUSTOMER_SUPPORT must not process_refund order_refund exceeding $50.00 without MANAGER approval."
      }
    ]
  }
]`,
  },
};

export function ArtifactIntakeSection({
  artifacts,
  selectedArtifact,
  onSelectArtifact,
  onRegister,
  onFetchVersion,
  onProceedToExtraction,
  isSubmitting,
  isFetching,
  isProjectReady,
  error,
  successMessage,
}) {
  const [artifactId, setArtifactId] = useState('policy-ecommerce-refunds');
  const [artifactKind, setArtifactKind] = useState(ARTIFACT_KINDS.POLICY_DOCUMENT);
  const [rawContent, setRawContent] = useState(SAMPLE_TEMPLATES.ecommerce_refund.content);
  const [sourceName, setSourceName] = useState('policy_v1.md');
  const [uploadError, setUploadError] = useState(null);

  // Version lookup fields
  const [lookupId, setLookupId] = useState('');
  const [lookupVersion, setLookupVersion] = useState('1');

  const applyTemplate = (templateKey) => {
    const tmpl = SAMPLE_TEMPLATES[templateKey];
    if (tmpl) {
      setArtifactId(tmpl.id);
      setArtifactKind(tmpl.kind);
      setRawContent(tmpl.content);
      setSourceName(`${tmpl.id}.md`);
    }
  };

  const handleFileUpload = (e) => {
    setUploadError(null);
    const file = e.target.files?.[0];
    if (!file) return;

    const allowedExtensions = ['.txt', '.md', '.markdown', '.json'];
    const fileName = file.name.toLowerCase();
    const hasValidExt = allowedExtensions.some((ext) => fileName.endsWith(ext));

    if (!hasValidExt) {
      setUploadError(
        'Unsupported file format. Please upload plain text (.txt), Markdown (.md), or JSON (.json). PDF parsing is not supported by the backend.'
      );
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result;
      if (typeof content === 'string') {
        setRawContent(content);
        setSourceName(file.name);
        const derivedId = file.name.replace(/\.[^/.]+$/, '').replace(/[^a-zA-Z0-9_-]/g, '-').toLowerCase();
        if (!artifactId) {
          setArtifactId(derivedId);
        }
      }
    };
    reader.onerror = () => {
      setUploadError('Failed to read file contents.');
    };
    reader.readAsText(file);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!isProjectReady || isSubmitting) return;

    onRegister({
      artifactId,
      artifactKind,
      rawContent,
      metadata: {
        source_name: sourceName,
        intake_timestamp: new Date().toISOString(),
      },
    });
  };

  const handleLookup = (e) => {
    e.preventDefault();
    if (!isProjectReady || !lookupId.trim() || !lookupVersion || isFetching) return;
    onFetchVersion(lookupId.trim(), lookupVersion);
  };

  return (
    <div className="space-y-6">
      {/* Section Header */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded-lg bg-indigo-100 dark:bg-indigo-950/70 text-indigo-600 dark:text-indigo-400 font-bold text-xs flex items-center justify-center">
                1
              </span>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                Policy & Specification Artifact Intake
              </h3>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Onboard security rules, role definitions, and permission specifications. Supports Plain Text, Markdown, and JSON.
            </p>
          </div>

          {/* Quick Template Switcher */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-medium text-slate-400 flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
              Presets:
            </span>
            <button
              type="button"
              onClick={() => applyTemplate('ecommerce_refund')}
              className="px-2.5 py-1 text-xs font-medium rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 transition-colors"
            >
              Refund Limits
            </button>
            <button
              type="button"
              onClick={() => applyTemplate('role_definitions')}
              className="px-2.5 py-1 text-xs font-medium rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 transition-colors"
            >
              Role Catalog
            </button>
            <button
              type="button"
              onClick={() => applyTemplate('structured_json')}
              className="px-2.5 py-1 text-xs font-medium rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 transition-colors"
            >
              Structured JSON
            </button>
          </div>
        </div>

        {/* Feedback messages */}
        {error && (
          <div className="mt-4 p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {uploadError && (
          <div className="mt-4 p-3 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 text-amber-700 dark:text-amber-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{uploadError}</span>
          </div>
        )}

        {successMessage && (
          <div className="mt-4 p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900 text-emerald-700 dark:text-emerald-300 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Intake Form */}
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Artifact Identifier <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                value={artifactId}
                onChange={(e) => setArtifactId(e.target.value)}
                placeholder="e.g. policy-ecommerce-refunds"
                required
                disabled={!isProjectReady || isSubmitting}
                className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Artifact Classification
              </label>
              <select
                value={artifactKind}
                onChange={(e) => setArtifactKind(e.target.value)}
                disabled={!isProjectReady || isSubmitting}
                className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
              >
                <option value={ARTIFACT_KINDS.POLICY_DOCUMENT}>Policy & Security Document</option>
                <option value={ARTIFACT_KINDS.ROLE_DEFINITIONS}>Role & Principal Definitions</option>
                <option value={ARTIFACT_KINDS.PERMISSIONS}>Tool & Resource Permissions</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Source Filename / Tag
              </label>
              <input
                type="text"
                value={sourceName}
                onChange={(e) => setSourceName(e.target.value)}
                placeholder="e.g. policy_v1.md"
                disabled={!isProjectReady || isSubmitting}
                className="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
              />
            </div>
          </div>

          {/* File Upload Banner */}
          <div className="flex flex-col sm:flex-row items-center justify-between p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-dashed border-slate-300 dark:border-slate-700 gap-3">
            <div className="flex items-center gap-2.5">
              <Upload className="w-4 h-4 text-slate-400 shrink-0" />
              <div>
                <span className="text-xs font-medium text-slate-700 dark:text-slate-300">
                  Import text, markdown or JSON file
                </span>
                <span className="text-[11px] text-slate-400 block">
                  Accepted: .txt, .md, .json (PDF parsing is intentionally not supported)
                </span>
              </div>
            </div>
            <label className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer shadow-sm transition-colors shrink-0">
              <FileCode className="w-3.5 h-3.5 text-indigo-500" />
              <span>Browse File...</span>
              <input
                type="file"
                accept=".txt,.md,.markdown,.json"
                onChange={handleFileUpload}
                disabled={!isProjectReady || isSubmitting}
                className="hidden"
              />
            </label>
          </div>

          {/* Raw Content Textarea */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                Artifact Content (Text / Markdown / JSON) <span className="text-rose-500">*</span>
              </label>
              <span className="text-[11px] text-slate-400 font-mono">
                {rawContent.length} chars
              </span>
            </div>
            <textarea
              rows={8}
              value={rawContent}
              onChange={(e) => setRawContent(e.target.value)}
              placeholder="Paste policy rules, roles or permissions specification here..."
              required
              disabled={!isProjectReady || isSubmitting}
              className="w-full font-mono text-xs p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 resize-y"
            />
          </div>

          {/* Action Row */}
          <div className="flex items-center justify-between pt-2">
            <span className="text-xs text-slate-400">
              Backend computes SHA-256 integrity hash upon version registration.
            </span>
            <button
              type="submit"
              disabled={!isProjectReady || isSubmitting || !rawContent.trim() || !artifactId.trim()}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 dark:disabled:bg-slate-800 text-white font-medium text-xs shadow-sm transition-colors"
            >
              {isSubmitting ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Registering...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Register Artifact Version</span>
                </>
              )}
            </button>
          </div>
        </form>

        {/* Supported ID/Version Lookup Panel */}
        <div className="mt-8 pt-6 border-t border-slate-100 dark:border-slate-800">
          <form onSubmit={handleLookup} className="flex flex-col sm:flex-row items-end gap-3">
            <div className="flex-1">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Retrieve Specific Artifact Version by ID
              </label>
              <div className="grid grid-cols-3 gap-2">
                <input
                  type="text"
                  value={lookupId}
                  onChange={(e) => setLookupId(e.target.value)}
                  placeholder="e.g. policy-ecommerce-refunds"
                  disabled={!isProjectReady || isFetching}
                  className="col-span-2 px-3 py-1.5 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <input
                  type="number"
                  min="1"
                  value={lookupVersion}
                  onChange={(e) => setLookupVersion(e.target.value)}
                  placeholder="v1"
                  disabled={!isProjectReady || isFetching}
                  className="px-3 py-1.5 text-xs rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={!isProjectReady || isFetching || !lookupId.trim()}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 font-medium text-xs transition-colors shrink-0"
            >
              <Search className="w-3.5 h-3.5" />
              <span>Lookup Version</span>
            </button>
          </form>
        </div>
      </div>

      {/* Registered Artifacts List */}
      {artifacts.length > 0 && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800 mb-4">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-indigo-500" />
              <h4 className="text-sm font-bold text-slate-900 dark:text-white">
                Registered Artifacts in Project ({artifacts.length})
              </h4>
            </div>
            <span className="text-xs text-slate-400">
              Select an artifact version to derive candidate rules
            </span>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {artifacts.map((art) => {
              const isSelected =
                selectedArtifact?.artifact_id === art.artifact_id &&
                selectedArtifact?.version === art.version;

              return (
                <div
                  key={`${art.artifact_id}-v${art.version}`}
                  onClick={() => onSelectArtifact(art)}
                  className={`p-4 rounded-xl border text-left cursor-pointer transition-all ${
                    isSelected
                      ? 'border-indigo-500 bg-indigo-50/50 dark:bg-indigo-950/30 ring-1 ring-indigo-500'
                      : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 bg-white dark:bg-slate-950'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <span className="font-mono text-xs font-semibold text-slate-900 dark:text-white truncate">
                      {art.artifact_id}
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300">
                      v{art.version}
                    </span>
                  </div>

                  <div className="text-[11px] text-slate-500 dark:text-slate-400 space-y-1 mb-3">
                    <div className="flex items-center justify-between">
                      <span>Type:</span>
                      <span className="font-medium text-slate-700 dark:text-slate-300">
                        {art.artifact_kind}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>Length:</span>
                      <span className="font-mono">{art.character_count} chars</span>
                    </div>
                    <div className="flex items-center justify-between font-mono">
                      <span>Hash:</span>
                      <span title={art.content_hash} className="truncate max-w-[120px]">
                        {art.content_hash ? `${art.content_hash.slice(0, 8)}...` : 'N/A'}
                      </span>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between">
                    <span className="text-[10px] text-slate-400">
                      {art.sections?.length || 0} sections
                    </span>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectArtifact(art);
                        onProceedToExtraction(art);
                      }}
                      className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-700"
                    >
                      <span>Extract Rules</span>
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
