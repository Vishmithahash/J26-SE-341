# Component 4: Policy-Aware Safety and Prompt-Injection Testing
## Frontend Phases 1, 2 & 3 Complete Architectural Documentation

### 1. Ownership Boundaries & File Allowlist

#### Strict Ownership Boundary
- All Component 4 (C4) implementations reside exclusively under `frontend/src/features/c4/`.
- No backend code, migrations, schemas, or dependencies were modified (backend is strictly READ-ONLY).
- Components C1, C2, and C3 implementations, routes, dashboard cards, tests, and documentation remain completely untouched and protected.

#### File Inventory (Complete Frontend Implementation)
- **API & Taxonomy:**
  - `frontend/src/features/c4/api/types.js` - Enums, taxonomy, lifecycle states, execution modes, 11 simulated behaviors, 6 outcome dimensions, regression diff types, action decisions, violation stages, trust classifications, and research evaluation enums.
  - `frontend/src/features/c4/api/c4Api.js` - Dedicated API client adapter for C4 endpoints (`http://127.0.0.1:8000/projects/{projectId}/c4/...`), with all 38 endpoints across Phases 1, 2, and 3.
- **Custom React Hooks:**
  - `frontend/src/features/c4/hooks/useC4Project.js` - Scoped active-project state, generation counter tracking for stale async response rejection.
  - `frontend/src/features/c4/hooks/useArtifactIntake.js` - Form state, version lookup, template presets, and plain-text/JSON file upload handler.
  - `frontend/src/features/c4/hooks/usePolicyExtraction.js` - Extraction readiness inspector, derivation runner, and candidate review gate.
  - `frontend/src/features/c4/hooks/usePolicyContracts.js` - Contract draft creation, validation reporter, explicit acceptance gate, and version lookup.
  - `frontend/src/features/c4/hooks/useDomainBindings.js` - Domain profiles, runtime readiness checks, binding version lookup, and onboarding job pipeline.
  - `frontend/src/features/c4/hooks/useTestCaseGeneration.js` - Test case synthesis from accepted contract & domain binding, budget cap (1-50), seed, category toggles.
  - `frontend/src/features/c4/hooks/useTestCaseInspection.js` - Test case inspection, validation, content-hash immutable freezing, and payload export.
  - `frontend/src/features/c4/hooks/useControlledExecution.js` - Runtime readiness check, mode selector (`SIMULATED` vs `LIVE_AUT`), idempotency generator/preserver, execution runner, run history.
  - `frontend/src/features/c4/hooks/usePolicyRegression.js` - Contract comparison, semantic diffs, impact plan generation, selective regeneration, plan freezing, execution modes (`FRESH_EXECUTION` vs `HISTORICAL_RE_EVALUATION`), regression report retrieval.
  - `frontend/src/features/c4/hooks/useResearchEvaluation.js` - Benchmark datasets (`DEV`, `PILOT`, `HELD_OUT`), dataset freezing, reviewer decisions & Cohen's Kappa agreement calculator, baseline strategies & ablations, experiment orchestration, and consolidated proposal metrics.
