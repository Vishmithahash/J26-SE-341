# Component 2: State-Aware Multi-Step Workflow Testing
## Phase 1 Frontend API Contract and Endpoint Mapping

This document provides the authoritative mapping between user actions in the Component 2 (C2) Models Workspace and the existing FastAPI backend endpoints under `/api/v1/c2`.

---

### 1. Endpoint Mappings

#### 1.1 List Workflow Models
- **User Action**: Open the Models workspace for the selected active project, or refresh the models list.
- **HTTP Method & Endpoint**: `GET /api/v1/c2/projects/{project_id}/models`
- **Request Parameters**:
  - Path: `project_id` (string, required) - Project identifier scoped to the active project context.
- **Request Headers**:
  - `Authorization: Bearer <token>` (forwarded via shared `request` client; see note on backend authorization).
- **Response Status & Body**:
  - `200 OK`: `list[C2WorkflowModelSummaryResponse]`
    ```json
    [
      {
        "id": "c2_mod_xxx",
        "project_id": "proj_123",
        "model_id": "order_refund_workflow",
        "version": "1.0.0",
        "schema_version": "2026.1",
        "name": "Latest Paid Order Refund Workflow",
        "description": "Workflow for customer refund requests",
        "content_hash": "sha256:abc...",
        "lifecycle_status": "DRAFT", // "DRAFT" | "VALIDATED" | "APPROVED"
        "approved_by": null,
        "approved_at": null,
        "created_at": "2026-10-21T10:00:00Z",
        "updated_at": "2026-10-21T10:00:00Z"
      }
    ]
    ```
- **Readiness & Error States**:
  - `200 OK`: Empty list if no models registered yet.
  - `500 / 503`: Database unavailable or server connection failure.

---

#### 1.2 Retrieve Model Definition
- **User Action**: Select a workflow model from the list or change the version selector dropdown.
- **HTTP Method & Endpoint**: `GET /api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}`
- **Request Parameters**:
  - Path: `project_id` (string, required)
  - Path: `model_id` (string, required)
  - Path: `version` (string, required)
- **Response Status & Body**:
  - `200 OK`: `C2WorkflowModelResponse`
    Contains all summary fields plus:
    - `definition`: Complete `EFSMModelDefinition` object:
      - `states`: `list[StateDefinition]` (`id`, `name`, `type`, `description`, `milestone`)
      - `initial_state_id`: `str`
      - `accepting_state_ids`: `list[str]`
      - `rejection_state_ids`: `list[str]`
      - `variables`: `list[VariableDeclaration]` (`name`, `type`, `domain`, `initial_value`, `description`)
      - `transitions`: `list[TransitionDefinition]` (`id`, `source_state`, `target_state`, `trigger_event`, `guard`, `actions`, `expected_effects`, `deferred_effects`, `source_rules`, `description`)
      - `event_mappings`: `list[EventMapping]` (`event_id`, `tool_name`, `parameter_mappings`, `description`)
      - `invariants`: `list[WorkflowInvariant]` (`id`, `name`, `predicate`, `description`, `source_rule`)
      - `milestones`: `list[MilestoneDefinition]` (`id`, `name`, `state_id`, `required`, `description`)
      - `entity_continuity_rules`: `list[EntityContinuityRule]` (`id`, `entity_type`, `key_field`, `bound_variable`, `description`)
      - `protected_fields`: `list[ProtectedField]` (`entity_type`, `field_path`, `allowed_mutations`, `strict_unchanged_on_rejection`, `description`)
      - `final_outcomes`: `list[FinalOutcome]` (`outcome_id`, `type`, `terminal_state_id`, `description`, `predicate`, `task_prompt`)
      - `builder_version`, `assumptions`, `diagnostics`
    - `review_basis`: `str | null`
    - `review_notes`: `str | null`
- **Readiness & Error States**:
  - `200 OK`: Definition returned successfully.
  - `404 Not Found`: Model or version not found for this project.

---

#### 1.3 Propose & Build Candidate Model (from Workflow Input)
- **User Action**: Fill in the structured workflow input form (or load the reference template) and click "Propose & Build Model".
- **HTTP Method & Endpoint**: `POST /api/v1/c2/projects/{project_id}/models/build?auto_validate=true`
- **Request Parameters**:
  - Path: `project_id` (string, required)
  - Query: `auto_validate` (boolean, default: `true`)
