"""
Gantt Chart — Pydantic schemas (standalone, no CMP coupling).
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ── Domain models ──

class GanttDependency(BaseModel):
    task_id: str
    type: str = "finish_to_start"


class GanttProject(BaseModel):
    gantt_project_id: str
    owner_user_id: str
    title: str
    description: Optional[str] = None
    created_at: str
    updated_at: str


class GanttTask(BaseModel):
    task_id: str
    gantt_project_id: str
    owner_user_id: str
    order: int
    type: Literal["task", "milestone"]
    phase: Optional[str] = None
    title: str
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration_days: Optional[int] = None
    status: str = "not_started"
    responsible_party: Optional[str] = None
    dependencies: List[GanttDependency] = Field(default_factory=list)
    source: Literal["manual", "ai_generated", "imported"] = "manual"
    created_at: str
    updated_at: str


# ── Draft / import models (Phase 3) ──

class GanttDraftDependency(BaseModel):
    temp_task_id: str
    type: str = "finish_to_start"


class GanttDraftTask(BaseModel):
    temp_id: str
    type: Literal["task", "milestone"] = "task"
    phase: Optional[str] = None
    title: str
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration_days: Optional[int] = None
    status: str = "not_started"
    responsible_party: Optional[str] = None
    dependencies: List[GanttDraftDependency] = Field(default_factory=list)
    field_confidence: dict = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


class GanttExtractionDraft(BaseModel):
    draft_id: str
    owner_user_id: str
    gantt_project_id: str
    file_id: str
    status: Literal["pending", "confirmed", "discarded", "expired"]
    source_type: Literal["pdf", "image", "csv"]
    tasks: List[GanttDraftTask]
    warnings: List[str] = Field(default_factory=list)
    review_message: str
    created_at: str
    updated_at: str
    expires_at: str


class GanttUploadedFile(BaseModel):
    file_id: str
    owner_user_id: str
    gantt_project_id: str
    original_filename: str
    stored_filename: str
    content_type: Optional[str] = None
    file_size_bytes: int
    extension: str
    created_at: str
    expires_at: str


# ── Request DTOs ──

class CreateGanttProjectRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None


class UpdateGanttProjectRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None


class CreateGanttTaskRequest(BaseModel):
    type: Literal["task", "milestone"] = "task"
    phase: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration_days: Optional[int] = None
    status: Optional[str] = None
    responsible_party: Optional[str] = None
    dependencies: List[GanttDependency] = Field(default_factory=list)


class UpdateGanttTaskRequest(BaseModel):
    type: Optional[Literal["task", "milestone"]] = None
    phase: Optional[str] = None
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration_days: Optional[int] = None
    status: Optional[str] = None
    responsible_party: Optional[str] = None
    dependencies: Optional[List[GanttDependency]] = None


class ReorderGanttTasksRequest(BaseModel):
    task_ids: List[str] = Field(..., min_length=1)


# ── Response DTOs ──

class DeleteGanttProjectResponse(BaseModel):
    message: str
    gantt_project_id: str
    deleted_task_count: int


class ExtractGanttRequest(BaseModel):
    file_id: str
    gantt_project_id: str


class UpdateGanttDraftRequest(BaseModel):
    tasks: List[GanttDraftTask] = Field(..., min_length=1)


class ConfirmGanttDraftResponse(BaseModel):
    message: str
    draft_id: str
    created_task_count: int
    tasks: List[GanttTask]
