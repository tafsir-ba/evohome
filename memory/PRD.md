# Evohome CMP — Product Requirements Document

## Architecture
- **Backend**: FastAPI + Motor (MongoDB async) — canonical SSOT services, thin routes
- **Frontend**: React 18 + TailwindCSS + Shadcn/UI
- **Database**: MongoDB Atlas (`evohome_cmp`)
- **Integrations**: OpenAI GPT-4o, Stripe (webhooks verified), Resend, Google OAuth

## Organ Status (Contractual)
| Organ | Status | Preview-Verified |
|-------|--------|-----------------|
| 1. Upload/Media | Implemented | Partial (backend curl + vault page screenshot) |
| 2. Client/Project/Unit | Implemented | Yes (all pages screenshotted) |
| 3. Change Request Thread | Implemented | Yes (full e2e via UI) |

**None are production-verified. Closure requires deployment to app.evo-home.ch.**

## Verified via UI Screenshots (Preview)
- Invoice upload: context subtitle shows `Résidence Les Pins / Lot 3.01` below selector
- Clients list: project + unit badges visible
- Client detail: project name renders correctly (after GET /projects/{id} fix)
- Quote detail: ChangeRequestPanel with Reply/Resolve buttons
- Invoice detail: ChangeRequestPanel identical to quote (parity confirmed)
- Agent Reply submission: toast "Response sent", status → Under Review, message visible
- Agent Resolve: toast "Change request resolved", status → Resolved, Close button appears
- Buyer sees resolved thread: full message history (buyer + agent) visible after resolution
- Buyer notifications: real notifications visible in bell dropdown
- Dashboard: 6 Change Requests aggregate count

## Canonical Formatters (lib/utils.js)
- `formatClientContext`: "Name — Project — Unit"
- `formatClientContextCompact`: "Name (Project / Unit)"
- `formatContextSubtitle`: "Project / Unit"
- `formatDocContext`: "Number · Client · Project · Unit"

## Bug Fixed During Validation
- Missing `GET /api/projects/{project_id}` endpoint (caused raw ID display in client detail)

## Test Accounts
- Agent: agent@evohome-test.ch / Evohome2026! (POST /api/auth/login)
- Buyer: buyer@evohome-test.ch / Evohome2026! (POST /api/auth/buyer/login)

## Remaining
- P0: Production deployment + verification on app.evo-home.ch
- P1: Organ 4 — Control Tower Dashboard restructuring
- P1: Organ 5 — Decisions rebuild
- P2: Hook dependency warnings
- P3: Email digests, reporting/export

---
Last Updated: April 12, 2026