- **Request Body**: `WorkflowInputContract`
  ```json
  {
    "schema_version": "2026.1",
    "project_id": "proj_123",
    "domain": "ecommerce",
    "workflow_id": "order_refund_workflow",
    "name": "Order Refund Workflow",
    "version": "1.0.0",
    "task": "Refund my latest paid order.",
    "business_rules": [
      {
        "rule_id": "RULE_OWNERSHIP",
        "name": "Customer Ownership",
        "description": "Order must belong to customer",
        "category": "eligibility",
        "priority": 1
      }
    ],
    "tool_specifications": [
      {
        "tool_name": "get_customer_orders",
        "description": "Retrieve customer orders",
        "parameters": [
          { "name": "customer_id", "type": "integer", "required": true }
        ],
        "return_type": "list",
        "has_side_effects": false
      }
    ],
    "observable_state_mappings": [
      {
        "entity_type": "orders",
        "primary_key": "id",
        "observable_fields": ["id", "status", "payment_status"]
      }
    ],
    "synthetic_fixture": {
      "fixture_id": "fixture_customer_42",
      "description": "Customer 42 fixture",
      "initial_entities": {},
      "protected_state": {}
    },
    "assumptions": []
  }
  ```
- **Response Status & Body**:
  - `201 Created`: `C2WorkflowModelResponse`
- **Readiness & Error States**:
  - `201 Created`: Candidate model built and persisted with status `DRAFT` (or `VALIDATED` if auto-validate passed).
  - `400 Bad Request`: Route `project_id` does not match payload `project_id`.
  - `409 Conflict`: Model ID with this version already exists.
  - `422 Unprocessable Entity`: `InsufficientInputError` (`{ "message": "...", "diagnostics": [...] }`).

---

#### 1.4 Directly Create Draft Model (EFSM Definition)
- **User Action**: Submit a raw or externally authored EFSM model definition JSON.
- **HTTP Method & Endpoint**: `POST /api/v1/c2/projects/{project_id}/models`
- **Request Parameters**:
  - Path: `project_id` (string, required)
- **Request Body**: `EFSMModelDefinition` (JSON)
- **Response Status & Body**:
  - `201 Created`: `C2WorkflowModelResponse`
- **Readiness & Error States**:
  - `201 Created`: Model created in `DRAFT` status.
  - `400 Bad Request`: Route `project_id` mismatch.
  - `409 Conflict`: Model already exists.
  - `422 Unprocessable Entity`: Schema validation errors in definition.

---

#### 1.5 Validate Model
- **User Action**: Click the "Run Validation" button on an active model version.
- **HTTP Method & Endpoint**: `POST /api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/validate`
- **Request Parameters**:
  - Path: `project_id`, `model_id`, `version`
- **Response Status & Body**:
  - `200 OK`: `C2ValidationReportResponse`
    ```json
    {
      "id": "c2_val_xxx",
      "model_record_id": "c2_mod_xxx",
      "project_id": "proj_123",
      "model_id": "order_refund_workflow",
      "version": "1.0.0",
      "content_hash": "sha256:abc...",
      "is_valid": true,
      "readiness": "READY", // or "MODEL NOT READY"
      "summary": {
        "is_valid": true,
        "readiness": "READY",
        "total_errors": 0,
        "total_warnings": 0,
        "states_count": 6,
        "transitions_count": 7,
        "invariants_count": 1
      },
      "errors": [],
      "warnings": [],
      "diagnostics": {
        "structural_checks_passed": true,
        "semantic_checks_passed": true
      },
      "created_at": "2026-10-21T10:05:00Z"
    }
    ```
- **Readiness & Error States**:
  - `200 OK`: Validation completed. If valid and currently `DRAFT`, backend promotes model to `VALIDATED`.
  - `404 Not Found`: Model does not exist.

---

#### 1.6 Retrieve Validation Reports History
- **User Action**: Open the "Validation History" tab or modal for the selected model version.
- **HTTP Method & Endpoint**: `GET /api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/validation-reports`
- **Request Parameters**:
  - Path: `project_id`, `model_id`, `version`
