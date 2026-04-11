"""
Notification Service — Canonical Implementation.

No is_demo. Notification is derived only.
Never source of truth. No business state lives only in notifications.
"""
import logging
from typing import List, Dict, Any
from datetime import datetime, timezone

from database import db

logger = logging.getLogger(__name__)


async def list_notifications(user_id: str) -> List[Dict[str, Any]]:
    """List notifications for a user, newest first."""
    return await db.notifications.find(
        {"user_id": user_id}, {"_id": 0, "is_demo": 0}
    ).sort("created_at", -1).to_list(50)


async def mark_read(notification_id: str, user_id: str) -> bool:
    """Mark a single notification as read."""
    result = await db.notifications.update_one(
        {"notification_id": notification_id, "user_id": user_id},
        {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}},
    )
    return result.modified_count > 0


async def mark_all_read(user_id: str) -> int:
    """Mark all notifications as read for a user. Returns count updated."""
    result = await db.notifications.update_many(
        {"user_id": user_id, "read": False},
        {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}},
    )
    return result.modified_count
