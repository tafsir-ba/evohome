# Evohome CMP — Prioritized Roadmap

## COMPLETE — Canonical Rebuild (Phases 1-4)
- Core, Content, Orchestration, Billing — all canonical
- is_demo fully purged
- SSOT architecture with thin routes

## COMPLETE — Phase 5 Sprint 1: UX Refinement (2026-04-11)
- Feed skeleton bug fixed (N+1 query removal)
- Feed promoted to primary navigation
- Dashboard transformed to Control Tower (action cards + KPI strip)
- Billing UX cleanup (removed Sync, removed duplicate section)
- Settings cleanup (removed duplicate plan grid, added redirect)
- 9/9 tests passed (iteration_17)

## NEXT — P1: Production Hardening
- [ ] Stripe Webhook smoke test (needs user STRIPE_WEBHOOK_SECRET)
- [ ] Backend activities endpoint optimization (6.3s → target <1s via batch queries)

## P2 — Product Compounding
- [ ] Email digest notifications
- [ ] Reporting/export features
- [ ] AI-powered command enhancements

## Backlog
- [ ] Backend: Optimize activity_service.enrich_activity (N+1 DB queries per activity)
- [ ] Frontend: Buyer dashboard UX review
- [ ] Test coverage expansion
