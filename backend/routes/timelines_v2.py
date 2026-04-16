"""
Timeline Routes — Canonical Implementation

Thin route layer. No is_demo. No extraction.
Covers: timeline CRUD, step management, templates.
"""
import logging
from typing import Optional, List
import os
import json
import re
import uuid
import tempfile
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query
from pydantic import BaseModel, Field
import openai
import fitz

from core.auth import get_current_user, get_current_agent
from core.access_control import can_access_project, get_workspace_owner_id, get_accessible_project_ids
from database import db
from services import timeline_service, step_service
from services.realtime_service import send_milestone_notification
from services.ai_service import OPENAI_API_KEY

logger = logging.getLogger(__name__)
router = APIRouter()


SWISS_DEFAULT_PHASES = [
    {"name": "Planning & Permits", "description": "Finalize plans, permits, and execution schedule.", "planned_date": "Month 1-2"},
    {"name": "Site Preparation", "description": "Mobilization, setup, demolition and preparatory work.", "planned_date": "Month 2-3"},
    {"name": "Structural Works (Gros Oeuvre)", "description": "Foundations, slabs, load-bearing structure and masonry.", "planned_date": "Month 3-7"},
    {"name": "Building Envelope", "description": "Roofing, facade, windows and weatherproofing.", "planned_date": "Month 6-9"},
    {"name": "Technical Installations (CVCSE)", "description": "Heating, ventilation, plumbing and electrical systems.", "planned_date": "Month 8-11"},
    {"name": "Interior Finishes", "description": "Partitions, flooring, painting, joinery and fixtures.", "planned_date": "Month 10-13"},
    {"name": "Commissioning & Handover", "description": "Testing, inspections, punch list and final delivery.", "planned_date": "Month 13-14"},
]


def _normalize_phases(phases: List[dict]) -> List[dict]:
    cleaned = []
    for p in phases or []:
        name = str(p.get("name") or "").strip()
        if not name:
            continue
        cleaned.append({
            "name": name,
            "description": str(p.get("description") or "").strip(),
            "planned_date": str(p.get("planned_date") or "").strip(),
        })

    # enforce 6-7 key steps for MVP UX
    if len(cleaned) > 7:
        cleaned = cleaned[:7]
    if len(cleaned) < 6:
        existing = {c["name"].lower() for c in cleaned}
        for default in SWISS_DEFAULT_PHASES:
            if default["name"].lower() not in existing:
                cleaned.append(default)
            if len(cleaned) >= 7:
                break
    return cleaned[:7]


async def _extract_text_from_document(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        doc = fitz.open(path)
        try:
            parts = []
            for i in range(min(len(doc), 30)):
                parts.append(doc[i].get_text())
            return "\n".join(parts).strip()
        finally:
            doc.close()

    if ext in {".png", ".jpg", ".jpeg", ".webp"} and OPENAI_API_KEY:
        with open(path, "rb") as f:
            b64 = __import__("base64").b64encode(f.read()).decode("utf-8")
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }[ext]
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract all planning/timeline text from this construction document image."},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"}},
                ],
            }],
            max_tokens=1800,
        )
        return (response.choices[0].message.content or "").strip()

    if ext in {".xlsx", ".xls"}:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, data_only=True)
            lines = []
            for ws in wb.worksheets[:3]:
                for row in ws.iter_rows(max_row=300, values_only=True):
                    text = " | ".join([str(c) for c in row if c is not None]).strip()
                    if text:
                        lines.append(text)
            return "\n".join(lines)
        except Exception:
            return ""

    return ""


async def _extract_swiss_timeline_phases(text: str) -> dict:
    if not OPENAI_API_KEY:
        return {
            "phases": SWISS_DEFAULT_PHASES[:7],
            "project_duration": "Approx. 12-18 months",
            "confidence": "low",
            "notes": "AI key not configured, using Swiss default phase model.",
        }

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    prompt = """You are a Swiss construction planning assistant.
Given the document text, produce a simplified timeline with exactly 6 or 7 key phases aligned with common Swiss construction norms.

Rules:
- Output exactly 6 or 7 phases.
- Keep each phase concise and business-friendly.
- Include rough date labels as text (e.g. "Q2 2026", "Month 1-2", "Spring 2027") if available.
- If dates are missing, infer realistic relative periods.
- Use French/English neutral professional naming suitable for Swiss real-estate clients.

Return ONLY JSON:
{
  "phases": [{"name":"", "description":"", "planned_date":""}],
  "project_duration":"string",
  "confidence":"high|medium|low",
  "notes":"string"
}
"""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text[:12000] or "No text extracted; return a Swiss-standard 6-7 phase plan."},
        ],
        max_tokens=1400,
    )
    raw = response.choices[0].message.content or ""
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        raise ValueError("AI did not return JSON")
    parsed = json.loads(match.group())
    parsed["phases"] = _normalize_phases(parsed.get("phases", []))
    if len(parsed["phases"]) < 6:
        parsed["phases"] = SWISS_DEFAULT_PHASES[:7]
        parsed["confidence"] = "low"
    return parsed


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


