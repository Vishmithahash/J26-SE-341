# Component 4 (C4) — Policy-Aware Safety & Prompt-Injection Testing
## Frontend Phase 1: Policy Preparation & Contract Onboarding

### 1. Overview
Component 4 addresses the challenge of testing policy-aware safety, authorization constraints, data confidentiality boundaries, and instruction authority (prompt injection resistance) in tool-using LLM agent applications.

Phase 1 provides the frontend foundation for **Policy Preparation**:
- **Artifact Intake**: Ingesting policy documents, role catalogs, and permission specifications.
- **Extraction & Engine Readiness**: Checking extraction provider readiness and deriving candidate rules.
- **Candidate Inspection & Review Gate**: Inspecting authorization, confidentiality, and instruction authority rules with exact conditions, excerpts, ambiguity warnings, and human review decisions (ACCEPT / REJECT).
- **Policy Contract Drafting, Validation & Acceptance**: Assembling reviewed candidates into versioned draft contracts, running validation gates, and explicitly accepting contracts to produce immutable, cryptographically hashed policy versions ready for Phase 2 test generation.

---

### 2. Architecture & File Ownership
All C4 frontend files are strictly encapsulated within `frontend/src/features/c4/`:

```
frontend/src/features/c4/
├── README.md                              # This C4 architecture & mapping document
├── api/
│   ├── types.js                           # C4 enums (families, requirements, boundaries, states)
│   └── c4Api.js                           # C4 API client adapter
├── hooks/
│   ├── useC4Project.js                    # Active project scoping & stale response prevention
│   ├── useArtifactIntake.js               # Artifact intake and registration state
│   ├── usePolicyExtraction.js             # Provider readiness, derivation & candidate review state
│   └── usePolicyContracts.js              # Contract drafting, validation & acceptance state
├── components/
│   ├── ProjectHeader.jsx                  # Active project banner & domain indicator
│   ├── C4Navigation.jsx                   # Sub-navigation bar across all 5 lifecycle phases
│   ├── PendingPhasePlaceholder.jsx        # Honest roadmap placeholder for Phases 2, 3, 5, 6
│   ├── intake/
│   │   └── ArtifactIntakeSection.jsx      # Intake form, file upload & registered artifact list
│   ├── extraction/
│   │   └── ExtractionSection.jsx          # Provider readiness card & derivation triggers
│   ├── candidates/
│   │   ├── CandidateRuleCard.jsx          # Rule properties, conditions & provenance excerpt
│   │   ├── CandidateRulesList.jsx         # Filterable, selectable rule list & metrics
│   │   └── ReviewModal.jsx                # Explicit review decision (ACCEPT / REJECT) modal
│   └── contracts/
│       └── ContractSection.jsx            # Drafting, validation issues & acceptance gate
├── pages/
│   └── PolicySafetyWorkspace.jsx          # Main C4 workspace container
└── tests/
    └── c4Phase1.test.js                   # Node test runner suite for C4 Phase 1
```

**Permitted Shared File Edit:**
- `frontend/src/App.jsx`: Updated routes for `policy-safety` under both `/admin` and `/app` layouts to render `<PolicySafetyWorkspace title="Policy-Aware Safety and Prompt-Injection Testing" icon={ShieldCheck} />`. All other shared components (C1, C2, C3, shared auth, projects, layouts) remain untouched.

---

### 3. Backend Endpoints & Screen Mapping

