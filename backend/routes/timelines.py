"""Auto-extracted route module from server.py — Phase 3 modularization."""
import os
import re
import json
import uuid
import base64
import logging
import secrets
import tempfile
import openai
import fitz
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Literal, Dict, Any
from io import BytesIO

from fastapi import APIRouter, HTTPException, Depends, Request, Response, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field, EmailStr

from database import db
from core.auth import get_current_user, get_current_agent, get_current_buyer, verify_token
from core.access_control import can_access_project, can_access_client, can_access_vault_doc, can_access_document, get_accessible_project_ids, get_accessible_client_ids, is_agent, is_buyer, get_is_demo
from core.rate_limit import rate_limit_check, check_rate_limit
from core.monitoring import capture_exception, capture_auth_failure, capture_payment_error, capture_email_error, capture_ai_error, capture_websocket_error, capture_document_error, ErrorContext
from core.responses import AuthSessionResponse, AuthLoginResponse, AuthRefreshResponse, AuthLogoutResponse, DocumentResponse, VaultDocumentResponse, NotificationResponse, ActivityResponse, ActivitiesListResponse, SuccessResponse

from helpers import get_demo_filter, build_query, secure_filename, VALID_TRANSITIONS, validate_transition, SUBSCRIPTION_PLANS, VAULT_CATEGORIES, VAULT_DOC_TYPES
from services.email_service import send_email_async, send_notification_email, create_notification, get_email_template
from services.realtime_service import ws_manager, notify_realtime, send_milestone_notification
from services.qr_service import generate_swiss_qr_code, generate_swiss_qr_code_base64, DEFAULT_IBAN, DEFAULT_COMPANY_NAME
from services.ai_service import extract_document_from_pdf, OPENAI_API_KEY

from models.schemas import *

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter()

# ==================== TIMELINE MANAGEMENT, TEMPLATES, EXTRACTION ====================

# ==================== TIMELINE/WORKFLOW ENDPOINTS ====================

# Valid status transitions
TIMELINE_STATUS_TRANSITIONS = {
    "pending": ["in_progress", "completed", "approved"],  # Can skip ahead
    "in_progress": ["pending", "completed", "approved"],  # Can go back or skip ahead
    "completed": ["pending", "in_progress", "approved"],  # Can go back or forward
    "approved": ["pending", "in_progress", "completed"]  # Can reopen if needed
}

# ==================== AI TIMELINE EXTRACTION ====================

