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


def _collect_string_ids(rows: List[Dict[str, Any]], key: str) -> List[str]:
    """Collect non-empty string IDs from row dicts without raising KeyError."""
    ids: List[str] = []
    for row in rows:
        value = row.get(key)
        if isinstance(value, str) and value:
            ids.append(value)
    return ids


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


async def create_timeline_with_steps(
    project_id: str,
    agent_id: str,
    name: str,
    steps_data: List[dict],
) -> Dict[str, Any]:
    """Create a timeline with steps in one operation."""
    timeline = await create_timeline(project_id, agent_id, name)
    timeline_id = timeline['timeline_id']
    now = datetime.now(timezone.utc).isoformat()

    created_steps = []
    for i, sd in enumerate(steps_data):
        step_id = f"step_{uuid.uuid4().hex[:12]}"
        step = {
            "step_id": step_id,
            "timeline_id": timeline_id,
            "project_id": project_id,
            "title": sd.get('title', f'Step {i+1}'),
            "description": sd.get('description', ''),
            "planned_date": sd.get('planned_date'),
            "status": sd.get('status', 'pending'),
            "order_index": sd.get('order', i),
            "progress_percent": 0,
            "created_at": now,
        }
        await db.timeline_steps.insert_one(step)
        step.pop('_id', None)
        created_steps.append(step)

    return {"timeline": timeline, "steps": created_steps}


async def get_enriched_timeline(project_id: str, user_role: str) -> Optional[Dict[str, Any]]:
    """Get full timeline with enriched steps (documents, notes)."""
    timeline = await get_timeline_by_project(project_id)
    if not timeline:
        return None

    tl_id = timeline.get('timeline_id')
    if not tl_id:
        timeline['steps'] = []
        return timeline

    # Enrich with template name
    if timeline.get('template_id'):
        template = await db.timeline_templates.find_one(
            {"template_id": timeline['template_id']}, {"_id": 0, "name": 1}
        )
        timeline['template_name'] = template['name'] if template else None

    # Get steps
    steps = await db.timeline_steps.find(
        {"timeline_id": tl_id}, {"_id": 0}
    ).sort("order_index", 1).to_list(100)

    # Enrich steps
    for step in steps:
        step_id = step.get("step_id")
        if not isinstance(step_id, str) or not step_id:
            step['documents'] = []
            step['internal_notes'] = [] if user_role == 'agent' else []
            continue

        # Linked documents
        doc_links = await db.timeline_step_documents.find(
            {"timeline_step_id": step_id}, {"_id": 0}
        ).to_list(50)
        documents = []
        for link in doc_links:
            activity_id = link.get("activity_id")
            if not isinstance(activity_id, str) or not activity_id:
                continue
            activity = await db.activities.find_one(
                {"activity_id": activity_id},
                {"_id": 0, "activity_id": 1, "title": 1, "type": 1,
                 "file_name": 1, "file_url": 1, "created_at": 1}
            )
            if activity:
                documents.append(activity)
        step['documents'] = documents

        # Internal notes (agent only)
        if user_role == 'agent':
            notes = await db.timeline_step_internal_notes.find(
                {"timeline_step_id": step_id}, {"_id": 0}
            ).sort("created_at", -1).to_list(50)
            for note in notes:
                author_id = note.get("author_id")
                if not isinstance(author_id, str) or not author_id:
                    note['author_name'] = 'Unknown'
                    continue
                author = await db.users.find_one(
                    {"user_id": author_id}, {"_id": 0, "name": 1}
                )
                note['author_name'] = author['name'] if author else 'Unknown'
            step['internal_notes'] = notes
        else:
            step['internal_notes'] = []

    timeline['steps'] = steps
    return timeline


