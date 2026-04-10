# SSOT (Single Source of Truth) Audit Report
## Evohome CMP - Data Consistency Analysis

**Audit Date**: January 2026  
**Severity**: HIGH - Multiple data isolation issues found

---

## Executive Summary

The codebase has **significant inconsistencies** in data isolation (`is_demo` filtering) and naming conventions that can cause:
- Demo data appearing to production users
- Production data appearing to demo users
- "Not found" errors when data exists but with different `is_demo` flag
- Confusion between similar collections (units vs project_units)

---

## 1. is_demo Filter Inconsistency

### Current State (CRITICAL)

| Collection | Total Queries | Missing is_demo | % Inconsistent |
|------------|---------------|-----------------|----------------|
| users | 88 | 85 | 97% |
| clients | 86 | 84 | 98% |
| projects | 59 | 58 | 98% |
| documents | 68 | 67 | 99% |
| activities | 25 | 24 | 96% |
| timeline_steps | 33 | 32 | 97% |
| project_timelines | 27 | 25 | 93% |
| vault_documents | 10 | 10 | 100% |
| team_members | 14 | 13 | 93% |
| notifications | 6 | 5 | 83% |

### Root Cause
The `is_demo` flag is used inconsistently:
- Some endpoints filter by `is_demo`
- Most endpoints do NOT filter by `is_demo`
- This causes cross-contamination between demo and production data

### Recommendation
**Option A: Remove is_demo entirely**
- Simpler architecture
- Separate demo environment with separate database
- No risk of data leakage

**Option B: Consistent is_demo filtering (Complex)**
- Add `is_demo` to EVERY query
- Create middleware/helper to auto-inject `is_demo`
- High risk of missing cases

**Recommended: Option A** - Use a separate demo database/environment

---

## 2. Collection Naming Inconsistencies

### Duplicate Collections for Same Data

| Issue | Collections | Impact |
|-------|-------------|--------|
| Units | `db.units` AND `db.project_units` | Data split between two collections |
| Stages | `db.project_stages` AND `db.timeline_steps` | Confusion about source of truth |

### Evidence

```python
# Units - used in TWO different collections
db.units.find(...)           # Line 1210
db.project_units.find(...)   # Line 2517, 2560, 2581, 2616, 2671

# Stages - used in TWO different collections  
db.project_stages.find(...)  # Line 3200, 7990
db.timeline_steps.find(...)  # Primary collection (33 usages)
```

### Recommendation
1. Migrate all `db.units` → `db.project_units`
2. Migrate all `db.project_stages` → `db.timeline_steps`
3. Remove deprecated collections

---

## 3. ID Field Naming Inconsistencies

### Timeline IDs

The codebase uses TWO different field names for timeline IDs:

```python
timeline_id          # 156 usages
project_timeline_id  # Mixed usage
```

### Evidence (Confusion in code)
```python
# Line 4878, 4963, 5365, 5434
timeline_id = timeline.get('timeline_id') or timeline.get('project_timeline_id')
```

This "OR" pattern shows the code itself is confused about which field to use.

### Stage/Step IDs

The API uses `stage_id` but database uses `step_id`:

```python
# API endpoints use stage_id
@api_router.put("/projects/{project_id}/stages/{stage_id}")
@api_router.delete("/projects/{project_id}/stages/{stage_id}")

# But queries use step_id
step = await db.timeline_steps.find_one({"step_id": stage_id})

# Returns stage_id to frontend
return {"stage_id": step.get('step_id'), ...}
```

### Recommendation
1. Standardize on `step_id` everywhere (database and API)
2. OR standardize on `stage_id` everywhere
3. Add migration to rename fields

---

## 4. API Response Format Inconsistencies

### Pydantic Models vs Raw Dicts

Some endpoints use Pydantic response models:
```python
@api_router.get("/clients/{client_id}", response_model=Client)
@api_router.post("/projects", response_model=Project)
```

Others return raw dicts:
```python
return {"message": "Success", "data": {...}}
return await db.documents.find_one(query, {"_id": 0})
```

### Recommendation
1. Define Pydantic response models for ALL endpoints
2. Ensures consistent field names
3. Auto-validation of responses

---

## 5. Queries Without Owner Check

### Security Issue
Some queries only filter by resource ID, not owner:

```python
# Missing agent_id check - any agent could access
project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})

# Correct pattern - includes ownership check
project = await db.projects.find_one({
    "project_id": project_id, 
    "agent_id": user['user_id'],
    "is_demo": is_demo
}, {"_id": 0})
```

### High-Risk Endpoints (Need Review)
- `/projects/{project_id}` (GET)
- `/clients/{client_id}` (GET) 
- `/documents/{document_id}` (GET)
- Team member operations
- Vault operations

---

## 6. Recommended Fix Priority

### P0 - Critical (Before Production)

1. **Fix project listing** ✅ DONE
   - Added `is_demo` filter to `/api/projects`

2. **Fix stage creation** ✅ DONE
   - Added `is_demo` filter to `/api/projects/{id}/stages`

3. **Decision: Remove or enforce is_demo**
   - Current state is dangerous
   - Pick one approach and implement consistently

### P1 - High Priority (Week 1)

4. **Consolidate collections**
   - Migrate `db.units` → `db.project_units`
   - Migrate `db.project_stages` → `db.timeline_steps`

5. **Standardize ID fields**
   - Choose `timeline_id` OR `project_timeline_id`
   - Choose `step_id` OR `stage_id`

6. **Add owner checks to all queries**
   - Every resource query must include `agent_id`

### P2 - Medium Priority (Week 2-3)

7. **Pydantic response models**
   - Define models for all endpoints
   - Use `response_model=` parameter

8. **Create query helper**
   ```python
   def build_query(user, **filters):
       return {
           **filters,
           "agent_id": user['user_id'],
           "is_demo": user.get('is_demo', False)
       }
   ```

---

## 7. Immediate Actions Required

### Before Next Deploy

1. **Document the is_demo strategy**
   - Is demo data same database or separate?
   - Who can see what?

2. **Audit all endpoints for owner checks**
   - Every endpoint must verify user owns the resource

3. **Add integration tests**
   - Test that demo user can't see production data
   - Test that production user can't see demo data

---

## 8. Database Schema Recommendations

### Current (Problematic)
```
projects
  - project_id
  - agent_id
  - is_demo (inconsistently used)

units / project_units (DUPLICATE!)
  - unit_id
  - project_id

project_stages / timeline_steps (DUPLICATE!)
  - step_id / stage_id (INCONSISTENT!)
  - project_timeline_id / timeline_id (INCONSISTENT!)
```

### Recommended
```
projects
  - project_id (PK)
  - agent_id (FK)
  - created_at
  
units (single collection)
  - unit_id (PK)
  - project_id (FK)
  
timeline_steps (single collection)
  - step_id (PK)
  - timeline_id (FK)
  - project_id (FK, denormalized for queries)
```

Remove `is_demo` from application logic - use separate database for demo.

---

*SSOT Audit completed: January 2026*
