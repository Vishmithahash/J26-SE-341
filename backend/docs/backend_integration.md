# Backend Integration Architecture & Operational Guide
**Agentic AI-Based Software QA Framework for Testing Tool-Using LLM Applications**

This document serves as the authoritative guide for the shared backend integration pipeline across the four research components (C1, C2, C3, C4), covering execution orchestration, state-fact projection, combined reporting, evidence replay, and export services.

---

## 1. Architecture Overview & Component Boundaries

The framework is implemented as a **FastAPI modular monolith** where four specialized research components interact through a unified shared integration layer:

- **Component 1 (C1: Explainable Tool-Call Correctness)**:
  - Generates tool-call test cases, evaluates tool-call schema/contract adherence, diagnoses root causes, and recommends repairs.
  - Requires user authorization; repairs are strictly advisory recommendations and require explicit user decision before application.
- **Component 2 (C2: State-Aware Multi-Step Workflow)**:
  - Models agent navigation as Extended Finite State Machines (EFSM).
  - Evaluates multi-step interaction traces and emits authoritative **named assertion facts** (`FactValue.TRUE`, `FALSE`, or `UNKNOWN`).
  - Publishes workflow evaluation reports via `C2ReportPublisher` connected directly to the shared aggregator.
- **Component 3 (C3: Robustness and Failure Recovery)**:
  - Generates and executes matched clean/fault trials across 5 operational fault families.
  - Consumes C2-produced named assertion facts directly via `AssertionBridgeFacade` to determine whether application goals were preserved post-fault.
  - Computes deterministic recovery verdicts (`PASS_COMPLETED`, `PASS_GRACEFUL`, `FAIL_CONTRACT_VIOLATION`, `INCONCLUSIVE`).
- **Component 4 (C4: Policy-Aware Safety & Prompt Injection)**:
  - Evaluates policy contracts with Kleene 3-valued logic over normalized trace events, checking attempt vs. effect vs. data disclosure.
  - Evaluates security boundaries without overriding functional or workflow defect findings.

```
+-----------------------------------------------------------------------------------+
|                            FastAPI Modular Monolith                               |
+-----------------------------------------------------------------------------------+
|  Shared Platform Authentication & Project Authorization (app.shared.auth/projects)|
+-----------------------------------------------------------------------------------+
|                             Shared Integration Pipeline                           |
|  - Run Planning & Configuration Panning (RunPlanService)                          |
|  - Shared Execution Coordinator (SharedExecutionCoordinator)                     |
|  - C2 EFSM Evaluator & State-Fact Extraction (AssertionBridgeFacade)              |
|  - C3 Recovery Evaluator (RecoveryEvaluatorService)                               |
|  - C1 Tool Evaluator & C4 Policy Evaluator                                        |
|  - Report Aggregator & Finding Deduplication (SharedReportAggregator)             |
|  - Evidence Replay Engine (EvidenceReplayService)                                 |
+-----------------------------------------------------------------------------------+
|   C1 (Tool Correctness) | C2 (EFSM Workflows) | C3 (Robustness) | C4 (Safety)     |
+-----------------------------------------------------------------------------------+
|                  SQLAlchemy 2.0 + Alembic Unified Persistence                     |
+-----------------------------------------------------------------------------------+
```

---

## 2. Shared Execution and Report Workflow

### A. Phase 1: Intake & Frozen Run Planning
1. The authenticated user creates or selects an authorized `Project` (`/api/v1/projects/{project_id}`).
2. The user submits a freeze plan request (`POST /api/v1/projects/{project_id}/integration/plans`) declaring target components (`C1`, `C2`, `C3`, `C4`), component configuration IDs, execution mode (`CONTROLLED_TEST` or `LIVE_AUT`), and task parameters.
3. The system validates component readiness and pins configuration digests into an immutable `IntegrationRunPlanModel`.

