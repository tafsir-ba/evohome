# Phase B.2 Addendum: Content and Document Layer
## Canonical Schema Extension - SSOT Completion

**Version**: 1.1  
**Date**: January 2026  
**Status**: NORMATIVE - Extends DELIVERABLE_1_CANONICAL_SCHEMA.md

---

## Purpose

This addendum completes the Single Source of Truth by defining the **content layer**:
- Activities (updates, messages)
- Documents (quotes, invoices)
- Attachments and media
- Vault documents
- Notifications
- Visibility and ownership rules

Without this layer, the SSOT only covers structural entities. This addendum ensures **every data object** in the system has a canonical definition.

---

## Content Layer Overview

| Entity | Type | Owner | Parent | Visibility |
|--------|------|-------|--------|------------|
| Activity | First-class | Agent | Project (optional) | Configurable |
| Activity Reply | Subtype | User | Activity | Inherits from parent |
| Document | First-class | Agent | Client | Buyer-facing |
| Document Attachment | Subtype | Document | Document | Inherits from parent |
| Vault Document | First-class | Agent | Project (optional) | Configurable |
| Notification | Derived | System | User | Private to recipient |
| Timeline Step Document | Junction | Agent | Step + Activity | Buyer-facing |
| Timeline Step Note | Subtype | Agent | Step | Internal only |

---

## Entity Definitions

### 13. ACTIVITY

**Collection**: `activities`

**Type**: First-class entity

**Description**: A message, update, or announcement sent by an agent. Can be broadcast to multiple clients or targeted to specific ones.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `activity_id` | string | ✅ | Primary key, format: `act_{uuid12}` |
| `agent_id` | string | ✅ | FK → users.user_id (owner) |
| `author_id` | string | ✅ | FK → users.user_id (creator, may differ from agent) |
| `project_id` | string | ❌ | FK → projects.project_id (scoping) |
| `unit_id` | string | ❌ | FK → units.unit_id (optional unit context) |
| `type` | enum | ✅ | See Activity Types below |
| `title` | string | ❌ | Activity title/subject |
| `content` | string | ✅ | Activity body (markdown supported) |
| `attachments` | array | ❌ | Inline attachments (see Attachment schema) |
| `visibility` | enum | ✅ | `"all"`, `"selected"`, `"internal"` |
| `status` | enum | ✅ | `"draft"`, `"published"` |
| `created_at` | datetime | ✅ | Creation timestamp |
| `published_at` | datetime | ❌ | When published |
| `updated_at` | datetime | ❌ | Last edit timestamp |

**Activity Types**:
| Type | Description | Buyer Visible |
|------|-------------|---------------|
| `message` | General communication | Yes |
| `update` | Project/construction update | Yes |
| `milestone` | Timeline milestone notification | Yes |
| `document` | Document-related activity | Yes |
| `internal_note` | Agent-only note | **No** |
| `system` | System-generated | Configurable |

**Visibility Rules**:
| Visibility | Meaning |
|------------|---------|
| `all` | All clients in project see it |
| `selected` | Only clients in `activity_recipients` see it |
| `internal` | Agent-only, never shown to buyers |

**Indexes**:
- `activity_id` (unique)
- `agent_id`
- `project_id`
- `created_at`
- `(project_id, visibility, created_at)`

**Relationships**:
- Activity → belongs to one Agent (owner)
- Activity → optionally scoped to one Project
- Activity → has many Recipients (junction table)
- Activity → has many Replies
- Activity → has many inline Attachments

**Lifecycle**:
```
Draft → Published → [Edited] → [Deleted]
```

---

### 14. ACTIVITY_RECIPIENT

**Collection**: `activity_recipients`

**Type**: Junction table

**Description**: Links activities to specific client recipients. Defines who can see an activity when `visibility = "selected"`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `activity_id` | string | ✅ | FK → activities.activity_id |
| `client_id` | string | ✅ | FK → clients.client_id |
| `read_at` | datetime | ❌ | When client viewed it |
| `created_at` | datetime | ✅ | When recipient was added |

