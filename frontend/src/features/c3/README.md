# Component 3: Robustness and Failure Recovery Testing
## Frontend Architecture & Implementation (Phase 1, Phase 2 & Phase 3)

This directory contains the complete Phase 1, Phase 2, and Phase 3 frontend implementation for **Component 3: Robustness and Failure Recovery Testing**.

---

### 1. Component Scope & Execution Capabilities

Component 3 evaluates AI agent and tool robustness under operational failures and verifies failure recovery behaviors against declarative recovery contracts.

#### HTTP vs. CLI Execution Capabilities Analysis

| Capability | Exposure Type | Description / Mechanism |
|---|---|---|
| **Single Matched Trial Execution** | **CLI-Only (No HTTP Endpoint)** | Executed via `python -m app.components.c3_robustness_recovery.runtime.runner --synthetic`. No backend HTTP run endpoint is exposed. |
| **Bounded Suite Execution** | **CLI-Only (No HTTP Endpoint)** | Executed via `python -m app.components.c3_robustness_recovery.runtime.suite_runner --synthetic`. No backend HTTP suite run endpoint is exposed. |
| **Runtime Readiness Checks** | **CLI / Static HTTP** | Static metadata validation is exposed over HTTP (`POST /cases/validate`). Live adapter and in-memory runtime checks are performed within runner processes. |
| **Server-Side Cancellation** | **Unsupported** | No server-side HTTP cancellation endpoint exists in the current backend API. |
| **Tracked Execution Retrieval** | **HTTP Available** | `GET /api/v1/c3/executions` & `GET /api/v1/c3/executions/{execution_id}` for authorized project. |
| **Matched Pair Retrieval** | **HTTP Available** | `GET /api/v1/c3/pairs` & `GET /api/v1/c3/pairs/{pair_id}` with exposure & clean qualification filters. |
| **Execution Artifact Import** | **HTTP Available** | `POST /api/v1/c3/executions/import` to persist execution records without live target execution. |
| **Matched Pair Evidence Import** | **HTTP Available** | `POST /api/v1/c3/pairs/import` to persist verified clean/fault trial paired evidence records. |
| **Deterministic Recovery Evaluation**| **HTTP Available** | Pure evaluation preview at `POST /api/v1/c3/recovery/evaluate` & persisted evaluation at `POST /api/v1/c3/evaluations/compute`. |
| **Recovery Evaluation Retrieval**| **HTTP Available** | `GET /api/v1/c3/evaluations` & `GET /api/v1/c3/evaluations/{id}` with verdict & version filters. |
| **Structured Execution Reports** | **HTTP Available** | `GET /api/v1/c3/reports/executions/{id}` & CSV export at `GET /api/v1/c3/reports/executions/{id}/export`. |
| **Research Validation & Splits** | **CLI-Only (No HTTP Endpoint)** | 40/20/40 splits, baselines B0-B3, and ablations A1-A3 executed via `python -m app.components.c3_robustness_recovery.runtime.research_runner`. |

> **Key Rule**: A Python runner function does not establish an HTTP execution endpoint. An execution-import endpoint stores supplied evidence; it does not start a live trial. The frontend clearly labels import actions as **"Import Evidence"** and presents honest live-execution blockers without fabricating execution progress or synthetic runs.

---

### 2. Authoritative Backend Endpoint Mappings

