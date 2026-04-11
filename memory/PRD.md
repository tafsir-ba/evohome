# Evohome CMP — Product Requirements Document

## Architecture
- **Backend**: FastAPI + Motor (MongoDB async) — canonical SSOT services, thin routes
- **Frontend**: React 18 + TailwindCSS + Shadcn/UI — decomposed dashboard
- **Database**: MongoDB Atlas (`evohome_cmp`)
- **Integrations**: OpenAI GPT-4o, Stripe (webhooks verified), Resend, Google OAuth

## Canonical Service Layer
All business logic lives in `/app/backend/services/`. Routes only validate, authorize, and delegate.

### file_service.py (NEW — Organ 1 Rebuild)
- Single source of truth for all file upload, validation, storage, deletion
- Frozen validation rules: images (JPEG/PNG/WebP), vault (PDF/images/Office docs), PDFs
- Max sizes: logo 2MB, hero 5MB, vault 50MB, PDF 20MB
- Storage: `/app/backend/uploads/` with prefixed stored_filenames
- Public images served via StaticFiles at `/api/uploads/` (no auth)
- Private files served via authenticated download endpoints
- Parent entities persist: url, stored_filename, original_filename, file_size, content_type
- NEVER persist absolute disk paths

### vault_service.py (REBUILT)
- Canonical fields: vault_document_id, title, category, stored_filename, original_filename, file_size, content_type, access_level, client_ids
- Categories: contracts, plans, permits, reports, other
- Routes: /api/vault/upload, /api/vault/documents, /api/vault/documents/{id}, /api/vault/documents/{id}/download

### client_service.py (FIXED)
- Batch-enriches clients with project_name AND unit_reference from units collection
- Canonical display format: Client Name — Project Name — Unit Reference

### change_request_service.py
- Unified thread model for quotes, invoices, decisions
- Buyer-visible thread persists after resolution (not gated on changeComment)

## Features Implemented
- Auth (JWT + Google OAuth), Projects/Units/Clients CRUD
- Documents: Quotes/Invoices with AI extraction, PDF generation, hero images
- Timelines/Workflows, Real-time Feed, Notifications
- Stripe billing (webhook verified), Team management, Vault
- **Unified Upload System**: One canonical file service for all uploads
- **Client/Project/Unit Context**: Enriched display across all selectors
- **Change Request Threads**: Buyer sees full conversation history, including after resolution
- FEAT-002: Unified Change Request System (canonical, shared across all entity types)
- FEAT-001: Decisions Module (full lifecycle)
- Control Tower dashboard, decomposed architecture

## Data Model
- `documents`: Quotes/invoices with hero_image_url, hero_image_stored_filename, pdf_stored_filename
- `vault_documents`: stored_filename, original_filename, file_size, content_type, access_level, client_ids
- `users`: company_logo_url, company_logo_stored_filename
- `change_requests`: Canonical threaded conversations with messages array
- `decisions` + `decision_recipients`: Formal approval requests
- `clients`, `projects`, `units`, `activities`, `timelines`, `notifications`, `team_members`

## Test Accounts
- Agent: agent@evohome-test.ch / Evohome2026!
- Buyer: buyer@evohome-test.ch / Evohome2026! (login via /api/auth/buyer/login)

## Completed Organs (Kill-and-Rebuild)
1. **Upload/Media System** — file_service.py, vault rebuilt, hero image rebuilt, logo rebuilt
2. **Client/Project/Unit Context** — unit_reference enrichment from units collection
3. **Change Request Thread** — buyer sees full thread after resolution, no changeComment gate

## Remaining (Tier 2-3)
- P1: Control Tower Dashboard restructuring (remove command bar, recent activity; add urgency)
- P1: Decisions feature (build on top of unified change request thread)
- P2: Hook dependency warnings (74+ instances)
- P3: Email digest notifications
- P3: Reporting and export features

---
Last Updated: April 11, 2026
