/**
 * Component 4 (C4) - Policy-Aware Safety and Prompt-Injection Testing Workspace
 * Root page for both Admin and User roles, covering Phase 1 and Phase 2 lifecycle workflows.
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  ShieldCheck,
  Shield,
  Info,
} from 'lucide-react';
import { useAuth } from '../../../context/AuthContext';
import { useC4Project } from '../hooks/useC4Project';
import { useArtifactIntake } from '../hooks/useArtifactIntake';
import { usePolicyExtraction } from '../hooks/usePolicyExtraction';
import { usePolicyContracts } from '../hooks/usePolicyContracts';
import { useDomainBindings } from '../hooks/useDomainBindings';
import { useTestCaseGeneration } from '../hooks/useTestCaseGeneration';
import { useTestCaseInspection } from '../hooks/useTestCaseInspection';
import { useControlledExecution } from '../hooks/useControlledExecution';
import { usePolicyRegression } from '../hooks/usePolicyRegression';
import { useResearchEvaluation } from '../hooks/useResearchEvaluation';

import { ProjectHeader } from '../components/ProjectHeader';
import { C4Navigation } from '../components/C4Navigation';
import { ArtifactIntakeSection } from '../components/intake/ArtifactIntakeSection';
import { ExtractionSection } from '../components/extraction/ExtractionSection';
import { CandidateRulesList } from '../components/candidates/CandidateRulesList';
import { ContractSection } from '../components/contracts/ContractSection';
import { DomainBindingsSection } from '../components/domains/DomainBindingsSection';
import { TestGenerationSection } from '../components/generation/TestGenerationSection';
import { TestCaseList } from '../components/cases/TestCaseList';
import { CasePayloadsModal } from '../components/cases/CasePayloadsModal';
import { ExecutionModal } from '../components/execution/ExecutionModal';
import { ExecutionRunsSection } from '../components/execution/ExecutionRunsSection';
import { PolicyRegressionSection } from '../components/regression/PolicyRegressionSection';
import { ResearchEvaluationSection } from '../components/evaluation/ResearchEvaluationSection';
import { FindingDetailsModal } from '../components/evidence/FindingDetailsModal';
import { ReportExportModal } from '../components/reports/ReportExportModal';
import { C4_WORKSPACE_TABS } from '../api/types';

export const PolicySafetyWorkspace = ({
  title = 'Policy-Aware Safety and Prompt-Injection Testing',
  icon: TitleIcon = ShieldCheck,
}) => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'ADMIN';

  // Active lifecycle tab state
  const [activeTab, setActiveTab] = useState(C4_WORKSPACE_TABS.POLICY_PREPARATION);

  // Selected candidate rule IDs for contract creation
  const [selectedRuleIds, setSelectedRuleIds] = useState([]);

  // Modal inspection states for Phase 2 & Phase 3
  const [isPayloadModalOpen, setIsPayloadModalOpen] = useState(false);
  const [isExecutionModalOpen, setIsExecutionModalOpen] = useState(false);
  const [modalTargetCase, setModalTargetCase] = useState(null);
  const [isFindingModalOpen, setIsFindingModalOpen] = useState(false);
  const [modalTargetFinding, setModalTargetFinding] = useState(null);
  const [modalTargetRunForFinding, setModalTargetRunForFinding] = useState(null);
  const [isReportExportModalOpen, setIsReportExportModalOpen] = useState(false);
  const [modalTargetRunForExport, setModalTargetRunForExport] = useState(null);

  // DOM refs to scroll directly to sections
  const extractionSectionRef = useRef(null);
  const contractsSectionRef = useRef(null);
  const testCasesListRef = useRef(null);

  // 1. Scoped project management with generation tracking to invalidate stale async responses
  const handleProjectReset = useCallback(() => {
    setSelectedRuleIds([]);
    setIsPayloadModalOpen(false);
    setIsExecutionModalOpen(false);
    setModalTargetCase(null);
    setIsFindingModalOpen(false);
    setModalTargetFinding(null);
    setModalTargetRunForFinding(null);
    setIsReportExportModalOpen(false);
    setModalTargetRunForExport(null);
  }, []);

  const {
    activeProject,
    activeProjectId,
    availableProjects,
    switchProject,
    isLoadingActive,
    isProjectReady,
    getGeneration,
    isCurrentGeneration,
  } = useC4Project(handleProjectReset);

  // 2. Lifecycle hooks
  const intake = useArtifactIntake(activeProjectId, isCurrentGeneration, getGeneration);
  const extraction = usePolicyExtraction(activeProjectId, isCurrentGeneration, getGeneration);
  const contracts = usePolicyContracts(activeProjectId, isCurrentGeneration, getGeneration);
  const bindings = useDomainBindings(activeProjectId, isCurrentGeneration, getGeneration);
  const generation = useTestCaseGeneration(activeProjectId, isCurrentGeneration, getGeneration);
  const cases = useTestCaseInspection(activeProjectId, isCurrentGeneration, getGeneration);
  const execution = useControlledExecution(activeProjectId, isCurrentGeneration, getGeneration);
  const regression = usePolicyRegression(activeProjectId, isCurrentGeneration, getGeneration);
  const evaluation = useResearchEvaluation(activeProjectId, isCurrentGeneration, getGeneration);

  // Load test cases when project is ready or tab switches to TEST_CASES
  const { loadTestCases } = cases;
  const { loadRuns } = execution;
  const { loadDatasets } = evaluation;

  useEffect(() => {
    if (activeProjectId && activeTab === C4_WORKSPACE_TABS.TEST_CASES) {
      loadTestCases();
    }
    if (activeProjectId && activeTab === C4_WORKSPACE_TABS.RUNS_AND_FINDINGS) {
      loadRuns();
    }
    if (activeProjectId && activeTab === C4_WORKSPACE_TABS.EVALUATION_AND_REPORTS) {
      loadDatasets();
    }
  }, [activeProjectId, activeTab, loadTestCases, loadRuns, loadDatasets]);

  // Candidate selection helpers
  const handleToggleSelectRule = useCallback((ruleId) => {
    setSelectedRuleIds((prev) =>
      prev.includes(ruleId) ? prev.filter((id) => id !== ruleId) : [...prev, ruleId]
    );
  }, []);

  const handleSelectAllRules = useCallback(() => {
    setSelectedRuleIds(extraction.candidates.map((r) => r.rule_id));
  }, [extraction.candidates]);

  const handleDeselectAllRules = useCallback(() => {
    setSelectedRuleIds([]);
  }, []);

  // Smooth scroll transitions between workflow stages
  const handleProceedToExtraction = useCallback(() => {
    if (extractionSectionRef.current) {
      extractionSectionRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, []);

  const handleProceedToContracts = useCallback(() => {
    if (contractsSectionRef.current) {
      contractsSectionRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, []);

  const handleViewGeneratedCases = useCallback(() => {
    if (testCasesListRef.current) {
      testCasesListRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, []);

  // Modal triggers
  const handleOpenPayloadModal = useCallback((tc) => {
    setModalTargetCase(tc);
    setIsPayloadModalOpen(true);
  }, []);

  const handleClosePayloadModal = useCallback(() => {
    setIsPayloadModalOpen(false);
    setModalTargetCase(null);
  }, []);

  const handleOpenExecutionModal = useCallback((tc) => {
    setModalTargetCase(tc);
    setIsExecutionModalOpen(true);
  }, []);

  const handleCloseExecutionModal = useCallback(() => {
    setIsExecutionModalOpen(false);
    setModalTargetCase(null);
  }, []);

  const handleOpenFindingModal = useCallback((finding, run) => {
    setModalTargetFinding(finding);
    setModalTargetRunForFinding(run);
    setIsFindingModalOpen(true);
  }, []);

  const handleCloseFindingModal = useCallback(() => {
    setIsFindingModalOpen(false);
    setModalTargetFinding(null);
    setModalTargetRunForFinding(null);
  }, []);

  const handleOpenReportExportModal = useCallback((run) => {
    setModalTargetRunForExport(run);
    setIsReportExportModalOpen(true);
  }, []);

  const handleCloseReportExportModal = useCallback(() => {
    setIsReportExportModalOpen(false);
    setModalTargetRunForExport(null);
  }, []);

  const handleGenerateCasesWrapper = useCallback(
    async (params) => {
      const report = await generation.generateCases(params);
      if (report) {
        cases.loadTestCases();
      }
      return report;
    },
    [generation, cases]
  );

  return (
    <div className="space-y-6 max-w-7xl mx-auto px-2 sm:px-4 lg:px-6 py-4">
      {/* Workspace Banner */}
      <div className="p-6 sm:p-8 rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white shadow-sm border border-slate-800">
        <div className="max-w-4xl">
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-semibold uppercase tracking-wider">
              <TitleIcon className="w-3.5 h-3.5" />
              Component 4 • Complete (Phases 1, 2 & 3 Active)
            </div>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-800 text-slate-300 border border-slate-700 text-xs font-medium">
              <Shield className="w-3 h-3 text-slate-400" />
              QA Account Role: {isAdmin ? 'Administrator' : 'Standard User'}
            </div>
          </div>

          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
            {title}
          </h1>

          <p className="mt-2 text-sm text-slate-300 leading-relaxed">
            Policy-aware safety, authorization boundaries, and prompt-injection testing for tool-using LLM applications.
            Derive candidate rules, bind domain capabilities, gate accepted contracts, synthesize policy-specific test cases, and execute controlled trials with disentangled outcome dimensions.
          </p>

          <div className="mt-4 p-3 rounded-xl bg-slate-800/60 border border-slate-700/80 flex items-start gap-2.5 text-xs text-slate-300 max-w-2xl">
            <Info className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold text-slate-200">Role Boundary Notice: </span>
              Your login identity represents the QA Framework account ({isAdmin ? 'ADMIN' : 'USER'}). Policy rules evaluate simulated target-application roles (e.g., CUSTOMER_SUPPORT, MANAGER, GUEST) rather than your framework session.
            </div>
          </div>
        </div>
      </div>

      {/* Authoritative Selected-Project Header */}
      <ProjectHeader
        activeProject={activeProject}
        isLoadingActive={isLoadingActive}
        availableProjects={availableProjects}
        onSelectProject={switchProject}
      />

      {/* Main Workspace Navigation */}
      {isProjectReady && (
        <C4Navigation
          activeTab={activeTab}
          onSelectTab={setActiveTab}
        />
      )}

      {/* Workspace Content by Tab */}
      {isProjectReady && (
        <div>
          {/* TAB 1: Policy Preparation (Artifacts -> Extraction -> Candidates -> Contracts) */}
          {activeTab === C4_WORKSPACE_TABS.POLICY_PREPARATION && (
            <div className="space-y-8">
              {/* Stage 1: Artifact Intake */}
              <section aria-labelledby="stage-intake-heading">
                <ArtifactIntakeSection
                  artifacts={intake.artifacts}
                  selectedArtifact={intake.selectedArtifact}
                  onSelectArtifact={intake.setSelectedArtifact}
                  onRegister={intake.registerArtifact}
                  onFetchVersion={intake.fetchArtifactVersion}
                  onProceedToExtraction={handleProceedToExtraction}
                  isSubmitting={intake.isSubmitting}
                  isFetching={intake.isFetching}
                  isProjectReady={isProjectReady}
                  error={intake.error}
                  successMessage={intake.successMessage}
                />
              </section>

              {/* Stage 2: Extraction & Provider Readiness */}
              <section ref={extractionSectionRef} aria-labelledby="stage-extraction-heading">
                <ExtractionSection
                  selectedArtifact={intake.selectedArtifact}
                  providerReadiness={extraction.providerReadiness}
                  selectedProvider={extraction.selectedProvider}
                  onCheckReadiness={extraction.checkReadiness}
                  isLoadingReadiness={extraction.isLoadingReadiness}
                  onDeriveCandidates={extraction.deriveCandidates}
                  onStartExtractionJob={extraction.startExtractionJob}
                  isExtracting={extraction.isExtracting}
                  activeJob={extraction.activeJob}
                  error={extraction.error}
                  successMessage={extraction.successMessage}
                  isProjectReady={isProjectReady}
                />
              </section>

              {/* Stage 3: Candidate Rules & Human Review */}
              <section aria-labelledby="stage-candidates-heading">
                <CandidateRulesList
                  candidates={extraction.candidates}
                  selectedRuleIds={selectedRuleIds}
                  onToggleSelectRule={handleToggleSelectRule}
                  onSelectAll={handleSelectAllRules}
                  onDeselectAll={handleDeselectAllRules}
                  onReviewRule={extraction.reviewCandidate}
                  onProceedToContracts={handleProceedToContracts}
                  isReviewing={extraction.isReviewing}
                />
              </section>

              {/* Stage 4: Contract Lifecycle & Acceptance Gating */}
              <section ref={contractsSectionRef} aria-labelledby="stage-contracts-heading">
                <ContractSection
                  selectedRuleIds={selectedRuleIds}
                  currentContract={contracts.currentContract}
                  contractValidation={contracts.contractValidation}
                  isDrafting={contracts.isDrafting}
                  isValidating={contracts.isValidating}
                  isAccepting={contracts.isAccepting}
                  isFetching={contracts.isFetching}
                  isAccepted={contracts.isAccepted}
                  onCreateDraft={contracts.createDraft}
                  onValidateDraft={contracts.validateDraft}
                  onAcceptDraft={contracts.acceptDraft}
                  onFetchContract={contracts.fetchContract}
                  error={contracts.error}
                  successMessage={contracts.successMessage}
                  isProjectReady={isProjectReady}
                />
              </section>
            </div>
          )}

          {/* TAB 2: Domain Bindings & Onboarding Readiness */}
          {activeTab === C4_WORKSPACE_TABS.DOMAIN_BINDINGS && (
            <div className="space-y-6">
              <DomainBindingsSection
                domainProfiles={bindings.domainProfiles}
                selectedDomainId={bindings.selectedDomainId}
                onSelectDomainId={bindings.setSelectedDomainId}
                domainReadiness={bindings.domainReadiness}
                domainBindings={bindings.domainBindings}
                selectedBinding={bindings.selectedBinding}
                onSelectBinding={bindings.setSelectedBinding}
                activeOnboardingJob={bindings.activeOnboardingJob}
                isLoadingDomains={bindings.isLoadingDomains}
                isLoadingReadiness={bindings.isLoadingReadiness}
                isSubmittingJob={bindings.isSubmittingJob}
                onCheckReadiness={bindings.checkDomainReadiness}
                onFetchBindingVersion={bindings.fetchBindingVersion}
                onStartOnboarding={bindings.startOnboarding}
                selectedArtifact={intake.selectedArtifact}
                error={bindings.error}
                successMessage={bindings.successMessage}
                isProjectReady={isProjectReady}
              />
            </div>
          )}

          {/* TAB 3: Test Cases (Phase 2 Implemented: Generation, Validation, Freezing, Payload Boundaries) */}
          {activeTab === C4_WORKSPACE_TABS.TEST_CASES && (
            <div className="space-y-8">
              <section aria-labelledby="stage-generation-heading">
                <TestGenerationSection
                  acceptedContract={contracts.currentContract}
                  domainBinding={bindings.selectedBinding || bindings.domainProfiles[0]?.binding}
                  onGenerateCases={handleGenerateCasesWrapper}
                  isGenerating={generation.isGenerating}
                  generationReport={generation.latestReport}
                  error={generation.error}
                  successMessage={generation.successMessage}
                  isProjectReady={isProjectReady}
                  onViewGeneratedCases={handleViewGeneratedCases}
                />
              </section>

              <section ref={testCasesListRef} aria-labelledby="stage-cases-heading">
                <TestCaseList
                  testCases={cases.testCases}
                  onValidateCase={cases.validateCase}
                  onFreezeCase={cases.freezeCase}
                  onInspectPayloads={handleOpenPayloadModal}
                  onOpenExecution={handleOpenExecutionModal}
                  onRefresh={() => cases.loadTestCases()}
                  isLoadingCases={cases.isLoadingCases}
                  isValidatingCase={cases.isValidatingCase}
                  isFreezingCase={cases.isFreezingCase}
                />
              </section>
            </div>
          )}

          {/* TAB 4: Runs & Findings (Phase 2 Implemented: Controlled Execution & 6 Outcome Dimensions) */}
          {activeTab === C4_WORKSPACE_TABS.RUNS_AND_FINDINGS && (
            <div className="space-y-6">
              <ExecutionRunsSection
                runsList={execution.runsList}
                activeRun={execution.activeRun}
                onSelectRun={execution.setActiveRun}
                onRefreshRuns={() => execution.loadRuns()}
                isLoadingRuns={execution.isLoadingRuns}
                onOpenFindingModal={handleOpenFindingModal}
                onOpenExportModal={handleOpenReportExportModal}
              />
            </div>
          )}

          {/* TAB 5: Policy Changes & Impact Regression (Phase 3 Implemented) */}
          {activeTab === C4_WORKSPACE_TABS.POLICY_CHANGES && (
            <div className="space-y-6">
              <PolicyRegressionSection
                regression={regression}
                contracts={contracts}
                bindings={bindings}
              />
            </div>
          )}

          {/* TAB 6: Research Evaluation & Benchmarks (Phase 3 Implemented) */}
          {activeTab === C4_WORKSPACE_TABS.EVALUATION_AND_REPORTS && (
            <div className="space-y-6">
              <ResearchEvaluationSection
                evaluation={evaluation}
                projectId={activeProjectId}
              />
            </div>
          )}
        </div>
      )}

      {/* Payloads Inspector Modal */}
      <CasePayloadsModal
        isOpen={isPayloadModalOpen}
        testCase={modalTargetCase}
        payloads={cases.activePayloads}
        isLoading={cases.isLoadingPayloads}
        onClose={handleClosePayloadModal}
        onLoadPayloads={cases.loadAllPayloads}
      />

      {/* Controlled Execution Modal */}
      <ExecutionModal
        isOpen={isExecutionModalOpen}
        testCase={modalTargetCase}
        domainBinding={bindings.selectedBinding || bindings.domainProfiles[0]?.binding}
        acceptedContract={contracts.currentContract}
        readinessReport={execution.readinessReport}
        isCheckingReadiness={execution.isCheckingReadiness}
        isExecuting={execution.isExecuting}
        executionMode={execution.executionMode}
        setExecutionMode={execution.setExecutionMode}
        simulatedBehavior={execution.simulatedBehavior}
        setSimulatedBehavior={execution.setSimulatedBehavior}
        idempotencyKey={execution.idempotencyKey}
        onRegenerateIdempotencyKey={execution.regenerateIdempotencyKey}
        onCheckReadiness={execution.checkReadiness}
        onExecuteCase={async (payload) => {
          const run = await execution.executeCase(payload);
          if (run) {
            handleCloseExecutionModal();
            setActiveTab(C4_WORKSPACE_TABS.RUNS_AND_FINDINGS);
          }
        }}
        onClose={handleCloseExecutionModal}
        error={execution.error}
        successMessage={execution.successMessage}
      />

      {/* Evidence-Linked Finding Details Modal */}
      <FindingDetailsModal
        isOpen={isFindingModalOpen}
        finding={modalTargetFinding}
        runRecord={modalTargetRunForFinding}
        onClose={handleCloseFindingModal}
      />

      {/* Authenticated Report Export Modal */}
      <ReportExportModal
        isOpen={isReportExportModalOpen}
        runRecord={modalTargetRunForExport}
        onClose={handleCloseReportExportModal}
      />
    </div>
  );
};

export default PolicySafetyWorkspace;
