"""
Internal Debug API Routes.

External debugging & verification console.
All routes require DEBUG_SECRET bearer token.
Not part of the main app. Not exposed in app navigation.
"""
import os
import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import FileResponse
from database import db

logger = logging.getLogger(__name__)

router = APIRouter()

DEBUG_SECRET = os.environ.get("DEBUG_SECRET", "")
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
DEBUG_STATIC_DIR = os.path.join(STATIC_DIR, "debug")

MIME_MAP = {".css": "text/css", ".js": "application/javascript"}


async def require_debug_auth(request: Request):
    """Verify DEBUG_SECRET bearer token. Not a JWT. Simple comparison."""
    if not DEBUG_SECRET:
        raise HTTPException(status_code=503, detail={
            "error": "debug_disabled", "message": "DEBUG_SECRET not configured", "source": "api"
        })
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or auth[7:] != DEBUG_SECRET:
        raise HTTPException(status_code=401, detail={
            "error": "unauthorized", "message": "Invalid debug token", "source": "api"
        })


@router.get("/internal/debug")
async def debug_console():
    """Serve the standalone debug console HTML."""
    html_path = os.path.join(DEBUG_STATIC_DIR, "index.html")
    if not os.path.exists(html_path):
        raise HTTPException(status_code=404, detail="Debug console not found")
    return FileResponse(html_path, media_type="text/html")


@router.get("/internal/debug/css/{filename}")
async def debug_css(filename: str):
    """Serve debug console CSS assets."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=404)
    filepath = os.path.join(DEBUG_STATIC_DIR, "css", filename)
    real = os.path.realpath(filepath)
    if not real.startswith(os.path.realpath(DEBUG_STATIC_DIR)) or not os.path.exists(real):
        raise HTTPException(status_code=404)
    return FileResponse(real, media_type="text/css")


@router.get("/internal/debug/js/{filename}")
async def debug_js(filename: str):
    """Serve debug console JS assets."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=404)
    filepath = os.path.join(DEBUG_STATIC_DIR, "js", filename)
    real = os.path.realpath(filepath)
    if not real.startswith(os.path.realpath(DEBUG_STATIC_DIR)) or not os.path.exists(real):
        raise HTTPException(status_code=404)
    return FileResponse(real, media_type="application/javascript")


@router.get("/internal/debug/health")
async def debug_health(_=Depends(require_debug_auth)):
    """Debug system health check."""
    try:
        trace_count = await db.trace_events.count_documents({})
        last_trace = await db.trace_events.find_one(
            {}, {"_id": 0, "created_at": 1}, sort=[("created_at", -1)]
        )
        return {
            "status": "ok",
            "trace_count": trace_count,
            "last_trace_at": last_trace.get("created_at") if last_trace else None,
            "collections": await db.list_collection_names(),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/internal/debug/traces")
async def list_traces(
    outcome: Optional[str] = None,
    errors_only: bool = False,
    method: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    _=Depends(require_debug_auth),
):
    """List trace events with filters."""
    query = {}
    if errors_only:
        query["outcome"] = {"$ne": "success"}
    elif outcome:
        query["outcome"] = outcome
    if method:
        query["method"] = method.upper()
    if entity_type:
        query["entity_type"] = entity_type
    if entity_id:
        query["entity_id"] = entity_id
    if action:
        query["action"] = {"$regex": action, "$options": "i"}

    total = await db.trace_events.count_documents(query)
    traces = await db.trace_events.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(offset).limit(min(limit, 200)).to_list(min(limit, 200))

    return {"traces": traces, "total": total, "limit": limit, "offset": offset}


@router.get("/internal/debug/traces/{trace_id}")
async def get_trace(trace_id: str, _=Depends(require_debug_auth)):
    """Get single trace detail."""
    trace = await db.trace_events.find_one({"trace_id": trace_id}, {"_id": 0})
    if not trace:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "message": f"Trace {trace_id} not found", "source": "api"
        })
    return trace


