/**
 * Component 4 (C4) - Policy-Aware Safety and Prompt-Injection Testing
 * Main Feature Workspace Page (Phase 1: Policy Preparation)
 */

import React, { useState, useEffect } from 'react';
import { ShieldCheck } from 'lucide-react';
import { ProjectHeader } from '../components/ProjectHeader';
import { C4Navigation } from '../components/C4Navigation';
import { PendingPhasePlaceholder } from '../components/PendingPhasePlaceholder';
import { ArtifactIntakeSection } from '../components/intake/ArtifactIntakeSection';
import { ExtractionSection } from '../components/extraction/ExtractionSection';
import { CandidateRulesList } from '../components/candidates/CandidateRulesList';
import { ContractSection } from '../components/contracts/ContractSection';

import { useC4Project } from '../hooks/useC4Project';
import { useArtifactIntake } from '../hooks/useArtifactIntake';
import { usePolicyExtraction } from '../hooks/usePolicyExtraction';
import { usePolicyContracts } from '../hooks/usePolicyContracts';
import { C4_WORKSPACE_TABS } from '../api/types';

export function PolicySafetyWorkspace({
  title = 'Policy-Aware Safety and Prompt-Injection Testing',
}) {
  const [activeTab, setActiveTab] = useState(C4_WORKSPACE_TABS.POLICY_PREPARATION);
  const [selectedRuleIds, setSelectedRuleIds] = useState([]);

  const {
    activeProject,
    activeProjectId,
    isLoadingActive,
    isProjectReady,
    getGeneration,
    isCurrentGeneration,
  } = useC4Project();

  // Sub-feature hooks
  const artifactIntake = useArtifactIntake(activeProjectId, isCurrentGeneration, getGeneration);
  const policyExtraction = usePolicyExtraction(activeProjectId, isCurrentGeneration, getGeneration);
  const policyContracts = usePolicyContracts(activeProjectId, isCurrentGeneration, getGeneration);

  const { resetState: resetArtifacts } = artifactIntake;
  const { resetState: resetExtraction } = policyExtraction;
  const { resetState: resetContracts } = policyContracts;

  // Clear state when active project changes
  useEffect(() => {
    resetArtifacts();
    resetExtraction();
    resetContracts();
    setSelectedRuleIds([]);
  }, [activeProjectId, resetArtifacts, resetExtraction, resetContracts]);

  // Sync candidate rules with rule selection
  const handleToggleSelectRule = (ruleId) => {
    setSelectedRuleIds((prev) =>
      prev.includes(ruleId) ? prev.filter((id) => id !== ruleId) : [...prev, ruleId]
    );
  };

  const handleSelectAllRules = () => {
    setSelectedRuleIds(policyExtraction.candidates.map((c) => c.rule_id));
  };

  const handleDeselectAllRules = () => {
    setSelectedRuleIds([]);
  };

  // Workflow step transitions
  const handleProceedToExtraction = (artifact) => {
    artifactIntake.setSelectedArtifact(artifact);
    const element = document.getElementById('c4-step-extraction');
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const handleProceedToContracts = () => {
    const element = document.getElementById('c4-step-contracts');
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Page Title & Mission Statement */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-indigo-600 text-white flex items-center justify-center shadow-sm">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <h1 className="text-xl md:text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
              {title}
            </h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-3xl">
            Policy contract extraction, provenance linking, adversarial candidate review, and cryptographic contract acceptance.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start md:self-center">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-100 dark:bg-indigo-950/80 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
            Phase 1: Policy Preparation
          </span>
        </div>
      </div>

      {/* Shared Active Project Scope Banner */}
      <ProjectHeader
        activeProject={activeProject}
        isLoadingActive={isLoadingActive}
      />

      {/* Lifecycle Sub-Navigation */}
      <C4Navigation
        activeTab={activeTab}
        onSelectTab={setActiveTab}
      />

      {/* Main Workspace Body based on Active Tab */}
      {activeTab === C4_WORKSPACE_TABS.POLICY_PREPARATION ? (
        <div className="space-y-8">
          {/* Step 1: Artifact Intake */}
          <section id="c4-step-intake" aria-label="Step 1: Policy Artifact Intake">
            <ArtifactIntakeSection
              artifacts={artifactIntake.artifacts}
              selectedArtifact={artifactIntake.selectedArtifact}
              onSelectArtifact={artifactIntake.setSelectedArtifact}
              onRegister={artifactIntake.registerArtifact}
              onProceedToExtraction={handleProceedToExtraction}
              isSubmitting={artifactIntake.isSubmitting}
              isProjectReady={isProjectReady}
              error={artifactIntake.error}
              successMessage={artifactIntake.successMessage}
            />
          </section>

          {/* Step 2: Extraction & Provider Readiness */}
          <section id="c4-step-extraction" aria-label="Step 2: Policy Extraction and Engine Readiness">
            <ExtractionSection
              selectedArtifact={artifactIntake.selectedArtifact}
              providerReadiness={policyExtraction.providerReadiness}
              selectedProvider={policyExtraction.selectedProvider}
              onSelectProvider={policyExtraction.setSelectedProvider}
              onCheckReadiness={policyExtraction.checkReadiness}
              isLoadingReadiness={policyExtraction.isLoadingReadiness}
              onDeriveCandidates={policyExtraction.deriveCandidates}
              onStartExtractionJob={policyExtraction.startExtractionJob}
              isExtracting={policyExtraction.isExtracting}
              activeJob={policyExtraction.activeJob}
              error={policyExtraction.error}
              successMessage={policyExtraction.successMessage}
              isProjectReady={isProjectReady}
            />
          </section>

          {/* Step 3: Candidate Rule Inspection & Review Gate */}
          <section id="c4-step-candidates" aria-label="Step 3: Candidate Rule Inspection and Review Gate">
            <CandidateRulesList
              candidates={policyExtraction.candidates}
              selectedRuleIds={selectedRuleIds}
              onToggleSelectRule={handleToggleSelectRule}
              onSelectAll={handleSelectAllRules}
              onDeselectAll={handleDeselectAllRules}
              onReviewRule={policyExtraction.reviewCandidate}
              onProceedToContracts={handleProceedToContracts}
              isReviewing={policyExtraction.isReviewing}
              error={policyExtraction.error}
              successMessage={policyExtraction.successMessage}
            />
          </section>

          {/* Step 4: Policy Contract Drafting, Validation & Acceptance */}
          <section id="c4-step-contracts" aria-label="Step 4: Policy Contract Drafting and Acceptance">
            <ContractSection
              selectedRuleIds={selectedRuleIds}
              candidates={policyExtraction.candidates}
              currentContract={policyContracts.currentContract}
              contractValidation={policyContracts.contractValidation}
              isDrafting={policyContracts.isDrafting}
              isValidating={policyContracts.isValidating}
              isAccepting={policyContracts.isAccepting}
              isAccepted={policyContracts.isAccepted}
              onCreateDraft={policyContracts.createDraft}
              onValidateDraft={policyContracts.validateDraft}
              onAcceptDraft={policyContracts.acceptDraft}
              error={policyContracts.error}
              successMessage={policyContracts.successMessage}
              isProjectReady={isProjectReady}
            />
          </section>
        </div>
      ) : (
        <PendingPhasePlaceholder tabId={activeTab} />
      )}
    </div>
  );
}

export default PolicySafetyWorkspace;
