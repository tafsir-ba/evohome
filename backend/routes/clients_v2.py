"""
Client Routes — Canonical Implementation

Thin route layer. No is_demo. No business logic.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from core.auth import get_current_user, get_current_agent
from core.access_control import can_access_project, can_access_client, is_agent, get_workspace_owner_id
from services import client_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request schemas ──

class CreateClientRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: Optional[str] = None
    phone: Optional[str] = None
    project_id: Optional[str] = None
    unit_id: Optional[str] = None
    notes: Optional[str] = None


class UpdateClientRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    project_id: Optional[str] = None
    unit_id: Optional[str] = None
    buyer_id: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


# ── Routes ──

@router.get("/clients")
async def list_clients(project_id: Optional[str] = None, user=Depends(get_current_agent)):
    """List clients for the agent, optionally filtered by project."""
    if project_id:
        if not await can_access_project(user, project_id):
            raise HTTPException(status_code=403, detail="Access denied to this project")
        return await client_service.list_clients_by_project(project_id)
    return await client_service.list_clients_by_agent(get_workspace_owner_id(user))


@router.get("/clients/{client_id}")
async def get_client(client_id: str, user=Depends(get_current_user)):
    """Get a single client."""
    if not await can_access_client(user, client_id):
        raise HTTPException(status_code=403, detail="Access denied")
    client = await client_service.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.get("/clients/{client_id}/preview")
async def get_client_preview(client_id: str, user=Depends(get_current_agent)):
    """Get client preview with documents, activities, unit info."""
    if not await can_access_client(user, client_id):
        raise HTTPException(status_code=403, detail="Access denied")
    preview = await client_service.get_client_preview(client_id)
    if not preview:
        raise HTTPException(status_code=404, detail="Client not found")
    return preview


@router.post("/clients")
async def create_client(data: CreateClientRequest, user=Depends(get_current_agent)):
    """Create a new client. Agent only."""
    if data.project_id and not await can_access_project(user, data.project_id):
        raise HTTPException(status_code=403, detail="Access denied to project")

    client = await client_service.create_client(
        agent_id=get_workspace_owner_id(user),
        name=data.name,
        email=data.email,
        phone=data.phone,
        project_id=data.project_id,
        unit_id=data.unit_id,
        notes=data.notes,
    )
    return client


@router.put("/clients/{client_id}")
async def update_client(client_id: str, data: UpdateClientRequest, user=Depends(get_current_agent)):
    """Update a client. Agent only."""
    if not await can_access_client(user, client_id):
        raise HTTPException(status_code=403, detail="Access denied")

    updates = data.model_dump(exclude_none=True)
    updated = await client_service.update_client(client_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Client not found")
    return updated


@router.delete("/clients/{client_id}")
async def delete_client(
    client_id: str,
    force: bool = Query(False),
    user=Depends(get_current_agent),
):
    """Delete a client with dependency guards."""
    if not await can_access_client(user, client_id):
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        deleted = await client_service.delete_client(client_id, force=force)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"message": "Client deleted"}


@router.get("/clients/{client_id}/delete-impact")
async def get_client_delete_impact(client_id: str, user=Depends(get_current_agent)):
    """Preview linked records and risks before deleting a client."""
    if not await can_access_client(user, client_id):
        raise HTTPException(status_code=403, detail="Access denied")
    client = await client_service.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return await client_service.get_client_delete_impact(client_id)
