"""
Trace System — Production Debugging & Verification.

Non-blocking trace capture for all mutating requests.
Trace failure NEVER fails user actions.

Components:
- TraceContext: per-request accumulator for service_chain and db_mutations
- trace_write: non-blocking persist to trace_events collection
- trace_service: decorator to record service chain entries
- trace_db_mutation: helper to record DB writes
"""
import time
import logging
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from database import db

logger = logging.getLogger(__name__)

# ── Per-request trace context (using contextvars for async safety) ──

_trace_ctx: ContextVar[Optional["TraceContext"]] = ContextVar("_trace_ctx", default=None)


class TraceContext:
    """Accumulates trace data during a single request lifecycle."""

    __slots__ = (
        "trace_id", "request_id", "user_id", "user_role",
        "action", "entity_type", "entity_id",
        "endpoint", "method", "start_time",
        "service_chain", "db_mutations", "side_effects",
        "request_summary",
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
        action = ctx.action or f"{ctx.method}_{ctx.endpoint.split('/')[-1]}"

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
            "response_summary": response_summary or {},
            "outcome": outcome,
            "error_code": error_code,
            "error_message": error_message,
            "duration_ms": duration_ms,
            "service_chain": ctx.service_chain,
            "db_mutations": ctx.db_mutations,
            "side_effects": ctx.side_effects,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.trace_events.insert_one(doc)
    except Exception as e:
        # Trace failure NEVER fails user action
        logger.warning(f"Trace write failed (non-blocking): {e}")
    finally:
        clear_trace_context()