| Method | Endpoint Path | Backend Router & Function | Description & Payload Requirements | Auth Status |
|---|---|---|---|---|
| `GET` | `/api/v1/c3/fault-catalog` | `router.py:fault_catalog()` | Returns catalogue of the 5 operational fault families (`TIMEOUT_DISCONNECTION`, `TRANSIENT_5XX`, `RATE_LIMIT_429`, `TOOL_UNAVAILABILITY`, `MALFORMED_RESPONSE`). | Unauthenticated (Platform research phase) |
| `POST` | `/api/v1/c3/cases/validate` | `router.py:validate_case()` | Pure deterministic static validation of candidate case against adapter manifest, fixture metadata, and recovery contract. Body: `FaultValidationRequest`. | Unauthenticated |
| `POST` | `/api/v1/c3/cases/generate` | `router.py:generate_cases()` | Deterministic candidate expansion, static filtering, deduplication, and suite freezing. Body: `FaultGenerationRequest`. | Unauthenticated |
| `POST` | `/api/v1/c3/suites/import` | `persistence_router.py:import_suite_endpoint()` | Idempotently persists a verified frozen suite and candidate cases. Body: `SuiteImportRequest { project_id, frozen_suite }`. | Unauthenticated (project_id param only) |
| `GET` | `/api/v1/c3/suites` | `persistence_router.py:list_suites_endpoint()` | Lists stored frozen suites for an authorized project. Query: `project_id`, `domain`, `limit`, `offset`. | Unauthenticated (project_id param only) |
| `GET` | `/api/v1/c3/suites/{id}` | `persistence_router.py:get_suite_endpoint()` | Retrieves stored frozen suite by ID or SHA-256 digest. Query: `project_id`. | Unauthenticated (project_id param only) |
| `GET` | `/api/v1/c3/cases` | `persistence_router.py:list_cases_endpoint()` | Lists stored candidate cases with filters. Query: `project_id`, `suite_digest`, `fault_family`, `effect_phase`, `limit`, `offset`. | Unauthenticated (project_id param only) |
| `GET` | `/api/v1/c3/cases/{case_id}` | `persistence_router.py:get_case_endpoint()` | Retrieves single stored candidate case snapshot. Query: `project_id`. | Unauthenticated (project_id param only) |
| `GET` | `/api/v1/c3/executions` | `persistence_router.py:list_executions_endpoint()` | Lists tracked executions with bounded pagination and status filters. Query: `project_id`, `status`, `target_mode`. | Unauthenticated (project_id param only) |
| `GET` | `/api/v1/c3/executions/{id}` | `persistence_router.py:get_execution_endpoint()` | Retrieves tracked suite execution record. Query: `project_id`. | Unauthenticated (project_id param only) |
| `POST` | `/api/v1/c3/executions/import` | `persistence_router.py:import_execution_endpoint()` | Imports execution artifact transactionally without target execution. Body: `ExecutionArtifactImportRequest`. | Unauthenticated (project_id param only) |
| `GET` | `/api/v1/c3/pairs` | `persistence_router.py:list_pairs_endpoint()` | Lists matched trial pairs with exposure and clean-qualification filters. Query: `project_id`, `exposure_status`, `clean_qualification`. | Unauthenticated (project_id param only) |
| `GET` | `/api/v1/c3/pairs/{pair_id}` | `persistence_router.py:get_pair_endpoint()` | Retrieves matched pair evidence record including clean and fault trials. Query: `project_id`. | Unauthenticated (project_id param only) |
| `POST` | `/api/v1/c3/pairs/import` | `persistence_router.py:import_pair_endpoint()` | Validates and persists matched clean/fault pair evidence. Body: `MatchedPairImportRequest`. | Unauthenticated (project_id param only) |
| `POST` | `/api/v1/c3/evaluations/compute`| `persistence_router.py:compute_evaluation_endpoint()` | Executes authoritative evaluation engine and stores evaluation result. Body: `EvaluationComputeRequest`. | Unauthenticated (project_id param only) |
| `GET` | `/api/v1/c3/evaluations` | `persistence_router.py:list_evaluations_endpoint()`| Lists stored recovery evaluations. Query: `project_id`, `pair_id`, `recovery_verdict`. | Unauthenticated (project_id param only) |
| `GET` | `/api/v1/c3/evaluations/{id}` | `persistence_router.py:get_evaluation_endpoint()`| Retrieves stored recovery evaluation record. Query: `project_id`. | Unauthenticated (project_id param only) |
| `POST` | `/api/v1/c3/recovery/evaluate` | `router.py:evaluate_recovery_endpoint()` | Pure deterministic evaluation of recovery rules against evidence and C2 facts. Body: `RecoveryEvaluationRequest`. | Unauthenticated |
| `GET` | `/api/v1/c3/reports/executions/{id}` | `persistence_router.py:get_execution_report_endpoint()` | Comprehensive execution summary and recovery evaluation metrics with explicit denominators. Query: `project_id`. | Unauthenticated (project_id param only) |
| `GET` | `/api/v1/c3/reports/executions/{id}/export` | `persistence_router.py:export_execution_report_csv_endpoint()` | Downloads execution report formatted as CSV attachment. Query: `project_id`. | Unauthenticated (project_id param only) |

