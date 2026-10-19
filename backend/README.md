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
- **Empty Initial Packages**: The reserved component packages currently contain only empty `__init__.py` markers (0 bytes) with no domain logic, models, or endpoints implemented yet.

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
