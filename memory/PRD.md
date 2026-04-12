# Evohome CMP — Product Requirements Document

## Architecture
- **Backend**: FastAPI + Motor (MongoDB async) — canonical SSOT services, thin routes
- **Frontend**: React 18 + TailwindCSS + Shadcn/UI
- **Database**: MongoDB Atlas (`evohome_cmp`)

## UI-Verified Items (Screenshot Proof)

### Organ 1 — Upload/Media
| Item | Evidence |
|------|----------|
| BUG-003: Hero image on edit page | Image visible at /agent/quotes/edit/{id} |
| BUG-004: Buyer sees hero image | Blue gradient banner visible on buyer timeline card |
| BUG-005: Vault upload through UI | File chooser → form fill → "Document uploaded successfully" toast → card appears |
| BUG-006: Vault download through UI | Click Download → file saved (9566 bytes matches upload) |

### Organ 2 — Client Context
| Item | Evidence |
|------|----------|
| BUG-011: Clients list | Project + unit badges visible on client card |
| BUG-012: Client detail | Project name "Résidence Les Pins" + "Lot 3.01" visible |

### Organ 3 — Change Requests
| Item | Evidence |
|------|----------|
| BUG-022: Buyer creates CR | "Question sent to your agent" toast, status → "UNDER REVIEW" |
| BUG-024: Buyer notification | Agent notification: "[change_request_created] New Change Request" |
| BUG-025: CR notification content | Buyer: "[change_request_response]" + "[change_request_resolved]" with correct text |
| BUG-026: Agent reply on quote | "Response sent" toast, thread shows buyer + agent messages |
| BUG-028: Resolve + Close | "Change request resolved" → "Resolved" badge → "Change request closed" → "Closed" badge |

### Bug Fixed During Verification
- **CR notification parameter mismatch**: `_notify()` passed `data=data` instead of `metadata=data`, causing all CR notifications to silently fail

## Items NOT Yet UI-Verified
- BUG-007: Authenticated vault access (verified via API only)
- BUG-008: Legacy file compatibility (verified via API only)
- BUG-013: Client preview context (code verified, not screenshot)
- BUG-014: Project endpoint (verified via curl)
- BUG-015: Formatter consistency (verified via grep)
- BUG-016: Invoice upload parity (verified in earlier session, not re-verified post-wipe)
- BUG-027: Quote/invoice full parity (quote verified, invoice not tested through full CR UI flow)
- BUG-029-032: Dashboard aggregation (Control Tower shows count, detailed cards on legacy route only)

## Remaining
- P0: Production deployment + verification on app.evo-home.ch
- P1: Organ 4 — Control Tower Dashboard (move CR detail cards to primary dashboard)
- P1: Organ 5 — Decisions rebuild
- P2: Hook dependency warnings
- P3: Email digests, reporting/export

---
Last Updated: April 12, 2026
