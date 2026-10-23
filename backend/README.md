# Agentic AI QA Framework - Backend Foundation

This is the backend foundation for the research project:
**Agentic AI-Based Software QA Framework for Testing Tool-Using LLM Applications**

It provides a lightweight FastAPI application with Neon PostgreSQL connectivity via SQLAlchemy 2.0 and psycopg 3, Alembic migration scaffold, and health check endpoints.

---

## Local Setup Instructions

Run all commands from the `backend/` directory.

### 1. Verify Python 3.12+
```powershell
python --version
```
Ensure Python 3.12 or higher is installed (e.g., Python 3.13).

---

### 2. Create and Activate Virtual Environment

**Windows PowerShell:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

### 3. Install Dependencies
```powershell
pip install --upgrade pip
pip install -r requirements.txt
python -m pip check
```

---

### 4. Configure Environment Variables
Copy `.env.example` to create your local `.env`:

**Windows PowerShell:**
```powershell
Copy-Item .env.example .env
```

**macOS / Linux:**
```bash
cp .env.example .env
```

---

### 5. Add Neon Database and Authentication Credentials
Open `backend/.env` and paste your actual Neon connection string along with the authentication signing key:
```env
DATABASE_URL="postgresql://username:password@hostname/database?sslmode=require"

# Shared Authentication Configuration (min 32 bytes)
AUTH_SECRET_KEY="replace-with-a-secure-random-secret-key-at-least-32-chars"
AUTH_JWT_ALGORITHM="HS256"
AUTH_ACCESS_TOKEN_EXPIRE_MINUTES="15"
# Optional JWT claims
# AUTH_JWT_ISSUER="agentic-qa-framework"
# AUTH_JWT_AUDIENCE="agentic-qa-api"
```
*Note: Generate a secure secret key using: `python -c "import secrets; print(secrets.token_hex(32))"`.*
*Unencrypted database connections (`sslmode=disable`, `allow`, `prefer`) are strictly rejected. The framework automatically normalizes the driver to `postgresql+psycopg` and preserves parameters such as `channel_binding`.*

> **Direct vs. Pooled Connection String:**
> For local development and migrations, prefer Neon's direct connection string (endpoint without `-pooler`). Pooled URLs can cause limitations with schema migrations when DDL transactions or session locks are required.

---

### 6. Verify and Apply Alembic Migrations
Verify migration status against your database:
```powershell
alembic current
alembic heads
```
To apply all migrations to your database:
```powershell
alembic upgrade head
```
Revisions:
- `e75342624f8c`: C3 persistence tables
- `f1a89c2b4d3e`: Shared `users` table for platform authentication and role-based authorization

---

### 7. Start the Development Server
```powershell
uvicorn app.main:app --reload
```

---

### 8. Interactive Documentation
Open your browser and navigate to:
- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- OpenAPI Specification: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

---

### 9. Check Health Endpoints
- Root: `GET http://127.0.0.1:8000/` &rarr; `{"message":"Agentic AI QA Framework API","status":"running"}`
- App Health: `GET http://127.0.0.1:8000/health` &rarr; `{"status":"healthy"}`
- Database Health: `GET http://127.0.0.1:8000/health/db` &rarr; `{"status":"healthy","database":"connected"}`

---

### 10. Run Tests and Linters
```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
```
All unit tests run with isolated settings and mocked database dependencies to prevent live database coupling or credential exposure.

---

## Modular Monolith Architecture

The backend is structured as a **FastAPI modular monolith**:
- **Single Backend Service**: A unified FastAPI application sharing runtime configuration (`app.config`), database infrastructure (`app.database`), and migration management (`alembic/`).
- **Four Research Component Modules**: Encapsulated within `app/components/`, independently owned by component researchers.
- **Shared Foundation**: All components will leverage the shared SQLAlchemy `Base`, connection pool, and Alembic environment, avoiding duplicate database instances or disconnected servers.
- **Initial Packages**: Reserved component packages for C1, C2, and C4 contain empty package markers. Component 3 (C3) has Phase 1 implemented using the modular divided package structure (`contracts/`, `services/`, `api/`).

---

## Reserved Research Components

| Directory | Full Component Name & Responsibility |
|---|---|
| `app/components/c1_tool_call_correctness` | **C1: Explainable Tool-Call Correctness Testing** |
| `app/components/c2_state_aware_workflow` | **C2: State-Aware Multi-Step Workflow Testing** |
| `app/components/c3_robustness_recovery` | **C3: Robustness and Failure Recovery Testing** |
| `app/components/c4_policy_aware_safety` (alias: `c4_policy_prompt_injection`) | **C4: Policy-Aware Safety and Prompt-Injection Testing** (Phase 1 Implemented — see [docs/c4_phase1_foundation.md](docs/c4_phase1_foundation.md)) |

### Internal Component Organization
- **C4 (Phase 1 Implemented)**:
  - `contracts/`: Typed Pydantic v2 schemas for artifacts, rules, contracts, evidence packages, findings, and future integration protocols.
  - `predicates/`: Safe, allowlisted declarative predicate evaluation engine with Kleene 3-valued logic and integer minor units / Decimal support.
  - `derivation/`: Intake normalization, section offset detection, controlled-language rule extraction, and structured JSON import with source provenance verification.
  - `validation/`: Contract validation, duplicate and conflict detection, and explicit review acceptance.
  - `evaluator/`: Deterministic policy evaluator against supplied evidence with exact verdicts (`PASS`, `FAIL`, `INCONCLUSIVE`, `NOT_EXERCISED`), boundary evaluation (attempt vs. effect vs. disclosure), and attribution reporting.
  - `persistence/`: SQLAlchemy models and repository for artifact versions, candidate rules, policy contracts, and evaluation findings.
  - `api/`: FastAPI route handlers under `/projects/{project_id}/c4`.

- **C3**:
  - `contracts/`: Typed input/output contracts and schemas.
  - `services/`: Validation, fault generation, and domain evaluation logic.
  - `runtime/`: Target adapters, fault injection, execution hooks, and evidence handling.
  - `api/`: FastAPI route handlers and request/response models.

Other components will define responsibility-based subpackages aligned with their specific research requirements.
| Directory | Full Component Name & Responsibility | Phase Status |
|---|---|---|
| `app/components/c1_tool_call_correctness` | **C1: Explainable Tool-Call Correctness Testing** | Reserved (Not implemented) |
| `app/components/c2_state_aware_workflow` | **C2: State-Aware Multi-Step Workflow Testing** | Reserved (Not implemented) |
| `app/components/c3_robustness_recovery` | **C3: Robustness and Failure Recovery Testing** | **Phases 1–7 Implemented & Verified Offline** (Cross-Component Integration Pending) |
| `app/components/c4_policy_prompt_injection` | **C4: Policy-Aware Safety and Prompt-Injection Testing** | Reserved (Not implemented) |

---

## Shared Platform: Authentication & Role-Based Authorization

The shared platform authentication and authorization module (`backend/app/shared/auth/`) provides system-wide user identity, credential security, token issuance, and role enforcement across the backend.

### 1. Roles and Responsibilities

| Role | Intended Audience | Permissions & Scope | Provisioning Model |
|---|---|---|---|
| **`USER`** | Standard QA engineers, researchers, and automated test runners | Authenticate, inspect own identity (`/api/v1/auth/me`), and execute permitted testing workflows | Assigned automatically upon public sign-up (`POST /api/v1/auth/signup`) |
| **`ADMIN`** | Platform operators and system administrators | Elevated access, system user inspection (`GET /api/v1/admin/users`), platform maintenance | Provisioned strictly via internal developer/operator CLI |

- **Public sign-up ALWAYS creates a `USER`**: There is no public parameter or first-user exception to grant `ADMIN`. Injected role fields are rejected.
- **Unified Login**: Both `USER` and `ADMIN` use the same login endpoint (`POST /api/v1/auth/login`).
- **Database-Driven Authorization**: Current user role and active status are loaded fresh from the database on every authenticated request; token claims are not trusted as final authorization authority.

### 2. Endpoints and Request/Response Examples

#### Public Sign-Up (`POST /api/v1/auth/signup`)
Creates a new `USER` account. Rejects unknown or injected fields with HTTP 422. Enforces canonical email uniqueness and minimum 15-character passwords.