**Indexes**:
- `(activity_id, client_id)` (unique compound)
- `client_id`
- `(client_id, read_at)`

**Relationships**:
- Junction between Activity and Client
- Many-to-many relationship

---

### 15. ACTIVITY_REPLY

**Collection**: `activity_replies`

**Type**: Subtype (child of Activity)

**Description**: A reply to an activity, creating a thread.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `reply_id` | string | ✅ | Primary key, format: `reply_{uuid12}` |
| `activity_id` | string | ✅ | FK → activities.activity_id (parent) |
| `author_id` | string | ✅ | FK → users.user_id (can be agent or buyer) |
| `author_role` | enum | ✅ | `"agent"` or `"buyer"` |
| `content` | string | ✅ | Reply text |
| `attachments` | array | ❌ | Inline attachments |
| `created_at` | datetime | ✅ | Creation timestamp |

**Indexes**:
- `reply_id` (unique)
- `activity_id`
- `(activity_id, created_at)`

**Relationships**:
- Reply → belongs to one Activity
- Reply → created by one User

**Visibility**: Inherits from parent Activity

---

### 16. DOCUMENT

**Collection**: `documents`

**Type**: First-class entity

**Description**: A financial document (quote or invoice) created by an agent for a client. This is the **unified document model** - quotes and invoices are distinguished by `doc_type`, not separate collections.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `document_id` | string | ✅ | Primary key, format: `doc_{uuid12}` |
| `agent_id` | string | ✅ | FK → users.user_id (owner) |
| `client_id` | string | ✅ | FK → clients.client_id (recipient) |
| `project_id` | string | ❌ | FK → projects.project_id (optional scoping) |
| `doc_type` | enum | ✅ | `"quote"` or `"invoice"` |
| `status` | enum | ✅ | See Document Status below |
| `title` | string | ✅ | Document title |
| `description` | string | ❌ | Description/notes |
| `amount` | number | ❌ | Total amount |
| `currency` | string | ❌ | Currency code (CHF, EUR, USD) |
| `items` | array | ❌ | Line items (see LineItem schema) |
| `supplier_name` | string | ❌ | Supplier/vendor name |
| `supplier_address` | string | ❌ | Supplier address |
| `hero_image` | string | ❌ | Hero image URL |
| `pdf_path` | string | ❌ | Original uploaded PDF path |
| `generated_pdf_path` | string | ❌ | System-generated PDF path |
| `qr_code_path` | string | ❌ | Swiss QR code image (invoices) |
| `due_date` | string | ❌ | Payment due date (invoices) |
| `validity_date` | string | ❌ | Quote validity date (quotes) |
| `payment_reference` | string | ❌ | Payment reference number |
| `iban` | string | ❌ | Bank account for payment |
| `created_at` | datetime | ✅ | Creation timestamp |
| `sent_at` | datetime | ❌ | When sent to client |
| `approved_at` | datetime | ❌ | When approved by client |
| `rejected_at` | datetime | ❌ | When rejected |
| `paid_at` | datetime | ❌ | When marked paid |
| `change_requested_at` | datetime | ❌ | When client requested changes |
| `change_reason` | string | ❌ | Reason for change request |

**Document Status (Lifecycle)**:
```
                    ┌──────────────────┐
                    │      Draft       │
                    └────────┬─────────┘
                             │ send
                             ▼
                    ┌──────────────────┐
                    │       Sent       │◄─────────────┐
                    └────────┬─────────┘              │
                             │                        │ revert
            ┌────────────────┼────────────────┐       │
            ▼                ▼                ▼       │
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐│
    │   Approved   │ │   Rejected   │ │Change Request├┘
    └──────┬───────┘ └──────────────┘ └──────────────┘
           │ (invoice only)
           ▼
    ┌──────────────┐
    │     Paid     │
    └──────────────┘
```

