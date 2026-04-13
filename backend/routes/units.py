"""
Unit Routes — Canonical Implementation

Thin route layer: validates, authorizes, delegates to service, shapes response.
No business logic. No is_demo. No legacy fields.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from core.auth import get_current_user, get_current_agent
from core.access_control import can_access_project, is_agent, get_workspace_owner_id
from services import unit_service, client_service
from services.billing_service import can_create_unit, get_unit_limit

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request schemas ──

class CreateUnitRequest(BaseModel):
    unit_reference: str = Field(..., min_length=1, max_length=100)
    notes: Optional[str] = None


class UpdateUnitRequest(BaseModel):
    unit_reference: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


# ── Routes ──

@router.post("/projects/{project_id}/units")
async def create_unit(project_id: str, data: CreateUnitRequest, user=Depends(get_current_agent)):
    """Create a unit within a project. Agent only. Checks subscription limits."""
    if not await can_access_project(user, project_id):
        raise HTTPException(status_code=403, detail="Access denied to this project")

    # Subscription limit check
    if not await can_create_unit(user['user_id']):
        limit = await get_unit_limit(user['user_id'])
        raise HTTPException(
            status_code=403,
            detail=f"Unit limit reached ({limit}). Upgrade your plan."
        )

    unit = await unit_service.create_unit(
        project_id=project_id,
        agent_id=get_workspace_owner_id(user),
        unit_reference=data.unit_reference,
        notes=data.notes,
    )
    return unit


@router.get("/projects/{project_id}/units")
async def list_project_units(project_id: str, user=Depends(get_current_user)):
    """List all units for a project."""
    if not await can_access_project(user, project_id):
        raise HTTPException(status_code=403, detail="Access denied to this project")

    units = await unit_service.list_units_by_project(project_id)
    return units


@router.get("/units/{unit_id}")
async def get_unit(unit_id: str, user=Depends(get_current_user)):
    """Get a single unit by ID."""
    unit = await unit_service.get_unit(unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    if not await can_access_project(user, unit['project_id']):
        raise HTTPException(status_code=403, detail="Access denied")

    return unit


@router.get("/units/{unit_id}/clients")
async def list_unit_clients(unit_id: str, user=Depends(get_current_user)):
    """List clients currently assigned to a unit."""
    unit = await unit_service.get_unit(unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    if not await can_access_project(user, unit['project_id']):
        raise HTTPException(status_code=403, detail="Access denied")
    clients = await client_service.list_clients_by_project(unit["project_id"])
    return [c for c in clients if c.get("unit_id") == unit_id]


@router.post("/units/{unit_id}/clients/{client_id}")
async def attach_client_to_unit(unit_id: str, client_id: str, user=Depends(get_current_agent)):
    """Assign a client to this unit (unit-side action)."""
    unit = await unit_service.get_unit(unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    if not await can_access_project(user, unit['project_id']):
        raise HTTPException(status_code=403, detail="Access denied")

    client = await client_service.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if client.get("agent_id") != get_workspace_owner_id(user):
        raise HTTPException(status_code=403, detail="Access denied")
    if client.get("project_id") != unit.get("project_id"):
        raise HTTPException(status_code=400, detail="Client and unit must belong to the same project")

    updated = await client_service.update_client(client_id, {"unit_id": unit_id})
    if not updated:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"message": "Client attached to unit", "client": updated}


@router.delete("/units/{unit_id}/clients/{client_id}")
async def detach_client_from_unit(unit_id: str, client_id: str, user=Depends(get_current_agent)):
    """Detach a client from this unit (set client unit to null)."""
    unit = await unit_service.get_unit(unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    if not await can_access_project(user, unit['project_id']):
        raise HTTPException(status_code=403, detail="Access denied")

    client = await client_service.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if client.get("agent_id") != get_workspace_owner_id(user):
        raise HTTPException(status_code=403, detail="Access denied")
    if client.get("unit_id") != unit_id:
        raise HTTPException(status_code=400, detail="Client is not assigned to this unit")

    updated = await client_service.update_client(client_id, {"unit_id": None})
    if not updated:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"message": "Client detached from unit", "client": updated}


@router.put("/units/{unit_id}")
async def update_unit(unit_id: str, data: UpdateUnitRequest, user=Depends(get_current_agent)):
    """Update a unit. Agent only."""
    unit = await unit_service.get_unit(unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    if not await can_access_project(user, unit['project_id']):
        raise HTTPException(status_code=403, detail="Access denied")

    updates = data.model_dump(exclude_none=True)
    updated = await unit_service.update_unit(unit_id, updates)
    return updated


@router.delete("/units/{unit_id}")
async def delete_unit(unit_id: str, user=Depends(get_current_agent)):
    """Delete a unit. Agent only."""
    unit = await unit_service.get_unit(unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    if not await can_access_project(user, unit['project_id']):
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        await unit_service.delete_unit(unit_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Unit deleted"}
