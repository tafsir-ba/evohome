# Phase C: Conflict Report
## Live Code vs Canonical Schema Discrepancies

**Date**: January-February 2026  
**Status**: COMPLETE

---

## Phase C Progress

| Task | Status | Notes |
|------|--------|-------|
| Create db_compat.py | COMPLETE | Compatibility helper module |
| Initialize in server.py | COMPLETE | `init_compat(db)` called at boot |
| Add dual /steps routes | COMPLETE | Both /stages and /steps work |
| Update GET /units | COMPLETE | Uses canonical + fallback |
| Update POST /units | COMPLETE | Writes to canonical |
| Update DELETE /units | COMPLETE | Deletes from both |
| Timeline collection migration | COMPLETE | All `db.project_timelines` routed through compat |
| Timeline ID field normalization | COMPLETE | API responses use `timeline_id` only |
| Step FK field normalization | COMPLETE | `project_timeline_id` normalized to `timeline_id` in responses |
| Regression tests | PASSED | 14/14 endpoints verified |

---

## Conflicts Found and Resolved

### 1. Units Collection

| Location | Current Code | Canonical | Status |
|----------|--------------|-----------|--------|
| get_units | `db.project_units` -> `db_compat.get_units` | `db.units` | RESOLVED |
| create_unit | `db.project_units` -> `db_compat.create_unit` | `db.units` | RESOLVED |
| delete_unit | `db.project_units` -> `db_compat.delete_unit` | `db.units` | RESOLVED |

### 2. Timelines Collection

| Location | Current Code | Canonical | Status |
|----------|--------------|-----------|--------|
| get_project_stages | `db.project_timelines` -> `db_compat.find_timeline_one` | `db.timelines` | RESOLVED |
| create_project_stage | `db.project_timelines` -> `db_compat.find_timeline_one` + `insert_timeline` | `db.timelines` | RESOLVED |
| update_project_stage | `db.project_timelines` -> `db_compat.find_timeline_one` | `db.timelines` | RESOLVED |
| delete_project_stage | `db.project_timelines` -> `db_compat.find_timeline_one` | `db.timelines` | RESOLVED |
| get_project_timeline_full | `db.project_timelines` -> `db_compat.find_timeline_one` | `db.timelines` | RESOLVED |
| get_project_workflow_full | `db.project_timelines` -> `db_compat.find_timeline_one` | `db.timelines` | RESOLVED |
| create_timeline (endpoint) | `db.project_timelines` -> `db_compat.insert_timeline` | `db.timelines` | RESOLVED |
| approve_timeline_extraction | `db.project_timelines` -> `db_compat.insert_timeline` | `db.timelines` | RESOLVED |
| apply_template | `db.project_timelines` -> `db_compat.find_timeline_one` + `insert_timeline` | `db.timelines` | RESOLVED |
| get_project_timeline | `db.project_timelines` -> `db_compat.find_timeline_one` | `db.timelines` | RESOLVED |
| update_timeline_step | `db.project_timelines` -> `db_compat.find_timeline_one` | `db.timelines` | RESOLVED |
| add_timeline_step | `db.project_timelines` -> `db_compat.find_timeline_one` | `db.timelines` | RESOLVED |
| delete_timeline_step | `db.project_timelines` -> `db_compat.find_timeline_one` | `db.timelines` | RESOLVED |
| link_document_to_step | `db.project_timelines` -> `db_compat.find_timeline_one` | `db.timelines` | RESOLVED |
| unlink_document_from_step | `db.project_timelines` -> `db_compat.find_timeline_one` | `db.timelines` | RESOLVED |
| add_internal_note | `db.project_timelines` -> `db_compat.find_timeline_one` | `db.timelines` | RESOLVED |
| delete_project_timeline | `db.project_timelines` -> `db_compat` (find + delete) | `db.timelines` | RESOLVED |
| demo reset | `db.project_timelines.delete_many` -> `db_compat.delete_timelines_many` | `db.timelines` | RESOLVED |
| demo seed | `db.project_timelines.insert_one` -> `db_compat.insert_timeline` | `db.timelines` | RESOLVED |
| AI extraction check | `db.project_timelines` -> `db_compat.find_timeline_one` | `db.timelines` | RESOLVED |
| selector (timeline_step) | `db.project_timelines` -> `db_compat.find_timeline_one/many` | `db.timelines` | RESOLVED |

