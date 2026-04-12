# Evohome CMP — Product Requirements Document

## Architecture
- **Backend**: FastAPI + Motor (MongoDB async) — canonical SSOT services, thin routes
- **Frontend**: React 18 + TailwindCSS + Shadcn/UI
- **Database**: MongoDB Atlas (`evohome_cmp`)
- **Debug Console**: Standalone at /api/internal/debug (DEBUG_SECRET auth)

## 36-Item Verification Checklist — Executed April 12, 2026

**Results: 35 PASSED / 0 FAILED / 1 UNTESTED (BUG-008: no legacy data)**

### Organ 1: Upload/Media (10 items — 9 passed, 1 untested)
| ID | Name | Status | Evidence |
|----|------|--------|----------|
| BUG-001 | Logo Upload API | PASSED | POST returns {url, filename, size}. HTTP 200. |
| BUG-002 | Logo Display | PASSED | logo_url stored in GET /api/settings |
| BUG-003 | Hero Image Upload | PASSED | Hero image stored on document |
| BUG-004 | Buyer Hero Image | PASSED | Buyer timeline returns heroImageUrl |
| BUG-005 | Vault Upload UI | PASSED | Returns vault_document_id. HTTP 200. |
| BUG-006 | Vault Download | PASSED | Returns file. HTTP 200. |
| BUG-007 | Vault Auth | PASSED | Unauthenticated returns HTTP 401 |
| BUG-008 | Legacy Compat | UNTESTED | No pdf_path documents in DB |
| BUG-009 | Upload Validation | PASSED | Wrong type rejected with canonical error |
| BUG-010 | Upload Error Shape | PASSED | {error, message, request_id, source} |

### Organ 2: Client Context (10 items — 10 passed)
| ID | Name | Status | Evidence |
|----|------|--------|----------|
| BUG-011 | Clients List Context | PASSED | project_name + unit_reference enriched |
| BUG-012 | Client Detail Context | PASSED | **Fixed this session** — added enrichment to get_client |
| BUG-013 | Client Preview Context | PASSED | formatContextSubtitle used |
| BUG-014 | Project Endpoint | PASSED | GET /api/projects/{id} returns name |
| BUG-015 | Formatter Consistency | PASSED | Zero inline patterns outside utils.js |
| BUG-016 | Invoice Upload Parity | PASSED | Uses formatContextSubtitle |
| BUG-017 | Quote List Format | PASSED | Uses formatDocContext |
| BUG-018 | Invoice List Format | PASSED | Uses formatDocContext |
| BUG-019 | Dashboard Format | PASSED | Uses formatDocContext |
| BUG-020 | Decisions Format | PASSED | Uses formatClientContext |

### Organ 3: Change Requests (12 items — 12 passed)
| ID | Name | Status | Evidence |
|----|------|--------|----------|
| BUG-021 | CR Create | PASSED | Doc status → Change Requested |
| BUG-022 | CR Reply | PASSED | CR status → under_review |
| BUG-023 | CR Resolve | PASSED | Doc status → Sent (NOT Draft) |
| BUG-024 | CR Notification - Create | PASSED | Agent notified (change_request_created) |
| BUG-025 | CR Notification - Respond | PASSED | Buyer notified (change_request_response) |
| BUG-026 | CR Notification - Resolve | PASSED | Buyer notified (change_request_resolved) |
| BUG-027 | CR Close | PASSED | Terminal state: closed |
| BUG-028 | CR State Guards | PASSED | Cannot respond to closed CR |
| BUG-029 | Quote/Invoice Parity | PASSED | Same code path for both types |
| BUG-030 | Buyer Thread Visibility | PASSED | Full thread via entity endpoint |
| BUG-031 | Dashboard CR Aggregation | PASSED | Stats returns change_requests + count |
| BUG-032 | Dashboard CR Navigation | PASSED | Links to /agent/quotes or /invoices by type |

### System (4 items — 4 passed)
| ID | Name | Status | Evidence |
|----|------|--------|----------|
| BUG-033 | Canonical Error Shape | PASSED | {error, message, request_id, source} |
| BUG-034 | Request ID Propagation | PASSED | x-request-id header on all responses |
| BUG-035 | Trace Events | PASSED | 135 trace events in DB |
| BUG-036 | Debug Console | PASSED | Accessible at /api/internal/debug |

## Bugs Found & Fixed During Checklist Execution
1. **BUG-012**: `get_client()` returned raw DB doc without project_name/unit_reference enrichment. Fixed by adding project+unit lookups.
2. **Missing trace coverage**: `confirm_payment` and `convert_to_invoice` had no trace instrumentation. Fixed.
3. **Missing related_entities**: CR creation didn't link back to parent document. Fixed.
4. **Missing response_summary**: `request_change` action didn't record state transition. Fixed.

## Test Accounts
- Agent: agent@evohome-test.ch / Evohome2026!
- Buyer: buyer@evohome-test.ch / Evohome2026!

## Remaining
- P1: Organ 4 — Control Tower Dashboard restructuring
- P1: Organ 5 — Decisions rebuild
- P2: Hook dependency warnings (74+ instances)
- P3: Email digests, reporting/export
- P3: Dead code cleanup (parseApiError in api.js)
- P3: Refactor debug console JS to ES modules

---
Last Updated: April 12, 2026
