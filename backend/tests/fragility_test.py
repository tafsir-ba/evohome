#!/usr/bin/env python3
"""
Evohome CMP — Structural Fragility Test
Not testing if endpoints return 200.
Testing if the system behaves correctly under real conditions.
"""
import json
import time
import uuid
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone

API = "http://localhost:8001"
PASS = 0
FAIL = 0
FINDINGS = []

def api(method, path, data=None, token=None, form=None):
    url = f"{API}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if form:
        body = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif data:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read().decode() or '{}')
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except:
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  \u2705 {name}")
    else:
        FAIL += 1
        print(f"  \u274c {name} — {detail}")
        FINDINGS.append({"test": name, "detail": detail})

def section(t):
    print(f"\n{'='*60}\n  {t}\n{'='*60}")

# ════════════════════════════════════════════════════════════
section("PHASE 1: AUTH EDGE CASES")
# ════════════════════════════════════════════════════════════

# Register
email = f"fragility.{uuid.uuid4().hex[:6]}@test.com"
c, d = api("POST", "/api/auth/register", {"email": email, "password": "Test2026!", "name": "Fragility Test"})
TOKEN = d.get("token", "")
AGENT_ID = d.get("user_id", "")
check("Register returns token", bool(TOKEN))
check("Register returns user_id", bool(AGENT_ID))

# Duplicate registration
c2, d2 = api("POST", "/api/auth/register", {"email": email, "password": "Test2026!", "name": "Duplicate"})
check("Duplicate email rejected", c2 in [400, 409], f"got {c2}")

# Login
c, d = api("POST", "/api/auth/login", {"email": email, "password": "Test2026!"})
check("Login works", c == 200 and bool(d.get("token")))
TOKEN = d.get("token", TOKEN)

# Wrong password
c, d = api("POST", "/api/auth/login", {"email": email, "password": "wrong"})
check("Wrong password rejected", c in [401, 403], f"got {c}")

# No token
c, d = api("GET", "/api/projects")
check("No-auth request rejected", c == 401, f"got {c}")

# Invalid token
c, d = api("GET", "/api/projects", token="invalid.token.here")
check("Invalid token rejected", c == 401, f"got {c}")

# ════════════════════════════════════════════════════════════
section("PHASE 2: PROJECT + UNIT CREATION & EDGE CASES")
# ════════════════════════════════════════════════════════════

c, d = api("POST", "/api/projects", {"name": "Test Project Alpha", "total_units": 3}, TOKEN)
PID = d.get("project_id", "")
check("Create project", c == 200 and bool(PID), f"got {c}: {d}")

# Create 2 units (free plan allows 2)
c, d = api("POST", f"/api/projects/{PID}/units", {"unit_reference": "Lot A1"}, TOKEN)
UID1 = d.get("unit_id", "")
check("Create unit 1", c == 200 and bool(UID1))

c, d = api("POST", f"/api/projects/{PID}/units", {"unit_reference": "Lot A2"}, TOKEN)
UID2 = d.get("unit_id", "")
check("Create unit 2", c == 200 and bool(UID2))

# Free plan limit: 3rd unit should fail
c, d = api("POST", f"/api/projects/{PID}/units", {"unit_reference": "Lot A3"}, TOKEN)
check("Free plan blocks 3rd unit", c == 403, f"got {c}")

# Duplicate unit reference
c, d = api("POST", f"/api/projects/{PID}/units", {"unit_reference": "Lot A1"}, TOKEN)
check("Duplicate unit ref handled", c in [400, 403, 409, 200], f"got {c}")

# Get units
c, d = api("GET", f"/api/projects/{PID}/units", token=TOKEN)
check("List units returns array", c == 200 and isinstance(d, list))
check("Exactly 2 units", len(d) == 2 if isinstance(d, list) else False, f"got {len(d) if isinstance(d, list) else d}")

# Verify unit excludes is_demo field (canonical rebuild)
if isinstance(d, list) and d:
    check("Unit excludes is_demo field", "is_demo" not in d[0], f"keys: {list(d[0].keys())[:10]}")
    check("Unit has project_id", d[0].get("project_id") == PID)

# ════════════════════════════════════════════════════════════
section("PHASE 3: CLIENT CREATION & CROSS-REFERENCES")
# ════════════════════════════════════════════════════════════

