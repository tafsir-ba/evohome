# Implementation Impact Map
## Phase C Control Panel (Updated)

**Date**: January-February 2026  
**Purpose**: Track implementation progress and remaining work

---

## Collections Impact

| Collection | Action | Phase C Status | Migration Script | Notes |
|------------|--------|----------------|------------------|-------|
| `project_units` | RENAME -> `units` | PARTIAL (compat for GET/POST/DELETE) | Yes | ~15 direct refs remain in server.py |
| `units` | KEEP (absorb data) | IN USE | Receiver | Canonical collection active |
| `project_timelines` | RENAME -> `timelines` | COMPLETE | Yes | All refs routed through `db_compat` |
| `timelines` | KEEP (absorb data) | IN USE | Receiver | Canonical collection active |
| `project_stages` | DELETE | PENDING (Phase D) | Yes (merge) | Only in demo reset delete_many |
| `timeline_steps` | KEEP | COMPLETE | Field rename only | Queries use $or for both FK names |
| `activities` | KEEP | N/A | None | Already canonical |
| `activity_recipients` | KEEP | N/A | None | Already canonical |
| `activity_replies` | KEEP | N/A | None | Already canonical |
| `documents` | KEEP | N/A | None | Already canonical |
| `vault_documents` | KEEP | N/A | None | Already canonical |
| `notifications` | KEEP | N/A | None | Already canonical |
| `team_members` | KEEP | N/A | None | Already canonical |
| `clients` | KEEP | N/A | None | Already canonical |
| `projects` | KEEP | N/A | None | Already canonical |
| `users` | KEEP | N/A | None | Already canonical |

---

## Field Renames Status

| Collection | Old Field | New Field | Phase C Status | DB Migration Needed |
|------------|-----------|-----------|----------------|---------------------|
| `timelines` | `project_timeline_id` | `timeline_id` | NORMALIZED IN API | Yes (Phase D) |
| `timeline_steps` | `project_timeline_id` | `timeline_id` | DUAL-WRITE + NORMALIZED IN API | Yes (Phase D) |

---

## Backend Endpoints Phase C Status

### Routes With Compatibility Routing (COMPLETE)

| Route | Collection Migration | Field Normalization | Status |
|-------|---------------------|---------------------|--------|
| `GET /projects/{id}/stages` | via `db_compat.find_timeline_one` | `timeline_id` in response | COMPLETE |
| `POST /projects/{id}/stages` | via `db_compat.find_timeline_one` + `insert_timeline` | dual-write FK | COMPLETE |
| `PUT /projects/{id}/stages/{id}` | via `db_compat.find_timeline_one` | N/A | COMPLETE |
| `DELETE /projects/{id}/stages/{id}` | via `db_compat.find_timeline_one` | N/A | COMPLETE |
| `GET /projects/{id}/steps` | delegates to /stages impl | Same as /stages | COMPLETE |
| `POST /projects/{id}/steps` | delegates to /stages impl | Same as /stages | COMPLETE |
| `PUT /projects/{id}/steps/{id}` | delegates to /stages impl | Same as /stages | COMPLETE |
| `DELETE /projects/{id}/steps/{id}` | delegates to /stages impl | Same as /stages | COMPLETE |
| `GET /project-timeline` | via `db_compat.find_timeline_one` | Both timeline + step FK normalized | COMPLETE |
| `GET /projects/{id}/timeline/full` | via `db_compat.find_timeline_one` | `timeline_id` in response | COMPLETE |
| `GET /projects/{id}/workflow/full` | via `db_compat.find_timeline_one` | `timeline_id` in response | COMPLETE |
| `POST /timeline/create` | via `db_compat.insert_timeline` | dual-write FK | COMPLETE |
| `POST /timeline/{id}/steps` | via `db_compat.find_timeline_one` | dual-write FK, normalized return | COMPLETE |
| `PATCH /timeline/steps/{id}` | via `db_compat.find_timeline_one` | normalized return | COMPLETE |
| `DELETE /timeline/steps/{id}` | via `db_compat.find_timeline_one` | N/A | COMPLETE |
| `POST /timeline/steps/{id}/documents` | via `db_compat.find_timeline_one` | N/A | COMPLETE |
| `DELETE /timeline/steps/{id}/documents/{id}` | via `db_compat.find_timeline_one` | N/A | COMPLETE |
| `POST /timeline/steps/{id}/notes` | via `db_compat.find_timeline_one` | N/A | COMPLETE |
| `DELETE /timeline/{id}` | via `db_compat.find_timeline_one` + `delete_timeline_one` | N/A | COMPLETE |
| `POST /timeline/extractions/{id}/approve` | via `db_compat.insert_timeline` | dual-write FK | COMPLETE |
| `POST /timeline/apply-template` | via `db_compat.find_timeline_one` + `insert_timeline` | dual-write FK | COMPLETE |
| Demo seed | via `db_compat.insert_timeline` + `delete_timelines_many` | dual-write FK | COMPLETE |
| AI extraction timeline check | via `db_compat.find_timeline_one` | N/A | COMPLETE |
| Selector (timeline_step) | via `db_compat.find_timeline_one/many` | normalized in response | COMPLETE |

