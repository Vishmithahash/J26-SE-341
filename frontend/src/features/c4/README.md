# Component 4: Policy-Aware Safety and Prompt-Injection Testing
## Frontend Phase 1 Implementation & Architectural Documentation

### 1. Ownership Boundaries & File Allowlist

#### Strict Ownership Boundary
- All Component 4 (C4) implementations reside exclusively under `frontend/src/features/c4/`.
- No backend code, migrations, schemas, or dependencies were modified (backend is strictly READ-ONLY).
- Components C1, C2, and C3 implementations, routes, dashboard cards, tests, and documentation remain completely untouched and protected.

#### File Allowlist (Created / Modified)
- **New Files (C4 Exclusive):**
  - `frontend/src/features/c4/api/types.js` - Enums, taxonomy, lifecycle states, and domain types.
  - `frontend/src/features/c4/api/c4Api.js` - Dedicated API client adapter for C4 endpoints (`http://127.0.0.1:8000/projects/{projectId}/c4/...`).
  - `frontend/src/features/c4/hooks/useC4Project.js` - Scoped active-project state, generation counter tracking for stale async response rejection.
  - `frontend/src/features/c4/hooks/useArtifactIntake.js` - Form state, version lookup, template presets, and plain-text/JSON file upload handler.
  - `frontend/src/features/c4/hooks/usePolicyExtraction.js` - Extraction readiness inspector, derivation runner, and candidate review gate.
  - `frontend/src/features/c4/hooks/usePolicyContracts.js` - Contract draft creation, validation reporter, explicit acceptance gate, and version lookup.
  - `frontend/src/features/c4/hooks/useDomainBindings.js` - Domain profiles, runtime readiness checks, binding version lookup, and onboarding job pipeline.
  - `frontend/src/features/c4/components/ProjectHeader.jsx` - Project banner, active scope indicator, and role-appropriate project switcher links (`/app/projects` vs `/admin/projects`).
  - `frontend/src/features/c4/components/C4Navigation.jsx` - Sub-tab lifecycle bar distinguishing implemented Phase 1 tabs from future phases.
  - `frontend/src/features/c4/components/PendingPhasePlaceholder.jsx` - Transparent roadmap for Phases 2, 3, 5, and 6 with zero fabricated data.
  - `frontend/src/features/c4/components/intake/ArtifactIntakeSection.jsx` - Policy document registration, JSON/plain-text uploads (PDF disclaimed), templates, version lookup.
  - `frontend/src/features/c4/components/extraction/ExtractionSection.jsx` - Extraction provider readiness (`offline_mock` vs external LLM), mode selection, active extraction job status.
  - `frontend/src/features/c4/components/candidates/ReviewModal.jsx` - Human review modal with reviewer actor ID, decision justification, and audit disclaimer.
  - `frontend/src/features/c4/components/candidates/CandidateRuleCard.jsx` - Policy family badges, exact condition properties without rounding, excerpt coordinates, and review actions.
  - `frontend/src/features/c4/components/candidates/CandidateRulesList.jsx` - Filterable, searchable candidate table with bulk selection and review modal triggers.
  - `frontend/src/features/c4/components/contracts/ContractSection.jsx` - Draft creation, validation issue inspector, explicit acceptance modal, version lookup, and immutable accepted contract viewer.
  - `frontend/src/features/c4/components/domains/DomainBindingsSection.jsx` - Multi-tab domain binding inspector (roles, tools with bounds, resources, approvals, canaries, untrusted injection surfaces), readiness runner, and onboarding launcher.
  - `frontend/src/features/c4/components/dashboard/C4DashboardCard.jsx` - Reusable dashboard card for User and Admin dashboard component grids.
  - `frontend/src/features/c4/pages/PolicySafetyWorkspace.jsx` - Unified C4 workspace page mounted under both `/app/policy-safety` and `/admin/policy-safety`.
  - `frontend/src/features/c4/tests/c4Phase1.test.js` - Unit and integration test suite covering API mapping, generation counters, XSS prevention, and boundary guarantees.
  - `frontend/src/features/c4/README.md` - This architectural documentation.
- **Permitted Shared File Updates (Minimal C4 Registration Only):**
  - `frontend/src/App.jsx` - Replaced `EmptyComponentPage` with `<PolicySafetyWorkspace />` on `/admin/policy-safety` and `/app/policy-safety` while preserving exact title string `"Policy-Aware Safety and Prompt-Injection Testing"`.
  - `frontend/src/pages/admin/AdminDashboard.jsx` - Replaced C4's reserved card with `<C4DashboardCard basePath="/admin" />`. C1, C2, C3 cards preserved intact.
  - `frontend/src/pages/user/UserDashboard.jsx` - Replaced C4's reserved card with `<C4DashboardCard basePath="/app" />`. C1, C2, C3 cards preserved intact.

