# Architecture Migration Brief - Execution Grade
**Date:** March 19, 2026
**Status:** PENDING APPROVAL

---

## 1. COLLECTION-BY-COLLECTION ENTITY MAP

### 1.1 Core Domain Collections

| # | Collection | Records Owner | Foreign Keys | Status | Action |
|---|------------|---------------|--------------|--------|--------|
| 1 | `users` | System | - | **KEEP** | Canonical identity store |
| 2 | `projects` | Agent (`agent_id`) | `agent_id` | **KEEP** | Primary container entity |
| 3 | `project_units` | Project | `project_id`, `client_id?` | **KEEP** | Unit within project |
| 4 | `clients` | Agent+Project | `agent_id`, `project_id`, `buyer_id?`, `unit_id?` | **KEEP** | Buyer profile - fix ownership |
| 5 | `documents` | Agent | `agent_id`, `client_id`, `project_id?` | **KEEP** | Quotes/Invoices |

### 1.2 Timeline Collections (CONFLICT ZONE)

| # | Collection | Records Owner | Foreign Keys | Status | Action |
|---|------------|---------------|--------------|--------|--------|
| 6 | `project_stages` | Agent+Project | `project_id`, `agent_id` | **DELETE** | Migrate to timeline_steps |
| 7 | `project_timelines` | Project | `project_id`, `template_id?` | **KEEP** | Timeline container |
| 8 | `timeline_steps` | Timeline | `project_timeline_id` | **KEEP** | Steps within timeline |
| 9 | `timeline_step_documents` | Step | `step_id`, `activity_id` | **KEEP** | Linked documents |
| 10 | `timeline_step_internal_notes` | Step | `step_id` | **KEEP** | Agent notes |
| 11 | `timeline_templates` | Agent | `agent_id` | **KEEP** | Reusable templates |
| 12 | `timeline_template_steps` | Template | `template_id` | **KEEP** | Template steps |
| 13 | `timeline_extractions` | Agent | `agent_id`, `project_id` | **KEEP** | AI draft - mark as DRAFT |

### 1.3 Team Collections

| # | Collection | Records Owner | Foreign Keys | Status | Action |
|---|------------|---------------|--------------|--------|--------|
| 14 | `team_members` | Project | `project_id` | **KEEP** | Contractors/contacts |
| 15 | `team_invitations` | Agent | `agent_id` | **KEEP** | Pending invites |

### 1.4 Activity/Communication Collections

| # | Collection | Records Owner | Foreign Keys | Status | Action |
|---|------------|---------------|--------------|--------|--------|
| 16 | `activities` | Agent+Project | `agent_id`, `project_id?`, `client_id?` | **KEEP** | Fix: require project_id |
| 17 | `activity_recipients` | Activity | `activity_id`, `user_id` | **KEEP** | Delivery tracking |
| 18 | `activity_replies` | Activity | `activity_id` | **KEEP** | Reply chain |
| 19 | `notifications` | User | `user_id` | **KEEP** | Push notifications |

### 1.5 Storage/Vault Collections

| # | Collection | Records Owner | Foreign Keys | Status | Action |
|---|------------|---------------|--------------|--------|--------|
| 20 | `vault_documents` | Agent | `agent_id`, `project_id?` | **KEEP** | File storage |

### 1.6 Settings/Config Collections

| # | Collection | Records Owner | Foreign Keys | Status | Action |
|---|------------|---------------|--------------|--------|--------|
| 21 | `agent_settings` | Agent | `agent_id` | **KEEP** | Branding/config |
| 22 | `agent_profiles` | Agent | `agent_id` | **MERGE** | Into agent_settings |

### 1.7 AI/Command Collections

| # | Collection | Records Owner | Foreign Keys | Status | Action |
|---|------------|---------------|--------------|--------|--------|
| 23 | `command_drafts` | Agent | `agent_id` | **KEEP** | Mark as DRAFT state |
| 24 | `command_drafts_autosave` | Agent | `agent_id` | **DELETE** | Merge into command_drafts |
| 25 | `command_logs` | Agent | `agent_id` | **KEEP** | Audit trail |
| 26 | `extraction_cache` | System | - | **KEEP** | Performance cache |

