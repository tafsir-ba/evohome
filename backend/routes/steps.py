"""Auto-extracted route module from server.py — Phase 3 modularization."""
import os
import re
import json
import uuid
import base64
import logging
import secrets
import tempfile
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

# ==================== PROJECT STEPS CRUD ====================

# ==================== PROJECT STEPS ENDPOINTS ====================

@router.get("/projects/{project_id}/steps")
async def get_project_steps(project_id: str, user: dict = Depends(get_current_user)):
    """Get all steps for a project timeline.
    
    SOURCE OF TRUTH: timeline_steps collection.
    """
    if user['role'] == 'agent':
        project = await db.projects.find_one(
            {"project_id": project_id, "agent_id": user['user_id']},
            {"_id": 0}
        )
    else:
        clients = await db.clients.find(
            {"buyer_id": user['user_id'], "project_id": project_id},
            {"_id": 0}
        ).to_list(10)
        if not clients:
            raise HTTPException(status_code=403, detail="No access to this project")
        project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Single source: timeline_steps (via compat layer)
    timeline = await db.timelines.find_one({"project_id": project_id}, {"_id": 0})
    
    if not timeline:
        # No timeline exists yet - return empty stages
        return {"project": project, "stages": []}
    
    timeline_id = timeline.get('timeline_id')
    steps = await db.timeline_steps.find(
        {"timeline_id": timeline_id},
        {"_id": 0}
    ).sort("order_index", 1).to_list(50)
    
    # Map to ProjectStage format for API compatibility
    stages = []
    for step in steps:
        stages.append({
            "stage_id": step.get('step_id'),
            "project_id": project_id,
            "agent_id": project.get('agent_id'),
            "name": step.get('title'),
            "description": step.get('description'),
            "order": step.get('order_index', 0),
            "planned_start": step.get('planned_start') or step.get('planned_date'),
            "planned_end": step.get('planned_end'),
            "actual_start": step.get('actual_start'),
            "actual_end": step.get('completed_at'),
            "status": _map_timeline_status_to_stage(step.get('status', 'pending')),
            "progress_percent": step.get('progress_percent', 0),
            "notes": step.get('notes'),
            "dependencies": step.get('dependencies', []),
            "is_demo": step.get('is_demo', False),
            "created_at": step.get('created_at'),
            "updated_at": step.get('updated_at')
        })
    
    return {"project": project, "stages": stages}


def _map_timeline_status_to_stage(timeline_status: str) -> str:
    """Map TimelineStep status to ProjectStage status for API compatibility"""
    mapping = {
        'pending': 'upcoming',
        'in_progress': 'in_progress',
        'completed': 'completed',
        'approved': 'completed'
    }
    return mapping.get(timeline_status, 'upcoming')


def _map_stage_status_to_timeline(stage_status: str) -> str:
    """Map ProjectStage status to TimelineStep status"""
    mapping = {
        'upcoming': 'pending',
        'in_progress': 'in_progress',
        'completed': 'completed',
        'delayed': 'in_progress',
        'on_hold': 'pending'
    }
    return mapping.get(stage_status, 'pending')

