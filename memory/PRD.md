# Evohome CMP — Product Requirements Document

## Architecture
- **Backend**: FastAPI + Motor (MongoDB async) — canonical SSOT services, thin routes
- **Frontend**: React 18 + TailwindCSS + Shadcn/UI
- **Database**: MongoDB Atlas (`evohome_cmp`)
- **Debug Console**: Standalone at /api/internal/debug (DEBUG_SECRET auth)

## Production Debug & Verification System

### Components Built
1. **Request ID Middleware** — `req_xxxxxxxxxxxx` on every request, `X-Request-ID` response header
2. **Canonical Error Normalizer** — all errors return `{error, message, request_id, source, details}`
3. **Auto-Tracing Middleware** — all POST/PUT/PATCH/DELETE + critical GETs automatically traced
4. **Trace Events Collection** — 30-day TTL, service_chain, db_mutations, side_effects
5. **Debug API** — `/api/internal/debug/*` with DEBUG_SECRET bearer auth
6. **Debug Console UI** — modular HTML/JS/CSS at `/api/internal/debug` with 4 tabs:
   - Live Trace: real-time action trace with filters (outcome, method, action search, auto-refresh)
   - Errors Only: filtered to failures
   - Entity Inspector: search by type/ID, shows state + traces + notifications + state transitions
   - Verification Checklist: 36-item bug matrix with pass/fail tracking + notes

### Auto-Extraction Features (Verified)
- **Entity extraction**: URL patterns auto-populate `entity_type` and `entity_id` for documents, vault_documents, change_requests, decisions, clients, projects
- **Action derivation**: Method + URL automatically maps to human-readable action names (e.g., `document_create`, `cr_respond`, `vault_upload`)
- **Response summary**: State transitions tracked (e.g., `{status: "Draft", type: "quote"}`)
- **DB mutations**: Tracked per-request (collection, operation, entity_id)
- **Side effects**: Notifications and emails logged in trace context

### Modular Debug Console Architecture
```
/app/backend/static/debug/
├── index.html              # Shell — loads all modules
├── css/styles.css          # All styles (dark theme, tables, badges)
├── js/api.js               # API layer (fetch, auth, secret management)
├── js/traces.js            # Live Trace + Errors tab (filters, table rendering)
├── js/entity-inspector.js  # Entity Inspector tab (state, transitions, traces)
└── js/verifications.js     # Verification Checklist tab (36-item matrix)
```

### Access
- URL: `{domain}/api/internal/debug`
- Auth: Bearer token = `DEBUG_SECRET` env var
- Not linked from main app. Not accessible to agents or buyers.

### Files Created/Modified
- `/app/backend/core/request_id.py`
- `/app/backend/core/errors.py`
- `/app/backend/core/trace.py` (auto-extraction, side_effects, response_summary)
- `/app/backend/routes/debug.py` (serves modular static assets: HTML, JS, CSS)
- `/app/backend/static/debug/*` (6 modular files)
- `/app/backend/server.py` — middleware integration, error handlers, TTL indexes

## Organ Status
| Organ | Status |
|-------|--------|
| 1. Upload/Media | Implemented, preview-verified |
| 2. Client Context | Implemented, preview-verified |
| 3. Change Request | Implemented, preview-verified |
| Debug System | Implemented, modularized, verified |

## Test Accounts
- Agent: agent@evohome-test.ch / Evohome2026!
- Buyer: buyer@evohome-test.ch / Evohome2026!

## Remaining
- P1: Fix Control Tower Dashboard CR Cards (Issue 3)
- P1: Client Context formatting UI verification (Issue 4)
- P1: Organ 4 — Control Tower Dashboard restructuring
- P1: Organ 5 — Decisions rebuild
- P2: Execute 36-item Verification Checklist via Debug Console
- P2: Hook dependency warnings (74+ instances)
- P3: Email digests, reporting/export
- P3: Dead code cleanup (parseApiError in api.js)

---
Last Updated: April 12, 2026
