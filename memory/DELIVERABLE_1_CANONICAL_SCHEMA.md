# Deliverable 1: Canonical Schema Document
## Evohome CMP - Single Source of Truth Data Model

**Version**: 1.0  
**Date**: January 2026  
**Status**: NORMATIVE - This is the authoritative schema definition

---

## Naming Conventions

### General Rules

| Rule | Convention | Example |
|------|------------|---------|
| Collection names | `snake_case`, plural | `projects`, `clients`, `timeline_steps` |
| Field names | `snake_case` | `project_id`, `created_at` |
| ID fields | `{entity}_id` | `project_id`, `client_id`, `step_id` |
| Foreign keys | `{referenced_entity}_id` | `agent_id`, `project_id` |
| Timestamps | ISO 8601 string | `"2026-01-15T10:30:00Z"` |
| Booleans | Positive naming | `is_active`, `has_password` (not `not_deleted`) |

### Forbidden Patterns

| Pattern | Reason | Replacement |
|---------|--------|-------------|
| `camelCase` | Inconsistent | Use `snake_case` |
| Duplicate collections | Data fragmentation | Consolidate |
| Dual ID fields | Confusion | Pick one canonical name |
| `is_demo` in queries | Fragile isolation | Database-level separation |

---

## Entity Definitions

### 1. USER

**Collection**: `users`

**Description**: Authentication identity. Can be an Agent (property manager) or Buyer (client).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | ✅ | Primary key, format: `{role}_{uuid12}` |
| `email` | string | ✅ | Unique email address |
| `name` | string | ✅ | Display name |
| `role` | enum | ✅ | `"agent"` or `"buyer"` |
| `password_hash` | string | ❌ | bcrypt hash (null for OAuth-only) |
| `picture` | string | ❌ | Profile picture URL |
| `created_at` | datetime | ✅ | Account creation timestamp |
| `subscription_plan` | string | ❌ | Agent only: `"free"`, `"pro"`, `"enterprise"` |
| `subscription_status` | string | ❌ | Agent only: `"active"`, `"cancelled"`, `"past_due"` |
| `settings` | object | ❌ | User preferences (language, currency, etc.) |

**Indexes**:
- `email` (unique)
- `user_id` (unique)
- `role`

**Relationships**:
- Agent → owns many Projects
- Agent → owns many Clients
- Buyer → linked to one Client

---

### 2. PROJECT

**Collection**: `projects`

**Description**: A real estate development or building being managed.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `project_id` | string | ✅ | Primary key, format: `proj_{uuid12}` |
| `agent_id` | string | ✅ | FK → users.user_id (owner) |
| `name` | string | ✅ | Project name |
| `address` | string | ❌ | Physical address |
| `description` | string | ❌ | Project description |
| `total_units` | integer | ❌ | Total units in project |
| `construction_start` | string | ❌ | Start date |
| `estimated_completion` | string | ❌ | Completion date |
| `created_at` | datetime | ✅ | Creation timestamp |

**Indexes**:
- `project_id` (unique)
- `agent_id`

**Relationships**:
- Project → belongs to one Agent
- Project → has many Units
- Project → has many Clients
- Project → has one Timeline
- Project → has many Team Members

---

### 3. UNIT

**Collection**: `units` ← **CANONICAL** (deprecate `project_units`)

**Description**: An individual property unit within a project (apartment, office, etc.).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `unit_id` | string | ✅ | Primary key, format: `unit_{uuid12}` |
| `project_id` | string | ✅ | FK → projects.project_id |
| `unit_reference` | string | ✅ | Display reference (e.g., "A-301") |
| `floor` | string | ❌ | Floor level |
| `type` | string | ❌ | Unit type (studio, 2BR, etc.) |
| `size_sqm` | number | ❌ | Size in square meters |
| `price` | number | ❌ | Price |
| `status` | enum | ❌ | `"available"`, `"reserved"`, `"sold"` |
| `created_at` | datetime | ✅ | Creation timestamp |

**Indexes**:
- `unit_id` (unique)
- `project_id`
- `(project_id, unit_reference)` (unique)

**Relationships**:
- Unit → belongs to one Project
- Unit → assigned to zero or one Client

---

### 4. CLIENT

**Collection**: `clients`

**Description**: A property purchaser/acquirer managed by an agent.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `client_id` | string | ✅ | Primary key, format: `client_{uuid12}` |
| `agent_id` | string | ✅ | FK → users.user_id (owner) |
| `project_id` | string | ❌ | FK → projects.project_id |
| `unit_id` | string | ❌ | FK → units.unit_id |
| `buyer_id` | string | ❌ | FK → users.user_id (linked buyer account) |
| `name` | string | ✅ | Client name |
| `email` | string | ✅ | Contact email |
| `phone` | string | ❌ | Phone number |
| `address` | string | ❌ | Mailing address |
| `language` | string | ❌ | Preferred language |
| `notes` | string | ❌ | Internal notes |
| `created_at` | datetime | ✅ | Creation timestamp |

**Indexes**:
- `client_id` (unique)
- `agent_id`
- `project_id`
- `buyer_id`

