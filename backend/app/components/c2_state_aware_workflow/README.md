# Component 2: State-Aware Multi-Step Workflow Testing

## 1. Research Overview & Scope

Component 2 (C2) evaluates tool-using Large Language Model (LLM) application workflows against validated and versioned **Finite State Machine (FSM)** and **Extended Finite State Machine (EFSM)** reference models.

Unlike individual tool-call evaluators (Component 1), operational fault injection (Component 3), or security/safety policies (Component 4), Component 2 specifically targets multi-step workflow conformance:
- Precondition & guard verification on each state transition
- Three-valued Kleene logic predicate evaluation distinguishing missing observations from explicit nulls
- Entity continuity across multi-step transactions (e.g. tracking customer 42 and order 503 from selection to refund and verification)
- Workflow safety invariants (e.g. unpaid orders must never be marked refunded)
- Expected state effects and post-conditions
- Protected state integrity on negative/rejection paths
- Earliest first-divergence localization and workflow coverage metrics

---

## 2. Component Architecture

```
app/components/c2_state_aware_workflow/
├── contracts/               # Typed, versioned Pydantic contracts (schema 2026.1)
│   ├── workflow_input.py    # Structured task, business rules, tools, state mappings, fixtures
│   ├── efsm_model.py        # States, transitions, guards, updates, invariants, milestones, protected fields
│   ├── test_definition.py   # Test definition, category, mutation provenance, readiness, agent/QA exports
│   ├── runtime_evidence.py  # Ordered events, tool correlation, before/after states, completeness
│   └── evaluation_result.py # The six exact runtime verdicts, divergence details, coverage summary
├── predicates/              # Declarative predicate engine (Kleene 3-valued logic, no eval/exec)
│   ├── tristate.py          # TriState (TRUE, FALSE, UNKNOWN), MissingType sentinel, logical operators
│   ├── expressions.py       # ComparisonPredicate, PresencePredicate, LogicalPredicate, VariableUpdate
│   └── evaluator.py         # EvaluationContext with explicit scopes (event, vars, fixture, before, after)
├── persistence/             # Versioned storage, canonical hashing, and approval lifecycle
│   ├── hashing.py           # Deterministic canonical SHA-256 content hashing
│   ├── models.py            # SQLAlchemy models: c2_workflow_models, c2_validation_reports, c2_test_suites, c2_test_cases
│   └── repository.py        # Project/version isolation, immutable approved versions, transactional approval, suite persistence
├── builder/                 # Candidate EFSM construction
│   ├── base.py              # ModelAssistedProvider abstract interface (offline/credential-free)
│   └── deterministic.py     # Deterministic candidate builder with input sufficiency diagnostics
├── validator/               # Formal reference model validation
│   ├── structural.py        # Static graph integrity: duplicate IDs, dangling transitions, reachability, dead ends
│   ├── semantic.py          # Bounded semantic checks: guard feasibility, reachability, conflicting updates, invariants
│   └── service.py           # ModelValidationService orchestrating reports and lifecycle progression
├── generator/               # Day 2 Part A: Coverage-guided generation & mutations
│   ├── engine.py            # Bounded BFS traversal, Kleene guard solving, input binding, path deduplication
│   ├── mutations.py         # 8 systematic workflow mutation operators with valid-alternative filtering
│   ├── readiness.py         # Generation readiness validation (MODEL NOT READY vs TEST NOT READY)
│   └── service.py           # TestGenerationService orchestrating generation, mutation, readiness, and persistence
├── api/                     # Project-scoped REST API
│   └── router.py            # FastAPI endpoints under prefix /api/v1/c2
├── integrations/            # Integration interfaces and synthetic stubs
│   └── interfaces.py        # Intake, FixtureReset, AgentExecution, StateObservation, UnifiedReport stubs
├── examples/                # Synthetic domain implementations
│   └── refund_workflow.py   # Complete NexaCart "Refund latest paid order" & unpaid order rejection examples
└── README.md                # Component documentation
```

---

## 3. The Six Runtime Verdicts

