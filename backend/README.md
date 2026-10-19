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
| `app/components/c3_robustness_recovery` | **C3: Robustness and Failure Recovery Testing** | **Phase 1, Phase 2 & Phase 3 Implemented** (Phases 4–6 Unimplemented) |
| `app/components/c4_policy_prompt_injection` | **C4: Policy-Aware Safety and Prompt-Injection Testing** | Reserved (Not implemented) |

---

## Component 3: Robustness and Failure Recovery Testing

### Six-Phase Implementation Roadmap
1. **Phase 1: Contracts, Fault Catalogue, Static Validation and APIs** &mdash; **IMPLEMENTED (Stateless Foundation)**
2. **Phase 2: One-Tool Integration, Matched Trials, Verified Timeout Exposure and Safeguards** &mdash; **IMPLEMENTED (Demonstrated Vertical Slice)**
3. **Phase 3: Automatic Generation, Frozen Suites, Remaining Fault Families and Supported Post-Commit Experiments** &mdash; **IMPLEMENTED (Pure Generation & Bounded Suites)**
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