### 1.8 Tracking Collections

| # | Collection | Records Owner | Foreign Keys | Status | Action |
|---|------------|---------------|--------------|--------|--------|
| 27 | `user_activity_tracking` | User | `user_id` | **KEEP** | Read receipts |

### 1.9 Legacy/Unused (Verify)

| # | Collection | Status | Action |
|---|------------|--------|--------|
| 28 | `units` | **DELETE** | Superseded by project_units |

---

## 2. PROJECT_STAGES → TIMELINE_STEPS MIGRATION PROOF

### 2.1 Field Mapping

| ProjectStage Field | TimelineStep Equivalent | Migration |
|--------------------|------------------------|-----------|
| `stage_id` | `step_id` | Rename |
| `project_id` | Via `project_timeline_id` | Lookup parent |
| `agent_id` | Via timeline → project | Inherited |
| `name` | `title` | Rename |
| `description` | `description` | Direct |
| `order` | `order_index` | Rename |
| `planned_start` | `planned_date` | Use start only |
| `planned_end` | - | **LOSS**: No end date in TimelineStep |
| `actual_start` | - | **LOSS**: Not tracked |
| `actual_end` | `completed_at` | Rename |
| `status` | `status` | Map values |
| `progress_percent` | - | **LOSS**: Not tracked |
| `notes` | Via `timeline_step_internal_notes` | Separate collection |
| `dependencies` | - | **LOSS**: Not tracked |
| `is_demo` | `is_demo` (on timeline) | Parent level |
| `created_at` | `created_at` | Direct |
| `updated_at` | `updated_at` | Direct |

### 2.2 Field Coverage Analysis

| Category | Count | Details |
|----------|-------|---------|
| Direct mapping | 8 | id, name, description, order, end→completed, status, created, updated |
| Requires lookup | 2 | project_id, agent_id (via parent) |
| **Data loss** | 4 | planned_end, actual_start, progress_percent, dependencies |

### 2.3 Migration Decision

**OPTION A: Extend TimelineStep schema** (Recommended)
- Add missing fields to `TimelineStep`: `planned_start`, `planned_end`, `actual_start`, `progress_percent`, `dependencies`
- Migrate all `project_stages` data
- Delete `project_stages` collection and endpoints

**OPTION B: Keep both systems** (Not recommended)
- Continues confusion
- Two sources of truth

### 2.4 Status Value Mapping

| ProjectStage.status | TimelineStep.status |
|--------------------|---------------------|
| `upcoming` | `pending` |
| `in_progress` | `in_progress` |
| `completed` | `completed` |
| `delayed` | `in_progress` (flag needed) |
| `on_hold` | `pending` (flag needed) |

---

## 3. SCREEN-BY-SCREEN CONTRACT MAPPING

### 3.0 Complete Screen Coverage (11 screens)

| # | Screen | File | Status |
|---|--------|------|--------|
| 1 | Dashboard/Command Center | AgentHomePage.js | Mapped |
| 2 | Timeline | AgentTimeline.js | Mapped |
| 3 | Workflow | AgentWorkflow.js | Mapped |
| 4 | Team Directory | AgentTeam.js | Mapped |
| 5 | Clients | AgentClients.js | Mapped |
| 6 | Vault | AgentVault.js | Mapped |
| 7 | Invoices | AgentInvoices.js | Mapped |
| 8 | Quotes | AgentQuotes.js | Mapped |
| 9 | Projects | AgentProjects.js | **Added** |
| 10 | Settings | AgentSettings.js | **Added** |
| 11 | Feed | AgentFeed.js + Feed.js | **Added** |
| 12 | Analytics | AgentAnalytics.js | **Added** |

### 3.1 AgentHomePage (Command Center)

