# Deliverable 4: Phased Implementation Sequence
## Data Model Normalization Execution Plan

**Version**: 1.0  
**Date**: January 2026  
**Duration**: 4-6 weeks

---

## Phase Overview

| Phase | Name | Duration | Dependencies |
|-------|------|----------|--------------|
| A | Define Model | Week 1 | None |
| B | Pick Winners | Week 1 | Phase A |
| C | Compatibility Layer | Week 2 | Phase B |
| D | Migrate Data | Week 2-3 | Phase C |
| E | Update Code | Week 3-4 | Phase D |
| F | Remove Deprecated | Week 5-6 | Phase E + 30 days |

---

## Phase A: Define Canonical Model

**Duration**: 3-5 days  
**Status**: ✅ COMPLETE (Deliverable 1)

### Deliverables
- [x] Canonical schema document
- [x] Entity definitions
- [x] Naming conventions
- [x] Relationship diagram
- [x] Vocabulary standard

### Exit Criteria
- Schema document reviewed and approved
- All stakeholders agree on naming conventions
- Document becomes authoritative reference

---

## Phase B: Pick Winning Collections and Names

**Duration**: 1-2 days  
**Status**: ✅ COMPLETE

### Decisions Made

| Conflict | Winner | Loser | Rationale |
|----------|--------|-------|-----------|
| `units` vs `project_units` | `units` | `project_units` | Simpler, more usages |
| `timeline_steps` vs `project_stages` | `timeline_steps` | `project_stages` | Already primary, better name |
| `timelines` vs `project_timelines` | `timelines` | `project_timelines` | Consistent with other collections |
| `timeline_id` vs `project_timeline_id` | `timeline_id` | `project_timeline_id` | Shorter, consistent |
| `step_id` vs `stage_id` | `step_id` | `stage_id` | Matches collection name |

### Exit Criteria
- [x] All naming conflicts resolved
- [x] Winner/loser documented
- [x] Migration path clear for each

---

## Phase C: Add Compatibility Layer

**Duration**: 3-5 days  
**Status**: 🔲 NOT STARTED

### Task C.1: Create Database Helper Functions

```python
# /app/backend/core/db_compat.py

async def get_units(project_id: str):
    """Read units with backward compatibility."""
    # Primary: new collection
    units = await db.units.find({"project_id": project_id}).to_list(500)
    if units:
        return units
    # Fallback: old collection (during migration only)
    return await db.project_units.find({"project_id": project_id}).to_list(500)

async def get_timeline(project_id: str):
    """Read timeline with backward compatibility."""
    # Primary: new collection
    timeline = await db.timelines.find_one({"project_id": project_id})
    if timeline:
        return normalize_timeline_id(timeline)
    # Fallback: old collection
    timeline = await db.project_timelines.find_one({"project_id": project_id})
    if timeline:
        return normalize_timeline_id(timeline)
    return None

def normalize_timeline_id(timeline: dict) -> dict:
    """Ensure timeline uses timeline_id field."""
    if 'project_timeline_id' in timeline and 'timeline_id' not in timeline:
        timeline['timeline_id'] = timeline.pop('project_timeline_id')
    return timeline
```

### Task C.2: Create Dual Routes for API Endpoints

```python
# Add new routes alongside old ones
@api_router.post("/projects/{project_id}/steps")  # NEW
async def create_step(project_id: str, data: TimelineStepCreate, ...):
    return await _create_step_impl(project_id, data, ...)

@api_router.post("/projects/{project_id}/stages")  # OLD - deprecated
async def create_stage_deprecated(project_id: str, data: ProjectStageCreate, ...):
    logger.warning(f"Deprecated route /stages used. Use /steps instead.")
    return await _create_step_impl(project_id, data, ...)
```

### Task C.3: Update Write Operations

All writes go to new/canonical collections only:
- `db.units.insert_one()` (not `project_units`)
- `db.timelines.insert_one()` (not `project_timelines`)
- `db.timeline_steps.insert_one()` (not `project_stages`)

### Exit Criteria
- [ ] Compatibility helpers created
- [ ] All reads work from either collection
- [ ] All writes go to canonical collection
- [ ] Dual routes deployed
- [ ] No breaking changes for existing clients

---

## Phase D: Migrate Existing Data

**Duration**: 3-5 days  
**Status**: 🔲 NOT STARTED

### Task D.1: Backup All Collections

```javascript
// Run in MongoDB Atlas console

// Backup before any changes
db.project_units.aggregate([{ $out: "project_units_backup_20260115" }]);
db.project_timelines.aggregate([{ $out: "project_timelines_backup_20260115" }]);
db.project_stages.aggregate([{ $out: "project_stages_backup_20260115" }]);
db.timeline_steps.aggregate([{ $out: "timeline_steps_backup_20260115" }]);
```

### Task D.2: Migrate Units Collection

