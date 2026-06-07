"""
Trace System — Production Debugging & Verification.

Non-blocking trace capture for all mutating requests.
Trace failure NEVER fails user actions.

Components:
- TraceContext: per-request accumulator for service_chain and db_mutations
- trace_write: non-blocking persist to trace_events collection
- trace_service: record service chain entries
- trace_db_mutation: record DB writes
- trace_side_effect: record notifications, emails, etc.
- auto_extract_entity: derive entity_type/id from URL patterns
- auto_extract_action: derive human-readable action from method+path
"""
import re
import time
import logging
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from database import db

logger = logging.getLogger(__name__)

# ── URL pattern → entity extraction ──

_ENTITY_PATTERNS = [
    (re.compile(r"/documents/(doc_[a-f0-9]+)"), "document"),
    (re.compile(r"/vault/documents/(vault_[a-f0-9]+)"), "vault_document"),
    (re.compile(r"/change-requests/(cr_[a-f0-9]+)"), "change_request"),
    (re.compile(r"/decisions/(dec_[a-f0-9]+)"), "decision"),
    (re.compile(r"/clients/(client_[a-f0-9]+)"), "client"),
    (re.compile(r"/projects/(proj_[a-f0-9]+)"), "project"),
]

# ── URL → readable action name ──

_ACTION_OVERRIDES = {
    ("POST", "/vault/upload"): "vault_upload",
    ("POST", "/documents/upload"): "document_upload_pdf",
    ("POST", "/documents/create"): "document_create",
    ("POST", "/settings/logo"): "logo_upload",
    ("DELETE", "/settings/logo"): "logo_delete",
    ("POST", "/auth/login"): "auth_login",
    ("POST", "/auth/buyer/login"): "auth_login_buyer",
    ("POST", "/auth/register"): "auth_register",
    ("POST", "/auth/buyer/register"): "auth_register_buyer",
    ("POST", "/auth/logout"): "auth_logout",
}

_ACTION_SUFFIX_MAP = {
    "hero-image": {"POST": "hero_image_upload", "DELETE": "hero_image_delete", "GET": "hero_image_get"},
    "send": {"POST": "document_send"},
    "action": {"POST": "document_action"},
    "reupload": {"POST": "document_reupload"},
    "revert-to-draft": {"POST": "document_revert_draft"},
    "respond": {"POST": "cr_respond"},
    "resolve": {"POST": "cr_resolve"},
    "close": {"POST": "cr_close"},
    "upload-attachment": {"POST": "decision_attachment_upload"},
    "source-pdf": {"GET": "document_source_pdf"},
    "download": {"GET": "vault_download"},
}


def _auto_extract_entity(path: str) -> tuple:
    """Extract entity_type and entity_id from URL path."""
    for pattern, etype in _ENTITY_PATTERNS:
        m = pattern.search(path)
        if m:
            return etype, m.group(1)
    return None, None


def _auto_derive_action(method: str, path: str) -> str:
    """Derive a human-readable action name from method + path."""
    # Strip /api prefix for matching
    clean = path.replace("/api", "", 1) if path.startswith("/api") else path

    # Check explicit overrides
    for (m, p), action in _ACTION_OVERRIDES.items():
        if method == m and clean == p:
            return action

    # Check suffix-based patterns (e.g., /documents/{id}/send)
    parts = clean.rstrip("/").split("/")
    if parts:
        suffix = parts[-1]
        if suffix in _ACTION_SUFFIX_MAP:
            return _ACTION_SUFFIX_MAP[suffix].get(method, f"{method.lower()}_{suffix}")

    # Default: method + last meaningful path segment
    entity_type, _ = _auto_extract_entity(path)
    if entity_type:
        op = {"POST": "create", "PUT": "update", "DELETE": "delete", "PATCH": "update"}.get(method, method.lower())
        return f"{entity_type}_{op}"

    # Fallback
    slug = clean.rstrip("/").split("/")[-1] if clean else "unknown"
    return f"{method.lower()}_{slug}"

# ── Per-request trace context (using contextvars for async safety) ──

_trace_ctx: ContextVar[Optional["TraceContext"]] = ContextVar("_trace_ctx", default=None)


