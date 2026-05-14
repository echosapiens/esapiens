# E.sapiens — Security Concerns & Audit Findings

**Audit Date:** 2026-05-13  
**Scope:** Full-stack (FastAPI backend, React frontend, Express reference app)  
**Project Root:** `Esapiens-Sprint-2/`

---

## CRITICAL

### F-01: Live API Keys in `.env` (Plaintext on Disk)

- **File:** `backend/.env`, lines 1–2
- **Content:** Real `OPENROUTER_API_KEY` and `BRAVE_SEARCH_API_KEY` stored in plaintext
- **Risk:** If this directory is ever pushed to git (even accidentally), keys are permanently exposed in git history. Both services bill per-use — an attacker could drain accounts.
- **Fix:**
  1. **Rotate both keys immediately** at their respective dashboards
  2. Never commit `.env` files — `.gitignore` now excludes them
  3. Use `.env.example` with placeholder values for documentation
- **Status:** 🔴 Keys still active — rotation required by user

### F-02: No Root `.gitignore` — Secrets at Risk of Accidental Commit

- **File:** (was missing) project root `.gitignore`
- **Risk:** Without a `.gitignore`, `git init` would track `backend/.env`, SQLite databases, `__pycache__/`, etc.
- **Fix:** Root `.gitignore` created with `.env`, `*.db`, `__pycache__/`, `node_modules/`, `data/`, `esapiens-data/`
- **Status:** ✅ Fixed

### F-03: Unauthenticated Arbitrary Code Execution

- **Files:** `backend/tools.py:560–622` (`execute_python`), `backend/tools.py:549–557` (`create_tool`), `backend/tools.py:437–441` (`run_python_plot`), `backend/tools.py:496–500` (`plotly_plot`)
- **Risk:** The LLM agent can execute arbitrary Python code via `subprocess.run` with `os`, `sys`, `subprocess`, `httpx` available in the preamble. `create_tool` writes persistent Python modules to disk that survive restarts. All reachable from unauthenticated `/chat` and `/chat/stream` endpoints.
- **Fix:** Before production deployment:
  1. Add authentication middleware on all endpoints
  2. Sandbox code execution (Docker container, gVisor, Firecracker) with no network access and read-only filesystem
  3. Apply import allowlists — remove `subprocess`, `os.system`, and filesystem access unless explicitly needed
  4. Audit `create_tool` generated code before writing to disk; do not auto-execute
  5. Implement prompt-injection detection and guardrails
- **Status:** 🔴 Open — architectural change needed before production

---

## HIGH

### F-04: CORS Wildcard with `allow_credentials=True`

- **File:** `backend/app.py:23–29`
- **Risk:** `allow_origins=["*"]` + `allow_credentials=True` allows any origin to make credentialed cross-origin requests in some browser configurations.
- **Fix:** Restricted to `["http://localhost:5173", "http://localhost:4173", "http://localhost:3000"]`. Credentials disabled. Methods limited to `GET`, `POST`, `DELETE`. Production origins configurable via `CORS_ORIGINS` env var.
- **Status:** ✅ Fixed

### F-05: Zero Authentication on All API Endpoints

- **Files:** `backend/streaming.py` (all routes), `backend/app.py`
- **Risk:** Every endpoint is fully public: `/chat`, `/chat/stream`, `/sessions`, `/sessions/{id}`, `DELETE /sessions/{id}`, `/chat/report/{id}`. An unauthenticated user can enumerate sessions, read conversations, trigger LLM API calls (which cost money), and generate PDF reports.
- **Fix:** Add authentication middleware. Use `Depends(get_current_user)` with JWT or API key validation on all routes.
- **Status:** 🔴 Open — authentication middleware needed before production

### F-06: No Rate Limiting

- **Files:** `backend/app.py`, `backend/streaming.py`
- **Risk:** No per-IP or per-user throttling. An attacker can DDoS the service or drain the OpenRouter API key balance with rapid requests.
- **Fix:** Add `slowapi` or Redis-based rate limiter. Apply stricter limits on `/chat` endpoints.
- **Status:** 🔴 Open — rate limiting middleware needed before production

### F-07: SSRF via NCBI Proxy (Reference App Only)

- **File:** `online-generated-ui/server.ts:57–68`
- **Risk:** The `:tool` path parameter is passed directly into the fetch URL without validation. Path traversal within the NCBI domain is possible.
- **Fix:** Whitelist allowed NCBI E-utilities tool names: `esearch`, `esummary`, `efetch`, `elink`, `einfo`.
- **Status:** 🟡 Low priority — `online-generated-ui` is a reference app, not production

### F-08: API Key Embedded in Client-Side JS Bundle (Reference App Only)

- **File:** `online-generated-ui/vite.config.ts:10–12`
- **Content:** `process.env.GEMINI_API_KEY` is injected via Vite's `define`, embedding the key directly into the JavaScript bundle visible in DevTools.
- **Fix:** Route Gemini API calls through the backend server instead of making them client-side.
- **Status:** 🟡 Low priority — `online-generated-ui` is a reference app, not production

---

## MEDIUM

### F-09: `subprocess.run` Code Execution in Plotting Tools

- **Files:** `backend/tools.py:437–441` (`run_python_plot`), `backend/tools.py:496–500` (`plotly_plot`)
- **Risk:** Code is constructed from LLM-generated parameters and executed via `subprocess.run`. While `shell=True` is not used, a compromised LLM could inject harmful code. 30-second timeout helps but doesn't prevent all abuse.
- **Fix:** Same sandboxing as F-03. Consider `RestrictedPython` or container isolation.
- **Status:** 🟡 Open — same as F-03

