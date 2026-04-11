"""
TimelineStep Service — Canonical Implementation

Business logic for TimelineStep entity.
step_id, title, order_index — no legacy stage_id/name/order.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from database import db
from services.timeline_service import get_or_create_timeline

logger = logging.getLogger(__name__)

VALID_STATUSES = {"pending", "in_progress", "completed", "blocked"}


def _make_step_id() -> str:
    return f"step_{uuid.uuid4().hex[:12]}"


async def create_step(
    project_id: str,
    agent_id: str,
    title: str,
    order_index: int,
    description: Optional[str] = None,
    planned_start: Optional[str] = None,
    planned_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a timeline step. Auto-creates timeline if needed."""
    timeline = await get_or_create_timeline(project_id, agent_id)
    timeline_id = timeline['timeline_id']

    step_id = _make_step_id()
    doc = {
        "step_id": step_id,
        "timeline_id": timeline_id,
        "project_id": project_id,
        "title": title,
        "description": description,
        "order_index": order_index,
        "status": "pending",
        "progress_percent": 0,
        "planned_start": planned_start,
        "planned_end": planned_end,
        "actual_start": None,
        "actual_end": None,
        "dependencies": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.timeline_steps.insert_one(doc)
    doc.pop('_id', None)
    return doc


async def get_step(step_id: str) -> Optional[Dict[str, Any]]:
    return await db.timeline_steps.find_one({"step_id": step_id}, {"_id": 0})


async def list_steps_by_project(project_id: str) -> List[Dict[str, Any]]:
    """List all steps for a project, ordered by order_index."""
    return await db.timeline_steps.find(
        {"project_id": project_id}, {"_id": 0}
    ).sort("order_index", 1).to_list(200)


async def update_step(
    step_id: str,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    allowed = {"title", "description", "order_index", "status", "progress_percent",
               "planned_start", "planned_end", "actual_start", "actual_end", "dependencies"}
    filtered = {k: v for k, v in updates.items() if k in allowed}

    if "status" in filtered and filtered["status"] not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {filtered['status']}")

    if "progress_percent" in filtered:
        filtered["progress_percent"] = max(0, min(100, int(filtered["progress_percent"])))

    if not filtered:
        return await get_step(step_id)

    filtered["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.timeline_steps.update_one({"step_id": step_id}, {"$set": filtered})
    return await get_step(step_id)


async def delete_step(step_id: str) -> bool:
    result = await db.timeline_steps.delete_one({"step_id": step_id})
    return result.deleted_count > 0


async def count_steps_by_project(project_id: str) -> int:
    return await db.timeline_steps.count_documents({"project_id": project_id})
