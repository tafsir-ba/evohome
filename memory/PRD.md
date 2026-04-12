# Evohome CMP — Product Requirements Document

## Architecture
- **Backend**: FastAPI + Motor (MongoDB async) — canonical SSOT services, thin routes
- **Frontend**: React 18 + TailwindCSS + Shadcn/UI
- **Database**: MongoDB Atlas (`evohome_cmp`)
- **Integrations**: OpenAI GPT-4o, Stripe (webhooks verified), Resend, Google OAuth

## Organ Status
| Organ | Backend | Frontend | Preview-Verified | Production-Verified |
|-------|---------|----------|-----------------|-------------------|
| 1. Upload/Media | Canonical | Rebuilt | Yes (iteration_29) | Pending deployment |
| 2. Client Context | Enriched | Canonical formatters | Yes (iteration_29) | Pending deployment |
| 3. Change Request | Canonical | Verified | Yes (iteration_29) | Pending deployment |

## Test Matrix (36 items)
- 13 verified by user in production (BUG-001,002,009,010,017-023,035,036)
- 23 verified by testing agent in preview (BUG-003-008,011-016,024-034) - iteration_29
- Total: 36/36 items verified in at least one environment

## What Requires Production Verification After Deployment
All 23 items verified in preview need production re-verification on app.evo-home.ch

## Canonical Formatters (lib/utils.js)
- `formatClientContext`: "Name — Project — Unit"
- `formatClientContextCompact`: "Name (Project / Unit)"
- `formatContextSubtitle`: "Project / Unit"
- `formatDocContext`: "Number · Client · Project · Unit"

## Test Accounts
- Agent: agent@evohome-test.ch / Evohome2026! (POST /api/auth/login)
- Buyer: buyer@evohome-test.ch / Evohome2026! (POST /api/auth/buyer/login)

## Seed Data (after April 12 wipe)
- Project: Résidence Les Pins
- Units: Lot 3.01-4.02 (4 units)
- Client: Test Buyer → Lot 3.01
- Quote: doc_b5d46abd6e6c (Hero Image Test Quote, CHF 5000, with hero image)

## Remaining
- P0: Deploy to production + verify all 23 items on app.evo-home.ch
- P1: Organ 4 — Control Tower Dashboard restructuring
- P1: Organ 5 — Decisions rebuild
- P2: Hook dependency warnings
- P3: Email digests, reporting/export

---
Last Updated: April 12, 2026
