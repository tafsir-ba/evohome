# Phase C: Conflict Report
## Live Code vs Canonical Schema Discrepancies

**Date**: January 2026  
**Status**: IN PROGRESS

---

## Phase C Progress

| Task | Status | Notes |
|------|--------|-------|
| Create db_compat.py | ✅ Complete | Compatibility helper module |
| Initialize in server.py | ✅ Complete | `init_compat(db)` called |
| Add dual /steps routes | ✅ Complete | Both /stages and /steps work |
| Update GET /units | ✅ Complete | Uses canonical + fallback |
| Update POST /units | ✅ Complete | Writes to canonical |
| Update DELETE /units | ✅ Complete | Deletes from both |
| Regression test | ✅ Passed | All endpoints working |

---

## Conflicts Found and Logged

### 1. Units Collection

| Location | Line | Current Code | Canonical | Status |
|----------|------|--------------|-----------|--------|
| get_units | 2673 | `db.project_units` → `db.units` | `db.units` | ✅ Fixed |
| create_unit | 2729 | `db.project_units` → `db.units` | `db.units` | ✅ Fixed |
| delete_unit | 2764 | `db.project_units` → `db.units` | `db.units` | ✅ Fixed |

### 2. API Routes

| Route | Status | Notes |
|-------|--------|-------|
| `GET /projects/{id}/stages` | DEPRECATED | Works, delegates to impl |
| `POST /projects/{id}/stages` | DEPRECATED | Works, delegates to impl |
| `PUT /projects/{id}/stages/{id}` | DEPRECATED | Works, delegates to impl |
| `DELETE /projects/{id}/stages/{id}` | DEPRECATED | Works, delegates to impl |
| `GET /projects/{id}/steps` | ✅ CANONICAL | New route |
| `POST /projects/{id}/steps` | ✅ CANONICAL | New route |
| `PUT /projects/{id}/steps/{id}` | ✅ CANONICAL | New route |
| `DELETE /projects/{id}/steps/{id}` | ✅ CANONICAL | New route |

---

## Remaining Phase C Tasks

| Task | Status |
|------|--------|
| Update timelines collection references | 🔲 Pending |
| Update timeline_id field normalization | 🔲 Pending |
| Frontend notification about new routes | 🔲 Pending |

---

## Regression Test Results

```
✅ Health: OK
✅ Projects: 1 found
✅ Units: 2 found  
✅ Steps (canonical): 1 found
✅ Stages (deprecated): 1 found
✅ Clients: 2 found
✅ Documents: 6 found
```

All existing features working.

---

*Last updated: January 2026*