**Relationships**:
- Client → belongs to one Agent
- Client → optionally belongs to one Project
- Client → optionally assigned one Unit
- Client → optionally linked to one Buyer (user)
- Client → has many Documents
- Client → receives many Activities

---

### 5. TIMELINE

**Collection**: `timelines` ← **CANONICAL** (deprecate `project_timelines`)

**Description**: A project's milestone timeline.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `timeline_id` | string | ✅ | Primary key, format: `tl_{uuid12}` |
| `project_id` | string | ✅ | FK → projects.project_id |
| `agent_id` | string | ✅ | FK → users.user_id |
| `name` | string | ❌ | Timeline name |
| `description` | string | ❌ | Description |
| `created_at` | datetime | ✅ | Creation timestamp |
| `updated_at` | datetime | ❌ | Last update timestamp |

**Indexes**:
- `timeline_id` (unique)
- `project_id` (unique - one timeline per project)

**Relationships**:
- Timeline → belongs to one Project
- Timeline → has many Steps

**Note**: Deprecate `project_timeline_id` field name. Use `timeline_id` everywhere.

---

### 6. TIMELINE_STEP

**Collection**: `timeline_steps` ← **CANONICAL** (deprecate `project_stages`)

**Description**: A milestone or phase within a timeline.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `step_id` | string | ✅ | Primary key, format: `step_{uuid12}` |
| `timeline_id` | string | ✅ | FK → timelines.timeline_id |
| `project_id` | string | ✅ | FK → projects.project_id (denormalized) |
| `name` | string | ✅ | Step name |
| `description` | string | ❌ | Description |
| `order` | integer | ✅ | Sort order |
| `status` | enum | ✅ | `"pending"`, `"in_progress"`, `"completed"` |
| `start_date` | string | ❌ | Planned start |
| `end_date` | string | ❌ | Planned end |
| `completed_at` | datetime | ❌ | Actual completion |
| `created_at` | datetime | ✅ | Creation timestamp |

**Indexes**:
- `step_id` (unique)
- `timeline_id`
- `project_id`
- `(timeline_id, order)`

**Relationships**:
- Step → belongs to one Timeline
- Step → has many Documents (linked activities)
- Step → has many Internal Notes

**Note**: API uses `stage_id` in URL paths for backward compatibility, but database field is `step_id`. Standardize to `step_id` everywhere in Phase 2.

---

### 7. DOCUMENT

**Collection**: `documents`

**Description**: A quote or invoice for a client.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `document_id` | string | ✅ | Primary key, format: `doc_{uuid12}` |
| `agent_id` | string | ✅ | FK → users.user_id |
| `client_id` | string | ✅ | FK → clients.client_id |
| `project_id` | string | ❌ | FK → projects.project_id |
| `doc_type` | enum | ✅ | `"quote"` or `"invoice"` |
| `status` | enum | ✅ | `"Draft"`, `"Sent"`, `"Approved"`, `"Change Requested"`, `"Rejected"`, `"Paid"` |
| `title` | string | ✅ | Document title |
| `amount` | number | ❌ | Total amount |
| `currency` | string | ❌ | Currency code (CHF, EUR) |
| `items` | array | ❌ | Line items |
| `supplier_name` | string | ❌ | Supplier |
| `due_date` | string | ❌ | Payment due date |
| `validity_date` | string | ❌ | Quote validity date |
| `pdf_path` | string | ❌ | Original PDF path |
| `created_at` | datetime | ✅ | Creation timestamp |
| `sent_at` | datetime | ❌ | When sent to client |
| `approved_at` | datetime | ❌ | When approved |
| `paid_at` | datetime | ❌ | When marked paid |

**Indexes**:
- `document_id` (unique)
- `agent_id`
- `client_id`
- `project_id`
- `status`

**Relationships**:
- Document → belongs to one Agent
- Document → belongs to one Client
- Document → optionally belongs to one Project

---

### 8. ACTIVITY

**Collection**: `activities`

**Description**: A message, update, or notification sent to clients.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `activity_id` | string | ✅ | Primary key, format: `act_{uuid12}` |
| `agent_id` | string | ✅ | FK → users.user_id |
| `project_id` | string | ❌ | FK → projects.project_id |
| `author_id` | string | ✅ | FK → users.user_id (creator) |
| `type` | enum | ✅ | `"message"`, `"update"`, `"document"`, `"milestone"` |
| `title` | string | ❌ | Activity title |
| `content` | string | ✅ | Activity content |
| `attachments` | array | ❌ | File attachments |
| `visibility` | enum | ✅ | `"all"`, `"selected"` |
| `created_at` | datetime | ✅ | Creation timestamp |

**Indexes**:
- `activity_id` (unique)
- `agent_id`
- `project_id`
- `created_at`

**Relationships**:
- Activity → belongs to one Agent
- Activity → optionally belongs to one Project
- Activity → has many Recipients
- Activity → has many Replies

---

### 9. ACTIVITY_RECIPIENT

**Collection**: `activity_recipients`

