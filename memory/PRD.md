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

## What's Been Implemented (March 2026)

### P0 Data Consistency Fix (March 19, 2026) 🔥
- [x] **DataContext as Single Source of Truth** - All project data now flows through centralized DataContext
- [x] Eliminated fragmented project fetching across 8+ components
- [x] Project selection persists across page navigation (Dashboard, Timeline, Team, Workflow)
- [x] Files refactored: AgentHomePage, AgentTimeline, AgentTeam, AgentWorkflow, AgentClients, AgentProjects, AgentVault, Feed
- [x] Added `/api/command/recent-work` endpoint for homepage Recent Activity
- [x] DataContext re-fetches after user login (useAuth integration)

### Core Platform
- [x] JWT + Self-hosted Google OAuth authentication
- [x] Password reset flow via Resend
- [x] Agent dashboard with WebSocket real-time updates
- [x] Projects, units, and clients CRUD
- [x] Analytics dashboard with business metrics
- [x] Team member invitation system

### Document Management
- [x] Quotes and invoices with AI extraction (OpenAI GPT-4o)
- [x] PDF generation with QR codes
- [x] Document status workflow (Draft → Sent → Approved/Rejected → Paid)
- [x] In-app PDF viewer
- [x] Edit/delete functionality for drafts and sent documents

### Agent Profile & Branding
- [x] Agent profile settings (display name, contact email, phone)
- [x] Company branding (name, logo upload)
- [x] Profile info used in email signatures

### Document Vault
- [x] Centralized document storage at `/agent/vault`
- [x] Category organization (Contracts, Plans, Permits, Reports, Other)
- [x] Project association and access levels (private/shared)
- [x] Drag-and-drop upload with `FileDropZone` component
- [x] In-app preview and download
- [x] Edit and delete capabilities
- [x] **Buyer Vault UI** - "Documents" tab in buyer view showing shared documents
- [x] Granular document sharing with specific buyers

### AI Timeline Extraction
- [x] Upload planning documents (PDF, Excel, images)
- [x] AI (OpenAI GPT-4o) extracts project phases/milestones
- [x] Agent can review, edit, and approve extracted timeline
- [x] Applied timeline creates template and project steps
- [x] "Extract with AI" button on Workflow page
- [x] Manual timeline creation without templates
- [x] Add new steps to existing timeline (POST /timeline/{id}/steps)
- [x] Delete steps from timeline (DELETE /timeline/steps/{id})

### Language System (NEW - March 18, 2026)
- [x] Simplified to English (EN) and French (FR) only
- [x] Removed German (de) and Italian (it) translations
- [x] EN/FR toggle in header navigation (next to notification bell)
- [x] Language persists via localStorage
- [x] Settings page Preferences tab shows only currency selector

### Document Vault Hardening (NEW - March 19, 2026)
- [x] **Critical Bug Fix**: Route collision fixed - `/vault/buyer` now correctly routes to buyer endpoint
- [x] **Document Name Display**: Fixed VaultDocumentCard to use `document.name` instead of `filename`
- [x] **Tab Labeling**: Buyer tabs renamed for clarity:
  - "Quotes & Invoices" (with pending count badge)
  - "Shared Files" (with document count badge)
- [x] **File Type Icons**: getFileIcon() checks mime type and extension for proper icons (PDF, image, spreadsheet, word doc)
- [x] **Upload Progress**: Real progress bar with percentage using XMLHttpRequest progress events
- [x] **Delete Confirmation**: Custom modal dialog instead of browser confirm()
- [x] **Empty States**: Helpful messaging when buyer has no shared documents
- [x] **Better Error Messages**: User-friendly error for unsupported file types
- [x] **Download Filename Fix**: Uses correct field name for download filename

### Client Profile - Unit Assignment (NEW - March 18, 2026)
- [x] Unit displayed prominently in client profile with project context
- [x] Editable unit dropdown showing all project units
- [x] Availability status badges (Available / Assigned to [name] / Current)
- [x] Confirmation dialog when reassigning unit from another client
- [x] Data integrity: validates unit exists in project
- [x] Prevents duplicate assignment (one unit = one client)
- [x] Force reassignment option with automatic removal from previous client

### AI Team Directory Extraction (NEW - March 18, 2026)
- [x] "Import from Document" button in Team Directory
- [x] Upload PDF, Word, Excel, or image files containing contact info
- [x] AI (GPT-4o) extracts structured contacts: company, name, role, email, phone, website, address
- [x] Automatic deduplication of extracted contacts
- [x] Preview and edit contacts before import
- [x] Bulk import endpoint: POST /api/projects/{id}/team/bulk
- [x] Global team directory: GET /api/team/directory with search/filter

