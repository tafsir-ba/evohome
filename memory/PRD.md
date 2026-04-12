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
6. **Debug Console UI** — modular HTML/JS/CSS at `/api/internal/debug` with 4 tabs

### Auto-Extraction (Verified E2E)
- Entity extraction from URL patterns (document, vault_document, change_request, decision, client, project)
- Action derivation from method+path (document_create, cr_respond, vault_upload, etc.)
- Response summary with state transitions (e.g., {status: "Change Requested", previous_status: "Sent"})
- DB mutations per-request (collection, operation, entity_id)
- Side effects (notifications, emails) logged in trace context
- Related entities (CR → parent document linkage)

### Trace Coverage (All Mutating Paths)
- document_create, document_send, document_reupload, document_revert_draft
- document_action: approve, reject, request_change, confirm_payment, convert_to_invoice
- change_request: create, respond, resolve, close
- vault: upload, download
- settings: logo upload/delete, hero image upload/delete
- auth: login, register, logout

### Modular Debug Console
```
/app/backend/static/debug/
├── index.html              # Shell
├── css/styles.css          # Dark theme styles
├── js/api.js               # Fetch + auth layer
├── js/traces.js            # Live Trace + Errors tabs
├── js/entity-inspector.js  # Entity Inspector tab
└── js/verifications.js     # 36-item Verification Checklist
```

### Security
- Path traversal protection (realpath containment check)
- XSS escaping on user-input fields
- DEBUG_SECRET bearer auth on all API endpoints

### Testing (Iteration 30)
- Backend: 35/35 tests passed (auth, health, traces, entity inspector, verifications, static assets, path traversal)
- Frontend: All 4 tabs verified via Playwright (auth gate, trace expand, entity inspect, verification update, filters, auto-refresh)

## Organ Status
| Organ | Status |
|-------|--------|
| 1. Upload/Media | Implemented, preview-verified |
| 2. Client Context | Implemented, preview-verified |
| 3. Change Request | Implemented, preview-verified |
| Debug System | Implemented, modularized, tested (35/35 + UI) |

## Test Accounts
- Agent: agent@evohome-test.ch / Evohome2026!
- Buyer: buyer@evohome-test.ch / Evohome2026!

## Remaining
- P1: Fix Control Tower Dashboard CR Cards (move to /agent/home)
- P1: Client Context formatting UI verification (AgentClientDetail.js, ClientPreview.js)
- P1: Organ 4 — Control Tower Dashboard restructuring
- P1: Organ 5 — Decisions rebuild
- P2: Execute 36-item Verification Checklist via Debug Console
- P2: Hook dependency warnings (74+ instances)
- P3: Email digests, reporting/export
- P3: Dead code cleanup (parseApiError in api.js)

### Known Limitations
- Debug console JS modules rely on global scope and implicit load order (not ES modules)
- Orphaned test documents in DB: doc_1057cdb1c89d, doc_4ea1e9124d2b (with CRs, cannot delete)

---
Last Updated: April 12, 2026