async def extract_timeline_from_file(file_path: str, filename: str, mime_type: str) -> dict:
    """Extract timeline/phases from a planning document using AI (OpenAI)"""
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set, returning fallback")
        return {
            "phases": [],
            "project_duration": None,
            "notes": "AI extraction unavailable - please enter timeline manually",
            "confidence": "low",
            "extraction_failed": True
        }
    
    try:
        # Initialize OpenAI client
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        system_prompt = """You are a construction project timeline extraction assistant.

Your task is to analyze planning documents (PDFs, spreadsheets, images) and extract a structured project timeline.

EXTRACTION RULES:

1. PHASES/MILESTONES:
   - Extract distinct project phases or milestones
   - Each phase should have a name and brief description
   - Order phases chronologically
   - Look for: preparation, demolition, construction, installation, finishing, inspection, handover

2. DATES - PRESERVE EXACT WORDING:
   - Copy the date text EXACTLY as written in the document
   - Examples: "March 2026", "Q4 2027", "3 Mar 2026", "Mid-February", "Week 12"
   - Do NOT convert or calculate dates
   - Do NOT use YYYY-MM-DD format unless that's what the document says
   - If no date found, use null

3. KEY DELIVERABLES:
   - What is expected to be completed at each phase

Return ONLY a JSON object with this structure:
{
  "phases": [
    {
      "name": "Phase name",
      "order": 1,
      "planned_date": "exact date text from document or null",
      "description": "Brief description of work in this phase",
      "deliverables": ["key deliverable 1", "key deliverable 2"]
    }
  ],
  "notes": "any important notes about the timeline",
  "confidence": "high/medium/low"
}"""
        
        # Convert file to images for OpenAI vision
        import base64
        image_contents = []
        
        # Check if it's a PDF
        if mime_type == "application/pdf" or file_path.lower().endswith('.pdf'):
            # Convert PDF to images using PyMuPDF
            doc = fitz.open(file_path)
            for page_num in range(min(3, len(doc))):
                page = doc[page_num]
                mat = fitz.Matrix(150/72, 150/72)
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes("png")
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                image_contents.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img_base64}"}
                })
            doc.close()
        else:
            # For images, use directly
            with open(file_path, "rb") as f:
                file_base64 = base64.b64encode(f.read()).decode('utf-8')
            # Map common mime types
            img_mime = mime_type if mime_type in ['image/png', 'image/jpeg', 'image/gif', 'image/webp'] else 'image/png'
            image_contents.append({
                "type": "image_url",
                "image_url": {"url": f"data:{img_mime};base64,{file_base64}"}
            })
        
        # Build message
        message_content = [
            {"type": "text", "text": "Extract the project timeline/phases from this planning document. Identify all phases, milestones, and their durations or dates. Return only valid JSON."}
        ] + image_contents
        
        # Use GPT-4o with vision for document analysis
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message_content}
            ],
            max_tokens=2000
        )
        
        response_text = response.choices[0].message.content
        
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            extracted = json.loads(json_match.group())
        else:
            raise ValueError("No JSON found in response")
        
        # Validate and clean phases - use text-based planned_date
        valid_phases = []
        for idx, phase in enumerate(extracted.get("phases", [])):
            if isinstance(phase, dict) and phase.get("name"):
                valid_phases.append({
                    "name": str(phase.get("name", "")),
                    "order": phase.get("order", idx + 1),
                    "planned_date": phase.get("planned_date") or "",  # Text-based date
                    "description": str(phase.get("description", "")),
                    "deliverables": phase.get("deliverables", [])
                })
        
        return {
            "phases": valid_phases,
            "notes": extracted.get("notes", ""),
            "confidence": extracted.get("confidence", "medium"),
            "extraction_failed": False
        }
        
    except Exception as e:
        logger.error(f"Timeline extraction failed: {str(e)}")
        return {
            "phases": [],
            "notes": f"Extraction error: {str(e)}",
            "confidence": "low",
            "extraction_failed": True
        }

class ManualTimelineCreate(BaseModel):
    project_id: str
    name: str = "Project Timeline"
    steps: List[dict]

@router.post("/timeline/create")
async def create_manual_timeline(data: ManualTimelineCreate, user: dict = Depends(get_current_agent)):
    """Create a timeline manually with custom steps"""
    is_demo = user.get('is_demo', False)
    
    # Verify project access
    project = await db.projects.find_one({
        "project_id": data.project_id,
        "agent_id": user['user_id'],
        "is_demo": is_demo
    }, {"_id": 0})
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if timeline already exists (via compat layer)
    existing = await db.timelines.find_one({
        "project_id": data.project_id,
        "is_demo": is_demo
    }, {"_id": 0})
    
    if existing:
        raise HTTPException(status_code=400, detail="Timeline already exists for this project. Delete the existing one first.")
    
    now = datetime.now(timezone.utc).isoformat()
    timeline_id = str(uuid.uuid4())
    
    # Create timeline (writes to canonical collection only)
    timeline = {
        "timeline_id": timeline_id,
        "project_id": data.project_id,
        "agent_id": user['user_id'],
        "name": data.name,
        "status": "published",
        "is_demo": is_demo,
        "created_at": now,
        "updated_at": now
    }
    await db.timelines.insert_one(timeline)
    
    # Create steps
    created_steps = []
    for i, step_data in enumerate(data.steps):
        step = {
            "step_id": str(uuid.uuid4()),
            "timeline_id": timeline_id,
            "title": step_data.get('title', f'Step {i+1}'),
            "description": step_data.get('description', ''),
            "planned_date": step_data.get('planned_date'),
            "status": step_data.get('status', 'pending'),
            "order": step_data.get('order', i + 1),
            "is_demo": is_demo,
            "created_at": now
        }
        await db.timeline_steps.insert_one(step)
        created_steps.append({k: v for k, v in step.items() if k != '_id'})
    
    return {
        "message": "Timeline created successfully",
        "timeline": {k: v for k, v in timeline.items() if k != '_id'},
        "steps": created_steps
    }

