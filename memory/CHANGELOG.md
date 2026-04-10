# Evohome Changelog

## March 18, 2026

### Timeline/Workflow Engine - Batch 3D
- **Structured construction timeline system**
  - Project-level timeline (not unit-level)
  - Templates → Project instance pattern
  - Status flow: pending → in_progress → completed → approved
  - Documents link via activity_id only (no duplication)
- **Agent Workflow page** (`/workflow`)
  - View/edit timeline steps
  - Advance status with validation
  - Link activities as documents
  - Add internal notes (agent-only)
  - Delete timeline
- **Buyer Construction Progress**
  - Collapsible progress card
  - Shows current phase + percentage
  - Detailed view with linked documents
  - Internal notes hidden (security enforced)

**Files added/modified:**
- `/app/frontend/src/pages/agent/AgentWorkflow.js` (NEW)
- `/app/frontend/src/pages/buyer/BuyerTimeline.js` (UPDATED - ConstructionPhaseCard)
- `/app/frontend/src/components/AgentLayout.js` (UPDATED - Workflow nav)
- `/app/backend/server.py` (UPDATED - Timeline endpoints and models)

---

### Enhanced Features - Batch 3C
- **Team Library**: Project-level team management (CRUD)
  - Agent: Full management at `/projects/{id}/team`
  - Buyer: Read-only access via new "Team" tab
  - 4 demo team members seeded (Plumber, Electrician, Architect, Interior Designer)
- **Project Unit Count**: Shows actual unit count on project cards
- **View as Client**: Agent can preview client's perspective with VIEW ONLY banner
- **Feed Notification Badge**: Unread count using `last_seen_at` timestamp
- **Document File Type**: Activities support `type=file` for contracts, plans, etc.

**Files added/modified:**
- `/app/frontend/src/pages/agent/AgentTeam.js` (NEW)
- `/app/frontend/src/pages/agent/ClientPreview.js` (NEW)
- `/app/frontend/src/pages/buyer/BuyerTimeline.js` (UPDATED - 3 tabs)
- `/app/frontend/src/pages/agent/AgentProjects.js` (UPDATED - unit_count)
- `/app/frontend/src/pages/agent/AgentClients.js` (UPDATED - View button)
- `/app/frontend/src/components/AgentLayout.js` (UPDATED - Team nav)
- `/app/frontend/src/components/Feed.js` (UPDATED - file type)
- `/app/backend/server.py` (UPDATED - new endpoints)

### Core Communication (Activity Feed) - Batch 3B
- Added shared `Feed.js` component with role-based UI adaptation
- Agent view: Full post creation, 4 activity types, project/recipient selection
- Buyer view: Read + reply only via "Updates" tab in timeline
- Backend role-based filtering (buyer auto-filtered to their unit)
- Fixed MongoDB ObjectId serialization bug in reply endpoint

**Files added/modified:**
- `/app/frontend/src/components/Feed.js` (NEW)
- `/app/frontend/src/pages/agent/AgentFeed.js` (UPDATED)
- `/app/frontend/src/pages/buyer/BuyerTimeline.js` (UPDATED)
- `/app/frontend/src/components/AgentLayout.js` (UPDATED)
- `/app/frontend/src/App.js` (UPDATED)
- `/app/backend/server.py` (FIXED)

---

## March 17, 2026

### Architecture Foundation - Batch 3A
- Separate login flows for Buyer/Agent with role enforcement
- Original PDF as source of truth (no generated PDFs for viewing)
- Document versioning with history tracking
- Removed legacy /quotes/* and /invoices/* endpoints

### Project Management Improvements
- Project-based client filtering
- Unit management within projects
- Click project → view filtered clients

### UI/UX Fixes
- Clickable "action needed" badge scrolls to relevant item
- Unified agent-side color scheme
- Fixed agent list pages to use unified /documents endpoint
- Renamed "Ask" to "Request Change"

---

## March 16, 2026

### Document UX - Iteration 7
- Hero image upload for quotes/invoices
- Card summary field for timeline cards
- E-commerce style timeline cards
- Swiss QR payment modal

### Evohome Rebrand - Iteration 6
- Renamed from UpgradeFlow to Evohome
- Blue color system (primary: #2563EB)
- Updated all interfaces and login page