**Current Fetches (17 endpoints):**
```
/api/projects                                    READ
/api/clients                                     READ
/api/clients?limit=5                             READ (fallback)
/api/clients?project_id=${projectId}             READ
/api/projects/${projectId}/units                 READ
/api/command/recent-work                         READ
/api/command/interpret                           WRITE
/api/command/execute                             WRITE
/api/command/draft                               WRITE
/api/command/classify-document                   WRITE
/api/command/extract-document                    WRITE
/api/workflows/templates                         READ
/api/workflows/execute                           WRITE
/api/workflows/executions/.../retry              WRITE
/api/workflows/selectors?selector_type=document  READ
/api/workflows/selectors?selector_type=timeline  READ
```

**Canonical Replacement:**
```
GET  /api/agent/dashboard                        → {projects, recentWork, workflows}
GET  /api/projects/{id}/context                  → {clients, units}
POST /api/command/process                        → unified command handler
```

**Write Flow:**
- All commands go through `/api/command/process`
- Returns draft state, not executed
- Explicit confirm triggers execution

**Invalidation Rules:**
- On command execute: invalidate `recentWork`
- On project switch: clear `clients`, `units`

---

### 3.2 AgentTimeline

**Current Fetches (7 endpoints):**
```
/api/projects                                    READ
/api/projects/${projectId}/stages                READ (project_stages)
/api/projects/${selectedProject}/stages          READ (duplicate)
/api/projects/${selectedProject}/stages/{id}     WRITE
/api/command/classify-document                   WRITE
/api/command/extract-document                    WRITE
```

**Canonical Replacement:**
```
GET  /api/projects/{id}/timeline                 → {project, timeline, steps}
PUT  /api/timeline/steps/{id}                    → update step
POST /api/timeline/extract                       → AI extraction (returns DRAFT)
POST /api/timeline/draft/{id}/confirm            → commit draft to persisted
```

**Write Flow:**
- Extraction creates DRAFT timeline
- User reviews DRAFT
- Confirm promotes DRAFT → PERSISTED
- Cancel discards DRAFT

**Invalidation Rules:**
- On step update: refetch timeline
- On draft confirm: invalidate timeline, clear draft state

---

### 3.3 AgentWorkflow

**Current Fetches (15 endpoints):**
```
/api/projects                                    READ
/api/project-timeline?project_id=${projectId}    READ (different endpoint!)
/api/timeline/${timelineId}                      READ
/api/timeline/${timelineId}/steps                READ
/api/timeline/create                             WRITE
/api/timeline/extract                            WRITE
/api/timeline/extractions/{id}/approve           WRITE
/api/timeline/templates                          READ
/api/timeline/templates/{id}/apply               WRITE
/api/timeline/steps/{id}                         READ/WRITE
/api/timeline/steps/{id}/documents               WRITE
/api/timeline/steps/{id}/notes                   WRITE
/api/activities?project_id=${projectId}          READ
```

**Canonical Replacement:**
```
GET  /api/projects/{id}/workflow                 → {project, timeline, steps, activities, templates}
PUT  /api/timeline/steps/{id}                    → update step
POST /api/timeline/steps/{id}/documents          → link document
POST /api/timeline/steps/{id}/notes              → add note
```

**Write Flow:**
- Same as AgentTimeline for extraction
- Step updates are immediate (no draft)

**Invalidation Rules:**
- On step update: refetch workflow
- On document link: refetch step documents

---

### 3.4 AgentTeam

**Current Fetches (3 endpoints):**
```
/api/projects                                    READ
/api/projects/${projectId}/team                  READ
/api/projects/${selectedProject}/team/{id}       WRITE
```

**Canonical Replacement:**
```
GET  /api/projects/{id}/team                     → {project, teamMembers} (already exists)
POST /api/projects/{id}/team                     → create member
PUT  /api/projects/{id}/team/{memberId}          → update member
DELETE /api/projects/{id}/team/{memberId}        → delete member
```

**Write Flow:**
- Direct CRUD, no draft state needed

**Invalidation Rules:**
- On member create/update/delete: refetch team

---

### 3.5 AgentClients

