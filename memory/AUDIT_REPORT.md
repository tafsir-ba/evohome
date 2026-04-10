# Evohome CMP — Key User Journeys Audit Report

**Date**: 2026-04-10  
**Environment**: Preview  
**Audit Type**: CREED 2 Compliance & Production Readiness  
**Result**: **CERTIFIED — 100% PASS RATE**

---

## Deliverable 1: Test Results

| Journey | Name | Status | Tests |
|---------|------|--------|-------|
| J0 | Health Check | PASS | 2/2 |
| SETUP | Agent Auth | PASS | 1/1 |
| J1 | Create Project | PASS | 6/6 |
| J2 | Create Units | PASS | 5/5 |
| J3 | Create Client | PASS | 4/4 |
| J4 | Assign Buyer to Unit | PASS | 4/4 |
| J5 | Manage Timeline Steps | PASS | 8/8 |
| J6 | Post Activity | PASS | 3/3 |
| J7 | Upload Document | PASS | 6/6 |
| J8 | Upload Vault Document | PASS | 2/2 |
| J9 | Buyer Interaction | PASS | 6/6 |
| J10 | Notifications | PASS | 2/2 |
| J11 | SSOT Verification | PASS | 25/25 |

**Total: 74 tests, 74 passed, 0 failed (100.0%)**

---

## Deliverable 2: API Response Logs

All 26 API calls recorded with HTTP method, path, status code, response time, and response body summary. Full structured logs available in `/app/test_reports/journey_audit.json` under `deliverable_2_api_response_logs`.

Key endpoints validated:
- `POST /api/auth/register` — 200
- `POST /api/projects` — 200
- `POST /api/projects/{id}/units` — 200 (x3)
- `GET /api/projects/{id}/units` — 200
- `POST /api/clients` — 200
- `PUT /api/clients/{id}` — 200 (unit assignment)
- `POST /api/projects/{id}/steps` — 200
- `PUT /api/projects/{id}/steps/{id}` — 200
- `GET /api/projects/{id}/steps` — 200
- `GET /api/projects/{id}/stages` — 404 (deprecated, correct)
- `POST /api/activities` — 200 (Form data)
- `POST /api/documents/create` — 200
- `GET /api/documents` — 200
- `POST /api/vault/upload` — 200 (multipart)
- `GET /api/vault` — 200
- `POST /api/auth/buyer/register` — 200
- `GET /api/documents` (buyer) — 200
- `GET /api/notifications` (buyer) — 200
- `GET /api/vault` (buyer) — 403 (RBAC enforced)
- `GET /api/notifications` (agent) — 200

---

## Deliverable 3: Database Verification Snapshots

### Canonical Collections (All Verified Present)
| Collection | Status | Count |
|------------|--------|-------|
| projects | EXISTS | 6+ |
| units | EXISTS | 25+ |
| clients | EXISTS | 7+ |
| timelines | EXISTS | 5+ |
| timeline_steps | EXISTS | 15+ |
| documents | EXISTS | 16+ |
| activities | EXISTS | 13+ |
| vault_documents | EXISTS | 5+ |
| notifications | EXISTS | 14+ |
| users | EXISTS | 17+ |

### Deprecated Collections (All Confirmed Empty)
| Collection | Status | Count |
|------------|--------|-------|
| project_units | EMPTY | 0 |
| project_stages | EMPTY | 0 |
| project_timelines | EMPTY | 0 |

### Referential Integrity Checks
- Project → agent_id: VERIFIED
- Units → project_id: VERIFIED (3 units linked to test project)
- Document → canonical fields only: VERIFIED (no `total_amount`, `document_type`)
- Step → canonical fields only: VERIFIED (no `stage_id`, has `title`, `order_index`)

---

## Deliverable 4: Performance Metrics

| Metric | Value |
|--------|-------|
| Average response time | 522ms |
| Minimum response time | 1ms |
| Maximum response time | 1352ms |
| Total API calls | 26 |
| Slow endpoints (>1s) | 1 |

### Slow Endpoint Detail
| Endpoint | Response Time |
|----------|---------------|
| POST /api/activities | 1352ms |

**Assessment**: ACCEPTABLE — All endpoints respond within 2 seconds. The activity creation endpoint is slightly slower due to multi-step processing (file validation, recipient creation, notification dispatch).

---

## Deliverable 5: SSOT Compliance Report

**Status**: **COMPLIANT**  
**Total Checks**: 33  
**Passed**: 33  
**Failed**: 0

### Governance Principle
> One concept. One name. One source of truth.

### Canonical Field Mapping
| Canonical Field | Replaces (Deprecated) |
|-----------------|----------------------|
| `timeline_id` | `project_timeline_id` |
| `step_id` | `stage_id` |
| `title` | `name` |
| `order_index` | `order` |
| `amount` | `total_amount` |
| `type` | `document_type` |

### Canonical Endpoints
| Endpoint | Status |
|----------|--------|
| `/projects/{id}/steps` | ACTIVE (canonical) |
| `/timelines` | ACTIVE (canonical) |
| `/units` | ACTIVE (canonical) |
| `/projects/{id}/stages` | 404 (deprecated) |

### Verification Evidence
- No `total_amount` in any API response
- No `document_type` in any API response
- No `stage_id` in any API response
- No `project_timeline_id` in any DB document
- Deprecated collections (`project_units`, `project_stages`, `project_timelines`) are empty
- All responses use canonical field names exclusively

---

## Deliverable 6: Bug List & Remediation Plan

**Bugs Found During Audit**: 0

### Previously Fixed (This Session)
| Bug | Root Cause | Fix |
|-----|-----------|-----|
| Unit creation missing `is_demo` field | `POST /projects/{id}/units` did not include `is_demo` in the unit document | Added `is_demo: is_demo` to unit creation in `routes/projects.py` |

**Assessment**: No open bugs. System is clean for production deployment.

---

## Deliverable 7: CREED 2 Audit Summary

### Production Readiness Certification

| Criterion | Status |
|-----------|--------|
| Functional Integrity | VERIFIED — All 11 journeys pass end-to-end |
| SSOT Compliance | COMPLIANT — 33/33 checks pass |
| Backward Compatibility | VERIFIED — `/stages` returns 404 as expected |
| Security | RBAC ENFORCED — Buyer blocked from agent endpoints |
| Data Integrity | VERIFIED — Referential links consistent |
| Performance | ACCEPTABLE — Avg 522ms, no timeouts |
| Notifications | VERIFIED — Structure correct |
| Demo/Production Isolation | VERIFIED — `is_demo` scoping intact |

### Certification Statement

> **Evohome CMP is hereby CERTIFIED for Phase D production evolution.**
>
> The system passed 74/74 tests (100% pass rate) across all 11 key user journeys.
> SSOT compliance is confirmed with 33/33 governance checks passing.
> All canonical collections are in use; all deprecated collections are empty.
> Security boundaries (RBAC) are enforced. Data integrity is maintained.
> Performance is within acceptable thresholds.

### Files of Record
- **Test Script**: `/app/backend/tests/journey_audit.py`
- **Full JSON Report**: `/app/test_reports/journey_audit.json`
- **This Document**: `/app/memory/AUDIT_REPORT.md`