**Description**: Links activities to specific client recipients.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `activity_id` | string | ✅ | FK → activities.activity_id |
| `client_id` | string | ✅ | FK → clients.client_id |
| `read_at` | datetime | ❌ | When client read it |

**Indexes**:
- `(activity_id, client_id)` (unique)
- `client_id`

---

### 10. NOTIFICATION

**Collection**: `notifications`

**Description**: In-app notifications for users.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `notification_id` | string | ✅ | Primary key |
| `user_id` | string | ✅ | FK → users.user_id (recipient) |
| `type` | string | ✅ | Notification type |
| `title` | string | ✅ | Title |
| `message` | string | ✅ | Message body |
| `link` | string | ❌ | Navigation link |
| `read` | boolean | ✅ | Read status |
| `created_at` | datetime | ✅ | Creation timestamp |

**Indexes**:
- `notification_id` (unique)
- `user_id`
- `(user_id, read)`

---

### 11. VAULT_DOCUMENT

**Collection**: `vault_documents`

**Description**: General document storage (contracts, plans, etc.).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `vault_id` | string | ✅ | Primary key |
| `agent_id` | string | ✅ | FK → users.user_id |
| `project_id` | string | ❌ | FK → projects.project_id |
| `name` | string | ✅ | Document name |
| `category` | string | ✅ | Category |
| `file_path` | string | ✅ | File storage path |
| `file_type` | string | ✅ | MIME type |
| `access_level` | enum | ✅ | `"private"`, `"shared"` |
| `shared_with_clients` | array | ❌ | List of client_ids |
| `created_at` | datetime | ✅ | Creation timestamp |

**Indexes**:
- `vault_id` (unique)
- `agent_id`
- `project_id`

---

### 12. TEAM_MEMBER

**Collection**: `team_members`

**Description**: Project team contacts (suppliers, contractors, etc.).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `member_id` | string | ✅ | Primary key |
| `agent_id` | string | ✅ | FK → users.user_id |
| `project_id` | string | ✅ | FK → projects.project_id |
| `name` | string | ✅ | Contact name |
| `role` | string | ✅ | Role/title |
| `company` | string | ❌ | Company name |
| `email` | string | ❌ | Email |
| `phone` | string | ❌ | Phone |
| `created_at` | datetime | ✅ | Creation timestamp |

**Indexes**:
- `member_id` (unique)
- `project_id`

---

## Deprecated Structures (TO REMOVE)

| Structure | Replacement | Migration |
|-----------|-------------|-----------|
| `db.project_units` | `db.units` | Rename collection |
| `db.project_stages` | `db.timeline_steps` | Migrate data, delete |
| `db.project_timelines` | `db.timelines` | Rename collection |
| `project_timeline_id` field | `timeline_id` | Rename field |
| `stage_id` in API | `step_id` | Update routes |
| `is_demo` field | Database separation | Remove after migration |

---

## Entity Relationship Diagram

```
┌──────────┐       ┌──────────┐       ┌──────────┐
│  USER    │       │ PROJECT  │       │   UNIT   │
│ (agent)  │──────<│          │>──────│          │
└──────────┘  owns └──────────┘  has  └──────────┘
     │                  │                  │
     │                  │                  │assigned
     │                  │                  │
     │            ┌─────┴─────┐            │
     │            ▼           ▼            ▼
     │       ┌────────┐  ┌────────┐  ┌──────────┐
     └──────>│TIMELINE│  │  TEAM  │  │  CLIENT  │
      owns   │        │  │ MEMBER │  │          │
             └────────┘  └────────┘  └──────────┘
                  │                       │
                  │has                    │has
                  ▼                       ▼
             ┌────────┐             ┌──────────┐
             │  STEP  │             │ DOCUMENT │
             │        │             │          │
             └────────┘             └──────────┘

┌──────────┐       ┌────────────────┐
│ ACTIVITY │──────>│ACTIVITY_RECIPNT│
│          │       │                │
└──────────┘       └────────────────┘
     │
     └───────────> NOTIFICATION (triggered)

┌──────────────┐
│VAULT_DOCUMENT│
│              │
└──────────────┘
```

---

## Vocabulary Standard

| Term | Definition | Collection |
|------|------------|------------|
| **User** | Authentication identity | `users` |
| **Agent** | Property manager (user with role=agent) | `users` |
| **Buyer** | Client with portal access (user with role=buyer) | `users` |
| **Project** | Real estate development | `projects` |
| **Unit** | Individual property unit | `units` |
| **Client** | Property purchaser record | `clients` |
| **Timeline** | Project milestone schedule | `timelines` |
| **Step** | Single milestone in timeline | `timeline_steps` |
| **Document** | Quote or invoice | `documents` |
| **Activity** | Message/update to clients | `activities` |
| **Vault** | Document storage | `vault_documents` |
| **Team Member** | Project contact | `team_members` |
| **Notification** | In-app alert | `notifications` |

**Forbidden Terms**:
- "Stage" → Use "Step"
- "project_timeline_id" → Use "timeline_id"
- "project_units" → Use "units"
- "is_demo" in queries → Use database separation

---

*This is the authoritative schema document. All code must conform to these definitions.*
