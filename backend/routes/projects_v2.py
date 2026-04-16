"""
Project Routes — Canonical Implementation

Thin route layer. No is_demo. No business logic.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from core.auth import get_current_user, get_current_agent
from core.access_control import can_access_project, get_workspace_owner_id, get_accessible_project_ids
from services import project_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request schemas ──

class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    address: Optional[str] = None
    description: Optional[str] = None
    total_units: Optional[int] = None
    construction_start: Optional[str] = None
    estimated_completion: Optional[str] = None


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    total_units: Optional[int] = None
    construction_start: Optional[str] = None
    estimated_completion: Optional[str] = None
    status: Optional[str] = None


# ── Routes ──

@router.get("/projects")
async def list_projects(user=Depends(get_current_user)):
    """List projects. Agents see theirs; buyers see linked projects."""
    if user['role'] == 'agent':
        return await project_service.list_projects_by_agent(
            get_workspace_owner_id(user),
            await get_accessible_project_ids(user),
        )
    elif user['role'] == 'buyer':
        return await project_service.list_projects_for_buyer(user['user_id'])
    return []


@router.post("/projects")
async def create_project(data: CreateProjectRequest, user=Depends(get_current_agent)):
    """Create a project. Agent only."""
    project = await project_service.create_project(
        agent_id=get_workspace_owner_id(user),
        name=data.name,
        address=data.address,
        description=data.description,
        total_units=data.total_units or 0,
        construction_start=data.construction_start,
        estimated_completion=data.estimated_completion,
    )
    return project


@router.get("/projects/{project_id}")
async def get_project(project_id: str, user=Depends(get_current_agent)):
    """Get a single project by ID."""
    if not await can_access_project(user, project_id):
        raise HTTPException(status_code=403, detail="Access denied")
    project = await project_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project



@router.put("/projects/{project_id}")
async def update_project(project_id: str, data: UpdateProjectRequest, user=Depends(get_current_agent)):
    """Update a project. Agent only."""
    if not await can_access_project(user, project_id):
        raise HTTPException(status_code=403, detail="Access denied")

    updates = data.model_dump(exclude_none=True)
    updated = await project_service.update_project(project_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Project not found")
    return updated


@router.get("/projects/{project_id}/delete-impact")
async def get_project_delete_impact(project_id: str, user=Depends(get_current_agent)):
    """Preview linked records and risks before deleting a project."""
    if not await can_access_project(user, project_id):
        raise HTTPException(status_code=403, detail="Access denied")
    project = await project_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await project_service.get_project_delete_impact(project_id)


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    force: bool = Query(False),
    user=Depends(get_current_agent),
):
    """Delete a project with dependency guards and optional force cascade."""
    if not await can_access_project(user, project_id):
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        result = await project_service.delete_project(project_id, get_workspace_owner_id(user), force=force)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not result.get("deleted"):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"message": "Project deleted", "impact": result.get("impact", {})}
