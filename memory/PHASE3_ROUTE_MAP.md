# Phase 3 — Orchestration Route Map

## Command Flow (Canonical)

```
User Input
  |
  v
POST /api/command/interpret         [commands.py — thin route]
  |  Validates auth, delegates to CommandInterpreter
  v
CommandInterpreter.interpret()      [command_service.py — pure function]
  |  1. classify_intent (rule-based)
  |  2. get_tool definition
  |  3. extract_fields_from_text
  |  4. resolve_entities (project/client names)
  |  5. validate via tool.validate()
  |  6. compute missing_fields
  v
CommandPlan (no side effects)
  |
  v
POST /api/command/draft             [commands.py — thin route]
  |  Validates auth, delegates to CommandExecutor.create_draft
  v
CommandExecutor.create_draft()      [command_service.py]
  |  Builds draft_data via tool.build_draft_data()
  |  Writes to command_drafts collection (draft management only)
  v
CommandDraft {status: pending}
  |
  v
POST /api/command/execute           [commands.py — thin route]
  |  Validates auth + idempotency check
  v
CommandExecutor.execute_draft()     [command_service.py]
  |  1. Fetch draft, verify status + ownership
  |  2. Mark confirmed
  |  3. _route_to_service() — PURE ROUTING
  v
_route_to_service()
  |
  +--[QUOTE/INVOICE intent]--> _route_document()
  |     --> document_service.create_document()   [canonical Phase 2 service]
  |
  +--[MESSAGE intent]--> _route_activity()
  |     --> activity_service.create_draft_activity()  [canonical Phase 2 service]
  |
  v
Result {type, id, redirect}
```

## Notification Flow (Canonical)

```
Phase 2 Service (document_service, activity_service, vault_service)
  |
  v
notification_service.emit_notification()   [canonical write]
  |  Creates notification in notifications collection
  |  No is_demo parameter
  v

notification_service.emit_email()          [delivery side-effect]
  |  Lazy import: email_service.send_notification_email
  v

notification_service.emit_realtime()       [delivery side-effect]
  |  Lazy import: realtime_service.notify_realtime
  v
```

## Endpoints

| Method | Path | Route File | Service |
|--------|------|------------|---------|
| POST | /api/command/interpret | commands.py | command_service.CommandInterpreter |
| POST | /api/command/draft | commands.py | command_service.CommandExecutor.create_draft |
| POST | /api/command/execute | commands.py | command_service.CommandExecutor.execute_draft |
| GET | /api/command/draft/{id} | commands.py | DB read (command_drafts) |
| GET | /api/command/drafts | commands.py | DB read (command_drafts) |
| GET | /api/command/tools | commands.py | TOOL_REGISTRY |
| GET | /api/command/logs | commands.py | DB read (command_logs) |
| GET | /api/command/history | commands.py | DB read (command_drafts + extraction_cache) |
| POST | /api/command/draft/auto-save | commands.py | DB upsert (command_drafts_autosave) |
| GET | /api/command/draft/auto-save/{id} | commands.py | DB read (command_drafts_autosave) |
| GET | /api/notifications | notifications_v2.py | notification_service.list_notifications |
| PATCH | /api/notifications/{id}/read | notifications_v2.py | notification_service.mark_read |
| PATCH | /api/notifications/read-all | notifications_v2.py | notification_service.mark_all_read |

## Direct DB Writes Removed from command_service.py

| Old Method | Old Behavior | New Behavior |
|-----------|-------------|-------------|
| `_create_document()` | Direct insert to `documents` collection with `is_demo` field | Deleted. Routes to `document_service.create_document()` |
| `_create_feed_activity()` | Direct insert to `activities` collection with `is_demo` field | Deleted. Routes to `activity_service.create_draft_activity()` |

## is_demo Purge — Phase 3 Scope

| File | Before | After |
|------|--------|-------|
| command_service.py | 12 occurrences (execute_draft, _execute_by_intent, _create_document, _create_feed_activity) | 0 |
| commands.py | 3 occurrences (execute endpoint, history, import) | 0 (import of get_is_demo removed) |
| notification_service.py | N/A (new) | 0 (canonical, no is_demo) |
| notification_bridge.py | 1 (is_demo=False wrapper) | DELETED |
| realtime_service.py | 2 (send_milestone_notification param + call) | 0 |
| timelines_v2.py | 1 (is_demo=False call) | 0 |

## Deleted Files

- `/app/backend/services/notification_bridge.py` — temporary adapter, no longer needed

## Conflict Report

No orchestration action depends on legacy workflow logic (`routes/workflows.py`).
Phase 3 orchestration is self-contained and routes exclusively to Phase 1/2 canonical services.
