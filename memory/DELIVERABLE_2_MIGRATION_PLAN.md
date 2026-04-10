# Deliverable 2: Migration Plan
## Collection Consolidation and ID Normalization

**Version**: 1.0  
**Date**: January 2026

---

## Migration Overview

| Migration | From | To | Risk | Complexity |
|-----------|------|-----|------|------------|
| Units | `project_units` | `units` | LOW | Simple rename |
| Stages | `project_stages` | `timeline_steps` | MEDIUM | Data merge |
| Timelines | `project_timelines` | `timelines` | LOW | Simple rename |
| Timeline ID | `project_timeline_id` | `timeline_id` | MEDIUM | Field rename |
| Stage/Step ID | `stage_id` (API) | `step_id` | MEDIUM | Route update |

---

## Migration 1: Units Collection

### Current State

```
db.units          → 1 usage (legacy, line 1260)
db.project_units  → 18 usages (current)
```

### Target State

```
db.units          → All unit operations
db.project_units  → DELETED
```

### Migration Steps

**Step 1: Create compatibility view** (no-risk)
```javascript
// In MongoDB, create alias or update code to read from both
```

**Step 2: Update code to write to `units`**
```python
# Change all db.project_units.insert_one → db.units.insert_one
```

**Step 3: Migrate existing data**
```javascript
// MongoDB migration script
db.project_units.find().forEach(function(doc) {
    db.units.insertOne(doc);
});
```

**Step 4: Update all read operations**
```python
# Change all db.project_units.find → db.units.find
```

**Step 5: Verify and delete old collection**
```javascript
db.project_units.drop();
```

### Files Affected

| File | Lines | Changes |
|------|-------|---------|
| `server.py` | 2567, 2612, 2633, 2669, 2725, 2743, 2744, 2760, 2771, 3291, 3373, 3915, 5350, 5554, 5578, 8455, 8456, 8934 | Replace `project_units` → `units` |

### Rollback Plan

Keep `project_units` data until migration verified. No data loss possible.

---

## Migration 2: Timeline Steps Collection

### Current State

```
db.project_stages  → 3 usages (legacy demo seed)
db.timeline_steps  → 34 usages (current)
```

### Target State

```
db.timeline_steps  → All step operations
db.project_stages  → DELETED
```

### Analysis

`project_stages` is only used in demo seed code (lines 3254, 8065, 8073). The actual step data is already in `timeline_steps`. This is a simple cleanup.

### Migration Steps

**Step 1: Audit `project_stages` data**
```javascript
// Check if any real data exists
db.project_stages.countDocuments()
```

**Step 2: Migrate any real data to `timeline_steps`**
```javascript
// If data exists, map to timeline_steps schema
db.project_stages.find().forEach(function(stage) {
    // Transform stage → step format
    var step = {
        step_id: stage.stage_id || "step_" + new ObjectId().toString().substring(0,12),
        timeline_id: stage.project_timeline_id,
        project_id: stage.project_id,
        name: stage.name,
        description: stage.description,
        order: stage.order,
        status: stage.status || "pending",
        created_at: stage.created_at
    };
    db.timeline_steps.insertOne(step);
});
```

**Step 3: Update demo seed code**
```python
# Remove all db.project_stages references in seed function
# Use only db.timeline_steps
```

**Step 4: Delete old collection**
```javascript
db.project_stages.drop();
```

### Files Affected

| File | Lines | Changes |
|------|-------|---------|
| `server.py` | 3254 | Remove or redirect |
| `server.py` | 8065, 8073 | Update seed to use `timeline_steps` |

---

## Migration 3: Timelines Collection

### Current State

```
db.project_timelines  → 28 usages
```

### Target State

```
db.timelines          → All timeline operations
db.project_timelines  → DELETED (or aliased)
```

### Migration Steps

**Step 1: Create new collection with rename**
```javascript
db.project_timelines.renameCollection("timelines");
```

**Step 2: Update all code references**
```python
# Global replace: db.project_timelines → db.timelines
```

### Files Affected

| File | Lines | Changes |
|------|-------|---------|
| `server.py` | 28 occurrences | Replace `project_timelines` → `timelines` |

---

## Migration 4: Timeline ID Field

### Current State

Two field names used interchangeably:
- `timeline_id`
- `project_timeline_id`