**Status Values**:
| Status | Description | Applies To |
|--------|-------------|------------|
| `Draft` | Not yet sent | Both |
| `Sent` | Sent to client, awaiting response | Both |
| `Approved` | Client approved | Both |
| `Rejected` | Client rejected | Both |
| `Change Requested` | Client wants modifications | Both |
| `Paid` | Payment received | Invoice only |

**Line Item Schema**:
```json
{
  "description": "Kitchen installation",
  "quantity": 1,
  "unit_price": 15000,
  "total": 15000
}
```

**Indexes**:
- `document_id` (unique)
- `agent_id`
- `client_id`
- `project_id`
- `status`
- `doc_type`
- `(agent_id, doc_type, status)`
- `(client_id, status)`

**Relationships**:
- Document → belongs to one Agent (owner)
- Document → belongs to one Client (recipient)
- Document → optionally scoped to one Project
- Document → may have one parent Document (for revisions)

**Visibility**: Always buyer-facing when status ≠ Draft

---

### 17. ATTACHMENT

**Type**: Embedded schema (not a collection)

**Description**: An inline attachment within an Activity, Reply, or Document. Stored as embedded array, not separate collection.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `attachment_id` | string | ✅ | Unique ID, format: `att_{uuid8}` |
| `name` | string | ✅ | Original filename |
| `file_path` | string | ✅ | Storage path |
| `file_type` | string | ✅ | MIME type |
| `file_size` | number | ✅ | Size in bytes |
| `uploaded_at` | datetime | ✅ | Upload timestamp |

**Storage**: Embedded within parent document's `attachments` array.

**Visibility**: Inherits from parent entity.

**NOT a First-Class Entity**: Attachments do not have their own collection. They are always embedded within:
- Activity.attachments[]
- ActivityReply.attachments[]
- Document (as pdf_path, hero_image, etc.)

---

### 18. VAULT_DOCUMENT

**Collection**: `vault_documents`

**Type**: First-class entity

**Description**: A general-purpose document stored in the agent's vault. Unlike Documents (quotes/invoices), vault documents are for contracts, plans, permits, reports, etc.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `vault_id` | string | ✅ | Primary key, format: `vault_{uuid12}` |
| `agent_id` | string | ✅ | FK → users.user_id (owner) |
| `project_id` | string | ❌ | FK → projects.project_id (optional scoping) |
| `name` | string | ✅ | Document name |
| `description` | string | ❌ | Description |
| `category` | enum | ✅ | See Vault Categories |
| `file_path` | string | ✅ | Storage path |
| `file_type` | string | ✅ | MIME type |
| `file_size` | number | ❌ | Size in bytes |
| `access_level` | enum | ✅ | `"private"`, `"shared"` |
| `shared_with_clients` | array | ❌ | List of client_ids if shared |
| `doc_type` | enum | ❌ | `"general"`, `"action_required"` |
| `created_at` | datetime | ✅ | Upload timestamp |
| `updated_at` | datetime | ❌ | Last update |

**Vault Categories**:
| Category | Description |
|----------|-------------|
| `Contract` | Legal contracts |
| `Plan` | Architectural/floor plans |
| `Permit` | Building permits |
| `Report` | Inspection reports |
| `Photo` | Progress photos |
| `Other` | Miscellaneous |

**Access Levels**:
| Level | Description |
|-------|-------------|
| `private` | Agent-only, never visible to buyers |
| `shared` | Visible to clients in `shared_with_clients` list |

**Indexes**:
- `vault_id` (unique)
- `agent_id`
- `project_id`
- `category`
- `(agent_id, access_level)`

**Relationships**:
- Vault Document → belongs to one Agent
- Vault Document → optionally scoped to one Project
- Vault Document → optionally shared with many Clients

**Visibility Rules**:
```
IF access_level = "private" THEN
    Only agent can see
ELSE IF access_level = "shared" THEN
    Agent + clients in shared_with_clients[] can see
```

---

### 19. NOTIFICATION

**Collection**: `notifications`

**Type**: Derived entity (system-generated)

