# Evohome CMP — Product Requirements Document

## Architecture
- **Backend**: FastAPI + Motor (MongoDB async) — canonical SSOT services, thin routes
- **Frontend**: React 18 + TailwindCSS + Shadcn/UI — decomposed dashboard
- **Database**: MongoDB Atlas (`evohome_cmp`)
- **Integrations**: OpenAI GPT-4o, Stripe (webhooks verified), Resend, Google OAuth

## Canonical Service Layer

### file_service.py (Organ 1)
- Single upload pipeline. Frozen validation: images 2-5MB, vault 50MB, PDF 20MB
- Storage: `/app/backend/uploads/` with prefixed stored_filenames
- Public images at `/api/uploads/` (no auth). Private files via authenticated download.
- Parent entities persist: url, stored_filename, original_filename, file_size, content_type
- Legacy backward compat for old pdf_path and hero_image_path fields

### Client Context (Organ 2)
- Backend: client_service.py batch-enriches project_name + unit_reference on UI-facing endpoints
- Frontend: Canonical formatters in lib/utils.js (single source of truth):
  - formatClientContext: "Name — Project — Unit" (cards, detail)
  - formatClientContextCompact: "Name (Project / Unit)" (selectors)
  - formatContextSubtitle: "Project / Unit" (below-selector context)
  - formatDocContext: "Number · Client · Project · Unit" (list rows)
- All 14 mandatory files audited. Zero inline formatting. Zero N/A placeholders.

### change_request_service.py (Organ 3)
- One change_requests collection. Embedded messages. No second comment system.
- Fields: change_request_id, entity_type, entity_id, agent_id, buyer_id, status, messages
- State: open → under_review → resolved → closed (forbidden: closed→anything, resolved→under_review)
- Resolve always returns document to Sent (NEVER Draft)
- Quote and invoice behavior identical. Dashboard aggregates across entity types.
- Notifications: buyer→agent on create, agent→buyer on respond/resolve

## Organ Status (Contractual)
| Organ | Status |
|-------|--------|
| 1. Upload/Media | Implemented — Pending Production Verification |
| 2. Client/Project/Unit | Implemented — Pending Production Verification |
| 3. Change Request Thread | Implemented — Pending Production Verification |
| 4. Control Tower Dashboard | Drafted (contract needed) |
| 5. Decisions | Drafted (depends on Organ 3) |

## Test Accounts
- Agent: agent@evohome-test.ch / Evohome2026!
- Buyer: buyer@evohome-test.ch / Evohome2026! (login via /api/auth/buyer/login)

## Test Reports
- iteration_25: Organ 1 upload system (100% pass)
- iteration_26: Organ 2 initial + Organ 3 initial (100% pass)
- iteration_27: Organ 3 backend (15/15 pass)
- iteration_28: Organ 2 corrective + Organ 3 frontend (100% pass)

## Remaining
- P0: Production verification of Organs 1-3 on app.evo-home.ch (requires deployment)
- P1: Control Tower Dashboard restructuring
- P1: Decisions rebuild on unified CR thread
- P2: Hook dependency warnings
- P3: Email digests, reporting/export

---
Last Updated: April 11, 2026
