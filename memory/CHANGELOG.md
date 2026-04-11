# Workflow Canonicalization + Entitlement Fix — COMPLETE (2026-04-11)

### Objective
Eliminate all direct DB writes from workflows.py. Remove semantically wrong entitlement check from project creation.

### Completed Work

#### `workflows.py` — Fully Rewritten (zero direct DB writes)
- `create_client` action → `client_service.create_client()`
- `update_document_status` action → `document_service.transition_document_status()`
- `complete_timeline_step` action → `step_service.update_step()`
- `create_announcement` action → `activity_service.create_and_distribute_activity()`
- Email actions remain as orchestration (Resend API, no DB mutation)
- 19 read-only DB queries for context enrichment and selectors (allowed)
- Reduced from 1027 lines to ~640 lines

#### `document_service.py` — Added `transition_document_status()`
- Workflow-initiated status transitions with state machine validation
- Sets appropriate timestamps (paid_date, sent_at)

#### `projects_v2.py` — Entitlement Check Removed
- Project creation no longer checks unit limits (semantically wrong)
- Unit limits enforced only at unit creation (units.py)

### Regression
- 18/18 tests passed (iteration_16)
- All 5 workflow templates verified: new_client_onboarding, invoice_paid_processing, milestone_completion, send_document, project_announcement

---


# Frontend Canonical Alignment — COMPLETE (2026-04-11)

### Objective
Align frontend to canonical backend contracts. Remove dead `is_demo` UI branches. Fix stale billing field names.

### Completed Work

#### Dead `is_demo` UI Branches — Removed
- AgentLayout.js: Removed `{user?.is_demo && (<span>DEMO</span>)}` block
- BuyerLayout.js: Removed identical block

#### Billing Field Alignment — 5 Files Fixed
- `property_usage` → `unit_usage` (AgentBilling, AgentProjects, AgentSettings)
- `can_create_property` → `can_create_unit` (AgentBilling, AgentProjects)
- `usage_percent` → computed locally from `unit_usage / property_limit` (AgentBilling, AgentSettings)
- `near_limit` → computed locally: `unit_usage >= property_limit * 0.8` (AgentBilling, AgentProjects)

### Result
- Zero stale field references remaining in entire frontend codebase
- Zero `is_demo` / `isDemo` references remaining
- 12/12 frontend tests passed (iteration_15)

---


# Phase 4: Canonical Billing Rebuild — COMPLETE (2026-04-11)

### Objective
Rebuild billing as a canonical subsystem: single source of truth for subscription state, thin routes, webhook signature verification, real Stripe cancel, centralized entitlements.

### Domain Model (Frozen)
- **Plan**: Static config in helpers.py. Immutable.
- **Subscription**: Local projection of Stripe state on users collection.
- **Entitlement**: Computed from Plan + Subscription. Never stored.
- **Truth hierarchy**: Webhook = primary authority. verify-session = reconciliation. Local DB = projection.

### Completed Work

#### `billing_service.py` — Fully Rewritten as SSOT
- `apply_subscription_update()` with `_UNSET` sentinel pattern (distinguishes "not provided" from "set to None")
- `get_subscription_status()` — full status with derived entitlements
- `can_create_unit()`, `get_unit_limit()` — centralized entitlement checks
- `create_checkout_session()` — Stripe session creation
- `verify_checkout()` — recovery/reconciliation (calls canonical updater)
- `handle_webhook_event()` — PRIMARY truth dispatcher for 4 event types
- `cancel_subscription()` — real Stripe cancel via `stripe.Subscription.modify(cancel_at_period_end=True)`
- `sync_subscription()` — recovery from Stripe (tries sub first, falls back to session)
- `create_billing_portal()` — Stripe portal session
- `get_all_plans()`, `get_plan()` — plan lookup