c, d = api("POST", "/api/clients", {
    "name": "Sophie Martin", "email": "sophie@test.com",
    "phone": "+41791234567", "project_id": PID
}, TOKEN)
CID = d.get("client_id", "")
check("Create client", c == 200 and bool(CID))
check("Client has agent_id", d.get("agent_id") == AGENT_ID)
check("Client has project_id", d.get("project_id") == PID)

# Assign client to unit
c, d = api("PUT", f"/api/clients/{CID}", {"unit_id": UID1}, TOKEN)
check("Assign client to unit", c == 200)
check("Client.unit_id updated", d.get("unit_id") == UID1)

# Verify cross-reference: unit should show assignment
c, d = api("GET", f"/api/projects/{PID}/units", token=TOKEN)
if isinstance(d, list):
    assigned = next((u for u in d if u.get("unit_id") == UID1), {})
    check("Unit shows assigned_client_id", assigned.get("assigned_client_id") == CID,
          f"got: {assigned.get('assigned_client_id')}")

# Project context endpoint
c, d = api("GET", f"/api/projects/{PID}/context", token=TOKEN)
check("Project context returns 200", c == 200)
check("Context has units", len(d.get("units", [])) == 2, f"units: {len(d.get('units', []))}")
check("Context has clients", len(d.get("clients", [])) >= 1, f"clients: {len(d.get('clients', []))}")

# Client preview (was crashing due to missing enrich_activity import)
c, d = api("GET", f"/api/clients/{CID}/preview", token=TOKEN)
check("Client preview works", c == 200, f"got {c}: {str(d)[:100]}")

# ════════════════════════════════════════════════════════════
section("PHASE 4: DOCUMENT LIFECYCLE")
# ════════════════════════════════════════════════════════════

# Create quote
c, d = api("POST", "/api/documents/create", {
    "type": "quote", "title": "Kitchen Renovation",
    "amount": 15000, "client_id": CID, "project_id": PID,
    "items": [
        {"description": "Cabinets", "quantity": 1, "unit_price": 10000, "total": 10000},
        {"description": "Countertop", "quantity": 1, "unit_price": 5000, "total": 5000}
    ], "currency": "CHF"
}, TOKEN)
DOC_ID = d.get("document_id", "")
check("Create document", c == 200 and bool(DOC_ID))
check("Doc uses canonical 'type' not 'document_type'", "type" in d and "document_type" not in d)
check("Doc uses canonical 'amount' not 'total_amount'", "amount" in d and "total_amount" not in d)
check("Doc amount correct", d.get("amount") == 15000)
check("Doc has items", len(d.get("items", [])) == 2)

# List documents
c, d = api("GET", "/api/documents", token=TOKEN)
check("List documents", c == 200 and isinstance(d, list))
check("Created doc appears in list", any(doc.get("document_id") == DOC_ID for doc in d) if isinstance(d, list) else False)

# Get single document
c, d = api("GET", f"/api/documents/{DOC_ID}", token=TOKEN)
check("Get document by ID", c == 200 and d.get("document_id") == DOC_ID)

# Generate PDF (uses reportlab — was crashing)
c, d = api("GET", f"/api/documents/{DOC_ID}/pdf", token=TOKEN)
check("PDF generation works", c == 200, f"got {c}: {str(d)[:100]}")

# Create invoice
c, d = api("POST", "/api/documents/create", {
    "type": "invoice", "title": "Kitchen Invoice",
    "amount": 15000, "client_id": CID, "project_id": PID,
    "items": [{"description": "Kitchen complete", "quantity": 1, "unit_price": 15000, "total": 15000}]
}, TOKEN)
INV_ID = d.get("document_id", "")
check("Create invoice", c == 200 and bool(INV_ID))
check("Invoice type is 'invoice'", d.get("type") == "invoice")

# ════════════════════════════════════════════════════════════
section("PHASE 5: TIMELINE STEPS (CANONICAL)")
# ════════════════════════════════════════════════════════════

c, d = api("POST", f"/api/projects/{PID}/steps", {
    "title": "Foundation Work", "description": "Excavation and pouring",
    "order_index": 1, "planned_start": "2026-04-01", "planned_end": "2026-05-15"
}, TOKEN)
STEP_ID = d.get("step_id", "")
check("Create step", c == 200 and bool(STEP_ID))
check("Step uses step_id (not stage_id)", "step_id" in d and "stage_id" not in d)
check("Step uses title (not name)", d.get("title") == "Foundation Work")
check("Step uses order_index", "order_index" in d)