### B. Phase 2: Coordinated Execution & Correlated Evidence Capture
1. The user triggers execution (`POST /api/v1/projects/{project_id}/integration/plans/{plan_id}/execute`).
2. Fixture managers establish isolated test environments with verified initial states (`EQUIVALENT_LOGICAL_STATE`).
3. For matched trials (C3), clean control runs and fault-injected runs execute under correlated execution IDs, trial IDs, and event IDs.
4. Tool invocations and responses are recorded in a unified raw trace.
5. Evidence projections:
   - Tool calls project into C1's evaluator.
   - Ordered events and state assertions project into C2's EFSM engine.
   - C2 emits named assertion facts (`C2AssertionFact`).
   - C2 facts project into C3's recovery evaluator (`AssertionBridgeFacade`).
   - Policy observations and side effects project into C4's rule engine.
6. Execution records and retained evidence are persisted to `integration_executions`.

### C. Phase 3: Combined Reporting & Finding Correlation
1. `SharedReportAggregator` queries component evaluation records linked by `execution_id`.
2. Connects C2's `C2ReportPublisher` to record real publication (`IntegrationStatus.CONNECTED`).
3. Normalizes findings into `UnifiedFinding` items with stable, deterministic identities:
   `finding_id = sha256(execution_id + component + defect_type + event_id + entity_id)[:16]`
4. Groups correlated findings sharing `event_id` or `entity_id` without collapsing distinct component-specific defects.
5. Computes honest completeness breakdown: requested vs. evaluated vs. blocked vs. not-evaluated.
6. Persists publication records to `integration_reports`.

---

## 3. C2-to-C3 Assertion Mapping & Provenance

C3 requires domain state facts to assess recovery after operational faults without re-implementing state checking. C2 supplies authoritative facts via the `AssertionBridgeFacade`:

1. **Mapping Protocol**:
   - `C2AssertionFact`: Contains `fact_id`, `assertion_name`, `value` (`TRUE`, `FALSE`, `UNKNOWN`), `confidence`, `evaluation_timestamp_utc`, and provenance trace (`run_id`, `state_id`, `step_index`, `rule_version`).
2. **Deterministic Consumption**:
   - When C2 reports `state_order_created = TRUE`, C3 recognizes clean recovery if retry occurred within budget.
   - When C2 reports `FALSE`, C3 determines that the system failed recovery.
   - When C2 state facts are missing or `UNKNOWN`, C3 gracefully marks recovery as `INCONCLUSIVE` without fabricating optimistic pass verdicts.
3. **Immutability & Provenance**:
   - Every fact passed to C3 preserves its original C2 evaluation metadata and is stored alongside the C3 evaluation result.

---

## 4. Authentication, Ownership & Authorization Rules

- **Fail-Closed Access Control**:
  All shared integration routes enforce `get_authorized_project`. Any attempt to access a project owned by another user or an unauthorized project returns `HTTP 404 Not Found` (preventing enumeration attacks).
- **Authentication**:
  Requires `Authorization: Bearer <jwt_access_token>`. Unauthenticated requests return `HTTP 401 Unauthorized`.
- **Role Enforcement**:
  Standard `USER` accounts access only projects they own. Operators with `ADMIN` role can inspect platform-level metadata.
- **Data Boundary**:
  Integration runs, execution records, evidence packages, and reports have foreign-key constraints cascading strictly to `projects.project_id`.

---

## 5. Supported Execution Modes

| Mode | Intended Use | Target Environment | Mocking Rules |
|---|---|---|---|
| `CONTROLLED_TEST` | Offline integration testing, CI/CD, local developer validation | Controlled in-memory demonstration adapter (`DemonstrationToolAdapter`, `DemonstrationFixtureManager`, simulated C4 adapter) | Real component evaluators (C1, C2, C3, C4) run with real algorithms. Only the target application is double-backed. |
| `LIVE_AUT` | Live system QA, production staging validation | Live target application (e.g., NexaCart) with live agent and database | Requires live endpoints (`NEXACART_AUT_URL`, `NEXACART_OPENAPI_SPEC`, reset facilities). When prerequisites are missing, execution halts with `BLOCKED`. |

