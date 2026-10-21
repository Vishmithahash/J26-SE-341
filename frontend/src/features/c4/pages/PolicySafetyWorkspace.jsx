/**
 * Component 4 (C4) - Policy-Aware Safety and Prompt-Injection Testing Workspace
 * Root page for both Admin and User roles, adhering to strict ownership boundaries.
 */

import React, { useState, useCallback, useRef } from 'react';
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
import { ProjectHeader } from '../components/ProjectHeader';
import { C4Navigation } from '../components/C4Navigation';
import { ArtifactIntakeSection } from '../components/intake/ArtifactIntakeSection';
import { ExtractionSection } from '../components/extraction/ExtractionSection';
import { CandidateRulesList } from '../components/candidates/CandidateRulesList';
import { ContractSection } from '../components/contracts/ContractSection';
import { DomainBindingsSection } from '../components/domains/DomainBindingsSection';
import { PendingPhasePlaceholder } from '../components/PendingPhasePlaceholder';
import { C4_WORKSPACE_TABS } from '../api/types';

export const PolicySafetyWorkspace = ({
  title = 'Policy-Aware Safety and Prompt-Injection Testing',
  icon: TitleIcon = ShieldCheck,
}) => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'ADMIN';

  // Active sub-tab state
  const [activeTab, setActiveTab] = useState(C4_WORKSPACE_TABS.POLICY_PREPARATION);

  // Selected candidate rule IDs for contract creation
  const [selectedRuleIds, setSelectedRuleIds] = useState([]);

  // DOM ref to scroll directly to sections
  const extractionSectionRef = useRef(null);
  const contractsSectionRef = useRef(null);

  // 1. Scoped project management with generation tracking to invalidate stale async responses
  const handleProjectReset = useCallback(() => {
    setSelectedRuleIds([]);
  }, []);

  const {
    activeProject,
    activeProjectId,
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

  return (
    <div className="space-y-6 max-w-7xl mx-auto px-2 sm:px-4 lg:px-6 py-4">
      {/* Workspace Banner */}
      <div className="p-6 sm:p-8 rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white shadow-sm border border-slate-800">
        <div className="max-w-4xl">
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-xs font-semibold uppercase tracking-wider">
              <TitleIcon className="w-3.5 h-3.5" />
              Component 4 • Phase 1
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
            Derive candidate rules from versioned policy artifacts, bind domain capabilities, and gate accepted contracts through human review.
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

          {/* FUTURE PHASES: Clear roadmap placeholders without fake data */}
          {activeTab !== C4_WORKSPACE_TABS.POLICY_PREPARATION &&
            activeTab !== C4_WORKSPACE_TABS.DOMAIN_BINDINGS && (
              <PendingPhasePlaceholder tabId={activeTab} />
            )}
        </div>
      )}
    </div>
  );
};

export default PolicySafetyWorkspace;