---

### 2. Endpoint Mappings

| User Action | Method & Path | Request Payload / Query | Response Payload | Permissions Required | Known Limitations & Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Check Extraction Readiness** | `GET /projects/{project_id}/c4/extraction/readiness` | `?provider_id=offline_mock` | `{ ready: bool, status: str, provider_id: str, model_identifier: str, supported_policy_families: [], blockers: [] }` | Authenticated session (shared token) | Backend uses deterministic regex (`offline_mock`). External LLM providers require server environment configuration. |
| **Register Policy Artifact** | `POST /projects/{project_id}/c4/artifacts` | `{ artifact_id: str, artifact_kind: str, raw_content: str, metadata: {} }` | `{ artifact_id: str, version: int, artifact_kind: str, content_hash: str, raw_content: str, metadata: {}, created_at: str }` | Authenticated session | Plain-text, Markdown, and JSON supported. PDF upload and OCR parsing are not implemented on the server. |
| **Lookup Artifact Version** | `GET /projects/{project_id}/c4/artifacts/{artifact_id}/versions/{version}` | None | `{ artifact_id: str, version: int, raw_content: str, content_hash: str, ... }` | Authenticated session | Requires exact `artifact_id` and positive integer `version`. Server returns 404 if version does not exist. |
| **Derive / Import Candidate Rules** | `POST /projects/{project_id}/c4/rules/derive` | `{ artifact_id: str, artifact_version: int, mode: "controlled_language" \| "structured_import", structured_payload?: [] }` | `Array<CandidateRule>` | Authenticated session | Controlled-language parser extracts authorization, confidentiality, and instruction authority rules from structured clauses. |
| **Start Extraction Job** | `POST /projects/{project_id}/c4/extraction/jobs` | `{ artifact_id: str, artifact_version: int, provider_id: str }` | `{ job_id: str, status: "PENDING" \| "COMPLETED", ... }` | Authenticated session | Background asynchronous extraction job. |
| **Get Extraction Job Status** | `GET /projects/{project_id}/c4/extraction/jobs/{job_id}` | None | `{ job_id: str, status: str, candidate_rules: [], errors: [] }` | Authenticated session | Polls job status until terminal state. |
| **Review Candidate Rule** | `POST /projects/{project_id}/c4/candidates/{rule_id}/review` | `{ decision: "ACCEPTED" \| "REJECTED", reviewer: str, review_notes?: str, is_synthetic_review: false }` | Updated `CandidateRule` with review audit record | Authenticated session | Gated human/dev review decision. Reviewer metadata is client-entered (see Blocker notice). |
| **Create Contract Draft** | `POST /projects/{project_id}/c4/contracts` | `{ contract_id: str, rule_ids: string[], description?: str }` | `{ contract_id: str, version: 1, lifecycle_state: "DRAFT", rules: [], ... }` | Authenticated session | Draft contract binds candidate rules. Contract is mutable in DRAFT state. |
| **Validate Contract Draft** | `POST /projects/{project_id}/c4/contracts/{contract_id}/versions/{version}/validate` | None | `{ valid: bool, issues: Array<{ issue_type: str, rule_id: str, message: str, severity: str }> }` | Authenticated session | Checks for ungrounded rules, conflicts, unsupported targets, or syntax anomalies. |
| **Explicitly Accept Contract** | `POST /projects/{project_id}/c4/contracts/{contract_id}/versions/{version}/accept` | `{ accepted_by: str, rationale?: str }` | Updated `PolicyContract` with `lifecycle_state: "ACCEPTED"` | Authenticated session | Transitions contract to immutable state. Further modifications require a new version draft. |
| **Lookup Contract Version** | `GET /projects/{project_id}/c4/contracts/{contract_id}/versions/{version}` | None | `{ contract_id: str, version: int, lifecycle_state: str, rules: [], accepted_at: str, ... }` | Authenticated session | Point lookup by contract ID and version. |
| **List Domain Profiles** | `GET /projects/{project_id}/c4/domains` | None | `Array<{ domain_id: str, name: str, description: str, binding: {} }>` | Authenticated session | Pre-configured target application domain templates (e.g., `domain-ecommerce-c4`). |
| **Check Domain Readiness** | `GET /projects/{project_id}/c4/domains/{domain_id}/readiness` | `?mode=SIMULATED` | `{ ready: bool, domain_id: str, runtime_mode: str, blockers: [] }` | Authenticated session | Verifies runtime adapter connection, tool call harnesses, and test fixture availability. |
| **List Domain Bindings** | `GET /projects/{project_id}/c4/bindings` | `?binding_id={id}` (optional) | `Array<DomainBinding>` | Authenticated session | Lists registered domain bindings for the current project. |
| **Lookup Binding Version** | `GET /projects/{project_id}/c4/bindings/{binding_id}/versions/{version}` | None | `{ binding_id: str, version: int, roles: [], tools: [], ... }` | Authenticated session | Point lookup by binding ID and version. |
| **Register Domain Binding** | `POST /projects/{project_id}/c4/bindings` | `{ binding_id: str, roles: [], tools: [], resources: [], approval_states: [], protected_data: [], instruction_surfaces: [] }` | Registered `DomainBinding` record | Authenticated session | Registers domain capability schema for policy rule binding. |
| **Start Onboarding Pipeline** | `POST /projects/{project_id}/c4/onboarding/jobs` | `{ domain_id: str, artifact_id: str, artifact_version: int, auto_derive: bool }` | `{ job_id: str, status: "RUNNING", current_step: str, steps: [] }` | Authenticated session | Multi-stage pipeline linking policy artifact registration, rule derivation, and domain capability binding. |
| **Get Onboarding Job Status** | `GET /projects/{project_id}/c4/onboarding/jobs/{job_id}` | None | `{ job_id: str, status: str, current_step: str, steps: [], results: {} }` | Authenticated session | Polls onboarding progress and stage transitions. |

