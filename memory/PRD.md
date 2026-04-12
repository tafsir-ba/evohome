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
- [x] Unified Document Architecture (AgentDocuments.js, AgentDocumentUpload.js, AgentDocumentDetail.js)
- [x] Unified Sync Layer (buyer_portal_service.py)
- [x] DigitalOcean Spaces file storage migration
- [x] HEIC / macOS octet-stream upload validation
- [x] Vault preview CORS fix (window.open)
- [x] Vault buyer parity (client_ids fallback)
- [x] Editing "Rejected" documents (reverts to Draft)
- [x] Buyer Auth Token Bug fix (localStorage)
- [x] PdfUploadZone prop fixes
- [x] Debug Console modularized
- [x] Unit bugs fixed: DELETE path corrected to `/api/units/{unit_id}`, field names aligned to `assigned_client_id`/`assigned_client_name`

## Remaining
- P0: Deploy and verify unified architecture on production
- P1: Control Tower Dashboard restructuring
- P1: Decisions Module completion
- P1: Image previews in feed (not just file links)
- P2: Agent-side sync pipeline (agent mutations auto-propagate to buyer)
- P2: Hook dependency warnings (74+ instances)
- P3: Email digests, reporting/export
- P3: Dead code cleanup in api.js
- P3: Strip legacy /agent/quotes and /agent/invoices route aliases

---
Last Updated: April 12, 2026