### Supplier Field Integration (NEW - March 18, 2026)
- [x] SupplierAutocomplete component in Invoice and Quote upload pages
- [x] Autocomplete searches Team Directory by company/contact name
- [x] Shows suggestions with role, email, phone
- [x] Manual entry fallback for new suppliers
- [x] Team Directory as single source of truth for contacts

### Email System
- [x] Transactional emails via Resend
- [x] Email templates with inline CTA button styles
- [x] Notifications for document events, invitations, milestones

### Buyer & Agent Journey Hardening (NEW - March 19, 2026)
- [x] **Critical Fix**: `/api/clients` endpoint now works (was returning 500 error)
  - Made `unit_reference` and `status` optional in Client Pydantic model
  - Added default values ("General" and "active") for missing fields
- [x] **Data Migration**: `POST /api/admin/migrate-clients` backfills missing fields
- [x] **Data Health Check**: `GET /api/admin/data-health` returns integrity report
- [x] **Improved Send Document**: Returns detailed delivery status
  - Tracks: notification_created, websocket_sent, email_sent
  - Returns warnings array if email delivery fails
  - Validates client exists and has email before sending
- [x] **Better Error Messages**: Specific error messages throughout the flow
- [x] **Mobile UX Improvements**: 
  - Larger tap targets (h-12) on all action buttons
  - Better button labels with full text ("Approve Quote" vs "Approve")
  - Improved spacing between mobile buttons
- [x] **Quote Detail**: Enhanced send feedback showing recipient name and email status

### Stabilization Sprint - Phase 1: Session/Auth (COMPLETE - March 19, 2026)
**Initial Implementation:**
- [x] **Centralized Auth Module** (`/app/backend/core/auth.py`):
  - JWT token creation/verification in one place
  - Token blacklist for proper logout invalidation
  - `is_demo` fetched from database (not JWT) - prevents stale is_demo state
- [x] **New Auth Endpoints**:
  - `GET /api/auth/session` - Check auth state, returns user with is_demo from DB
  - `POST /api/auth/refresh` - Extend session without re-login (24hr grace period)
  - `POST /api/auth/logout` - Invalidates token (blacklist) + clears cookie
- [x] **Frontend AuthContext Updated**:
  - Uses `/auth/session` for auth state check
  - Auto-refresh on 401 before giving up
  - Proper logout calls `/auth/logout`
- [x] **Session Stability**:
  - JWT_SECRET properly loaded from .env
  - Token invalidation persists until server restart (in-memory blacklist)
  - Consistent auth state across browser refreshes

**Phase 1 Completion (March 19, 2026) - CRITICAL FIXES:**
- [x] **Unified Auth System**: Removed duplicate local auth functions from `server.py`
  - `get_current_user`, `get_current_agent`, `get_current_buyer` now imported from `core/auth.py`
  - Legacy `create_jwt_token` redirects to `create_access_token`
  - All 200+ endpoints now use centralized auth module
- [x] **Token Structure Standardized**:
  - New tokens have `type: 'access'` and `jti` fields
  - `is_demo` NO LONGER stored in token - always looked up from DB
  - Backward compatible: tokens without `type` field treated as 'access'
- [x] **Vault Buyer Access Fixed**:
  - `GET /api/vault/{vault_id}` now works for both agents (owner) and buyers (shared access)
  - Previously returned "Agent access required" for all buyers
- [x] **Project Data Scoping Fixed**:
  - Buyers now only see projects they are associated with (via client record)
  - Previously leaked all demo projects to any demo user
- [x] **Centralized Access Control Layer** (`/app/backend/core/access_control.py`):
  - `can_access_project()`, `can_access_client()`, `can_access_vault_doc()`, `can_access_document()`
  - Enforces consistent authorization across all endpoints

**Validation Suite** (`/app/backend/tests/validate_auth_stability.py`):
- 13/13 real-world validation tests passing:
  - ✓ Buyer vault isolation (buyers only see their shared docs)
  - ✓ Buyer project access scoped (buyers only see their project)
  - ✓ Buyer cross-access blocked (buyer1 can't access buyer2's docs)
  - ✓ Agent full access (projects, vault, clients)
  - ✓ Shared doc visible to authorized buyer
  - ✓ Private doc inaccessible to buyers
  - ✓ Data stable after refresh
  - ✓ Session consistency
  - ✓ Logout invalidation
  - ✓ Login cycle clean (logout->login->works)
  - ✓ Document operations work

### Billing
- [x] Stripe subscription integration
- [x] Manual sync button for subscription recovery
- [x] Plan-based feature access (logo upload = Pro)

## Tech Stack
- **Frontend**: React, TailwindCSS, Shadcn/UI
- **Backend**: FastAPI, Motor (MongoDB async)
- **Database**: MongoDB Atlas (self-hosted)
- **Integrations**: 
  - OpenAI GPT-4o (AI extraction) - requires user API key
  - Stripe (payments) - requires user API key
  - Resend (emails) - requires user API key
  - Google OAuth (self-hosted flow) - requires user credentials

