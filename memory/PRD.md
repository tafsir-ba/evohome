# Evohome - Real Estate Upgrade Management Platform

## Original Problem Statement
Build a SaaS platform for real estate agents to manage client upgrades, track construction progress, and streamline communication with buyers.

## Core Requirements
1. **Authentication**: JWT + Google OAuth login for agents and buyers
2. **Project Management**: Agents manage projects, units, and clients
3. **Document Management**: Create, send, and track quotes/invoices with AI extraction
4. **Timeline/Workflow**: Construction phase tracking with templates
5. **Communication**: Real-time updates, notifications, activity feed
6. **Billing**: Stripe subscription tiers (Free, Starter, Pro, Enterprise)

## Architecture (Post-Canonical Rebuild — April 2026)
```
/app/backend/
├── server.py              # Slim orchestrator
├── database.py            # Shared MongoDB connection
├── helpers.py             # Utility functions
├── models/
│   └── schemas.py         # All Pydantic models (explicit exports in __init__.py)
├── services/              # Strict canonical domain logic
│   ├── activity_service, document_service, vault_service
│   ├── notification_service, project_service, client_service
│   ├── timeline_service, step_service, team_service, unit_service
│   ├── command_service, workflow_service, billing_service
│   ├── email_service, realtime_service, qr_service, ai_service
├── routes/                # Thin route layer (explicit imports only)
├── core/                  # config, auth, access_control, rate_limit, monitoring, responses
├── tests/
│   └── conftest.py        # Centralized test credentials fixtures
└── uploads/
/app/frontend/
└── src/
    ├── pages/agent/       # AgentHomePage (Control Tower), AgentFeed, AgentBilling, AgentSettings
    ├── pages/buyer/       # BuyerDashboard, BuyerTimeline
    ├── components/        # Feed.js, CreateActivityDialog.js, AgentLayout, NotificationCenter
    └── context/           # AuthContext (env-var OAuth), SettingsContext, DataContext
```

## What's Been Implemented

### Core Platform
- JWT + Google OAuth authentication
- Password reset flow via Resend
- Agent dashboard with WebSocket real-time updates
- Projects, units, clients CRUD
- Analytics dashboard
- Team member invitation system

### Document Management
- Quotes/invoices with AI extraction (OpenAI GPT-4o)
- PDF generation with QR codes
- Document status workflow, In-app PDF viewer

### Communication
- Real-time activity feed (Feed.js — lazy-load replies, extracted CreateActivityDialog)
- Email notifications via Resend
- In-app notifications with WebSocket

### Agent Command Workspace
- Command bar with text/voice/file input
- Rule-based intent classification
- Draft-first system, Multi-step workflow automation (5 templates)

### Billing
- Stripe subscription integration (canonical billing_service.py)
- Plan-based feature access (centralized entitlements)

### Canonical Rebuild (Complete)
- Phase 1-4: Core, Content, Orchestration, Billing — all canonical
- is_demo fully purged, SSOT architecture

### Phase 5: UX Refinement (Sprint 1 — April 11, 2026)
- P0 Feed Bug: N+1 query removal, lazy-load replies
- P1 Feed in primary nav, Control Tower Dashboard
- P2 Billing/Settings cleanup

### Code Quality Pass (April 11, 2026)
- Wildcard imports → explicit imports (admin.py, analytics.py, models/__init__.py)
- Circular import chain fixed (realtime_service ↔ notification_service → lazy import)
- Google OAuth client ID moved to REACT_APP_GOOGLE_CLIENT_ID env var
- Feed.js renderCreateDialog → extracted CreateActivityDialog.js component
- Centralized test credentials in tests/conftest.py
- Undefined variables fixed in admin.py (RESEND_API_KEY, SENDER_EMAIL, FRONTEND_URL)

## Tech Stack
- **Frontend**: React 18, TailwindCSS, Shadcn/UI
- **Backend**: FastAPI, Motor (MongoDB async)
- **Database**: MongoDB
- **Integrations**: OpenAI GPT-4o, Stripe, Resend, Google OAuth

## Pending/Backlog

### P1 — Production Hardening
- [ ] Stripe Webhook smoke test (requires user's STRIPE_WEBHOOK_SECRET)
- [ ] Backend activities endpoint optimization (6.3s → <1s)

### P2 — Code Quality (Lower Priority)
- [ ] Fix React hook dependency warnings (74 instances — high regression risk, needs careful per-component review)
- [ ] Replace array index keys with stable keys in list renders
- [ ] Decompose AgentHomePage.js (2,375 lines) into smaller components
- [ ] Reduce complexity in BuyerTimeline.js useCallback (18+ missing deps)

### P3 — Product Compounding
- [ ] Email digest notifications
- [ ] Reporting/export features
- [ ] AI-powered command enhancements

---
Last Updated: April 11, 2026
