"""
Response Models - Pydantic models for API responses
Ensures consistent field names between backend and frontend.

These models validate what the API returns, catching mismatches early.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# ==================== AUTH RESPONSES ====================

class UserResponse(BaseModel):
    """User data returned from auth endpoints"""
    user_id: str
    email: str
    name: str
    role: str


class AuthSessionResponse(BaseModel):
    """Response from /auth/session endpoint"""
    authenticated: bool
    user: Optional[UserResponse] = None


class AuthLoginResponse(BaseModel):
    """Response from /auth/login endpoint"""
    user_id: str
    email: str
    name: str
    role: str
    token: str


class AuthRefreshResponse(BaseModel):
    """Response from /auth/refresh endpoint"""
    success: bool
    token: str
    expires_in: int  # seconds


class AuthLogoutResponse(BaseModel):
    """Response from /auth/logout endpoint"""
    success: bool
    message: str


# ==================== DOCUMENT RESPONSES ====================

class DocumentLineItemResponse(BaseModel):
    """Line item in a document"""
    description: str
    quantity: float = 1
    unit_price: float = 0
    total: Optional[float] = None


class DocumentResponse(BaseModel):
    """Document data returned from API - canonical schema"""
    document_id: str
    type: str  # 'quote' or 'invoice'
    status: str
    title: str
    amount: float
    currency: str = "CHF"
    supplier_name: Optional[str] = None
    description: Optional[str] = None
    summary: Optional[str] = None
    items: List[DocumentLineItemResponse] = []
    project_id: Optional[str] = None
    client_id: Optional[str] = None
    agent_id: str
    buyer_id: Optional[str] = None
    unit_reference: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None
    sent_at: Optional[str] = None
    due_date: Optional[str] = None
    paid_date: Optional[str] = None
    document_number: Optional[str] = None
    notes: Optional[str] = None
    hero_image_url: Optional[str] = None
    hero_image_path: Optional[str] = None
    pdf_filename: Optional[str] = None
    pdf_path: Optional[str] = None
    ai_extraction_confidence: Optional[str] = None
    parent_document_id: Optional[str] = None
    change_request_comment: Optional[str] = None
    
    class Config:
        extra = "allow"


class DocumentListResponse(BaseModel):
    """List of documents"""
    documents: List[DocumentResponse]
    total: int


class DocumentSendResponse(BaseModel):
    """Response from sending a document"""
    message: str
    status: str
    document_id: str
    recipient: Dict[str, Any]
    delivery: Dict[str, Any]
    warnings: List[str] = []


# ==================== VAULT RESPONSES ====================

class VaultDocumentResponse(BaseModel):
    """Vault document data"""
    vault_id: str
    agent_id: str
    name: str  # Display name (NOT filename!)
    original_filename: str
    file_url: Optional[str] = None
    file_path: Optional[str] = None  # Internal path
    file_type: str
    file_size: Optional[int] = None  # Optional for migration
    category: str
    description: Optional[str] = None
    access_level: str = "private"
    shared_with_clients: List[str] = []
    project_id: Optional[str] = None
    doc_type: str = "general"
    created_at: str
    updated_at: Optional[str] = None

    class Config:
        extra = "allow"


# ==================== CLIENT RESPONSES ====================

class ClientResponse(BaseModel):
    """Client data returned from API"""
    client_id: str
    agent_id: str
    buyer_id: Optional[str] = None
    name: str
    email: str
    phone: Optional[str] = None
    project_id: str
    unit_id: Optional[str] = None
    unit_reference: Optional[str] = "General"
    status: Optional[str] = "active"
    created_at: Optional[str] = None


# ==================== PROJECT RESPONSES ====================

class ProjectResponse(BaseModel):
    """Project data returned from API"""
    project_id: str
    agent_id: str
    name: str
    address: Optional[str] = None
    description: Optional[str] = None
    status: str = "active"
    cover_image: Optional[str] = None
    created_at: str


# ==================== TIMELINE RESPONSES ====================

class TimelineStepResponse(BaseModel):
    """Timeline step data"""
    step_id: str
    project_timeline_id: str
    title: str  # Note: 'title' not 'name'
    description: Optional[str] = None
    planned_date: Optional[str] = None
    actual_date: Optional[str] = None
    status: str = "pending"
    order_index: int = 0


class ProjectTimelineResponse(BaseModel):
    """Project timeline with steps"""
    timeline_id: str
    project_id: str
    project_name: Optional[str] = None
    steps: List[TimelineStepResponse] = []


# ==================== NOTIFICATION RESPONSES ====================

class NotificationResponse(BaseModel):
    """Notification data"""
    notification_id: str
    user_id: str
    title: str
    message: str
    type: str = "info"
    link: Optional[str] = None
    is_read: bool = False
    created_at: str


# ==================== ACTIVITY RESPONSES ====================

class ActivityAttachmentResponse(BaseModel):
    """Activity attachment data"""
    file_id: Optional[str] = None
    filename: str
    file_url: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None

class ActivityResponse(BaseModel):
    """Activity/feed data returned from API"""
    activity_id: str
    activity_type: str  # 'message', 'document_shared', 'milestone', etc.
    agent_id: str  # Required - ownership scoping
    project_id: Optional[str] = None
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    project_name: Optional[str] = None
    unit_reference: Optional[str] = None
    title: Optional[str] = None
    message: Optional[str] = None
    content: Optional[str] = None  # Alias for message
    status: str = "draft"  # draft, sent, read
    is_read: bool = False
    is_seen: bool = False
    sender_id: Optional[str] = None
    sender_name: Optional[str] = None
    sender_role: Optional[str] = None
    recipient_id: Optional[str] = None
    recipient_name: Optional[str] = None
    attachments: List[ActivityAttachmentResponse] = []
    document_id: Optional[str] = None
    document_type: Optional[str] = None
    document_title: Optional[str] = None
    parent_activity_id: Optional[str] = None
    thread_id: Optional[str] = None
    replies_count: int = 0
    created_at: str
    updated_at: Optional[str] = None
    sent_at: Optional[str] = None
    
    class Config:
        extra = "allow"  # Allow extra fields during migration


class ActivitiesListResponse(BaseModel):
    """List of activities with metadata"""
    activities: List[ActivityResponse]
    total: int = 0
    has_more: bool = False


# ==================== WORKFLOW RESPONSES ====================

class WorkflowStepResponse(BaseModel):
    """Workflow step status"""
    step_index: int
    name: str
    description: Optional[str] = None
    status: str
    error: Optional[str] = None
    warning: Optional[str] = None
    optional: bool = False
    can_retry: bool = False


class WorkflowExecutionResponse(BaseModel):
    """Workflow execution result"""
    execution_id: str
    template_id: str
    template_name: str
    status: str
    mode: str = "automatic"
    progress: Dict[str, int]
    steps: List[WorkflowStepResponse]
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None


# ==================== GENERIC RESPONSES ====================

class SuccessResponse(BaseModel):
    """Generic success response"""
    success: bool = True
    message: str


class ErrorResponse(BaseModel):
    """Generic error response"""
    detail: str


class PaginatedResponse(BaseModel):
    """Generic paginated response"""
    items: List[Any]
    total: int
    page: int = 1
    page_size: int = 20
    has_more: bool = False
