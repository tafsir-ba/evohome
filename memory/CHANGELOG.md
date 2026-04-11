# Evohome CMP — Canonical Surgical Rebuild Changelog

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
