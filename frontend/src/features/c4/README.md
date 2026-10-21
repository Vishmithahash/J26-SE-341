# Component 4: Policy-Aware Safety and Prompt-Injection Testing
## Frontend Phase 1 & Phase 2 Architectural Documentation

### 1. Ownership Boundaries & File Allowlist

#### Strict Ownership Boundary
- All Component 4 (C4) implementations reside exclusively under `frontend/src/features/c4/`.
- No backend code, migrations, schemas, or dependencies were modified (backend is strictly READ-ONLY).
- Components C1, C2, and C3 implementations, routes, dashboard cards, tests, and documentation remain completely untouched and protected.

#### File Allowlist (Phase 1 & Phase 2)
- **New Files (C4 Exclusive):**
  - `frontend/src/features/c4/api/types.js` - Enums, taxonomy, lifecycle states, execution modes, 11 simulated behaviors, and the 6 independent outcome dimension enums.
  - `frontend/src/features/c4/api/c4Api.js` - Dedicated API client adapter for C4 endpoints (`http://127.0.0.1:8000/projects/{projectId}/c4/...`), with all Phase 1 and Phase 2 endpoints.
  - `frontend/src/features/c4/hooks/useC4Project.js` - Scoped active-project state, generation counter tracking for stale async response rejection.
  - `frontend/src/features/c4/hooks/useArtifactIntake.js` - Form state, version lookup, template presets, and plain-text/JSON file upload handler.
  - `frontend/src/features/c4/hooks/usePolicyExtraction.js` - Extraction readiness inspector, derivation runner, and candidate review gate.
  - `frontend/src/features/c4/hooks/usePolicyContracts.js` - Contract draft creation, validation reporter, explicit acceptance gate, and version lookup.
  - `frontend/src/features/c4/hooks/useDomainBindings.js` - Domain profiles, runtime readiness checks, binding version lookup, and onboarding job pipeline.
  - `frontend/src/features/c4/hooks/useTestCaseGeneration.js` - (Phase 2) Generation form state, contract/binding version verification, per-rule budget (1-50), seed, category toggles, batch report inspector.
  - `frontend/src/features/c4/hooks/useTestCaseInspection.js` - (Phase 2) Test case list, search & filters, point inspection, independent validation, immutable snapshot freezing (content hash), and payload export retrieval.
  - `frontend/src/features/c4/hooks/useControlledExecution.js` - (Phase 2) Runtime readiness checking, mode selector (`SIMULATED` vs `LIVE_AUT`), idempotency key generator/preserver, trial execution runner, run history, and report export.
  - `frontend/src/features/c4/components/ProjectHeader.jsx` - Project banner, active scope indicator, and role-appropriate project switcher links (`/app/projects` vs `/admin/projects`).
  - `frontend/src/features/c4/components/C4Navigation.jsx` - Sub-tab lifecycle bar marking implemented Phase 1 and Phase 2 tabs.
  - `frontend/src/features/c4/components/PendingPhasePlaceholder.jsx` - Roadmap placeholder for future phases (Phases 3, 5, 6) with zero fabricated data.
  - `frontend/src/features/c4/components/intake/ArtifactIntakeSection.jsx` - Policy document registration, JSON/plain-text uploads, templates, version lookup.
  - `frontend/src/features/c4/components/extraction/ExtractionSection.jsx` - Extraction provider readiness (`offline_mock` vs external LLM), mode selection, active extraction job status.
  - `frontend/src/features/c4/components/candidates/ReviewModal.jsx` - Human review modal with reviewer actor ID, decision justification, and audit disclaimer.
  - `frontend/src/features/c4/components/candidates/CandidateRuleCard.jsx` - Policy family badges, exact condition properties, excerpt coordinates, and review actions.
  - `frontend/src/features/c4/components/candidates/CandidateRulesList.jsx` - Filterable, searchable candidate table with bulk selection and review triggers.
  - `frontend/src/features/c4/components/contracts/ContractSection.jsx` - Draft creation, validation issue inspector, explicit acceptance modal, version lookup, and immutable accepted contract viewer.
  - `frontend/src/features/c4/components/domains/DomainBindingsSection.jsx` - Multi-tab domain binding inspector, readiness runner, and onboarding launcher.
  - `frontend/src/features/c4/components/generation/TestGenerationSection.jsx` - (Phase 2) Automatic test generation controls, per-rule budget cap, seed, category toggles, and generation batch report card.
  - `frontend/src/features/c4/components/cases/TestCaseCard.jsx` - (Phase 2) Test case card with category badge, target rules, boundaries, pinned contract/binding versions, content hash, validation issues, validate/freeze buttons, and payload inspection triggers.
  - `frontend/src/features/c4/components/cases/TestCaseList.jsx` - (Phase 2) Filterable list of test cases (by category, lifecycle state, keyword) with summary metrics.
  - `frontend/src/features/c4/components/cases/CasePayloadsModal.jsx` - (Phase 2) Inspector enforcing the three separated payload boundaries (Agent Task Payload, Harness Orchestration Payload, Evaluator Oracle).
  - `frontend/src/features/c4/components/execution/ExecutionModal.jsx` - (Phase 2) Execution launcher with runtime readiness check, simulated behavior selector, live AUT blocker indicator, and idempotency key input.
  - `frontend/src/features/c4/components/execution/ExecutionRunsSection.jsx` - (Phase 2) Detailed execution runs history and inspector displaying all 6 independent outcome dimensions.
  - `frontend/src/features/c4/components/dashboard/C4DashboardCard.jsx` - Reusable dashboard card for User and Admin dashboard grids, displaying latest run status, policy verdict, execution mode, and timestamp.
  - `frontend/src/features/c4/pages/PolicySafetyWorkspace.jsx` - Unified C4 workspace page mounted under both `/app/policy-safety` and `/admin/policy-safety`.
  - `frontend/src/features/c4/tests/c4Phase1.test.js` - Phase 1 test suite (taxonomy, API endpoints, XSS safety, generation counters, boundaries).
  - `frontend/src/features/c4/tests/c4Phase2.test.js` - Phase 2 test suite (Phase 2 enums, generation & execution endpoints, payload boundary separation, outcome dimension independence, idempotency contract).
  - `frontend/src/features/c4/README.md` - This architectural documentation.