#### `routes/billing.py` — Rewritten as Thin Routes
- 8 endpoints, each: validate → auth → delegate to service → return response
- Zero business logic, zero direct DB writes, zero Stripe SDK calls
- Webhook signature verification when STRIPE_WEBHOOK_SECRET is configured
- Clean imports (only what's used)

#### Entitlement Checks Centralized
- `units.py`: Uses `can_create_unit()` + `get_unit_limit()` from billing_service
- `projects_v2.py`: Uses `get_subscription_status()` from billing_service
- `settings.py`: Uses `get_subscription_status()` from billing_service
- `project_service.py`: Updated import

#### Webhook Events Handled
- `checkout.session.completed` → activates subscription
- `customer.subscription.updated` → updates status/plan
- `customer.subscription.deleted` → downgrades to free, clears stripe_subscription_id
- `invoice.payment_failed` → sets status to past_due

### Regression
- 33/33 tests passed (iteration_14)
- Plans, status, checkout, webhook (all 4 events), cancel, sync, entitlement enforcement, auth requirements all verified.
- Sentinel pattern verified: subscription.deleted correctly writes `stripe_subscription_id: null`

### Architecture Notes
- Plan catalog lives in app config (helpers.py), not Stripe Products. Acceptable for now. Future: Stripe-native product catalog optional.
- Inline price_data at checkout (not pre-created Stripe Prices). Documented as intentional.

---


# System Perimeter `is_demo` Purge — COMPLETE (2026-04-11)

### Objective
Purge `is_demo` from ALL remaining system ingress points: invitations, demo seeding, Pydantic schemas, and auth signatures. After this pass, no non-test backend code writes, reads, or branches on `is_demo`.

### Completed Work

#### `invitations.py` — Purged
- [x] Removed 2 defensive `"is_demo": 0` projections (lines 114, 147)
- [x] File already had zero is_demo writes from previous overwrite

#### `demo.py` — Fully Rewritten (Canonical)
- [x] Deterministic `demo_*` ID namespace for ALL seeded entities
- [x] Cleanup via ID prefix regex (`{id_field: {"$regex": "^demo_"}}`) — no is_demo deletes
- [x] Zero `is_demo` writes across all seeded documents
- [x] Zero `is_demo` branching (DEMO_MODE logic removed)
- [x] Trimmed imports (removed ~20 unused imports from mechanical extraction)
- [x] ID namespace: demo_agent_*, demo_buyer_*, demo_proj_*, demo_client_*, demo_doc_*, demo_act_*, demo_rcpt_*, demo_reply_*, demo_member_*, demo_unit_*, demo_tmpl_*, demo_tmpl_step_*, demo_timeline_*, demo_step_*, demo_link_*, demo_note_*

#### `schemas.py` — 7 Dead Fields Removed
- [x] `UserBase.is_demo` removed
- [x] `Client.is_demo` removed
- [x] `TeamMember.is_demo` removed
- [x] `Document.is_demo` removed
- [x] `ProjectStage.is_demo` removed
- [x] `Activity.is_demo` removed
- [x] `Notification.is_demo` removed

#### `core/auth.py` — Dead Wrapper Deleted
- [x] `create_jwt_token(user_id, role, is_demo=False)` wrapper deleted entirely
- [x] Stale is_demo comments cleaned from docstrings
- [x] Added `JWT_EXPIRY_DAYS = 7` (was missing, needed by invitations.py import)

#### `routes/auth.py` — Cleaned
- [x] Local `create_jwt_token` wrapper deleted
- [x] All 10 callers replaced with direct `create_access_token`
- [x] 5 defensive `"is_demo": 0` projections removed
- [x] is_demo filter in `/auth/me` response removed

#### `admin.py`, `analytics.py` — Dead Assignments Removed
- [x] 2 dead `is_demo = user.get('is_demo', False)` assignments removed from admin.py
- [x] 1 dead `is_demo = user.get('is_demo', False)` assignment removed from analytics.py

#### Database Cleanup
- [x] 16 orphaned legacy demo records (activity_recipients, activity_replies, timeline_templates) cleaned
- [x] Post-seed verification: zero is_demo fields across ALL 16 checked collections

### Regression
- 24/24 tests passed (iteration_13)
- Demo seed, demo login, agent login, auth/me, auth/session, team invitations, data relationships, agent registration, E2E access all verified

---


# Evohome CMP — Canonical Surgical Rebuild Changelog

## Phase 3: Orchestration — COMPLETE (2026-04-11)

### Objective
Rebuild the Comment Center / Command Service as a pure orchestration brain that routes intents to Phase 1/2 canonical services. Eliminate notification_bridge.py. Make notification_service.py the canonical notification module. Purge is_demo from all orchestration code.

### Completed Work

#### notification_service.py — Canonical Notification Module
- [x] `create_notification` — canonical write, no is_demo
- [x] `emit_notification` — alias for create_notification
- [x] `emit_email` — lazy-import wrapper for email_service.send_notification_email
- [x] `emit_realtime` — lazy-import wrapper for realtime_service.notify_realtime
- [x] `list_notifications`, `mark_read`, `mark_all_read` — existing read ops preserved

#### notification_bridge.py — DELETED
- [x] 3 Phase 2 services (document_service, activity_service, vault_service) migrated to notification_service
- [x] realtime_service.py updated: create_notification imported from notification_service
- [x] email_service.create_notification converted to backward-compat shim (absorbs is_demo via **kwargs)
- [x] Zero references to notification_bridge remain in codebase

#### command_service.py — Pure Routing Brain
- [x] `_route_to_service()` replaces `_execute_by_intent()` — routes to canonical services
- [x] `_route_document()` delegates to `document_service.create_document()`
- [x] `_route_activity()` delegates to `activity_service.create_draft_activity()`
- [x] `_create_document()` DELETED (was 47 lines of direct DB write with is_demo)
- [x] `_create_feed_activity()` DELETED (was 39 lines of direct DB write with is_demo)
- [x] `execute_draft()` no longer takes is_demo parameter

#### activity_service.py — New canonical function
- [x] `create_draft_activity()` — creates draft activity without is_demo, no distribution

#### commands.py route — Cleaned
- [x] Removed is_demo from execute endpoint call
- [x] Removed is_demo from history endpoint
- [x] Removed unused get_is_demo import

#### is_demo Purge (Phase 3 Scope)
- [x] command_service.py: 12 → 0 occurrences
- [x] commands.py: 3 → 0 occurrences
- [x] realtime_service.py (send_milestone_notification): 2 → 0 occurrences
- [x] timelines_v2.py: 1 → 0 occurrences
- [x] notification_bridge.py: DELETED entirely

### Regression: 20/20 passed (100%) — `/app/test_reports/iteration_8.json`

### Notification Contract Fix (post-evaluation) — COMPLETE (2026-04-11)
- [x] C1: Response shape restored: `{"notifications": [...], "unread_count": N}` (was flat array)
- [x] C2: Standardized on `is_read` field (was `read` — broke frontend + mark_read queries)
- [x] I1: `mark_read`/`mark_all_read` queries now use `is_read` (matched legacy data + frontend)
- [x] DB migration: removed `read` field (0 docs) and `is_demo` field (1 doc) from notifications collection
- [x] Frontend fix: `NotificationCenter.js` HTTP method PUT→PATCH (matched notifications_v2.py)
- [x] MongoDB clean: 5/5 docs with `is_read`, 0 with `read`, 0 with `is_demo`
### Regression: 19/19 passed (100%) — `/app/test_reports/iteration_9.json`
### Route Map: `/app/memory/PHASE3_ROUTE_MAP.md`

---

## P1 Legacy Cleanup — COMPLETE (2026-04-11)

### Deleted V1 Route Files (9 total)
- [x] `routes/activities.py` — dead code, replaced by `activities_v2.py`
- [x] `routes/clients.py` — dead code, replaced by `clients_v2.py`
- [x] `routes/documents.py` — dead code, replaced by `documents_v2.py`
- [x] `routes/notifications.py` — dead code, replaced by `notifications_v2.py`
- [x] `routes/steps.py` — dead code, replaced by `steps_v2.py`
- [x] `routes/timeline_view.py` — dead code, replaced by `timelines_v2.py`
- [x] `routes/timelines.py` — dead code, replaced by `timelines_v2.py`
- [x] `routes/vault.py` — dead code, replaced by `vault_v2.py`
- [x] `routes/projects.py` — team endpoints extracted to `team_v2.py`, then deleted

### Team Module Extraction
- [x] `services/team_service.py` — canonical team member lifecycle, no is_demo
- [x] `routes/team_v2.py` — thin route for CRUD + directory + AI extraction
- [x] 7 endpoints: GET/POST/PUT/DELETE team, bulk, directory, extract-contacts
- [x] `server.py` wired `team_router`, removed `projects_team_router`

### Workflow Sanitization
- [x] `routes/workflows.py` — 10 is_demo refs removed (imports, queries, writes)
- [x] `services/workflow_service.py` — 5 is_demo refs removed (model, create, query)

### Dead Import Cleanup
- [x] `create_notification` import removed from 11 route files
- [x] `email_service.create_notification` shim deleted entirely

### Regression: 33/33 passed (100%) — `/app/test_reports/iteration_10.json`

### P1 Corrective Pass — COMPLETE (2026-04-11)
- [x] C1: `RESEND_API_KEY` imported from `email_service` into `workflows.py` (was NameError)
- [x] I1: `doc_extraction.py` zero `is_demo` references (was writing to documents collection)
- [x] I2: `stats.py` zero `is_demo` filtering (was filtering buyer stats by `is_demo`)
- [x] I3: Dead `get_is_demo` import removed from 9 route files
- [x] DB migration: `is_demo` field removed from 127 documents across 9 collections
### Regression: 24/24 passed (100%) — `/app/test_reports/iteration_11.json`

---

## Phase 2: Content Layer — COMPLETE (2026-04-11)

### Objective
Rebuild 4 content modules (Activity, Document, VaultDocument, Notification) with canonical services and thin routes. Eradicate `is_demo` from all Phase 2 modules.

### Completed Work

#### Services Layer
- [x] `activity_service.py` — CRUD, enrichment, replies, draft send, mark-seen, unread count, notification orchestration
- [x] `document_service.py` — CRUD, status machine (send/approve/reject/pay/convert), reupload with versioning, document timeline
- [x] `vault_service.py` — CRUD, buyer access, notification on share
- [x] `notification_service.py` — list, mark_read, mark_all_read (canonical, replaces class-based legacy)
- [x] `notification_bridge.py` — Temporary wrapper for `create_notification(is_demo=False)`, to be removed later

#### V2 Thin Routes
- [x] `activities_v2.py` — Full activity lifecycle, file serving
- [x] `documents_v2.py` — Full document lifecycle, PDF gen, QR code, hero images, AI extraction (assistive only)
- [x] `vault_v2.py` — Vault CRUD, file upload/download
- [x] `notifications_v2.py` — 3 thin endpoints

#### Traffic Switching (module by module)
- [x] Activity: `activities.py` → `activities_v2.py`
- [x] Document: `documents.py` → `documents_v2.py`
- [x] VaultDocument: `vault.py` → `vault_v2.py`
- [x] Notification: `notifications.py` → `notifications_v2.py`
- [x] `timeline_view.py` removed from server.py (replaced by `documents_v2.py`)

#### is_demo Eradication (Phase 2 Scope)
- [x] No `is_demo` in any Phase 2 service query filter
- [x] All Phase 2 service projections exclude `is_demo` via `{"is_demo": 0}`
- [x] New documents do NOT include `is_demo`
- [x] `notification_bridge.py` wraps legacy `create_notification` — no `is_demo=False` propagation in new code

### Regression: 32/32 passed (100%) — `/app/test_reports/iteration_7.json`

---

## Phase 1: Canonical Core — COMPLETE (2026-04-11)

### Completed
- [x] 5 core modules (Unit, Project, Timeline, TimelineStep, Client) rebuilt
- [x] Services + thin V2 routes, traffic switched
- [x] `is_demo` eradicated from Phase 1 schemas and services
- [x] Timeline AI extraction intentionally removed

### Regression: 33/33 passed (100%) — `/app/test_reports/iteration_6.json`

---

## Pre-Phase 1: Deploy Hardening (2026-04-10)
- CORS, exception handler, health checks, security headers
- Missing imports fix across 7 route files
- Stripe session mode fix