async def delete_timeline_cascade(timeline_id: str) -> bool:
    """Delete timeline and all associated steps, documents, notes."""
    steps = await db.timeline_steps.find(
        {"timeline_id": timeline_id}, {"step_id": 1}
    ).to_list(200)
    step_ids = _collect_string_ids(steps, "step_id")

    if step_ids:
        await db.timeline_step_documents.delete_many(
            {"timeline_step_id": {"$in": step_ids}}
        )
        await db.timeline_step_internal_notes.delete_many(
            {"timeline_step_id": {"$in": step_ids}}
        )

    await db.timeline_steps.delete_many({"timeline_id": timeline_id})
    result = await db.timelines.delete_one({"timeline_id": timeline_id})
    return result.deleted_count > 0


# ── Template operations ──

async def list_templates(agent_id: str) -> List[Dict[str, Any]]:
    """List templates for an agent (owned + global)."""
    templates = await db.timeline_templates.find(
        {"$or": [{"agent_id": agent_id}, {"is_global": True}]},
        {"_id": 0}
    ).to_list(100)
    for t in templates:
        t['steps'] = await db.timeline_template_steps.find(
            {"template_id": t['template_id']}, {"_id": 0}
        ).sort("order_index", 1).to_list(50)
    return templates


async def create_template(
    agent_id: str, name: str, steps_data: List[dict]
) -> Dict[str, Any]:
    """Create a timeline template with steps."""
    template_id = f"tmpl_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    template = {
        "template_id": template_id,
        "agent_id": agent_id,
        "name": name,
        "created_at": now,
    }
    await db.timeline_templates.insert_one(template)

    for sd in steps_data:
        step_doc = {
            "step_id": f"tmpl_step_{uuid.uuid4().hex[:12]}",
            "template_id": template_id,
            "title": sd.get('title', ''),
            "description": sd.get('description'),
            "order_index": sd.get('order_index', 0),
        }
        await db.timeline_template_steps.insert_one(step_doc)

    template.pop('_id', None)
    template['steps'] = await db.timeline_template_steps.find(
        {"template_id": template_id}, {"_id": 0}
    ).sort("order_index", 1).to_list(50)
    return template


async def delete_template(template_id: str, agent_id: str) -> bool:
    """Delete a template owned by the agent."""
    template = await db.timeline_templates.find_one(
        {"template_id": template_id, "agent_id": agent_id}
    )
    if not template:
        return False
    await db.timeline_template_steps.delete_many({"template_id": template_id})
    await db.timeline_templates.delete_one({"template_id": template_id})
    return True


async def apply_template(
    template_id: str, project_id: str, agent_id: str
) -> Optional[Dict[str, Any]]:
    """Apply a template to create a project timeline."""
    template = await db.timeline_templates.find_one(
        {"$or": [
            {"template_id": template_id, "agent_id": agent_id},
            {"template_id": template_id, "is_global": True},
        ]},
        {"_id": 0}
    )
    if not template:
        return None

    existing = await get_timeline_by_project(project_id)
    if existing:
        return None

    now = datetime.now(timezone.utc).isoformat()
    timeline_id = _make_timeline_id()

    timeline_doc = {
        "timeline_id": timeline_id,
        "project_id": project_id,
        "agent_id": agent_id,
        "template_id": template_id,
        "name": template.get('name', 'Timeline'),
        "created_at": now,
    }
    await db.timelines.insert_one(timeline_doc)

    template_steps = await db.timeline_template_steps.find(
        {"template_id": template_id}, {"_id": 0}
    ).sort("order_index", 1).to_list(50)

    for ts in template_steps:
        step_doc = {
            "step_id": f"step_{uuid.uuid4().hex[:12]}",
            "timeline_id": timeline_id,
            "project_id": project_id,
            "title": ts.get('title', ''),
            "description": ts.get('description'),
            "status": "pending",
            "order_index": ts.get('order_index', 0),
            "progress_percent": 0,
            "created_at": now,
        }
        await db.timeline_steps.insert_one(step_doc)

    timeline_doc.pop('_id', None)
    return {"timeline_id": timeline_id}
