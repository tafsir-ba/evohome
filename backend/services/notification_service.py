"""
Notification Service - handles notification creation and management.
This is a new service structure for building modular backend code.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing notifications"""
    
    def __init__(self, db):
        self.db = db
    
    async def create_notification(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        message: str,
        link: Optional[str] = None,
        is_demo: bool = False,
        metadata: Optional[dict] = None
    ) -> dict:
        """Create a new notification for a user"""
        notification = {
            "notification_id": str(uuid.uuid4()),
            "user_id": user_id,
            "notification_type": notification_type,
            "title": title,
            "message": message,
            "link": link,
            "is_read": False,
            "is_demo": is_demo,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await self.db.notifications.insert_one(notification)
        logger.info(f"Created notification {notification['notification_id']} for user {user_id}")
        
        return {k: v for k, v in notification.items() if k != '_id'}
    
    async def get_user_notifications(
        self,
        user_id: str,
        is_demo: bool = False,
        limit: int = 50
    ) -> dict:
        """Get notifications for a user"""
        query = {"user_id": user_id, "is_demo": is_demo}
        
        notifications = await self.db.notifications.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        unread_count = await self.db.notifications.count_documents({
            **query,
            "is_read": False
        })
        
        return {
            "notifications": notifications,
            "unread_count": unread_count
        }
    
    async def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        """Mark a notification as read"""
        result = await self.db.notifications.update_one(
            {"notification_id": notification_id, "user_id": user_id},
            {"$set": {"is_read": True}}
        )
        return result.modified_count > 0
    
    async def mark_all_as_read(self, user_id: str, is_demo: bool = False) -> int:
        """Mark all notifications as read for a user"""
        result = await self.db.notifications.update_many(
            {"user_id": user_id, "is_demo": is_demo, "is_read": False},
            {"$set": {"is_read": True}}
        )
        return result.modified_count
    
    async def delete_notification(self, notification_id: str, user_id: str) -> bool:
        """Delete a notification"""
        result = await self.db.notifications.delete_one({
            "notification_id": notification_id,
            "user_id": user_id
        })
        return result.deleted_count > 0
    
    async def create_document_shared_notification(
        self,
        buyer_id: str,
        agent_name: str,
        document_name: str,
        is_demo: bool = False
    ) -> dict:
        """Create notification when agent shares a document with buyer"""
        return await self.create_notification(
            user_id=buyer_id,
            notification_type="document_shared",
            title="New Document Available",
            message=f"{agent_name} shared a document with you: {document_name}",
            link="/buyer/vault",
            is_demo=is_demo
        )