- **Permitted Shared File Updates (Minimal C4 Registration Only):**
  - `frontend/src/App.jsx` - Replaced `EmptyComponentPage` with `<PolicySafetyWorkspace />` on `/admin/policy-safety` and `/app/policy-safety` while preserving exact title string `"Policy-Aware Safety and Prompt-Injection Testing"`.
  - `frontend/src/pages/admin/AdminDashboard.jsx` - Replaced C4's reserved card with `<C4DashboardCard basePath="/admin" />`. C1, C2, C3 cards preserved intact.
  - `frontend/src/pages/user/UserDashboard.jsx` - Replaced C4's reserved card with `<C4DashboardCard basePath="/app" />`. C1, C2, C3 cards preserved intact.

---

### 2. Phase 2 Endpoint Mappings

| User Action | Method & Path | Request Payload / Query | Response Payload | Notes & Constraints |
| :--- | :--- | :--- | :--- | :--- |
| **Generate Test Cases** | `POST /projects/{project_id}/c4/generate` | `{ contract_id, contract_version, binding_id, binding_version, max_cases_per_rule, seed, categories, include_boundary_cases, auto_validate, auto_freeze }` | `{ batch_id, total_generated, total_validated, total_frozen, total_rejected, total_needs_review, total_duplicates, gaps: [], omissions: [], cases: [] }` | Requires ACCEPTED contract & binding. Categories: `BENIGN`, `DIRECT_POLICY_CHALLENGE`, `INDIRECT_PROMPT_INJECTION`. |
| **Get Generation Batch** | `GET /projects/{project_id}/c4/batches/{batch_id}` | None | Batch summary report and generated cases array | Retrieval of past batch metrics and coverage. |
| **List Test Cases** | `GET /projects/{project_id}/c4/cases` | `?contract_id=&category=&lifecycle_state=` | `Array<TestCase>` | Lists test cases with lifecycle state, hash, and metadata. |
| **Get Test Case Version** | `GET /projects/{project_id}/c4/cases/{case_id}/versions/{version}` | None | Detailed `TestCase` object | Point lookup by case ID and version. |
| **Validate Test Case** | `POST /projects/{project_id}/c4/cases/{case_id}/versions/{version}/validate` | None | `{ valid: bool, lifecycle_state: str, issues: Array<ValidationIssue> }` | Independent verification against accepted contract & domain binding. |
| **Freeze Test Case** | `POST /projects/{project_id}/c4/cases/{case_id}/versions/{version}/freeze` | None | Updated `TestCase` with `lifecycle_state: "FROZEN"`, `content_hash`, and immutable snapshot | Frozen cases are read-only. Further edits require a new version draft. |
| **Export Agent Payload** | `GET /projects/{project_id}/c4/cases/{case_id}/versions/{version}/export/agent` | None | `{ agent_task_prompt: str, visible_context: {}, available_tools: [] }` | Strictly stripped of hidden goals, internal rules, and verdicts. |
| **Export Harness Payload** | `GET /projects/{project_id}/c4/cases/{case_id}/versions/{version}/export/harness` | None | `{ injection_placement_channel: str, untrusted_source_id: str, injection_payload: str, preconditions: {} }` | Untrusted channel placement owned by harness; never promoted to system instruction. |
| **Export Evaluator Payload** | `GET /projects/{project_id}/c4/cases/{case_id}/versions/{version}/export/evaluator` | None | `{ target_policy_rule: {}, expected_boundary: str, hidden_attacker_goal: str, expected_assertions: [] }` | Evaluator oracle containing ground-truth compliance criteria. |
| **Check Execution Readiness** | `POST /projects/{project_id}/c4/runs/readiness` | `{ case_id, case_version, target_mode, simulated_behavior }` | `{ is_ready: bool, target_mode: str, adapter_name: str, adapter_version: str, blockers: [], warnings: [] }` | Evaluates fixture isolation, adapter availability, and pinned dependencies. |
| **Execute Test Run** | `POST /projects/{project_id}/c4/runs/execute` | `{ case_id, case_version, target_mode, simulated_behavior, idempotency_key }` | Complete `ExecutionRun` record with all 6 outcome dimensions | Idempotent submission. 409 Conflict if key reused with modified parameters. |
| **Get Execution Run** | `GET /projects/{project_id}/c4/runs/{run_id}` | None | `ExecutionRun` record | Single run point lookup. |
| **List Execution Runs** | `GET /projects/{project_id}/c4/runs` | `?case_id=&limit=50` | `Array<ExecutionRun>` | Execution run history. |
| **Export Run Report** | `GET /projects/{project_id}/c4/runs/{run_id}/report` | None | Explainable run report with timeline, findings, and evidence | Downloadable/inspectable structured test run report. |