- **Response Status & Body**:
  - `200 OK`: `list[C2ValidationReportResponse]` (chronological reports, newest first).
- **Readiness & Error States**:
  - `200 OK`: Empty list if never validated.

---

#### 1.7 Check Model Readiness
- **User Action**: Viewed automatically as the authoritative readiness banner on any selected model version.
- **HTTP Method & Endpoint**: `GET /api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/readiness`
- **Request Parameters**:
  - Path: `project_id`, `model_id`, `version`
- **Response Status & Body**:
  - `200 OK`: `ModelReadinessResponse`
    ```json
    {
      "project_id": "proj_123",
      "model_id": "order_refund_workflow",
      "version": "1.0.0",
      "lifecycle_status": "VALIDATED",
      "readiness": "MODEL NOT READY", // Requires is_approved AND validation_passed
      "is_approved": false,
      "content_hash": "sha256:abc...",
      "validation_passed": true,
      "reasons": [
        "Model has not been explicitly reviewed and approved."
      ]
    }
    ```
- **Readiness & Error States**:
  - `200 OK`: Authoritative readiness status returned.
  - `404 Not Found`: Model does not exist.

---

#### 1.8 Record Review and Approval
- **User Action**: Click "Review & Approve", fill in reviewer provenance, review basis, and notes, and submit.
- **HTTP Method & Endpoint**: `POST /api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/approve`
- **Request Parameters**:
  - Path: `project_id`, `model_id`, `version`
- **Request Body**: `ApprovalRequest`
  ```json
  {
    "reviewer_id": "user@example.com",
    "review_basis": "Verified states, guards, and invariants against business specification v1.0",
    "review_notes": "All transitions have valid event triggers; protected state unchanged.",
    "review_type": "SELF_REPORTED_DEVELOPMENT" // "SELF_REPORTED_DEVELOPMENT" | "INDEPENDENT_PEER_REVIEW" | "FORMAL_QA_SIGNOFF"
  }
  ```
- **Response Status & Body**:
  - `200 OK`: `C2WorkflowModelResponse`
    Backend records `approved_by: "{reviewer_id} [{review_type}]"`, sets `lifecycle_status: "APPROVED"`, and freezes the definition.
- **Readiness & Error States**:
  - `200 OK`: Model approved and frozen.
  - `400 Bad Request`: `ApprovalBlockedError` if model has not passed validation, if errors exist, or if validation report is stale.
  - `404 Not Found`: Model does not exist.

---

#### 1.9 Create a New Draft Version
- **User Action**: Click "New Version" on an existing model version to branch a subsequent draft.
- **HTTP Method & Endpoint**: `POST /api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/new-draft`
- **Request Parameters**:
  - Path: `project_id`, `model_id`, `version` (source version)
- **Request Body**: `NewDraftVersionRequest`
  ```json
  {
    "new_version": "1.1.0",
    "description": "Added order cancellation transition and updated guard conditions."
  }
  ```
- **Response Status & Body**:
  - `201 Created`: `C2WorkflowModelResponse`
    New draft created with status `DRAFT` and independent content hash.
- **Readiness & Error States**:
  - `201 Created`: New draft version successfully initialized.
  - `404 Not Found`: Source model version does not exist.
  - `409 Conflict`: Target version already exists for this model.

---

### 2. Backend Authorization Gap & Server Security Blocker

#### 2.1 Exact Endpoints Missing Server-Side Authentication & Project Ownership Enforcement
The FastAPI router for Component 2 (`backend/app/components/c2_state_aware_workflow/api/router.py`) declares route parameters scoped by `project_id: str` and injects `db: DbSession = Annotated[Session, Depends(get_db)]`, but **completely lacks** any dependency on `current_user` (e.g. `Annotated[User, Depends(require_active_user)]`) and performs **zero database checks** to verify whether the calling user owns or is an authorized member of `project_id`.

