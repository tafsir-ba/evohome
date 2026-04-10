"""
Common Pydantic models used across the application.
These models are for NEW features - existing features still use inline models in server.py
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class BaseResponse(BaseModel):
    """Base response model with common fields"""
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """Standard error response"""
    detail: str
    error_code: Optional[str] = None


class PaginatedResponse(BaseModel):
    """Base model for paginated responses"""
    items: List
    total: int
    page: int = 1
    page_size: int = 20
    has_more: bool = False


class NotificationCreate(BaseModel):
    """Model for creating notifications"""
    user_id: str
    notification_type: str
    title: str
    message: str
    link: Optional[str] = None
    metadata: Optional[dict] = None


class NotificationResponse(BaseModel):
    """Response model for notifications"""
    notification_id: str
    notification_type: str
    title: str
    message: str
    link: Optional[str] = None
    is_read: bool = False
    created_at: str
