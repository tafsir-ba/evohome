"""Lightweight audit logging helpers for destructive/admin operations."""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from database import db

logger = logging.getLogger("evohome.audit")


async def log_audit_event(
    *,
    actor_user: Dict[str, Any],
    action: str,
    target_type: str,
    target_id: str,
    workspace_owner_id: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Write an audit event and avoid breaking request flow on failure."""
    event = {
        "audit_id": f"audit_{datetime.now(timezone.utc).timestamp()}_{target_id}",
        "workspace_owner_id": workspace_owner_id,
        "actor_user_id": actor_user.get("user_id"),
        "actor_role": actor_user.get("role"),
        "actor_workspace_role": actor_user.get("workspace_role") or "owner",
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await db.audit_logs.insert_one(event)
    except Exception as e:
        logger.warning("Failed to persist audit event action=%s target=%s error=%s", action, target_id, e)
