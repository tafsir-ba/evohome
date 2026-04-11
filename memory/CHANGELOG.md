# Phase 5: UX Refinement Sprint 1 — COMPLETE (2026-04-11)

### P0 — Feed Skeleton Bug Fix
- Root cause: N+1 query pattern — frontend fetched each activity's detail individually (9 requests x 6.3s = 56s total timeout)
- Fix: Removed Promise.all enrichment loop from Feed.js. List endpoint already returns enriched activities.
- Added lazy-load replies on expand (fetches detail only when user clicks "More")
- Added Authorization header fallback alongside credentials: 'include'
- Feed now loads in ~6s (single API call) instead of timing out

### P1 — Feed Promoted to Primary Navigation
- Moved Feed from `moreNavigation` to `navigation` array in AgentLayout.js
- Positioned between Team and Quotes in sidebar

### P1 — Dashboard Control Tower
- Replaced "Command Center" header with "Control Tower" title
- Added Action Cards row: Change Requests (amber), Pending Invoices (red), Pending Quotes (blue) — all clickable
- Added KPI Strip: Total Clients, Active Projects, Revenue (CHF), Approved Quotes
- Repositioned Command Bar below action cards with "Command Bar" label
- Added deduplication filter on Recent Activity (removes duplicate titles)
- Data source: `/api/stats/agent` (existing canonical endpoint)

### P2 — Billing UX Cleanup
- Removed Sync button (debug-only affordance) from AgentBilling.js
- Removed duplicate "Subscription Details" card at bottom of billing page
- Single authoritative billing control area remains

### P2 — Settings Billing Tab Cleanup
- Replaced full plan grid in Settings > Billing tab with compact plan summary
- Added "Manage Billing" button that redirects to dedicated `/agent/billing` page
- Payment Settings (IBAN) section preserved — this is settings-appropriate
- One source of truth for billing management

### Regression
- 9/9 frontend tests passed (iteration_17)
- All action cards render and route correctly
- Feed loads 8 activities without skeleton hang
- No console errors

---

# P3 Optimization Pass — COMPLETE (2026-04-11)

### Removed
- 44 defensive projections (`"is_demo": 0`) across 9 service files
- 2 defensive pops (`activity.pop('is_demo')`, `doc.pop('is_demo')`)
- 6 dead mega-import blocks (`from helpers import ...` in stats, doc_extraction, test_endpoints, commands, admin, analytics)
- 2 redundant billing response fields (`current_unit_count`, `unit_limit`)
- Fixed billing contract: `subscription_period_end` → `current_period_end` (matches frontend + Stripe naming)

### Result
- Backend `is_demo` refs: 73 → 26 (22 comments, 3 config, 1 migration file)
- Zero defensive ballast remaining
- Billing API contract: 9 fields, zero duplicates
- All endpoints verified working

---

# Workflow Canonicalization + Entitlement Fix — COMPLETE (2026-04-11)

### Completed Work
- `workflows.py` — Fully Rewritten (zero direct DB writes)
- `document_service.py` — Added `transition_document_status()`
- `projects_v2.py` — Entitlement Check Removed
- 18/18 regression tests passed (iteration_16)

---

# Frontend Canonical Alignment — COMPLETE (2026-04-11)
- Dead `is_demo` UI branches removed
- Billing field alignment (5 files fixed)
- 12/12 frontend tests passed (iteration_15)

---

# Phase 4: Canonical Billing Rebuild — COMPLETE (2026-04-11)
- billing_service.py as SSOT
- Thin routes, webhook verification, real Stripe cancel
- 33/33 tests passed (iteration_14)

---

# System Perimeter is_demo Purge — COMPLETE (2026-04-11)
- All is_demo removed from invitations, demo, schemas, auth
- 24/24 tests passed (iteration_13)

---

# Earlier phases (1-3, Legacy Cleanup) — All COMPLETE
- See previous changelog entries for details
