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