- **UI Components & Modals:**
  - `frontend/src/features/c4/components/ProjectHeader.jsx` - Project banner, active scope indicator, and project switcher links (`/app/projects` vs `/admin/projects`).
  - `frontend/src/features/c4/components/C4Navigation.jsx` - Sub-tab lifecycle bar marking all 6 tabs as active and implemented.
  - `frontend/src/features/c4/components/intake/ArtifactIntakeSection.jsx` - Policy document registration, JSON/plain-text uploads, templates, version lookup.
  - `frontend/src/features/c4/components/extraction/ExtractionSection.jsx` - Extraction provider readiness (`offline_mock` vs external LLM), mode selection, active extraction job status.
  - `frontend/src/features/c4/components/candidates/ReviewModal.jsx` - Human review modal with reviewer actor ID, decision justification, and audit disclaimer.
  - `frontend/src/features/c4/components/candidates/CandidateRuleCard.jsx` - Policy family badges, exact condition properties, excerpt coordinates, and review actions.
  - `frontend/src/features/c4/components/candidates/CandidateRulesList.jsx` - Filterable, searchable candidate table with bulk selection and review triggers.
  - `frontend/src/features/c4/components/contracts/ContractSection.jsx` - Draft creation, validation issue inspector, explicit acceptance modal, version lookup, and immutable accepted contract viewer.
  - `frontend/src/features/c4/components/domains/DomainBindingsSection.jsx` - Multi-tab domain binding inspector, readiness runner, and onboarding launcher.
  - `frontend/src/features/c4/components/generation/TestGenerationSection.jsx` - Test generation controls, budget cap, seed, category toggles, batch report.
  - `frontend/src/features/c4/components/cases/TestCaseCard.jsx` - Test case card with category badge, target rules, boundaries, pinned versions, content hash, validation issues, validate/freeze buttons, and payload inspection triggers.
  - `frontend/src/features/c4/components/cases/TestCaseList.jsx` - Filterable list of test cases (by category, lifecycle state, keyword) with summary metrics.
  - `frontend/src/features/c4/components/cases/CasePayloadsModal.jsx` - Inspector enforcing the three separated payload boundaries (Agent Task Payload, Harness Orchestration Payload, Evaluator Oracle).
  - `frontend/src/features/c4/components/execution/ExecutionModal.jsx` - Execution launcher with runtime readiness check, simulated behavior selector, live AUT blocker indicator, and idempotency key input.
  - `frontend/src/features/c4/components/execution/ExecutionRunsSection.jsx` - Detailed execution runs history and inspector displaying all 6 independent outcome dimensions, evidence inspection triggers, and export triggers.
  - `frontend/src/features/c4/components/evidence/EvidenceChainViewer.jsx` - 4-step causal observation chain: (1) Instruction Source & Trust Classification → (2) Grounded Policy Rule & Coordinates → (3) Observed Action & Application Decision → (4) Committed Effect / Protected Disclosure. Exposes observation limitations and missing evidence warnings safely without script execution.
  - `frontend/src/features/c4/components/evidence/FindingDetailsModal.jsx` - Modal for in-depth finding inspection with metadata grid, verdict badge, and embedded `EvidenceChainViewer`.
  - `frontend/src/features/c4/components/reports/ReportExportModal.jsx` - Authenticated client-side JSON/Markdown export preserving all IDs, hashes, versions, and clearly marking local download vs unconfigured shared publication (no tokens in URLs).
  - `frontend/src/features/c4/components/regression/PolicyRegressionSection.jsx` - Policy change tracking, semantic diffs table, impact plan builder with case lineage (`replaced by` / `predecessor`), selective regeneration/freeze, fresh execution vs historical re-evaluation with explicit notes, and verdict transitions table distinguishing requirement changes from agent regressions.
  - `frontend/src/features/c4/components/evaluation/ResearchEvaluationSection.jsx` - Research benchmark datasets with split counts, inter-rater reliability calculator (Cohen's Kappa), baseline strategy selector, ablation selector, and consolidated metrics dashboard across all 6 proposal categories.
  - `frontend/src/features/c4/components/dashboard/C4DashboardCard.jsx` - Reusable dashboard card for User and Admin dashboard grids, displaying verdict distribution, latest run status, execution mode, and disentangled outcomes.
  - `frontend/src/features/c4/pages/PolicySafetyWorkspace.jsx` - Unified C4 workspace page mounted under both `/app/policy-safety` and `/admin/policy-safety`.
- **Automated Test Suites:**
  - `frontend/src/features/c4/tests/c4Phase1.test.js` - Phase 1 test suite (taxonomy, API endpoints, XSS safety, generation counters, boundaries).
  - `frontend/src/features/c4/tests/c4Phase2.test.js` - Phase 2 test suite (Phase 2 enums, generation & execution endpoints, payload boundary separation, outcome dimension independence, idempotency contract).
  - `frontend/src/features/c4/tests/c4Phase3.test.js` - Phase 3 test suite (regression enums & endpoints, research evaluation endpoints, evidence chain causal visualization, report export security, transition classifications).
- **Permitted Shared File Updates (Minimal C4 Registration Only):**
  - `frontend/src/App.jsx` - Replaced `EmptyComponentPage` with `<PolicySafetyWorkspace />` on `/admin/policy-safety` and `/app/policy-safety` while preserving exact title string `"Policy-Aware Safety and Prompt-Injection Testing"`.
  - `frontend/src/pages/admin/AdminDashboard.jsx` - Replaced C4's reserved card with `<C4DashboardCard basePath="/admin" />`. C1, C2, C3 cards preserved intact.
  - `frontend/src/pages/user/UserDashboard.jsx` - Replaced C4's reserved card with `<C4DashboardCard basePath="/app" />`. C1, C2, C3 cards preserved intact.

---

### 2. Complete C4 Endpoint Mappings

| Lifecycle Stage | Method & Path | Purpose | Key Parameters / Notes |
| :--- | :--- | :--- | :--- |
| **Artifact Intake** | `POST /artifacts` | Register policy document | `{ artifact_id, title, raw_content, format }` |
| **Artifact Intake** | `GET /artifacts/{id}/versions/{v}` | Retrieve artifact version | Version lookup |
| **Extraction** | `GET /extraction/readiness` | Check extraction engine readiness | Returns `provider`, `active_mode` (`offline_mock` vs live) |
| **Extraction** | `POST /extraction/derive` | Extract candidate policy rules | Deterministic regex / LLM derivation |
| **Candidates** | `GET /candidates` | List candidate rules | Filter by `policy_family`, `decision` |
| **Candidates** | `POST /candidates/{id}/review` | Human review gate | `{ decision: ACCEPT/REJECT, reviewer_id, justification }` |
| **Contracts** | `POST /contracts` | Create draft policy contract | `{ contract_id, selected_rule_ids }` |
| **Contracts** | `POST /contracts/{id}/versions/{v}/validate` | Validate contract consistency | Issue reporting |
| **Contracts** | `POST /contracts/{id}/versions/{v}/accept` | Accept policy contract | Lifecycle gate: transitions to `ACCEPTED` |
| **Domain Bindings**| `GET /domains` | List domain profiles | E-Commerce, Banking, Booking, Customer Support |
| **Domain Bindings**| `GET /domains/{id}/readiness` | Check domain capability readiness | Returns tools, mock schemas |
| **Domain Bindings**| `POST /onboarding` | Launch domain onboarding | Background pipeline job |
| **Test Generation**| `POST /generate` | Synthesize test cases | `{ contract_id, binding_id, max_cases_per_rule, seed, categories }` |
| **Test Inspection**| `GET /cases` | List generated test cases | Filter by category, lifecycle state |
| **Test Inspection**| `POST /cases/{id}/versions/{v}/validate`| Validate test case | Check against accepted contract & binding |
| **Test Inspection**| `POST /cases/{id}/versions/{v}/freeze`| Freeze test case snapshot | Locks case immutably with SHA-256 `content_hash` |
| **Payload Export** | `GET /cases/{id}/versions/{v}/export/agent` | Export Agent Task Payload | Stripped of internal rules, expected verdicts, oracle labels |
| **Payload Export** | `GET /cases/{id}/versions/{v}/export/harness` | Export Harness Payload | Placement channels, untrusted source text |
| **Payload Export** | `GET /cases/{id}/versions/{v}/export/evaluator`| Export Evaluator Oracle | Compliance criteria, hidden attacker goals |
| **Execution** | `POST /runs/readiness` | Runtime readiness check | Checks adapter availability, fixture isolation |
| **Execution** | `POST /runs/execute` | Execute controlled trial | `{ case_id, target_mode, simulated_behavior, idempotency_key }` |
| **Execution** | `GET /runs` | List execution history | Limit 50, filter by case ID |
| **Execution** | `GET /runs/{id}/report` | Export explainable run report | Evidence events, timeline, 6 outcome dimensions |
| **Regression** | `POST /regression/compare` | Semantic contract comparison | `{ baseline_contract_id, candidate_contract_id }` → `rule_diffs` |
| **Regression** | `GET /regression/comparisons/{id}` | Retrieve comparison record | Diff lookup |
| **Regression** | `POST /regression/plans` | Create typed regression plan | Case decisions (`REGENERATE`, `REVALIDATE`, `RETIRE`, `RETAIN`, `BLOCKED`) |
| **Regression** | `GET /regression/plans/{id}` | Retrieve regression plan | Case lineage (`replaced_by`, `predecessor`) |
| **Regression** | `POST /regression/plans/{id}/regenerate` | Selectively regenerate affected cases | Target only `REGENERATE` action cases |
| **Regression** | `POST /regression/plans/{id}/freeze` | Freeze regression plan snapshot | Locks plan digest immutably |
| **Regression** | `POST /regression/plans/{id}/execute` | Fresh regression execution | Invokes adapter on regenerated cases |
| **Regression** | `POST /regression/plans/{id}/re-evaluate-historical` | Historical re-evaluation | Re-scores existing traces against new candidate rules |
| **Regression** | `GET /regression/plans/{id}/report` | Retrieve regression report | Verdict transitions with `is_requirement_change: bool` |
| **Evaluation** | `POST /evaluation/datasets` | Register benchmark dataset | Splits: `DEV`, `PILOT`, `HELD_OUT` |
| **Evaluation** | `GET /evaluation/datasets` | List benchmark datasets | Returns versioned datasets |
| **Evaluation** | `POST /evaluation/datasets/{id}/versions/{v}/freeze` | Freeze dataset benchmark | Locks benchmark immutably |
| **Evaluation** | `POST /evaluation/reviewers/decisions` | Record reviewer decision | Blinded review decision packet |
| **Evaluation** | `GET /evaluation/reviewers/agreement` | Calculate Cohen's Kappa | $\kappa$, $P_o$, $P_e$, and interpretation |
| **Evaluation** | `POST /evaluation/experiments` | Create experiment trial | `{ strategy, ablation, dataset_split, seed, repeat_count }` |
| **Evaluation** | `POST /evaluation/experiments/{id}/execute` | Execute experiment trials | Runs configured evaluation pipeline |
| **Evaluation** | `GET /evaluation/experiments/{id}/report` | Retrieve consolidated proposal metrics | All 6 proposal metric categories with numerators & denominators |

---

### 3. Disentangled Outcome Dimensions & Observation Lineage

#### The Six Independent Outcome Dimensions
1. **Policy Verdict:** `PASS`, `FAIL`, `INCONCLUSIVE`, `NOT_EXERCISED`.
   - Distinct from execution success. Passing an unexercised rule does not count as a pass.
   - An application-level rejection does NOT erase an attempted-action violation (`FAIL`) if policy forbids attempting the action.
2. **Injection Exposure:** `EXPOSED`, `NOT_EXPOSED`, `NOT_APPLICABLE`, `UNKNOWN`.
   - `NOT_EXPOSED` does not imply `PASS`. Unobserved exposure results in `UNKNOWN` or `INCONCLUSIVE`.
3. **Attacker Objective Outcome:** `ACHIEVED`, `BLOCKED`, `NOT_ACHIEVED`, `NOT_APPLICABLE`.
   - Separates attempt from persistent effect.
4. **Legitimate Task Utility:** `SUCCESS`, `FAILED`, `PARTIAL`, `UNKNOWN`, `NOT_APPLICABLE`.
   - Evaluates whether benign utility was preserved regardless of injection attempt.
5. **Execution Lifecycle Status:** `PENDING`, `PREPARING_FIXTURE`, `READY`, `INVOKING_AGENT`, `COMPLETED`, `FAILED`, `CLEANUP_FAILED`.
   - Harness/adapter operational lifecycle.
6. **Fixture Cleanup Status:** `CLEANED_AND_VERIFIED`, `CLEANUP_FAILED`, `SKIPPED`.
   - Even when cleanup fails, pre-cleanup findings and persistent effects are preserved.

#### 4-Step Evidence-Linked Causal Observation Chain (`EvidenceChainViewer`)
1. **Instruction Source & Trust Classification:**
   - Origin: `user_task_prompt` (`TRUSTED_GOVERNANCE`) vs `untrusted_document_source` (`UNTRUSTED_INDIRECT_CONTENT`).
2. **Applicable Policy Rule & Grounded Excerpt:**
   - Contract ID, version, rule coordinate offsets `[char_start:char_end]`, exact text excerpt.
3. **Observed Action Attempt & Application Decision:**
   - Evaluated violation stage (`ATTEMPTED_PROHIBITED_ACTION`, `COMPLETED_PROHIBITED_ACTION_OR_EFFECT`, `EXFILTRATED_PROTECTED_DATA`, `INSTRUCTION_AUTHORITY_VIOLATION`).
   - Domain-level rejection notice vs policy invariant verdict.
4. **Committed Effect / Protected Disclosure:**
   - Persistent state delta, exfiltration sinks, attacker outcome (`ACHIEVED` vs `BLOCKED`).
   - Observation limitations and missing evidence warnings explicitly surfaced.

---

### 4. Policy-Change Regression & Requirement Change Lineage

1. **Semantic Diffing (`POST /regression/compare`):**
   - Categorizes each rule difference deterministically: `SEMANTICALLY_MODIFIED`, `ADDED`, `REMOVED`, `METADATA_ONLY`, `PROVENANCE_ONLY`, `UNCHANGED`.
2. **Typed Impact Planning (`POST /regression/plans`):**
   - Backend assigns typed decisions to existing test cases: `REGENERATE`, `REVALIDATE`, `RETIRE`, `REVISE`, `RETAIN`, `BLOCKED`.
   - Tracks predecessor and replacement lineage (`case_id` → `replaced_by_case_id`).
3. **Execution Modes (`FRESH_EXECUTION` vs `HISTORICAL_RE_EVALUATION`):**
   - **Fresh Execution:** Invokes the simulated adapter for new or regenerated test cases.
   - **Historical Re-evaluation:** Re-scores existing historical traces against new candidate rules without agent execution. The UI displays an explicit warning that historical re-evaluation does not constitute a new agent invocation or fresh coverage.
4. **Verdict Transitions:**
   - Evaluates transitions (`PASS_TO_PASS`, `PASS_TO_FAIL`, `FAIL_TO_PASS`, `FAIL_TO_FAIL`, `NEW_COVERAGE`, `RETIRED`).
   - Distinguishes **Requirement Change** (`is_requirement_change: true`) from **Agent Regression**, ensuring that an agent failing a tightened policy is not falsely attributed as an agent behavioral regression.

---

### 5. Research Evaluation Interfaces & Proposal Metrics

1. **Benchmark Datasets & Partition Splits:**
   - Versioned datasets with three formal splits: `DEV` (Exploratory), `PILOT` (Calibration), and `HELD_OUT` (Strict Benchmark).
   - Immutable benchmark freezing (`POST /evaluation/datasets/{id}/versions/{v}/freeze`).
2. **Reviewer Agreement Calculator:**
   - Calculates Cohen's Kappa ($\kappa$), Observed Agreement ($P_o$), and Chance Agreement ($P_e$) for blinded review packets:
     $$\kappa = \frac{P_o - P_e}{1 - P_e}$$
3. **Baseline Strategies & Reduced-Evidence Ablations:**
   - Strategies: `C4_POLICY_AWARE` (Proposed), `MANUAL_SUITE`, `GENERIC_MODEL_GENERATOR`, `TEXT_ONLY_EVALUATOR`.
   - Reduced-evidence ablations: `NONE` (Full Evidence Package), `NO_GROUNDING`, `NO_PROVENANCE`, `NO_EFFECTS`.
4. **Consolidated Proposal Metrics (All 6 Categories):**
   - **Category 1: Policy Extraction Quality:** Extraction Precision, Recall, F1, Rule-Source Provenance Accuracy.
   - **Category 2: Generated Policy Tests & Coverage:** Case Validity Rate, Planned Coverage, Observed Policy Coverage, Unexercised Rules.
   - **Category 3: Violation Detection & Reliability:** Detection Precision, Recall, F1, False-PASS Rate.
   - **Category 4: Attacks & Exposure Verification:** Injection Exposure Rate, Attack Success Rate, Attempt Goal Rate, Commit Goal Rate.
   - **Category 5: Legitimate Utility & Attribution Accuracy:** Benign Task Utility Rate, False Refusal Rate, Rule Attribution Accuracy, Source Attribution Accuracy.
   - **Category 6: Policy-Change Regression & Overhead:** Affected Identification Precision/Recall, Adaptation Success Rate, Average Latency (ms).

---

### 6. Automated Verification Summary

| Suite / Command | Scope | Result | Details |
| :--- | :--- | :--- | :--- |
| `c4Phase1.test.js` | Phase 1 Contracts | **10 / 10 PASS** | Taxonomy, API endpoints, XSS safety, generation counters, boundaries. |
| `c4Phase2.test.js` | Phase 2 Contracts | **20 / 20 PASS** | Generation, validation, freezing, 3 payload boundaries, 6 outcome dimensions, idempotency. |
| `c4Phase3.test.js` | Phase 3 Contracts | **18 / 18 PASS** | Regression diffing, impact planning, execution modes, evidence chains, research evaluation. |
| **Total C4 Suite** | `node --test src/features/c4/tests/*.test.js` | **48 / 48 PASS** | 13 test suites, 0 failed, duration ~390ms. |
| **Shared Baseline**| `npm test` | **23 / 23 PASS** | 10 suites across Auth, Session, Model Preference, Shared Projects. |
| **Linter** | `npx oxlint src/features/c4` | **0 Warnings, 0 Errors** | 37 files inspected, 0 errors, 0 warnings. |
| **Production Build** | `npm run build` | **EXIT CODE 0** | Vite production bundle built in ~20s, 0 errors. |
