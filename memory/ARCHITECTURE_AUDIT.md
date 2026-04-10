# Architecture Audit - Evohome Platform
**Date:** March 19, 2026
**Status:** Analysis Complete - Awaiting Approval Before Execution

---

## Executive Summary

The system currently operates as a **patchwork of features without a unified data model**. There is no single source of truth - instead, truth is determined by "whatever resolves last". This creates non-deterministic behavior that breaks user trust.

**Core Problem:** The architecture has drifted from "define data → build features" to "add features → patch data issues".

---

## 1. CORE ENTITIES AND RELATIONSHIPS

### 1.1 Entity Map

```
┌─────────────────────────────────────────────────────────────────┐
│                         AGENT (user)                            │
│                      agent_id (owner)                           │
└─────────────────┬───────────────────────────────────────────────┘
                  │ owns
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                          PROJECT                                │
│   project_id, agent_id, name, address                           │
└──────┬──────────────┬──────────────┬───────────────────────────┘
       │              │              │
       │ has          │ has          │ has
       ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────────────────┐
│    UNITS     │ │   CLIENTS    │ │     PROJECT_TIMELINE         │
│  unit_id     │ │  client_id   │ │  project_timeline_id         │
│  project_id  │ │  project_id  │ │  project_id                  │
│  client_id?  │ │  unit_id?    │ └──────────────┬───────────────┘
└──────────────┘ │  buyer_id?   │                │ has
                 └──────────────┘                ▼
                       │              ┌──────────────────────────┐
                       │ linked to    │    TIMELINE_STEPS        │
                       ▼              │  step_id                 │
                 ┌──────────────┐     │  project_timeline_id     │
                 │    BUYER     │     └──────────────────────────┘
                 │   (user)     │
                 │   buyer_id   │
                 └──────────────┘
```

### 1.2 Full Collection List (28 Collections)

| Collection | Owner | Purpose | Relationships |
|------------|-------|---------|---------------|
| `users` | System | Auth/identity | agent_id OR buyer_id |
| `projects` | Agent | Project container | agent_id |
| `project_units` | Project | Units within project | project_id, client_id? |
| `clients` | Agent+Project | Buyer profiles | agent_id, project_id, buyer_id?, unit_id? |
| `documents` | Agent | Quotes/Invoices | agent_id, client_id, project_id? |
| `project_timelines` | Project | Timeline container | project_id |
| `timeline_steps` | Timeline | Steps in timeline | project_timeline_id |
| `timeline_step_documents` | Step | Linked docs | step_id, activity_id |
| `timeline_step_internal_notes` | Step | Agent notes | step_id |
| `project_stages` | Project | **DUPLICATE of timeline?** | project_id |
| `team_members` | Project | Contractors/contacts | project_id |
| `activities` | Agent | Feed items | agent_id, client_id?, project_id? |
| `activity_recipients` | Activity | Who sees activity | activity_id, user_id |
| `activity_replies` | Activity | Replies | activity_id |
| `vault_documents` | Agent | File storage | agent_id, project_id? |
| `notifications` | User | Push notifications | user_id |
| `timeline_templates` | Agent | Reusable templates | agent_id |
| `timeline_template_steps` | Template | Template steps | template_id |
| `timeline_extractions` | Agent | AI extraction drafts | agent_id |
| `agent_settings` | Agent | Branding/config | agent_id |
| `team_invitations` | Agent | Team invites | agent_id |
| `command_drafts` | Agent | AI command drafts | agent_id |
| `command_drafts_autosave` | Agent | Autosave | agent_id |
| `command_logs` | Agent | Command history | agent_id |
| `extraction_cache` | System | Cache | - |
| `user_activity_tracking` | User | Read tracking | user_id |

### 1.3 Identified Entity Conflicts

| Issue | Collections Involved | Problem |
|-------|---------------------|---------|
| **Timeline vs Stages** | `project_timelines` + `timeline_steps` vs `project_stages` | Two systems for the same concept |
| **Client ownership** | `clients` | Has both `agent_id` AND `project_id` - unclear which is authoritative |
| **Document context** | `documents` | Has `client_id` but `project_id` is optional - inconsistent |
| **Activity scope** | `activities` | `project_id` and `client_id` both optional - no clear scope |

---

## 2. OWNER OF TRUTH (CURRENT vs PROPOSED)

### 2.1 Current State (Ambiguous)