C2 strictly adheres to the six runtime verdicts defined in the research proposal:
1. `PASS`: Every observed transition, guard, invariant, entity continuity condition, and state effect was verified across a permitted model path to an accepting state.
2. `EXPECTED REJECTION PASS`: The agent correctly rejected an invalid or ineligible request without modifying protected application state.
3. `FAIL`: A specific transition, guard, invariant, entity continuity check, state effect, or terminal outcome failed. Includes first-divergence localization.
4. `INCONCLUSIVE`: Essential observation evidence was missing or incomplete, preventing definitive conformance evaluation.
5. `MODEL NOT READY`: The reference EFSM model has structural errors, contradictory guards, or unapproved status.
6. `TEST NOT READY`: The generated test definition is ambiguous, infeasible, or has unresolvable fixture references.

---

## 4. Safe Declarative Predicates & Three-Valued Logic

### Kleene 3-Valued Logic
- `FALSE AND UNKNOWN = FALSE`
- `TRUE AND UNKNOWN = UNKNOWN`
- `TRUE OR UNKNOWN = TRUE`
- `NOT UNKNOWN = UNKNOWN`

Explicit comparisons are enforced via the `TriState` type (`TriState.TRUE`, `TriState.FALSE`, `TriState.UNKNOWN`). Direct Python boolean coercion (`bool(tristate)`) raises `TypeError` to prevent subtle truthiness bugs.

### Scopes & Missing Observations
Five explicit scopes are supported:
- `event`: Event data (e.g. `event.arguments.order_id`)
- `vars`: Bound variables (e.g. `vars.selected_order_id`)
- `fixture`: Fixture context (e.g. `fixture.customer_id`)
- `before`: State snapshot observed before the tool call
- `after`: State snapshot observed after the tool call

**Explicit Null vs. Missing Observation:**
- If a key exists with `None`, `PresenceOperator.IS_NULL` evaluates to `TriState.TRUE`.
- If a key or path is absent from the snapshot, resolving yields `MISSING`. Comparison against missing fields evaluates to `TriState.UNKNOWN`.

---

## 5. Model Lifecycle & Immutability

The lifecycle strictly progresses as:
```
DRAFT -> VALIDATED -> APPROVED
```
- **DRAFT**: Initial state of any newly created or modified model.
- **VALIDATED**: Automatically promoted when a model passes all structural and bounded semantic checks with 0 errors.
- **APPROVED**: Explicitly approved by domain reviewer.
  - Requires: valid report, exact canonical content hash match, reviewer identity, review basis, and review notes.
  - Development reviews are labelled as `[SELF_REPORTED_DEVELOPMENT]`.
  - Once `APPROVED`, the model definition is **immutable**. Any modification requires invoking `POST .../new-draft` to spawn a new version (e.g., `1.1.0`), leaving the approved baseline intact.

---

## 6. Test Generation & Systematic Workflow Mutations (Day 2 Part A)

### 6.1 Coverage-Guided Path Generation
The generator (`CoverageGuidedGenerator`) performs a deterministic, bounded BFS traversal over an approved, ready EFSM reference model:
- Explores accepting paths (`NORMAL`), permitted branching workflows (`ALTERNATIVE`), and negative rejection flows (`EXPECTED_REJECTION`).
- Dynamically resolves transition guards and variable bindings using the Kleene 3-valued logic predicate engine.
- Binds inputs and fixture context from declared finite domains and supported synthetic fixture providers.
- Deduplicates generated paths by structural transition sequence and variable bindings.
- Tracks planned coverage targets (planned transition and guard coverage) separately from observed runtime execution coverage.

### 6.2 Eight Systematic Workflow Mutation Operators
Synthetic evaluator mutants are produced from valid generated parent cases to systematically benchmark divergence detection:
1. `skipped_step`: Deletes a non-optional intermediate transition.
2. `reordered_step`: Swaps adjacent dependent transitions.
3. `repeated_step`: Duplicates a non-repeatable, non-idempotent action.
4. `illegal_transition`: Injects a transition not permitted from the current state.
5. `wrong_entity`: Mutates an entity identifier argument (e.g., swapping customer or order ID).
6. `missing_effect`: Omission of an expected application state modification post-transition.
7. `unexpected_protected_state_change`: Injects unauthorized modification to protected fields on rejection paths.
8. `premature_termination`: Terminates execution prior to reaching an accepting final state.