The exact Phase 1 (and related) endpoints missing server-side authentication and project authorization are:
1. `POST /api/v1/c2/projects/{project_id}/models/build` (Line 320) — Builds/proposes candidate EFSM models.
2. `POST /api/v1/c2/projects/{project_id}/models` (Line 367) — Directly creates draft EFSM models.
3. `GET /api/v1/c2/projects/{project_id}/models` (Line 395) — Lists all workflow models for a project.
4. `GET /api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}` (Line 426) — Retrieves full model definition.
5. `POST /api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/validate` (Line 447) — Executes validation engine on model version.
6. `GET /api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/validation-reports` (Line 469) — Retrieves validation report history.
7. `POST /api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/approve` (Line 485) — Freezes model version and records approval.
8. `POST /api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/new-draft` (Line 519) — Branches new draft versions from an approved model.
9. `GET /api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/readiness` (Line 553) — Returns authoritative readiness status.

*(Note: All subsequent suite generation, evaluation, reporting, and benchmark endpoints in `router.py` similarly lack `current_user` dependencies).*

#### 2.2 Security Blocker Disclosure
- **Crucial Limitation**: Neither client-side route guards (`ProtectedRoute`), nor project-scoped URL parameters, nor frontend request filtering resolve or mitigate this server-side vulnerability.
- Any unauthenticated or unauthorized client capable of sending HTTP requests to the backend server can list, inspect, modify, validate, or approve workflow models for any `project_id`.
- **Classification**: Server-side authorization is an **active integration blocker** to secure multi-user or multi-tenant deployment.
- **Frontend Safeguards**: The C2 frontend strictly isolates outgoing requests to the active user's authorized active project ID, includes the user's bearer token in headers (`Authorization: Bearer <token>`), and never introduces cross-project administrative bypasses.
- **Backend Boundary**: In accordance with the strict read-only boundary on backend files, all backend files remain unchanged.

---

### 3. Shared ProjectContext Response-Unwrap Blocker

#### 3.1 Defect Description
In the shared `ProjectContext` (`frontend/src/context/ProjectContext.jsx`):
- Line 32-33:
  ```javascript
  const res = await projectsApi.getProject(storedId);
  const project = res.project;
  ```
- Line 64-65:
  ```javascript
  const res = await projectsApi.getProject(projectId);
  const project = res.project;
  if (project.lifecycle === 'archived') { ... }
  ```
The backend endpoint `GET /api/v1/projects/{project_id}` returns a `ProjectResponse` object directly:
`{ "project_id": "...", "name": "...", "lifecycle": "active", ... }`.
It does **not** return `{ "project": { ... } }`.
Consequently, `res.project` evaluates to `undefined`, which:
1. Causes `loadActiveProject()` to silently clear the stored selection (`setActiveProjectState(null)`).
2. Causes `selectActiveProject(projectId)` to throw a `TypeError: Cannot read properties of undefined (reading 'lifecycle')`.

#### 3.2 Component 2 Handling & Required Shared Fix
- **One Authoritative Active Project**: Component 2 strictly consumes the shared `ProjectContext` (`activeProject` / `activeProjectId`) and does not maintain an independent active project or private storage bypass.
- **Integration Blocker Notice**: When no active project is resolved in the shared context, C2 renders an explicit blocker notice and provides role-correct navigation (`/admin/projects` for ADMIN, `/app/projects` for USER).
- **Delegation**: Any project selection triggered from C2 delegates strictly to `selectActiveProject(projectId)`. If `selectActiveProject` throws due to the unwrap mismatch, the error is displayed without silently substituting an active project.
- **Required Shared Fix**: In `frontend/src/context/ProjectContext.jsx` (lines 33 and 65), update:
  ```diff
  - const project = res.project;
  + const project = res.project || res;
  ```

---

### 4. Truthful Review Provenance Rules

1. **Default Category**: The approval form defaults strictly to `SELF_REPORTED_DEVELOPMENT`. Independent review is never automatically selected.
2. **Explicit Reviewer Details**: For any claimed non-development category (`INDEPENDENT_PEER_REVIEW` or `FORMAL_QA_SIGNOFF`), explicit reviewer identity, organizational affiliation, review basis, and observation notes are mandatory.
3. **Audit Truthfulness**: The UI labels dropdown options and recorded provenance as client-asserted claims (`Recorded Claim: Independent Review (Unverified by Backend)`). A dropdown selection is never presented as verified independent review.
