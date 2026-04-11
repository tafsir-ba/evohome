# Evohome CMP — Prioritized Roadmap

## COMPLETE — Canonical Rebuild (Phases 1-4)
## COMPLETE — Phase 5: UX Refinement (2026-04-11)
## COMPLETE — Code Quality Pass (2026-04-11)
## COMPLETE — Performance Optimization (2026-04-11) — 6.3s → 1.0s
## COMPLETE — AgentHomePage Decomposition (2026-04-11) — 2,436 → 229 lines
## COMPLETE — Stable React Keys (2026-04-11)

## COMPLETE — Stripe Webhook Smoke Test (2026-04-11)
- STRIPE_WEBHOOK_SECRET configured (`whsec_...`)
- Fixed Stripe Event object attribute access bug in billing_service.py
- 6/6 smoke tests passed:
  1. Unsigned requests rejected (signature verification works)
  2. checkout.session.completed → subscription activated
  3. customer.subscription.updated → status synced
  4. customer.subscription.deleted → downgraded to free
  5. invoice.payment_failed → marked past_due
  6. Unhandled events accepted gracefully
- Database mutations verified end-to-end
- Production endpoint: `https://app.evo-home.ch/api/billing/webhook`

## P2 — Code Quality
- [ ] Hook dependency warnings (74 instances — per-component audit)

## P3 — Product Compounding
- [ ] Email digest notifications
- [ ] Reporting/export features
- [ ] AI-powered command enhancements
- [ ] Buyer feed optimization (only if measured slowness)
