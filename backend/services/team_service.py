"""
Team Service — Canonical Implementation.

Single source of truth for team member lifecycle.
No is_demo. Ownership scoped via agent_id + project_id.
"""
import uuid
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from database import db
from core.access_control import get_workspace_owner_id, can_access_project, get_accessible_project_ids

logger = logging.getLogger(__name__)


async def _verify_project_access(project_id: str, user: dict) -> dict:
    """Verify user has access to the project. Returns project dict."""
    if user["role"] == "agent":
        if not await can_access_project(user, project_id):
            return None
        scope_agent_id = get_workspace_owner_id(user)
        project = await db.projects.find_one(
            {"project_id": project_id, "agent_id": scope_agent_id}, {"_id": 0}
        )
    else:
        client = await db.clients.find_one(
            {"buyer_id": user["user_id"], "project_id": project_id}, {"_id": 0}
        )
        if client:
            project = await db.projects.find_one(
                {"project_id": project_id}, {"_id": 0}
            )
        else:
            project = None
    return project


async def list_team_members(project_id: str, user: dict) -> List[Dict[str, Any]]:
    """List team members for a project."""
    project = await _verify_project_access(project_id, user)
    if not project:
        return None  # caller raises 404/403
    return await db.team_members.find(
        {"project_id": project_id}, {"_id": 0}
    ).sort("name", 1).to_list(100)


async def create_team_member(
    project_id: str,
    agent_id: str,
    company_name: str,
    contact_name: str,
    role: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    website: Optional[str] = None,
    address: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a team member. Returns the created member dict."""
    member_id = f"member_{uuid.uuid4().hex[:12]}"
    doc = {
        "member_id": member_id,
        "project_id": project_id,
        "agent_id": agent_id,
        "company_name": company_name,
        "contact_name": contact_name,
        "role": role,
        "email": email,
        "phone": phone,
        "website": website,
        "address": address,
        "notes": notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.team_members.insert_one(doc)
    return await db.team_members.find_one({"member_id": member_id}, {"_id": 0})


async def update_team_member(
    member_id: str, project_id: str, agent_id: str, update_data: dict
) -> Optional[Dict[str, Any]]:
    """Update a team member. Returns updated doc or None if not found."""
    member = await db.team_members.find_one(
        {"member_id": member_id, "project_id": project_id, "agent_id": agent_id},
        {"_id": 0},
    )
    if not member:
        return None
    clean = {k: v for k, v in update_data.items() if v is not None}
    if clean:
        await db.team_members.update_one({"member_id": member_id}, {"$set": clean})
    return await db.team_members.find_one({"member_id": member_id}, {"_id": 0})


async def delete_team_member(
    member_id: str, project_id: str, agent_id: str
) -> bool:
    """Delete a team member. Returns True if deleted."""
    member = await db.team_members.find_one(
        {"member_id": member_id, "project_id": project_id, "agent_id": agent_id},
        {"_id": 0},
    )
    if not member:
        return False
    await db.team_members.delete_one({"member_id": member_id})
    return True


async def get_directory(
    agent_id: str,
    accessible_project_ids: Optional[List[str]] = None,
    search: Optional[str] = None,
    project_id: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Global supplier/contact directory for an agent."""
    query: dict = {"agent_id": agent_id}
    if project_id:
        query["project_id"] = project_id
    elif accessible_project_ids is not None:
        if not accessible_project_ids:
            return []
        query["project_id"] = {"$in": accessible_project_ids}

    members = await db.team_members.find(query, {"_id": 0}).to_list(500)

    # Deduplicate by company_name + contact_name
    seen: set = set()
    unique: list = []
    for m in members:
        key = (m.get("company_name", "").lower(), m.get("contact_name", "").lower())
        if key not in seen:
            seen.add(key)
            unique.append(m)

    if search:
        s = search.lower()
        unique = [
            m for m in unique
            if s in (m.get("company_name", "") or "").lower()
            or s in (m.get("contact_name", "") or "").lower()
            or s in (m.get("role", "") or "").lower()
        ]

    unique.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return unique[:limit]


async def bulk_create_team_members(
    project_id: str,
    agent_id: str,
    contacts: List[dict],
) -> Dict[str, Any]:
    """Bulk import team members. Returns created count, skipped count, and members."""
    created_members: list = []
    skipped = 0

    for contact in contacts:
        if not contact.get("company_name") and not contact.get("contact_name"):
            skipped += 1
            continue

        existing = await db.team_members.find_one({
            "project_id": project_id,
            "agent_id": agent_id,
            "company_name": contact.get("company_name", ""),
            "contact_name": contact.get("contact_name", ""),
        })
        if existing:
            skipped += 1
            continue

        member = await create_team_member(
            project_id=project_id,
            agent_id=agent_id,
            company_name=contact.get("company_name", ""),
            contact_name=contact.get("contact_name", ""),
            role=contact.get("role", "Supplier"),
            email=contact.get("email"),
            phone=contact.get("phone"),
            website=contact.get("website"),
            address=contact.get("address"),
            notes=contact.get("notes"),
        )
        created_members.append(member)

    return {
        "created": len(created_members),
        "skipped": skipped,
        "members": created_members,
    }
