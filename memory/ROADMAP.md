# Evohome CMP — Prioritized Roadmap

## P0 — Phase 1: Canonical Core COMPLETE (2026-04-11)
- Unit, Project, Timeline, TimelineStep, Client
- 33/33 tests passed

## P0 — Phase 2: Content Layer COMPLETE (2026-04-11)
- Activity, Document, VaultDocument, Notification
- 32/32 tests passed

## P1 — Phase 3: Orchestration
- **Comment Center** rebuild as orchestration hub
- Cross-module coordination patterns
- `notification_bridge.py` cleanup (remove `is_demo=False` wrapper)

## P2 — Phase 4: Commercial Systems
- **Billing** module canonical rebuild
- **Plan/Upgrade** workflow rebuild
- Stripe integration hardening

## P3 — Phase 5: Optimization
- AI Precision Enhancements
- Dashboard performance improvements
- Query optimization

## Backlog
- `is_demo` cleanup in non-canonical files (auth.py, email_service.py, realtime_service.py, etc.)
- Legacy route file deletion (projects.py CRUD removed, timelines.py fully replaced, etc.)
- Frontend canonical alignment (remove is_demo references in React components)
- Test coverage expansion