**Current Fetches (4 endpoints):**
```
/api/clients                                     READ
/api/clients/${clientId}                         READ
/api/projects                                    READ
/api/projects/${projectId}/units                 READ
```

**Canonical Replacement:**
```
GET  /api/projects/{id}/clients                  → {project, clients, units}
GET  /api/clients/{id}                           → single client detail
```

**Write Flow:**
- Client CRUD via `/api/clients` endpoints

**Invalidation Rules:**
- On client create/update: refetch project clients
- On unit assignment: refetch units

---

### 3.6 AgentVault

**Current Fetches (5 endpoints):**
```
/api/vault                                       READ
/api/vault/${id}                                 WRITE (update/delete)
/api/clients                                     READ
/api/projects                                    READ
```

**Canonical Replacement:**
```
GET  /api/vault?project_id={id}                  → {documents} filtered by project
POST /api/vault                                  → upload
PUT  /api/vault/{id}                             → update metadata
DELETE /api/vault/{id}                           → delete
```

**Invalidation Rules:**
- On upload/delete: refetch vault list

---

### 3.8 AgentProjects

**Current Fetches (6 endpoints):**
```
/api/projects                                    READ
/api/projects/${projectId}                       READ/WRITE
/api/projects/${project.project_id}/units        READ
/api/projects/${unitsProject.project_id}/units   READ (duplicate)
/api/projects/.../units/${unitId}                WRITE
/api/billing/status                              READ
```

**Canonical Replacement:**
```
GET  /api/projects                               → {projects[]} (list)
GET  /api/projects/{id}                          → {project, units, clientCount}
POST /api/projects                               → create
PUT  /api/projects/{id}                          → update
DELETE /api/projects/{id}                        → delete
POST /api/projects/{id}/units                    → add unit
DELETE /api/projects/{id}/units/{unitId}         → remove unit
```

**Write Flow:**
- Direct CRUD, no draft state

**Invalidation Rules:**
- On project create/update/delete: refetch projects list
- On unit add/remove: refetch project detail

---

### 3.9 AgentSettings

**Current Fetches (10 endpoints):**
```
/api/settings                                    READ/WRITE
/api/settings/logo                               WRITE
/api/team/members                                READ
/api/team/members/${memberId}                    WRITE
/api/team/invitations                            READ
/api/team/invitations/${invitationId}            WRITE
/api/billing/status                              READ
/api/billing/plans                               READ
/api/billing/portal                              READ
/api/billing/create-checkout-session             WRITE
```

**Canonical Replacement:**
```
GET  /api/agent/settings                         → {settings, teamMembers, invitations, billing}
PUT  /api/agent/settings                         → update settings
POST /api/agent/settings/logo                    → upload logo
POST /api/team/invite                            → send invitation
DELETE /api/team/invitations/{id}                → revoke invitation
```

**Write Flow:**
- Settings are immediate save
- Invitations have pending state

**Invalidation Rules:**
- On settings update: refetch settings
- On team change: refetch team list

---

### 3.10 AgentFeed (via Feed.js component)

**Current Fetches (8 endpoints):**
```
/api/activities                                  READ
/api/activities/${activityId}                    READ/WRITE
/api/activities/${activityId}/reply              WRITE
/api/activities/${activityId}/send               WRITE
/api/clients                                     READ
/api/projects                                    READ
```

**Canonical Replacement:**
```
GET  /api/feed?project_id={id}                   → {activities[], projects, clients}
POST /api/activities                             → create activity
PUT  /api/activities/{id}                        → update activity
POST /api/activities/{id}/reply                  → add reply
POST /api/activities/{id}/send                   → send to recipients
```

**Write Flow:**
- Activity created as draft
- Send promotes to delivered

**Invalidation Rules:**
- On activity create/reply: refetch feed
- WebSocket push for real-time updates

---

### 3.11 AgentAnalytics

**Current Fetches (1 endpoint):**
```
/api/analytics?period=${period}                  READ
```

**Canonical Replacement:**
```
GET  /api/analytics?period={period}              → {metrics} (already canonical)
```

