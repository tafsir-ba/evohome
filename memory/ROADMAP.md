# Evohome CMP — Prioritized Roadmap

## COMPLETE — Canonical Rebuild (Phases 1-4)
- Core, Content, Orchestration, Billing — all canonical
- is_demo fully purged, SSOT architecture

## COMPLETE — Phase 5 Sprint 1: UX Refinement (2026-04-11)
- Feed skeleton bug fixed, Feed promoted to primary nav
- Dashboard → Control Tower (action cards + KPI strip)
- Billing/Settings cleanup

## COMPLETE — Code Quality Pass (2026-04-11)
- Wildcard → explicit imports, circular import fixed
- Google OAuth client ID → env var
- Feed.js CreateActivityDialog extracted
- Test fixtures centralized

## COMPLETE — Performance Optimization (2026-04-11)
- Activities endpoint: 6.3s → 1.0s via batch_enrich_activities()
- MongoDB indexes for hot query paths

## COMPLETE — AgentHomePage Decomposition (2026-04-11)
- 2,436 → 229 lines (90.6% reduction)
- 5 components: ControlTower, CommandBar, ActionPreviewDrawer, WorkflowDialog, RecentActivity
- Zero regressions (10/10 tests passed)

## COMPLETE — Stable React Keys (2026-04-11)
- Replaced array-index keys with stable identifiers in:
  - InvoiceDetail, QuoteDetail (line items → description+index composite)
  - Billing (plan features → feature string)
  - Workflow (manual steps → step.id, editing phases → phase.name)
  - Timeline (extracted stages → stage.title)

## NEXT — P1: Production Hardening
- [ ] Stripe Webhook smoke test (needs STRIPE_WEBHOOK_SECRET)

## P2 — Code Quality
- [ ] Hook dependency warnings (74 instances — per-component audit)

## P3 — Product Compounding
- [ ] Email digest notifications
- [ ] Reporting/export features
- [ ] AI-powered command enhancements
- [ ] Buyer feed optimization (only if measured slowness)
