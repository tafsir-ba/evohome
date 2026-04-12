# Evohome CMP — Product Requirements Document

## Architecture
- **Backend**: FastAPI + Motor (MongoDB async)
- **Frontend**: React 18 + TailwindCSS + Shadcn/UI
- **Database**: MongoDB Atlas (`evohome_cmp`)
- **File Storage**: DigitalOcean Spaces (`evohome-assets.fra1`)
- **Debug Console**: `/api/internal/debug` (DEBUG_SECRET auth)

## Unified Document System (April 12, 2026)
Quotes and Invoices merged into a single document system:
- **One list page**: `AgentDocuments.js` with category filter (Quote/Invoice)
- **One upload/edit page**: `AgentDocumentUpload.js` with type selector
- **One detail page**: `AgentDocumentDetail.js` — renders quote or invoice actions based on `doc.type`
- **One sidebar entry**: "Quotes / Invoices" → `/agent/documents`
- **Change requests**: unified under document detail, accessed via notification bell
- **7 old files deleted**: AgentQuotes, AgentInvoices, AgentQuoteDetail, AgentInvoiceDetail, AgentQuoteUpload, AgentInvoiceUpload, AgentQuoteEdit

## Sync Layer (Buyer Portal)
Single communication layer between agent and buyer:
- **Read**: `GET /api/buyer/portal` — returns everything (project, branding, documents, vault, CRs, decisions, team, timeline, unread count)
- **Write**: `POST /api/buyer/portal/action` — all buyer mutations (approve, reject, request_change, confirm_payment, respond_decision, mark_seen)
- **After every mutation**: returns fresh portal state — frontend auto-updates all views
- **No bypass**: buyer frontend only calls portal endpoints + 3 binary file downloads

## Units API Contract
- `POST /api/projects/{project_id}/units` — Create unit
- `GET /api/projects/{project_id}/units` — List units (enriched with `assigned_client_name`)
- `GET /api/units/{unit_id}` — Get single unit
- `PUT /api/units/{unit_id}` — Update unit
- `DELETE /api/units/{unit_id}` — Delete unit (NOT nested under /projects/)

## List Endpoints Query Param Audit (April 12, 2026)
All GET list endpoints verified: every `?param=` the frontend sends is declared on the route handler.
- `GET /api/clients?project_id=X` — NOW WORKS (was silently ignored). Calls `list_clients_by_project()` with `can_access_project` check.
- `GET /api/activities?limit=&offset=&client_id=&project_id=` — All params declared, with ownership checks
- `GET /api/analytics?period=` — Declared
- `GET /api/decisions?project_id=&status=&limit=&offset=` — All declared with `Query()`
- `GET /api/workflows/selectors?selector_type=&project_id=` — Declared
- `GET /api/team/directory?search=&limit=` — Declared
- `GET /api/vault/documents?project_id=` — Declared
- `GET /api/documents` — No query params sent from list page (client-side filtering). Backend has `doc_type`/`status` available if needed.

## File Storage (DigitalOcean Spaces)
- All uploads persist in `evohome-assets.fra1.digitaloceanspaces.com/uploads/`
- HEIC/HEIF supported, validation by MIME OR extension
- Direct Spaces URLs in frontend (no CORS redirect)

## Production
- URL: app.evo-home.ch
- Agent: tafsir@evo-home.ch / evoagent123
- Buyer: batafsir3@gmail.com (Google OAuth)
- Debug: app.evo-home.ch/api/internal/debug (DEBUG_SECRET auth)

## Completed (as of April 12, 2026)
- [x] Production database wiped (preserving tafsir@evo-home.ch only)
- [x] Unified Document Architecture
- [x] Unified Sync Layer (buyer_portal_service.py)
- [x] DigitalOcean Spaces file storage migration
- [x] HEIC / macOS octet-stream upload validation
- [x] Vault preview CORS fix, buyer parity
- [x] Buyer Auth Token Bug fix (localStorage)
- [x] PdfUploadZone prop fixes
- [x] Unit bugs: DELETE path + field name alignment
- [x] Test file fix: `test_foundation_features.py` cleanup path
- [x] **Clients list `?project_id=` filtering** — backend now declares, validates ownership, and delegates to `list_clients_by_project()`
- [x] **Auth header fix** on `AgentClients.js` fetch call

## Remaining
- P0: Deploy and verify unified architecture on production
- P1: Control Tower Dashboard restructuring
- P1: Decisions Module completion
- P1: Image previews in feed
- P2: Agent-side sync pipeline
- P2: Hook dependency warnings (74+)
- P3: Email digests, reporting/export
- P3: Dead code cleanup in api.js
- P3: Strip legacy route aliases

---
Last Updated: April 12, 2026