---

### 3. Distinct Status Dimensions & Orthogonality

To ensure research validity and eliminate confounding factors, the frontend strictly distinguishes independent status dimensions:

1. **Readiness Status**:
   - `READY`: All pre-execution prerequisites, adapter identity, and fixture capabilities verified.
   - `NOT_READY`: Environment or adapter prerequisites missing.
   - `BLOCKED`: Target AUT unreachable or execution blocked.
   - `TEST_NOT_READY`: Static metadata validation identified unsupported parameters.
2. **Execution Tracking Status**:
   - `PLANNED`, `RUNNING`, `COMPLETED`, `CANCELLED`, `INTERRUPTED`, `ERROR`, `EXECUTION_ERROR`.
   - *Note*: An `EXECUTION_ERROR` in the harness or baseline is not an agent failure.
3. **Exposure Status**:
   - `CONFIRMED`: Injected operational fault matched target tool, hook, and occurrence, and was verifiably delivered.
   - `NOT_TRIGGERED`: Target tool or occurrence was never called during trial execution (e.g. caller exited early).
   - `EXPOSURE_UNKNOWN`: Indeterminate exposure receipt.
   - *Note*: `NOT_TRIGGERED` is **not** a successful recovery test.
4. **Clean Baseline Control Qualification**:
   - `QUALIFIED`: Baseline clean trial ran without fault injection and completed successfully.
   - `DISQUALIFIED`: Clean control failed (e.g. crashed or produced an unhandled exception).
   - *Note*: Failed clean controls are **retained** honestly in the paired results and are never retried until passing or hidden.
5. **Recovery Verdict** (Eligible trials with confirmed exposure only):
   - `PASS_COMPLETED`: Task successfully completed following fault recovery (`Pass: Completed`).
   - `PASS_GRACEFUL`: Task aborted gracefully without state corruption and notified caller/user (`Pass: Graceful`).
   - `FAIL`: Violated recovery contract rules (e.g., duplicate side effects or unverified retries) (`Fail`).
   - `INCONCLUSIVE`: Trial did not qualify for recovery evaluation or evidence was insufficient (`Inconclusive`).
   - *Note*: A harness deadline or timeout is not graceful recovery. Recovery verdicts are never inferred client-side. Ineligible trials return `null` verdict and `NOT_EVALUATED` status.

---

### 4. Component 2 Discrete Assertion Facts Integration

- **Strict Boundary**: Component 3 consumes discrete assertion facts from Component 2 fixtures/evaluations without re-evaluating domain state machines or redefining workflow rules.
- **Truth Values**: Rendered verbatim as `TRUE`, `FALSE`, or `UNKNOWN`.
- **Integrity**: Preserves assertion identifiers (`assertion_id`), versions, provenance (`C2_FIXTURE`), time scopes, snapshot IDs, and supporting evidence references.

---

### 5. Execution Reports & Explicit Denominators

Structured execution reports strictly specify explicit denominators for all counts:
- `planned_cases`: Total candidate fault cases defined in the frozen suite manifest.
- `executed_pairs`: Total matched trial pairs initiated by the runner.
- `evaluated_trials`: Total fault trials evaluated by the recovery evaluation engine.
- Breakdown: Clean qualification, exposure outcomes, recovery verdicts, and cleanup certainty.
- Direct CSV export streamed via `/api/v1/c3/reports/executions/{id}/export`.

---

### 6. Three-Way Research Protocol & Ablation Governance (Phase 7)

- **CLI-Only Tooling**: Evaluated via `python -m app.components.c3_robustness_recovery.runtime.research_runner`.
- **Partitions**: 40% Development, 20% Validation, 40% Blinded Held-Out Test.
- **Baselines**: B0 Clean Control, B1 Blind Retry, B2 Stateless Error Handling, B3 Idempotent Recovery Agent.
- **Ablations**: A1 No Fixture Reset, A2 No Exposure Receipt, A3 No C2 Facts.
- **Prerequisites**: Live research accuracy claims remain blocked until independent reviewed ground truth and inter-annotator agreement thresholds are certified.
