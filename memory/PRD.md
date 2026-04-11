# Evohome CMP — Product Requirements Document

## Architecture
- **Backend**: FastAPI + Motor (MongoDB async) — canonical SSOT services, thin routes
- **Frontend**: React 18 + TailwindCSS + Shadcn/UI — decomposed dashboard
- **Database**: MongoDB Atlas (`evohome_cmp`)
- **Integrations**: OpenAI GPT-4o, Stripe (webhooks verified), Resend, Google OAuth

## Canonical Service Layer

### file_service.py (Organ 1)
- Single upload pipeline. Frozen validation rules. No absolute disk paths in DB.
- Storage: `/app/backend/uploads/` with prefixed stored_filenames
- Public images at `/api/uploads/` (no auth). Private files via authenticated download.
- Parent entities persist: url, stored_filename, original_filename, file_size, content_type

### client_service.py (Organ 2)
- Batch-enriches clients with project_name AND unit_reference on all UI-facing endpoints
- Canonical formatters in `lib/utils.js`: formatClientContext, formatClientContextCompact, formatDocContext
- No N/A. Missing parts omitted, never replaced with placeholder text.
- Current rule: client → one unit (operational, not eternal domain law)

### change_request_service.py (Organ 3)
- One change_requests collection. Embedded messages. No second comment system.
- Fields: change_request_id, entity_type, entity_id, agent_id, buyer_id, status, messages
- State: open → under_review → resolved → closed (no reopen; new CR instead)
- Resolve always returns document to Sent (NEVER Draft)
- Quote and invoice behavior identical. No entity-specific logic.
- Notifications: buyer→agent on create, agent→buyer on respond/resolve

### vault_service.py (rebuilt with Organ 1)
- Canonical fields: vault_document_id, title, category, stored_filename, content_type, access_level, client_ids
- Routes: /api/vault/upload, /api/vault/documents, /api/vault/documents/{id}/download

## Features Implemented
- Auth (JWT + Google OAuth), Projects/Units/Clients CRUD
- Documents: Quotes/Invoices with AI extraction, PDF generation, hero images
- Timelines/Workflows, Real-time Feed, Notifications
- Stripe billing (webhook verified), Team management, Vault
- Control Tower dashboard (CR aggregation across entity types)
- FEAT-001: Decisions Module, FEAT-002: Unified Change Requests

## Organ Status
1. **Upload/Media** — provisionally accepted, pending production verification
2. **Client/Project/Unit Context** — provisionally accepted, pending production verification
3. **Change Request Thread** — provisionally accepted, pending production verification
4. **Control Tower Dashboard** — not started (Tier 2)
5. **Decisions** — existing, not rebuilt yet (Tier 3)

## Test Accounts
- Agent: agent@evohome-test.ch / Evohome2026!
- Buyer: buyer@evohome-test.ch / Evohome2026! (login via /api/auth/buyer/login)

## Legacy Backward Compatibility
- Documents with old `pdf_path` field served via absolute path fallback
- Documents with old `hero_image_path` field served via absolute path fallback
- Delete operations clean up both old and new field paths

## Remaining
- P1: Control Tower Dashboard restructuring
- P1: Decisions rebuild on unified CR thread
- P2: Production verification of Organs 1-3 on app.evo-home.ch
- P2: Hook dependency warnings
- P3: Email digests, reporting/export

---
Last Updated: April 11, 2026