### Routes Unchanged (Already Canonical)

- All `/activities/*` routes
- All `/documents/*` routes
- All `/vault/*` routes
- All `/notifications/*` routes
- All `/clients/*` routes
- All `/auth/*` routes
- All `/billing/*` routes

---

## Compat Layer Methods Used

| Method | Purpose | Usage Count |
|--------|---------|-------------|
| `find_timeline_one(query, projection)` | Dual-read find_one | ~20 |
| `find_timeline_many(query, projection)` | Dual-read find | 1 |
| `insert_timeline(doc)` | Write to canonical only | 5 |
| `delete_timeline_one(query)` | Delete from both | 1 |
| `delete_timelines_many(query)` | Delete many from both | 2 |
| `timeline_ref_query(tl_id)` | $or query for step FK | ~8 |
| `timeline_ref_fields(tl_id)` | Dual-write FK fields | ~6 |
| `get_step_timeline_ref(step)` | Defensive FK access | ~8 |

---

## Phase C Done Condition Checklist

- [x] `timelines` is the canonical collection path
- [x] `timeline_id` is the canonical field everywhere externally visible
- [x] `/stages` still works via compatibility
- [x] All regression tests pass (14/14)
- [x] Docs updated (this file + PHASE_C_CONFLICT_REPORT.md)

---

## Remaining Work (Phase E-F)

| Phase | Task | Priority |
|-------|------|----------|
| E | Remove compat dual-reads (read canonical only) | P1 |
| E | Update remaining `db.project_units` direct refs in server.py | P1 |
| E | Update Pydantic models to drop deprecated fields | P1 |
| E | Update frontend API calls if needed | P1 |
| F | Remove deprecated `/stages` routes | P2 |
| F | Drop `project_timelines` collection | P2 |
| F | Drop `project_units` collection | P2 |
| F | Drop `project_stages` collection | P2 |
| F | Remove `db_compat.py` compat layer | P2 |

## Phase D: Data Migration (COMPLETE)

**Executed**: 2026-04-10  
**Script**: `/app/backend/migrations/phase_d_migrate.py`  
**Report**: `/app/backend/migrations/MIGRATION_REPORT.md`

| Migration | Result | Details |
|---|---|---|
| M1: project_units → units | PASS | 17 docs migrated, 0 errors |
| M2: project_timelines → timelines | PASS | 2 docs migrated, field renamed |
| M3: timeline_steps field normalization | PASS | 12 docs got `timeline_id` field |

**Verification**: 5/5 checks passed (collection counts, field coverage, referential integrity)  
**Idempotency**: Confirmed (second run: 0 inserts, all skipped)  
**Regression**: 14/14 API endpoints passed post-migration  
**Backups**: `/app/backend/migrations/backup/20260410_180933/` and `/app/backend/migrations/backup/20260410_181137/`

---

*Last updated: February 2026*
