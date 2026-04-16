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
from services.billing_service import get_subscription_status

logger = logging.getLogger(__name__)
NON_DRAFT_DOCUMENT_STATUS = {"Draft"}


def _make_project_id() -> str:
    return f"proj_{uuid.uuid4().hex[:12]}"


def _clean(doc: dict) -> dict:
    doc.pop('_id', None)
    return doc


def _collect_string_ids(rows: List[Dict[str, Any]], key: str) -> List[str]:
    """Collect non-empty string IDs from row dicts without raising KeyError."""
    ids: List[str] = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, str) and value:
            ids.append(value)
    return ids


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


async def list_projects_by_agent(agent_id: str, project_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """List all projects for an agent, enriched with counts."""
    query: Dict[str, Any] = {"agent_id": agent_id}
    if project_ids is not None:
        if not project_ids:
            return []
        query["project_id"] = {"$in": project_ids}
    projects = await db.projects.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)

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


async def get_project_delete_impact(project_id: str) -> Dict[str, Any]:
    """Summarize linked records and deletion risks for a project."""
    doc_status_pipeline = [
        {"$match": {"project_id": project_id}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]
    status_rows = await db.documents.aggregate(doc_status_pipeline).to_list(50)
    documents_by_status = {row.get("_id") or "unknown": row.get("count", 0) for row in status_rows}
    non_draft_documents = sum(
        count for status, count in documents_by_status.items() if status not in NON_DRAFT_DOCUMENT_STATUS
    )

    impact = {
        "project_id": project_id,
        "clients": await db.clients.count_documents({"project_id": project_id}),
        "units": await db.units.count_documents({"project_id": project_id}),
        "documents_total": await db.documents.count_documents({"project_id": project_id}),
        "documents_non_draft": non_draft_documents,
        "documents_by_status": documents_by_status,
        "activities": await db.activities.count_documents({"project_id": project_id}),
        "timelines": await db.timelines.count_documents({"project_id": project_id}),
        "timeline_steps": await db.timeline_steps.count_documents({"project_id": project_id}),
        "team_members": await db.team_members.count_documents({"project_id": project_id}),
        "vault_documents": await db.vault_documents.count_documents({"project_id": project_id}),
        "decisions": await db.decisions.count_documents({"project_id": project_id}),
        "change_requests": await db.change_requests.count_documents({"project_id": project_id}),
    }
    impact["has_linked_data"] = any(v > 0 for k, v in impact.items() if isinstance(v, int))
    return impact


async def delete_project(project_id: str, agent_id: str, force: bool = False) -> Dict[str, Any]:
    """
    Delete a project with dependency guards.
    - Blocks deletion when non-draft financial documents exist.
    - Requires force=true when linked records exist.
    - Cascades cleanup for draft-only project data.
    """
    project = await db.projects.find_one({"project_id": project_id, "agent_id": agent_id}, {"_id": 0})
    if not project:
        return {"deleted": False, "reason": "not_found"}

    impact = await get_project_delete_impact(project_id)
    if impact["documents_non_draft"] > 0:
        raise ValueError(
            "Cannot delete project with issued documents (Sent/Approved/Paid/etc). "
            "Archive the project instead."
        )

    if impact["has_linked_data"] and not force:
        raise ValueError(
            "Project has linked data. Re-run delete with force=true after reviewing delete impact."
        )

    # Delete draft document files before DB cleanup.
    from services.file_service import delete_file
    draft_docs = await db.documents.find(
        {"project_id": project_id, "status": "Draft"},
        {"_id": 0, "document_id": 1, "pdf_stored_filename": 1, "hero_image_stored_filename": 1},
    ).to_list(10000)
    draft_doc_ids = _collect_string_ids(draft_docs, "document_id")
    for doc in draft_docs:
        for fk in ("pdf_stored_filename", "hero_image_stored_filename"):
            if doc.get(fk):
                delete_file(doc[fk])

    # Delete vault files before removing vault records.
    vault_docs = await db.vault_documents.find(
        {"project_id": project_id}, {"_id": 0, "stored_filename": 1}
    ).to_list(10000)
    for vd in vault_docs:
        if vd.get("stored_filename"):
            delete_file(vd["stored_filename"])

    # Activity cascade cleanup (children first)
    activities = await db.activities.find({"project_id": project_id}, {"_id": 0, "activity_id": 1}).to_list(10000)
    activity_ids = _collect_string_ids(activities, "activity_id")
    if activity_ids:
        await db.activity_recipients.delete_many({"activity_id": {"$in": activity_ids}})
        await db.activity_replies.delete_many({"activity_id": {"$in": activity_ids}})
    await db.activities.delete_many({"project_id": project_id})

    # Timeline cascade cleanup (children first)
    timelines = await db.timelines.find({"project_id": project_id}, {"_id": 0, "timeline_id": 1}).to_list(1000)
    timeline_ids = _collect_string_ids(timelines, "timeline_id")
    step_ids: List[str] = []
    if timeline_ids:
        steps = await db.timeline_steps.find(
            {"timeline_id": {"$in": timeline_ids}}, {"_id": 0, "step_id": 1}
        ).to_list(5000)
        step_ids = _collect_string_ids(steps, "step_id")
    if step_ids:
        await db.timeline_step_documents.delete_many({"timeline_step_id": {"$in": step_ids}})
        await db.timeline_step_internal_notes.delete_many({"timeline_step_id": {"$in": step_ids}})
    await db.timeline_steps.delete_many({"project_id": project_id})
    await db.timelines.delete_many({"project_id": project_id})

    # Decision recipients linked to project decisions
    decisions = await db.decisions.find({"project_id": project_id}, {"_id": 0, "decision_id": 1}).to_list(5000)
    decision_ids = _collect_string_ids(decisions, "decision_id")
    if decision_ids:
        await db.decision_recipients.delete_many({"decision_id": {"$in": decision_ids}})

    # Remove project-scoped records
    await db.documents.delete_many({"project_id": project_id})
    if draft_doc_ids:
        await db.change_requests.delete_many({"entity_id": {"$in": draft_doc_ids}})
    await db.change_requests.delete_many({"project_id": project_id})
    await db.decisions.delete_many({"project_id": project_id})
    await db.team_members.delete_many({"project_id": project_id})
    await db.vault_documents.delete_many({"project_id": project_id})
    await db.clients.delete_many({"project_id": project_id})
    await db.units.delete_many({"project_id": project_id})

    result = await db.projects.delete_one({"project_id": project_id, "agent_id": agent_id})
    return {"deleted": result.deleted_count > 0, "impact": impact}


async def count_projects_by_agent(agent_id: str) -> int:
    return await db.projects.count_documents({"agent_id": agent_id})


async def list_projects_for_buyer(buyer_id: str) -> List[Dict[str, Any]]:
    """List projects accessible by a buyer via client linkage."""
    clients = await db.clients.find(
        {"buyer_id": buyer_id}, {"_id": 0, "project_id": 1}
    ).to_list(100)
    project_ids = list(set(c['project_id'] for c in clients if c.get('project_id')))
    if not project_ids:
        return []
    return await db.projects.find(
        {"project_id": {"$in": project_ids}}, {"_id": 0}
    ).to_list(100)


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