**Description**: An in-app notification for a user. Notifications are **derived** from actions on other entities - they are not created directly by users.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `notification_id` | string | ✅ | Primary key, format: `notif_{uuid12}` |
| `user_id` | string | ✅ | FK → users.user_id (recipient) |
| `type` | enum | ✅ | See Notification Types |
| `title` | string | ✅ | Notification title |
| `message` | string | ✅ | Notification body |
| `link` | string | ❌ | Navigation link |
| `reference_type` | string | ❌ | Entity type that triggered it |
| `reference_id` | string | ❌ | Entity ID that triggered it |
| `read` | boolean | ✅ | Read status (default: false) |
| `created_at` | datetime | ✅ | Creation timestamp |
| `read_at` | datetime | ❌ | When marked read |

**Notification Types**:
| Type | Trigger | Recipient |
|------|---------|-----------|
| `document_sent` | Document sent | Buyer |
| `document_approved` | Document approved | Agent |
| `document_rejected` | Document rejected | Agent |
| `document_change_requested` | Change requested | Agent |
| `document_paid` | Document paid | Agent |
| `activity_new` | New activity published | Buyer |
| `activity_reply` | Reply to activity | Agent or Buyer |
| `milestone_completed` | Timeline step completed | Buyer |
| `vault_shared` | Vault doc shared | Buyer |

**Derivation Rules**:
```
ON Document.status changed to 'Sent':
    CREATE Notification for buyer with type='document_sent'

ON Document.status changed to 'Approved':
    CREATE Notification for agent with type='document_approved'

ON Activity published with visibility='all' or 'selected':
    FOR EACH recipient client:
        CREATE Notification for buyer with type='activity_new'

ON TimelineStep.status changed to 'completed':
    FOR EACH client in project:
        CREATE Notification for buyer with type='milestone_completed'
```

**Indexes**:
- `notification_id` (unique)
- `user_id`
- `(user_id, read)`
- `(user_id, created_at)`

**Relationships**:
- Notification → belongs to one User (recipient)
- Notification → references one source entity (via reference_type/reference_id)

**Visibility**: Private to recipient user only

---

### 20. TIMELINE_STEP_DOCUMENT

**Collection**: `timeline_step_documents`

**Type**: Junction table

**Description**: Links a timeline step to an activity (document/update). This allows associating relevant documents and updates with specific milestones.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `step_id` | string | ✅ | FK → timeline_steps.step_id |
| `activity_id` | string | ✅ | FK → activities.activity_id |
| `created_at` | datetime | ✅ | When linked |
| `created_by` | string | ✅ | FK → users.user_id |

**Indexes**:
- `(step_id, activity_id)` (unique compound)
- `step_id`
- `activity_id`

**Relationships**:
- Junction between TimelineStep and Activity
- Many-to-many relationship

**Visibility**: Inherits from Activity visibility

---

### 21. TIMELINE_STEP_NOTE

**Collection**: `timeline_step_internal_notes`

**Type**: Subtype (child of TimelineStep)

**Description**: Internal notes on a timeline step. These are **never visible to buyers**.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `note_id` | string | ✅ | Primary key, format: `note_{uuid12}` |
| `step_id` | string | ✅ | FK → timeline_steps.step_id |
| `author_id` | string | ✅ | FK → users.user_id (agent) |
| `content` | string | ✅ | Note content |
| `created_at` | datetime | ✅ | Creation timestamp |

**Indexes**:
- `note_id` (unique)
- `step_id`
- `(step_id, created_at)`

**Relationships**:
- Note → belongs to one TimelineStep
- Note → created by one Agent

**Visibility**: **Internal only** - never visible to buyers

---

## Visibility Matrix

| Entity | Agent | Buyer (Linked) | Buyer (Unlinked) | Public |
|--------|-------|----------------|------------------|--------|
| Activity (visibility=all) | ✅ | ✅ | ❌ | ❌ |
| Activity (visibility=selected) | ✅ | If in recipients | ❌ | ❌ |
| Activity (visibility=internal) | ✅ | ❌ | ❌ | ❌ |
| Activity Reply | ✅ | If can see parent | ❌ | ❌ |
| Document (status=Draft) | ✅ | ❌ | ❌ | ❌ |
| Document (status≠Draft) | ✅ | If is client | ❌ | ❌ |
| Vault (access=private) | ✅ | ❌ | ❌ | ❌ |
| Vault (access=shared) | ✅ | If in shared_with | ❌ | ❌ |
| Notification | ❌ | If is recipient | ❌ | ❌ |
| Timeline Step Note | ✅ | ❌ | ❌ | ❌ |

