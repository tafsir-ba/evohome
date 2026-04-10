# Implementation Impact Map
## Pre-Phase C Control Panel

**Date**: January 2026  
**Purpose**: Practical control panel before code changes begin

---

## Collections Impact

| Collection | Action | Risk | Migration Script | Notes |
|------------|--------|------|------------------|-------|
| `project_units` | RENAME → `units` | LOW | Yes | 18 code references |
| `units` | KEEP (absorb data) | LOW | Receiver | 1 legacy reference |
| `project_timelines` | RENAME → `timelines` | LOW | Yes | 28 code references |
| `project_stages` | DELETE | LOW | Yes (merge) | 3 references, demo seed only |
| `timeline_steps` | KEEP | NONE | Field rename only | 34 references, canonical |
| `activities` | KEEP | NONE | None | Already canonical |
| `activity_recipients` | KEEP | NONE | None | Already canonical |
| `activity_replies` | KEEP | NONE | None | Already canonical |
| `documents` | KEEP | NONE | None | Already canonical |
| `vault_documents` | KEEP | NONE | None | Already canonical |
| `notifications` | KEEP | NONE | None | Already canonical |
| `team_members` | KEEP | NONE | None | Already canonical |
| `clients` | KEEP | NONE | None | Already canonical |
| `projects` | KEEP | NONE | None | Already canonical |
| `users` | KEEP | NONE | None | Already canonical |

**Summary**: 3 collections to rename/delete, 12 collections unchanged

---

## Field Renames Required

| Collection | Old Field | New Field | Document Count | Risk |
|------------|-----------|-----------|----------------|------|
| `timelines` | `project_timeline_id` | `timeline_id` | TBD | LOW |
| `timeline_steps` | `project_timeline_id` | `timeline_id` | TBD | LOW |

---

## Backend Endpoints Impact

### Routes Requiring Rename

| Current Route | New Route | Method | Risk | Breaking |
|---------------|-----------|--------|------|----------|
| `/projects/{id}/stages` | `/projects/{id}/steps` | POST | LOW | Yes* |
| `/projects/{id}/stages/{stage_id}` | `/projects/{id}/steps/{step_id}` | PUT | LOW | Yes* |
| `/projects/{id}/stages/{stage_id}` | `/projects/{id}/steps/{step_id}` | DELETE | LOW | Yes* |

*Breaking change mitigated by dual routes in Phase C

### Routes Requiring Collection Updates (Internal Only)

| Route | Current Collection | New Collection | Risk |
|-------|-------------------|----------------|------|
| `GET /projects/{id}/units` | `project_units` | `units` | LOW |
| `POST /projects/{id}/units` | `project_units` | `units` | LOW |
| `DELETE /projects/{id}/units/{id}` | `project_units` | `units` | LOW |
| `GET /projects/{id}/timeline` | `project_timelines` | `timelines` | LOW |
| `POST /timeline/create` | `project_timelines` | `timelines` | LOW |

### Routes Unchanged (Already Canonical)

- All `/activities/*` routes
- All `/documents/*` routes
- All `/vault/*` routes
- All `/notifications/*` routes
- All `/clients/*` routes
- All `/auth/*` routes
- All `/billing/*` routes

**Summary**: 3 routes to rename, ~8 routes need collection updates, ~50+ routes unchanged

---

## Frontend Pages/Components Impact

| Component | File | Changes Required | Risk |
|-----------|------|------------------|------|
| AgentTimeline | `AgentTimeline.js` | `/stages/` → `/steps/` | MEDIUM |
| BuyerTimeline | `BuyerTimeline.js` | Verify step_id usage | LOW |
| AgentProjects | `AgentProjects.js` | None (route unchanged) | NONE |
| AgentClients | `AgentClients.js` | None | NONE |
| AgentClientDetail | `AgentClientDetail.js` | None | NONE |
| AgentHomePage | `AgentHomePage.js` | Verify timeline response | LOW |
| AgentVault | `AgentVault.js` | None | NONE |
| AgentQuotes | `AgentQuotes.js` | None | NONE |
| AgentInvoices | `AgentInvoices.js` | None | NONE |
| AgentFeed | `AgentFeed.js` | None | NONE |

**Summary**: 2 components need updates, 8+ components unchanged

---

## Migration Scripts Required

| Script | Purpose | Collections | Reversible |
|--------|---------|-------------|------------|
| `migrate_units.js` | Merge `project_units` → `units` | 2 | Yes |
| `migrate_timelines.js` | Rename `project_timelines` → `timelines` | 1 | Yes |
| `normalize_timeline_id.js` | Rename field `project_timeline_id` → `timeline_id` | 2 | Yes |
| `migrate_stages.js` | Merge `project_stages` → `timeline_steps` | 2 | Yes |
| `verify_integrity.js` | Post-migration verification | All | N/A |
| `cleanup_deprecated.js` | Drop old collections (Phase F only) | 3 | No |

---

## Rollback Risk by Area

| Area | Risk Level | Rollback Method | Time to Rollback |
|------|------------|-----------------|------------------|
| Units collection | LOW | Restore from backup | < 1 hour |
| Timelines collection | LOW | Restore from backup | < 1 hour |
| Timeline ID field | LOW | Re-rename field | < 1 hour |
| Stages merge | LOW | Restore from backup | < 1 hour |
| API route renames | LOW | Redeploy old code | < 30 min |
| Frontend changes | LOW | Redeploy old build | < 30 min |

**Overall Rollback Risk**: LOW - All changes reversible with backups

---

## Conflict Checkpoints

During implementation, flag if ANY of these are found:

| Checkpoint | Expected | Action if Different |
|------------|----------|---------------------|
| `project_units` has data | Yes | Document count, verify merge |
| `project_stages` has data | Minimal (demo only) | Verify before delete |
| `timeline_id` already exists | Some docs | Skip rename for those |
| Frontend uses `project_timeline_id` | Possibly | Flag and fix |
| Frontend uses `stage_id` | Yes | Flag locations |
| Other collections use deprecated names | No | Flag immediately |

---

## Implementation Order (Strict)

```
Phase C: Compatibility Layer
├── C.1: Create db_compat.py helper module
├── C.2: Add dual read (old + new collections)
├── C.3: Write only to canonical collections
├── C.4: Add dual API routes (/stages AND /steps)
├── C.5: Verify all features still work
└── C.6: Deploy compatibility layer

Phase D: Data Migration
├── D.1: Backup all collections
├── D.2: Run migrate_units.js
├── D.3: Run migrate_timelines.js
├── D.4: Run normalize_timeline_id.js
├── D.5: Run migrate_stages.js
├── D.6: Run verify_integrity.js
└── D.7: Verify all features still work

Phase E: Code Normalization
├── E.1: Remove compatibility helpers (read from canonical only)
├── E.2: Update all collection references in code
├── E.3: Update Pydantic models
├── E.4: Update frontend API calls
├── E.5: Run full test suite
└── E.6: Deploy normalized code

Phase F: Cleanup (30 days later)
├── F.1: Remove deprecated routes
├── F.2: Drop old collections
├── F.3: Remove compatibility code
└── F.4: Final verification
```

---

## Go/No-Go Checklist

Before starting Phase C:
- [x] Canonical schema complete (Deliverable 1 + 1B)
- [x] Migration plan documented (Deliverable 2)
- [x] Code audit complete (Deliverable 3)
- [x] Implementation sequence defined (Deliverable 4)
- [x] Impact map created (this document)
- [ ] Database backup verified
- [ ] Rollback procedure tested

---

*Implementation Impact Map created: January 2026*
