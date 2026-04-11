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
├── server.py              # Slim orchestrator (184 lines)
├── database.py            # Shared MongoDB connection
├── helpers.py             # Utility functions
├── models/
│   └── schemas.py         # All Pydantic models (is_demo fully removed)
├── services/              # Strict canonical domain logic
│   ├── activity_service, document_service, vault_service
│   ├── notification_service, project_service, client_service
│   ├── timeline_service, step_service, team_service, unit_service
│   ├── command_service, workflow_service, billing_service
│   ├── email_service, realtime_service, qr_service, ai_service
├── routes/ (22 files)     # Thin route layer — no is_demo anywhere
│   ├── auth.py, projects.py, clients.py, documents.py, timelines.py
│   ├── activities.py, notifications.py, vault.py, billing.py, settings.py
│   ├── invitations.py, dashboard.py, stats.py, analytics.py
│   ├── commands.py, workflows.py, steps.py, timeline_view.py
│   ├── demo.py, admin.py, doc_extraction.py, test_endpoints.py
├── core/                  # config, auth, access_control, rate_limit, monitoring, responses
└── uploads/
/app/frontend/
└── src/
    ├── pages/agent/       # AgentDashboard, AgentVault, AgentSettings, etc.
    ├── pages/buyer/       # BuyerDashboard, BuyerTimeline
    ├── components/        # LanguageToggle, FileDropZone, PdfViewer, AgentLayout, NotificationCenter
    └── context/           # AuthContext, SettingsContext
```

## Canonical Rebuild Status

### SSOT Architecture Rule
**No `is_demo` field allowed in canonical data.** Demo data is identified by deterministic `demo_*` ID prefixes (e.g., `demo_agent_001`, `demo_proj_001`). Cleanup uses ID prefix regex matching.

### Phase 1: Core — COMPLETE
- 5 core modules: Unit, Project, Timeline, TimelineStep, Client
- Service layer + V2 thin routes

### Phase 2: Content Layer — COMPLETE
- 4 content modules: Activity, Document, VaultDocument, Notification
- Services + V2 thin routes

### Phase 3: Orchestration Spine — COMPLETE
- Command Service as pure router
- notification_bridge eliminated, notification_service canonical

### System Perimeter `is_demo` Purge — COMPLETE (April 11, 2026)
- [x] Auth Surgery: is_demo removed from user creation, JWT payloads, session responses, response models
- [x] Demo login: uses demo_* user_id prefix convention (not is_demo query)
- [x] Legacy route cleanup: 9 V1 route files deleted
- [x] DB migration: is_demo removed from 127+ documents across all collections
- [x] `invitations.py`: Purged all is_demo projections
- [x] `demo.py`: Fully rewritten — canonical seed using demo_* ID namespace, zero is_demo writes/deletes/branching
- [x] `schemas.py`: Removed is_demo from all 7 Pydantic models (UserBase, Client, TeamMember, Document, ProjectStage, Activity, Notification)
- [x] `core/auth.py`: Dead create_jwt_token wrapper deleted, stale is_demo comments removed
- [x] `routes/auth.py`: Local create_jwt_token wrapper deleted, all calls replaced with create_access_token, is_demo projections removed
- [x] `admin.py`, `analytics.py`: Dead is_demo variable assignments removed
- [x] 24/24 regression tests passed (iteration_13)
- [x] Database verified: zero is_demo fields in any collection after seed

### Remaining `is_demo` References (non-blocking)
- **Service layer defensive projections** (`"is_demo": 0`): ~40 instances across services. Harmless MongoDB field exclusions. Can be cleaned in a future sweep.
- **Frontend conditionals**: `AgentLayout.js`, `BuyerLayout.js` still have UI is_demo conditionals (P2 task).

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
- Real-time activity feed
- Email notifications via Resend
- In-app notifications with WebSocket

### Agent Command Workspace (Phases 1-4)
- Command bar with text/voice/file input
- Rule-based intent classification
- Draft-first system for all document operations
- Multi-step workflow automation (5 templates)

### Billing
- Stripe subscription integration
- Plan-based feature access

## Tech Stack
- **Frontend**: React 18, TailwindCSS, Shadcn/UI
- **Backend**: FastAPI, Motor (MongoDB async)
- **Database**: MongoDB
- **Integrations**: OpenAI GPT-4o, Stripe, Resend, Google OAuth

## Pending/Backlog

### P1 — Phase 4: Commercial Systems (Billing/Stripe Rebuild)
- [ ] Canonical Stripe integration rebuild
- [ ] Must start ONLY after is_demo perimeter purge is verified complete

### P2 — Frontend Canonical Alignment
- [ ] Remove is_demo conditionals from AgentLayout.js, BuyerLayout.js
- [ ] Clean service-layer defensive projections (~40 instances)

### P3 — Architecture Cleanup
- [ ] Canonicalize routes/workflows.py (direct DB writes → delegate to services)

### P4 — Phase 5: Optimization
- [ ] AI enhancements
- [ ] Dashboard improvements
- [ ] Email digest notifications

---
Last Updated: April 11, 2026