**Soundness Guarantee:**
- A mutant that inadvertently matches a valid alternative model path is automatically detected and rejected (`discarded_non_discriminating_mutants`).
- Every mutant records full provenance: `parent_test_id`, `mutation_type`, `mutation_location_step`, `targeted_rule`, `changed_details`, and `intended_violation`.
- Evaluator mutants are clearly labeled as synthetic test cases, not observed live LLM failures.

### 6.3 Readiness & Feasibility Validation
`GenerationReadinessValidator` executes pre-flight checks:
- **Model Readiness**: Rejects unapproved, modified, or hash-mismatched models (`MODEL NOT READY`).
- **Test Definition Feasibility**: Flags ambiguous variable references, unresolved fixture values, or broken parent paths (`TEST NOT READY`).
- Retains non-ready cases and diagnostic reasons for auditability without failing suite generation.

### 6.4 Strict Oracle Isolation
To avoid data contamination during evaluation:
- **Agent Task Payload Export (`/export/agent`)**: Strictly allowlists task description, permitted context, and fixture reference. Excludes private reference paths, assertions, expected outcomes, and mutation metadata.
- **QA Suite Export (`/export/qa`)**: Full unredacted test suite containing reference transition paths, expected outcomes, invariants, and mutation provenance for evaluation engines and test runners.

---

## 7. REST API Endpoints

Mounted under `/api/v1/c2`:

### Model Lifecycle Endpoints
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/c2/projects/{project_id}/models/build` | Propose and build candidate model from workflow input |
| `POST` | `/api/v1/c2/projects/{project_id}/models` | Directly create draft model definition |
| `GET` | `/api/v1/c2/projects/{project_id}/models` | List all models for a project |
| `GET` | `/api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}` | Retrieve specific model version |
| `POST` | `/api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/validate` | Run validation and store validation report |
| `GET` | `/api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/validation-reports` | List validation reports for model |
| `POST` | `/api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/approve` | Record review decision and approve model |
| `POST` | `/api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/new-draft` | Create new draft version from existing model |
| `GET` | `/api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/readiness` | Check model readiness (`READY` vs `MODEL NOT READY`) |

### Test Generation & Suite Endpoints (Day 2 Part A)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/c2/projects/{project_id}/suites/generate` | Generate coverage-guided test suite with mutations |
| `GET` | `/api/v1/c2/projects/{project_id}/suites` | List all generated test suites for a project |
| `GET` | `/api/v1/c2/projects/{project_id}/suites/{suite_id}` | Retrieve generated test suite metadata and diagnostics |
| `GET` | `/api/v1/c2/projects/{project_id}/suites/{suite_id}/cases` | List test cases (filter by `category` or `readiness`) |
| `GET` | `/api/v1/c2/projects/{project_id}/suites/{suite_id}/cases/{test_id}` | Retrieve individual test case definition |
| `GET` | `/api/v1/c2/projects/{project_id}/suites/{suite_id}/readiness` | Diagnostic readiness report for test suite |
| `GET` | `/api/v1/c2/projects/{project_id}/suites/{suite_id}/export/qa` | Complete QA test suite export with oracle details |
| `GET` | `/api/v1/c2/projects/{project_id}/suites/{suite_id}/export/agent` | Redacted agent task payloads (strict oracle isolation) |
| `GET` | `/api/v1/c2/projects/{project_id}/suites/{suite_id}/cases/{test_id}/agent-payload` | Redacted agent task payload for single test |

---

## 8. Reproducible API Usage Examples

```powershell
# Set Project and Model IDs
$PROJECT_ID = "nexacart_test_proj"
$MODEL_ID = "c2_refund_efsm_nexacart"
$VERSION = "1.0.0"

# 1. Generate a test suite with 8 mutation operators
$GEN_BODY = @{
    suite_name = "NexaCart Refund Suite - Regression Run"
    model_id = $MODEL_ID
    model_version = $VERSION
    generator_version = "2026.1.0"
    random_seed = 42
    max_search_depth = 12
    max_loop_visits = 1
    case_budget = 50
    generate_mutations = $true
    enabled_mutation_types = @(
        "skipped_step", "reordered_step", "repeated_step", "illegal_transition",
        "wrong_entity", "missing_effect", "unexpected_protected_state_change", "premature_termination"
    )
} | ConvertTo-Json -Depth 5

$SUITE = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/v1/c2/projects/$PROJECT_ID/suites/generate" `
    -ContentType "application/json" -Body $GEN_BODY

