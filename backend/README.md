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

### 5. Add Neon Database Credentials
Open `backend/.env` and paste your actual Neon connection string:
```env
DATABASE_URL="postgresql://username:password@hostname/database?sslmode=require"
```
*Note: Unencrypted connections (`sslmode=disable`, `allow`, `prefer`) are strictly rejected. The framework automatically normalizes the driver to `postgresql+psycopg` and preserves parameters such as `channel_binding`.*

> **Direct vs. Pooled Connection String:**
> For local development and migrations, prefer Neon's direct connection string (endpoint without `-pooler`). Pooled URLs can cause limitations with schema migrations when DDL transactions or session locks are required.

---

### 6. Verify Alembic Migrations
Verify migration status against your database:
```powershell
alembic current
alembic heads
```
*Note: "No revisions yet" is the expected result at this stage. No domain models or tables have been created yet. `alembic upgrade head` will be used once the first actual model migration is generated.*

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

| Directory | Full Component Name & Responsibility | Phase Status |
|---|---|---|
| `app/components/c1_tool_call_correctness` | **C1: Explainable Tool-Call Correctness Testing** | Reserved (Not implemented) |
| `app/components/c2_state_aware_workflow` | **C2: State-Aware Multi-Step Workflow Testing** | Reserved (Not implemented) |
| `app/components/c3_robustness_recovery` | **C3: Robustness and Failure Recovery Testing** | **Phase 1 Implemented** (Phases 2–6 Unimplemented) |
| `app/components/c4_policy_prompt_injection` | **C4: Policy-Aware Safety and Prompt-Injection Testing** | Reserved (Not implemented) |

---

## Component 3: Robustness and Failure Recovery Testing (Phase 1)

### Six-Phase Implementation Roadmap
1. **Phase 1: Contracts, Fault Catalogue, Static Validation and APIs** &mdash; **IMPLEMENTED (Stateless Foundation)**
2. **Phase 2: One-Tool Integration, Matched Trials, Verified Timeout Exposure and Safeguards** &mdash; *UNIMPLEMENTED*
3. **Phase 3: Automatic Generation, Frozen Suites, Remaining Fault Families and Supported Post-Commit Experiments** &mdash; *UNIMPLEMENTED*
4. **Phase 4: Recovery Evaluation Using Evidence and C2 Facts** &mdash; *UNIMPLEMENTED*
5. **Phase 5: Shared Persistence, Execution Tracking, Results and Reporting** &mdash; *UNIMPLEMENTED*
6. **Phase 6: Second Domain, Research Experiments, Baselines, Metrics and Final Validation** &mdash; *UNIMPLEMENTED*

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

## Shared Integration & Architecture Design Notes (Design Only)

The following integration agreements are documented for team alignment and will be finalized prior to component implementation:
1. **Identifier Conventions**: Uniform format for shared identifiers: `project_id`, `case_id`, `run_id`, and `event_id`.
2. **C3 Matched Trials**: Pairwise identifiers explicitly linking matched baseline (clean) and fault-injected trials for differential evaluation.
3. **Traceability Metadata**: Versioned tracking for test tasks, environment fixtures, tool adapters, agent/LLM models, contract schemas, and evaluation heuristics.
4. **Distinct Verdict Semantics**: Strict conceptual separation between test *readiness*, execution *health*, fault *exposure*, and individual component *verdicts*.
5. **Component Boundary (C2 & C3)**: C2 owns multi-step state machine modeling and workflow state assertions; C3 consumes discrete `true` / `false` / `unknown` state facts to evaluate recovery behavior without re-implementing state checking.
6. **Decoupled Evaluation Rules**: Each research component maintains authoritative ownership of its specialized generation algorithms and evaluation rules.
7. **Unified Execution Infrastructure**: Shared execution orchestration, target fixture/state reset, and evidence transport designed once as a shared capability rather than re-invented across components.
8. **Deduplicated Findings**: Vulnerabilities, faults, and failures reference shared `event_id` traces without multiplying counts for a single root cause.
9. **Database Boundary**: QA framework test metadata, evidence, and run results remain strictly partitioned in the QA framework database, completely isolated from Application-Under-Test (AUT) databases.
10. **Shared Code & Migration Coordination**: Clear code ownership across shared foundations (`app/database.py`, `app/config.py`, `alembic/`) with synchronized Alembic migration reviews across component teams.
