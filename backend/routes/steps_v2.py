"""
TimelineStep Routes — Canonical Implementation

Thin route layer. step_id/title/order_index only. No stage_id/name/order.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from core.auth import get_current_user, get_current_agent
from core.access_scope import resolve_agent_access_scope
from services import step_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request schemas ──

class CreateStepRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = None
    order_index: int = Field(default=0, ge=0)
    planned_start: Optional[str] = None
    planned_end: Optional[str] = None


class UpdateStepRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    order_index: Optional[int] = None
    status: Optional[str] = None
    progress_percent: Optional[int] = None
    planned_start: Optional[str] = None
    planned_end: Optional[str] = None
    actual_start: Optional[str] = None
    actual_end: Optional[str] = None


# ── Routes ──

@router.post("/projects/{project_id}/steps")
async def create_step(project_id: str, data: CreateStepRequest, user=Depends(get_current_agent)):
    """Create a timeline step. Agent only."""
    scope = await resolve_agent_access_scope(user)
    scope.ensure_project_access(project_id)

    step = await step_service.create_step(
        project_id=project_id,
        agent_id=scope.workspace_owner_id,
        title=data.title,
        description=data.description,
        order_index=data.order_index,
        planned_start=data.planned_start,
        planned_end=data.planned_end,
    )
    return step


@router.get("/projects/{project_id}/steps")
async def list_steps(project_id: str, user=Depends(get_current_user)):
    """List all steps for a project."""
    if user.get("role") == "agent":
        (await resolve_agent_access_scope(user)).ensure_project_access(project_id)

    steps = await step_service.list_steps_by_project(project_id)
    return {"steps": steps, "total": len(steps)}


@router.get("/steps/{step_id}")
async def get_step(step_id: str, user=Depends(get_current_user)):
    """Get a single step by ID."""
    step = await step_service.get_step(step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    if user.get("role") == "agent":
        (await resolve_agent_access_scope(user)).ensure_project_access(step["project_id"])
    return step


@router.put("/projects/{project_id}/steps/{step_id}")
async def update_step(project_id: str, step_id: str, data: UpdateStepRequest, user=Depends(get_current_agent)):
    """Update a step. Agent only."""
    (await resolve_agent_access_scope(user)).ensure_project_access(project_id)

    step = await step_service.get_step(step_id)
    if not step or step['project_id'] != project_id:
        raise HTTPException(status_code=404, detail="Step not found in this project")

    try:
        updates = data.model_dump(exclude_none=True)
        updated = await step_service.update_step(step_id, updates)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/projects/{project_id}/steps/{step_id}")
async def delete_step(project_id: str, step_id: str, user=Depends(get_current_agent)):
    """Delete a step. Agent only."""
    (await resolve_agent_access_scope(user)).ensure_project_access(project_id)

    step = await step_service.get_step(step_id)
    if not step or step['project_id'] != project_id:
        raise HTTPException(status_code=404, detail="Step not found in this project")

    await step_service.delete_step(step_id)
    return {"message": "Step deleted"}
