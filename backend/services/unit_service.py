"""
Unit Service — Canonical Implementation

All business logic for the Unit entity.
Routes delegate here. No is_demo. No legacy fields.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from database import db

logger = logging.getLogger(__name__)


def _make_unit_id() -> str:
    return f"unit_{uuid.uuid4().hex[:12]}"


def _clean(doc: dict) -> dict:
    """Remove MongoDB _id from a document."""
    doc.pop('_id', None)
    return doc


async def create_unit(
    project_id: str,
    agent_id: str,
    unit_reference: str,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a unit within a project."""
    unit_id = _make_unit_id()
    doc = {
        "unit_id": unit_id,
        "project_id": project_id,
        "agent_id": agent_id,
        "unit_reference": unit_reference,
        "assigned_client_id": None,
        "is_available": True,
        "status": "active",
        "notes": notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.units.insert_one(doc)
    return _clean(doc)


async def get_unit(unit_id: str) -> Optional[Dict[str, Any]]:
    """Get a single unit by ID."""
    doc = await db.units.find_one({"unit_id": unit_id}, {"_id": 0})
    return doc


async def list_units_by_project(project_id: str) -> List[Dict[str, Any]]:
    """List all units for a project, enriched with client assignment info."""
    cursor = db.units.find({"project_id": project_id}, {"_id": 0})
    units = await cursor.to_list(500)

    # Enrich with assigned client name
    for unit in units:
        if unit.get('assigned_client_id'):
            client = await db.clients.find_one(
                {"client_id": unit['assigned_client_id']},
                {"_id": 0, "name": 1}
            )
            unit['assigned_client_name'] = client['name'] if client else None
        else:
            unit['assigned_client_name'] = None

    return units


async def list_units_by_agent(agent_id: str) -> List[Dict[str, Any]]:
    """List all units owned by an agent."""
    cursor = db.units.find({"agent_id": agent_id}, {"_id": 0})
    return await cursor.to_list(5000)


async def update_unit(
    unit_id: str,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Update a unit. Only allowed fields are applied."""
    allowed = {"unit_reference", "notes", "status"}
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        return await get_unit(unit_id)

    filtered["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.units.update_one({"unit_id": unit_id}, {"$set": filtered})
    return await get_unit(unit_id)


async def assign_client(unit_id: str, client_id: str) -> Optional[Dict[str, Any]]:
    """Assign a client to a unit."""
    await db.units.update_one(
        {"unit_id": unit_id},
        {"$set": {
            "assigned_client_id": client_id,
            "is_available": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    return await get_unit(unit_id)


async def unassign_client(unit_id: str) -> Optional[Dict[str, Any]]:
    """Remove client assignment from a unit."""
    await db.units.update_one(
        {"unit_id": unit_id},
        {"$set": {
            "assigned_client_id": None,
            "is_available": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    return await get_unit(unit_id)


async def delete_unit(unit_id: str) -> bool:
    """Delete a unit."""
    result = await db.units.delete_one({"unit_id": unit_id})
    return result.deleted_count > 0


async def count_units_by_agent(agent_id: str) -> int:
    """Count total units owned by an agent (for billing limits)."""
    return await db.units.count_documents({"agent_id": agent_id})


async def count_units_by_project(project_id: str) -> int:
    """Count units in a project."""
    return await db.units.count_documents({"project_id": project_id})
