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

VALID_STATUSES = {"pending", "in_progress", "completed", "blocked", "approved"}


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
        {"project_id": project_id}, {"_id": 0, "is_demo": 0}
    ).sort("order_index", 1).to_list(200)


async def update_step(
    step_id: str,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    allowed = {"title", "description", "order_index", "status", "progress_percent",
               "planned_start", "planned_end", "actual_start", "actual_end",
               "dependencies", "planned_date", "notes"}
    filtered = {k: v for k, v in updates.items() if k in allowed}

    if "status" in filtered and filtered["status"] not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {filtered['status']}")

    if "progress_percent" in filtered:
        filtered["progress_percent"] = max(0, min(100, int(filtered["progress_percent"])))

    # Auto-set completed_at on status transitions
    if "status" in filtered:
        if filtered["status"] == "completed":
            filtered["completed_at"] = datetime.now(timezone.utc).isoformat()
        elif filtered["status"] in ("pending", "in_progress"):
            filtered["completed_at"] = None

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


async def add_step_to_timeline(
    timeline_id: str,
    project_id: str,
    title: str,
    description: Optional[str] = None,
    planned_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a step to a timeline with auto-incrementing order_index."""
    pipeline = [
        {"$match": {"timeline_id": timeline_id}},
        {"$group": {"_id": None, "max_order": {"$max": "$order_index"}}}
    ]
    result = await db.timeline_steps.aggregate(pipeline).to_list(1)
    max_order = result[0]['max_order'] if result and result[0].get('max_order') is not None else -1

    step_id = _make_step_id()
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "step_id": step_id,
        "timeline_id": timeline_id,
        "project_id": project_id,
        "title": title,
        "description": description or '',
        "planned_date": planned_date,
        "status": "pending",
        "order_index": max_order + 1,
        "progress_percent": 0,
        "created_at": now,
    }
    await db.timeline_steps.insert_one(doc)
    doc.pop('_id', None)
    return doc


async def link_document(step_id: str, activity_id: str) -> Optional[str]:
    """Link an activity/document to a step. Returns link_id or None if already linked."""
    existing = await db.timeline_step_documents.find_one({
        "timeline_step_id": step_id, "activity_id": activity_id
    })
    if existing:
        return None

    link_id = f"link_{uuid.uuid4().hex[:12]}"
    await db.timeline_step_documents.insert_one({
        "link_id": link_id,
        "timeline_step_id": step_id,
        "activity_id": activity_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return link_id


async def unlink_document(step_id: str, activity_id: str) -> bool:
    """Unlink a document from a step."""
    result = await db.timeline_step_documents.delete_one({
        "timeline_step_id": step_id, "activity_id": activity_id
    })
    return result.deleted_count > 0


async def add_note(
    step_id: str, author_id: str, author_name: str, content: str
) -> Dict[str, Any]:
    """Add an internal note to a step."""
    note_id = f"note_{uuid.uuid4().hex[:12]}"
    doc = {
        "note_id": note_id,
        "timeline_step_id": step_id,
        "author_id": author_id,
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.timeline_step_internal_notes.insert_one(doc)
    doc.pop('_id', None)
    doc['author_name'] = author_name
    return doc
