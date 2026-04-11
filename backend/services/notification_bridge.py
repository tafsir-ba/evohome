"""
Notification Bridge — Temporary canonical wrapper.

Wraps legacy create_notification (which requires is_demo parameter).
This bridge exists so Phase 2+ modules never propagate is_demo=False.
Removed entirely when Notification module is rebuilt (Phase 2 Step 4).
"""
import logging
from services.email_service import create_notification as _legacy_create_notification
from services.email_service import send_notification_email
from services.realtime_service import notify_realtime

logger = logging.getLogger(__name__)


async def emit_notification(
    user_id: str,
    title: str,
    message: str,
    notification_type: str,
    link: str = None,
    metadata: dict = None,
):
    """Canonical notification emission. No is_demo parameter exposed."""
    await _legacy_create_notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        link=link,
        metadata=metadata,
        is_demo=False,
    )


async def emit_email(template: str, to_email: str, data: dict):
    """Send notification email. Thin wrapper for traceability."""
    try:
        return await send_notification_email(template, to_email, data)
    except Exception as e:
        logger.error(f"Email send failed ({template} -> {to_email}): {e}")
        return None


async def emit_realtime(user_ids: list, event: str, payload: dict):
    """Send real-time WebSocket notification."""
    try:
        await notify_realtime(user_ids, event, payload)
    except Exception as e:
        logger.error(f"Realtime notify failed ({event}): {e}")
