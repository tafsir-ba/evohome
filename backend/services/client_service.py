"""
Client Service — Canonical Implementation

Business logic for Client (Buyer) entity.
Self-contained — no cross-import from activities.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from database import db

logger = logging.getLogger(__name__)


def _make_client_id() -> str:
    return f"client_{uuid.uuid4().hex[:12]}"


async def create_client(
    agent_id: str,
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    project_id: Optional[str] = None,
    unit_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a client."""
    client_id = _make_client_id()
    doc = {
        "client_id": client_id,
        "agent_id": agent_id,
        "name": name,
        "email": email,
        "phone": phone,
        "project_id": project_id,
        "unit_id": unit_id,
        "buyer_id": None,
        "status": "active",
        "notes": notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # If unit_id is provided, mark unit as assigned
    if unit_id:
        await db.units.update_one(
            {"unit_id": unit_id},
            {"$set": {"assigned_client_id": client_id, "is_available": False,
                      "updated_at": datetime.now(timezone.utc).isoformat()}}
        )

    await db.clients.insert_one(doc)
    doc.pop('_id', None)
    return doc


async def get_client(client_id: str) -> Optional[Dict[str, Any]]:
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        return None
    # Enrich with project name
    if client.get("project_id"):
        project = await db.projects.find_one(
            {"project_id": client["project_id"]}, {"_id": 0, "name": 1}
        )
        if project:
            client["project_name"] = project["name"]
    # Enrich with unit reference
    if client.get("unit_id"):
        unit = await db.units.find_one(
            {"unit_id": client["unit_id"]}, {"_id": 0, "unit_reference": 1}
        )
        if unit:
            client["unit_reference"] = unit.get("unit_reference") or client.get("unit_reference")
    return client


async def list_clients_by_agent(agent_id: str) -> List[Dict[str, Any]]:
    clients = await db.clients.find(
        {"agent_id": agent_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(1000)

    # Batch-enrich with project names
    project_ids = list({c["project_id"] for c in clients if c.get("project_id")})
    if project_ids:
        projects = await db.projects.find(
            {"project_id": {"$in": project_ids}}, {"_id": 0, "project_id": 1, "name": 1}
        ).to_list(len(project_ids))
        project_map = {p["project_id"]: p["name"] for p in projects}
        for c in clients:
            c["project_name"] = project_map.get(c.get("project_id"))

    # Batch-enrich with unit_reference from units collection
    unit_ids = list({c["unit_id"] for c in clients if c.get("unit_id")})
    if unit_ids:
        units = await db.units.find(
            {"unit_id": {"$in": unit_ids}}, {"_id": 0, "unit_id": 1, "unit_reference": 1}
        ).to_list(len(unit_ids))
        unit_map = {u["unit_id"]: u.get("unit_reference") for u in units}
        for c in clients:
            c["unit_reference"] = unit_map.get(c.get("unit_id")) or c.get("unit_reference")

    return clients


async def list_clients_by_project(project_id: str) -> List[Dict[str, Any]]:
    clients = await db.clients.find(
        {"project_id": project_id}, {"_id": 0}
    ).to_list(500)

    # Enrich with project name
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0, "name": 1})
    project_name = project.get("name") if project else None

    # Batch-enrich with unit_reference
    unit_ids = list({c["unit_id"] for c in clients if c.get("unit_id")})
    if unit_ids:
        units = await db.units.find(
            {"unit_id": {"$in": unit_ids}}, {"_id": 0, "unit_id": 1, "unit_reference": 1}
        ).to_list(len(unit_ids))
        unit_map = {u["unit_id"]: u.get("unit_reference") for u in units}
        for c in clients:
            c["unit_reference"] = unit_map.get(c.get("unit_id")) or c.get("unit_reference")
            c["project_name"] = project_name

    return clients


async def update_client(
    client_id: str,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    allowed = {"name", "email", "phone", "project_id", "unit_id",
               "buyer_id", "status", "notes"}
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        return await get_client(client_id)

    # Handle unit assignment changes
    old_client = await get_client(client_id)
    if "unit_id" in filtered and old_client:
        old_unit_id = old_client.get("unit_id")
        new_unit_id = filtered.get("unit_id")

        # Unassign old unit
        if old_unit_id and old_unit_id != new_unit_id:
            await db.units.update_one(
                {"unit_id": old_unit_id},
                {"$set": {"assigned_client_id": None, "is_available": True,
                          "updated_at": datetime.now(timezone.utc).isoformat()}}
            )

        # Assign new unit
        if new_unit_id:
            await db.units.update_one(
                {"unit_id": new_unit_id},
                {"$set": {"assigned_client_id": client_id, "is_available": False,
                          "updated_at": datetime.now(timezone.utc).isoformat()}}
            )

    filtered["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.clients.update_one({"client_id": client_id}, {"$set": filtered})
    return await get_client(client_id)


async def delete_client(client_id: str) -> bool:
    client = await get_client(client_id)
    if client and client.get("unit_id"):
        await db.units.update_one(
            {"unit_id": client["unit_id"]},
            {"$set": {"assigned_client_id": None, "is_available": True}}
        )
    result = await db.clients.delete_one({"client_id": client_id})
    return result.deleted_count > 0


async def link_buyer(client_id: str, buyer_id: str) -> Optional[Dict[str, Any]]:
    """Link a buyer account to a client record."""
    await db.clients.update_one(
        {"client_id": client_id},
        {"$set": {"buyer_id": buyer_id, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return await get_client(client_id)


async def get_client_preview(client_id: str) -> Dict[str, Any]:
    """Get client preview data for agent 'view as client' page."""
    client = await get_client(client_id)
    if not client:
        return {}

    # Get associated documents
    documents = await db.documents.find(
        {"client_id": client_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(20)

    # Get recent activities involving this client
    activities = await db.activities.find(
        {"client_ids": client_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(10)

    # Get unit info
    unit = None
    if client.get("unit_id"):
        unit = await db.units.find_one(
            {"unit_id": client["unit_id"]},
            {"_id": 0, "unit_id": 1, "unit_reference": 1}
        )

    # Get project info
    project = None
    if client.get("project_id"):
        project = await db.projects.find_one(
            {"project_id": client["project_id"]},
            {"_id": 0, "project_id": 1, "name": 1, "address": 1}
        )

    # Get team members for this project
    team = []
    if client.get("project_id"):
        team = await db.team_members.find(
            {"project_id": client["project_id"]},
            {"_id": 0}
        ).to_list(50)

    return {
        "client": client,
        "project": project,
        "documents": documents,
        "activities": activities,
        "team": team,
        "unit": unit,
    }
