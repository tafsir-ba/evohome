"""
Gantt Chart Service — standalone CRUD (no CMP coupling).
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from database import db
from services.gantt_validation import GanttValidationError, validate_task_payload

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_project_id() -> str:
    return f"gp_{uuid.uuid4().hex[:12]}"


def _make_task_id() -> str:
    return f"gt_{uuid.uuid4().hex[:12]}"


async def _get_project_for_owner(
    gantt_project_id: str,
    owner_user_id: str,
) -> Optional[Dict[str, Any]]:
    return await db.gantt_projects.find_one(
        {"gantt_project_id": gantt_project_id, "owner_user_id": owner_user_id},
        {"_id": 0},
    )


async def create_project(
    owner_user_id: str,
    title: str,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    now = _now()
    gantt_project_id = _make_project_id()
    doc = {
        "gantt_project_id": gantt_project_id,
        "owner_user_id": owner_user_id,
        "title": title,
        "description": description,
        "created_at": now,
        "updated_at": now,
    }
    await db.gantt_projects.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def list_projects(owner_user_id: str) -> List[Dict[str, Any]]:
    return await db.gantt_projects.find(
        {"owner_user_id": owner_user_id},
        {"_id": 0},
    ).sort("updated_at", -1).to_list(500)


async def get_project(
    gantt_project_id: str,
    owner_user_id: str,
) -> Optional[Dict[str, Any]]:
    return await _get_project_for_owner(gantt_project_id, owner_user_id)


async def update_project(
    gantt_project_id: str,
    owner_user_id: str,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    allowed = {"title", "description"}
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        return await get_project(gantt_project_id, owner_user_id)

    filtered["updated_at"] = _now()
    result = await db.gantt_projects.update_one(
        {"gantt_project_id": gantt_project_id, "owner_user_id": owner_user_id},
        {"$set": filtered},
    )
    if result.matched_count == 0:
        return None
    return await get_project(gantt_project_id, owner_user_id)


async def delete_project(
    gantt_project_id: str,
    owner_user_id: str,
) -> Optional[int]:
    project = await _get_project_for_owner(gantt_project_id, owner_user_id)
    if not project:
        return None

    delete_result = await db.gantt_tasks.delete_many(
        {"gantt_project_id": gantt_project_id, "owner_user_id": owner_user_id}
    )
    await db.gantt_projects.delete_one(
        {"gantt_project_id": gantt_project_id, "owner_user_id": owner_user_id}
    )
    return delete_result.deleted_count


async def _list_tasks_raw(
    gantt_project_id: str,
    owner_user_id: str,
) -> List[Dict[str, Any]]:
    return await db.gantt_tasks.find(
        {"gantt_project_id": gantt_project_id, "owner_user_id": owner_user_id},
        {"_id": 0},
    ).sort("order", 1).to_list(1000)


async def _next_task_order(gantt_project_id: str, owner_user_id: str) -> int:
    pipeline = [
        {"$match": {"gantt_project_id": gantt_project_id, "owner_user_id": owner_user_id}},
        {"$group": {"_id": None, "max_order": {"$max": "$order"}}},
    ]
    result = await db.gantt_tasks.aggregate(pipeline).to_list(1)
    if result and result[0].get("max_order") is not None:
        return result[0]["max_order"] + 1
    return 0


async def create_task(
    gantt_project_id: str,
    owner_user_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    project = await _get_project_for_owner(gantt_project_id, owner_user_id)
    if not project:
        raise PermissionError("Project not found or access denied")

    existing_tasks = await _list_tasks_raw(gantt_project_id, owner_user_id)
    project_task_ids = {t["task_id"] for t in existing_tasks}

    task_id = _make_task_id()
    task_type = payload.get("type", "task")

    validated = validate_task_payload(
        payload,
        task_id=task_id,
        task_type=task_type,
        project_task_ids=project_task_ids,
        existing_tasks=existing_tasks,
        is_create=True,
    )

    now = _now()
    doc = {
        "task_id": task_id,
        "gantt_project_id": gantt_project_id,
        "owner_user_id": owner_user_id,
        "order": await _next_task_order(gantt_project_id, owner_user_id),
        "phase": validated.get("phase"),
        "title": validated["title"],
        "description": validated.get("description"),
        "type": validated["type"],
        "start_date": validated["start_date"],
        "end_date": validated["end_date"],
        "duration_days": validated["duration_days"],
        "status": validated["status"],
        "responsible_party": validated.get("responsible_party"),
        "dependencies": validated["dependencies"],
        "source": "manual",
        "created_at": now,
        "updated_at": now,
    }
    await db.gantt_tasks.insert_one(doc)
    doc.pop("_id", None)

    await db.gantt_projects.update_one(
        {"gantt_project_id": gantt_project_id, "owner_user_id": owner_user_id},
        {"$set": {"updated_at": now}},
    )
    return doc


async def list_tasks(
    gantt_project_id: str,
    owner_user_id: str,
) -> List[Dict[str, Any]]:
    project = await _get_project_for_owner(gantt_project_id, owner_user_id)
    if not project:
        raise PermissionError("Project not found or access denied")
    return await _list_tasks_raw(gantt_project_id, owner_user_id)


async def update_task(
    gantt_project_id: str,
    owner_user_id: str,
    task_id: str,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    project = await _get_project_for_owner(gantt_project_id, owner_user_id)
    if not project:
        raise PermissionError("Project not found or access denied")

    existing = await db.gantt_tasks.find_one(
        {
            "task_id": task_id,
            "gantt_project_id": gantt_project_id,
            "owner_user_id": owner_user_id,
        },
        {"_id": 0},
    )
    if not existing:
        return None

    existing_tasks = await _list_tasks_raw(gantt_project_id, owner_user_id)
    project_task_ids = {t["task_id"] for t in existing_tasks}

    merged = {**existing}
    for key, value in updates.items():
        merged[key] = value
    task_type = merged.get("type", "task")

    validated = validate_task_payload(
        merged,
        task_id=task_id,
        task_type=task_type,
        project_task_ids=project_task_ids,
        existing_tasks=existing_tasks,
        is_create=False,
    )

    allowed_fields = {
        "type", "phase", "title", "description", "start_date", "end_date",
        "duration_days", "status", "responsible_party", "dependencies",
    }
    filtered = {k: validated[k] for k in allowed_fields if k in validated}
    filtered["updated_at"] = _now()

    await db.gantt_tasks.update_one(
        {"task_id": task_id, "gantt_project_id": gantt_project_id, "owner_user_id": owner_user_id},
        {"$set": filtered},
    )
    await db.gantt_projects.update_one(
        {"gantt_project_id": gantt_project_id, "owner_user_id": owner_user_id},
        {"$set": {"updated_at": filtered["updated_at"]}},
    )
    return await db.gantt_tasks.find_one(
        {"task_id": task_id, "gantt_project_id": gantt_project_id, "owner_user_id": owner_user_id},
        {"_id": 0},
    )


async def count_task_dependents(
    gantt_project_id: str,
    owner_user_id: str,
    task_id: str,
) -> int:
    return await db.gantt_tasks.count_documents({
        "gantt_project_id": gantt_project_id,
        "owner_user_id": owner_user_id,
        "dependencies.task_id": task_id,
    })


async def delete_task(
    gantt_project_id: str,
    owner_user_id: str,
    task_id: str,
) -> str:
    """
    Delete a task. Returns 'deleted', 'not_found', or 'has_dependents'.
    """
    project = await _get_project_for_owner(gantt_project_id, owner_user_id)
    if not project:
        raise PermissionError("Project not found or access denied")

    existing = await db.gantt_tasks.find_one(
        {
            "task_id": task_id,
            "gantt_project_id": gantt_project_id,
            "owner_user_id": owner_user_id,
        },
        {"_id": 0},
    )
    if not existing:
        return "not_found"

    dependents = await count_task_dependents(gantt_project_id, owner_user_id, task_id)
    if dependents > 0:
        return "has_dependents"

    await db.gantt_tasks.delete_one(
        {"task_id": task_id, "gantt_project_id": gantt_project_id, "owner_user_id": owner_user_id}
    )

    remaining = await _list_tasks_raw(gantt_project_id, owner_user_id)
    for index, task in enumerate(remaining):
        if task["order"] != index:
            await db.gantt_tasks.update_one(
                {"task_id": task["task_id"]},
                {"$set": {"order": index}},
            )

    now = _now()
    await db.gantt_projects.update_one(
        {"gantt_project_id": gantt_project_id, "owner_user_id": owner_user_id},
        {"$set": {"updated_at": now}},
    )
    return "deleted"


async def reorder_tasks(
    gantt_project_id: str,
    owner_user_id: str,
    task_ids: List[str],
) -> List[Dict[str, Any]]:
    project = await _get_project_for_owner(gantt_project_id, owner_user_id)
    if not project:
        raise PermissionError("Project not found or access denied")

    existing_tasks = await _list_tasks_raw(gantt_project_id, owner_user_id)
    existing_ids: Set[str] = {t["task_id"] for t in existing_tasks}
    submitted_ids: Set[str] = set(task_ids)

    if existing_ids != submitted_ids:
        raise GanttValidationError("task_ids must be a full permutation of project tasks")

    now = _now()
    for index, tid in enumerate(task_ids):
        await db.gantt_tasks.update_one(
            {
                "task_id": tid,
                "gantt_project_id": gantt_project_id,
                "owner_user_id": owner_user_id,
            },
            {"$set": {"order": index, "updated_at": now}},
        )

    await db.gantt_projects.update_one(
        {"gantt_project_id": gantt_project_id, "owner_user_id": owner_user_id},
        {"$set": {"updated_at": now}},
    )
    return await _list_tasks_raw(gantt_project_id, owner_user_id)