## Pending/Backlog

### P0 - Critical (Stabilization Sprint) 
- [x] Phase 1: Auth/Session Stabilization - COMPLETED March 19, 2026
  - Unified auth system, token structure standardized, vault buyer access fixed
- [x] Phase 4: is_demo Data Entanglement FIX - COMPLETED March 19, 2026
  - **Query-level fix**: Removed `is_demo` from ALL data queries (~150 patterns)
  - **Ownership-based scoping**: All data now filtered by `agent_id`/ownership, not `is_demo`
  - **Key validation tests (21/21 pass)**:
    - ✓ Prod user cannot see demo data (0 demo projects visible)
    - ✓ Demo user cannot see prod data (only owns their projects)
    - ✓ Cross-refresh data stability
    - ✓ Relogin data consistency
    - ✓ Frontend state consistency across session checks
    - ✓ Document upload visibility (agent/buyer scoped)
    - ✓ Notification scoping
    - ✓ Agent-buyer interaction flow
  - **Remaining cleanup (non-blocking)**:
    - INSERT operations still add `is_demo` (75 patterns) - harmless metadata
    - Demo cleanup scripts still use `is_demo: True` (14 patterns) - required for data management
- [x] Phase 2: API Contracts - COMPLETED March 19, 2026
  - ✓ Added `response_model` to auth endpoints (session, logout)
  - ✓ **Document schema normalized**:
    - Unified `type`/`document_type` fields (both populated on create)
    - Unified `amount`/`total_amount` fields (both populated on create)
    - All documents now have `agent_id` (ownership scoping)
    - Fixed 5 orphaned documents with missing `agent_id`
  - ✓ Applied strict `response_model` to:
    - `/documents` endpoint - `List[DocumentResponse]`
    - `/vault` and `/vault/buyer` endpoints - `List[VaultDocumentResponse]`
    - `/vault/{vault_id}` endpoint - `VaultDocumentResponse`
  - ✓ **Vault/Activities/Timeline ownership cleaned**:
    - Removed leftover `is_demo` from vault, activities, and timeline queries
    - All data queries now use ownership scoping only
  - ✓ **Frontend consistency verified**:
    - Frontend already handles both field names with fallbacks (total_amount || amount)
    - Invoice/Quote pages render correctly
    - Buyer timeline shows documents with correct amounts
    - Agent command center fully functional
  - **E2E Workflow Validation (25/25 PASS)**:
    - Document creation with unified schema
    - Vault sharing visibility
    - Activity client scoping
    - Refresh/relogin data integrity
  - **Remaining (non-blocking cleanup)**:
    - Writing both field names (type/document_type, amount/total_amount) is temporary migration debt
    - `is_demo` extraction still present for subscription gating (correct behavior)
- [ ] Phase 3: Decompose `server.py` Monolith (~11,000 lines)
  - Split into domain-specific route files: `/routes/auth.py`, `/routes/projects.py`, etc.
  - **READY**: Document schema normalized, API contracts validated, frontend consistent

### P1 - High Priority (Agent Command Workspace Phase 4) - COMPLETED
- [x] Multi-step workflows (chaining commands) - COMPLETED March 19, 2026
- [x] Re-run extraction button in UI (COMPLETED - March 19, 2026)
- [x] Manual document type override in preview drawer (COMPLETED - March 19, 2026)
- [x] Field-level confidence indicators in preview drawer (COMPLETED - March 19, 2026)

### P2 - Medium Priority  
- [ ] Email digest notifications (daily/weekly summary)
- [ ] Document archiving feature
- [ ] Proactive AI suggestions (future)

### P3 - Low Priority / Future
- [ ] Continue backend refactoring (migrate more endpoints to modular structure)
- [ ] WhatsApp notifications (Twilio/WhatsApp Business API)
- [ ] SMS notifications (Twilio)
- [ ] Advanced reporting/export
- [ ] Mobile app considerations

## Completed This Session (March 19, 2026)

### UI Simplification Sprint (COMPLETE - March 19, 2026)
- [x] **Agent Homepage Simplified** (~40-50% UI reduction):
  - **REMOVED**: Beta banner, Quick Actions buttons, Automated Workflows section, Priority Queue, Overview metrics, Module Shortcuts/Quick Access panel
  - **RESTRUCTURED**: Command Center is now the dominant visual block
  - **Supporting Block**: Deterministic behavior - shows Recent Activity when data exists, shows CTA when empty
  - **Sidebar "More" Menu**: Vault, Analytics, Feed moved to collapsible "More" menu in sidebar
  - **Simplified Header**: Condensed title and subtitle, removed Switch to Classic button
  
- [x] **Sidebar Navigation Updated** (`AgentLayout.js`):
  - Primary items: Dashboard, Projects, Clients, Timeline, Team, Quotes, Invoices, Settings
  - Secondary (in More): Vault, Analytics, Feed
  - More menu expands/collapses, highlights when nested route active
  