```javascript
// Migrate project_units → units
db.project_units.find().forEach(function(doc) {
    // Check if already exists in units
    var existing = db.units.findOne({ unit_id: doc.unit_id });
    if (!existing) {
        db.units.insertOne(doc);
    }
});

// Verify count
print("project_units count: " + db.project_units.countDocuments());
print("units count: " + db.units.countDocuments());
```

### Task D.3: Migrate Timelines Collection

```javascript
// Migrate project_timelines → timelines with field rename
db.project_timelines.find().forEach(function(doc) {
    // Normalize timeline_id
    if (doc.project_timeline_id && !doc.timeline_id) {
        doc.timeline_id = doc.project_timeline_id;
        delete doc.project_timeline_id;
    }
    
    // Check if already exists
    var existing = db.timelines.findOne({ timeline_id: doc.timeline_id });
    if (!existing) {
        db.timelines.insertOne(doc);
    }
});

// Verify
print("project_timelines count: " + db.project_timelines.countDocuments());
print("timelines count: " + db.timelines.countDocuments());
```

### Task D.4: Normalize Timeline Steps

```javascript
// Rename project_timeline_id → timeline_id in timeline_steps
db.timeline_steps.updateMany(
    { project_timeline_id: { $exists: true }, timeline_id: { $exists: false } },
    [{ $set: { timeline_id: "$project_timeline_id" } }]
);

db.timeline_steps.updateMany(
    { project_timeline_id: { $exists: true } },
    { $unset: { project_timeline_id: "" } }
);

// Verify
print("Steps with timeline_id: " + db.timeline_steps.countDocuments({ timeline_id: { $exists: true } }));
print("Steps with project_timeline_id: " + db.timeline_steps.countDocuments({ project_timeline_id: { $exists: true } }));
```

### Task D.5: Migrate Project Stages (if any data exists)

```javascript
// Check if project_stages has any real data
var stageCount = db.project_stages.countDocuments();
print("project_stages count: " + stageCount);

if (stageCount > 0) {
    db.project_stages.find().forEach(function(stage) {
        // Transform to timeline_step format
        var step = {
            step_id: stage.stage_id || ("step_" + new ObjectId().toString().substring(0,12)),
            timeline_id: stage.project_timeline_id || stage.timeline_id,
            project_id: stage.project_id,
            agent_id: stage.agent_id,
            name: stage.name,
            description: stage.description || "",
            order: stage.order || 0,
            status: stage.status || "pending",
            created_at: stage.created_at || new Date().toISOString()
        };
        
        // Check if already migrated
        var existing = db.timeline_steps.findOne({ step_id: step.step_id });
        if (!existing) {
            db.timeline_steps.insertOne(step);
        }
    });
}
```

### Task D.6: Verify Data Integrity

```javascript
// Post-migration verification script

// 1. Units
var unitCheck = {
    old: db.project_units.countDocuments(),
    new: db.units.countDocuments(),
    match: db.project_units.countDocuments() <= db.units.countDocuments()
};
print("Units migration: " + (unitCheck.match ? "PASS" : "FAIL"));

// 2. Timelines
var timelineCheck = {
    old: db.project_timelines.countDocuments(),
    new: db.timelines.countDocuments(),
    match: db.project_timelines.countDocuments() <= db.timelines.countDocuments()
};
print("Timelines migration: " + (timelineCheck.match ? "PASS" : "FAIL"));

// 3. Timeline IDs normalized
var idCheck = {
    oldField: db.timeline_steps.countDocuments({ project_timeline_id: { $exists: true } }),
    newField: db.timeline_steps.countDocuments({ timeline_id: { $exists: true } })
};
print("Timeline ID normalization: " + (idCheck.oldField === 0 ? "PASS" : "FAIL - " + idCheck.oldField + " still have old field"));

// 4. Stages migrated
var stageCheck = {
    old: db.project_stages.countDocuments(),
    migrated: db.timeline_steps.countDocuments()
};
print("Stages migration: project_stages=" + stageCheck.old);
```

### Exit Criteria
- [ ] All backups created
- [ ] Units migrated and verified
- [ ] Timelines migrated and verified
- [ ] Timeline IDs normalized
- [ ] Project stages migrated (if any)
- [ ] Data integrity verified
- [ ] Zero data loss confirmed

---

## Phase E: Update Endpoints and Frontend

**Duration**: 5-7 days  
**Status**: 🔲 NOT STARTED

### Task E.1: Update Backend to Use Canonical Collections

```python
# Global search and replace in server.py

# Step 1: Collection names
db.project_units → db.units
db.project_timelines → db.timelines
db.project_stages → db.timeline_steps (or remove)

# Step 2: Field names
.get('timeline_id') or .get('project_timeline_id') → .get('timeline_id')
"project_timeline_id": → "timeline_id":
```

### Task E.2: Update Pydantic Models

```python
# Remove deprecated models
- ProjectStage
- ProjectStageCreate  
- ProjectStageUpdate

# Update timeline models
class ProjectTimeline(BaseModel):
    timeline_id: str  # ONLY this, not project_timeline_id
    project_id: str
    # ...

class TimelineStep(BaseModel):
    step_id: str  # ONLY this, not stage_id
    timeline_id: str  # ONLY this, not project_timeline_id
    # ...
```