**Write Flow:**
- Read-only, no writes

**Invalidation Rules:**
- None (read-only, user-triggered refresh)

---

### 3.7 Document Pages (Invoices/Quotes)

**Current Fetches:**
```
/api/documents?doc_type=invoice|quote            READ list
/api/documents/${id}                             READ detail
/api/documents/create                            WRITE
/api/documents/upload                            WRITE
/api/documents/${id}/send                        WRITE
/api/documents/${id}/action                      WRITE
/api/documents/${id}/pdf                         READ
```

**Canonical Replacement:** Keep as-is, already well-structured.

**Write Flow:**
- Upload creates DRAFT document
- User reviews/edits
- Send promotes to SENT

---

## 4. FIELD-LEVEL STATE CLASSIFICATION

### 4.1 AgentHomePage State Variables (28 total)

| Variable | Current Type | Correct Type | Action |
|----------|--------------|--------------|--------|
| `commandText` | mixed | UI | Rename: `ui_commandText` |
| `isListening` | mixed | UI | Rename: `ui_isListening` |
| `isProcessing` | mixed | UI | Rename: `ui_isProcessing` |
| `attachments` | mixed | TRANSIENT | Rename: `transient_attachments` |
| `isDragActive` | mixed | UI | Rename: `ui_isDragActive` |
| `selectedProject` | context | CACHED | Move to context |
| `selectedClient` | mixed | CACHED | Move to context |
| `selectedUnit` | mixed | CACHED | Move to context |
| `projects` | mixed | CACHED | Move to DataContext |
| `clients` | mixed | CACHED | Move to DataContext |
| `units` | mixed | CACHED | Move to DataContext |
| `recentWork` | mixed | CACHED | Move to DataContext |
| `loading` | mixed | UI | Rename: `ui_loading` |
| `previewOpen` | mixed | UI | Rename: `ui_previewOpen` |
| `previewData` | mixed | DRAFT | Rename: `draft_commandResult` |
| `executing` | mixed | UI | Rename: `ui_executing` |
| `reExtracting` | mixed | UI | Rename: `ui_reExtracting` |
| `overrideDocType` | mixed | TRANSIENT | Rename: `transient_docTypeOverride` |
| `workflowTemplates` | mixed | CACHED | Move to DataContext |
| `workflowDialogOpen` | mixed | UI | Rename: `ui_workflowDialogOpen` |
| `selectedWorkflow` | mixed | TRANSIENT | Rename: `transient_selectedWorkflow` |
| `workflowContext` | mixed | TRANSIENT | Rename: `transient_workflowContext` |
| `workflowExecuting` | mixed | UI | Rename: `ui_workflowExecuting` |
| `workflowResult` | mixed | DRAFT | Rename: `draft_workflowResult` |
| `workflowSelectors` | mixed | CACHED | Move to DataContext |
| `loadingSelectors` | mixed | UI | Rename: `ui_loadingSelectors` |
| `showConfirmation` | mixed | UI | Rename: `ui_showConfirmation` |
| `voiceSupported` | mixed | DERIVED | Compute on render |

### 4.2 State Type Definitions

| Type | Prefix | Lifetime | Storage | Example |
|------|--------|----------|---------|---------|
| **PERSISTED** | (none) | Until deleted | Database | `project`, `client` |
| **CACHED** | - | Until invalidated | DataContext | `projects[]`, `clients[]` |
| **DRAFT** | `draft_` | Until commit/discard | Local state | `draft_commandResult` |
| **TRANSIENT** | `transient_` | Until action complete | Local state | `transient_attachments` |
| **UI** | `ui_` | Component lifetime | Local state | `ui_loading`, `ui_dialogOpen` |
| **DERIVED** | - | Recalculated | Computed | `filteredClients` |
| **AI_GENERATED** | `ai_` | Until approved | Draft collection | `ai_extractedTimeline` |

---

## 5. MIGRATION SEQUENCE

### Phase 1: Schema Alignment (Backend) ✅ COMPLETE
**Completed:** March 19, 2026
**Risk:** Low
**Rollback:** Revert schema changes