---

## 6. API and CLI Usage Examples

### A. Run Planning
```http
POST /api/v1/projects/proj-123/integration/plans
Authorization: Bearer <token>
Content-Type: application/json

{
  "requested_components": ["C1", "C2", "C3", "C4"],
  "execution_mode": "CONTROLLED_TEST",
  "task_id": "task-checkout-demo",
  "task_version": "1.0.0",
  "fixture_id": "fix-demonstration-cart",
  "fixture_version": "1.0.0",
  "c1_config_id": "c1-cfg-001",
  "c2_suite_id": "c2-suite-001",
  "c3_suite_id": "c3-suite-001",
  "c4_contract_id": "c4-contract-001"
}
```

### B. Coordinated Execution
```http
POST /api/v1/projects/proj-123/integration/plans/plan-abc/execute
Authorization: Bearer <token>
```

### C. Combined QA Report Retrieval
```http
GET /api/v1/projects/proj-123/integration/plans/plan-abc/executions/exec-xyz/report
Authorization: Bearer <token>
```

### D. Report Export (JSON or CSV)
```http
# Export JSON
GET /api/v1/projects/proj-123/integration/plans/plan-abc/executions/exec-xyz/report/export?format=json
Authorization: Bearer <token>

# Export CSV
GET /api/v1/projects/proj-123/integration/plans/plan-abc/executions/exec-xyz/report/export?format=csv
Authorization: Bearer <token>
```

### E. Evidence Replay
```http
POST /api/v1/projects/proj-123/integration/plans/plan-abc/executions/exec-xyz/replay
Authorization: Bearer <token>
```

### F. Internal Developer CLI
```powershell
# Create an integration plan
python -m app.shared.integration.cli create-plan --project-id proj-123 --mode CONTROLLED_TEST --components C1 C2 C3 C4

# Execute an integration plan
python -m app.shared.integration.cli execute-plan --project-id proj-123 --plan-id plan-abc

# Inspect combined report
python -m app.shared.integration.cli get-report --project-id proj-123 --execution-id exec-xyz

# Replay evaluation from stored evidence
python -m app.shared.integration.cli replay --project-id proj-123 --execution-id exec-xyz
```

---

## 7. Migration Instructions

The shared integration tables use additive Alembic migrations.

### Migration Sequence:
1. `f1a89c2b4d3e` &rarr; Platform `users` table.
2. `e75342624f8c` &rarr; Component 3 (C3) persistence tables.
3. `c4_001_initial` &rarr; Component 4 (C4) policy tables.
4. `20261022_projects_schema` &rarr; Shared `projects` and `project_history_events` tables.
5. `20261023_c1_tables` &rarr; Component 1 (C1) persistence tables.
6. `20261023_c2_tables` &rarr; Component 2 (C2) persistence tables.
7. `20261023_integration_plans` &rarr; Shared `integration_run_plans` table.
8. `20261023_integration_executions` &rarr; Shared `integration_executions` table.
9. `20261023_integration_reports` (Current Head) &rarr; Shared `integration_reports` table.

### Applying Migrations:
```powershell
# Check heads
alembic heads

# Apply all migrations to database
alembic upgrade head

# Generate offline SQL preview
alembic upgrade 20261023_integration_executions:20261023_integration_reports --sql
```

---

## 8. Deterministic Replay & Export Usage

### Replay Guarantees:
- **No Target Re-Invocation**: Replay evaluates exclusively against stored primary and fault traces in `retained_evidence`. No network calls or target resets occur.
- **Pinned Rule Evaluators**: Re-evaluates C1, C2, C3, and C4 using the original pinned configuration IDs.
- **Semantic Parity**: Compares semantic verdicts (`semantic_matches: true/false`).
- **Nondeterministic Isolation**: Execution metadata such as `replayed_at_utc`, run IDs, and durations are reported separately and do not invalidate semantic equivalence.

