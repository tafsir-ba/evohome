"""
Project Service — Canonical Implementation

All business logic for the Project entity.
No is_demo. No legacy fields.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from database import db
from services.billing_service import get_agent_subscription_data

logger = logging.getLogger(__name__)


def _make_project_id() -> str:
    return f"proj_{uuid.uuid4().hex[:12]}"


def _clean(doc: dict) -> dict:
    doc.pop('_id', None)
    return doc


async def create_project(
    agent_id: str,
    name: str,
    address: Optional[str] = None,
    description: Optional[str] = None,
    total_units: int = 0,
    construction_start: Optional[str] = None,
    estimated_completion: Optional[str] = None,
    settings: Optional[dict] = None,
) -> Dict[str, Any]:
    """Create a new project."""
    project_id = _make_project_id()
    doc = {
        "project_id": project_id,
        "agent_id": agent_id,
        "name": name,
        "address": address,
        "description": description,
        "total_units": total_units,
        "construction_start": construction_start,
        "estimated_completion": estimated_completion,
        "status": "active",
        "settings": settings or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.projects.insert_one(doc)
    return _clean(doc)


async def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    return await db.projects.find_one({"project_id": project_id}, {"_id": 0})


async def list_projects_by_agent(agent_id: str) -> List[Dict[str, Any]]:
    """List all projects for an agent, enriched with counts."""
    projects = await db.projects.find(
        {"agent_id": agent_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)

    for p in projects:
        pid = p['project_id']
        p['unit_count'] = await db.units.count_documents({"project_id": pid})
        p['client_count'] = await db.clients.count_documents({"project_id": pid})

    return projects


async def update_project(
    project_id: str,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    allowed = {"name", "address", "description", "total_units",
               "construction_start", "estimated_completion", "status", "settings"}
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        return await get_project(project_id)

    filtered["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.projects.update_one({"project_id": project_id}, {"$set": filtered})
    return await get_project(project_id)


async def delete_project(project_id: str) -> bool:
    result = await db.projects.delete_one({"project_id": project_id})
    return result.deleted_count > 0


async def count_projects_by_agent(agent_id: str) -> int:
    return await db.projects.count_documents({"agent_id": agent_id})


async def get_project_context(project_id: str) -> Dict[str, Any]:
    """Get project context for the command center (units + clients)."""
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        return {"project_id": project_id, "units": [], "clients": []}

    units = await db.units.find(
        {"project_id": project_id},
        {"_id": 0, "unit_id": 1, "unit_reference": 1, "is_available": 1, "assigned_client_id": 1}
    ).to_list(500)

    clients = await db.clients.find(
        {"project_id": project_id},
        {"_id": 0, "client_id": 1, "name": 1, "email": 1, "unit_id": 1}
    ).to_list(500)

    return {
        "project_id": project_id,
        "project_name": project.get("name", ""),
        "units": [{"unit_id": u["unit_id"], "reference": u.get("unit_reference", ""), "is_available": u.get("is_available", True)} for u in units],
        "clients": [{"client_id": c["client_id"], "name": c.get("name", ""), "email": c.get("email"), "unit_id": c.get("unit_id")} for c in clients],
    }
