"""
Notification Routes — Canonical Implementation.

Thin route layer. No is_demo. Derived data only.
"""
from fastapi import APIRouter, HTTPException, Depends
from core.auth import get_current_user
from services import notification_service

router = APIRouter()


@router.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    """Get all notifications for the current user."""
    return await notification_service.list_notifications(user['user_id'])


@router.patch("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, user: dict = Depends(get_current_user)):
    """Mark a notification as read."""
    if not await notification_service.mark_read(notification_id, user['user_id']):
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification marked as read"}


@router.patch("/notifications/read-all")
async def mark_all_notifications_read(user: dict = Depends(get_current_user)):
    """Mark all notifications as read."""
    count = await notification_service.mark_all_read(user['user_id'])
    return {"message": f"{count} notifications marked as read", "count": count}