---

### 3. Router Mounting & Development Proxy Details

- **Backend Mount Path:** The C4 backend router is mounted directly at:
  `/projects/{project_id}/c4/...`
  (defined in `backend/app/main.py`: `app.include_router(c4_router, prefix="/projects/{project_id}/c4", tags=["Component 4"])`).
- **Proxy Considerations:** The Vite dev proxy in `vite.config.js` forwards `/api` to port 8000. Because C4 routes start with `/projects/`, `frontend/src/features/c4/api/c4Api.js` addresses `http://127.0.0.1:8000` directly. Backend FastAPI CORS middleware explicitly permits requests originating from `http://localhost:5173` and `http://127.0.0.1:5173`.

---

### 4. Critical Backend Integration Blocker: Server-Side Authorization

> [!WARNING]
> **CRITICAL SECURITY INTEGRATION BLOCKER:** Missing Server-Side Project Authorization
> - **Issue:** In `backend/app/components/c4_policy_aware_safety/api/routes.py`, all endpoints declare parameters `project_id: str` and `db: Session`, but do **NOT** use `Depends(get_current_user)` or verify that the authenticated caller owns or has member access to the referenced `project_id`.
> - **Risk:** Any user with a valid bearer token can query or mutate policy artifacts, candidate rules, contracts, and domain bindings of any other project simply by changing the `project_id` URL parameter.
> - **Boundary Adherence:** Per strict ownership boundaries, backend files are READ-ONLY for the frontend agent. Client-side authorization was NOT implemented as a pseudo-substitute, as client-side checks provide zero true security enforcement.
> - **Remediation Needed (Backend Team):** Add `current_user = Depends(get_current_user)` to all C4 route handlers and verify project membership via `db.query(Project).filter(...)` before executing operations.

---

### 5. Role Workspaces & Disclaimers

1. **QA Framework Roles vs Application Policy Roles:**
   - Framework login accounts (`ADMIN` vs `USER`) govern framework UI access.
   - Application roles described in policy bindings (`CUSTOMER_SUPPORT`, `MANAGER`, `GUEST`, `INVENTORY_CLERK`) govern simulated target LLM authorization boundaries. The UI explicitly separates these two concepts.
2. **Reviewer Provenance Disclaimer:**
   - In `ReviewModal.jsx`, client-entered reviewer actor names are explicitly labelled:
     *"Client-entered reviewer metadata; not independently authenticated server provenance."*
3. **Safe Text Rendering:**
   - All document excerpts, candidate rule statements, and adversarial injection strings are rendered strictly as data (`{text}` React nodes), never through `dangerouslySetInnerHTML` or `eval()`.
4. **State Isolation & Invalidation:**
   - Generation counters in `useC4Project.js` increment whenever the active project or authenticated account switches. Inflight asynchronous promises from previous project scopes are automatically dropped upon resolution.
