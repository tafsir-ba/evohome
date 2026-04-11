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
- 20/20 + 19/19 tests passed

## P1 — Legacy Cleanup COMPLETE (2026-04-11)
- 9 dead V1 route files deleted
- Team extracted into team_v2.py + team_service.py
- Workflows sanitized, RESEND_API_KEY fix
- Dead imports cleaned, DB migration (127 docs)
- 33/33 + 24/24 tests passed

## Auth Surgery COMPLETE (2026-04-11)
- is_demo removed from user creation, JWT, session, auth responses
- Demo login uses demo_* user_id prefix (not is_demo field)
- get_is_demo + get_demo_filter deleted
- Response models cleaned (9 Pydantic models)
- Users collection migrated (20 docs)
- 20/20 tests passed

## NEXT — Invitations Surgery
- Remove is_demo from invitation creation/acceptance
- Stop writing is_demo into users/clients via onboarding

## NEXT — Demo.py Decision
- Kill, quarantine, or rewrite demo seeder
- Must not re-introduce is_demo into any collection

## P2 — Phase 4: Commercial Systems
- Billing module canonical rebuild
- Plan/Upgrade workflow rebuild
- Stripe integration hardening

## P3 — Phase 5: Optimization
- AI Precision Enhancements
- Dashboard performance improvements
- Query optimization

## Backlog
- Frontend canonical alignment (remove is_demo from AgentLayout.js, BuyerLayout.js)
- Workflows canonicalization (replace direct DB writes with service delegation)
- admin.py is_demo cleanup
- Test coverage expansion
