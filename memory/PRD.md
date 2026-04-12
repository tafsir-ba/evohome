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
6. **Debug Console UI** — standalone HTML at `/api/internal/debug` with 4 tabs:
   - Live Trace: real-time action trace with filters
   - Errors Only: filtered to failures
   - Entity Inspector: search by type/ID, shows state + traces + notifications
   - Verification Checklist: 36-item bug matrix with pass/fail tracking

### Access
- URL: `{domain}/api/internal/debug`
- Auth: Bearer token = `DEBUG_SECRET` env var
- Not linked from main app. Not accessible to agents or buyers.

### Files Created
- `/app/backend/core/request_id.py`
- `/app/backend/core/errors.py`
- `/app/backend/core/trace.py`
- `/app/backend/routes/debug.py`
- `/app/backend/static/debug.html`

### Files Modified
- `/app/backend/server.py` — middleware integration, error handlers, TTL indexes
- `/app/backend/core/auth.py` — trace user context injection
- `/app/backend/services/file_service.py` — trace request summary
- `/app/backend/routes/documents_v2.py` — trace hero image upload
- `/app/backend/routes/vault_v2.py` — trace vault upload
- `/app/backend/routes/settings.py` — trace logo upload
- `/app/backend/services/change_request_service.py` — trace CR creation + fixed notification param

## Organ Status
| Organ | Status |
|-------|--------|
| 1. Upload/Media | Implemented, preview-verified |
| 2. Client Context | Implemented, preview-verified |
| 3. Change Request | Implemented, preview-verified |
| Debug System | Implemented, preview-verified |

## Test Accounts
- Agent: agent@evohome-test.ch / Evohome2026!
- Buyer: buyer@evohome-test.ch / Evohome2026!

## Remaining
- P0: Deploy to production + verify all items via debug console on app.evo-home.ch
- P1: Organ 4 — Control Tower Dashboard restructuring
- P1: Organ 5 — Decisions rebuild
- P2: Hook dependency warnings
- P3: Email digests, reporting/export

---
Last Updated: April 12, 2026
