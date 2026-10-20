# QA Framework Frontend

Shared frontend application for the Agentic AI-Based Software QA Framework for Testing Tool-Using LLM Applications.

## Architecture & Boundary Principles

1. **Frontend-Only Scope**: The frontend communicates with the shared FastAPI backend exclusively via `/api/v1/auth/*`. No backend files or application registrations are altered.
2. **Session and Role Isolation**:
   - `ADMIN` and `USER` roles are strictly enforced at layout and route levels via `ProtectedRoute`.
   - Unknown or unverified roles fail closed to `AccessDeniedPage`.
   - Monotonically increasing session generation counters discard in-flight asynchronous responses from earlier sessions when switching accounts or logging out.
   - Return URLs are role-filtered and sanitized against open redirect vulnerabilities (protocol-relative URLs or backslashes).
3. **Empty Component Shells**:
   - All four component routes remain empty shells with only breadcrumbs, page title, and empty workspace:
     - `Explainable Tool-Call Correctness Testing` (`/app/tool-call-correctness`)
     - `State-Aware Multi-Step Workflow Testing` (`/app/workflow-testing`)
     - `Robustness and Failure Recovery Testing` (`/app/robustness-recovery`)
     - `Policy-Aware Safety and Prompt-Injection Testing` (`/app/safety-prompt-injection`)
   - Main component pages contain no placeholder text or icons.
   - Zero component API requests, SDKs, or background executions occur.
4. **Model Selection Preferences**:
   - Stored in browser storage, scoped strictly per user (`qa_model_pref_${userId}`).
   - Accounts do not inherit other accounts' configurations.
   - Resilient against corrupted or malformed localStorage entries.
   - Collects no credentials, API keys, or provider secrets.
   - Triggers no provider discovery, connectivity checks, or inference requests.

---

## Development Setup

### Prerequisites
- Node.js >= 20.x
- Backend running on `http://127.0.0.1:8000` (Vite dev proxy forwards `/api` automatically).

### Scripts
```bash
# Run local development server
npm run dev

# Run Oxlint linter (0 errors, 0 warnings)
npm run lint

# Run unit tests (auth, session safeguards, isolation, empty shells)
npm test

# Create production bundle
npm run build
```

---

## Production Hosting & SPA Route Fallback Requirement

This application is built as a single-page application (SPA) using React Router (HTML5 History API / pushState routing).

### Production Server Configuration Requirement
Direct navigation to routes (e.g., `/app/dashboard`, `/admin/users`, `/app/tool-call-correctness`) or browser refreshes will return HTTP 404 from static file servers unless the web server is configured to fall back to `/index.html` for client-side routing.

#### Nginx
```nginx
location / {
    try_files $uri $uri/ /index.html;
}
```

#### Apache (`.htaccess`)
```apache
<IfModule mod_rewrite.c>
  RewriteEngine On
  RewriteBase /
  RewriteRule ^index\.html$ - [L]
  RewriteCond %{REQUEST_FILENAME} !-f
  RewriteCond %{REQUEST_FILENAME} !-d
  RewriteRule . /index.html [L]
</IfModule>
```

#### Caddy
```caddy
example.com {
    root * /path/to/dist
    encode gzip
    try_files {path} /index.html
    file_server
}
```

---

## Testing & Quality Guarantees

- **Linter**: `oxlint` (runs across all files with 0 warnings, 0 errors).
- **JavaScript & JSX**: Modular ES2023 JavaScript and React 19 JSX without TypeScript dependencies.
- **Node Test Runner**: 16 focused unit tests covering:
  - Unicode code point password counting (matching backend Python behavior for supplementary Unicode characters).
  - Return URL sanitization and role-aware navigation boundaries.
  - Stale asynchronous response invalidation via generation counters.
  - Model preference storage resilience and cross-user isolation.
  - Component shell purity (no placeholders, no component APIs).
