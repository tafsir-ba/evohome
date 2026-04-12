# Evohome CMP — Product Requirements Document

## Architecture
- **Backend**: FastAPI + Motor (MongoDB async) — canonical SSOT services, thin routes
- **Frontend**: React 18 + TailwindCSS + Shadcn/UI
- **Database**: MongoDB Atlas (`evohome_cmp`)
- **Integrations**: OpenAI GPT-4o, Stripe (webhooks verified), Resend, Google OAuth

## Canonical Service Layer

### file_service.py (Organ 1)
- Single upload pipeline. Frozen validation. stored_filename (no absolute paths in DB).
- Legacy backward compat for old pdf_path and hero_image_path fields

### Client Context Formatters (Organ 2)
- `formatClientContext`: "Name — Project — Unit" (full label for cards, detail)
- `formatClientContextCompact`: "Name (Project / Unit)" (selectors)
- `formatContextSubtitle`: "Project / Unit" (below-selector context)
- `formatDocContext`: "Number · Client · Project · Unit" (list rows)
- All defined in `lib/utils.js`. Used across all 14 mandatory files. Zero inline formatting.

### change_request_service.py (Organ 3)
- One collection, embedded messages, buyer_id, state guards
- Resolve → Sent (NEVER Draft). Quote/invoice identical.
- Notifications: create → agent, respond → buyer, resolve → buyer

## Organ Status (Contractual)
| Organ | Backend | Frontend | Preview-Verified | Production-Verified |
|-------|---------|----------|-----------------|-------------------|
| 1. Upload/Media | Canonical | Rebuilt | Yes | No |
| 2. Client Context | Enriched | Canonical formatters used everywhere | Yes | No |
| 3. Change Request | Canonical | Verified via UI screenshots | Partially | No |

## What Has Been UI-Verified (Preview Only)
- Vault page loads correctly with upload, search, filter
- Quotes list shows formatDocContext format
- Clients list shows project/unit badges
- Quote detail shows ChangeRequestPanel with Reply/Resolve
- Buyer portal shows change request thread with buyer + agent messages
- Buyer portal shows invoice + quote with correct type badges and status
- Dashboard home shows aggregate CR count
- Agent reply textarea opens and is functional

## What Has NOT Been UI-Verified
- Actual Reply submission through UI (textarea opened, not submitted)
- Resolve through UI
- Close through UI
- Invoice-specific CR panel through UI
- Notification content when bell is clicked
- Hero image display on buyer timeline
- Logo upload/display through settings page
- Vault download through UI

## Test Accounts
- Agent: agent@evohome-test.ch / Evohome2026! (POST /api/auth/login)
- Buyer: buyer@evohome-test.ch / Evohome2026! (POST /api/auth/buyer/login)

## Remaining Work
- P0: Production deployment + verification on app.evo-home.ch
- P1: Organ 4 — Control Tower Dashboard restructuring
- P1: Organ 5 — Decisions rebuild on unified CR thread
- P2: Hook dependency warnings
- P3: Email digests, reporting/export

---
Last Updated: April 12, 2026