**Executed:**
1. ✅ Extended `TimelineStep` model with fields from `ProjectStage`:
   - `planned_start`, `planned_end`, `actual_start`, `progress_percent`, `notes`, `dependencies`
2. ✅ Extended `TimelineStepUpdate` model with same fields
3. ✅ Updated `update_timeline_step` endpoint to handle new fields
4. ✅ Added status mapping helpers: `_map_timeline_status_to_stage()`, `_map_stage_status_to_timeline()`
5. ✅ **GET /projects/{id}/stages** - reads ONLY from timeline_steps (no fallback)
6. ✅ **POST /projects/{id}/stages** - writes ONLY to timeline_steps (creates timeline if needed)
7. ✅ **PUT /projects/{id}/stages/{id}** - updates ONLY in timeline_steps
8. ✅ **DELETE /projects/{id}/stages/{id}** - deletes ONLY from timeline_steps
9. ✅ Demo seeding uses timeline_steps (not project_stages)

**Verification:**
- `project_stages`: 0 records
- `timeline_steps`: 23 records
- All CRUD operations verified working
- **Single source of truth enforced**

### Phase 2: Endpoint Unification (Backend + Frontend) ✅ COMPLETE
**Completed:** March 19, 2026
**Risk:** Medium
**Rollback:** Restore old endpoints + fetch logic

**Backend - Completed:**
1. ✅ Defined composite response models:
   - `DashboardResponse` - for AgentHomePage
   - `ProjectContextResponse` - for context switching
   - `ProjectTimelineResponse` - for AgentTimeline
   - `ProjectWorkflowResponse` - for AgentWorkflow
   - Supporting models: `ProjectSummary`, `ClientSummary`, `UnitSummary`, `TimelineStepSummary`, `RecentWorkItem`

2. ✅ Created canonical composite endpoints:
   - `GET /api/agent/dashboard` → returns projects, selected_project, recent_work
   - `GET /api/projects/{id}/context` → returns project, clients, units
   - `GET /api/projects/{id}/timeline/full` → returns project, timeline_id, steps, progress
   - `GET /api/projects/{id}/workflow/full` → returns project, steps, activities, templates

**Frontend - Completed:**
3. ✅ Updated AgentHomePage:
   - Replaced 5+ fragmented fetches with single `fetchDashboard()` → `/api/agent/dashboard`
   - Replaced context fetches with `fetchProjectContext()` → `/api/projects/{id}/context`
   - Removed `fetchRecentWorkFallback()` - no more UI reconstruction

4. ✅ Updated AgentTimeline:
   - Replaced `fetchStages()` with `fetchTimeline()` → `/api/projects/{id}/timeline/full`
   - Status mapping handled locally for UI compatibility

5. ✅ Updated AgentWorkflow:
   - Replaced 3 separate fetches with `fetchWorkflow()` → `/api/projects/{id}/workflow/full`
   - Templates now fetched as part of workflow response

**Verification:**
- Dashboard: Project loaded, 5 recent activity items displayed
- Timeline: 5 steps displayed with 33% progress
- All data from single canonical endpoints

### Phase 3: Frontend Data Layer
**Duration:** 4-5 days
**Risk:** High
**Rollback:** Revert to per-page fetching

1. Create `DataContext` provider:
   ```javascript
   DataContext {
     // Cached data
     projects: Project[]
     clients: Map<projectId, Client[]>
     timelines: Map<projectId, Timeline>
     
     // Selection state
     selectedProject: string
     
     // Actions
     fetchProjects()
     fetchProjectContext(projectId)
     invalidate(entity)
   }
   ```
2. Update pages one at a time (AgentTeam → AgentTimeline → AgentWorkflow → AgentHomePage)
3. Remove per-page fetch logic
4. Delete fallback chains

### Phase 4: State Separation (Frontend)
**Duration:** 2-3 days
**Risk:** Low
**Rollback:** Rename variables back