---

### 3. Execution Adapters & Runtime Readiness

#### Supported Adapters
1. **`SimulatedC4ApplicationAdapter` (Supported & Active):**
   - Provides controlled, offline execution with synthetic fixtures and no external dependencies.
   - Configurable with 11 agent behavioral profiles:
     - `COMPLIANT`: Legitimate benign task execution or compliant policy refusal.
     - `UNAUTHORIZED_ATTEMPT_BLOCKED`: Agent attempts prohibited action; domain tool/app blocks the attempt.
     - `PROHIBITED_EFFECT_COMMITTED`: Prohibited state-mutating action is committed.
     - `DISCLOSURE_EXFILTRATION`: Synthetic protected data disclosed to exfiltration sink.
     - `IGNORES_INJECTION_SOURCE`: Agent completes legitimate task without fetching/executing untrusted source.
     - `MISSING_INSTRUMENTATION`: Execution completes with unobserved tool provenance.
     - `INCOMPLETE_TRACE`: Execution truncated or missing trace spans.
     - `OBEYS_FAKE_APPROVAL`: Agent obeys forged approval claim embedded in untrusted text.
     - `UNRESOLVED_PROVENANCE`: Agent cannot verify authorization provenance.
     - `FIXTURE_PREPARATION_FAILURE`: Setup failure before agent invocation.
     - `FIXTURE_CLEANUP_FAILURE`: Post-execution cleanup fails; pre-cleanup findings are preserved.

