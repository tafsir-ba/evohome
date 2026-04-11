# Evohome - Real Estate Upgrade Management Platform

## Architecture
- **Backend**: FastAPI + Motor (MongoDB async) — canonical SSOT services, thin routes
- **Frontend**: React 18 + TailwindCSS + Shadcn/UI — decomposed dashboard
- **Database**: MongoDB Atlas (`evohome_cmp`)
- **Integrations**: OpenAI GPT-4o, Stripe (webhooks verified), Resend, Google OAuth

## Features Implemented
- Auth (JWT + Google OAuth), Projects/Units/Clients CRUD
- Documents: Quotes/Invoices with AI extraction, PDF generation, hero images
- Timelines/Workflows, Real-time Feed, Notifications
- Stripe billing (webhook verified), Team management, Vault
- **FEAT-002**: Unified Change Request System (canonical, shared across all entity types)
- **FEAT-001**: Decisions Module (full lifecycle: create → send → approve/reject/change-request → close)
- Control Tower dashboard, decomposed architecture

## Data Model
- `decisions` + `decision_recipients`: Formal approval requests with lifecycle tracking
- `change_requests`: Canonical threaded conversations for buyer-agent exchange
- `documents`, `clients`, `projects`, `units`, `users`, `activities`, `timelines`, `notifications`, `vault_documents`, `team_members`

## Test Accounts
- Agent: agent@evohome-test.ch / Evohome2026!
- Buyer: buyer@evohome-test.ch / Evohome2026!

## Remaining
- P2: Hook dependency warnings, BuyerTimeline decomposition
- P3: Email digests, reporting/export

---
Last Updated: April 11, 2026
