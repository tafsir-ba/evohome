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
├── server.py              # Slim orchestrator + index management
├── database.py            # Shared MongoDB connection
├── models/
│   └── schemas.py         # All Pydantic models (explicit exports in __init__.py)
├── services/              # Canonical domain logic
│   ├── activity_service   # batch_enrich_activities() for O(1) list enrichment
│   ├── billing_service, client_service, document_service
│   ├── notification_service, project_service, team_service
│   ├── workflow_service, command_service, email_service
│   ├── realtime_service (lazy imports to avoid circular deps)
├── routes/                # Thin route layer (explicit imports only)
├── core/                  # config, auth, access_control, rate_limit, monitoring
├── tests/
│   └── conftest.py        # Centralized test credentials
└── uploads/
/app/frontend/
└── src/
    ├── pages/agent/       # AgentHomePage (Control Tower), AgentFeed, AgentBilling, AgentSettings
    ├── components/        # Feed.js, CreateActivityDialog.js (extracted), AgentLayout
    └── context/           # AuthContext (env-var OAuth), SettingsContext, DataContext
```

## What's Been Implemented

### Core Platform
- JWT + Google OAuth authentication (client ID in env var)
- Password reset flow via Resend
- Control Tower dashboard with action cards + KPI strip
- Projects, units, clients CRUD
- Analytics dashboard, Team member invitation system

### Document Management
- Quotes/invoices with AI extraction (OpenAI GPT-4o)
- PDF generation with QR codes, Document status workflow

### Communication
- Real-time activity feed with batch enrichment (6 queries per page, was 56)
- Email notifications via Resend, In-app notifications with WebSocket
- CreateActivityDialog extracted component

### Billing
- Stripe subscription integration (canonical billing_service.py)
- Plan-based feature access (centralized entitlements)

### Performance Optimizations (April 11, 2026)
- Activities endpoint: 6.3s → 1.0s (6.3x faster) via batch_enrich_activities()
- MongoDB indexes on activity_recipients, activity_replies, activities compound
- Frontend N+1 removal: replies lazy-loaded on expand

### Code Quality (April 11, 2026)
- Wildcard imports → explicit (admin.py, analytics.py, models/__init__.py)
- Circular import fixed (realtime_service ↔ notification_service)
- Google OAuth client ID → REACT_APP_GOOGLE_CLIENT_ID env var
- Feed.js renderCreateDialog → extracted CreateActivityDialog.js
- Test fixtures centralized in conftest.py

## Tech Stack
- **Frontend**: React 18, TailwindCSS, Shadcn/UI
- **Backend**: FastAPI, Motor (MongoDB async)
- **Database**: MongoDB (indexed for hot query paths)
- **Integrations**: OpenAI GPT-4o, Stripe, Resend, Google OAuth

## Pending/Backlog

### P1 — Production Hardening
- [ ] Stripe Webhook smoke test (requires STRIPE_WEBHOOK_SECRET)

### P2 — Code Quality
- [ ] React hook dependency warnings (74 instances)
- [ ] Array index keys → stable keys
- [ ] Decompose AgentHomePage.js (2,375 lines)

### P3 — Product Compounding
- [ ] Email digest notifications
- [ ] Reporting/export features
- [ ] AI-powered command enhancements

---
Last Updated: April 11, 2026
