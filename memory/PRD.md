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
│   └── schemas.py         # All Pydantic models
├── services/              # Strict canonical domain logic
│   ├── activity_service, document_service, vault_service
│   ├── notification_service, project_service, client_service
│   ├── timeline_service, step_service, team_service, unit_service
│   ├── command_service, workflow_service, billing_service
│   ├── email_service, realtime_service, qr_service, ai_service
├── routes/ (22 files)     # Thin route layer
│   ├── auth.py, projects.py, clients.py, documents.py, timelines.py
│   ├── activities.py, notifications.py, vault.py, billing.py, settings.py
│   ├── invitations.py, dashboard.py, stats.py, analytics.py
│   ├── commands.py, workflows.py, steps.py, timeline_view.py
│   ├── demo.py, admin.py, doc_extraction.py, test_endpoints.py
├── core/                  # config, auth, access_control, rate_limit, monitoring, responses
└── uploads/
/app/frontend/
└── src/
    ├── pages/agent/       # AgentHomePage (Control Tower), AgentFeed, AgentBilling, AgentSettings, etc.
    ├── pages/buyer/       # BuyerDashboard, BuyerTimeline
    ├── components/        # Feed.js, AgentLayout, NotificationCenter, etc.
    └── context/           # AuthContext, SettingsContext, DataContext
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
- Document status workflow
- In-app PDF viewer

### Communication
- Real-time activity feed (Feed.js — lazy-load replies)
- Email notifications via Resend
- In-app notifications with WebSocket

### Agent Command Workspace
- Command bar with text/voice/file input
- Rule-based intent classification
- Draft-first system for all document operations
- Multi-step workflow automation (5 templates)

### Billing
- Stripe subscription integration (canonical billing_service.py)
- Plan-based feature access (centralized entitlements)
- Webhook signature verification

### Canonical Rebuild (Complete)
- Phase 1-4: Core, Content, Orchestration, Billing — all canonical
- is_demo fully purged from all active code
- SSOT architecture with thin routes + canonical services
- P3.5 optimization: 44 projections, 7 dead imports removed

### Phase 5: UX Refinement (Sprint 1 — April 11, 2026)
- **P0 Feed Bug Fixed**: Removed N+1 query pattern (was causing 56s load times). Activities now load with single API call. Replies lazy-loaded on expand.
- **P1 Feed Promoted**: Moved from "More" dropdown to primary sidebar navigation.
- **P1 Control Tower Dashboard**: Replaced command-input-only homepage with actionable Control Tower: Action Cards (Change Requests, Pending Invoices, Pending Quotes) + KPI Strip (Clients, Projects, Revenue, Approved Quotes) + Command Bar (repositioned) + Deduplicated Recent Activity.
- **P2 Billing Cleanup**: Removed Sync button (debug affordance) and duplicate Subscription Details section.
- **P2 Settings Cleanup**: Replaced duplicate plan grid in Settings > Billing tab with plan summary + "Manage Billing" redirect to dedicated page.

## Tech Stack
- **Frontend**: React 18, TailwindCSS, Shadcn/UI
- **Backend**: FastAPI, Motor (MongoDB async)
- **Database**: MongoDB
- **Integrations**: OpenAI GPT-4o, Stripe, Resend, Google OAuth

## Pending/Backlog

### P1 — Production Hardening
- [ ] Stripe Webhook smoke test (requires user's STRIPE_WEBHOOK_SECRET)
- [ ] Backend activities endpoint optimization (6.3s per request due to N+1 enrichment)

### P2 — Product Compounding
- [ ] Email digest notifications
- [ ] Reporting/export features
- [ ] AI-powered command enhancements

---
Last Updated: April 11, 2026