| Entity | Who "Owns" Truth | Problem |
|--------|------------------|---------|
| Project | Agent | ✅ Clear |
| Client | Agent + Project | ❌ Dual ownership - queries inconsistent |
| Timeline | Project | ❌ Two systems (stages vs timelines) |
| Team | Project | ✅ Clear |
| Documents | Agent | ⚠️ Project link is optional |
| Activities | Multiple | ❌ No clear owner - fetched differently per context |

### 2.2 Proposed Owner of Truth

| Entity | Owner | Authoritative Query |
|--------|-------|---------------------|
| Project | Agent | `{agent_id}` |
| Client | Project (via Agent) | `{project_id, agent_id}` |
| Timeline | Project | `{project_id}` - **SINGLE system** |
| Team | Project | `{project_id}` |
| Documents | Client (via Project via Agent) | `{client_id}` OR `{project_id, agent_id}` |
| Activities | Project | `{project_id}` |
| Vault | Agent | `{agent_id}` with optional project filter |

---

## 3. DUPLICATE FETCH PATHS

### 3.1 Backend Endpoint Duplication

| Data | Endpoints | Issue |
|------|-----------|-------|
| **Timeline** | `GET /projects/{id}/stages` | Returns `project_stages` |
| | `GET /project-timeline?project_id=` | Returns `project_timelines` + `timeline_steps` |
| | `GET /timeline` | Returns buyer view of timeline |
| **Clients** | `GET /clients` | All agent's clients |
| | `GET /clients?project_id=` | Filtered by project |
| | `GET /clients/{id}` | Single client |
| | `GET /clients/{id}/preview` | Client with extra data |
| **Documents** | `GET /documents` | All documents |
| | `GET /documents?project_id=` | By project |
| | `GET /documents?client_id=` | By client |
| | `GET /documents/{id}` | Single document |

### 3.2 Frontend Fetch Duplication (77 unique fetch paths)

**Projects fetched from:**
- `AgentHomePage.js` → `/api/projects`
- `AgentTeam.js` → `/api/projects`
- `AgentTimeline.js` → `/api/projects`
- `AgentWorkflow.js` → `/api/projects`
- `AgentClients.js` → `/api/projects`
- `AgentProjects.js` → `/api/projects`
- `AgentQuoteUpload.js` → `/api/projects`
- `AgentInvoiceUpload.js` → `/api/projects`

**8 separate fetches for the same data** - each page maintains its own copy.

**Clients fetched from:**
- `AgentHomePage.js` → `/api/clients` AND `/api/clients?project_id=`
- `AgentClients.js` → `/api/clients` OR `/api/clients?project_id=`
- `AgentQuoteUpload.js` → `/api/clients`
- `AgentInvoiceUpload.js` → `/api/clients`

---

## 4. SCREEN-TO-PAYLOAD MAPPING

### 4.1 Current State (Multiple Payloads Per Screen)

| Screen | Current Fetches | Problem |
|--------|-----------------|---------|
| **AgentHomePage** | projects, clients, units, recentWork, workflowTemplates | 5+ async calls, race conditions |
| **AgentTimeline** | projects, stages | 2 calls but uses `project_stages` |
| **AgentWorkflow** | projects, timeline, steps, templates, activities | 5+ calls |
| **AgentTeam** | projects, teamMembers | 2 calls |
| **AgentClients** | clients, projects, units | 3 calls |

### 4.2 Proposed Canonical Payloads

| Screen | Single Endpoint | Payload |
|--------|-----------------|---------|
| **AgentHomePage** | `GET /api/agent/dashboard` | `{projects, selectedProject: {clients, timeline, recentActivity}}` |
| **AgentTimeline** | `GET /api/projects/{id}/timeline` | `{project, timeline, steps}` |
| **AgentWorkflow** | `GET /api/projects/{id}/workflow` | `{project, timeline, steps, activities, templates}` |
| **AgentTeam** | `GET /api/projects/{id}/team` | `{project, teamMembers}` - already exists |
| **AgentClients** | `GET /api/projects/{id}/clients` | `{project, clients, units}` |

---

## 5. STATE CLASSIFICATION

### 5.1 Current State (Mixed/Unclear)

The frontend currently mixes all state types in `useState`:

```javascript
// All treated the same - no distinction
const [projects, setProjects] = useState([]);      // Should be: PERSISTED
const [stages, setStages] = useState([]);          // Should be: PERSISTED  
const [extractedStages, setExtractedStages] = useState([]); // Should be: TRANSIENT
const [loading, setLoading] = useState(true);      // Should be: UI
```

### 5.2 Proposed State Hierarchy