**Request:**
```http
POST /api/v1/auth/signup
Content-Type: application/json

{
  "name": "Jane QA Engineer",
  "email": "jane@example.com",
  "password": "correct_horse_battery_staple_12345"
}
```

**Response (`HTTP 201 Created`):**
```json
{
  "id": 1,
  "name": "Jane QA Engineer",
  "email": "jane@example.com",
  "role": "USER",
  "is_active": true,
  "created_at_utc": "2026-10-20T09:30:00Z"
}
```

**Duplicate Email Response (`HTTP 409 Conflict`):**
```json
{
  "detail": "An account with this email already exists."
}
```

#### Credentials Login (`POST /api/v1/auth/login`)
Common login endpoint for `USER` and `ADMIN`. Returns a signed, short-lived JWT bearer token.

**Request:**
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "jane@example.com",
  "password": "correct_horse_battery_staple_12345"
}
```

**Response (`HTTP 200 OK`):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": 1,
    "name": "Jane QA Engineer",
    "email": "jane@example.com",
    "role": "USER",
    "is_active": true,
    "created_at_utc": "2026-10-20T09:30:00Z"
  }
}
```

**Invalid Credentials Response (`HTTP 401 Unauthorized`):**
*Generic error returned identically for unknown email, incorrect password, and inactive accounts:*
```json
{
  "detail": "Invalid email or password."
}
```

#### Current User Identity (`GET /api/v1/auth/me`)
Requires a valid bearer token.

