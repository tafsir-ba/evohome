"""
Timeline Routes — Canonical Implementation

Thin route layer. No is_demo. No extraction.
Covers: timeline CRUD, step management, templates.
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from core.auth import get_current_user, get_current_agent
from core.access_control import can_access_project
from database import db
from services import timeline_service, step_service
from services.realtime_service import send_milestone_notification

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request schemas ──

class ManualTimelineCreate(BaseModel):
    project_id: str
    name: str = "Project Timeline"
    steps: List[dict]


class TimelineStepUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    planned_date: Optional[str] = None
    order_index: Optional[int] = None
    planned_start: Optional[str] = None
    planned_end: Optional[str] = None
    actual_start: Optional[str] = None
    progress_percent: Optional[int] = None
    notes: Optional[str] = None


class AddStepRequest(BaseModel):
    title: str = "New Step"
    description: Optional[str] = None
    planned_date: Optional[str] = None


class LinkDocumentRequest(BaseModel):
    activity_id: str


class AddNoteRequest(BaseModel):
    content: str


class TemplateStepCreate(BaseModel):
    title: str
    description: Optional[str] = None
    order_index: int


class TemplateCreate(BaseModel):
    name: str
    steps: List[TemplateStepCreate]


# ── Timeline CRUD ──

@router.post("/timeline/create")
async def create_manual_timeline(data: ManualTimelineCreate, user=Depends(get_current_agent)):
    """Create a timeline manually with custom steps."""
    if not await can_access_project(user, data.project_id):
        raise HTTPException(status_code=403, detail="Access denied to this project")

    existing = await timeline_service.get_timeline_by_project(data.project_id)
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Timeline already exists for this project. Delete the existing one first."
        )

    result = await timeline_service.create_timeline_with_steps(
        project_id=data.project_id,
        agent_id=user['user_id'],
        name=data.name,
        steps_data=data.steps,
    )
    return {"message": "Timeline created successfully", **result}


@router.get("/project-timeline")
async def get_project_timeline(project_id: Optional[str] = None, user=Depends(get_current_user)):
    """Get project construction timeline with enriched steps."""
    if user['role'] == 'buyer':
        client = await db.clients.find_one(
            {"buyer_id": user['user_id']}, {"_id": 0, "project_id": 1}
        )
        if not client:
            return {"timeline": None, "steps": []}
        project_id = client['project_id']
    elif not project_id:
        raise HTTPException(status_code=400, detail="project_id required for agents")

    if not await can_access_project(user, project_id):
        raise HTTPException(status_code=403, detail="Access denied")

    timeline = await timeline_service.get_enriched_timeline(project_id, user['role'])
    if not timeline:
        return {"timeline": None, "steps": []}

    return {"timeline": timeline, "steps": timeline.get('steps', [])}


@router.delete("/timeline/{timeline_id}")
async def delete_timeline(timeline_id: str, user=Depends(get_current_agent)):
    """Delete a timeline and all its steps, documents, notes."""
    timeline = await timeline_service.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    if not await can_access_project(user, timeline['project_id']):
        raise HTTPException(status_code=403, detail="Access denied")

    await timeline_service.delete_timeline_cascade(timeline_id)
    return {"message": "Timeline deleted"}


# ── Step management ──

@router.patch("/timeline/steps/{step_id}")
async def update_timeline_step(step_id: str, data: TimelineStepUpdateRequest, user=Depends(get_current_agent)):
    """Update a timeline step. Agent only."""
    step = await step_service.get_step(step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    if not await can_access_project(user, step['project_id']):
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        updates = data.model_dump(exclude_none=True)
        updated = await step_service.update_step(step_id, updates)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Send milestone notification when step is completed
    if updates.get('status') == 'completed':
        project = await db.projects.find_one(
            {"project_id": step['project_id']}, {"_id": 0}
        )
        timeline = await db.timelines.find_one(
            {"timeline_id": step.get('timeline_id')}, {"_id": 0}
        )
        if project and timeline:
            await send_milestone_notification(
                step=step, project=project, timeline=timeline,
                user=user
            )

    return updated


@router.post("/timeline/{timeline_id}/steps")
async def add_step_to_timeline(timeline_id: str, data: AddStepRequest, user=Depends(get_current_agent)):
    """Add a new step to an existing timeline."""
    timeline = await timeline_service.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    if not await can_access_project(user, timeline['project_id']):
        raise HTTPException(status_code=403, detail="Access denied")

    step = await step_service.add_step_to_timeline(
        timeline_id=timeline_id,
        project_id=timeline['project_id'],
        title=data.title,
        description=data.description,
        planned_date=data.planned_date,
    )
    return step


@router.delete("/timeline/steps/{step_id}")
async def delete_timeline_step(step_id: str, user=Depends(get_current_agent)):
    """Delete a timeline step."""
    step = await step_service.get_step(step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    if not await can_access_project(user, step['project_id']):
        raise HTTPException(status_code=403, detail="Access denied")

    await step_service.delete_step(step_id)
    return {"message": "Step deleted", "step_id": step_id}


# ── Step documents and notes ──

@router.post("/timeline/steps/{step_id}/documents")
async def link_document_to_step(step_id: str, data: LinkDocumentRequest, user=Depends(get_current_agent)):
    """Link an activity/document to a timeline step."""
    step = await step_service.get_step(step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    if not await can_access_project(user, step['project_id']):
        raise HTTPException(status_code=403, detail="Access denied")

    activity = await db.activities.find_one(
        {"activity_id": data.activity_id}, {"_id": 0}
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    link_id = await step_service.link_document(step_id, data.activity_id)
    if link_id is None:
        raise HTTPException(status_code=400, detail="Document already linked")

    return {"message": "Document linked", "link_id": link_id}


@router.delete("/timeline/steps/{step_id}/documents/{activity_id}")
async def unlink_document_from_step(step_id: str, activity_id: str, user=Depends(get_current_agent)):
    """Remove a document link from a timeline step."""
    step = await step_service.get_step(step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    if not await can_access_project(user, step['project_id']):
        raise HTTPException(status_code=403, detail="Access denied")

    deleted = await step_service.unlink_document(step_id, activity_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Link not found")

    return {"message": "Document unlinked"}


@router.post("/timeline/steps/{step_id}/notes")
async def add_internal_note(step_id: str, data: AddNoteRequest, user=Depends(get_current_agent)):
    """Add an internal note to a timeline step. Agent only."""
    step = await step_service.get_step(step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    if not await can_access_project(user, step['project_id']):
        raise HTTPException(status_code=403, detail="Access denied")

    note = await step_service.add_note(
        step_id=step_id,
        author_id=user['user_id'],
        author_name=user.get('name', 'Unknown'),
        content=data.content,
    )
    return note


# ── Template operations ──

@router.get("/timeline/templates")
async def list_templates(user=Depends(get_current_agent)):
    """List all timeline templates for the agent."""
    return await timeline_service.list_templates(user['user_id'])


@router.post("/timeline/templates")
async def create_template(data: TemplateCreate, user=Depends(get_current_agent)):
    """Create a new timeline template."""
    steps_data = [s.model_dump() for s in data.steps]
    return await timeline_service.create_template(user['user_id'], data.name, steps_data)


@router.delete("/timeline/templates/{template_id}")
async def delete_template(template_id: str, user=Depends(get_current_agent)):
    """Delete a timeline template."""
    deleted = await timeline_service.delete_template(template_id, user['user_id'])
    if not deleted:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"message": "Template deleted"}


@router.post("/timeline/templates/{template_id}/apply")
async def apply_template(template_id: str, project_id: str, user=Depends(get_current_agent)):
    """Apply a template to create a project timeline."""
    if not await can_access_project(user, project_id):
        raise HTTPException(status_code=403, detail="Access denied")

    result = await timeline_service.apply_template(template_id, project_id, user['user_id'])
    if result is None:
        raise HTTPException(
            status_code=400,
            detail="Template not found or project already has a timeline"
        )

    return {"message": "Timeline created", **result}
