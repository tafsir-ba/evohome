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

## P1 — Legacy Cleanup
- Delete legacy V1 route files (projects.py CRUD, timelines.py, activities.py, documents.py, vault.py, notifications.py, timeline_view.py, steps.py, clients.py)
- Clean routes/workflows.py is_demo contamination
- Clean routes/billing.py is_demo contamination

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
