# Evohome - Real Estate Upgrade Management Platform

## Architecture
- **Backend**: FastAPI + Motor (MongoDB async) — canonical SSOT services, thin routes
- **Frontend**: React 18 + TailwindCSS + Shadcn/UI — decomposed dashboard components
- **Database**: MongoDB Atlas (`evohome_cmp` — isolated from website `evohome`)
- **Integrations**: OpenAI GPT-4o, Stripe (webhooks verified), Resend, Google OAuth

## What's Been Implemented
- Complete Real Estate SaaS: auth, projects/units/clients, documents (AI extraction), timelines/workflows
- Stripe billing with webhook signature verification (production-ready)
- Control Tower dashboard, decomposed into 5 clean components
- Real-time feed with batch enrichment (1.0s response)
- **Unified Change Request System** (FEAT-002): canonical change_request_service, full lifecycle (create/respond/resolve/close), ChangeRequestPanel component on invoice/quote detail pages
- Code quality: explicit imports, no circular deps, env-var secrets, stable React keys, centralized auth headers

## Production Status
- Backend: Canonical, clean, all endpoints verified
- Frontend: Decomposed, auth headers applied to all 23+ files
- Billing: Webhook endpoint live at `https://app.evo-home.ch/api/billing/webhook`
- Database: Isolated `evohome_cmp` (no cross-project contamination)

## Remaining
- **FEAT-001**: Decisions Module (next — builds on FEAT-002 change request foundation)
- P2: Hook dependency warnings (74 instances)
- P3: Email digests, reporting/export

---
Last Updated: April 11, 2026
