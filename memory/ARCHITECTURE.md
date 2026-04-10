# Evohome CMP - Architecture Overview

## 1. System Overview

**Evohome CMP** (Client Management Platform) is a **Real Estate Post-Sale Management** SaaS for Swiss real estate agents managing property handover, document workflows, and client communications.

### Tech Stack
- **Backend**: FastAPI (Python 3.11+) with Motor (async MongoDB driver)
- **Frontend**: React 18 with TailwindCSS + shadcn/ui components
- **Database**: MongoDB Atlas
- **Email**: Resend API
- **Payments**: Stripe (subscriptions)
- **AI**: OpenAI (document extraction), Google Generative AI
- **PDF Generation**: ReportLab, QRBill (Swiss QR invoices)

---

## 2. Database Collections

| Collection | Purpose |
|------------|---------|
| `users` | Agents and buyers (role-based) |
| `projects` | Real estate projects/buildings |
| `units` | Individual units within projects |
| `clients` | Client records (linked to buyers) |
| `documents` | Quotes and invoices |
| `activities` | Feed/messages/updates |
| `activity_recipients` | Per-client activity visibility |
| `notifications` | In-app notifications |
| `timeline_steps` | Project timeline milestones |
| `vault_documents` | Document storage (contracts, plans) |
| `team_members` | Project team directory (suppliers, contractors) |
| `agent_settings` | Agent branding/settings |
| `workflow_executions` | Multi-step workflow tracking |
| `command_drafts` | AI command drafts |
| `command_logs` | Command execution audit log |

### Key Data Isolation Pattern
All data queries filter by `is_demo` flag:
- `is_demo: true` = Demo/sandbox data
- `is_demo: false` = Production data

---

## 3. Authentication System

### Roles
- **Agent**: Property managers, full CRUD access
- **Buyer**: Property purchasers, read-only timeline view

### Flow
1. JWT-based authentication with refresh tokens
2. Session cookies for web clients
3. Bearer tokens for API clients
4. Google OAuth supported (via callback)

### Key Files
- `/backend/core/auth.py` - Token creation/verification
- `/backend/core/access_control.py` - Permission checks
- `/frontend/src/context/AuthContext.js` - Client-side auth state

---

## 4. API Structure (~120 endpoints)

### Auth (`/api/auth/*`)
- `POST /login` - Agent login
- `POST /buyer/login` - Buyer login
- `POST /register` - Agent registration
- `POST /buyer/register` - Buyer registration
- `GET /session` - Check auth status
- `POST /refresh` - Refresh token
- `POST /logout` - Invalidate session
- `POST /demo/{role}` - Demo login

### Projects (`/api/projects/*`)
- CRUD for projects
- Units management (`/projects/{id}/units`)
- Team/contacts (`/projects/{id}/team`)
- Timeline stages (`/projects/{id}/stages`)

### Clients (`/api/clients/*`)
- CRUD for client records
- Preview mode for client portal

### Documents (`/api/documents/*`)
- Upload with AI extraction
- Create/edit quotes and invoices
- Send to clients with email
- Status workflow (Draft→Sent→Approved/Paid)
- Hero images, PDF generation
- Swiss QR code generation

### Activities/Feed (`/api/activities/*`)
- Create messages/updates
- Send to specific clients
- Reply threading
- File attachments

### Timeline (`/api/timeline/*`)
- Project timeline with steps
- AI extraction from PDFs
- Templates system

### Vault (`/api/vault/*`)
- Document storage
- Sharing with clients
- Categories: contracts, plans, permits, reports

### Workflows (`/api/workflows/*`)
- Pre-defined automation templates
- Multi-step execution engine
- Templates: Client onboarding, Invoice paid, Milestone completion

### Billing (`/api/billing/*`)
- Stripe integration
- Subscription plans
- Checkout sessions

---

## 5. Frontend Pages

### Agent Pages (`/agent/*`)
| Route | Component | Purpose |
|-------|-----------|---------|
| `/agent/home` | AgentHomePage | Command center dashboard |
| `/agent/dashboard-legacy` | AgentDashboard | Legacy dashboard |
| `/agent/clients` | AgentClients | Client list |
| `/agent/clients/:id` | AgentClientDetail | Client detail |
| `/agent/projects` | AgentProjects | Project management |
| `/agent/quotes` | AgentQuotes | Quote list |
| `/agent/quotes/:id` | AgentQuoteDetail | Quote detail |
| `/agent/invoices` | AgentInvoices | Invoice list |
| `/agent/invoices/:id` | AgentInvoiceDetail | Invoice detail |
| `/agent/timeline` | AgentTimeline | Timeline management |
| `/agent/feed` | AgentFeed | Activity feed |
| `/agent/team` | AgentTeam | Team directory |
| `/agent/vault` | AgentVault | Document vault |
| `/agent/workflow` | AgentWorkflow | Workflow automation |
| `/agent/analytics` | AgentAnalytics | Analytics dashboard |
| `/agent/billing` | AgentBilling | Subscription management |
| `/agent/settings` | AgentSettings | Agent settings/branding |