# Update step
c, d = api("PUT", f"/api/projects/{PID}/steps/{STEP_ID}", {
    "status": "in_progress", "progress_percent": 40
}, TOKEN)
check("Update step status", c == 200 and d.get("status") == "in_progress")

# List steps
c, d = api("GET", f"/api/projects/{PID}/steps", token=TOKEN)
check("List steps", c == 200 and "steps" in d if isinstance(d, dict) else False)

# Deprecated /stages endpoint
c, d = api("GET", f"/api/projects/{PID}/stages", token=TOKEN)
check("/stages returns 404 (deprecated)", c == 404)

# ════════════════════════════════════════════════════════════
section("PHASE 6: ACTIVITIES (FORM DATA)")
# ════════════════════════════════════════════════════════════

c, d = api("POST", "/api/activities", token=TOKEN, form={
    "type": "message", "title": "Construction Update",
    "content": "Foundation work is 40% complete",
    "project_id": PID, "client_ids": CID
})
ACT_ID = d.get("activity_id", "")
check("Create activity (form data)", c == 200 and bool(ACT_ID))

# ════════════════════════════════════════════════════════════
section("PHASE 7: VAULT (FILE UPLOAD)")
# ════════════════════════════════════════════════════════════

# We need multipart for vault — skip in this script (tested by testing agent)
# Just verify the list endpoint works
c, d = api("GET", "/api/vault", token=TOKEN)
check("Vault list works", c == 200 and isinstance(d, list))

# ════════════════════════════════════════════════════════════
section("PHASE 8: COMMAND CENTER FLOW")
# ════════════════════════════════════════════════════════════

# Command recent work
c, d = api("GET", "/api/command/recent-work", token=TOKEN)
check("Recent work endpoint", c == 200, f"got {c}")

# ════════════════════════════════════════════════════════════
section("PHASE 9: BILLING")
# ════════════════════════════════════════════════════════════

c, d = api("POST", "/api/billing/create-checkout-session", {
    "plan_id": "starter", "origin_url": "https://app.evo-home.ch"
}, TOKEN)
check("Stripe checkout returns URL", c == 200 and bool(d.get("checkout_url")))
check("Checkout URL is Stripe", d.get("checkout_url", "").startswith("https://checkout.stripe.com"))

# Invalid plan
c, d = api("POST", "/api/billing/create-checkout-session", {
    "plan_id": "nonexistent", "origin_url": "https://app.evo-home.ch"
}, TOKEN)
check("Invalid plan rejected", c in [400, 404], f"got {c}")

# ════════════════════════════════════════════════════════════
section("PHASE 10: NOTIFICATIONS")
# ════════════════════════════════════════════════════════════

c, d = api("GET", "/api/notifications", token=TOKEN)
check("Notifications endpoint", c == 200)
check("Notifications has structure", isinstance(d, dict) and "notifications" in d and "unread_count" in d,
      f"keys: {list(d.keys()) if isinstance(d, dict) else type(d)}")

# ════════════════════════════════════════════════════════════
section("PHASE 11: BUYER RBAC ISOLATION")
# ════════════════════════════════════════════════════════════

buyer_email = f"buyer.{uuid.uuid4().hex[:6]}@test.com"
c, d = api("POST", "/api/auth/buyer/register", {
    "email": buyer_email, "password": "Buyer2026!", "name": "Test Buyer"
})
BUYER_TOKEN = d.get("token", "")
check("Buyer registration", c == 200 and bool(BUYER_TOKEN))
check("Buyer role is 'buyer'", d.get("role") == "buyer")

# Buyer CANNOT access agent-only endpoints
c, d = api("GET", "/api/vault", token=BUYER_TOKEN)
check("Buyer blocked from vault (RBAC)", c == 403, f"got {c}")

c, d = api("POST", "/api/projects", {"name": "Buyer Project"}, BUYER_TOKEN)
check("Buyer blocked from creating projects", c in [403, 401], f"got {c}")