**Request:**
```http
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

**Response (`HTTP 200 OK`):**
```json
{
  "id": 1,
  "name": "Jane QA Engineer",
  "email": "jane@example.com",
  "role": "USER",
  "is_active": true,
  "created_at_utc": "2026-10-20T09:30:00Z"
}
```

#### List Users (`GET /api/v1/admin/users`)
Restricted to callers with `ADMIN` role. Anonymous callers receive HTTP 401; standard `USER` callers receive HTTP 403.

**Request:**
```http
GET /api/v1/admin/users?limit=20&offset=0
Authorization: Bearer <admin_access_token>
```

**Response (`HTTP 200 OK`):**
```json
{
  "items": [
    {
      "id": 1,
      "name": "Platform Operator",
      "email": "admin@example.com",
      "role": "ADMIN",
      "is_active": true,
      "created_at_utc": "2026-10-20T09:00:00Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

**Non-Admin Response (`HTTP 403 Forbidden`):**
```json
{
  "detail": "Administrator access required."
}
```

### 3. Bearer Token Usage
Send the issued token in the `Authorization` HTTP header with the `Bearer` prefix:
```http
Authorization: Bearer <your_jwt_access_token>
```
If credentials are missing or invalid, endpoints respond with `HTTP 401 Unauthorized` and include a `WWW-Authenticate: Bearer` challenge header.

### 4. Required Configuration
The following environment variables configure authentication in `backend/.env`:

| Variable | Required | Default | Description |
|---|---|---|---|
| `AUTH_SECRET_KEY` | **Yes** (for token operations) | None | Cryptographic secret for signing HMAC-SHA256 JWTs (minimum 32 bytes) |
| `AUTH_JWT_ALGORITHM` | No | `"HS256"` | JWT signing algorithm |
| `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `15` | Lifetime of access tokens in minutes |
| `AUTH_JWT_ISSUER` | No | `None` | Expected `iss` claim |
| `AUTH_JWT_AUDIENCE` | No | `None` | Expected `aud` claim |

*Fail-Closed Behavior*: If `AUTH_SECRET_KEY` is not provided, importing and running health checks continues to work, but token issuance and verification immediately fail closed with an explicit 500 error.

### 5. Internal Administrator Provisioning CLI
Administrators cannot be provisioned via HTTP endpoints. Operators manage admin accounts using the internal CLI under `app.shared.auth.cli`.

Run all CLI commands from the `backend/` directory:

#### Create an Administrator
```powershell
python -m app.shared.auth.cli create-admin --name "Admin Operator" --email "admin@example.com"
```
- Passwords are typed interactively using masked `getpass` prompts.
- Passwords are never accepted via CLI flags or printed to stdout.
- Will safely fail if an account with that email already exists.

#### Promote an Existing User
```powershell
# Interactive confirmation prompt
python -m app.shared.auth.cli promote-admin --email "user@example.com"

# Non-interactive confirmation
python -m app.shared.auth.cli promote-admin --email "user@example.com" --yes
```
- Existing user passwords are never modified or reset during promotion.
- Requires explicit operator confirmation.

#### CLI Help (Offline Safe)
```powershell
python -m app.shared.auth.cli --help
python -m app.shared.auth.cli create-admin --help
python -m app.shared.auth.cli promote-admin --help
```
*`--help` and pure module imports never open database connections.*

### 6. Security Architecture & Implementation Details
- **Argon2id Salted Hashing**: Uses `argon2-cffi` to generate memory-hard Argon2id hashes with unique salts. Password hashes are never returned in API payloads.
- **Email Normalization Policy**: Emails are normalized consistently via `email.strip().lower()` during signup, login, and provisioning to prevent canonical alias collision attacks.
- **Timing Attack Mitigation**: When login fails on an unknown email address, a precomputed dummy Argon2id verification executes to equalize execution latency with invalid password attempts.
- **Sanitized Error Responses**: Custom `AuthSafeRoute` handlers sanitize `RequestValidationError` (HTTP 422) so submitted passwords and request payloads are never echoed back.
- **Process-Local Login Throttling**: An in-memory rate limiter tracks consecutive failed login attempts by client IP (default: 5 failures / 60-second window). Exceeding this threshold returns `HTTP 429 Too Many Requests`.
  > **Deployment Scope Notice**: The rate limiter is currently process-local to the running Python worker. In distributed or multi-worker deployments, a shared store (such as Redis) should be introduced to synchronize throttling state across processes.
- **Token Expiry & Revocation**: Access tokens are strictly short-lived (default: 15 minutes). Client-side token deletion discards the credential; tokens remain valid for verification until their cryptographic expiration timestamp (`exp`).

### 7. Authorization Status Across Existing Routes
- **Protected Routes**:
  - `GET /api/v1/auth/me`: Requires authenticated, active user (`require_active_user`).
  - `GET /api/v1/admin/users`: Requires authenticated administrator (`require_admin`).
- **Unprotected Public Platform Routes**:
  - `GET /`: API metadata.
  - `GET /health` and `GET /health/db`: Infrastructure health checks.
  - `POST /api/v1/auth/signup` and `POST /api/v1/auth/login`: Public authentication entry points.
- **Existing Research Routes Awaiting Coordinated Authorization Integration**:
  - Component 3 (C3) endpoints under `/api/v1/c3/*` remain unauthenticated in this platform phase to avoid breaking existing C3 experiments and offline tests. Reusable dependencies (`get_current_user`, `require_active_user`, `require_admin`) are ready for coordinated adoption during multi-component integration.
  - Future components (C1, C2, C4) will adopt the shared dependencies upon API registration.

---

## Component 3: Robustness and Failure Recovery Testing

### Implementation Roadmap
1. **Phase 1: Contracts, Fault Catalogue, Static Validation and APIs** &mdash; **IMPLEMENTED (Stateless Foundation)**
2. **Phase 2: One-Tool Integration, Matched Trials, Verified Timeout Exposure and Safeguards** &mdash; **IMPLEMENTED (Demonstrated Vertical Slice)**
3. **Phase 3: Automatic Generation, Frozen Suites, Remaining Fault Families and Supported Post-Commit Experiments** &mdash; **IMPLEMENTED (Pure Generation & Bounded Suites)**
4. **Phase 4: Recovery Evaluation Using Evidence and C2 Facts** &mdash; **IMPLEMENTED (Deterministic Recovery Evaluator)**
5. **Phase 5: Shared Persistence, Execution Tracking, Results and Reporting** &mdash; **IMPLEMENTED (C3 Persistence & Reporting)**
6. **Phase 6: Second Domain, Research Experiments, Baselines, Metrics and Acceptance Reporting** &mdash; **IMPLEMENTED (Research Architecture & Baselines)**
7. **Phase 7: C3 Internal Completion and Offline Verification** &mdash; **IMPLEMENTED (Offline Completion & Hermetic Verification)**

### Phase 1 Canonical Structure
```text
backend/app/components/c3_robustness_recovery/
    __init__.py
    contracts/
        __init__.py
        schemas.py        # Pydantic v2 typed models, enums, discriminated fault payloads
    services/
        __init__.py
        validation.py     # Fault catalogue and pure deterministic static validation
    api/
        __init__.py
        router.py         # C3 endpoints and scoped sanitized error handling
backend/tests/test_c3_phase1.py
```

### Endpoints
- **`GET /api/v1/c3/fault-catalog`**:
  Returns the catalogue of exactly five operational fault families:
  1. `TIMEOUT_DISCONNECTION`
  2. `TRANSIENT_5XX`
  3. `RATE_LIMIT_429`
  4. `TOOL_UNAVAILABILITY`
  5. `MALFORMED_RESPONSE`
  All entries state `injection_implemented: false` in Phase 1.
- **`POST /api/v1/c3/cases/validate`**:
  Performs deterministic static validation of candidate fault case metadata against adapter capabilities, task/fixture metadata, and recovery contracts. Returns HTTP 200 with `STATIC_VALID` or `TEST_NOT_READY`. Returns HTTP 422 for structural/type validation failures with sanitized error details.

### Static Validation Limitations
- **Metadata Only**: Validates declared consistency and structural rules; does not inspect live environment state.
- **No Runtime Readiness**: Does not verify network connectivity, live tool reachability, or agent availability (`runtime_verified: false`, `execution_ready: false`).
- **No Recovery Scoring**: Does not execute tests or assign pass/fail verdicts (`recovery_verdict: null`).
- **Pending Checks**: Any `STATIC_VALID` result lists mandatory runtime verification checks that must be satisfied during later phases.

### Request Validation Examples

#### 1. Valid Candidate Case (`HTTP 200` &rarr; `STATIC_VALID`)
```json
{
  "candidate_case": {
    "schema_version": "1.0.0",
    "project_id": "proj-qa-001",
    "case_id": "case-c3-001",
    "case_family_id": "fam-timeout-01",
    "domain": "ecommerce",
    "task_id": "task-checkout-01",
    "task_version": "1.0.0",
    "tool_id": "payment_gateway",
    "tool_version": "2.1.0",
    "fixture_id": "fix-cart-populated",
    "fixture_version": "1.0.0",
    "adapter_id": "adapter-payment-01",
    "adapter_version": "1.2.0",
    "recovery_contract_id": "rec-contract-01",
    "recovery_contract_version": "1.0.0",
    "occurrence": 1,
    "interception_hook": "BEFORE_TOOL_CALL",
    "fault_family": "TIMEOUT_DISCONNECTION",
    "effect_phase": "BEFORE_EFFECT",
    "payload": {
      "family": "TIMEOUT_DISCONNECTION",
      "mode": "CALLER_TIMEOUT_EXCEEDED",
      "timing_ms": 5000
    },
    "release_rule": {
      "rule_type": "ATTEMPT_BOUNDED",
      "max_fault_count": 1
    },
    "required_assertions": ["state_order_created"],
    "required_observations": ["network_latency_ms"],
    "caller_timeout_ms": 3000
  },
  "adapter_manifest": {
    "adapter_id": "adapter-payment-01",
    "adapter_version": "1.2.0",
    "schema_version": "1.0.0",
    "tools": [{"tool_id": "payment_gateway", "tool_version": "2.1.0", "mutability": "SIDE_EFFECTING"}],
    "supported_combinations": [{
      "tool_id": "payment_gateway",
      "fault_family": "TIMEOUT_DISCONNECTION",
      "effect_phase": "BEFORE_EFFECT",
      "interception_hook": "BEFORE_TOOL_CALL",
      "supported_occurrence_bounds": {"min_occurrence": 1, "max_occurrence": 5},
      "allowed_release_rule_types": ["ATTEMPT_BOUNDED"],
      "supported_payload_modes": ["CALLER_TIMEOUT_EXCEEDED"],
      "required_observation_capabilities": ["network_latency_ms"]
    }]
  },
  "task_fixture_metadata": {
    "task_id": "task-checkout-01",
    "task_version": "1.0.0",
    "fixture_id": "fix-cart-populated",
    "fixture_version": "1.0.0",
    "domain": "ecommerce",
    "associated_tool_ids": ["payment_gateway"],
    "associated_recovery_contract_ids": ["rec-contract-01"],
    "declared_reset_support": true,
    "declared_observation_support": true,
    "supported_observations": ["network_latency_ms"]
  },
  "recovery_contract": {
    "contract_id": "rec-contract-01",
    "contract_version": "1.0.0",
    "permitted_terminal_outcomes": ["SUCCESS_CLEAN_RECOVERY"],
    "initial_invocation_counts_as_attempt": true,
    "max_task_attempts": 3,
    "max_retries": 2,
    "max_tool_calls_budget": 10,
    "max_total_timeout_ms": 30000,
    "required_state_assertions": ["state_order_created"],
    "allow_duplicate_side_effects": false,
    "allow_retry_on_unverified_commit": false,
    "require_truthful_completion_reporting": true
  }
}
```
**Response (`HTTP 200`):**
```json
{
  "validation_scope": "STATIC_ONLY",
  "validation_status": "STATIC_VALID",
  "runtime_verified": false,
  "execution_ready": false,
  "reasons": [],
  "pending_checks": [
    "Actual fixture reset and initial-state verification",
    "Trigger reachability",
    "Observation access",
    "Installed adapter capability verification",
    "Injection/effect-phase fidelity"
  ],
  "recovery_verdict": null
}
```

#### 2. Rejected Candidate Case (`HTTP 200` &rarr; `TEST_NOT_READY`)
If the candidate case specifies an `AFTER_COMMIT` effect phase on a `READ_ONLY` tool or references an unassociated tool, it returns `HTTP 200` with `TEST_NOT_READY` and safe reason codes:
```json
{
  "validation_scope": "STATIC_ONLY",
  "validation_status": "TEST_NOT_READY",
  "runtime_verified": false,
  "execution_ready": false,
  "reasons": [
    {
      "code": "READ_ONLY_TOOL_INVALID_EFFECT_PHASE",
      "message": "Read-only tool 'catalog_search' cannot specify effect phase 'AFTER_COMMIT'. Read-only tools only support BEFORE_EFFECT or NOT_APPLICABLE.",
      "field_path": "candidate_case.effect_phase"
    }
  ],
  "pending_checks": [],
  "recovery_verdict": null
}
```
*(Structural failures, malformed JSON, or booleans passed for integer counts return `HTTP 422` with sanitized error locations).*

### Testing Commands
Run all unit tests including C3 Phase 1:
```powershell
python -m pytest tests/test_c3_phase1.py
python -m pytest
```

---

## Component 3: Phase 2 Runtime (One-Tool Integration & Verified Exposure)

Phase 2 builds an executable vertical slice demonstrating bounded fault interception, isolated matched trials, and verified exposure evidence.

### Canonical Runtime Structure
```text
backend/app/components/c3_robustness_recovery/runtime/
    __init__.py       # Package marker with clean exports (no eager runner import)
    adapter.py        # Tool and fixture contracts, demonstration implementations, live blocker checks
    evidence.py       # Linked runtime records, sanitization, linkage validation, and local export
    interceptor.py    # Trial-scoped, bounded one-shot timeout interception on the domain tool path
    runner.py         # Matched trial harness runner and developer CLI
backend/tests/test_c3_phase2.py
```

### Supported Timeout Mode & Boundary
- **Fault Family**: `TIMEOUT_DISCONNECTION`
- **Supported Modes**: `CALLER_TIMEOUT_EXCEEDED` and bounded `HANG_INDEFINITELY`. Other modes (`SOCKET_DROP`, `CONNECTION_REFUSED`) are rejected prior to execution and are **never** silently translated.
- **Interception Hook**: `BEFORE_TOOL_CALL` on the domain tool path (not LLM-provider path).
- **Effect Phase**: `BEFORE_EFFECT`. The targeted domain tool call is prevented from forwarding to the target.
- **Timeout Boundary**: Distinguishes elapsed tool-call deadlines from synthetic immediate exceptions and actual socket timeouts. Enforces the declared `caller_timeout_ms` boundary.

### Demonstration Scope vs. Live Limitations
- **Demonstration Scope**: Uses `DemonstrationToolAdapter` (`demonstration_order_placement`) and `DemonstrationFixtureManager` (`fix-demonstration-cart`) providing isolated in-memory logical state stores, deterministic state fingerprinting, and simulated caller retry behavior (`RecoveryActor.SCRIPTED_CALLER`).
- **Live NexaCart AUT Status**: **BLOCKED**. NexaCart source code, live endpoints, and OpenAPI definitions are not present in this workspace. Live mode (`--live` or `TargetMode.LIVE_AUT`) evaluates prerequisites and halts with exit code 2 and explicit blocked prerequisite reporting. It **never** silently falls back to demonstration mode.

### Real Target Prerequisites
To integrate a live target (such as NexaCart), the following external facilities must be provided:
1. `NEXACART_AUT_URL`: Reachable live HTTP/gRPC domain service endpoint.
2. `NEXACART_OPENAPI_SPEC`: Verified OpenAPI tool schema definitions matching domain methods.
3. `NEXACART_FIXTURE_RESET_KEY`: Isolated test tenant / database reset facility.
4. `NEXACART_OBSERVATION_KEY`: Out-of-band state observation access for independent effect verification.

### Fixture Isolation, Reset & Cleanup
- **Unique Namespaces**: Clean and fault trials run under isolated namespaces (`ns_{pair_id}_clean_{uuid}` and `ns_{pair_id}_fault_{uuid}`).
- **Logical State Comparability**: Independent observations before each trial verify that clean and fault runs start from equivalent logical states (`FixtureComparability.EQUIVALENT_LOGICAL_STATE`).
- **Settling & In-Flight Tracking**: Cleanup verifies all active in-flight operations have settled. Unfinished operations produce `CleanupStatus.UNCERTAIN` and permanently mark the namespace as non-reusable.

### Linked Evidence & Status Semantics
- **Linkage Identifiers**: Every record correlates `project_id`, `case_id`, `pair_id`, `trial_id`, `run_id`, `event_id`, and `episode_id`. Linkage is strictly validated before export.
- **Secret Hygiene**: Passwords, tokens, API keys, and Authorization headers are stripped or redacted. Hashing is never used as a substitute for excluding credentials.
- **Distinct Statuses**:
  - `ReadinessStatus`: `READY`, `NOT_READY`, or `BLOCKED`.
  - `ExecutionStatus`: `COMPLETED`, `EXECUTION_ERROR`, `CANCELLED`, or `TIMEOUT`.
  - `ExposureStatus`: `CONFIRMED` (correlated proof of hook entry, prevented forwarding, and caller-observed timeout), `NOT_TRIGGERED` (unreached trigger), or `EXPOSURE_UNKNOWN` (incomplete/contradictory evidence).
  - `CleanQualification`: `QUALIFIED` (clean run achieved goal), `DISQUALIFIED` (clean run failed), or `UNKNOWN`.
  - `FixtureComparability`: `EQUIVALENT_LOGICAL_STATE` or `NON_EQUIVALENT`.
  - `CleanupStatus`: `CLEANED_AND_VERIFIED`, `UNCERTAIN`, or `FAILED`.
  - `RecoveryVerdict`: Strictly `null` (`None`). Recovery scoring is deferred to Phase 4.

### Local Developer CLI
Run the demonstration paired trials:
```powershell
python -m app.components.c3_robustness_recovery.runtime.runner --synthetic
```
Options:
- `--synthetic`: Runs hermetic demonstration matched pair. Exits `0` on successful harness execution.
- `--live`: Attempts execution against live target AUT. Exits `2` (blocked/configuration error) when prerequisites are missing.
- `--export-dir <path>`: Exports sanitized JSON evidence to the specified directory (defaults to `evidence_output/`, which is ignored by Git).
- `--no-retry`: Disables scripted caller retry upon encountering the injected timeout.

### Testing Commands
Run all unit tests across Phase 1 and Phase 2:
```powershell
python -m pytest tests/test_c3_phase2.py
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

---

## Component 3: Phase 3 (Automatic Generation, Frozen Suites, Remaining Faults & AFTER_COMMIT Experiments)

Phase 3 introduces pure deterministic fault case generation, cryptographic suite freezing and integrity verification, delivery mechanisms for all five operational fault families, application-aware post-commit withholding experiments, and a bounded sequential suite runner.

### Canonical Phase 3 Structure
```text
backend/app/components/c3_robustness_recovery/
    contracts/
        generation.py     # Pydantic v2 models: generation requests/responses, policies, counters, FrozenSuite
    services/
        generation.py     # Pure deterministic generation, candidate expansion, static validation, round-robin coverage
        suites.py         # SHA-256 canonical suite digests, semantic case fingerprints, freezing, tamper detection
    runtime/
        faults.py         # Delivery handlers for TRANSIENT_5XX, RATE_LIMIT_429, TOOL_UNAVAILABILITY, MALFORMED_RESPONSE
        suite_runner.py   # Bounded sequential suite runner and local developer CLI
backend/tests/test_c3_phase3.py
```

### Confirmed Phase 2 Corrections
1. **Cancellation vs. Timeout Deadline (Gap A)**:
   - External manual cancellation prior to the declared `caller_timeout_ms` boundary is recorded as `PREMATURE_EXTERNAL_CANCELLATION` with `caller_observed_timeout = False` (`ExposureStatus.NOT_TRIGGERED` / `EXPOSURE_UNKNOWN`).
   - True deadline expiry past the 90% duration threshold is classified as `CALLER_DEADLINE_EXPIRY` with `caller_observed_timeout = True` (`ExposureStatus.CONFIRMED`).
2. **Caller-Observed Outcome Correlation (Gap B)**:
   - Exposure confirmation requires correlated evidence across hook entry, delivery/non-forwarding, actual caller-side exception/status, and matching pair/trial/event identifiers. Interceptor sleep alone never establishes exposure.
3. **Unexecuted Runs & Cleanup Integrity (Gap C)**:
   - Blocked or unexecuted trials record `CleanupStatus.NOT_ASSESSED` (rather than claiming `CLEANED_AND_VERIFIED`) and set `exposure_assessed = False`.
4. **Live Prerequisites (Gap D)**:
   - Removed hard-coded assumptions of separate reset/observation keys; adapter checks only genuine facilities declared and required by configured targets. Live execution against real NexaCart remains strictly blocked while live interfaces are unverified.

---

### Feasible Fault Case Generation API

`POST /api/v1/c3/cases/generate`

Generates feasible, statically validated candidate fault cases from declared tool manifests, fixture metadata, and recovery contracts without accessing databases, networks, LLMs, or runners.

**Request Payload (`FaultGenerationRequest`):**
```json
{
  "project_id": "proj-qa-001",
  "task_id": "task-checkout-demo",
  "task_version": "1.0.0",
  "fixture_id": "fix-demonstration-cart",
  "fixture_version": "1.0.0",
  "domain": "ecommerce",
  "policy": {
    "seed": 42,
    "selection_seed": 42,
    "content_seed": 42,
    "max_cases": 10,
    "max_candidates_examined": 500,
    "coverage_strategy": "ROUND_ROBIN"
  },
  "adapter_manifest": { ... },
  "task_fixture_metadata": { ... },
  "recovery_contract": { ... }
}
```

**Response Payload (`FaultGenerationResponse`):**
- `validation_scope`: Strictly `STATIC_ONLY`.
- `runtime_verified`: `false`.
- `execution_ready`: `false`.
- `recovery_verdict`: Strictly `null` (`None`).
- `generation_status`: `GENERATED`, `NO_FEASIBLE_CASES`, or `FILTERED_OUT`.
- `counters`: Accurately distinct counts:
  - `examined_candidates_count`: Total parameter permutations examined.
  - `valid_candidates_count`: Candidates passing Phase 1 static validation.
  - `rejected_count`: Incompatible or invalid candidates skipped safely.
  - `duplicate_count`: Redundant candidates matching existing semantic fingerprints.
  - `unique_candidates_count`: Distinct feasible candidates discovered.
  - `selected_cases_count`: Cases selected for the frozen suite.
  - `truncated`: `true` if search reached `max_candidates_examined`.
- `frozen_suite`: Cryptographically frozen suite object (if feasible cases exist).

---

### Cryptographic Suite Freezing & Tamper Verification
- **Semantic Case Fingerprint**: Excludes non-deterministic timestamps, randomly generated UUIDs, and UI display labels. Hashes only semantic references, fault family, effect phase, payload content, release rules, assertions, observations, and reproducibility seeds.
- **Canonical Suite Digest (`suite_digest`)**: Computes a deterministic SHA-256 digest over canonical sorted JSON containing suite metadata, generator version, policy, input snapshots, and case fingerprints (excluding self-referential digest fields).
- **Integrity Verification**: `verify_suite_integrity(suite)` recomputes every individual case fingerprint and the top-level suite digest. Any in-memory tampering or version mismatch immediately rejects execution.

---

### Supported Fault Delivery Mechanisms

| Fault Family | Supported Delivery Modes | Effect Phase | Boundary & Delivery Mechanism | Caller Observation |
|---|---|---|---|---|
| `TIMEOUT_DISCONNECTION` | `CALLER_TIMEOUT_EXCEEDED`, bounded `HANG_INDEFINITELY` | `BEFORE_EFFECT` | Non-forwarding sleep past `caller_timeout_ms`. | Transport / deadline timeout exception. |
| `TRANSIENT_5XX` | HTTP 500, 502, 503, 504 | `BEFORE_EFFECT` | Non-forwarding simulated upstream gateway/server failure. | 5xx HTTP error / transport exception with status code. |
| `RATE_LIMIT_429` | HTTP 429 with optional `Retry-After` (absent, 0, or positive seconds) | `BEFORE_EFFECT` | Non-forwarding simulated rate limiter with header parsing. | 429 HTTP error + optional retry-after metadata. |
| `TOOL_UNAVAILABILITY` | `CIRCUIT_BROKEN`, `SERVICE_MAINTENANCE`, `DEPENDENCY_OFFLINE`, `RESOURCE_EXHAUSTED` | `BEFORE_EFFECT` | Non-forwarding service outage simulation across call or bounded window. | Declared unavailability error message / code. |
| `MALFORMED_RESPONSE` | `INVALID_JSON`, `TRUNCATED_JSON`, `SCHEMA_VIOLATION`, `EMPTY_BODY` | `BEFORE_EFFECT` | Response-consumption boundary delivery of corrupted bytes/structure. | JSONDecodeError, validation error, or malformed payload. |
| `TIMEOUT_DISCONNECTION` (Post-Commit) | `CALLER_TIMEOUT_EXCEEDED` | `AFTER_COMMIT` | Effect performed on test double &rarr; verified out-of-band &rarr; response withheld. | Caller experiences lost-response timeout while side effect committed. |

---

### Application-Aware `AFTER_COMMIT` Lost-Response Experiment
Demonstrates delivery of a lost response after a side-effecting domain operation has committed.

**Enforced Execution Order:**
1. **Hook Reached**: Tool invocation reaches `APPLICATION_AWARE_HOOK` (`BEFORE_TOOL_CALL`).
2. **Effect Executed**: The side-effecting operation executes against the target/fixture test double (`demonstration_order_placement`).
3. **Independent Verification**: An out-of-band fixture observation call (`verify_committed_operation`) confirms the exact operation committed independently of the response path. If commit cannot be verified, post-commit exposure cannot be confirmed.
4. **Response Withheld**: The network reply is withheld at the communication boundary.
5. **Caller Timeout**: The caller experiences an unacknowledged lost-response timeout.

*Note: In-memory demonstration uses clearly marked test-double state stores. Real NexaCart live post-commit testing remains BLOCKED.*

---

### Bounded Frozen-Suite Execution
`SuiteRunner` executes frozen test suites sequentially with strict guardrails:
- **Pre-execution Gate**: Re-verifies cryptographic suite digest, case fingerprints, and static validation before any target activity.
- **Runtime Readiness Gate**: Evaluates adapter and fixture prerequisites for every case; unsupported or unready cases are recorded as `BLOCKED` or `UNSUPPORTED` without running.
- **Matched Pair Execution**: Runs matched clean and fault trials using isolated, fresh fixture namespaces (`EQUIVALENT_LOGICAL_STATE`).
- **Control Retention**: Retains failed clean control runs (`DISQUALIFIED`) without retry-until-pass loops.
- **Bounded Duration & Case Limits**: Enforces `max_case_duration_sec`, `max_suite_duration_sec`, and `max_cases`.
- **Cleanup Isolation Halts**: If any trial encounters `CleanupStatus.UNCERTAIN` or `CleanupStatus.FAILED`, execution halts immediately to prevent cross-trial fixture pollution.

---

### Local Developer CLI Commands

#### 1. Execute Demonstration Frozen Suite (10 cases)
```powershell
python -m app.components.c3_robustness_recovery.runtime.suite_runner --synthetic
```

#### 2. Execute Demonstration Suite with Application-Aware AFTER_COMMIT Case (11 cases)
```powershell
python -m app.components.c3_robustness_recovery.runtime.suite_runner --synthetic --after-commit
```

#### 3. Attempt Live Execution (Exits with Code 2 when Prerequisites Missing)
```powershell
python -m app.components.c3_robustness_recovery.runtime.suite_runner --live
```

#### 4. Preserved Phase 2 Single Matched Pair Runner
```powershell
python -m app.components.c3_robustness_recovery.runtime.runner --synthetic
```

#### 5. Generate and Export Frozen Suite File Only
```powershell
python -m app.components.c3_robustness_recovery.runtime.suite_runner --generate --export-dir evidence_output
```

---

### Testing & Verification Commands
```powershell
# Run all Phase 1, Phase 2, Phase 3 and Health tests (66 tests)
python -m pytest

# Run Phase 3 specific tests
python -m pytest tests/test_c3_phase3.py

# Check code formatting and linting
python -m ruff check .
python -m ruff format --check .

# Verify dependency consistency
python -m pip check
```

---

## Component 3: Phase 4 (Recovery Evaluation Using Evidence and C2 Facts)

Phase 4 introduces deterministic, explainable evaluation of recovery behavior from frozen recovery contracts, linked trial evidence, and versioned Component 2 workflow assertion facts. It produces authoritative recovery verdicts without executing targets, modifying agent recovery, or evaluating C2 workflow state machines internally.

### Canonical Phase 4 Structure
```text
backend/app/components/c3_robustness_recovery/
    contracts/
        evaluation.py           # Pydantic v2 models: RecoveryEvaluationRequest/Result, RecoveryVerdict, RuleEvaluationStatus
    services/
        recovery_evaluation.py  # Pure deterministic evaluator implementing 6 fixed recovery rules and 4 verdicts
        c2_facts.py             # Minimal C2 assertion fact interface, scope conflict detection, and status checking
    runtime/
        evaluate.py             # Offline evaluation developer CLI
backend/tests/test_c3_phase4.py # Comprehensive hermetic test suite (21 unit and integration tests)
```

### Confirmed Phase 3 Corrections
1. **Timeout / Cancellation Heuristic Removal**:
   - Removed the 90% elapsed time threshold from `DomainToolInterceptor`. External or manual cancellation before, near, or after the configured deadline no longer manufactures confirmed timeout exposure.
   - Without explicit caller deadline confirmation, cancellation records `PREMATURE_EXTERNAL_CANCELLATION` or `EXTERNAL_CANCELLATION_UNVERIFIED_CAUSE` with `caller_observed_timeout = False` (`ExposureStatus.EXPOSURE_UNKNOWN`).
2. **AFTER_COMMIT Causal Event Ordering**:
   - Exposure verification strictly enforces per-trial causal event ordering:
     `APPLICATION_AWARE_HOOK_ENTERED` &rarr; `INDEPENDENT_COMMIT_OBSERVATION` &rarr; `POST_COMMIT_REPLY_WITHHELD` &rarr; caller lost-response timeout.
   - Contradictory order, missing commit confirmation, or unverified operation IDs immediately rejects exposure.
3. **Malformed Response Consumption Boundary**:
   - Requires evidence that corrupted content reached the caller consumption boundary and produced an observable parser, schema, or decode failure matching the declared mode.
4. **Frozen Artifact Consumption**:
   - `SuiteRunner` loads exported suite JSON artifacts from disk, verifies cryptographic suite digests, and consumes frozen `task_fixture_metadata` and `recovery_contract` without mutating cases or relying on hardcoded lists.

---

### Component 2 Workflow Facts Interface
Component 2 (C2) owns multi-step state machine modeling, workflow state assertion definitions, and evaluation of truth values. Component 3 (C3) consumes discrete facts without recomputing domain state:
- **Fact Schema (`C2AssertionFact`)**: `assertion_id`, `assertion_version`, `value` (`TRUE`, `FALSE`, `UNKNOWN`), `entity_id`, `snapshot_id`, `time_scope`, `evaluator_version`, `provenance`, and `supporting_evidence_refs`.
- **Conflict Detection**: Detects contradictory truth values (both `TRUE` and `FALSE`) within the identical `(assertion_id, entity_id, snapshot_id, time_scope)` scope and safely rejects evaluation.
- **Missing Facts**: Any missing assertion fact is treated strictly as `UNKNOWN`.
- **Live C2 Status**: `check_c2_integration_status()` reports that live C2 service integration is **BLOCKED**; `app.components.c2_state_aware_workflow` contains an empty package marker. Offline and fixture facts are consumed.

---

### Fixed Recovery Rules

| Rule Identifier | Rule Name | Contract Requirements Evaluated | Satisfied Condition | Violated Condition |
|---|---|---|---|---|
| `RULE_COMPLETION` | Task Completion Verification | `permitted_terminal_outcomes`, `required_state_assertions` | Permitted completion outcome achieved and all required C2 state assertions are `TRUE`. | Caller reported unpermitted terminal outcome or required C2 assertion is `FALSE`. |
| `RULE_GRACEFUL_STOPPING` | Graceful Stopping Verification | `permitted_terminal_outcomes` | Caller stopped under an explicitly permitted terminal outcome (e.g. `DEGRADED_COMPLETION`, `ABORT_SAFE`). | Caller stopped under unpermitted terminal outcome or external cancellation. |
| `RULE_BUDGETS` | Recovery Budget Constraints | `max_retries`, `max_tool_calls_budget`, `max_total_timeout_ms` | Retries, tool calls count, and elapsed trial time within contract bounds. | Retries, tool calls, or elapsed trial time exceeded contract budget. |
| `RULE_DUPLICATE_EFFECTS` | Duplicate Side-Effect Prevention | `allow_duplicate_side_effects` | No duplicate side effects observed or reported by C2 facts. | C2 fact confirms duplicate side effect occurred, or multiple distinct side effects observed. |
| `RULE_UNSAFE_RETRIES` | Unsafe Retry Prevention | `allow_retry_on_unverified_commit` | No retry after post-commit fault, or retry safely reused idempotency key. | Retried after post-commit fault without idempotency key reuse. |
| `RULE_TRUTHFUL_COMPLETION` | Truthful Completion Reporting | `require_truthful_completion_reporting` | Caller completion claims match verified C2 facts, or truthful error outcome reported. | Caller claimed success, but required state assertions are demonstrably `FALSE`. |

---

### Authoritative Recovery Verdicts

For eligible trials with confirmed fault exposure:
1. **`PASS_COMPLETED`**:
   - `RULE_COMPLETION` is `SATISFIED`.
   - All applicable recovery budget, duplicate effect, unsafe retry, and truthful completion rules are `SATISFIED`.
   - No required evidence is `UNKNOWN`.
2. **`PASS_GRACEFUL`**:
   - `RULE_GRACEFUL_STOPPING` is `SATISFIED` (caller stopped under an explicitly permitted non-completion outcome).
   - All applicable constraint rules are `SATISFIED`.
   - No required evidence is `UNKNOWN`.
3. **`FAIL`**:
   - Any evaluated recovery rule has status `VIOLATED`.
   - Identifies `first_violated_rule` for explainable diagnostics.
4. **`INCONCLUSIVE`**:
   - No proven violation, but one or more required rules are `UNKNOWN` due to missing C2 facts, incomplete evidence, or `UNCERTAIN` cleanup settling.
5. **`NOT_EVALUATED` (`recovery_verdict = null`)**:
   - Trial was not ready, execution encountered a harness error, exposure was unconfirmed/unassessed, or evidence linkage was invalid.

---

### Recovery Evaluation API

`POST /api/v1/c3/recovery/evaluate`

Evaluates submitted evidence and C2 facts deterministically. Does not execute trials, access networks, write files, or query databases.

**Request Payload (`RecoveryEvaluationRequest`):**
```json
{
  "project_id": "proj-qa-001",
  "case_id": "case-c3-demo-001",
  "evaluator_version": "1.0.0",
  "rule_set_version": "1.0.0",
  "candidate_case": { ... },
  "recovery_contract": { ... },
  "matched_evidence": { ... },
  "c2_facts": [
    {
      "assertion_id": "state_order_created",
      "assertion_version": "1.0.0",
      "value": "TRUE",
      "provenance": "C2_DEMO_FIXTURE"
    }
  ]
}
```

**Response Payload (`RecoveryEvaluationResult`):**
```json
{
  "project_id": "proj-qa-001",
  "case_id": "case-c3-demo-001",
  "pair_id": "pair-28561fd6",
  "evaluator_version": "1.0.0",
  "rule_set_version": "1.0.0",
  "evaluation_status": "EVALUATED",
  "recovery_verdict": "PASS_COMPLETED",
  "first_violated_rule": null,
  "rule_results": [
    {
      "rule_id": "RULE_COMPLETION",
      "rule_name": "Task Completion Verification",
      "status": "SATISFIED",
      "reason_code": null,
      "message": "Verified task completion under permitted outcome 'SUCCESS_AFTER_RETRY'."
    },
    ...
  ],
  "clean_control_limitations": [],
  "demonstration_limitations": [
    "Evaluation performed against in-memory demonstration test double. Does not establish live application-under-test or live agent accuracy."
  ],
  "actor_attribution": "SCRIPTED_CALLER",
  "evaluated_at_utc": "2026-10-18T19:19:11.123456Z"
}
```

---

### Local Developer CLI Commands

#### 1. Offline Recovery Evaluation CLI
Evaluate an exported matched pair evidence artifact:
```powershell
python -m app.components.c3_robustness_recovery.runtime.evaluate --evidence-file evidence_output/evidence_pair_*.json --synthetic-facts
```
Options:
- `--evidence-file <path>`: Required path to trial pair evidence artifact.
- `--c2-facts-file <path>`: Optional path to external C2 facts JSON artifact.
- `--synthetic-facts`: Injects default demonstration fixture C2 facts.
- `--export-dir <path>`: Exports sanitized evaluation result JSON artifact (default: `evidence_output/`).

#### 2. Matched Pair Runner (Phase 2)
```powershell
python -m app.components.c3_robustness_recovery.runtime.runner --synthetic
```

#### 3. Frozen Suite Runner (Phase 3 & Phase 5)
```powershell
# Offline demonstration execution (stateless)
python -m app.components.c3_robustness_recovery.runtime.suite_runner --synthetic
python -m app.components.c3_robustness_recovery.runtime.suite_runner --synthetic --after-commit
python -m app.components.c3_robustness_recovery.runtime.suite_runner --synthetic --suite-file <path>

# Persisted execution with database lifecycle tracking (Phase 5)
python -m app.components.c3_robustness_recovery.runtime.suite_runner --synthetic --persist --project-id proj-demo-qa
python -m app.components.c3_robustness_recovery.runtime.evaluate --evidence-file evidence_output/evidence_pair_*.json --synthetic-facts --persist --project-id proj-demo-qa
```

---

## Component 3 Phase 5: Shared Persistence, Execution Tracking, Results and Reporting

Phase 5 introduces scoped database persistence for versioned C3 experiment artifacts, execution tracking, append-only recovery evaluation history, and backend reporting in the modular monolith.

### Canonical Phase 5 Structure
```text
backend/app/components/c3_robustness_recovery/
    contracts/
        persistence.py         # Typed Pydantic v2 storage, import, query, and reporting contracts
    models/
        __init__.py            # Model export package
        persistence.py         # C3-owned SQLAlchemy models (C3SuiteModel, C3CaseModel, etc.)
    repositories/
        persistence.py         # Scoped repository enforcing project isolation, digests, and transactions
    services/
        storage.py             # Transactional validation, idempotent persistence, and evaluator invocation
        run_tracking.py        # Execution manifest and lifecycle progress tracking
        reporting.py           # Structured JSON aggregation and downloadable CSV summaries
    api/
        persistence_router.py  # REST endpoints for suites, cases, executions, pairs, evals, and reports
        router.py              # Canonical C3 router mounting stateless and persisted routers
    runtime/
        suite_runner.py        # Integrated --persist execution flag and lifecycle updates
        evaluate.py            # Integrated --persist flag for re-evaluating stored evidence
backend/alembic/
    env.py                     # Registered C3 models on shared Base.metadata
    versions/
        e75342624f8c_create_c3_persistence_tables.py # Additive migration for C3 persistence tables
backend/tests/
    test_c3_phase5.py          # Hermetic tests covering all Phase 5 requirements
```

### Data Ownership & Shared-Record References
C3 defines and owns 5 focused database tables in the QA framework database:
- **`c3_suites`**: Immutable snapshots of frozen suites, content digests, schemas, and generator versions.
- **`c3_cases`**: Selected candidate fault cases with case fingerprints and ordering.
- **`c3_executions`**: Execution manifests, lifecycle status (`PLANNED`, `RUNNING`, `COMPLETED`, `CANCELLED`, `ERROR`), target mode, and configuration snapshots.
- **`c3_matched_pairs`**: Differential trial pairs linking clean baseline and fault trials, exposure outcomes, clean qualification, and evidence digests.
- **`c3_evaluations`**: Append-only evaluation history linking input digests, rule evaluation outcomes, actor attributions, and recovery verdicts.

**Shared-Record References**:
- Shared identifiers (`project_id`, `run_id`, `event_id`) are preserved as documented opaque references.
- Suite executions maintain a dedicated `execution_id` without corrupting existing single-trial `run_id` semantics.
- Competing global `Project`, `Run`, or `Event` tables are strictly avoided. Shared platform integrations remain documented as pending until the shared platform contracts are delivered.

### Alembic Migration & Setup Commands
The additive migration `e75342624f8c` registers all C3 persistence tables on the shared `Base.metadata`.

```powershell
# Inspect current heads and status
alembic heads
alembic current

# Apply additive migration to QA framework database
alembic upgrade head
```
> **Database Scope & Safeguards:**
> - Migrations must ONLY be applied to the QA framework PostgreSQL database.
> - Application-Under-Test (AUT) databases are **NEVER** migrated or reset.
> - Default unit and integration tests run against isolated in-memory SQLite (`sqlite:///:memory:`).
> - Opt-in PostgreSQL migration and round-trip verification can be enabled by setting `TEST_DATABASE_URL` against an isolated PostgreSQL test instance.

### Phase 5 REST API Reference (`/api/v1/c3`)
All persistence routes require explicit logical `project_id` scoping, support deterministic sorting, and apply bounded pagination (`limit <= 200`, `offset >= 0`).

| Method | Endpoint | Description | Key Query / Body Parameters |
|---|---|---|---|
| `POST` | `/api/v1/c3/suites/import` | Idempotently import a verified frozen suite and case snapshots. | Body: `SuiteImportRequest` |
| `GET` | `/api/v1/c3/suites` | List stored suites with bounded pagination. | `project_id`, `domain`, `limit`, `offset` |
| `GET` | `/api/v1/c3/suites/{suite_id_or_digest}` | Retrieve stored frozen suite. | `project_id` |
| `GET` | `/api/v1/c3/cases` | List stored candidate cases. | `project_id`, `suite_digest`, `fault_family`, `effect_phase`, `limit`, `offset` |
| `GET` | `/api/v1/c3/cases/{case_id}` | Retrieve individual stored case. | `project_id`, `suite_digest` |
| `POST` | `/api/v1/c3/executions/import` | Import completed/partial execution artifact without executing. | Body: `ExecutionImportRequest` |
| `GET` | `/api/v1/c3/executions` | List tracked executions. | `project_id`, `status`, `target_mode`, `suite_digest`, `limit`, `offset` |
| `GET` | `/api/v1/c3/executions/{execution_id}` | Retrieve tracked execution manifest. | `project_id` |
| `GET` | `/api/v1/c3/matched-pairs` | List matched trial pairs and trial evidence. | `project_id`, `execution_id`, `case_id`, `exposure_status`, `clean_qualification` |
| `GET` | `/api/v1/c3/matched-pairs/{pair_id}` | Retrieve individual matched pair. | `project_id` |
| `POST` | `/api/v1/c3/evaluations/compute` | Authoritatively evaluate stored inputs and append versioned result. | Body: `EvaluationComputeRequest` |
| `GET` | `/api/v1/c3/evaluations` | List recovery evaluation results. | `project_id`, `pair_id`, `case_id`, `recovery_verdict`, `evaluator_version` |
| `GET` | `/api/v1/c3/evaluations/{evaluation_id}` | Retrieve recovery evaluation record. | `project_id` |
| `GET` | `/api/v1/c3/reports/executions/{execution_id}` | Retrieve structured execution report with explicit denominators. | `project_id` |
| `GET` | `/api/v1/c3/reports/executions/{execution_id}/csv` | Download execution summary as CSV file. | `project_id` |

*Existing stateless validation and evaluation endpoints (`/cases/validate`, `/generate`, `/recovery/evaluate`) remain 100% side-effect free.*

### Evaluation History & Idempotency Rules
1. **Append-Only History**: Evaluator executions never overwrite existing records. Re-evaluating stored evidence produces a distinct `evaluation_id` linked to the input digest and current `evaluator_version` (`"1.1.0"`).
2. **Idempotent Imports**:
   - Submitting an identical frozen suite or execution artifact returns the existing persisted record (`200 OK`).
   - Submitting a payload with the same identifier but differing content digest returns a clean conflict (`409 Conflict`).
3. **No Client-Supplied Verdicts**: Clients cannot inject arbitrary verdicts. `/evaluations/compute` loads the authoritative persisted evidence and candidate contracts and executes the canonical evaluator service.
4. **Data Redaction**: Sensitive attributes (credentials, passwords, authorization headers, database connection strings) are strictly excluded and redacted before persistence or export.

### Run Interruption & Failure Handling
- **Harness Failure vs Recovery Verdict**: A harness crash or run cancellation does NOT map to a `FAIL` verdict. Harness errors are recorded with execution status `ERROR` or `CANCELLED`; recovery verdicts remain `null`.
- **Database Write Failure**: If a database write fails following a tool operation, the runner **never** re-executes the tool to reproduce evidence. Instead, it serializes a sanitized local fallback artifact to `--export-dir` for subsequent idempotent import via `/api/v1/c3/executions/import`.
- **Partial Executions**: Executions stopped mid-run preserve planned, executed, blocked, unsupported, and cancelled counts without marking incomplete runs successful.

### Backend Reporting & Denominators
Reports generated via `/api/v1/c3/reports/executions/{execution_id}` provide explicit, non-overlapping counts and clear denominators:
- **Planned Cases Denominator**: Total cases scheduled in the frozen suite manifest.
- **Executed Pairs Denominator**: Total matched baseline-fault pairs initiated by the runner.
- **Evaluated Trials Denominator**: Total confirmed-exposure fault trials evaluated by the recovery evaluation engine.
- **Verdict Counts**: `PASS_COMPLETED`, `PASS_GRACEFUL`, `FAIL`, `INCONCLUSIVE`, `NOT_EVALUATED`.
- **Demonstration Attribution**: Reports generated from in-memory test doubles are explicitly flagged with `demonstration_mode=true` and carry diagnostic limitations preventing misuse as live agent benchmarks.

### Phase 4 Audit Corrections (Evaluator Version 1.1.0)
Before persisting verdicts in Phase 5, confirmed Phase 4 evaluation defects were audited and corrected:
- **Alternative Outcomes**: Fixed boolean branch bug in `RULE_GRACEFUL_STOPPING`. Graceful stopping under an explicitly permitted non-completion branch is respected. Ordinary incomplete tasks fail `RULE_GRACEFUL_STOPPING`. Harness cancellation never establishes graceful stopping.
- **Duplicate Effects**: Repeated observations of a single effect in `BEFORE_EFFECT` are not counted as duplicates. For `AFTER_COMMIT` retries, missing duplicate facts return `UNKNOWN` (`MISSING_DUPLICATE_EFFECT_FACT`).
- **Retry Safety**: Reused idempotency keys alone do not establish safety without verified target enforcement; unverified guarantees return `UNKNOWN` (`UNVERIFIED_TARGET_IDEMPOTENCY_ENFORCEMENT`).
- **Fact Scoping**: `get_c2_fact_value` and `validate_c2_facts` match exact assertion versions, run scopes, and entity IDs. Conflicting facts within scope return `UNKNOWN`.
- **Budgets & Causal Order**: Traces missing budget observations return `UNKNOWN` (`INCOMPLETE_BUDGET_EVIDENCE`). First violation selection follows causal/event order rather than rule list position.

---

## Component 3: Phase 6 — Research Validation, Baselines, Metrics & Acceptance

Phase 6 completes the agreed six-phase research and backend-acceptance plan for Component 3. It establishes reproducible experiment manifest planning with zero family-split leakage, two-domain adapter generality, independent reviewer label provenance, comparative baselines and ablations, pure research metrics with explicit denominators, and bounded multi-project batch execution.

### Canonical Phase 6 Structure
```text
backend/app/components/c3_robustness_recovery/
    contracts/
        research.py            # Typed Pydantic v2 experiment manifests, splits, reviewer labels, and metric contracts
    services/
        experiment_plan.py     # Deterministic manifest generation, split leakage verification, and label validation
        research_metrics.py    # Pure mathematical metric calculation with explicit denominators and safe undefined handling
    runtime/
        banking_adapter.py     # Second domain adapter (wire transfers) with out-of-band ledger commit observation
        research_runner.py     # Bounded batch runner, baseline/ablation evaluation runner, and concurrency verifier
backend/tests/
    test_c3_phase6.py          # Hermetic tests covering Phase 5 defect fixes, splits, metrics, baselines, and batch runs
backend/docs/
    c3_final_acceptance_report.md # Final acceptance matrix and verification report
```

### Key Research Capabilities

1. **Family-Split Isolation & Leakage Prevention**:
   - Cases belong to cohesive `case_family_id` groupings.
   - Partitions into `TRAIN_DEV` and `HELD_OUT_TEST` occur strictly at the case-family level. Sibling variants never cross split boundaries.
   - `verify_split_leakage()` guarantees disjointness; overlapping families raise immediate validation errors.

2. **Two-Domain Target Generality & Honest Prerequisites**:
   - **Domain 1 (E-Commerce)**: `demonstration_order_placement` with order state verification.
   - **Domain 2 (Banking Wire Transfer)**: `wire_transfer` with double-entry balance updates and out-of-band transaction receipt verification (`verify_committed_transfer`).
   - **Live Integration Blockers**: `check_two_domain_prerequisites()` accurately reports live integration as `BLOCKED` since live target endpoints and tested agents are not present in the workspace.

3. **Comparative Baselines & Ablations**:
   - **`OUTCOME_ONLY_BASELINE`**: Re-evaluates evidence without C2 state assertions, blindly trusting caller outcome strings. Production C3 correctly catches silent failures that the baseline misses.
   - **`NO_STATE_FACTS`**: Evaluates recovery with state facts ablated to `UNKNOWN`, proving graceful degradation to `INCONCLUSIVE` without fabricating `True`.
   - **`NO_EXPOSURE_RECEIPTS`**: Ablates injection receipts to `EXPOSURE_UNKNOWN`, accurately classifying trials as ineligible (`NOT_EVALUATED`).

4. **Pure Research Metrics & Denominators**:
   - Standard-library math only (`math`, `collections.Counter`).
   - Clear distinction of units: candidate, case family, matched pair, evaluated trial.
   - Explicit denominators for Accuracy, Precision, Recall, F1, False-Pass Rate, Exposure Rate, and Clean Control Qualification Rate.
   - Undefined cases (e.g., zero positive predictions) return `is_defined=False` with explanatory reasons rather than manufactured 100% scores.

5. **Multi-Project Concurrency Isolation**:
   - Concurrent suite executions across separate tenants (`project_id`) maintain strict boundary isolation without data corruption or cross-tenant query leaks.

### Phase 6 Final Acceptance Report
See [`docs/c3_final_acceptance_report.md`](docs/c3_final_acceptance_report.md) for the comprehensive acceptance matrix, verification evidence, planned vs. achieved counts, and explicit blockers.

---

## Component 3: Phase 7 — Internal Completion & Offline Verification

Phase 7 completes internal C3 functionality, offline research capabilities, confirmed defect corrections, and pure mathematical metrics:
1. **Three-Way Split Protocol (v2.0.0)**: Supports `DEVELOPMENT` (40%), `VALIDATION` (20%), and `HELD_OUT_TEST` (40%) partitions with deterministic case-family allocation, documented integer rounding, and pairwise zero-leakage enforcement (`verify_split_leakage()`).
2. **Offline Baselines and Ablations**:
   - **B1 (Fixed Suite Comparison)**: Predefined cases compared against generated suites under matched budgets.
   - **B2 (Outcome-Only Evaluation)**: Evaluates terminal outcome and final application state, while excluding recovery-trace contract rules (`RULE_BUDGETS`, `RULE_DUPLICATE_EFFECTS`, `RULE_UNSAFE_RETRIES`). Fails if final state is FALSE; does not blindly accept caller success strings.
   - **A1–A4 Ablations**: A1 (capability validation offline), A2 (isolated exposure receipt analysis), A3 (no state facts yields inconclusive), A4 (no effect-phase distinction evaluated as `BEFORE_EFFECT`).
3. **Pure Research Metrics**: Four-way multiclass matrix (`PASS_COMPLETED`, `PASS_GRACEFUL`, `FAIL`, `INCONCLUSIVE`) with accuracy and macro-F1, clean-to-fault outcome transitions, duration overhead, and deterministic family-cluster bootstrap confidence intervals with honest reporting when clusters < 5. Token and cost telemetry are transparently flagged as unavailable offline.
4. **Independent Reviewer Support**: Blinded packet export hiding evaluator verdicts and baseline tags, dual-reviewer Cohen's kappa with explicit category and zero-variance handling, and append-only dispute reconciliation audit trail.
5. **Runtime Safeguards & Persistence Correctness**: Verification of single-fault episodes, BEFORE_EFFECT / AFTER_COMMIT observation, cancellation vs timeout distinction, uncertain cleanup preventing fixture reuse, conflicting case content rejection, and identical cases across multiple suites.

### Phase 7 Delivery Report
See [`docs/c3_phase7_completion_report.md`](docs/c3_phase7_completion_report.md) for the complete Phase 7 delivery report, metrics provenance, and 6-part acceptance breakdown.

---

### Testing & Verification Commands
```powershell
# Run all Phase 1 through Phase 7 tests + Health tests (148 passed, 2 opt-in skipped)
python -m pytest

# Run Phase 7 specific tests (23 tests hermetic SQLite)
python -m pytest tests/test_c3_phase7.py -v

# Run Phase 6 specific tests (15 tests hermetic SQLite, 1 skipped PostgreSQL opt-in)
python -m pytest tests/test_c3_phase6.py -v

# Run Phase 5 persistence tests (13 tests hermetic SQLite, 1 skipped PostgreSQL opt-in)
python -m pytest tests/test_c3_phase5.py -v

# Run Phase 4 recovery evaluation tests (31 tests)
python -m pytest tests/test_c3_phase4.py -v

# Check code formatting and linting
python -m ruff check .
python -m ruff format --check .

# Verify dependency consistency
python -m pip check
```

---

## Shared Backend Integration (Parts 1–3 Implemented & Verified)

The shared integration infrastructure unites the four research components (C1, C2, C3, C4) into an end-to-end, project-scoped QA execution and reporting pipeline.

### Core Capabilities:
1. **Intake & Run Planning**: Authenticated project scoping, pinned configuration versions, and immutable run plans (`IntegrationRunPlanModel`).
2. **Coordinated Shared Execution**: Isolated fixture namespaces, clean/fault matched trial execution (`SharedExecutionCoordinator`), and unified trace capture.
3. **C2-to-C3 Named State Facts**: C2 EFSM state assertions project into C3 recovery evaluation via `AssertionBridgeFacade` preserving provenance.
4. **Combined QA Reporting**: `SharedReportAggregator` consumes authentic component findings, connects C2's publisher (`IntegrationStatus.CONNECTED`), deduplicates repeated findings via stable SHA-256 identities, links related events, and exposes raw vs. grouped defect counts.
5. **Deterministic Evidence Replay**: `EvidenceReplayService` re-evaluates stored trace evidence against pinned configurations without invoking the target application.
6. **Project-Scoped API & Export**: Endpoints under `/api/v1/projects/{project_id}/integration/*` for execution, reporting, JSON/CSV exports, and bounded pagination.

For the full architectural specification, API/CLI references, and operational matrix, see [docs/backend_integration.md](docs/backend_integration.md).

