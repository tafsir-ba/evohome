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