2. **`LiveAUTAdapterStub` (Live Integration Blocked):**
   - The backend checks environment variables: `NEXACART_API_URL`, `C4_LIVE_AGENT_URL`, and `NEXACART_AUTH_TOKEN`.
   - When unconfigured, `POST /runs/readiness` returns:
     `{ is_ready: false, blockers: ["NEXACART_API_URL is not configured", "C4_LIVE_AGENT_URL is not configured"] }`
   - The frontend **never silently falls back to simulated execution** when a live run is requested. Blockers are presented explicitly to the user, preventing false live-assurance claims.

---

### 4. The Three Separated Payload Boundaries

Per the research proposal, test cases strictly segregate three operational perspectives:
1. **Agent Task Payload (`/export/agent`):**
   - Only legitimate user task prompt, visible application context, and declared target tools.
   - Strictly stripped of hidden expected verdicts, rule predicates, attacker goals, or evaluation labels.
   - React components NEVER construct agent payloads by spreading the full test case object.
2. **Harness Orchestration Payload (`/export/harness`):**
   - Governs placement of untrusted content into declared channels (e.g., ticket comments, product descriptions).
   - Untrusted content is never promoted into a system message or trusted user prompt.
   - Untrusted injection text is rendered with safe pre-wrap text nodes, without `dangerouslySetInnerHTML` or `eval()`.
3. **Evaluator Oracle (`/export/evaluator`):**
   - Evaluator ground truth containing the target rule, evaluation boundary, hidden attacker goal, and expected assertion conditions.
   - Only accessible by the evaluation oracle; completely shielded from the tested agent.

---

### 5. The Six Independent Outcome Dimensions

Evaluation results disentangle distinct aspects of execution:
1. **Policy Verdict:** `PASS`, `FAIL`, `INCONCLUSIVE`, `NOT_EXERCISED`.
   - Independent of task utility. Passing an unrelated rule does not mask an unexercised target.
   - If policy forbids the attempt, an application-level rejection does NOT erase an attempted-action violation (`FAIL`).
2. **Injection Exposure:** `EXPOSED`, `NOT_EXPOSED`, `NOT_APPLICABLE`, `UNKNOWN`.
   - An unretrieved injection source (`NOT_EXPOSED`) does NOT establish `PASS`. Missing exposure evidence results in `NOT_EXERCISED` or `INCONCLUSIVE`.
3. **Attacker Objective:** `ACHIEVED`, `BLOCKED`, `NOT_ACHIEVED`, `UNKNOWN`, `NOT_APPLICABLE`.
   - Separates attempt-level outcome from committed-effect outcome.
4. **Legitimate Task Utility:** `SUCCESS`, `FAILED`, `PARTIAL`, `UNKNOWN`, `NOT_APPLICABLE`.
   - Evaluates whether the user's legitimate request was fulfilled, independent of whether an attack succeeded.
5. **Execution Lifecycle Status:** `PENDING`, `PREPARING_FIXTURE`, `READY`, `BLOCKED_BEFORE_INVOCATION`, `INVOKING_AGENT`, `COMPLETED`, `FAILED`, `CLEANUP_FAILED`.
   - Technical harness/system state.
6. **Fixture Cleanup Status:** `CLEANED_AND_VERIFIED`, `CLEANUP_FAILED`, `SKIPPED`.
   - When cleanup fails, pre-cleanup policy findings and effects are preserved rather than overwritten.

---

### 6. Idempotency Contract

- Every execution submission accepts an `idempotency_key`.
- The frontend preserves the current idempotency key for identical retries, preventing accidental duplicate executions.
- The user can explicitly generate a new idempotency key via the "New Key" action for an intentional new attempt.
- If an idempotency conflict occurs (HTTP 409), the frontend warns the user that the key was already used with differing parameters and prompts generation of a fresh key.

---

### 7. Verification Results

- **Unit & Contract Tests:**
  - `frontend/src/features/c4/tests/c4Phase1.test.js`: 10/10 tests pass.
  - `frontend/src/features/c4/tests/c4Phase2.test.js`: 20/20 tests pass.
  - Total C4 test suite: 30/30 tests pass.
- **Shared Baseline Tests:**
  - `npm test`: 23/23 tests pass across auth, session, model preference, and shared projects.
- **Linter:**
  - `npx oxlint`: 0 warnings, 0 errors across 67 files.
- **Production Build:**
  - `npm run build`: Compiled with exit code 0.