@router.post("/timeline/extract")
async def extract_timeline(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    user: dict = Depends(get_current_agent)
):
    """Upload a planning document and extract timeline using AI"""
    is_demo = user.get('is_demo', False)
    
    # Validate file type
    allowed_types = [
        'application/pdf',
        'image/jpeg', 'image/jpg', 'image/png', 'image/webp',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # xlsx
        'application/vnd.ms-excel',  # xls
    ]
    
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Unsupported file type. Allowed: PDF, images, Excel files")
    
    # Read and save file temporarily
    content = await file.read()
    
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File must be less than 20MB")
    
    extraction_id = f"timeline_ext_{uuid.uuid4().hex[:12]}"
    file_ext = file.filename.split('.')[-1] if '.' in file.filename else 'bin'
    temp_filename = f"{extraction_id}.{file_ext}"
    temp_path = UPLOAD_DIR / temp_filename
    
    try:
        with open(temp_path, "wb") as f:
            f.write(content)
        
        # Extract timeline using AI
        result = await extract_timeline_from_file(str(temp_path), file.filename, file.content_type)
        
        # Store the extraction result for later approval
        extraction_doc = {
            "extraction_id": extraction_id,
            "agent_id": user['user_id'],
            "project_id": project_id,
            "original_filename": file.filename,
            "file_path": str(temp_path),
            "extracted_data": result,
            "status": "pending_review",  # pending_review, approved, rejected
            "is_demo": is_demo,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.timeline_extractions.insert_one(extraction_doc)
        extraction_doc.pop('_id', None)
        
        return {
            "extraction_id": extraction_id,
            "status": "pending_review",
            "extracted_data": result
        }
        
    except Exception as e:
        # Clean up temp file on error
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(status_code=500, detail=f"Timeline extraction failed: {str(e)}")

@router.get("/timeline/extractions")
async def get_timeline_extractions(
    status: Optional[str] = None,
    project_id: Optional[str] = None,
    user: dict = Depends(get_current_agent)
):
    """Get all timeline extractions for the agent"""
    is_demo = user.get('is_demo', False)
    
    query = {"agent_id": user['user_id']}
    if status:
        query["status"] = status
    if project_id:
        query["project_id"] = project_id
    
    extractions = await db.timeline_extractions.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
    return extractions

@router.get("/timeline/extractions/{extraction_id}")
async def get_timeline_extraction(extraction_id: str, user: dict = Depends(get_current_agent)):
    """Get a specific timeline extraction"""
    is_demo = user.get('is_demo', False)
    
    extraction = await db.timeline_extractions.find_one(
        {"extraction_id": extraction_id, "agent_id": user['user_id']},
        {"_id": 0}
    )
    
    if not extraction:
        raise HTTPException(status_code=404, detail="Extraction not found")
    
    return extraction

@router.post("/timeline/extractions/{extraction_id}/approve")
async def approve_timeline_extraction(
    extraction_id: str,
    project_id: str = Form(...),
    phases: str = Form(...),  # JSON string of edited phases
    user: dict = Depends(get_current_agent)
):
    """Approve an extracted timeline and apply it to a project"""
    is_demo = user.get('is_demo', False)
    
    extraction = await db.timeline_extractions.find_one(
        {"extraction_id": extraction_id, "agent_id": user['user_id']}
    )
    
    if not extraction:
        raise HTTPException(status_code=404, detail="Extraction not found")
    
    # Validate project exists
    project = await db.projects.find_one(
        {"project_id": project_id, "agent_id": user['user_id']}
    )
    
    if not project:
        raise HTTPException(status_code=400, detail="Invalid project")
    
    # Parse phases
    try:
        phases_list = json.loads(phases)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid phases format")
    
    # Create a timeline template from the approved extraction
    template_id = f"template_{uuid.uuid4().hex[:12]}"
    template_doc = {
        "template_id": template_id,
        "agent_id": user['user_id'],
        "name": f"Extracted Timeline - {extraction.get('original_filename', 'Unknown')}",
        "is_demo": is_demo,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "ai_extraction",
        "extraction_id": extraction_id
    }
    
    await db.timeline_templates.insert_one(template_doc)
    
    # Create steps from phases
    for idx, phase in enumerate(phases_list):
        step_id = f"step_{uuid.uuid4().hex[:8]}"
        step_doc = {
            "step_id": step_id,
            "template_id": template_id,
            "name": phase.get("name", f"Phase {idx + 1}"),
            "description": phase.get("description", ""),
            "order_index": idx,
            "planned_date": phase.get("planned_date", ""),  # Text-based date
            "deliverables": phase.get("deliverables", []),
            "is_demo": is_demo
        }
        await db.timeline_template_steps.insert_one(step_doc)
    
    # Apply template to project (via compat layer)
    timeline_id = f"ptl_{uuid.uuid4().hex[:12]}"
    project_timeline_doc = {
        "timeline_id": timeline_id,
        "project_id": project_id,
        "agent_id": user['user_id'],
        "template_id": template_id,
        "name": template_doc['name'],
        "status": "active",
        "is_demo": is_demo,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.timelines.insert_one(project_timeline_doc)
    
    # Create timeline steps - use db.timeline_steps to match what get_project_timeline reads
    for idx, phase in enumerate(phases_list):
        step_id = f"pts_{uuid.uuid4().hex[:8]}"
        step_doc = {
            "step_id": step_id,
            "timeline_id": timeline_id,
            "project_id": project_id,
            "agent_id": user['user_id'],
            "title": phase.get("name", f"Phase {idx + 1}"),  # 'title' matches existing schema
            "description": phase.get("description", ""),
            "order_index": idx,
            "status": "pending",
            "planned_date": phase.get("planned_date", ""),  # Text-based date
            "is_demo": is_demo,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.timeline_steps.insert_one(step_doc)  # Use timeline_steps collection
    
    # Update extraction status
    await db.timeline_extractions.update_one(
        {"extraction_id": extraction_id},
        {"$set": {
            "status": "approved",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "applied_to_project": project_id,
            "template_id": template_id
        }}
    )
    
    # Clean up temp file
    if extraction.get('file_path') and Path(extraction['file_path']).exists():
        try:
            Path(extraction['file_path']).unlink()
        except OSError:
            pass
    
    return {
        "message": "Timeline approved and applied to project",
        "template_id": template_id,
        "timeline_id": timeline_id,
        "phases_count": len(phases_list)
    }

@router.delete("/timeline/extractions/{extraction_id}")
async def delete_timeline_extraction(extraction_id: str, user: dict = Depends(get_current_agent)):
    """Delete a pending timeline extraction"""
    is_demo = user.get('is_demo', False)
    
    extraction = await db.timeline_extractions.find_one(
        {"extraction_id": extraction_id, "agent_id": user['user_id']}
    )
    
    if not extraction:
        raise HTTPException(status_code=404, detail="Extraction not found")
    
    # Clean up temp file
    if extraction.get('file_path') and Path(extraction['file_path']).exists():
        try:
            Path(extraction['file_path']).unlink()
        except OSError:
            pass
    
    await db.timeline_extractions.delete_one({"extraction_id": extraction_id})
    
    return {"message": "Extraction deleted"}

@router.get("/timeline/templates")
async def get_timeline_templates(user: dict = Depends(get_current_agent)):
    """Get all timeline templates for agent"""
    is_demo = user.get('is_demo', False)
    
    templates = await db.timeline_templates.find(
        {"$or": [{"agent_id": user['user_id']}, {"is_demo": is_demo}]},
        {"_id": 0}
    ).to_list(100)
    
    # Enrich with steps
    for template in templates:
        steps = await db.timeline_template_steps.find(
            {"template_id": template['template_id']},
            {"_id": 0}
        ).sort("order_index", 1).to_list(50)
        template['steps'] = steps
    
    return templates

@router.post("/timeline/templates")
async def create_timeline_template(data: TimelineTemplateCreate, user: dict = Depends(get_current_agent)):
    """Create a new timeline template"""
    is_demo = user.get('is_demo', False)
    template_id = f"tmpl_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    
    template_doc = {
        "template_id": template_id,
        "agent_id": user['user_id'],
        "name": data.name,
        "is_demo": is_demo,
        "created_at": now
    }
    await db.timeline_templates.insert_one(template_doc)
    
    # Create template steps
    for step in data.steps:
        step_id = f"tmpl_step_{uuid.uuid4().hex[:12]}"
        step_doc = {
            "step_id": step_id,
            "template_id": template_id,
            "title": step.title,
            "description": step.description,
            "order_index": step.order_index
        }
        await db.timeline_template_steps.insert_one(step_doc)
    
    # Return with steps
    template_doc.pop('_id', None)
    steps = await db.timeline_template_steps.find(
        {"template_id": template_id},
        {"_id": 0}
    ).sort("order_index", 1).to_list(50)
    template_doc['steps'] = steps
    
    return template_doc

@router.delete("/timeline/templates/{template_id}")
async def delete_timeline_template(template_id: str, user: dict = Depends(get_current_agent)):
    """Delete a timeline template"""
    is_demo = user.get('is_demo', False)
    
    template = await db.timeline_templates.find_one({
        "template_id": template_id,
        "agent_id": user['user_id'],
        "is_demo": is_demo
    })
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    await db.timeline_template_steps.delete_many({"template_id": template_id})
    await db.timeline_templates.delete_one({"template_id": template_id})
    
    return {"message": "Template deleted"}

@router.post("/timeline/templates/{template_id}/apply")
async def apply_timeline_template(template_id: str, project_id: str, user: dict = Depends(get_current_agent)):
    """Apply a template to create project timeline"""
    is_demo = user.get('is_demo', False)
    
    # Verify template exists
    template = await db.timeline_templates.find_one({
        "template_id": template_id,
        "is_demo": is_demo
    }, {"_id": 0})
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Verify project exists and agent owns it
    project = await db.projects.find_one({
        "project_id": project_id,
        "agent_id": user['user_id'],
        "is_demo": is_demo
    }, {"_id": 0})
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if project already has a timeline (via compat layer)
    existing = await db.timelines.find_one({
        "project_id": project_id,
        "is_demo": is_demo
    }, {"_id": 0})
    
    if existing:
        raise HTTPException(status_code=400, detail="Project already has a timeline. Delete it first.")
    
    now = datetime.now(timezone.utc).isoformat()
    timeline_id = f"timeline_{uuid.uuid4().hex[:12]}"
    
    # Create project timeline (writes to canonical collection)
    timeline_doc = {
        "timeline_id": timeline_id,
        "project_id": project_id,
        "template_id": template_id,
        "is_demo": is_demo,
        "created_at": now
    }
    await db.timelines.insert_one(timeline_doc)
    
    # Get template steps and create timeline steps
    template_steps = await db.timeline_template_steps.find(
        {"template_id": template_id},
        {"_id": 0}
    ).sort("order_index", 1).to_list(50)
    
    for tmpl_step in template_steps:
        step_id = f"step_{uuid.uuid4().hex[:12]}"
        step_doc = {
            "step_id": step_id,
            "timeline_id": timeline_id,
            "title": tmpl_step['title'],
            "description": tmpl_step.get('description'),
            "status": "pending",
            "order_index": tmpl_step['order_index'],
            "planned_date": None,
            "completed_at": None,
            "is_demo": is_demo,
            "created_at": now,
            "updated_at": now
        }
        await db.timeline_steps.insert_one(step_doc)
    
    return {"message": "Timeline created", "timeline_id": timeline_id}

@router.get("/project-timeline")
async def get_project_timeline(
    project_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """
    Get project construction timeline (workflow stages).
    - Agent: can query any project they own via project_id
    - Buyer: gets timeline for their project automatically
    """
    is_demo = user.get('is_demo', False)
    
    if user['role'] == 'buyer':
        # Get buyer's project
        client = await db.clients.find_one(
            {"buyer_id": user['user_id']},
            {"_id": 0}
        )
        if not client:
            return {"timeline": None, "steps": []}
        project_id = client['project_id']
    else:
        if not project_id:
            raise HTTPException(status_code=400, detail="project_id required for agents")
        
        # Verify agent owns project
        project = await db.projects.find_one({
            "project_id": project_id,
            "agent_id": user['user_id'],
            "is_demo": is_demo
        })
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
    
    # Get project timeline (via compat layer)
    timeline = await db.timelines.find_one(
        {"project_id": project_id}, {"_id": 0}
    )
    
    if not timeline:
        return {"timeline": None, "steps": []}
    
    # Handle missing timeline_id (legacy data) - normalized by compat layer
    tl_id = timeline.get('timeline_id')
    if not tl_id:
        return {"timeline": timeline, "steps": []}
    
    # Enrich with template name
    if timeline.get('template_id'):
        template = await db.timeline_templates.find_one(
            {"template_id": timeline['template_id']},
            {"_id": 0, "name": 1}
        )
        timeline['template_name'] = template['name'] if template else None
    
    # Get steps with documents and notes
    steps = await db.timeline_steps.find(
        {"timeline_id": tl_id},
        {"_id": 0}
    ).sort("order_index", 1).to_list(100)
    
    # Enrich steps with linked documents and notes
    for step in steps:
        # Get linked documents (activities)
        doc_links = await db.timeline_step_documents.find(
            {"timeline_step_id": step['step_id']},
            {"_id": 0}
        ).to_list(50)
        
        documents = []
        for link in doc_links:
            activity = await db.activities.find_one(
                {"activity_id": link['activity_id']},
                {"_id": 0, "activity_id": 1, "title": 1, "type": 1, "file_name": 1, "file_url": 1, "created_at": 1}
            )
            if activity:
                documents.append(activity)
        step['documents'] = documents
        
        # Get internal notes (agent only)
        if user['role'] == 'agent':
            notes = await db.timeline_step_internal_notes.find(
                {"timeline_step_id": step['step_id']},
                {"_id": 0}
            ).sort("created_at", -1).to_list(50)
            
            # Enrich with author names
            for note in notes:
                author = await db.users.find_one(
                    {"user_id": note['author_id']},
                    {"_id": 0, "name": 1}
                )
                note['author_name'] = author['name'] if author else 'Unknown'
            step['internal_notes'] = notes
        else:
            step['internal_notes'] = []  # Buyer doesn't see notes
    
    timeline['steps'] = steps
    return {"timeline": timeline, "steps": steps}

@router.patch("/timeline/steps/{step_id}")
async def update_timeline_step(step_id: str, data: TimelineStepUpdate, user: dict = Depends(get_current_agent)):
    """Update a timeline step (agent only)"""
    is_demo = user.get('is_demo', False)
    
    # Find step and verify ownership
    step = await db.timeline_steps.find_one(
        {"step_id": step_id},
        {"_id": 0}
    )
    
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    
    # Verify agent owns the project via timeline (via compat layer)
    step_tl_ref = step.get('timeline_id', '')
    timeline = await db.timelines.find_one({
        "timeline_id": step_tl_ref,
        "is_demo": is_demo
    }, {"_id": 0})
    
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")
    
    project = await db.projects.find_one(
        {"project_id": timeline['project_id'], "agent_id": user['user_id']}
    )
    
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")
    
    update_data = {}
    now = datetime.now(timezone.utc).isoformat()
    
    if data.title is not None:
        update_data['title'] = data.title
    if data.description is not None:
        update_data['description'] = data.description
    if data.planned_date is not None:
        update_data['planned_date'] = data.planned_date
    if data.order_index is not None:
        update_data['order_index'] = data.order_index
    # Extended fields (from project_stages migration)
    if data.planned_start is not None:
        update_data['planned_start'] = data.planned_start
    if data.planned_end is not None:
        update_data['planned_end'] = data.planned_end
    if data.actual_start is not None:
        update_data['actual_start'] = data.actual_start
    if data.progress_percent is not None:
        update_data['progress_percent'] = data.progress_percent
    if data.notes is not None:
        update_data['notes'] = data.notes
    
    # Handle status transition
    if data.status is not None:
        current_status = step['status']
        new_status = data.status
        
        if new_status != current_status:
            allowed = TIMELINE_STATUS_TRANSITIONS.get(current_status, [])
            if new_status not in allowed:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status transition from '{current_status}' to '{new_status}'"
                )
            
            update_data['status'] = new_status
            
            # Set completed_at when transitioning to completed
            if new_status == 'completed':
                update_data['completed_at'] = now
            elif new_status in ['pending', 'in_progress']:
                update_data['completed_at'] = None
    
    if update_data:
        update_data['updated_at'] = now
        await db.timeline_steps.update_one(
            {"step_id": step_id},
            {"$set": update_data}
        )
        
        # Send milestone notification when status changes to completed
        if update_data.get('status') == 'completed':
            await send_milestone_notification(
                step=step,
                project=project,
                timeline=timeline,
                user=user,
                is_demo=is_demo
            )
    
    updated = await db.timeline_steps.find_one({"step_id": step_id}, {"_id": 0})
    return updated

@router.post("/timeline/{timeline_id}/steps")
async def add_timeline_step(timeline_id: str, data: dict, user: dict = Depends(get_current_agent)):
    """Add a new step to an existing timeline"""
    is_demo = user.get('is_demo', False)
    
    # Find timeline (canonical lookup)
    timeline = await db.timelines.find_one({
        "timeline_id": timeline_id,
        "is_demo": is_demo
    }, {"_id": 0})
    
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")
    
    # Verify agent owns the project
    project = await db.projects.find_one(
        {"project_id": timeline['project_id'], "agent_id": user['user_id']}
    )
    
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get current max order_index
    tl_id = timeline.get('timeline_id')
    pipeline = [
        {"$match": {"timeline_id": tl_id}},
        {"$group": {"_id": None, "max_order": {"$max": "$order_index"}}}
    ]
    result = await db.timeline_steps.aggregate(pipeline).to_list(1)
    max_order = result[0]['max_order'] if result and result[0].get('max_order') is not None else 0
    
    now = datetime.now(timezone.utc).isoformat()
    
    step_doc = {
        "step_id": f"step_{uuid.uuid4().hex[:12]}",
        "timeline_id": tl_id,
        "project_id": timeline['project_id'],
        "title": data.get('title', 'New Step'),
        "description": data.get('description', ''),
        "planned_date": data.get('planned_date'),
        "status": "pending",
        "order_index": max_order + 1,
        "documents": [],
        "internal_notes": [],
        "is_demo": is_demo,
        "created_at": now,
        "updated_at": now,
        "completed_at": None
    }
    
    await db.timeline_steps.insert_one(step_doc)
    result = await db.timeline_steps.find_one({"step_id": step_doc['step_id']}, {"_id": 0})
    return result

@router.delete("/timeline/steps/{step_id}")
async def delete_timeline_step(step_id: str, user: dict = Depends(get_current_agent)):
    """Delete a timeline step"""
    is_demo = user.get('is_demo', False)
    
    # Find step
    step = await db.timeline_steps.find_one(
        {"step_id": step_id},
        {"_id": 0}
    )
    
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    
    # Verify agent owns the project via timeline (via compat layer)
    step_tl_ref = step.get('timeline_id', '')
    timeline = await db.timelines.find_one({
        "timeline_id": step_tl_ref,
        "is_demo": is_demo
    }, {"_id": 0})
    
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")
    
    project = await db.projects.find_one(
        {"project_id": timeline['project_id'], "agent_id": user['user_id']}
    )
    
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Delete the step
    await db.timeline_steps.delete_one({"step_id": step_id})
    
    return {"message": "Step deleted", "step_id": step_id}

@router.post("/timeline/steps/{step_id}/documents")
async def link_document_to_step(step_id: str, data: TimelineStepDocumentCreate, user: dict = Depends(get_current_agent)):
    """Link an existing activity to a timeline step"""
    is_demo = user.get('is_demo', False)
    
    # Verify step exists and agent has access
    step = await db.timeline_steps.find_one(
        {"step_id": step_id},
        {"_id": 0}
    )
    
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    
    # Verify agent owns the project (via compat layer)
    step_tl_ref = step.get('timeline_id', '')
    timeline = await db.timelines.find_one(
        {"timeline_id": step_tl_ref}, {"_id": 0}
    )
    
    project = await db.projects.find_one(
        {"project_id": timeline['project_id'], "agent_id": user['user_id']}
    )
    
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Verify activity exists
    activity = await db.activities.find_one(
        {"activity_id": data.activity_id},
        {"_id": 0}
    )
    
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    # Check if already linked
    existing = await db.timeline_step_documents.find_one({
        "timeline_step_id": step_id,
        "activity_id": data.activity_id
    })
    
    if existing:
        raise HTTPException(status_code=400, detail="Document already linked")
    
    now = datetime.now(timezone.utc).isoformat()
    link_id = f"link_{uuid.uuid4().hex[:12]}"
    
    link_doc = {
        "link_id": link_id,
        "timeline_step_id": step_id,
        "activity_id": data.activity_id,
        "created_at": now
    }
    await db.timeline_step_documents.insert_one(link_doc)
    
    return {"message": "Document linked", "link_id": link_id}

@router.delete("/timeline/steps/{step_id}/documents/{activity_id}")
async def unlink_document_from_step(step_id: str, activity_id: str, user: dict = Depends(get_current_agent)):
    """Remove a document link from timeline step"""
    is_demo = user.get('is_demo', False)
    
    # Verify ownership chain
    step = await db.timeline_steps.find_one({"step_id": step_id})
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    
    step_tl_ref = step.get('timeline_id', '')
    timeline = await db.timelines.find_one(
        {"timeline_id": step_tl_ref}, {"_id": 0}
    )
    project = await db.projects.find_one({"project_id": timeline['project_id'], "agent_id": user['user_id']})
    
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")
    
    result = await db.timeline_step_documents.delete_one({
        "timeline_step_id": step_id,
        "activity_id": activity_id
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Link not found")
    
    return {"message": "Document unlinked"}

@router.post("/timeline/steps/{step_id}/notes")
async def add_internal_note(step_id: str, data: TimelineStepNoteCreate, user: dict = Depends(get_current_agent)):
    """Add an internal note to a timeline step (agent only)"""
    is_demo = user.get('is_demo', False)
    
    # Verify ownership
    step = await db.timeline_steps.find_one({"step_id": step_id})
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    
    step_tl_ref = step.get('timeline_id', '')
    timeline = await db.timelines.find_one(
        {"timeline_id": step_tl_ref}, {"_id": 0}
    )
    project = await db.projects.find_one({"project_id": timeline['project_id'], "agent_id": user['user_id']})
    
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")
    
    now = datetime.now(timezone.utc).isoformat()
    note_id = f"note_{uuid.uuid4().hex[:12]}"
    
    note_doc = {
        "note_id": note_id,
        "timeline_step_id": step_id,
        "author_id": user['user_id'],
        "content": data.content,
        "created_at": now
    }
    await db.timeline_step_internal_notes.insert_one(note_doc)
    
    # Enrich with author name
    note_doc['author_name'] = user.get('name', 'Unknown')
    note_doc.pop('_id', None)
    
    return note_doc

@router.delete("/timeline/{timeline_id}")
async def delete_project_timeline(timeline_id: str, user: dict = Depends(get_current_agent)):
    """Delete a project timeline and all its steps"""
    is_demo = user.get('is_demo', False)
    
    # Try to find by timeline_id (canonical lookup)
    timeline = await db.timelines.find_one({
        "timeline_id": timeline_id,
        "is_demo": is_demo
    }, {"_id": 0})
    
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")
    
    # Get the actual timeline ID (normalized by compat layer)
    actual_timeline_id = timeline.get('timeline_id')
    
    # Verify agent owns the project
    project = await db.projects.find_one({
        "project_id": timeline['project_id'],
        "agent_id": user['user_id'],
        "is_demo": is_demo
    })
    
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Delete all related data - use compat ref query for both FK names
    steps = await db.timeline_steps.find(
        {"timeline_id": actual_timeline_id}
    ).to_list(100)
    step_ids = [s['step_id'] for s in steps]
    
    if step_ids:
        await db.timeline_step_documents.delete_many({"timeline_step_id": {"$in": step_ids}})
        await db.timeline_step_internal_notes.delete_many({"timeline_step_id": {"$in": step_ids}})
    
    # Delete steps using compat ref query
    await db.timeline_steps.delete_many(
        {"timeline_id": actual_timeline_id}
    )
    
    # Delete the timeline document (canonical)
    await db.timelines.delete_one({"timeline_id": actual_timeline_id})
    
    return {"message": "Timeline deleted"}

