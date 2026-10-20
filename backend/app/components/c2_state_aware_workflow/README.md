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

## 2. Component Architecture (Day 1 Implementation)

```
app/components/c2_state_aware_workflow/
├── contracts/               # Typed, versioned Pydantic contracts (schema 2026.1)
│   ├── workflow_input.py    # Structured task, business rules, tools, state mappings, fixtures
│   ├── efsm_model.py        # States, transitions, guards, updates, invariants, milestones, protected fields
│   ├── test_definition.py   # Test definition, category, mutation provenance, readiness
│   ├── runtime_evidence.py  # Ordered events, tool correlation, before/after states, completeness
│   └── evaluation_result.py # The six exact runtime verdicts, divergence details, coverage summary
├── predicates/              # Declarative predicate engine (Kleene 3-valued logic, no eval/exec)
│   ├── tristate.py          # TriState (TRUE, FALSE, UNKNOWN), MissingType sentinel, logical operators
│   ├── expressions.py       # ComparisonPredicate, PresencePredicate, LogicalPredicate, VariableUpdate
│   └── evaluator.py         # EvaluationContext with explicit scopes (event, vars, fixture, before, after)
├── persistence/             # Versioned storage, canonical hashing, and approval lifecycle
│   ├── hashing.py           # Deterministic canonical SHA-256 content hashing
│   ├── models.py            # SQLAlchemy models: c2_workflow_models, c2_validation_reports
│   └── repository.py        # Project/version isolation, immutable approved versions, transactional approval
├── builder/                 # Candidate EFSM construction
│   ├── base.py              # ModelAssistedProvider abstract interface (offline/credential-free)
│   └── deterministic.py     # Deterministic candidate builder with input sufficiency diagnostics
├── validator/               # Formal reference model validation
│   ├── structural.py        # Static graph integrity: duplicate IDs, dangling transitions, reachability, dead ends
│   ├── semantic.py          # Bounded semantic checks: guard feasibility, reachability, conflicting updates, invariants
│   └── service.py           # ModelValidationService orchestrating reports and lifecycle progression
├── api/                     # Project-scoped REST API
│   └── router.py            # FastAPI endpoints under prefix /api/v1/c2
├── integrations/            # Integration interfaces and synthetic stubs
│   └── interfaces.py        # Intake, FixtureReset, AgentExecution, StateObservation, UnifiedReport stubs
├── examples/                # Synthetic domain implementations
│   └── refund_workflow.py   # Complete NexaCart "Refund latest paid order" synthetic example
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

## 6. REST API Endpoints

Mounted under `/api/v1/c2`:

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
| `GET` | `/api/v1/c2/projects/{project_id}/models/{model_id}/versions/{version}/readiness` | Check readiness (`READY` vs `MODEL NOT READY`) |

---

## 7. Synthetic Refund Example

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
  - Rejection path: `REJECTED_UNPAID` where protected fields (`order_502_payment_status: 'UNPAID'`, `customer_42_balance: 0.0`) remain unchanged.

---

## 8. Verification Commands

Run from `backend/`:

```powershell
# 1. Run all unit and API tests
.\.venv\Scripts\python.exe -m pytest

# 2. Run linter and formatting checks
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .

# 3. Verify Alembic offline migration generation
$env:DATABASE_URL="postgresql://test_user:test_pass@localhost:5432/test_db?sslmode=require"
.\.venv\Scripts\python.exe -m alembic upgrade head --sql
.\.venv\Scripts\python.exe -m alembic downgrade c2_001_initial:base --sql
```

---

## 9. Remaining Work for Day 2 & Day 3

- **Day 2**:
  - Automatic test generation from approved EFSM paths (valid, alternative, negative).
  - Workflow mutation generation (skipped step, reordered step, repeated step, illegal transition, wrong entity, missing effect).
  - Trace normalizer and runtime event/state observer.
  - Trace-to-EFSM alignment algorithm with first-divergence localization.
- **Day 3**:
  - Full integration with shared intake, execution runner, and QA report aggregator.
  - Transition, guard, and state-effect coverage calculation.
  - Baseline comparisons (B1 Final-state-only, B2 Trace-only, B3 Milestone-based vs B4 C2).