### F-10: SQLite `check_same_thread=False`

- **Files:** `backend/main.py:35–38`, `backend/agent.py:250`, `backend/storage.py:123`
- **Risk:** SQLite connections are not thread-safe by default. In a multi-threaded ASGI server, concurrent writes can corrupt data.
- **Fix:** Use `aiosqlite` for async operations, connection-per-thread pattern, or migrate to PostgreSQL for production.
- **Status:** 🟡 Open — acceptable for development; needs fix before multi-user deployment

### F-11: Unsandboxed HTML in PlotlyViewer Iframe

- **File:** `frontend/src/components/Visualizations/PlotlyViewer.tsx`
- **Risk:** `<iframe sandbox="allow-scripts" srcDoc={html}>` renders HTML generated from LLM-authored code. While `sandbox` blocks same-origin access, JavaScript execution within the iframe is permitted.
- **Fix:** Strip `<script>` tags and external resource references before rendering. Consider using Plotly's React component directly instead of raw HTML injection.
- **Status:** 🟡 Open — acceptable for local use; tighten before public deployment

### F-12: Predictable Job IDs (Reference App Only)

- **File:** `online-generated-ui/server.ts:15–25`
- **Risk:** `Math.random()` generates predictable IDs. Jobs stored in-memory with no auth check on `/api/jobs/:id`.
- **Fix:** Use `crypto.randomUUID()`, add authentication, implement job TTL/eviction.
- **Status:** 🟡 Low priority — reference app only

### F-13: Debug File Written to `/tmp`

- **File:** `backend/tools.py:501–506`
- **Risk:** Debug info (file paths, stdout, stderr) written to a predictable location. May contain user query fragments.
- **Fix:** Removed the debug file write entirely.
- **Status:** ✅ Fixed

### F-14: `.env` Baked into Docker Image

- **File:** `backend/Dockerfile:19` — `COPY . .`
- **Risk:** If `.env` exists during build, it gets baked into the image layer. Extractable with `docker cp` or layer inspection.
- **Fix:** `.dockerignore` created excluding `.env`, `*.db`, `__pycache__/`, etc.
- **Status:** ✅ Fixed

---

## LOW

### F-15: No HTTPS Enforcement

- **Files:** `docker-compose.yml`, `backend/Dockerfile`
- **Risk:** API keys transmitted in plaintext over HTTP.
- **Fix:** Add a reverse proxy (Caddy/Nginx) with TLS termination before production.
- **Status:** 🔵 Open — acceptable for local development

### F-16: Verbose Error Messages in API Responses

- **Files:** `backend/main.py:118`, `backend/main.py:222`
- **Risk:** Raw exception messages (file paths, stack traces, schema info) leaked to clients.
- **Fix:** Replaced `str(e)` with generic `"An internal error occurred."`. Full details logged server-side via `logging.exception()`.
- **Status:** ✅ Fixed

### F-17: No Input Length Validation on Chat Queries

- **File:** `backend/streaming.py:35`
- **Risk:** No maximum length on `query` field. Extremely long queries could consume the LLM context window and drain API budget.
- **Fix:** Added `max_length=10000` to `query` and `max_length=128` + regex validation `^[a-zA-Z0-9_-]+$` to `session_id`.
- **Status:** ✅ Fixed

---

## INFO

### F-18: Deployment Checklist Not Implemented

- **File:** `DEPLOY.md`
- **Note:** The deployment guide lists security items (restrict CORS, rate limiting, HTTPS, no hardcoded keys) but none were implemented in code at time of audit. Items are being addressed as part of this audit.

### F-19: No Git Repository Initialized

- **Note:** No `.git` directory exists at project root. This means no git history exposure currently, but also means secrets are unprotected if git is initialized later. The new `.gitignore` will protect them.

---

## Remediation Summary

| Finding | Severity | Status |
|---------|----------|--------|
| F-01 — API keys in `.env` | 🔴 CRITICAL | **User must rotate keys** |
| F-02 — No `.gitignore` | 🔴 CRITICAL | ✅ Fixed |
| F-03 — Unauth code execution | 🔴 CRITICAL | 🔴 Open — needs sandbox/auth |
| F-04 — CORS wildcard | 🟠 HIGH | ✅ Fixed |
| F-05 — No authentication | 🟠 HIGH | 🔴 Open — needs auth middleware |
| F-06 — No rate limiting | 🟠 HIGH | 🔴 Open — needs rate limiter |
| F-07 — SSRF (ref app) | 🟠 HIGH | 🟡 Low priority |
| F-08 — Key in client JS (ref app) | 🟠 HIGH | 🟡 Low priority |
| F-09 — subprocess in plots | 🟡 MEDIUM | 🔴 Open — same as F-03 |
| F-10 — SQLite thread safety | 🟡 MEDIUM | 🟡 Open — dev only |
| F-11 — iframe HTML | 🟡 MEDIUM | 🟡 Open — tighten for prod |
| F-12 — Predictable job IDs (ref) | 🟡 MEDIUM | 🟡 Low priority |
| F-13 — Debug file in `/tmp` | 🟡 MEDIUM | ✅ Fixed |
| F-14 — `.env` in Docker | 🟡 MEDIUM | ✅ Fixed |
| F-15 — No HTTPS | 🔵 LOW | 🔵 Open — dev acceptable |
| F-16 — Verbose errors | 🔵 LOW | ✅ Fixed |
| F-17 — No input validation | 🔵 LOW | ✅ Fixed |

**6 fixed, 4 open (architectural), 4 low-priority (reference app), 1 requires user action (key rotation).**