Code has defensive patterns like:
```python
timeline_id = timeline.get('timeline_id') or timeline.get('project_timeline_id')
```

### Target State

Single field name: `timeline_id`

### Migration Steps

**Step 1: Update documents in database**
```javascript
// Rename field in all documents
db.timelines.updateMany(
    { project_timeline_id: { $exists: true } },
    { $rename: { "project_timeline_id": "timeline_id" } }
);

db.timeline_steps.updateMany(
    { project_timeline_id: { $exists: true } },
    { $rename: { "project_timeline_id": "timeline_id" } }
);
```

**Step 2: Update Pydantic models**
```python
class ProjectTimeline(BaseModel):
    timeline_id: str  # Remove project_timeline_id
```

**Step 3: Update all code references**
```python
# Remove all .get('timeline_id') or .get('project_timeline_id') patterns
# Use only timeline_id
```

### Files Affected

| File | Lines | Changes |
|------|-------|---------|
| `server.py` | 1286, 4932, 4934, 5008, 5017, 5024, 5079, 5080, 5158, 5159, 5419, 5423, 5488, 5491, 6516, 6713, 6907, 6966, 7040, 7041 | Normalize to `timeline_id` |

---

## Migration 5: Stage ID → Step ID

### Current State

API routes use `stage_id`:
```
PUT  /projects/{project_id}/stages/{stage_id}
DELETE /projects/{project_id}/stages/{stage_id}
```

Database uses `step_id`:
```python
step = await db.timeline_steps.find_one({"step_id": stage_id})
```

### Target State

Consistent `step_id` everywhere, with backward-compatible routes.

### Migration Steps

**Step 1: Add new routes (parallel)**
```python
@api_router.put("/projects/{project_id}/steps/{step_id}")  # New
@api_router.put("/projects/{project_id}/stages/{stage_id}")  # Deprecated
```

**Step 2: Update frontend to use new routes**
```javascript
// Change /stages/ → /steps/ in API calls
```

**Step 3: Add deprecation warnings to old routes**
```python
@api_router.put("/projects/{project_id}/stages/{stage_id}")
async def update_stage_deprecated(...):
    logger.warning("Deprecated: Use /steps/{step_id} instead")
    return await update_step(...)
```

**Step 4: Remove old routes after frontend migrated**

### Files Affected

**Backend:**
| File | Lines | Changes |
|------|-------|---------|
| `server.py` | 5065, 5144 | Add parallel routes, deprecate old |

**Frontend:**
| File | Changes |
|------|---------|
| `AgentTimeline.js` | Update API calls |
| `BuyerTimeline.js` | Update API calls |

---

## Migration Sequence

### Phase A: Define Model (Week 1)
- [x] Document canonical schema
- [x] Define naming conventions
- [x] Identify deprecated structures

### Phase B: Pick Winners (Week 1)
- `units` wins over `project_units`
- `timeline_steps` wins over `project_stages`
- `timelines` wins over `project_timelines`
- `timeline_id` wins over `project_timeline_id`
- `step_id` wins over `stage_id`

### Phase C: Compatibility Layer (Week 2)
- Add helper functions that read from both old and new
- Ensure writes go to canonical collection only

### Phase D: Migrate Data (Week 2)
```javascript
// Run in MongoDB Atlas
// Migration script for all collections
```

### Phase E: Update Code (Week 3)
- Update backend routes
- Update frontend API calls
- Run full regression

### Phase F: Remove Deprecated (Week 4)
- Remove old collections
- Remove compatibility code
- Final cleanup

---

## Risk Assessment

| Migration | Data Loss Risk | Downtime Risk | Rollback Difficulty |
|-----------|----------------|---------------|---------------------|
| Units rename | NONE | NONE | Easy |
| Stages merge | LOW | NONE | Medium |
| Timelines rename | NONE | NONE | Easy |
| ID field rename | NONE | NONE | Easy |
| Route rename | NONE | NONE | Easy (parallel routes) |

---

## Testing Checklist

For each migration:

- [ ] Backup database before migration
- [ ] Run migration on staging first
- [ ] Verify data integrity after migration
- [ ] Run full API test suite
- [ ] Run frontend E2E tests
- [ ] Monitor for errors 24h post-migration
- [ ] Keep old structure for 1 week before deletion

---

*Migration plan approved: January 2026*
