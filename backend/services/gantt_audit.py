"""Standalone audit events for the Gantt tool (no CMP coupling)."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from database import db

logger = logging.getLogger("evohome.gantt_audit")


async def log_gantt_event(
    *,
    owner_user_id: str,
    action: str,
    gantt_project_id: Optional[str] = None,
    task_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist a Gantt audit event without breaking request flow on failure."""
    event = {
        "event_id": f"ga_{uuid.uuid4().hex[:12]}",
        "owner_user_id": owner_user_id,
        "gantt_project_id": gantt_project_id,
        "task_id": task_id,
        "action": action,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await db.gantt_audit_logs.insert_one(event)
    except Exception as exc:
        logger.warning(
            "Failed to persist gantt audit action=%s project=%s task=%s error=%s",
            action,
            gantt_project_id,
            task_id,
            exc,
        )