- [x] **Validation**: 19/19 frontend tests passed confirming all removed elements and new navigation

### Data Consistency Fix (COMPLETE - March 19, 2026)
- [x] **Root Cause**: Each page had its own isolated `selectedProject` state - no single source of truth
- [x] **Solution Phase 1**: Created `useProjectContext` hook (`/app/frontend/src/hooks/useProjectContext.js`)
  - Persists `selectedProject` in localStorage
  - Custom event for same-tab sync, storage event for cross-tab sync
  - `validateProjectSelection()` helper to validate against available projects
- [x] **Solution Phase 2 - Race Condition Fix**: Added proper fetch management
  - **AbortController**: Cancel pending requests on project switch
  - **Immediate state clearing**: Clear stale data before fetching new
  - **Response validation**: Ignore late responses that don't match current project
  - **Fetch tracking**: `currentFetchRef` to track which request is authoritative
- [x] **Updated Pages**: AgentHomePage, AgentTeam, AgentTimeline, AgentWorkflow
  - All now read/write from shared context
  - Project selection persists across navigation
  - Data fetching properly handles project changes with abort/ignore pattern

### Agent Command Workspace Phase 1 (COMPLETE)
- [x] **New Agent Homepage UI** (`AgentHomePage.js`) - Now simplified:
  - Command bar with text input, voice input, and file upload/drop
  - Context selectors (Project, Client, Unit)
  - Recent Activity (conditional) or CTA (when empty)
  - Action Preview Drawer with confirm/edit/cancel

- [x] **Voice Input (with graceful degradation)**:
  - Uses Web Speech API (webkitSpeechRecognition)
  - **Browser compatibility check**: Shows disabled state in unsupported browsers (Firefox, Safari)
  - **Detailed error messages**: Specific messages for microphone permissions, no speech detected, etc.
  - Tooltip explains browser requirements

- [x] **Routing Updates**:
  - `/agent/home` is now the default entry point for agents
  - `/agent/dashboard` redirects to `/agent/home`
  - `/agent/dashboard-legacy` provides access to old dashboard
  - `USE_NEW_AGENT_HOME` feature flag in App.js controls behavior (set to `true`)
  - All login/register/OAuth flows navigate to `/agent/home`
  - Sidebar navigation updated to point to `/agent/home`

### Agent Command Workspace Phase 2 (COMPLETE)
- [x] **Backend Command Service** (`/app/backend/services/command_service.py`):
  - Tool Registry with 3 tools: `create_quote`, `create_invoice`, `create_message`
  - Each tool defines: required_fields, optional_fields, validation, execution
  - Rule-based intent classification (deterministic, no AI yet)
  - Field extraction from command text (amounts, titles, content)

- [x] **API Endpoints**:
  - `POST /api/command/interpret` - Converts input → structured plan (no side effects)
  - `POST /api/command/draft` - Creates draft from validated plan
  - `POST /api/command/execute` - Executes confirmed draft through domain services (with idempotency)
  - `GET /api/command/tools` - Lists available tools and their definitions
  - `GET /api/command/drafts` - Lists user's drafts
  - `GET /api/command/logs` - Returns execution audit logs
  - `GET /api/command/history` - **NEW** Returns drafts and recent extractions
  - `POST /api/command/draft/auto-save` - **NEW** Periodic draft persistence
  - `GET /api/command/draft/auto-save/{plan_id}` - **NEW** Retrieve auto-saved draft

- [x] **Draft-First System**:
  - All commands create drafts before execution
  - Drafts stored in `command_drafts` collection
  - Status: pending → confirmed → executed (or cancelled/failed)
  - Execution logs stored in `command_logs` collection
  - **Idempotency**: Executing same draft_id twice returns cached result

- [x] **Frontend Debug Visibility**:
  - Intent with confidence badge
  - Extracted fields table with source column (input/context)
  - Missing fields with required indicator
  - Validation status panel
  - Collapsible debug log
  - Create Draft button disabled when can_execute=false

- [x] **Keyboard Shortcut**:
  - `Cmd+K` / `Ctrl+K` focuses the command bar

### Agent Command Workspace Phase 3 (COMPLETE)
- [x] **Document Classification** (`/api/command/classify-document`):
  - Rule-based classification: quote, invoice, timeline, contacts
  - Keyword and layout pattern matching
  - Confidence scoring (0.0-1.0)
  - Override option available in UI
  - **Supports PDF and images (JPG, PNG, WEBP)** - OCR via OpenAI Vision API

- [x] **Document Extraction** (`/api/command/extract-document`):
  - Quote extraction: supplier, total_amount, currency, description, line_items
  - Invoice extraction: supplier, total, due_date, reference
  - Timeline extraction: stages with raw date text (no normalization)
  - Contacts extraction: names, roles, emails, phones with deduplication
  - **Amount validation**: Negative/zero/large amounts trigger warnings
  - **Idempotency key** support to prevent duplicate extractions