### 3. Field Normalization (timeline_id)

| Context | Old Field | New Field | Status |
|---------|-----------|-----------|--------|
| Timeline documents | `project_timeline_id` | `timeline_id` | RESOLVED (via `_normalize_timeline_id`) |
| Step FK in writes | `project_timeline_id` only | Both `timeline_id` + `project_timeline_id` | RESOLVED (via `timeline_ref_fields`) |
| Step FK in reads | `project_timeline_id` | `$or` on both fields | RESOLVED (via `timeline_ref_query`) |
| Step FK in API output | `project_timeline_id` | `timeline_id` | RESOLVED (normalized before return) |
| Step access pattern | `step['project_timeline_id']` | `get_step_timeline_ref(step)` | RESOLVED |

### 4. API Routes

| Route | Status | Notes |
|-------|--------|-------|
| `GET /projects/{id}/stages` | DEPRECATED | Works via delegation to `get_project_stages` |
| `POST /projects/{id}/stages` | DEPRECATED | Works via delegation |
| `PUT /projects/{id}/stages/{id}` | DEPRECATED | Works via delegation |
| `DELETE /projects/{id}/stages/{id}` | DEPRECATED | Works via delegation |
| `GET /projects/{id}/steps` | CANONICAL | Delegates to same impl |
| `POST /projects/{id}/steps` | CANONICAL | Delegates to same impl |
| `PUT /projects/{id}/steps/{id}` | CANONICAL | Delegates to same impl |
| `DELETE /projects/{id}/steps/{id}` | CANONICAL | Delegates to same impl |

---

## Remaining Legacy Touchpoints

| Area | Deprecated Reference | Why Still Present | When to Remove |
|------|---------------------|-------------------|----------------|
| `project_timeline_id` field in DB | Stored alongside `timeline_id` in documents | Data not yet cleaned | Phase F |
| `/stages` API routes | Still functional | Maintained for backward compat | Phase F |
| `project_timelines` collection | Data still in deprecated collection | Not dropped yet | Phase F |
| `project_units` collection | Data still in deprecated collection | Not dropped yet | Phase F |
| `project_stages` collection | Demo reset still deletes from it | Legacy cleanup target | Phase F |
| Response normalization code | `pop('project_timeline_id')` in 3 endpoints | Safety net for DB data | Phase F |
| `db_compat.py` module | Still used for canonical reads | Simplify to direct DB calls | Phase F |

---

## Phase E: Code Refactoring (COMPLETE)

**Executed**: 2026-04-10

- [x] `COMPAT_MODE` set to `False` — no fallback reads from deprecated collections
- [x] All `db.project_units` (16 refs) → `db.units`
- [x] All `db.project_stages` reads → `db.timeline_steps`
- [x] All `$or` queries with `project_timeline_id` → canonical `timeline_id` only
- [x] `timeline_ref_query()` → returns `{"timeline_id": X}` (no $or)
- [x] `timeline_ref_fields()` → returns `{"timeline_id": X}` (no dual-write)
- [x] Pydantic `TimelineStep` model — dropped `project_timeline_id` field
- [x] Demo seed — writes `timeline_id` only
- [x] Frontend `AgentWorkflow.js` — removed `project_timeline_id` fallback
- [x] Regression: 14/14 tests passed

---

## Regression Test Results (Phase C Final)

```
 1. Health: PASS
 2. Auth: PASS
 3. Projects: PASS (1 project)
 4. Units: PASS (2 units)
 5. Stages (deprecated): PASS (5 stages)
 6. Steps (canonical): PASS (5 steps)
 7. Stages == Steps consistency: PASS (5 == 5)
 8. Timeline (project-timeline): PASS (timeline_id normalized, 5 steps)
 9. Timeline Full: PASS (timeline_demo_001, 5 steps)
10. Workflow Full: PASS (timeline_demo_001, 5 steps)
11. Clients: PASS (2 clients)
12. Documents: PASS (6 docs)
13. Dashboard: PASS (1 project)
14. Agent Stats: PASS (2 clients)
```

All 14 tests passed. No regressions detected.

---

*Last updated: February 2026*
