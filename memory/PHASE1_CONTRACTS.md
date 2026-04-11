# Module Contracts — Phase 1 Canonical Core

## Module 1: Unit

**Canonical entity**: `Unit`
**Collection**: `units`
**Parent/Owner**: `Project` (via `project_id`), `Agent` (via `agent_id`)
**Children**: None
**Foreign keys**: `project_id` → projects, `agent_id` → users, `assigned_client_id` → clients

### Required fields
- `unit_id`: str (unique, format: `unit_{uuid12}`)
- `project_id`: str (FK → projects)
- `agent_id`: str (FK → users)
- `unit_reference`: str (display label, e.g. "Lot 3.01")
- `created_at`: str (ISO 8601)

### Optional fields
- `assigned_client_id`: str | None (FK → clients)
- `is_available`: bool (derived: True if assigned_client_id is None)
- `status`: str (default: "active")
- `notes`: str | None

### Forbidden fields
- `is_demo` — REMOVED
- `client_id` — use `assigned_client_id`
- Any field not listed above

### Allowed transitions
- available → assigned (when client linked)
- assigned → available (when client unlinked)

---

## Module 2: Project

**Canonical entity**: `Project`
**Collection**: `projects`
**Parent/Owner**: `Agent` (via `agent_id`)
**Children**: Units, Timelines, Clients (via project_id)
**Foreign keys**: `agent_id` → users

### Required fields
- `project_id`: str (unique, format: `proj_{uuid12}`)
- `agent_id`: str (FK → users)
- `name`: str
- `created_at`: str (ISO 8601)

### Optional fields
- `address`: str | None
- `description`: str | None
- `total_units`: int (default: 0)
- `construction_start`: str | None
- `estimated_completion`: str | None
- `status`: str (default: "active")
- `settings`: dict | None

### Forbidden fields
- `is_demo`
- `stages` — use timeline_steps
- `stage_id` — use step_id

---

## Module 3: Timeline

**Canonical entity**: `Timeline`
**Collection**: `timelines`
**Parent/Owner**: `Project` (via `project_id`)
**Children**: TimelineSteps
**Foreign keys**: `project_id` → projects, `agent_id` → users

### Required fields
- `timeline_id`: str (unique, format: `tl_{uuid12}`)
- `project_id`: str (FK → projects)
- `agent_id`: str (FK → users)
- `created_at`: str (ISO 8601)

### Optional fields
- `name`: str (default: "Main Timeline")
- `description`: str | None

### Forbidden fields
- `is_demo`
- `project_timeline_id` — use `timeline_id`

---

## Module 4: TimelineStep

**Canonical entity**: `TimelineStep`
**Collection**: `timeline_steps`
**Parent/Owner**: `Timeline` (via `timeline_id`), `Project` (via `project_id`)
**Children**: None
**Foreign keys**: `timeline_id` → timelines, `project_id` → projects

### Required fields
- `step_id`: str (unique, format: `step_{uuid12}`)
- `timeline_id`: str (FK → timelines)
- `project_id`: str (FK → projects)
- `title`: str
- `order_index`: int
- `created_at`: str (ISO 8601)

### Optional fields
- `description`: str | None
- `status`: str (default: "pending", allowed: pending/in_progress/completed/blocked)
- `progress_percent`: int (0-100, default: 0)
- `planned_start`: str | None
- `planned_end`: str | None
- `actual_start`: str | None
- `actual_end`: str | None
- `dependencies`: list[str] (step_ids)

### Forbidden fields
- `is_demo`
- `stage_id` — use `step_id`
- `name` — use `title`
- `order` — use `order_index`

---

## Module 5: Client

**Canonical entity**: `Client`
**Collection**: `clients`
**Parent/Owner**: `Agent` (via `agent_id`)
**Children**: None
**Foreign keys**: `agent_id` → users, `project_id` → projects, `unit_id` → units, `buyer_id` → users

### Required fields
- `client_id`: str (unique, format: `client_{uuid12}`)
- `agent_id`: str (FK → users)
- `name`: str
- `created_at`: str (ISO 8601)

### Optional fields
- `email`: str | None
- `phone`: str | None
- `project_id`: str | None (FK → projects)
- `unit_id`: str | None (FK → units)
- `buyer_id`: str | None (FK → users, linked buyer account)
- `status`: str (default: "active")
- `notes`: str | None

### Forbidden fields
- `is_demo`

---

## Cross-cutting: is_demo Removal

**Before**: Every entity had `is_demo: bool` field. Every query filtered by it.
**After**: Field removed entirely. Demo/prod separation via database-level isolation.

### Access control pattern (canonical)
- Agent sees: `{"agent_id": user.user_id}`
- Buyer sees: `{"buyer_id": user.user_id}` or via client linkage
- No `is_demo` in any query, schema, index, or response