1. Rename state variables with type prefixes
2. Separate draft state from persisted state
3. Add explicit commit/discard flows for drafts
4. Remove ambiguous state mixing

### Phase 5: Cleanup (Backend + Database)
**Duration:** 1-2 days
**Risk:** Low (after validation)
**Rollback:** Restore from backup

1. Delete `project_stages` collection
2. Delete `command_drafts_autosave` collection
3. Delete `units` collection (if unused)
4. Merge `agent_profiles` into `agent_settings`
5. Remove deprecated endpoints
6. Remove dual-write logic for document fields

---

## 6. DELETION LIST WITH PHASE ASSIGNMENT

### 6.1 Collections to Delete

| Collection | Replacement | Phase | Precondition |
|------------|-------------|-------|--------------|
| `project_stages` | `timeline_steps` | **Phase 5** | After migration verified |
| `command_drafts_autosave` | `command_drafts` | **Phase 5** | After data merged |
| `units` | `project_units` | **Phase 5** | After no-reference verified |
| `agent_profiles` | `agent_settings` | **Phase 5** | After data merged |

### 6.2 Endpoints to Delete

| Endpoint | Replacement | Phase | Precondition |
|----------|-------------|-------|--------------|
| `GET /projects/{id}/stages` | `GET /projects/{id}/timeline` | **Phase 2** | After new endpoint live |
| `POST /projects/{id}/stages` | `POST /timeline/steps` | **Phase 2** | After new endpoint live |
| `PUT /projects/{id}/stages/{id}` | `PUT /timeline/steps/{id}` | **Phase 2** | After new endpoint live |
| `DELETE /projects/{id}/stages/{id}` | `DELETE /timeline/steps/{id}` | **Phase 2** | After new endpoint live |

### 6.3 Frontend Code to Delete

| File | Code Block | Phase | Precondition |
|------|------------|-------|--------------|
| AgentHomePage.js | `fetchRecentWorkFallback()` | **Phase 3** | After DataContext provides recentWork |
| AgentHomePage.js | `fetchClients()` duplicate | **Phase 3** | After DataContext provides clients |
| AgentHomePage.js | UI reconstruction: `clientsData.slice(0,5).map(...)` | **Phase 3** | After backend provides recentWork |
| AgentTimeline.js | `/projects/{id}/stages` fetches | **Phase 3** | After unified timeline endpoint |
| AgentWorkflow.js | Duplicate timeline fetches | **Phase 3** | After unified workflow endpoint |
| All pages | Per-page `/api/projects` fetches (8 instances) | **Phase 3** | After DataContext provides projects |

### 6.4 Frontend Reconstruction Logic to Remove (Phase 3)

| File | Line Range | Logic | Replacement |
|------|------------|-------|-------------|
| AgentHomePage.js | fetchRecentWorkFallback | Constructs recentWork from clients | Backend `/api/command/recent-work` |
| AgentHomePage.js | items mapping | Builds path, subtitle | Backend provides complete object |
| AgentTimeline.js | stages fetch | Uses project_stages | Unified timeline_steps |
| AgentWorkflow.js | multiple timeline sources | Fetches from 3 endpoints | Single `/api/projects/{id}/workflow` |

---

## 7. SUCCESS CRITERIA

| Criteria | Measurement |
|----------|-------------|
| Single source of truth | Each entity fetched from exactly 1 endpoint |
| No fallback chains | Zero `catch` blocks that fetch alternative data |
| Deterministic rendering | Same project_id → identical UI state |
| Clear state types | All state variables prefixed by type |
| Draft isolation | Draft data never overwrites persisted |
| Cache invalidation | Explicit rules per write operation |
| Endpoint count reduction | From 77 → ~30 canonical endpoints |

---

## 8. APPROVAL CHECKLIST

- [ ] Collection status (keep/merge/delete) approved
- [ ] Timeline migration approach approved (extend TimelineStep)
- [ ] Screen-to-payload mapping approved
- [ ] State classification scheme approved
- [ ] Migration sequence approved
- [ ] Deletion list approved

**Awaiting approval before Phase 1 execution.**
