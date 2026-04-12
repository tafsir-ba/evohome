# Evohome CMP — Product Requirements Document

## Architecture
- **Backend**: FastAPI + Motor (MongoDB async) — canonical SSOT services, thin routes
- **Frontend**: React 18 + TailwindCSS + Shadcn/UI
- **Database**: MongoDB Atlas (`evohome_cmp`)
- **File Storage**: DigitalOcean Spaces (`evohome-assets.fra1`)
- **Debug Console**: Standalone at /api/internal/debug (DEBUG_SECRET auth)

## Buyer Portal Service (NEW — April 12, 2026)
Single endpoint `GET /api/buyer/portal` replaces 8+ scattered API calls.
Returns everything the buyer needs in one response:
- **project**: name, unit_reference, address (all resolved from units/projects collections)
- **branding**: company_name, logo_url (absolute Spaces URL)
- **documents**: quotes + invoices with hero images (absolute URLs), status, items, amounts
- **vault_files**: shared docs with direct Spaces URLs (no CORS redirect)
- **change_requests**: CR threads with messages
- **decisions**: pending buyer decisions
- **team**: project team members
- **construction_timeline**: timeline with steps
- **unread_count**: notification count

### Why This Exists
Previously the buyer frontend made 8+ separate API calls, each with its own query, enrichment logic, and URL resolution. When agent mutations happened (upload, share, assign unit), the buyer's view broke because the stitching was fragile. The portal service computes everything server-side in one pass.

## File Storage (DigitalOcean Spaces)
- All uploads (logo, hero, vault, PDF) stored in `evohome-assets.fra1.digitaloceanspaces.com/uploads/`
- Files survive container restarts and deploys
- Frontend uses direct Spaces URLs (no CORS redirect through backend)
- Validation: MIME type OR extension match (handles macOS `application/octet-stream`)
- HEIC/HEIF supported for Apple device photos

## Bugs Fixed (April 12, 2026)
- **BUG-003**: Hero image upload — HEIC rejection, file size error toast missing, auto-save draft
- **Vault CORS**: Direct Spaces URLs instead of redirect-through-backend
- **Vault buyer access**: Query by client_ids, not just buyer_ids (race condition fix)
- **Rejected docs**: Removed from FINALIZED_STATUSES, agent can edit and revert to Draft
- **Buyer profile**: Unit reference enriched from units collection
- **Client detail**: project_name enrichment added to get_client()

## Test Accounts
- Agent (production): tafsir@evo-home.ch / evoagent123
- Buyer (production): batafsir3@gmail.com (Google OAuth only)

## Remaining
- P0: Deploy and verify all fixes on production
- P1: Organ 4 — Control Tower Dashboard restructuring  
- P1: Organ 5 — Decisions rebuild
- P2: Sync pipeline (agent mutations auto-propagate to buyer portal cache)
- P2: Hook dependency warnings (74+ instances)
- P3: Email digests, reporting/export

---
Last Updated: April 12, 2026