@router.post("/projects/{project_id}/steps")
async def create_project_step(project_id: str, data: ProjectStageCreate, user: dict = Depends(get_current_agent)):
    """Create a new step in project timeline.
    
    SOURCE OF TRUTH: timeline_steps collection.
    Creates timeline if it doesn't exist.
    """
    is_demo = user.get('is_demo', False)
    
    project = await db.projects.find_one(
        {"project_id": project_id, "agent_id": user['user_id'], "is_demo": is_demo},
        {"_id": 0}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Ensure timeline exists for this project (via compat layer)
    timeline = await db.timelines.find_one({"project_id": project_id, "is_demo": is_demo}, {"_id": 0})
    if not timeline:
        timeline_id = f"timeline_{uuid.uuid4().hex[:12]}"
        timeline = {
            "timeline_id": timeline_id,
            "project_id": project_id,
            "template_id": None,
            "template_name": None,
            "is_demo": is_demo,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.timelines.insert_one(timeline)
    
    timeline_id = timeline.get('timeline_id')
    step_id = f"step_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    
    # Write to timeline_steps (single source of truth)
    step_doc = {
        "step_id": step_id,
        "timeline_id": timeline_id,
        "title": data.name,
        "description": data.description,
        "order_index": data.order,
        "planned_date": data.planned_start,
        "planned_start": data.planned_start,
        "planned_end": data.planned_end,
        "actual_start": None,
        "completed_at": None,
        "status": "pending",
        "progress_percent": 0,
        "notes": None,
        "dependencies": data.dependencies or [],
        "is_demo": is_demo,
        "created_at": now,
        "updated_at": now
    }
    
    await db.timeline_steps.insert_one(step_doc)
    
    # Return in ProjectStage format for API compatibility
    return {
        "stage_id": step_id,
        "project_id": project_id,
        "agent_id": user['user_id'],
        "name": data.name,
        "description": data.description,
        "order": data.order,
        "planned_start": data.planned_start,
        "planned_end": data.planned_end,
        "actual_start": None,
        "actual_end": None,
        "status": "upcoming",
        "progress_percent": 0,
        "notes": None,
        "dependencies": data.dependencies or [],
        "is_demo": is_demo,
        "created_at": now,
        "updated_at": now
    }

@router.put("/projects/{project_id}/steps/{step_id}")
async def update_project_step(project_id: str, step_id: str, data: ProjectStageUpdate, user: dict = Depends(get_current_agent)):
    """Update a step in project timeline.
    
    SOURCE OF TRUTH: timeline_steps collection.
    """
    # Find the step in timeline_steps
    step = await db.timeline_steps.find_one({"step_id": step_id}, {"_id": 0})
    if not step:
        raise HTTPException(status_code=404, detail="Stage not found")
    
    # Verify ownership via timeline -> project
    step_tl_ref = step.get('timeline_id', '')
    timeline = await db.timelines.find_one({
        "timeline_id": step_tl_ref
    }, {"_id": 0})
    if not timeline or timeline.get('project_id') != project_id:
        raise HTTPException(status_code=404, detail="Stage not found in this project")
    
    project = await db.projects.find_one(
        {"project_id": project_id, "agent_id": user['user_id']},
        {"_id": 0}
    )
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")
    
    now = datetime.now(timezone.utc).isoformat()
    update_data = {"updated_at": now}
    
    # Map ProjectStageUpdate fields to TimelineStep fields
    if data.name is not None:
        update_data['title'] = data.name
    if data.description is not None:
        update_data['description'] = data.description
    if data.order is not None:
        update_data['order_index'] = data.order
    if data.planned_start is not None:
        update_data['planned_start'] = data.planned_start
        update_data['planned_date'] = data.planned_start
    if data.planned_end is not None:
        update_data['planned_end'] = data.planned_end
    if data.actual_start is not None:
        update_data['actual_start'] = data.actual_start
    if data.actual_end is not None:
        update_data['completed_at'] = data.actual_end
    if data.status is not None:
        update_data['status'] = _map_stage_status_to_timeline(data.status)
    if data.progress_percent is not None:
        update_data['progress_percent'] = data.progress_percent
    if data.notes is not None:
        update_data['notes'] = data.notes
    
    await db.timeline_steps.update_one({"step_id": step_id}, {"$set": update_data})
    
    # Return updated step
    updated_step = await db.timeline_steps.find_one({"step_id": step_id}, {"_id": 0})
    return {
        "stage_id": updated_step.get('step_id'),
        "project_id": project_id,
        "agent_id": user['user_id'],
        "name": updated_step.get('title'),
        "description": updated_step.get('description'),
        "order": updated_step.get('order_index', 0),
        "planned_start": updated_step.get('planned_start'),
        "planned_end": updated_step.get('planned_end'),
        "actual_start": updated_step.get('actual_start'),
        "actual_end": updated_step.get('completed_at'),
        "status": _map_timeline_status_to_stage(updated_step.get('status', 'pending')),
        "progress_percent": updated_step.get('progress_percent', 0),
        "notes": updated_step.get('notes'),
        "dependencies": updated_step.get('dependencies', []),
        "is_demo": updated_step.get('is_demo', False),
        "created_at": updated_step.get('created_at'),
        "updated_at": updated_step.get('updated_at')
    }

@router.delete("/projects/{project_id}/steps/{step_id}")
async def delete_project_step(project_id: str, step_id: str, user: dict = Depends(get_current_agent)):
    """Delete a step from project timeline.
    
    SOURCE OF TRUTH: timeline_steps collection.
    """
    # Find the step
    step = await db.timeline_steps.find_one({"step_id": step_id}, {"_id": 0})
    if not step:
        raise HTTPException(status_code=404, detail="Stage not found")
    
    # Verify ownership via timeline -> project
    step_tl_ref = step.get('timeline_id', '')
    timeline = await db.timelines.find_one({
        "timeline_id": step_tl_ref
    }, {"_id": 0})
    if not timeline or timeline.get('project_id') != project_id:
        raise HTTPException(status_code=404, detail="Stage not found in this project")
    
    project = await db.projects.find_one(
        {"project_id": project_id, "agent_id": user['user_id']},
        {"_id": 0}
    )
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")
    
    result = await db.timeline_steps.delete_one({"step_id": step_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Step not found")
    
    return {"message": "Step deleted"}

