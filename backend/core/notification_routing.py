"""
Canonical notification deep-link helpers.

All in-app notification targets use explicit paths + query params so SPA navigation
and refresh/deep-load behave consistently.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import urlencode

BUYER_HOME = "/buyer/dashboard"


def buyer_query(tab: str, **params: Optional[str]) -> str:
    """Build /buyer/dashboard?tab=...&... (drops None values)."""
    q: Dict[str, str] = {"tab": tab}
    for k, v in params.items():
        if v is not None and v != "":
            q[k] = str(v)
    return f"{BUYER_HOME}?{urlencode(q)}"


def normalize_legacy_link(link: Optional[str]) -> Optional[str]:
    """Fix legacy /buyer?... and bare /buyer paths."""
    if not link:
        return None
    s = link.strip()
    if s.startswith("/buyer?") or s == "/buyer":
        rest = s[6:] if s.startswith("/buyer?") else ""
        return f"{BUYER_HOME}?{rest}" if rest else BUYER_HOME
    return s


def compute_notification_link(
    notification_type: str,
    metadata: Optional[Dict[str, Any]],
    recipient_role: str,
    stored_link: Optional[str],
) -> Optional[str]:
    """
    Derive the best destination URL from type + metadata.
    recipient_role: 'agent' | 'buyer' | other
    """
    meta = dict(metadata or {})
    nt = (notification_type or "").strip()
    role = (recipient_role or "buyer").lower()

    # Agent-facing document / pipeline notifications
    if role == "agent":
        doc_id = meta.get("document_id")
        if nt in ("quote_approved", "quote_rejected", "change_requested", "payment_confirmed", "buyer_action"):
            if doc_id:
                return f"/agent/documents/{doc_id}"
            return "/agent/documents"
        if nt in ("change_request_created", "change_request_message"):
            return _agent_change_request_link(meta)
        if nt == "change_request_response":
            return _agent_change_request_link(meta)
        if nt == "change_request_resolved":
            return _agent_change_request_link(meta)
        if nt == "decision_updated":
            did = meta.get("decision_id")
            if did:
                return f"/agent/decisions?decision_id={did}"
            return "/agent/decisions"
        if nt == "feed_update":
            return "/agent/feed"
        stored = normalize_legacy_link(stored_link)
        return stored or "/agent/home"

    # Buyer-facing
    if nt == "document_sent":
        did = meta.get("document_id")
        if did:
            return buyer_query("documents", document_id=did)
        return buyer_query("documents")

    if nt == "invoice_created":
        did = meta.get("document_id")
        if did:
            return buyer_query("documents", document_id=did)
        return buyer_query("documents")

    if nt == "vault_document":
        vid = meta.get("vault_document_id")
        if vid:
            return buyer_query("vault", vault_document_id=vid)
        return buyer_query("vault")

    if nt in ("change_request_created", "change_request_response", "change_request_resolved", "change_request_message"):
        return _buyer_change_request_link(meta)

    if nt == "milestone_completed":
        sid = meta.get("step_id")
        pid = meta.get("project_id")
        if sid:
            return buyer_query("documents", milestone_step_id=sid, project_id=pid or "")
        return buyer_query("documents")

    if nt == "feed_update":
        aid = meta.get("activity_id")
        if aid:
            return buyer_query("updates", activity_id=aid)
        return buyer_query("updates")

    if nt == "decision_updated":
        did = meta.get("decision_id")
        if did:
            return buyer_query("decisions", decision_id=did)
        return buyer_query("decisions")

    stored = normalize_legacy_link(stored_link)
    if stored:
        return stored
    return BUYER_HOME


def _agent_change_request_link(meta: Dict[str, Any]) -> str:
    et = meta.get("entity_type")
    eid = meta.get("entity_id")
    cr = meta.get("change_request_id")
    if et in ("quote", "invoice") and eid:
        return f"/agent/documents/{eid}?change_request_id={cr}" if cr else f"/agent/documents/{eid}"
    if et == "decision" and eid:
        if cr:
            return f"/agent/decisions?decision_id={eid}&change_request_id={cr}"
        return f"/agent/decisions?decision_id={eid}"
    return "/agent/documents"


def _buyer_change_request_link(meta: Dict[str, Any]) -> str:
    et = meta.get("entity_type")
    eid = meta.get("entity_id")
    cr = meta.get("change_request_id")
    if et in ("quote", "invoice") and eid:
        return buyer_query("documents", document_id=eid, change_request_id=cr or "")
    if et == "decision" and eid:
        return buyer_query("decisions", decision_id=eid, change_request_id=cr or "")
    return buyer_query("documents")


def enrich_notification_record(n: Dict[str, Any], recipient_role: str) -> Dict[str, Any]:
    """Attach a resolved link for API responses (fixes old rows missing deep links)."""
    out = dict(n)
    meta = out.get("metadata") or {}
    if isinstance(meta, dict):
        meta = dict(meta)
    else:
        meta = {}
    computed = compute_notification_link(
        out.get("notification_type", ""),
        meta,
        recipient_role,
        out.get("link"),
    )
    out["link"] = computed
    return out