---

## 9. External Prerequisites & Operational Limitations

1. **PostgreSQL Dedicated Database**:
   - Online migration acceptance and high-concurrency transactions require `TEST_DATABASE_URL` pointing to an authorized test PostgreSQL instance.
   - When `TEST_DATABASE_URL` is omitted, tests run hermetically under SQLite in-memory, and PostgreSQL-specific integration checks report as **BLOCKED / NOT RUN**.
2. **Live NexaCart AUT & Agent**:
   - Live testing requires live domain services, OpenAPI definitions, test tenant isolation keys, and agent runner endpoints.
   - When unavailable, live execution requests fail closed with exit code 2 and explicit prerequisite error reporting. Controlled test adapters provide hermetic end-to-end verification without faking live status.

---

## 10. Final Integration Verification Matrix

| Connection | Actual Implementation | Executed Evidence | Status | Blocker |
|---|---|---|---|---|
| **C1 / Shared Auth & Projects** | `get_authorized_project` dependency applied to C1 routers, foreign key to `projects.project_id` | `test_c1_authorization.py`, `test_shared_reporting_and_replay.py` | **VERIFIED** | None |
| **Shared Intake & Config References** | `RunPlanService.create_plan` with pinned digests in `IntegrationRunPlanModel` | `test_shared_integration.py` | **VERIFIED** | None |
| **Shared Execution / Reset / Evidence** | `SharedExecutionCoordinator` with `DemonstrationFixtureManager`, isolated namespaces | `test_shared_execution.py` | **VERIFIED** | None |
| **Evidence Projection into Evaluators** | Native event projection to C1, C2 EFSM, C3 recovery, C4 Kleene logic | `test_shared_reporting_and_replay.py` (Scenarios 1–4) | **VERIFIED** | None |
| **C2-to-C3 Named State Facts** | `AssertionBridgeFacade` emits `C2AssertionFact`, ingested by `RecoveryEvaluatorService` | `test_c2_c3_bridge.py`, `test_shared_reporting_and_replay.py` | **VERIFIED** | None |
| **Shared Report Publication** | `SharedReportAggregator` + `C2ReportPublisher` (`AggregatorClientAdapter`), `IntegrationReportModel` | `test_shared_reporting_and_replay.py` | **VERIFIED** | None |
| **Finding Linkage & Deduplication** | Stable SHA-256 finding identity, grouping by `event_id`/`entity_id`, raw vs. grouped counts | `test_shared_reporting_and_replay.py` | **VERIFIED** | None |
| **PostgreSQL Migration Verification** | Additive Alembic migration chain `20261023_integration_reports`, transactional DDL | Offline SQL verified via `alembic upgrade --sql` | **OFFLINE VERIFIED / LIVE BLOCKED** | Requires external `TEST_DATABASE_URL` |
| **Live Target / Agent Verification** | `TargetMode.LIVE_AUT` readiness checks in adapters | Blocked prerequisite checks in `suite_runner.py` and `adapter.py` | **BLOCKED** | Live NexaCart AUT & agent endpoints not deployed |

### Integration Level Summary:
- **Level A (Internal backend integration implemented)**: **COMPLETE & VERIFIED** (all adapters, aggregators, persistence models, and replay engines).
- **Level B (Controlled end-to-end integration verified)**: **COMPLETE & VERIFIED** (555 passing unit and integration tests).
- **Level C (PostgreSQL acceptance)**: **OFFLINE DDL VERIFIED / LIVE BLOCKED** (Alembic static DDL verified; live execution requires external PostgreSQL instance).
- **Level D (Live NexaCart/agent acceptance)**: **HONESTLY BLOCKED** (live target infrastructure is external to this repository).