- [x] **New Extraction Tools**:
  - `extract_quote` - Extract quote from document
  - `extract_invoice` - Extract invoice from document  
  - `extract_timeline` - Extract timeline with raw dates
  - `extract_contacts` - Extract and deduplicate contacts

- [x] **Draft-First Document Flow**:
  - Document → Classification → Extraction → Structured Plan → Preview → Confirm → Draft
  - All outputs go through command system
  - No auto-actions, no direct DB writes from extraction
  - Agent reviews and confirms before any object is created

- [x] **Frontend Enhancements**:
  - File upload triggers classification → extraction flow
  - **Supports PDF, JPG, PNG, WEBP** - Drag-and-drop and file picker both work
  - Document classification display with confidence badge
  - Extracted fields shown with source (ai_extraction/context)
  - Missing fields highlighted for user action

### System Hardening (COMPLETE - March 19, 2026)
- [x] **User Control Features**:
  - Re-run Extraction button in Action Preview Drawer
  - Manual document type override dropdown (invoice/quote/timeline/contacts)
  - Field-level confidence indicators (High/Medium/Low badges)
  - "Was Overridden" badge when user changes document type

- [x] **Bug Fix - File Upload Priority** (March 19, 2026):
  - Fixed critical bug where file uploads were ignored when text was present in command bar
  - File uploads now ALWAYS trigger document classification/extraction flow
  - Text input is treated as optional context when file is present
  - Test scenarios verified: (1) File only, (2) File + text, (3) Text only

