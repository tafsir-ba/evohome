# Deliverable 3: Code Audit
## Backend Routes and Frontend Components Affected

**Version**: 1.0  
**Date**: January 2026

---

## Backend Routes Audit

### Routes Using `project_units` (TO MIGRATE)

| Route | Method | Line | Collection | Action Required |
|-------|--------|------|------------|-----------------|
| `/projects/{project_id}/units` | GET | 2661 | `project_units` | → `units` |
| `/projects/{project_id}/units` | POST | 2699 | `project_units` | → `units` |
| `/projects/{project_id}/units/{unit_id}` | DELETE | 2755 | `project_units` | → `units` |

### Routes Using `project_stages` (TO REMOVE)

| Route | Method | Line | Collection | Action Required |
|-------|--------|------|------------|-----------------|
| Internal query only | - | 3254 | `project_stages` | Remove usage |

### Routes Using `timeline_steps` (CANONICAL - Keep)

| Route | Method | Line | Notes |
|-------|--------|------|-------|
| `/projects/{project_id}/stages` | POST | 4983 | Rename to `/steps` |
| `/projects/{project_id}/stages/{stage_id}` | PUT | 5065 | Rename to `/steps/{step_id}` |
| `/projects/{project_id}/stages/{stage_id}` | DELETE | 5144 | Rename to `/steps/{step_id}` |
| `/timeline/steps/{step_id}` | PATCH | 7023 | Already correct |
| `/timeline/steps/{step_id}` | DELETE | 7176 | Already correct |
| `/timeline/steps/{step_id}/documents` | POST | 7214 | Already correct |
| `/timeline/steps/{step_id}/documents/{activity_id}` | DELETE | 7272 | Already correct |
| `/timeline/steps/{step_id}/notes` | POST | 7298 | Already correct |

### Routes Using `project_timelines` (TO RENAME)

| Route | Method | Line | Action Required |
|-------|--------|------|-----------------|
| `/projects/{project_id}/timeline` | GET | 5391 | Collection → `timelines` |
| `/timeline/create` | POST | 6383 | Collection → `timelines` |
| `/timeline/extract` | POST | 6430 | Collection → `timelines` |
| Internal queries | - | Various | Collection → `timelines` |

---

## Backend Code Changes Summary

### server.py Changes

| Section | Lines | Change Type | Risk |
|---------|-------|-------------|------|
| Units queries | 2567-2771 | Collection rename | LOW |
| Units in client lookups | 3291, 3373, 3915 | Collection rename | LOW |
| Units in dashboard | 5350, 5554, 5578 | Collection rename | LOW |
| Units in demo seed | 8455-8456, 8934 | Collection rename | LOW |
| Project stages | 3254, 8065, 8073 | Remove/redirect | LOW |
| Timeline steps | 34 locations | Field rename | MEDIUM |
| Project timelines | 28 locations | Collection rename | LOW |
| Timeline ID fields | 20 locations | Field rename | MEDIUM |

### Pydantic Models to Update

| Model | Line | Changes |
|-------|------|---------|
| `ProjectTimeline` | 574 | Remove `project_timeline_id`, ensure `timeline_id` |
| `TimelineStep` | 552 | Ensure `step_id`, remove `stage_id` references |
| `ProjectStage` | 440 | DEPRECATE - use `TimelineStep` |
| `ProjectStageCreate` | 420 | DEPRECATE - use `TimelineStepCreate` |
| `ProjectStageUpdate` | 428 | DEPRECATE - use `TimelineStepUpdate` |

---

## Frontend Components Audit

### Components Using Units

| Component | File | API Calls | Changes Required |
|-----------|------|-----------|------------------|
| AgentProjects | `AgentProjects.js` | `/projects/{id}/units` | None (route stays same) |
| AgentClientDetail | `AgentClientDetail.js` | `/projects/{id}/units` | None |
| AgentClients | `AgentClients.js` | `/projects/{id}/units` | None |

### Components Using Timeline/Stages

| Component | File | API Calls | Changes Required |
|-----------|------|-----------|------------------|
| AgentTimeline | `AgentTimeline.js` | `/projects/{id}/stages`, `/timeline/*` | Update to `/steps` |
| BuyerTimeline | `BuyerTimeline.js` | `/timeline/*` | Check step_id usage |
| AgentHomePage | `AgentHomePage.js` | `/projects/{id}/context` | Check timeline response |

### Frontend Type Patterns

**Current inconsistencies found:**