---

## Ownership Rules

| Entity | Owner Field | Meaning |
|--------|-------------|---------|
| Activity | `agent_id` | Agent who owns/manages it |
| Activity Reply | `author_id` | User who wrote it |
| Document | `agent_id` | Agent who created it |
| Vault Document | `agent_id` | Agent who uploaded it |
| Notification | `user_id` | User who receives it |
| Timeline Step Note | `author_id` | Agent who wrote it |

**Rule**: The `agent_id` field always indicates the **owning agent**. The `author_id` field indicates who **created** the content (may be agent or buyer for replies).

---

## Parent-Child Relationships

```
Agent (user)
├── Project
│   ├── Unit
│   ├── Client ──────────────────────┐
│   ├── Timeline                      │
│   │   └── TimelineStep              │
│   │       ├── TimelineStepDocument ─┤─→ Activity
│   │       └── TimelineStepNote      │
│   ├── TeamMember                    │
│   └── VaultDocument ────────────────┤ (shared_with)
│                                     │
├── Activity ─────────────────────────┤ (recipients)
│   └── ActivityReply                 │
│                                     │
├── Document ─────────────────────────┘ (client_id)
│
└── Notification (derived, system-owned)
```

---

## Foreign Key Reference

| Entity | Field | References |
|--------|-------|------------|
| Activity | agent_id | users.user_id |
| Activity | author_id | users.user_id |
| Activity | project_id | projects.project_id |
| Activity | unit_id | units.unit_id |
| ActivityRecipient | activity_id | activities.activity_id |
| ActivityRecipient | client_id | clients.client_id |
| ActivityReply | activity_id | activities.activity_id |
| ActivityReply | author_id | users.user_id |
| Document | agent_id | users.user_id |
| Document | client_id | clients.client_id |
| Document | project_id | projects.project_id |
| VaultDocument | agent_id | users.user_id |
| VaultDocument | project_id | projects.project_id |
| VaultDocument | shared_with_clients[] | clients.client_id |
| Notification | user_id | users.user_id |
| TimelineStepDocument | step_id | timeline_steps.step_id |
| TimelineStepDocument | activity_id | activities.activity_id |
| TimelineStepNote | step_id | timeline_steps.step_id |
| TimelineStepNote | author_id | users.user_id |

---

## Summary: First-Class vs Subtype

| Entity | Classification | Has Own Collection | Parent |
|--------|----------------|-------------------|--------|
| Activity | First-class | ✅ `activities` | None (optional project) |
| ActivityRecipient | Junction | ✅ `activity_recipients` | Activity ↔ Client |
| ActivityReply | Subtype | ✅ `activity_replies` | Activity |
| Document | First-class | ✅ `documents` | None (linked to client) |
| Attachment | Embedded | ❌ (embedded array) | Activity, Reply, or Document |
| VaultDocument | First-class | ✅ `vault_documents` | None (optional project) |
| Notification | Derived | ✅ `notifications` | None (system-generated) |
| TimelineStepDocument | Junction | ✅ `timeline_step_documents` | Step ↔ Activity |
| TimelineStepNote | Subtype | ✅ `timeline_step_internal_notes` | TimelineStep |

---

## Deprecated Structures in Content Layer

| Structure | Status | Replacement |
|-----------|--------|-------------|
| Separate quotes/invoices collections | ❌ Never existed | `documents` with `doc_type` |
| `is_demo` in content queries | Deprecated | Database separation |

---

*Phase B.2 Addendum completed: January 2026*
*This document extends DELIVERABLE_1_CANONICAL_SCHEMA.md*