- [x] **Bug Fix - Amount Parsing with Comma Separators** (March 19, 2026):
  - Fixed critical bug where "CHF 10,000" was parsed as CHF 10.00 instead of CHF 10,000.00
  - Comma was incorrectly interpreted as decimal separator instead of thousands separator
  - Updated `extract_amount()` function in `command_service.py` with smarter pattern detection
  - Now correctly handles: thousands separator (10,000), European decimal (10,50), Swiss apostrophe (10'000)
  - Test file created: `/app/backend/tests/test_amount_parsing.py`

- [x] **Bug Fix - OAuth & Email/Password Account Linking** (March 19, 2026):
  - Fixed critical bug where Google OAuth users couldn't add email/password login
  - Fixed login failure for OAuth-only accounts (missing password_hash error)
  - **New Features:**
    - Account linking: Register with same email links password to existing OAuth account
    - `POST /api/auth/check-email`: Check if email exists and what auth methods are available
    - `POST /api/auth/set-password`: Dedicated endpoint for OAuth users to set password
    - Clear error messages guide users to correct auth flow
  - **Behavior:**
    - Single unified account per email (no duplicates)
    - Can login via Google OR email/password after linking
    - OAuth-only users get helpful message directing them to set a password

- [x] **Bug Fix - Auto-creation of Draft Without Confirmation** (March 19, 2026):
  - Fixed critical violation of draft-first architecture
  - Documents were being created in DB immediately on PDF upload, before user confirmation
  - **Refactored workflow:**
    - `POST /api/documents/upload`: Now returns preview data ONLY (no DB write)
    - `POST /api/documents/create`: New endpoint - creates document only after user confirms
  - **Correct flow now:**
    - Upload PDF → Extract → Preview/Edit → User clicks Save → Document created
  - Both Invoice and Quote upload pages updated to use new two-step flow

- [x] **Enhancement - Image Preview in Feed Posts** (March 19, 2026):
  - Images now display as visual previews directly in feed posts (not generic file attachments)
  - Added drag-and-drop support for uploading images
  - Multiple images can be dropped/selected at once
  - Image previews shown in the create dialog before posting
  - Click on image to view full size
  - Fallback to file attachment display if image fails to load

- [x] **Bug Fix - Unsupported File Type Handling** (March 19, 2026):
  - Command Center now rejects non-PDF files with clear error message
  - Frontend file input restricted to PDFs only (`accept=".pdf"`)
  - Backend validates file extension before processing
  - Error messages no longer expose internal file paths
  - Graceful error handling for corrupted/invalid PDFs

- [x] **Bug Fix - Quote Creation Intent Misrouted** (March 19, 2026):
  - Fixed: "Create a quote" was creating invoices instead of quotes
  - Fixed: "Unknown intent extract_quote" error when clicking Create Draft
  - Added `EXTRACT_QUOTE` and `EXTRACT_INVOICE` handlers in `_execute_by_intent()`
  - Intent mapping now consistent end-to-end: create_quote → quote, extract_quote → quote

- [x] **Enhancement - Drag-and-Drop for Command Center** (March 19, 2026):
  - Entire command input area is now a drag-and-drop zone
  - Visual feedback when dragging files (border highlight, bounce animation)
  - Only accepts PDF files (validates on drop)
  - Clear overlay indicator: "Drop PDF here"
  - Toast confirmation when files are added

- [x] **Bug Fix - Timeline Stages Display [object Object]** (March 19, 2026):
  - Fixed: Timeline stages showing `[object Object]` instead of stage names
  - Added special rendering for array/object field values
  - Added dedicated "Timeline Stages" section in Action Preview drawer
  - Stages now display: name, date (date_text), description, status
  - Summary line shows count and stage names (e.g., "3 stages: Planning, Permits, Foundation")

- [x] **Bug Fix - No Source File for Re-extraction** (March 19, 2026):
  - Fixed: "No source file available for re-extraction" error after manual classification
  - Root cause: File reference lost when classification failed or returned 'unknown'
  - Solution: Store `original_file` reference in previewData
  - If file_path is lost, re-upload the original file automatically before extraction
  - Works for all document types: contacts, timeline, invoice, quote
  - **Final fix (March 19):** Added `uploadedFileRef` (useRef) for persistent file storage across re-renders
  - Priority fallback chain: originalFile → refFile → attachmentFile

- [x] **Bug Fix - File Upload Button Reliability** (March 19, 2026):
  - Fixed: Upload button intermittently failing to open file picker
  - **Final fix (March 19):** Moved hidden file input outside drop zone to prevent event interference
  - Created `triggerFileUpload` callback for clean click handling
  - Added z-20 class to upload button for proper stacking context
  - Testing verified: 3/3 consecutive clicks successfully triggered file picker

- [x] **Enhancement - Timeline Existence Check** (March 19, 2026):
  - System now checks if project already has a timeline before creating a new one
  - If timeline exists, shows warning with existing timeline name
  - Provides three options: "Cancel", "Update (Add New)", or "Replace All"
  - "Update" mode: Keeps existing stages and adds new extracted ones
  - "Replace" mode: Deletes all existing stages before adding new ones
  - Prevents accidental overwriting of project timelines

- [x] **Enhancement - Timeline AI Extraction Page** (March 19, 2026):
  - Dedicated Timeline page (`/agent/timeline`) with full AI extraction workflow
  - Upload PDF → AI extracts stages → Preview with editing → Confirm and save
  - Stage order continues from existing stages in "Update" mode
  - Extraction confidence indicator in preview dialog
  - Individual stage editing (name, date, status) before saving

- [x] **Bug Fix - Document Vault Preview (Buyer Side)** (March 19, 2026):
  - Fixed: Document preview returned "detail not found" error
  - Fixed: Pressing back after error logged user out
  - Fixed: Document titles not properly displayed on mobile
  - Fixed: Documents could not be downloaded
  - Solution: Updated handleVaultPreview to use authenticated download endpoint
  - Improved VaultDocumentCard mobile responsiveness with proper text wrapping

- [x] **Bug Fix - Activity Feed Edit/Delete (Agent Side)** (March 19, 2026):
  - Added: Three-dot dropdown menu on each activity card with Edit and Delete options
  - Added: Edit dialog with title and content inputs
  - Added: Delete confirmation dialog
  - Added: Backend endpoints PUT and DELETE /api/activities/{id}
  - Fixed: Backend was using wrong field name (agent_id vs author_id) - CRITICAL BUG FIX

- [x] **Bug Fix - Invoice/Document Deletion** (March 19, 2026):
  - Fixed: Deletion blocked with "cannot delete unless draft" message
  - Added: force=true parameter to DELETE /api/documents/{id} for deleting non-draft documents
  - Added: POST /api/documents/{id}/revert-to-draft endpoint to change status back to Draft
  - Now agents can delete documents in any status using force parameter

- [x] **Bug Fix - File + Text Priority** (March 19, 2026):
  - Issue: When uploading a file with conflicting text command (e.g., upload invoice.pdf + type "create quote"), text was taking priority
  - Fixed: When extraction fails but classification succeeds, preserve the classification's document_type
  - The detected intent now correctly shows "Extract Invoice" instead of "General Action"
  - Document Type dropdown auto-fills with the classified type (invoice/quote/timeline)
  - Moved classification variable to outer scope to preserve it in error handling

### Agent Command Workspace Phase 4 (COMPLETE - March 19, 2026)
- [x] **Multi-Step Workflow Automation** (Production-Ready: 95%):
  - Workflow service with template definitions and execution engine
  - **Database Persistence**: Workflow executions stored in MongoDB with 30-day TTL auto-cleanup
  - **Real Email Sending**: Workflows send actual emails via Resend API with graceful error handling
  - **Graceful Degradation**: Email failures return warnings, not errors - workflow continues
  - **Frontend Validation**: Run button disabled until required fields filled
  - **Warning Status**: `completed_with_warnings` status with amber UI styling
  - **Step Retry**: Failed/warning steps can be retried individually via UI button
  - **Confirmation Dialog**: Destructive workflows (e.g., mark invoice paid) show confirmation warning
  
  - 5 pre-defined workflow templates with UI selectors:
    1. **New Client Onboarding**: Create client → Send welcome email (manual input)
    2. **Invoice Paid Processing**: Mark paid → Send payment confirmation (document selector)
    3. **Milestone Completion**: Complete step → Send milestone notification (timeline step selector)
    4. **Send Document to Client**: Mark sent → Email document link (document selector)
    5. **Project Announcement**: Create announcement → Email all clients (manual input)
  
  - Backend features:
    - Context validation with clear error messages (e.g., "Missing required context: client_name, client_email")
    - Auto-enrichment fetches client email, project name from IDs
    - TTL index using BSON Date field `created_at_date` for proper auto-deletion after 30 days
    - safe_send_email helper with try/catch error handling
    - Retry endpoint: POST /api/workflows/executions/{id}/steps/{idx}/retry
    - Timeline step selector uses correct field mapping (`title` → `name`)
    - Step response includes `step_index` and `can_retry` fields
  
  - Frontend features:
    - Document/timeline step selector dropdowns (now working with demo data)
    - validateWorkflowContext() checks all required fields
    - canExecuteWorkflow() controls Run button state
    - Warning steps displayed with amber background and border
    - Warning banner explaining "Some steps completed with warnings"
    - Retry button visible on failed/warning steps with amber styling
    - Confirmation state for destructive workflows
    - Toast shows "Completed with warnings" when applicable

## Previously Completed (March 18, 2026)
1. **P0 Language System Simplification**:
   - Reduced languages from 4 (EN, DE, FR, IT) to 2 (EN, FR)
   - Created LanguageToggle component in header
   - Removed language dropdown from Settings > Preferences
   - Added localStorage persistence for language choice
   - Added changeLanguage function to SettingsContext

2. **Client Profile - Unit Assignment**:
   - Enhanced AgentClientDetail.js with Property/Unit Assignment section
   - Dropdown shows units with availability status (Available/Assigned/Current)
   - Confirmation dialog for reassigning units from other clients
   - Backend validation for unit existence and duplicate prevention
   - `force_unit_reassign` parameter for confirmed reassignments
   - Updated GET /projects/{id}/units to return assignment info

3. **AI Team Directory Extraction + Supplier Integration**:
   - TeamContactImport component: Upload → AI extract → Preview → Import workflow
   - SupplierAutocomplete component linked to Team Directory
   - Added 'address' field to team member model
   - New endpoints: GET /api/team/directory, POST /api/team/extract-contacts, POST /api/projects/{id}/team/bulk
   - Integrated SupplierAutocomplete in AgentInvoiceUpload and AgentQuoteUpload

4. **Timeline Step Management**:
   - "Add Step" button below timeline steps to add new steps
   - Delete (trash) button on each step card
   - New endpoints: POST /api/timeline/{id}/steps, DELETE /api/timeline/steps/{id}
   - Dialog for adding steps with title, description, and date fields

5. **Contact Sales Email**:
   - Updated all "Contact Sales" buttons to use hello@evo-home.ch

6. **Buyer Account Sync & Email Notifications Bug Fix**:
   - Fixed buyer-client linkage issue (buyer_id not set when buyer registers after client created)
   - Added email notifications when feed activities are posted to buyers
   - Added in-app notifications for feed updates
   - New admin endpoints: GET /api/admin/diagnose-buyer/{email}, POST /api/admin/fix-buyer-linkage/{email}
   - Buyer registration now auto-links to existing client records with matching email
   - Added 'feed_update' email template for activity notifications

## Architecture
```
/app
├── backend/
│   ├── server.py      # Monolithic FastAPI (existing endpoints)
│   ├── routes/        # Modular route definitions
│   ├── services/      # Business logic layer
│   ├── models/        # Pydantic models
│   ├── uploads/       # Uploaded files
│   └── .env          # MONGO_URL, API keys
└── frontend/
    └── src/
        ├── pages/agent/   # AgentDashboard, AgentVault, AgentSettings, etc.
        ├── pages/buyer/   # BuyerDashboard, BuyerTimeline
        ├── components/    # LanguageToggle, FileDropZone, PdfViewer, AgentLayout, NotificationCenter
        └── context/       # AuthContext, SettingsContext
```

## Key Endpoints
- `/api/settings` - Agent profile and settings
- `/api/vault/*` - Document vault CRUD
- `/api/vault/{id}/download` - Download vault document
- `/api/buyer/vault` - Get shared documents for buyer
- `/api/timeline/extract` - AI timeline extraction
- `/api/timeline/manual` - Manual timeline creation
- `/api/documents/*` - Quotes/invoices management
- `/api/documents/{id}?force=true` - Delete document (force=true to delete non-draft)
- `/api/documents/{id}/revert-to-draft` - Revert document to Draft status
- `/api/activities/{id}` - Activity CRUD (GET, PUT, DELETE)
- `/api/billing/*` - Stripe subscription management
- `/api/demo/seed` - Seed demo data for production
- `/api/clients/{id}` - Client CRUD with unit assignment (PUT supports force_unit_reassign)
- `/api/projects/{id}/units` - Get project units with assignment status
- `/api/team/directory` - Global team directory with search/filter (for supplier autocomplete)
- `/api/team/extract-contacts` - AI extraction of contacts from documents
- `/api/projects/{id}/team/bulk` - Bulk import team members
- `/api/admin/diagnose-buyer/{email}` - Diagnose buyer-client linkage issues
- `/api/admin/fix-buyer-linkage/{email}` - Fix unlinked client records

---
Last Updated: March 19, 2026

---

## Data Model Normalization Sprint (SSOT) - February 2026

### Phase C: Compatibility Layer (COMPLETE)

**Goal**: Route all database operations through a compatibility layer (`db_compat.py`) that reads from canonical collections first, falls back to deprecated collections during migration.

**Completed Work**:
- [x] Created `db_compat.py` with dual-read helpers for units, timelines, and timeline_steps
- [x] All `db.project_timelines` references in server.py routed through compat layer
- [x] `timeline_id` standardized as canonical field in all API responses
- [x] `project_timeline_id` stripped from all externally visible responses
- [x] New step writes use both FK field names (dual-write) for backward compat
- [x] Dual API routes: `/stages` (deprecated) and `/steps` (canonical) both working
- [x] Governance docs updated (PHASE_C_CONFLICT_REPORT.md, IMPLEMENTATION_IMPACT_MAP.md)
- [x] Regression tests: 16/16 passed (testing agent validated)

**Phase C Done Condition Met**:
- `timelines` is the canonical collection path
- `timeline_id` is the canonical field everywhere externally visible
- `/stages` still works via compatibility
- All tests pass
- Docs are updated

### Phase D: Data Migration (COMPLETE)

**Executed**: 2026-04-10  
**Script**: `/app/backend/migrations/phase_d_migrate.py` (idempotent, all modes: --dry-run, --backup, --execute, --verify, --full)

- [x] Pre-flight backup of all 6 collections (deprecated + canonical)
- [x] M1: `project_units` (17 docs) → `units` — migrated, 0 errors
- [x] M2: `project_timelines` (2 docs) → `timelines` — migrated with `project_timeline_id` → `timeline_id` field rename
- [x] M3: `timeline_steps` field normalization — added `timeline_id` alongside `project_timeline_id` for 12 docs
- [x] Integrity verification: 5/5 checks passed (collection counts, field coverage, referential integrity)
- [x] Idempotency confirmed (second run: 0 inserts, all skipped)
- [x] Post-migration regression: 14/14 API endpoint tests passed
- [x] Migration report: `/app/backend/migrations/MIGRATION_REPORT.md`

### Phase E: Code Refactoring (COMPLETE)

**Executed**: 2026-04-10

- [x] `COMPAT_MODE = False` — disabled fallback reads from deprecated collections
- [x] All `db.project_units` (16 refs) → `db.units` in server.py
- [x] All `db.project_stages` reads → `db.timeline_steps`
- [x] All `$or` queries with `project_timeline_id` simplified to canonical `timeline_id`
- [x] Pydantic `TimelineStep` model dropped deprecated `project_timeline_id` field
- [x] Demo seed writes `timeline_id` only (no dual-write)
- [x] Frontend `AgentWorkflow.js` removed `project_timeline_id` fallback
- [x] Regression: 14/14 tests passed

### Remaining Phases
- **Phase F**: Deprecation Cleanup (remove deprecated collections, endpoints, compat layer)
- **Phase 3**: Architecture (split monolithic server.py into modular routers)

### Key Files
- `/app/backend/core/db_compat.py` - Compatibility layer
- `/app/backend/core/config.py` - Fail-fast startup config
- `/app/memory/PHASE_C_CONFLICT_REPORT.md` - Conflict tracking
- `/app/memory/IMPLEMENTATION_IMPACT_MAP.md` - Implementation control panel
- `/app/memory/DELIVERABLE_1_CANONICAL_SCHEMA.md` - Canonical schema SSOT
- `/app/memory/DELIVERABLE_1B_CONTENT_LAYER_SCHEMA.md` - Content layer schema
- `/app/memory/DELIVERABLE_2_MIGRATION_PLAN.md` - Migration plan
- `/app/memory/DELIVERABLE_3_CODE_AUDIT.md` - Code audit
- `/app/memory/DELIVERABLE_4_IMPLEMENTATION_SEQUENCE.md` - Sequence plan

---
Last Updated: February 2026