```javascript
// Uses snake_case (correct)
project.project_id
client.client_id
step.step_id

// No camelCase found in API data - good
```

### Frontend Files to Update

| File | Lines | Changes |
|------|-------|---------|
| `AgentTimeline.js` | ~50 | `/stages/` → `/steps/` in API calls |
| `AgentTimeline.js` | ~20 | `stage_id` → `step_id` in variables |
| `BuyerTimeline.js` | ~10 | Verify step_id usage |

---

## Migration Risk Assessment

### HIGH RISK Areas

| Area | Risk | Mitigation |
|------|------|------------|
| Timeline ID field rename | Data loss if field missing | Add fallback during migration |
| Stage → Step route change | Frontend breaks if not synced | Deploy backend with both routes first |

### MEDIUM RISK Areas

| Area | Risk | Mitigation |
|------|------|------------|
| Collection renames | Queries fail if partial | Use compatibility layer |
| Demo seed changes | Demo data breaks | Test seed after each change |

### LOW RISK Areas

| Area | Risk | Mitigation |
|------|------|------------|
| Units collection rename | Just a name change | Simple search/replace |
| Removing project_stages | Barely used | Verify no real data first |

---

## Backward Compatibility Plan

### Phase 1: Dual Support (2 weeks)

**Backend changes:**
```python
# Read from both collections during migration
async def get_units(project_id):
    # Try new collection first
    units = await db.units.find({"project_id": project_id}).to_list(500)
    if not units:
        # Fallback to old collection
        units = await db.project_units.find({"project_id": project_id}).to_list(500)
    return units

# Write to new collection only
async def create_unit(unit_data):
    return await db.units.insert_one(unit_data)
```

**API routes:**
```python
# Keep old routes, add new ones
@api_router.put("/projects/{project_id}/stages/{stage_id}")  # Old - deprecated
@api_router.put("/projects/{project_id}/steps/{step_id}")    # New - preferred
```

### Phase 2: Migration Window (1 week)

- Run data migration scripts
- Verify data integrity
- Monitor error rates

### Phase 3: Deprecation (2 weeks)

- Add deprecation warnings to old routes
- Log usage of deprecated endpoints
- Notify any external integrations (if any)

### Phase 4: Removal (after 30 days)

- Remove old collections
- Remove old routes
- Remove compatibility code
- Clean up unused models

---

## Testing Requirements

### Unit Tests to Add/Update

| Test | Purpose |
|------|---------|
| `test_units_crud` | Verify units operations work with new collection |
| `test_timeline_steps_crud` | Verify step operations |
| `test_timeline_id_field` | Verify timeline_id is used consistently |
| `test_backward_compat` | Verify old routes still work during migration |

### Integration Tests

| Test | Purpose |
|------|---------|
| `test_project_with_units` | Create project, add units, assign to clients |
| `test_timeline_flow` | Create timeline, add steps, complete steps |
| `test_full_client_journey` | Client creation through to document approval |

### E2E Tests

| Flow | Components |
|------|------------|
| Agent creates project with units | AgentProjects |
| Agent creates timeline | AgentTimeline |
| Buyer views timeline | BuyerTimeline |
| Agent manages documents | AgentQuotes, AgentInvoices |

---

## Rollback Procedures

### If Migration Fails

1. **Stop writes** to new collections
2. **Restore** old collection names if renamed
3. **Revert** code to use old collections
4. **Investigate** cause of failure
5. **Re-plan** migration with fixes

### Collection Backup Commands

```javascript
// Before migration
db.project_units.aggregate([{ $out: "project_units_backup" }]);
db.project_timelines.aggregate([{ $out: "project_timelines_backup" }]);
db.timeline_steps.aggregate([{ $out: "timeline_steps_backup" }]);

// After verified success (30 days later)
db.project_units_backup.drop();
db.project_timelines_backup.drop();
db.timeline_steps_backup.drop();
```

---

## Affected Endpoints Summary

### Total Backend Routes Affected: 23

| Category | Count | Risk |
|----------|-------|------|
| Units routes | 3 | LOW |
| Timeline routes | 8 | MEDIUM |
| Stage routes (to rename) | 3 | MEDIUM |
| Internal queries | 9 | LOW |

### Total Frontend Components Affected: 5

| Category | Count | Risk |
|----------|-------|------|
| Timeline components | 2 | MEDIUM |
| Project components | 2 | LOW |
| Dashboard | 1 | LOW |

---

*Code audit completed: January 2026*
