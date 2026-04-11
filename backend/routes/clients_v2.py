"""
Client Routes — Canonical Implementation

Thin route layer. No is_demo. No business logic.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from core.auth import get_current_user, get_current_agent
from core.access_control import can_access_project, can_access_client, is_agent
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
async def list_clients(user=Depends(get_current_agent)):
    """List all clients for the agent."""
    clients = await client_service.list_clients_by_agent(user['user_id'])
    return clients


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
        agent_id=user['user_id'],
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
async def delete_client(client_id: str, user=Depends(get_current_agent)):
    """Delete a client. Agent only."""
    if not await can_access_client(user, client_id):
        raise HTTPException(status_code=403, detail="Access denied")
    deleted = await client_service.delete_client(client_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"message": "Client deleted"}