### Buyer Pages (`/buyer/*`)
| Route | Component | Purpose |
|-------|-----------|---------|
| `/buyer/dashboard` | BuyerTimeline | Unified buyer view (timeline, documents, feed) |

### Public Pages
- `/login` - Login page
- `/register` - Registration
- `/forgot-password` - Password reset request
- `/reset-password` - Password reset form

---

## 6. Services Layer

### Backend Services (`/backend/services/`)

#### WorkflowService
Pre-defined multi-step workflows:
- `new_client_onboarding` - Create client + welcome email
- `invoice_paid_processing` - Mark paid + confirmation
- `milestone_completion` - Complete step + notify
- `send_document` - Mark sent + email
- `project_announcement` - Broadcast to all clients

#### NotificationService
In-app notification management with read/unread tracking.

#### CommandService
AI-powered command interpretation:
- Intent classification (quote, invoice, message)
- Field extraction from natural language
- Draft creation → Confirmation → Execution
- Document type classification (quote/invoice/timeline/contacts)

---

## 7. Document Workflow

```
Draft → Sent → [Approved/Change Requested] → Paid
                     ↓
              Revert to Draft
```

### Document Types
- **Quote**: Estimates with validity date
- **Invoice**: Bills with due date, Swiss QR code

### AI Features
- PDF text extraction (PyMuPDF)
- OpenAI GPT for structured data extraction
- Amount, supplier, line items parsing

---

## 8. Key Design Patterns

### Data Isolation
```python
# Every query includes is_demo filter
query = {"agent_id": user['user_id'], "is_demo": user.get('is_demo', False)}
```

### Access Control
```python
from core.access_control import can_access_project, can_access_document
if not await can_access_project(user, project_id):
    raise HTTPException(403, "Access denied")
```

### Response Models
All API responses use Pydantic models from `core/responses.py`:
- `DocumentResponse`, `ClientResponse`, `ProjectResponse`, etc.
- Ensures consistent field names between backend and frontend

---

## 9. External Integrations

| Service | Purpose | Config |
|---------|---------|--------|
| MongoDB Atlas | Database | `MONGO_URL` |
| Resend | Email delivery | `RESEND_API_KEY` |
| Stripe | Payments | `STRIPE_SECRET_KEY` |
| OpenAI | AI extraction | `OPENAI_API_KEY` |
| Google OAuth | Social login | Google credentials |

---

## 10. File Structure

```
/app/
├── backend/
│   ├── server.py           # Main FastAPI app (11,600+ lines)
│   ├── core/
│   │   ├── auth.py         # JWT authentication
│   │   ├── access_control.py # Permission checks
│   │   └── responses.py    # Pydantic response models
│   ├── services/
│   │   ├── workflow_service.py    # Multi-step workflows
│   │   ├── notification_service.py # Notifications
│   │   └── command_service.py     # AI commands
│   ├── models/             # Data models
│   ├── routes/             # (Mostly unused, logic in server.py)
│   ├── tests/              # Test files
│   └── uploads/            # File uploads
├── frontend/
│   ├── src/
│   │   ├── App.js          # Router configuration
│   │   ├── context/
│   │   │   ├── AuthContext.js   # Auth state
│   │   │   ├── DataContext.js   # Data fetching
│   │   │   └── SettingsContext.js # Settings
│   │   ├── pages/
│   │   │   ├── agent/      # Agent pages (20+)
│   │   │   ├── buyer/      # Buyer pages
│   │   │   └── *.js        # Public pages
│   │   ├── components/     # Shared components
│   │   └── hooks/          # Custom hooks
│   └── public/             # Static assets
└── memory/
    └── PRD.md              # Product requirements
```

---

## 11. Demo System

Demo mode provides isolated sandbox data:
- Demo agent: `demo.agent@upgradeflow.com` / `demo123`
- Demo buyers: Sophie Müller, Thomas Weber
- Demo project: Residenza Lago Vista
- All demo data has `is_demo: true`

Seed endpoint: `POST /api/demo/seed`

---

## 12. Deployment

### Current: DigitalOcean App Platform
- `evohome-frontend` - Static React build
- `evohome-backend` - Python FastAPI container
- Environment variables for all secrets

### Requirements
- Python 3.11+
- Node.js 18+
- MongoDB Atlas connection
- Resend API key (for emails)
- Stripe keys (for billing)