| Backend Endpoint | HTTP Method | Request Schema / Params | Response Schema | UI Screen / Component |
| :--- | :---: | :--- | :--- | :--- |
| `/projects/{project_id}/c4/extraction/readiness` | `GET` | `provider_id` query param (default: `offline_mock`) | `ExtractionReadinessReport` (`ready`, `status`, `provider_id`, `model_identifier`, `supported_policy_families`, `blockers`) | `ExtractionSection.jsx` (Provider Readiness Badge) |
| `/projects/{project_id}/c4/artifacts` | `POST` | `ArtifactCreate` (`artifact_id`, `artifact_kind`, `raw_content`, `sections`, `metadata`) | `ArtifactVersionRecord` (`artifact_id`, `version`, `content_hash`, `character_count`, `sections`) | `ArtifactIntakeSection.jsx` (Intake Form) |
| `/projects/{project_id}/c4/artifacts/{artifact_id}/versions/{version}` | `GET` | Path params | `ArtifactVersionRecord` | `ArtifactIntakeSection.jsx` (Version Viewer) |
| `/projects/{project_id}/c4/rules/derive` | `POST` | `RuleDerivationRequest` (`artifact_id`, `artifact_version`, `mode`, `structured_payload`) | `list[CandidateRule]` | `ExtractionSection.jsx` (Derive Button) & `CandidateRulesList.jsx` |
| `/projects/{project_id}/c4/extraction/jobs` | `POST` | `ExtractionJobCreate` (`artifact_id`, `artifact_version`, `provider_id`, `options`) | `C4ExtractionJobRecord` | `ExtractionSection.jsx` (Start Job Button) |
| `/projects/{project_id}/c4/extraction/jobs/{job_id}` | `GET` | Path params | `C4ExtractionJobRecord` | `ExtractionSection.jsx` (Active Job Banner) |
| `/projects/{project_id}/c4/candidates/{rule_id}/review` | `POST` | `CandidateRuleReviewRequest` (`decision`, `reviewer`, `review_notes`, `is_synthetic_review`) | `CandidateRule` | `ReviewModal.jsx` (Review Gate) |
| `/projects/{project_id}/c4/contracts` | `POST` | `ContractCreate` (`contract_id`, `rule_ids`, `description`) | `PolicyContractVersion` | `ContractSection.jsx` (Draft Builder) |
| `/projects/{project_id}/c4/contracts/{contract_id}/versions/{version}` | `GET` | Path params | `PolicyContractVersion` | `ContractSection.jsx` (Version Viewer) |
| `/projects/{project_id}/c4/contracts/{contract_id}/versions/{version}/validate` | `POST` | Path params | `ContractValidationResult` (`contract_id`, `version`, `is_valid`, `issues`, `rules_validated_count`) | `ContractSection.jsx` (Validation Assessment Panel) |
| `/projects/{project_id}/c4/contracts/{contract_id}/versions/{version}/accept` | `POST` | `ContractAcceptanceRequest` (`accepted_by`, `rationale`) | `PolicyContractVersion` (`lifecycle_state`: `ACCEPTED`, `content_hash`) | `ContractSection.jsx` (Acceptance Modal & Immutable View) |

---

### 4. Key Security & Quality Guarantees

1. **Safe Policy and Excerpt Rendering:**
   - Policy text and supporting excerpts may contain adversarial prompt injection payloads (e.g., `<script>alert('pwned')</script>`, markdown images, or formatting tricks).
   - In accordance with QA framework security guidelines, all policy texts and excerpts are rendered strictly through standard text nodes or `<pre>` containers, never via `dangerouslySetInnerHTML`.

2. **Project Scoping & Stale Async Isolation:**
   - C4 operations use the shared `useProject()` context.
   - When the active project changes, local C4 state (artifacts, candidates, contract draft, validation results, selected rules) is automatically reset.
   - A request generation counter (`isCurrentGeneration`) tracks async operations and silently drops responses from previous sessions or previous project contexts.
   - When no project is active, project-specific actions are disabled and an alert links directly to the Projects workspace (`/admin/projects` or `/app/projects`).

3. **Provider Architecture Distinction:**
   - The UI clearly distinguishes the deterministic scripted extraction engine (`offline_mock`) from live external LLMs.
   - The shared Model Selection page preference is accurately documented as framework routing metadata, rather than an active external extraction provider.

4. **Exact Threshold Preservation:**
   - Numeric policy thresholds (e.g., `$50.00` refund limit) and compound conditions are preserved verbatim without JavaScript floating-point rounding or distortion.

5. **Validation and Acceptance Gating:**
   - Contract drafting requires at least one candidate rule.
   - Contracts with blocking validation issues (e.g. ambiguous terms, missing provenance) are caught by backend validation gates (`HTTP 400`), preventing illegitimate acceptance in the UI.
   - Accepted contracts are strictly read-only and immutable.

6. **Roadmap Integrity (No Fake Data):**
   - Subsequent lifecycle phases (Phase 2 Test Cases, Phase 3 Runs & Findings, Phase 5 Policy Changes, Phase 6 Evaluation & Reports) are honestly presented as pending with planned endpoints and capabilities. No fake or mock data is generated for unbuilt phases.
