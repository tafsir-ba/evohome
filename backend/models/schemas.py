"""
All Pydantic models for the Evohome API.
Consolidated from server.py during Phase 3 modularization.
"""
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime


# ==================== USER / AUTH MODELS ====================

class UserBase(BaseModel):
    user_id: str
    email: str
    name: str
    role: str
    picture: Optional[str] = None
    is_demo: bool = False
    created_at: datetime

class AgentRegister(BaseModel):
    email: EmailStr
    password: str
    name: str

class AgentLogin(BaseModel):
    email: EmailStr
    password: str

class BuyerRegister(BaseModel):
    email: EmailStr
    password: str
    name: str
    invitation_code: Optional[str] = None

class BuyerLogin(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordRequest(BaseModel):
    email: str
    role: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class SetPasswordRequest(BaseModel):
    email: str
    password: str
    role: str

class CheckEmailRequest(BaseModel):
    email: str
    role: str


# ==================== CLIENT MODELS ====================

class ClientCreate(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    project_id: str
    unit_id: Optional[str] = None

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    project_id: Optional[str] = None
    unit_id: Optional[str] = None
    force_unit_reassign: Optional[bool] = False

class Client(BaseModel):
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
    is_demo: bool = False
    created_at: Optional[datetime] = None


# ==================== PROJECT MODELS ====================

class ProjectCreate(BaseModel):
    name: str
    address: Optional[str] = None
    description: Optional[str] = None
    total_units: Optional[int] = None
    construction_start: Optional[str] = None
    estimated_completion: Optional[str] = None

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    total_units: Optional[int] = None
    construction_start: Optional[str] = None
    estimated_completion: Optional[str] = None

class Project(BaseModel):
    project_id: str
    agent_id: str
    name: str
    address: Optional[str] = None
    description: Optional[str] = None
    total_units: Optional[int] = None
    construction_start: Optional[str] = None
    estimated_completion: Optional[str] = None
    client_count: Optional[int] = 0
    unit_count: Optional[int] = 0
    is_demo: bool = False
    created_at: datetime


# ==================== TEAM MEMBER MODELS ====================

class TeamMemberCreate(BaseModel):
    company_name: str
    contact_name: str
    role: str
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None

class TeamMemberUpdate(BaseModel):
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None

class TeamMember(BaseModel):
    member_id: str
    project_id: str
    agent_id: str
    company_name: str
    contact_name: str
    role: str
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    is_demo: bool = False
    created_at: str

class ExtractedContact(BaseModel):
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    confidence: Optional[float] = None

class BulkContactsRequest(BaseModel):
    contacts: List[dict]


# ==================== DOCUMENT MODELS ====================

class DocumentLineItem(BaseModel):
    description: str
    quantity: int = 1
    unit_price: float
    total: float

class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    amount: Optional[float] = None
    items: Optional[List[DocumentLineItem]] = None
    supplier_name: Optional[str] = None
    notes: Optional[str] = None
    summary: Optional[str] = None
    hero_image_url: Optional[str] = None
    client_id: Optional[str] = None
    project_id: Optional[str] = None
    unit_id: Optional[str] = None

class DocumentAction(BaseModel):
    action: str
    comment: Optional[str] = None

class Document(BaseModel):
    id: str = Field(..., alias="document_id")
    type: Literal["quote", "invoice"]
    status: str
    title: str
    amount: float
    items: List[DocumentLineItem]
    pdf_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    buyer_id: Optional[str] = None
    agent_id: str
    client_id: str
    project_id: str
    unit_reference: str
    parent_document_id: Optional[str] = None
    version: int = 1
    version_history: Optional[list] = None
    document_number: str
    currency: str = "CHF"
    supplier_name: Optional[str] = None
    notes: Optional[str] = None
    summary: Optional[str] = None
    hero_image_url: Optional[str] = None
    hero_image_path: Optional[str] = None
    change_request_comment: Optional[str] = None
    pdf_filename: Optional[str] = None
    pdf_path: Optional[str] = None
    ai_extraction_confidence: Optional[str] = None
    due_date: Optional[str] = None
    paid_date: Optional[str] = None
    is_demo: bool = False


# ==================== PROJECT STAGE / STEP MODELS ====================

class ProjectStageCreate(BaseModel):
    title: str
    description: Optional[str] = None
    order_index: int
    planned_start: str
    planned_end: str
    dependencies: Optional[List[str]] = None
    # Legacy aliases for backward compat during transition
    name: Optional[str] = None
    order: Optional[int] = None

class ProjectStageUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    order_index: Optional[int] = None
    planned_start: Optional[str] = None
    planned_end: Optional[str] = None
    actual_start: Optional[str] = None
    actual_end: Optional[str] = None
    status: Optional[str] = None
    progress_percent: Optional[int] = None
    notes: Optional[str] = None
    # Legacy aliases for backward compat during transition
    name: Optional[str] = None
    order: Optional[int] = None

class ProjectStage(BaseModel):
    stage_id: str
    project_id: str
    agent_id: str
    name: str
    description: Optional[str] = None
    order: int
    planned_start: str
    planned_end: str
    actual_start: Optional[str] = None
    actual_end: Optional[str] = None
    status: str
    progress_percent: int = 0
    notes: Optional[str] = None
    dependencies: List[str] = []
    is_demo: bool = False
    created_at: datetime
    updated_at: datetime


# ==================== ACTIVITY FEED MODELS ====================

class ActivityCreate(BaseModel):
    type: Literal["message", "image", "file", "status"]
    title: Optional[str] = None
    content: Optional[str] = None
    project_id: str
    unit_id: Optional[str] = None
    client_ids: List[str]
    file_type: Optional[str] = None

class ActivityReplyCreate(BaseModel):
    content: str

class Activity(BaseModel):
    activity_id: str
    type: Literal["message", "image", "file", "status", "pdf"]
    title: Optional[str] = None
    content: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    author_id: str
    author_role: Literal["agent", "buyer"]
    author_name: Optional[str] = None
    project_id: str
    project_name: Optional[str] = None
    unit_id: Optional[str] = None
    unit_reference: Optional[str] = None
    is_demo: bool = False
    created_at: str
    updated_at: Optional[str] = None
    recipients: Optional[List[dict]] = None
    replies: Optional[List[dict]] = None
    reply_count: int = 0
    status: Optional[str] = None
    change_comment: Optional[str] = None

class ActivityReply(BaseModel):
    reply_id: str
    activity_id: str
    author_id: str
    author_role: Literal["agent", "buyer"]
    author_name: Optional[str] = None
    content: str
    created_at: str

class ActivityUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


# ==================== TIMELINE / WORKFLOW MODELS ====================

class TimelineTemplateStepCreate(BaseModel):
    title: str
    description: Optional[str] = None
    order_index: int

class TimelineTemplateCreate(BaseModel):
    name: str
    steps: List[TimelineTemplateStepCreate]

class TimelineTemplate(BaseModel):
    template_id: str
    agent_id: str
    name: str
    is_demo: bool = False
    created_at: str

class TimelineTemplateStep(BaseModel):
    step_id: str
    template_id: str
    title: str
    description: Optional[str] = None
    order_index: int

class TimelineStepUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[Literal["pending", "in_progress", "completed", "approved"]] = None
    planned_date: Optional[str] = None
    order_index: Optional[int] = None
    planned_start: Optional[str] = None
    planned_end: Optional[str] = None
    actual_start: Optional[str] = None
    progress_percent: Optional[int] = None
    notes: Optional[str] = None

class TimelineStepDocumentCreate(BaseModel):
    activity_id: str

class TimelineStepNoteCreate(BaseModel):
    content: str

class TimelineStep(BaseModel):
    step_id: str
    timeline_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    status: Literal["pending", "in_progress", "completed", "approved"]
    order_index: int
    planned_date: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str
    updated_at: str
    planned_start: Optional[str] = None
    planned_end: Optional[str] = None
    actual_start: Optional[str] = None
    progress_percent: Optional[int] = 0
    notes: Optional[str] = None
    dependencies: Optional[List[str]] = []
    documents: Optional[List[dict]] = None
    internal_notes: Optional[List[dict]] = None

class ProjectTimeline(BaseModel):
    timeline_id: str
    project_id: str
    template_id: Optional[str] = None
    template_name: Optional[str] = None
    is_demo: bool = False
    created_at: str
    steps: Optional[List[TimelineStep]] = None

class ManualTimelineCreate(BaseModel):
    project_id: str
    name: str = "Project Timeline"
    steps: List[dict]


# ==================== NOTIFICATION MODELS ====================

class Notification(BaseModel):
    notification_id: str
    user_id: str
    title: str
    message: str
    notification_type: str
    link: Optional[str] = None
    metadata: Optional[dict] = None
    is_read: bool = False
    is_demo: bool = False
    created_at: datetime


# ==================== SUBSCRIPTION / BILLING MODELS ====================

class SubscriptionStatus(BaseModel):
    plan_id: str
    plan_name: str
    property_limit: Optional[int]
    property_usage: int
    can_create_property: bool
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    subscription_status: Optional[str] = None
    current_period_end: Optional[str] = None

class CreateCheckoutRequest(BaseModel):
    plan_id: str
    origin_url: str

class CheckoutStatusRequest(BaseModel):
    session_id: str


# ==================== COMPOSITE RESPONSE MODELS ====================

class ProjectSummary(BaseModel):
    project_id: str
    name: str
    address: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[str] = None

class ClientSummary(BaseModel):
    client_id: str
    name: str
    email: Optional[str] = None
    project_id: Optional[str] = None
    unit_id: Optional[str] = None

class UnitSummary(BaseModel):
    unit_id: str
    reference: str
    type: Optional[str] = None
    client_id: Optional[str] = None

class TimelineStepSummary(BaseModel):
    step_id: str
    title: str
    description: Optional[str] = None
    status: str
    order_index: int
    planned_start: Optional[str] = None
    planned_end: Optional[str] = None
    progress_percent: int = 0

class RecentWorkItem(BaseModel):
    id: str
    type: str
    title: str
    subtitle: Optional[str] = None
    path: str
    timestamp: Optional[str] = None

class DashboardResponse(BaseModel):
    projects: List[ProjectSummary]
    selected_project: Optional[ProjectSummary] = None
    recent_work: List[RecentWorkItem] = []

class RecentWorkResponse(BaseModel):
    items: List[RecentWorkItem] = []

class ProjectContextResponse(BaseModel):
    project: ProjectSummary
    clients: List[ClientSummary] = []
    units: List[UnitSummary] = []

class ProjectTimelineResponse(BaseModel):
    project: ProjectSummary
    timeline_id: Optional[str] = None
    steps: List[TimelineStepSummary] = []
    progress_percent: int = 0

class ProjectTeamResponse(BaseModel):
    project: ProjectSummary
    team_members: List[dict] = []

class ProjectWorkflowResponse(BaseModel):
    project: ProjectSummary
    timeline_id: Optional[str] = None
    steps: List[TimelineStepSummary] = []
    activities: List[dict] = []
    templates: List[dict] = []


# ==================== VAULT MODELS ====================

class VaultDocumentCreate(BaseModel):
    name: str
    category: str = "Other"
    project_id: Optional[str] = None
    description: Optional[str] = None
    access_level: str = "private"
    shared_with_clients: Optional[List[str]] = None

class VaultDocumentUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    project_id: Optional[str] = None
    description: Optional[str] = None
    access_level: Optional[str] = None
    shared_with_clients: Optional[List[str]] = None


# ==================== TEAM INVITATION MODELS ====================

class TeamInviteCreate(BaseModel):
    email: EmailStr
    role: str = "member"
    message: Optional[str] = None

class TeamInviteResponse(BaseModel):
    invitation_id: str
    email: str
    role: str
    status: str
    invited_by: str
    invited_by_name: str
    created_at: str
    expires_at: str


# ==================== SETTINGS MODELS ====================

class BillingSettings(BaseModel):
    iban: Optional[str] = None
    company_name: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None

class AgentProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None

class AgentSettingsUpdate(BaseModel):
    language: Optional[str] = None
    currency: Optional[str] = None
    company_name: Optional[str] = None
    billing: Optional[BillingSettings] = None
    profile: Optional[AgentProfileUpdate] = None


# ==================== COMMAND SERVICE MODELS ====================

class CommandInterpretRequest(BaseModel):
    command: str
    context: Optional[dict] = None

class CommandExecuteRequest(BaseModel):
    draft_id: str
    confirmed: bool = True


# ==================== WORKFLOW MODELS ====================

class WorkflowExecuteRequest(BaseModel):
    template_id: str
    context: Dict[str, Any] = {}
    mode: str = "automatic"

class WorkflowConfirmRequest(BaseModel):
    skip_step: bool = False
