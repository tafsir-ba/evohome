"""
Notification Service — Canonical Implementation.

Single source of truth for the notification lifecycle:
  - create_notification (write)
  - list_notifications + count_unread (read)
  - mark_read / mark_all_read (update)

Delivery side-effects (email, websocket) are convenience wrappers.
Notifications are derived, never source of truth for business state.
No is_demo. Field standard: is_read (not read).
"""
import uuid
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from database import db

logger = logging.getLogger(__name__)


# ── Write ──

async def create_notification(
    user_id: str,
    title: str,
    message: str,
    notification_type: str,
    link: str = None,
    metadata: dict = None,
) -> str:
    """Create a notification in the database. Returns notification_id."""
    notification_id = f"notif_{uuid.uuid4().hex[:12]}"
    await db.notifications.insert_one({
        "notification_id": notification_id,
        "user_id": user_id,
        "title": title,
        "message": message,
        "notification_type": notification_type,
        "link": link,
        "metadata": metadata or {},
        "is_read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Record side effect in trace (non-blocking, non-failing)
    try:
        from core.trace import trace_side_effect, trace_db_mutation
        trace_side_effect("notification", target=user_id, detail=f"{notification_type}: {title}")
        trace_db_mutation("notifications", "insert_one", notification_id)
    except Exception:
        pass

    return notification_id


# ── Delivery wrappers (side-effects, not primary state) ──

async def emit_notification(
    user_id: str,
    title: str,
    message: str,
    notification_type: str,
    link: str = None,
    metadata: dict = None,
) -> str:
    """Canonical notification emission. Alias for create_notification."""
    return await create_notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        link=link,
        metadata=metadata,
    )


async def emit_email(template: str, to_email: str, data: dict):
    """Send notification email. Thin wrapper with error handling."""
    try:
        from services.email_service import send_notification_email
        return await send_notification_email(template, to_email, data)
    except Exception as e:
        logger.error(f"Email send failed ({template} -> {to_email}): {e}")
        return None


async def emit_realtime(user_ids: list, event: str, payload: dict):
    """Send real-time WebSocket notification. Thin wrapper with error handling."""
    try:
        from services.realtime_service import notify_realtime
        await notify_realtime(user_ids, event, payload)
    except Exception as e:
        logger.error(f"Realtime notify failed ({event}): {e}")


# ── Read ──

async def list_notifications_with_count(user_id: str) -> Dict[str, Any]:
    """List notifications for a user with unread count.
    Returns {"notifications": [...], "unread_count": N} — the frontend contract."""
    notifications = await db.notifications.find(
        {"user_id": user_id}, {"_id": 0, "read": 0}
    ).sort("created_at", -1).to_list(50)

    unread_count = await db.notifications.count_documents(
        {"user_id": user_id, "is_read": False}
    )

    return {"notifications": notifications, "unread_count": unread_count}


async def mark_read(notification_id: str, user_id: str) -> bool:
    """Mark a single notification as read."""
    result = await db.notifications.update_one(
        {"notification_id": notification_id, "user_id": user_id},
        {"$set": {"is_read": True, "read_at": datetime.now(timezone.utc).isoformat()}},
    )
    return result.modified_count > 0


async def mark_all_read(user_id: str) -> int:
    """Mark all notifications as read for a user. Returns count updated."""
    result = await db.notifications.update_many(
        {"user_id": user_id, "is_read": False},
        {"$set": {"is_read": True, "read_at": datetime.now(timezone.utc).isoformat()}},
    )
    return result.modified_count