class TraceContext:
    """Accumulates trace data during a single request lifecycle."""

    __slots__ = (
        "trace_id", "request_id", "user_id", "user_role",
        "action", "entity_type", "entity_id",
        "endpoint", "method", "start_time",
        "service_chain", "db_mutations", "side_effects",
        "request_summary", "related_entities", "response_summary_data",
    )

    def __init__(self, request_id: str, endpoint: str, method: str):
        self.trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        self.request_id = request_id
        self.user_id: Optional[str] = None
        self.user_role: Optional[str] = None
        self.action: Optional[str] = None
        self.entity_type: Optional[str] = None
        self.entity_id: Optional[str] = None
        self.endpoint = endpoint
        self.method = method
        self.start_time = time.monotonic()
        self.service_chain: List[str] = []
        self.db_mutations: List[Dict[str, Any]] = []
        self.side_effects: List[Dict[str, Any]] = []
        self.request_summary: Dict[str, Any] = {}
        self.related_entities: List[Dict[str, str]] = []
        self.response_summary_data: Dict[str, Any] = {}

        # Auto-extract entity from URL
        auto_type, auto_id = _auto_extract_entity(endpoint)
        if auto_type:
            self.entity_type = auto_type
            self.entity_id = auto_id


def get_trace_context() -> Optional[TraceContext]:
    return _trace_ctx.get()


def set_trace_context(ctx: TraceContext):
    _trace_ctx.set(ctx)


def clear_trace_context():
    _trace_ctx.set(None)


# ── Service chain tracking ──

def trace_service(func_path: str):
    """Record a service function in the current trace's service_chain.
    Use as: trace_service("services.document_service.send_document")
    Call at the top of service functions that should be visible in traces.
    """
    ctx = get_trace_context()
    if ctx:
        ctx.service_chain.append(func_path)


# ── DB mutation tracking ──

def trace_db_mutation(collection: str, operation: str, entity_id: str = ""):
    """Record a DB write in the current trace.
    Call after any insert_one, update_one, delete_one, etc.
    """
    ctx = get_trace_context()
    if ctx:
        ctx.db_mutations.append({
            "collection": collection,
            "operation": operation,
            "entity_id": entity_id,
        })


# ── Side effect tracking ──

def trace_side_effect(effect_type: str, target: str = "", detail: str = ""):
    """Record a side effect (notification, email, etc.)."""
    ctx = get_trace_context()
    if ctx:
        ctx.side_effects.append({
            "type": effect_type,
            "target": target,
            "detail": detail,
        })


# ── Set trace metadata ──

def set_trace_user(user_id: str, role: str):
    ctx = get_trace_context()
    if ctx:
        ctx.user_id = user_id
        ctx.user_role = role


def set_trace_entity(entity_type: str, entity_id: str):
    ctx = get_trace_context()
    if ctx:
        ctx.entity_type = entity_type
        ctx.entity_id = entity_id


def set_trace_action(action: str):
    """Override the auto-derived action name with an explicit one."""
    ctx = get_trace_context()
    if ctx:
        ctx.action = action


def set_trace_request_summary(summary: Dict[str, Any]):
    ctx = get_trace_context()
    if ctx:
        ctx.request_summary = summary


def set_trace_response_summary(summary: Dict[str, Any]):
    """Set response_summary data (e.g., {status: "Sent"} for state transitions)."""
    ctx = get_trace_context()
    if ctx:
        ctx.response_summary_data = summary


def trace_related_entity(entity_type: str, entity_id: str):
    """Record a related entity (e.g., CR resolve also affects a document)."""
    ctx = get_trace_context()
    if ctx:
        ctx.related_entities.append({"entity_type": entity_type, "entity_id": entity_id})


# ── Non-blocking trace writer ──

async def trace_write(
    response_status: int,
    response_summary: Optional[Dict[str, Any]] = None,
    outcome: str = "success",
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
):
    """Persist the current trace context to DB. Non-blocking — never fails user action."""
    ctx = get_trace_context()
    if not ctx:
        return

    try:
        duration_ms = int((time.monotonic() - ctx.start_time) * 1000)
        # Use explicit action if set, otherwise auto-derive from method+path
        action = ctx.action or _auto_derive_action(ctx.method, ctx.endpoint)
        # Merge response_summary from explicit set + parameter
        resp_summary = ctx.response_summary_data.copy() if ctx.response_summary_data else {}
        if response_summary:
            resp_summary.update(response_summary)

        doc = {
            "trace_id": ctx.trace_id,
            "request_id": ctx.request_id,
            "user_id": ctx.user_id,
            "user_role": ctx.user_role,
            "action": action,
            "entity_type": ctx.entity_type,
            "entity_id": ctx.entity_id,
            "endpoint": ctx.endpoint,
            "method": ctx.method,
            "request_summary": ctx.request_summary,
            "response_status": response_status,
            "response_summary": resp_summary,
            "outcome": outcome,
            "error_code": error_code,
            "error_message": error_message,
            "duration_ms": duration_ms,
            "service_chain": ctx.service_chain,
            "db_mutations": ctx.db_mutations,
            "side_effects": ctx.side_effects,
            "related_entities": ctx.related_entities,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.trace_events.insert_one(doc)
    except Exception as e:
        # Trace failure NEVER fails user action
        logger.warning(f"Trace write failed (non-blocking): {e}")
    finally:
        clear_trace_context()
