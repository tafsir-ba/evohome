# Evohome - Real Estate Upgrade Management Platform

## Original Problem Statement
Build a SaaS platform for real estate agents to manage client upgrades, track construction progress, and streamline communication with buyers.

## Architecture (Post-Decomposition — April 2026)
```
/app/backend/
├── server.py              # Slim orchestrator + index management
├── models/schemas.py      # Pydantic models (explicit exports in __init__.py)
├── services/              # Canonical domain logic (batch_enrich_activities, billing_service, etc.)
├── routes/                # Thin route layer (explicit imports only)
├── core/                  # config, auth, access_control, rate_limit, monitoring
├── tests/conftest.py      # Centralized test credentials
└── uploads/

/app/frontend/src/
├── pages/agent/
│   └── AgentHomePage.js   # 229 lines — thin orchestrator (was 2,436)
├── components/
│   ├── dashboard/         # Decomposed dashboard components
│   │   ├── ControlTower.js       (177 lines — stats, action cards, KPI)
│   │   ├── CommandBar.js         (428 lines — text/voice/file input)
│   │   ├── ActionPreviewDrawer.js(510 lines — extraction, classification, execution)
│   │   ├── WorkflowDialog.js     (397 lines — workflow execution)
│   │   ├── RecentActivity.js     (78 lines — pure presentational)
│   │   └── utils.js              (61 lines — shared helpers)
│   ├── Feed.js, CreateActivityDialog.js, AgentLayout
│   └── ui/                # Shadcn components
└── context/               # AuthContext, SettingsContext, DataContext
```

## What's Been Implemented
- Complete Real Estate SaaS with JWT + Google OAuth auth
- Projects/Units/Clients CRUD, Document Management (AI extraction), Timeline/Workflow
- Stripe billing (canonical billing_service.py)
- Real-time feed with batch enrichment (6.3s → 1.0s)
- Control Tower dashboard, decomposed component architecture
- Code quality: explicit imports, no circular deps, env-var secrets, stable React keys

## Tech Stack
- Frontend: React 18, TailwindCSS, Shadcn/UI
- Backend: FastAPI, Motor (MongoDB async)
- Database: MongoDB (indexed for hot query paths)
- Integrations: OpenAI GPT-4o, Stripe, Resend, Google OAuth

## Pending/Backlog

### P1 — Production Hardening
- [ ] Stripe Webhook smoke test (requires STRIPE_WEBHOOK_SECRET)

### P2 — Code Quality
- [ ] Hook dependency warnings (74 instances — careful per-component audit)

### P3 — Product Compounding
- [ ] Email digest notifications
- [ ] Reporting/export features
- [ ] AI-powered command enhancements

---
Last Updated: April 11, 2026
