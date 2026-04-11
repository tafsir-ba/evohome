"""
Timeline Service — Canonical Implementation

Business logic for Timeline entity.
Auto-created when a project is created.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from database import db

logger = logging.getLogger(__name__)


def _make_timeline_id() -> str:
    return f"tl_{uuid.uuid4().hex[:12]}"


async def create_timeline(
    project_id: str,
    agent_id: str,
    name: str = "Main Timeline",
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a timeline for a project."""
    timeline_id = _make_timeline_id()
    doc = {
        "timeline_id": timeline_id,
        "project_id": project_id,
        "agent_id": agent_id,
        "name": name,
        "description": description,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.timelines.insert_one(doc)
    doc.pop('_id', None)
    return doc


async def get_timeline(timeline_id: str) -> Optional[Dict[str, Any]]:
    return await db.timelines.find_one({"timeline_id": timeline_id}, {"_id": 0})


async def get_timeline_by_project(project_id: str) -> Optional[Dict[str, Any]]:
    """Get the main timeline for a project."""
    return await db.timelines.find_one({"project_id": project_id}, {"_id": 0})


async def get_or_create_timeline(project_id: str, agent_id: str) -> Dict[str, Any]:
    """Get existing timeline or create one for the project."""
    existing = await get_timeline_by_project(project_id)
    if existing:
        return existing
    return await create_timeline(project_id, agent_id)


async def list_timelines_by_agent(agent_id: str) -> List[Dict[str, Any]]:
    return await db.timelines.find({"agent_id": agent_id}, {"_id": 0}).to_list(500)


async def delete_timeline(timeline_id: str) -> bool:
    result = await db.timelines.delete_one({"timeline_id": timeline_id})
    return result.deleted_count > 0