c, d = api("GET", "/api/notifications", token=BUYER_TOKEN)
check("Buyer CAN access notifications", c == 200)

# ════════════════════════════════════════════════════════════
section("PHASE 12: SSOT DATABASE AUDIT")
# ════════════════════════════════════════════════════════════

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def db_audit():
    sys.path.insert(0, '/app/backend')
    from core.config import validate_config
    cfg = validate_config()
    client = AsyncIOMotorClient(os.environ.get('MONGO_URL'))
    db = client[cfg.get_database_name()]
    
    results = []
    
    # Check project in DB
    proj = await db.projects.find_one({"project_id": PID}, {"_id": 0})
    if proj:
        results.append(("Project has agent_id in DB", proj.get("agent_id") == AGENT_ID))
        results.append(("Project has NO legacy 'stages' field", "stages" not in proj))
        results.append(("Project excludes is_demo field", "is_demo" not in proj))
    
    # Check document in DB
    doc = await db.documents.find_one({"document_id": DOC_ID}, {"_id": 0})
    if doc:
        results.append(("Doc has canonical 'type' in DB", "type" in doc))
        results.append(("Doc has NO 'document_type' in DB", "document_type" not in doc))
        results.append(("Doc has canonical 'amount' in DB", "amount" in doc))
        results.append(("Doc has NO 'total_amount' in DB", "total_amount" not in doc))
    
    # Check step in DB
    step = await db.timeline_steps.find_one({"step_id": STEP_ID}, {"_id": 0})
    if step:
        results.append(("Step has NO 'stage_id' in DB", "stage_id" not in step))
        results.append(("Step has canonical 'title' in DB", "title" in step))
        results.append(("Step has canonical 'order_index' in DB", "order_index" in step))
    
    # Check deprecated collections empty
    for coll in ["project_units", "project_stages", "project_timelines"]:
        count = await db[coll].count_documents({})
        results.append((f"Deprecated '{coll}' is empty", count == 0))
    
    client.close()
    return results

os.chdir('/app/backend')
for name, passed in asyncio.run(db_audit()):
    check(f"[DB] {name}", passed)

# ════════════════════════════════════════════════════════════
section("PHASE 13: INFRASTRUCTURE")
# ════════════════════════════════════════════════════════════

c, d = api("GET", "/api/health")
check("Health liveness", c == 200 and d.get("status") == "alive")

c, d = api("GET", "/api/ready")
check("Readiness probe", c == 200 and d.get("status") == "ready")
check("DB connected", d.get("database") == "ok")
check("Email enabled", d.get("features", {}).get("email") == True)
check("Billing enabled", d.get("features", {}).get("billing") == True)
check("AI enabled", d.get("features", {}).get("ai_extraction") == True)

# ════════════════════════════════════════════════════════════
section("VERDICT")
# ════════════════════════════════════════════════════════════

total = PASS + FAIL
print(f"\n  Total:   {total}")
print(f"  Passed:  {PASS}")
print(f"  Failed:  {FAIL}")
print(f"  Rate:    {PASS/total*100:.1f}%" if total else "  Rate:    N/A")

if FINDINGS:
    print(f"\n  --- FAILURES ---")
    for f in FINDINGS:
        print(f"    \u274c {f['test']}: {f['detail']}")

# Classification
if FAIL == 0:
    print(f"\n  VERDICT: SYSTEM STABLE")
    print(f"  No structural fragility detected. Isolated fixes were sufficient.")
    verdict = "STABLE"
elif FAIL <= 3:
    print(f"\n  VERDICT: ISOLATED BUGS")
    print(f"  {FAIL} failure(s) — fixable without rebuild.")
    verdict = "ISOLATED"
else:
    print(f"\n  VERDICT: STRUCTURAL FRAGILITY")
    print(f"  {FAIL} failures across multiple phases — rebuild recommended.")
    verdict = "FRAGILE"

# Save report
report = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "total": total, "passed": PASS, "failed": FAIL,
    "pass_rate": f"{PASS/total*100:.1f}%" if total else "N/A",
    "verdict": verdict,
    "findings": FINDINGS
}
os.makedirs("/app/test_reports", exist_ok=True)
with open("/app/test_reports/fragility_test.json", "w") as f:
    json.dump(report, f, indent=2)
print(f"\n  Report: /app/test_reports/fragility_test.json")
