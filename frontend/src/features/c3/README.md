# Component 3: Robustness and Failure Recovery Testing
## Frontend Phase 1 Architecture & Implementation

This directory contains the complete Phase 1 frontend implementation for **Component 3: Robustness and Failure Recovery Testing**.

### 1. Component Scope & Boundaries

Component 3 evaluates agent and tool robustness under operational failures and verifies failure recovery behaviors against declarative recovery contracts.
In Phase 1, the frontend provides:
- Inspection of the 5 operational fault families from the authoritative backend fault catalogue.
- Structured input preparation for tasks, tool adapters, fixture metadata, recovery contracts, and generation policies.
- Interactive deterministic static validation (`POST /api/v1/c3/cases/validate`) with clear distinction between `STATIC_VALID` and live execution readiness.
- Pure deterministic feasible fault case generation (`POST /api/v1/c3/cases/generate`) with comprehensive candidate counter accounting.
- Inspection and verification of frozen test suites (`FrozenSuite`), cryptographic SHA-256 digests (`suite_digest`), and semantic case fingerprints.
- Project-scoped persistence integration (`POST /api/v1/c3/suites/import`, `GET /api/v1/c3/suites`, `GET /api/v1/c3/cases`).
- Role-separated User (`/app/robustness-recovery`) and Admin (`/admin/robustness-recovery`) workspaces.
- Seamless dashboard cards for User and Admin dashboards respecting existing layout, themes, and density settings.

---

### 2. Authoritative Backend Endpoint Mappings

| Method | Endpoint Path | Backend Router & Function | Description & Payload Requirements | Auth Status |
|---|---|---|---|---|
| `GET` | `/api/v1/c3/fault-catalog` | `router.py:fault_catalog()` | Returns catalogue of the 5 operational fault families (`TIMEOUT_DISCONNECTION`, `TRANSIENT_5XX`, `RATE_LIMIT_429`, `TOOL_UNAVAILABILITY`, `MALFORMED_RESPONSE`). All injection capabilities marked not implemented. | Unauthenticated (Platform research phase) |
| `POST` | `/api/v1/c3/cases/validate` | `router.py:validate_case()` | Pure deterministic static validation of declared candidate case against adapter manifest, fixture metadata, and recovery contract. Body: `FaultValidationRequest`. Returns `STATIC_VALID` or `TEST_NOT_READY`. | Unauthenticated |
| `POST` | `/api/v1/c3/cases/generate` | `router.py:generate_cases()` | Deterministic candidate expansion, static filtering, deduplication, and suite freezing. Body: `FaultGenerationRequest`. Returns `FaultGenerationResponse` with `counters` and `frozen_suite`. | Unauthenticated |
| `POST` | `/api/v1/c3/suites/import` | `persistence_router.py:import_suite_endpoint()` | Idempotently persists a verified frozen suite and its candidate cases. Body: `SuiteImportRequest { project_id, frozen_suite }`. | Unauthenticated (project_id param only) |
| `GET` | `/api/v1/c3/suites` | `persistence_router.py:list_suites_endpoint()` | Lists stored frozen suites for a project with bounded pagination. Query: `project_id` (required), `domain`, `limit`, `offset`. | Unauthenticated (project_id param only) |
| `GET` | `/api/v1/c3/suites/{suite_id_or_digest}` | `persistence_router.py:get_suite_endpoint()` | Retrieves stored frozen suite by ID or SHA-256 digest. Query: `project_id` (required). | Unauthenticated (project_id param only) |
| `GET` | `/api/v1/c3/cases` | `persistence_router.py:list_cases_endpoint()` | Lists stored candidate cases with filters. Query: `project_id` (required), `suite_digest`, `fault_family`, `effect_phase`, `limit`, `offset`. | Unauthenticated (project_id param only) |
| `GET` | `/api/v1/c3/cases/{case_id}` | `persistence_router.py:get_case_endpoint()` | Retrieves single stored candidate case snapshot. Query: `project_id` (required), `suite_digest`. | Unauthenticated (project_id param only) |
| `POST` | `/api/v1/c3/recovery/evaluate` | `router.py:evaluate_recovery_endpoint()` | Deterministic evaluation of recovery rules against evidence and C2 facts. Body: `RecoveryEvaluationRequest`. | Unauthenticated |

---

### 3. Server-Side Authentication & Authorization Gap Analysis

**Identified Architectural Gap:**
1. **Unauthenticated Endpoints**: As documented in `backend/README.md` (line 391), C3 endpoints under `/api/v1/c3/*` remain unauthenticated at the backend routing level (`C3SafeRoute` does not depend on `require_active_user` or `require_admin`).
2. **Project Ownership Enforcement**: The `project_id` parameter accepted by persistence endpoints (`/suites`, `/cases`, etc.) is used solely for logical database table filtering; it does **not** verify that the authenticated caller owns or has member access to the referenced project.
3. **Admin Operation Scope**: The backend currently exposes no dedicated role-based C3 administrator endpoints. Administrative actions must not assume server-enforced privileged global access.

**Frontend Safeguards & Policies Applied:**
- **Advisory Banners**: The frontend transparently displays an authorization status callout (`C3AuthGapNotice`) detailing that server-side auth integration is pending for C3.
- **Client-Side Role Enforcement**: Role-based access control is enforced via React Router and `useAuth()`. The Admin workspace displays project and owner information only when retrieved via authorized endpoints (`/api/v1/projects/{projectId}`).
- **Strict Project Scoping**: The frontend binds all C3 queries and submissions strictly to `activeProject.project_id`. The backend demonstration fallback (`proj-demo-qa`) is never silently substituted.
- **Honest State Handling**: If database persistence is unreachable (HTTP 503) or unconfigured, the UI presents an explicit "Unavailable" state rather than fabricating zero counts. Offline and hermetic test fixtures are provided for demonstration without falsifying backend state.

---

### 4. Fault Families vs. Effect Phases vs. Defects

- **Operational Fault Families (Exactly 5)**:
  1. `TIMEOUT_DISCONNECTION`
  2. `TRANSIENT_5XX`
  3. `RATE_LIMIT_429`
  4. `TOOL_UNAVAILABILITY`
  5. `MALFORMED_RESPONSE`
- **Effect Phases**:
  - `BEFORE_EFFECT`: Injected before side effect occurs on target.
  - `AFTER_COMMIT`: Injected after side effect commits on target, with network reply lost.
  - `PARTIAL_EFFECT`: Injected mid-operation if supported by target capabilities.
  - `NOT_APPLICABLE`: For read-only tools or faults where effect phase does not apply.
- **Important Conceptual Distinction**:
  - **Duplicate Effects are NOT a fault family**. Duplicate side effects (e.g., placing two orders or charging a card twice) are a severe **recovery defect** evaluated under `RULE_DUPLICATE_EFFECTS`, not an injected fault.

---

### 5. Readiness and Validation Semantics

- `STATIC_VALID`: Indicates metadata consistency, parameter type safety, schema validity, and capability match.
- `STATIC_VALID != Execution Readiness`: Static validation does **not** prove that a live adapter, fault injector, or AUT environment is reachable or installed (`runtime_verified: false`, `execution_ready: false`).
- Mandatory pending checks (e.g., fixture reset reachability, observation access, injector installation) are explicitly highlighted to users.
