# Evohome CMP — Prioritized Roadmap

## P0 — Phase 1: Canonical Core COMPLETE (2026-04-11)
- Unit, Project, Timeline, TimelineStep, Client
- 33/33 tests passed

## P0 — Phase 2: Content Layer COMPLETE (2026-04-11)
- Activity, Document, VaultDocument, Notification
- 32/32 tests passed

## P0 — Phase 3: Orchestration COMPLETE (2026-04-11)
- Command Service rebuilt as pure routing brain
- notification_bridge.py eliminated
- notification_service.py is canonical notification module
- is_demo purged from all orchestration code
- 20/20 tests passed
- Notification contract fix: response shape, is_read field, DB migration (19/19)

## P1 — Legacy Cleanup COMPLETE (2026-04-11)
- 9 dead V1 route files deleted (activities, clients, documents, notifications, steps, timeline_view, timelines, vault, projects)
- Team endpoints extracted into team_v2.py + team_service.py (zero is_demo)
- routes/workflows.py + workflow_service.py sanitized (10 is_demo refs removed)
- Dead create_notification imports removed from 10 active routes
- email_service.create_notification shim removed
- 33/33 tests passed

## P2 — Phase 4: Commercial Systems
- **Billing** module canonical rebuild
- **Plan/Upgrade** workflow rebuild
- Stripe integration hardening

## P3 — Phase 5: Optimization
- AI Precision Enhancements
- Dashboard performance improvements
- Query optimization

## Backlog
- `is_demo` cleanup in non-canonical files (auth.py, email_service.py, helpers.py, etc.)
- Frontend canonical alignment (remove is_demo references in React components)
- Test coverage expansion
