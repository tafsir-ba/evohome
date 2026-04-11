# Evohome CMP — Canonical Surgical Rebuild Changelog

## Phase 1: Canonical Core — COMPLETE (2026-04-11)

### Objective
Rebuild 5 core modules (Unit, Project, Timeline, TimelineStep, Client) with canonical services and thin routes. Eradicate `is_demo` from all Phase 1 modules.

### Completed Work

#### Services Layer (Canonical Business Logic)
- [x] `unit_service.py` — CRUD, bulk ops, project/agent queries
- [x] `project_service.py` — CRUD, list by agent/buyer, context enrichment
- [x] `timeline_service.py` — CRUD, create with steps, enriched timeline, cascade delete, template CRUD + apply
- [x] `step_service.py` — CRUD, add to timeline, document linking, notes, status transitions
- [x] `client_service.py` — CRUD, list by agent/project, detail enrichment

#### V2 Thin Routes (No is_demo, No Business Logic)
- [x] `routes/units.py` — Unit CRUD
- [x] `routes/projects_v2.py` — Project CRUD (team endpoints stay in legacy projects.py)
- [x] `routes/timelines_v2.py` — Timeline CRUD, step management, templates (NO extraction)
- [x] `routes/steps_v2.py` — Step CRUD via project context
- [x] `routes/clients_v2.py` — Client CRUD

#### Traffic Switching
- [x] `server.py` routes to V2 for all 5 modules
- [x] Legacy `projects.py` retained ONLY for team endpoints
- [x] Legacy `timelines.py` fully replaced

#### is_demo Eradication (Phase 1 Scope)
- [x] No `is_demo` in any Phase 1 service query filter
- [x] No `is_demo` in any Phase 1 Pydantic schema
- [x] All Phase 1 service projections exclude `is_demo`
- [x] New documents do NOT include `is_demo`
- [x] `fragility_test.py` updated

#### Intentionally Removed
- All timeline extraction endpoints (POST extract, GET/POST/DELETE extractions)

### Regression: 33/33 passed (100%) — `/app/test_reports/iteration_6.json`

---

## Pre-Phase 1: Deploy Hardening (2026-04-10)
- CORS, exception handler, health checks, security headers
- Missing imports fix across 7 route files
- Stripe session mode fix
- is_demo removed from access_control.py indexes