@router.post("/timeline/extract")
async def extract_timeline_from_document(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    user=Depends(get_current_agent),
):
    """Extract simplified 6-7 phase timeline from document."""
    if not await can_access_project(user, project_id):
        raise HTTPException(status_code=403, detail="Access denied to this project")
    scope_agent_id = get_workspace_owner_id(user)

    ext = os.path.splitext(file.filename or "")[1].lower()
    allowed = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".xlsx", ".xls"}
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF, image, or Excel.")

    temp_path = ""
    try:
        content = await file.read()
        fd, temp_path = tempfile.mkstemp(prefix="timeline_extract_", suffix=ext)
        os.close(fd)
        with open(temp_path, "wb") as f:
            f.write(content)

        extracted_text = await _extract_text_from_document(temp_path)
        timeline_data = await _extract_swiss_timeline_phases(extracted_text)
        phases = _normalize_phases(timeline_data.get("phases", []))

        extraction_id = f"tlx_{uuid.uuid4().hex[:12]}"
        extraction_doc = {
            "extraction_id": extraction_id,
            "agent_id": scope_agent_id,
            "project_id": project_id,
            "source_filename": file.filename,
            "status": "pending_review",
            "extracted_data": {
                "phases": phases,
                "project_duration": timeline_data.get("project_duration"),
                "confidence": timeline_data.get("confidence", "low"),
                "notes": timeline_data.get("notes", ""),
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.timeline_extractions.insert_one(extraction_doc)
        extraction_doc.pop("_id", None)
        return extraction_doc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Timeline extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


@router.get("/timeline/extractions")
async def list_timeline_extractions(
    status: Optional[str] = Query(None),
    user=Depends(get_current_agent),
):
    query = {"agent_id": get_workspace_owner_id(user)}
    accessible_project_ids = await get_accessible_project_ids(user)
    if not accessible_project_ids:
        return []
    query["project_id"] = {"$in": accessible_project_ids}
    if status:
        query["status"] = status
    rows = await db.timeline_extractions.find(query, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    return rows


@router.get("/timeline/extractions/{extraction_id}")
async def get_timeline_extraction(extraction_id: str, user=Depends(get_current_agent)):
    row = await db.timeline_extractions.find_one(
        {"extraction_id": extraction_id, "agent_id": get_workspace_owner_id(user)},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Extraction not found")
    if not await can_access_project(user, row.get("project_id")):
        raise HTTPException(status_code=403, detail="Access denied")
    return row


@router.post("/timeline/extractions/{extraction_id}/approve")
async def approve_timeline_extraction(
    extraction_id: str,
    project_id: str = Form(...),
    phases: str = Form(...),
    user=Depends(get_current_agent),
):
    """Approve extracted timeline and create project timeline steps."""
    if not await can_access_project(user, project_id):
        raise HTTPException(status_code=403, detail="Access denied to this project")

    row = await db.timeline_extractions.find_one(
        {"extraction_id": extraction_id, "agent_id": get_workspace_owner_id(user)},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Extraction not found")
    if not await can_access_project(user, row.get("project_id")):
        raise HTTPException(status_code=403, detail="Access denied")
    if row.get("project_id") and row.get("project_id") != project_id:
        raise HTTPException(status_code=400, detail="Extraction does not belong to the selected project")

    existing = await timeline_service.get_timeline_by_project(project_id)
    if existing:
        raise HTTPException(status_code=400, detail="Project already has a timeline. Delete it before approving a new extraction.")

    try:
        phase_rows = json.loads(phases)
        normalized = _normalize_phases(phase_rows)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid phases payload")

    steps_data = [
        {
            "title": p.get("name") or f"Step {i+1}",
            "description": p.get("description", ""),
            "planned_date": p.get("planned_date", ""),
            "order": i + 1,
            "status": "pending",
        }
        for i, p in enumerate(normalized)
    ]
    created = await timeline_service.create_timeline_with_steps(
        project_id=project_id,
        agent_id=get_workspace_owner_id(user),
        name="Project Timeline",
        steps_data=steps_data,
    )
    await db.timeline_extractions.update_one(
        {"extraction_id": extraction_id},
        {
            "$set": {
                "status": "approved",
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "approved_timeline_id": created["timeline"]["timeline_id"],
                "approved_phases": normalized,
            }
        },
    )
    return {
        "message": "Timeline approved and created",
        "extraction_id": extraction_id,
        "timeline_id": created["timeline"]["timeline_id"],
        "steps_count": len(created["steps"]),
    }


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