$SUITE_ID = $SUITE.suite_id
Write-Host "Generated Suite ID: $SUITE_ID (Total Cases: $($SUITE.total_cases))"

# 2. Check Suite Diagnostics & Readiness Breakdown
$DIAG = Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/v1/c2/projects/$PROJECT_ID/suites/$SUITE_ID/readiness"
Write-Host "Readiness Breakdown: $($DIAG.readiness_breakdown | ConvertTo-Json)"

# 3. Export QA Test Suite (Evaluator Oracle)
$QA_EXPORT = Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/v1/c2/projects/$PROJECT_ID/suites/$SUITE_ID/export/qa"
Write-Host "Exported QA cases: $($QA_EXPORT.cases.Count)"

# 4. Export Agent Task Payloads (Oracle Isolated)
$AGENT_EXPORT = Invoke-RestMethod -Method Get -Uri "http://localhost:8000/api/v1/c2/projects/$PROJECT_ID/suites/$SUITE_ID/export/agent"
Write-Host "Exported Agent payloads: $($AGENT_EXPORT.Count)"
# Confirm that private paths are absent:
# $AGENT_EXPORT[0].PSObject.Properties['private_reference_paths'] -eq $null
```

---

## 9. Synthetic Refund Example

Defined in `app/components/c2_state_aware_workflow/examples/refund_workflow.py`:
- Task: *"Refund my latest paid order."*
- Customer 42.
- Orders:
  - 501: Paid older order (`2026-10-10T10:00:00Z`).
  - 502: Unpaid order (`2026-10-12T12:00:00Z`). Ineligible for refund.
  - 503: Paid latest order (`2026-10-15T15:00:00Z`). Target order.
- Verified properties:
  - Latest-order timestamp comparison and ID tie-breaking.
  - Selected order binding to variable `vars.selected_order_id = 503`.
  - Entity continuity across `get_customer_orders` -> `select_order` -> `request_refund` -> `verify_refund_status`.
  - Legitimate alternative path: `ORDER_DETAILS_INSPECTED` (inspecting line items before refund request).
  - Terminal accepting state: `REFUNDED` with state effect `payment_status == 'REFUNDED'`.
  - Separate rejection model & flow: `REJECTED_UNPAID` where protected fields (`order_502_payment_status: 'UNPAID'`, `customer_42_balance: 0.0`) remain unchanged.

---

## 10. Verification Commands

Run from `backend/`:

```powershell
# 1. Run all unit and API tests (62 passing tests)
.\.venv\Scripts\python.exe -m pytest

# 2. Run linter and formatting checks (100% clean across 60 files)
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .

# 3. Verify Alembic migrations (offline SQL generation)
$env:DATABASE_URL="postgresql://test_user:test_pass@localhost:5432/test_db?sslmode=require"
.\.venv\Scripts\python.exe -m alembic upgrade head --sql
.\.venv\Scripts\python.exe -m alembic downgrade c2_001_initial:base --sql
```

---

## 11. Remaining Work for Day 2 Part B & Day 3

- **Day 2 Part B**:
  - Runtime execution runner & live tool/state observer.
  - Trace normalizer converting raw agent tool traces to canonical EFSM event sequences.
  - Trace-to-EFSM alignment algorithm with earliest first-divergence localization.
  - Runtime verdict calculation (`PASS`, `EXPECTED REJECTION PASS`, `FAIL`, `INCONCLUSIVE`, `MODEL NOT READY`, `TEST NOT READY`).
- **Day 3**:
  - Integration with shared intake adapter and multi-component execution runner.
  - Unified QA report aggregator combining C1 tool metrics, C2 workflow conformance, C3 fault resilience, and C4 safety metrics.
  - Research baseline comparisons (B1 Final-state-only, B2 Trace-only, B3 Milestone-based vs B4 C2 State-Aware Alignment).
