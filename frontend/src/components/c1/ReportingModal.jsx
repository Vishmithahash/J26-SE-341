import React, { useState, useEffect } from 'react';
import {
  FileDown,
  FileSpreadsheet,
  BarChart2,
  CheckCircle,
  XCircle,
  Layers,
  Database,
  Calendar,
  Clock,
  Sparkles,
  Info,
  ShieldCheck,
  RefreshCw,
  Search,
} from 'lucide-react';
import { c1Api } from './c1Api';

export const ReportingModal = ({
  projectId,
  activeRunId,
  onClose,
  correctionEnabled = true,
}) => {
  const [activeTab, setActiveTab] = useState('export'); // 'export', 'research'

  // Export State
  const [reportItems, setReportItems] = useState([]);
  const [totalReportItems, setTotalReportItems] = useState(0);
  const [isLoadingReport, setIsLoadingReport] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState(null);

  // Research Metrics State
  const [selectedSplit, setSelectedSplit] = useState('train_dev');
  const [metricsReport, setMetricsReport] = useState(null);
  const [referenceLabels, setReferenceLabels] = useState([]);
  const [isLoadingMetrics, setIsLoadingMetrics] = useState(false);
  const [metricsError, setMetricsError] = useState(null);

  // Load preview workflow report items
  useEffect(() => {
    let isCancelled = false;
    if (!projectId) return;

    const fetchReport = async () => {
      setIsLoadingReport(true);
      setExportError(null);
      try {
        const rep = await c1Api.getWorkflowReport(projectId, {
          run_id: activeRunId || null,
          limit: 15,
        });
        if (!isCancelled && rep) {
          setReportItems(rep.items || []);
          setTotalReportItems(rep.total_count || 0);
        }
      } catch (err) {
        if (!isCancelled) {
          setExportError(err.message || 'Failed to preview workflow report.');
        }
      } finally {
        if (!isCancelled) {
          setIsLoadingReport(false);
        }
      }
    };

    fetchReport();

    return () => {
      isCancelled = true;
    };
  }, [projectId, activeRunId]);

  // Load research labels & metrics on tab switch
  useEffect(() => {
    let isCancelled = false;
    if (activeTab === 'research' && projectId) {
      const fetchLabels = async () => {
        try {
          const labels = await c1Api.listReferenceLabels(projectId, {
            dataset_split: selectedSplit,
          });
          if (!isCancelled) {
            setReferenceLabels(labels || []);
          }
        } catch {
          // Handled silently
        }
      };
      fetchLabels();
    }
    return () => {
      isCancelled = true;
    };
  }, [activeTab, projectId, selectedSplit]);

  // Handle Export Download
  const handleDownloadExport = async (format) => {
    setIsExporting(true);
    setExportError(null);
    try {
      await c1Api.exportWorkflowReport(projectId, {
        runId: activeRunId || null,
        format,
      });
    } catch (err) {
      setExportError(err.message || `Export download failed for ${format}.`);
    } finally {
      setIsExporting(false);
    }
  };

  // Compute Research Metrics
  const handleComputeMetrics = async () => {
    setIsLoadingMetrics(true);
    setMetricsError(null);
    try {
      const report = await c1Api.computeResearchMetrics(projectId, {
        runId: activeRunId || null,
        datasetSplit: selectedSplit,
      });
      setMetricsReport(report);
    } catch (err) {
      setMetricsError(
        err.message ||
          `No reference labels found for dataset split '${selectedSplit}'. Import ground truth labels before computing accuracy metrics.`
      );
    } finally {
      setIsLoadingMetrics(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
      <div className="w-full max-w-4xl max-h-[85vh] flex flex-col p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl">
        {/* Modal Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
              <FileDown className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                Component 1 Reports &amp; Research Metrics
              </h3>
              <p className="text-xs text-slate-500">
                End-to-end workflow audit reports and ground-truth research evaluation
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-lg font-bold"
          >
            ✕
          </button>
        </div>

        {/* Modal Tabs */}
        <div className="flex space-x-2 border-b border-slate-200 dark:border-slate-800 pt-3 pb-2 text-xs">
          <button
            type="button"
            onClick={() => setActiveTab('export')}
            className={`px-3 py-1.5 font-semibold rounded-lg transition-colors ${
              activeTab === 'export'
                ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
            }`}
          >
            1. Workflow Export (JSON / CSV)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('research')}
            className={`px-3 py-1.5 font-semibold rounded-lg transition-colors ${
              activeTab === 'research'
                ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
            }`}
          >
            2. Documented Research Metrics &amp; Baselines
          </button>
        </div>

        {/* Tab 1: Export View */}
        {activeTab === 'export' && (
          <div className="flex-1 overflow-y-auto space-y-4 py-4 text-xs">
            {exportError && (
              <div className="p-3 rounded-lg bg-red-50 text-red-700 text-xs border border-red-200">
                {exportError}
              </div>
            )}

            <div className="flex items-center justify-between p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800">
              <div>
                <span className="font-semibold text-slate-800 dark:text-slate-200 block">
                  Export Workflow Audit Report
                </span>
                <span className="text-[11px] text-slate-500">
                  Total Records: <strong>{totalReportItems}</strong> case executions across all pipeline stages.
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleDownloadExport('JSON')}
                  disabled={isExporting}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 font-medium rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-100 disabled:opacity-50"
                >
                  <FileDown className="w-3.5 h-3.5" />
                  Export JSON
                </button>

                <button
                  type="button"
                  onClick={() => handleDownloadExport('CSV')}
                  disabled={isExporting}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm disabled:opacity-50"
                >
                  <FileSpreadsheet className="w-3.5 h-3.5" />
                  Export Tabular CSV
                </button>
              </div>
            </div>

            {/* Preview Table */}
            <div className="space-y-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
                Report Items Preview (First 15 records)
              </span>

              {isLoadingReport ? (
                <div className="p-8 text-center text-slate-400">
                  <div className="w-5 h-5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                  Loading report records...
                </div>
              ) : reportItems.length === 0 ? (
                <div className="p-6 text-center text-slate-400 border border-dashed rounded-lg">
                  No execution records available to export.
                </div>
              ) : (
                <div className="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-xl">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-[11px] text-slate-500">
                      <tr>
                        <th className="py-2 px-3">Case ID</th>
                        <th className="py-2 px-3">Verdict</th>
                        <th className="py-2 px-3">Root Cause</th>
                        {correctionEnabled && <th className="py-2 px-3">Candidate Fix</th>}
                        {correctionEnabled && <th className="py-2 px-3">Verified</th>}
                        <th className="py-2 px-3">Review</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {reportItems.map((item) => (
                        <tr key={item.case_id} className="hover:bg-slate-50/50">
                          <td className="py-2 px-3 font-mono font-medium text-slate-800 dark:text-slate-200">
                            {item.case_id}
                          </td>
                          <td className="py-2 px-3">
                            <span
                              className={`px-1.5 py-0.5 text-[10px] font-bold rounded ${
                                item.verdict === 'PASS'
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : item.verdict === 'FAIL'
                                  ? 'bg-red-100 text-red-800'
                                  : 'bg-amber-100 text-amber-800'
                              }`}
                            >
                              {item.verdict}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-[11px] text-slate-600 dark:text-slate-400">
                            {item.cause_category || 'N/A'}
                          </td>
                          {correctionEnabled && (
                            <td className="py-2 px-3 font-mono text-[10px] text-slate-500">
                              {item.candidate_patch_hash?.slice(0, 8) || 'None'}
                            </td>
                          )}
                          {correctionEnabled && (
                            <td className="py-2 px-3">
                              {item.is_verified ? (
                                <span className="text-emerald-600 font-semibold">Yes</span>
                              ) : (
                                <span className="text-slate-400">No</span>
                              )}
                            </td>
                          )}
                          <td className="py-2 px-3 text-[11px]">
                            {item.review_decision || 'PENDING'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab 2: Research Metrics View */}
        {activeTab === 'research' && (
          <div className="flex-1 overflow-y-auto space-y-4 py-4 text-xs">
            {metricsError && (
              <div className="p-3 rounded-lg bg-amber-50 text-amber-800 text-xs border border-amber-200">
                {metricsError}
              </div>
            )}

            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Dataset Split:
                </span>
                <select
                  value={selectedSplit}
                  onChange={(e) => setSelectedSplit(e.target.value)}
                  className="px-2.5 py-1 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 font-mono"
                >
                  <option value="train_dev">train_dev (Development)</option>
                  <option value="validation">validation (Model Selection)</option>
                  <option value="held_out_test">held_out_test (Isolated Benchmark)</option>
                </select>
                <span className="text-[11px] text-slate-400">
                  ({referenceLabels.length} reference labels recorded)
                </span>
              </div>

              <button
                type="button"
                onClick={handleComputeMetrics}
                disabled={isLoadingMetrics}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm disabled:opacity-50"
              >
                <Sparkles className="w-3.5 h-3.5" />
                {isLoadingMetrics ? 'Computing Metrics...' : 'Compute Documented Research Metrics'}
              </button>
            </div>

            {/* Documented Metrics Table */}
            {metricsReport ? (
              <div className="space-y-3">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  <div className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                    <div className="text-[10px] text-slate-500">Detection Precision</div>
                    <div className="text-base font-bold text-indigo-600">
                      {(metricsReport.failure_detection_precision.value * 100).toFixed(1)}%
                    </div>
                    <div className="text-[10px] text-slate-400">
                      {metricsReport.failure_detection_precision.numerator}/{metricsReport.failure_detection_precision.denominator} cases
                    </div>
                  </div>

                  <div className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                    <div className="text-[10px] text-slate-500">Detection Recall</div>
                    <div className="text-base font-bold text-indigo-600">
                      {(metricsReport.failure_detection_recall.value * 100).toFixed(1)}%
                    </div>
                    <div className="text-[10px] text-slate-400">
                      {metricsReport.failure_detection_recall.numerator}/{metricsReport.failure_detection_recall.denominator} cases
                    </div>
                  </div>

                  <div className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                    <div className="text-[10px] text-slate-500">Top-1 Localisation Acc</div>
                    <div className="text-base font-bold text-emerald-600">
                      {(metricsReport.top_1_code_localisation_accuracy.value * 100).toFixed(1)}%
                    </div>
                    <div className="text-[10px] text-slate-400">
                      {metricsReport.top_1_code_localisation_accuracy.numerator}/{metricsReport.top_1_code_localisation_accuracy.denominator} cases
                    </div>
                  </div>

                  {correctionEnabled && (
                    <div className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                      <div className="text-[10px] text-slate-500">Verified Fix Rate</div>
                      <div className="text-base font-bold text-emerald-600">
                        {(metricsReport.verified_correction_rate.value * 100).toFixed(1)}%
                      </div>
                      <div className="text-[10px] text-slate-400">
                        {metricsReport.verified_correction_rate.numerator}/{metricsReport.verified_correction_rate.denominator} cases
                      </div>
                    </div>
                  )}
                </div>

                {/* Timing & Performance Latency */}
                <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-1">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
                    Performance Latency Targets (Stored-Result Target: &lt;3,000ms)
                  </span>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-1 text-slate-700 dark:text-slate-300">
                    <div>Median Diagnosis: <strong>{metricsReport.median_diagnosis_time_ms.toFixed(1)}ms</strong></div>
                    <div>P95 Diagnosis: <strong>{metricsReport.p95_diagnosis_time_ms.toFixed(1)}ms</strong></div>
                    <div>Median Verification: <strong>{metricsReport.median_verification_time_ms.toFixed(1)}ms</strong></div>
                    <div>P95 Verification: <strong>{metricsReport.p95_verification_time_ms.toFixed(1)}ms</strong></div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-8 text-center text-slate-400 border border-dashed rounded-lg space-y-1">
                <BarChart2 className="w-7 h-7 mx-auto text-slate-300 dark:text-slate-600" />
                <div>No metrics report computed yet for this split.</div>
                <p className="text-[11px] text-slate-400">
                  Select a dataset split and click &quot;Compute Documented Research Metrics&quot;.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