### Task E.3: Update API Route Names

```python
# Rename stage routes to step routes
@api_router.post("/projects/{project_id}/stages")  # REMOVE
@api_router.post("/projects/{project_id}/steps")   # KEEP

@api_router.put("/projects/{project_id}/stages/{stage_id}")   # REMOVE
@api_router.put("/projects/{project_id}/steps/{step_id}")     # KEEP

@api_router.delete("/projects/{project_id}/stages/{stage_id}")  # REMOVE
@api_router.delete("/projects/{project_id}/steps/{step_id}")    # KEEP
```

### Task E.4: Update Frontend API Calls

```javascript
// AgentTimeline.js
// Replace all occurrences:
/projects/${projectId}/stages → /projects/${projectId}/steps
/stages/${stageId} → /steps/${stepId}

// Variable names (optional but recommended)
stageId → stepId
stage → step
stages → steps
```

### Task E.5: Update Frontend Data Handling

```javascript
// Ensure frontend uses normalized field names
// In response handling:
const timelineId = timeline.timeline_id;  // Not project_timeline_id
const stepId = step.step_id;              // Not stage_id
```

### Task E.6: Run Full Regression Suite

- [ ] All backend unit tests pass
- [ ] All integration tests pass
- [ ] Frontend E2E tests pass
- [ ] Manual testing of critical flows
- [ ] Performance benchmarks unchanged

### Exit Criteria
- [ ] All backend code uses canonical collections
- [ ] All Pydantic models updated
- [ ] All routes renamed
- [ ] Frontend updated
- [ ] All tests pass
- [ ] No regressions

---

## Phase F: Remove Deprecated Structures

**Duration**: After 30-day observation period  
**Status**: 🔲 NOT STARTED

### Task F.1: Remove Compatibility Code

```python
# Delete from server.py
- get_timeline_id_compat()
- read_from_both_collections()
- Any fallback patterns
```

### Task F.2: Remove Old Routes

```python
# Delete deprecated routes
@api_router.post("/projects/{project_id}/stages")  # DELETE
@api_router.put("/projects/{project_id}/stages/{stage_id}")  # DELETE
@api_router.delete("/projects/{project_id}/stages/{stage_id}")  # DELETE
```

### Task F.3: Remove Deprecated Pydantic Models

```python
# Delete from server.py
class ProjectStage(BaseModel): ...      # DELETE
class ProjectStageCreate(BaseModel): ...  # DELETE
class ProjectStageUpdate(BaseModel): ...  # DELETE
```

### Task F.4: Drop Old Collections

```javascript
// Run in MongoDB Atlas console AFTER verification

// Final verification before drop
print("project_units: " + db.project_units.countDocuments() + " documents");
print("project_timelines: " + db.project_timelines.countDocuments() + " documents");
print("project_stages: " + db.project_stages.countDocuments() + " documents");

// Drop old collections (IRREVERSIBLE)
db.project_units.drop();
db.project_timelines.drop();
db.project_stages.drop();

// Drop backups after 60 days
// db.project_units_backup_20260115.drop();
// etc.
```

### Task F.5: Update Documentation

- [ ] Remove references to old collection names
- [ ] Remove references to old route names
- [ ] Update API documentation
- [ ] Update developer onboarding docs

### Exit Criteria
- [ ] No compatibility code remains
- [ ] No deprecated routes exist
- [ ] No deprecated models exist
- [ ] Old collections dropped
- [ ] Documentation updated
- [ ] Clean codebase

---

## Timeline Summary

```
Week 1:  [A] Define Model ✓   [B] Pick Winners ✓
Week 2:  [C] Compatibility Layer
Week 3:  [D] Migrate Data
Week 4:  [E] Update Code
Week 5:  (Observation period)
Week 6:  [F] Remove Deprecated
```

---

## Checkpoints

### Checkpoint 1: After Phase C
- [ ] Dual support working
- [ ] No breaking changes
- [ ] Ready to migrate data

### Checkpoint 2: After Phase D
- [ ] Data migrated
- [ ] Integrity verified
- [ ] Zero data loss

### Checkpoint 3: After Phase E
- [ ] Code fully updated
- [ ] Tests passing
- [ ] Frontend working

### Checkpoint 4: After Phase F
- [ ] Cleanup complete
- [ ] Codebase clean
- [ ] SSOT achieved

---

## Success Criteria

**The migration is complete when:**

1. ✅ One document defines all entities (Deliverable 1)
2. ✅ Each entity has ONE collection (no duplicates)
3. ✅ Each field has ONE name (no aliases)
4. ✅ API uses consistent vocabulary
5. ✅ Frontend uses consistent vocabulary
6. ✅ No deprecated structures remain
7. ✅ All tests pass
8. ✅ No data loss

---

*Implementation sequence approved: January 2026*