| Type | Description | Lifetime | Example |
|------|-------------|----------|---------|
| **PERSISTED** | Database records | Permanent until deleted | projects, clients, documents |
| **CACHED** | Fetched persisted data | Until invalidated | local copy of projects list |
| **TRANSIENT** | In-progress work | Until committed or discarded | AI extraction draft, form data |
| **UI** | Rendering state | Component lifetime | loading, dialogOpen, expanded |
| **DERIVED** | Computed from other state | Recalculated on change | filteredClients, totalAmount |

### 5.3 Current Problems

| Problem | Example |
|---------|---------|
| **Transient treated as persisted** | `extractedTimeline` can overwrite `timeline` |
| **No cache invalidation** | Stale project data persists after navigation |
| **Derived state stored** | `stats` computed but stored, not recalculated |
| **No distinction in naming** | Can't tell from variable name what type it is |

---

## 6. WHAT MUST BE DELETED

### 6.1 Duplicate Systems

| Delete | Keep | Reason |
|--------|------|--------|
| `project_stages` collection | `project_timelines` + `timeline_steps` | One timeline system |
| `/projects/{id}/stages` endpoints | `/project-timeline` endpoints | Unified API |

### 6.2 Fallback Fetch Chains (Frontend)

These compensate for missing data and create ambiguity:

```javascript
// DELETE THESE PATTERNS:

// AgentHomePage.js - fetchRecentWorkFallback
if (recentRes.ok) {
  setRecentWork(await recentRes.json());
} else {
  await fetchRecentWorkFallback(); // ❌ DELETE
}

// Multiple fetch paths for same data
const fetchClients = async () => { ... }           // ❌ DELETE
const fetchClientsForProject = async () => { ... } // KEEP (unified)
```

### 6.3 UI-Side Data Reconstruction

```javascript
// DELETE: Frontend computing what backend should provide
const items = clientsData.slice(0, 5).map(client => ({
  id: client.client_id,
  type: 'client',
  title: client.name,
  subtitle: client.project_name || 'No project', // ❌ Frontend constructing
  path: `/agent/clients/${client.client_id}`      // ❌ Frontend building URLs
}));
```

### 6.4 Ambiguous Draft vs Persisted Flows

| Delete | Issue |
|--------|-------|
| `extractedStages` mixed with `stages` | Draft overwrites persisted |
| `extractedTimeline` mixed with `timeline` | Same issue |
| `previewData` with no clear lifecycle | When does preview become real? |

### 6.5 "Last Response Wins" Patterns

Every fetch that doesn't validate against current context:

```javascript
// DELETE THIS PATTERN:
const res = await fetch(...);
if (res.ok) {
  setData(await res.json()); // ❌ No check if context changed
}

// ALREADY FIXED but pattern still exists in some places
```

---

## 7. PROPOSED MIGRATION PATH

### Phase 1: Entity Consolidation (Backend)
1. Merge `project_stages` into `timeline_steps`
2. Delete `/projects/{id}/stages` endpoints
3. Ensure all entities have clear ownership fields

### Phase 2: Endpoint Unification (Backend)
1. Create composite endpoints per screen:
   - `GET /api/agent/dashboard`
   - `GET /api/projects/{id}/full` (timeline + team + clients)
2. Deprecate fragmented endpoints
3. Add `response_model` to all endpoints (already partially done)

### Phase 3: Frontend Data Layer
1. Create `DataContext` with:
   - Canonical state per entity type
   - Clear cache invalidation rules
   - Loading/error states per entity
2. Remove per-page fetch logic
3. Delete fallback chains

### Phase 4: State Separation
1. Rename state variables with prefixes:
   - `persisted_*` - from database
   - `draft_*` - not yet committed
   - `ui_*` - rendering only
2. Add commit/discard flows for drafts

### Phase 5: Decompose server.py
1. Split by domain: `/routes/projects.py`, `/routes/clients.py`, etc.
2. Each route file owns its entity completely
3. No cross-cutting queries

---

## 8. SUCCESS CRITERIA

After migration, the system must satisfy:

1. **Deterministic**: Same input → same output, always
2. **Single source of truth**: One query path per entity
3. **Clear ownership**: Every record has one owner
4. **Explicit state**: Can tell from name if data is persisted, draft, or UI
5. **No fallbacks**: If data doesn't exist, show empty state - don't reconstruct
6. **Backend authority**: Frontend renders, never interprets

---

## 9. NEXT STEPS (Pending Approval)

1. [ ] Review and approve this audit
2. [ ] Confirm migration phases order
3. [ ] Begin Phase 1: Entity consolidation

**No code changes until audit is approved.**