@router.get("/internal/debug/entity/{entity_type}/{entity_id}")
async def inspect_entity(entity_type: str, entity_id: str, _=Depends(require_debug_auth)):
    """Inspect entity state + related traces + notifications + state transitions."""
    # Resolve collection and ID field
    collection_map = {
        "document": ("documents", "document_id"),
        "quote": ("documents", "document_id"),
        "invoice": ("documents", "document_id"),
        "vault_document": ("vault_documents", "vault_document_id"),
        "client": ("clients", "client_id"),
        "change_request": ("change_requests", "change_request_id"),
        "decision": ("decisions", "decision_id"),
        "user": ("users", "user_id"),
    }

    mapping = collection_map.get(entity_type)
    if not mapping:
        raise HTTPException(status_code=400, detail={
            "error": "invalid_entity_type",
            "message": f"Unknown entity type: {entity_type}. Valid: {list(collection_map.keys())}",
            "source": "validation",
        })

    col_name, id_field = mapping

    # Current state
    entity = await db[col_name].find_one({id_field: entity_id}, {"_id": 0})

    # Related traces
    traces = await db.trace_events.find(
        {"entity_type": entity_type, "entity_id": entity_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)

    # Also find traces that reference this entity via related_entities or endpoint URL
    url_traces = await db.trace_events.find(
        {"$or": [
            {"endpoint": {"$regex": entity_id}},
            {"related_entities": {"$elemMatch": {"entity_type": entity_type, "entity_id": entity_id}}},
        ]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(20)

    # Merge and deduplicate
    seen_ids = {t["trace_id"] for t in traces}
    for t in url_traces:
        if t["trace_id"] not in seen_ids:
            traces.append(t)
            seen_ids.add(t["trace_id"])

    # Sort by created_at desc
    traces.sort(key=lambda t: t.get("created_at", ""), reverse=True)

    # Related notifications
    notifications = []
    try:
        notifs = await db.notifications.find(
            {"$or": [
                {"metadata.entity_id": entity_id},
                {"metadata.document_id": entity_id},
                {"metadata.change_request_id": entity_id},
                {"metadata.vault_document_id": entity_id},
                {"metadata.decision_id": entity_id},
            ]},
            {"_id": 0}
        ).sort("created_at", -1).to_list(20)
        notifications = notifs
    except Exception:
        pass

    # Related change requests (if entity is a document)
    change_requests = []
    if entity_type in ("document", "quote", "invoice"):
        crs = await db.change_requests.find(
            {"entity_id": entity_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(10)
        change_requests = crs

    # State transitions (computed from traces)
    state_transitions = []
    for t in reversed(traces):
        resp = t.get("response_summary", {})
        if "status" in resp:
            state_transitions.append({
                "status": resp["status"],
                "action": t.get("action"),
                "timestamp": t.get("created_at"),
                "user_id": t.get("user_id"),
                "request_id": t.get("request_id"),
            })

    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "exists": entity is not None,
        "current_state": entity,
        "traces": traces[:50],
        "notifications": notifications,
        "change_requests": change_requests,
        "state_transitions": state_transitions,
    }


@router.get("/internal/debug/verifications")
async def list_verifications(_=Depends(require_debug_auth)):
    """List verification checklist items."""
    items = await db.debug_verifications.find({}, {"_id": 0}).sort("item_id", 1).to_list(100)
    if not items:
        # Seed with initial checklist
        await _seed_verification_checklist()
        items = await db.debug_verifications.find({}, {"_id": 0}).sort("item_id", 1).to_list(100)
    return {"items": items}


@router.put("/internal/debug/verifications/{item_id}")
async def update_verification(item_id: str, request: Request, _=Depends(require_debug_auth)):
    """Update a verification item status."""
    body = await request.json()
    allowed = {"status", "notes", "verified_by", "evidence"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if "status" in updates and updates["status"] not in ("untested", "passed", "failed"):
        raise HTTPException(status_code=400, detail={
            "error": "invalid_status", "message": "Status must be: untested, passed, failed", "source": "validation"
        })
    updates["last_verified"] = datetime.now(timezone.utc).isoformat()

    result = await db.debug_verifications.find_one_and_update(
        {"item_id": item_id},
        {"$set": updates},
        return_document=True,
        projection={"_id": 0},
    )
    if not result:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "message": f"Verification item {item_id} not found", "source": "api"
        })
    return result


async def _seed_verification_checklist():
    """Seed the 36-item bug matrix as verification checklist."""
    items = [
        ("BUG-001", "Organ 1", "Logo Upload API", "POST /api/settings/logo returns canonical response"),
        ("BUG-002", "Organ 1", "Logo Display", "Logo URL renders in settings page"),
        ("BUG-003", "Organ 1", "Hero Image Upload", "Upload hero image on quote edit page"),
        ("BUG-004", "Organ 1", "Buyer Hero Image", "Buyer sees hero image on timeline card"),
        ("BUG-005", "Organ 1", "Vault Upload UI", "Upload document through vault modal"),
        ("BUG-006", "Organ 1", "Vault Download", "Download vault document through UI"),
        ("BUG-007", "Organ 1", "Vault Auth", "Unauthenticated vault access fails"),
        ("BUG-008", "Organ 1", "Legacy Compat", "Old pdf_path documents still serve"),
        ("BUG-009", "Organ 1", "Upload Validation", "Oversized/wrong-type files rejected with canonical error"),
        ("BUG-010", "Organ 1", "Upload Error Shape", "Upload errors return {error, message, request_id, source}"),
        ("BUG-011", "Organ 2", "Clients List Context", "Client cards show project + unit badges"),
        ("BUG-012", "Organ 2", "Client Detail Context", "Client detail shows project name, not raw ID"),
        ("BUG-013", "Organ 2", "Client Preview Context", "Client preview uses formatContextSubtitle"),
        ("BUG-014", "Organ 2", "Project Endpoint", "GET /api/projects/{id} returns project with name"),
        ("BUG-015", "Organ 2", "Formatter Consistency", "Zero inline .filter(Boolean).join patterns"),
        ("BUG-016", "Organ 2", "Invoice Upload Parity", "Invoice upload shows same context subtitle as quote"),
        ("BUG-017", "Organ 2", "Quote List Format", "Quotes list uses formatDocContext"),
        ("BUG-018", "Organ 2", "Invoice List Format", "Invoices list uses formatDocContext"),
        ("BUG-019", "Organ 2", "Dashboard Format", "Dashboard CR cards use formatDocContext"),
        ("BUG-020", "Organ 2", "Decisions Format", "Decisions picker uses formatClientContext"),
        ("BUG-021", "Organ 3", "CR Create", "Buyer creates CR, doc status → Change Requested"),
        ("BUG-022", "Organ 3", "CR Reply", "Agent replies, CR status → under_review"),
        ("BUG-023", "Organ 3", "CR Resolve", "Agent resolves, doc status → Sent (NOT Draft)"),
        ("BUG-024", "Organ 3", "CR Notification - Create", "Agent notified when buyer creates CR"),
        ("BUG-025", "Organ 3", "CR Notification - Respond", "Buyer notified when agent responds"),
        ("BUG-026", "Organ 3", "CR Notification - Resolve", "Buyer notified when agent resolves"),
        ("BUG-027", "Organ 3", "CR Close", "Agent closes resolved CR, terminal state"),
        ("BUG-028", "Organ 3", "CR State Guards", "Cannot respond to closed CR"),
        ("BUG-029", "Organ 3", "Quote/Invoice Parity", "CR flow identical for quote and invoice"),
        ("BUG-030", "Organ 3", "Buyer Thread Visibility", "Buyer sees full thread after resolution"),
        ("BUG-031", "Organ 3", "Dashboard CR Aggregation", "Stats endpoint returns CRs across entity types"),
        ("BUG-032", "Organ 3", "Dashboard CR Navigation", "CR cards link to correct entity detail"),
        ("BUG-033", "System", "Canonical Error Shape", "All errors return {error, message, request_id, source}"),
        ("BUG-034", "System", "Request ID Propagation", "X-Request-ID header on all responses"),
        ("BUG-035", "System", "Trace Events", "Mutating requests produce trace events"),
        ("BUG-036", "System", "Debug Console", "Debug console accessible with DEBUG_SECRET"),
    ]

    for item_id, category, name, description in items:
        await db.debug_verifications.update_one(
            {"item_id": item_id},
            {"$setOnInsert": {
                "item_id": item_id,
                "category": category,
                "name": name,
                "description": description,
                "status": "untested",
                "last_verified": None,
                "notes": "",
                "verified_by": "",
                "evidence": "",
            }},
            upsert=True,
        )
