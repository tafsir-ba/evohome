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

# ==================== DASHBOARD, RECENT WORK, PROJECT CONTEXT ====================

# ==================== COMPOSITE ENDPOINTS (Phase 2) ====================
# One canonical endpoint per major screen. Backend is single source of truth.
# No fallbacks. No reconstruction logic. Frontend renders only.

@router.get("/agent/dashboard", response_model=DashboardResponse)
async def get_agent_dashboard(user: dict = Depends(get_current_agent)):
    """
    Canonical endpoint for AgentHomePage (Command Center).
    Returns: projects, selected_project, recent_work
    Single source of truth. No client-side reconstruction.
    """
    # Get all projects for this agent
    projects_cursor = db.projects.find(
        {"agent_id": user['user_id']},
        {"_id": 0}
    ).sort("created_at", -1)
    projects_raw = await projects_cursor.to_list(100)
    
    projects = [
        ProjectSummary(
            project_id=p['project_id'],
            name=p['name'],
            address=p.get('address'),
            status=p.get('status'),
            created_at=p.get('created_at')
        ) for p in projects_raw
    ]
    
    # Selected project (first by default, or from user preference later)
    selected_project = projects[0] if projects else None
    
    # Recent work - last 6 activities/modifications
    recent_work = []
    
    # Get recent clients
    recent_clients = await db.clients.find(
        {"agent_id": user['user_id']},
        {"_id": 0}
    ).sort("updated_at", -1).limit(3).to_list(3)
    
    for c in recent_clients:
        recent_work.append(RecentWorkItem(
            id=c['client_id'],
            type='client',
            title=c['name'],
            subtitle=c.get('email'),
            path=f"/agent/clients/{c['client_id']}",
            timestamp=c.get('updated_at')
        ))
    
    # Get recent documents
    recent_docs = await db.documents.find(
        {"agent_id": user['user_id']},
        {"_id": 0}
    ).sort("updated_at", -1).limit(3).to_list(3)
    
    for d in recent_docs:
        doc_type = d.get('type', 'document')
        recent_work.append(RecentWorkItem(
            id=d['document_id'],
            type='document',
            title=d.get('title') or f"{doc_type.title()} #{d.get('document_number', '')}",
            subtitle=d.get('client_name'),
            path=f"/agent/{doc_type}s/{d['document_id']}",
            timestamp=d.get('updated_at')
        ))
    
    # Sort by timestamp and limit to 6
    recent_work.sort(key=lambda x: x.timestamp or '', reverse=True)
    recent_work = recent_work[:6]
    
    return DashboardResponse(
        projects=projects,
        selected_project=selected_project,
        recent_work=recent_work
    )



class RecentWorkResponse(BaseModel):
    items: List[RecentWorkItem] = []

@router.get("/command/recent-work", response_model=RecentWorkResponse)
async def get_recent_work(user: dict = Depends(get_current_agent)):
    """
    Returns recent work items for the agent.
    Independent of project selection.
    """
    recent_work = []
    
    # Get recent clients
    recent_clients = await db.clients.find(
        {"agent_id": user['user_id']},
        {"_id": 0}
    ).sort("updated_at", -1).limit(3).to_list(3)
    
    for c in recent_clients:
        recent_work.append(RecentWorkItem(
            id=c['client_id'],
            type='client',
            title=c['name'],
            subtitle=c.get('email'),
            path=f"/agent/clients/{c['client_id']}",
            timestamp=c.get('updated_at')
        ))
    
    # Get recent documents
    recent_docs = await db.documents.find(
        {"agent_id": user['user_id']},
        {"_id": 0}
    ).sort("updated_at", -1).limit(3).to_list(3)
    
    for d in recent_docs:
        doc_type = d.get('type', 'document')
        recent_work.append(RecentWorkItem(
            id=d['document_id'],
            type='document',
            title=d.get('title') or f"{doc_type.title()} #{d.get('document_number', '')}",
            subtitle=d.get('client_name'),
            path=f"/agent/{doc_type}s/{d['document_id']}",
            timestamp=d.get('updated_at')
        ))
    
    # Sort by timestamp and limit to 6
    recent_work.sort(key=lambda x: x.timestamp or '', reverse=True)
    recent_work = recent_work[:6]
    
    return RecentWorkResponse(items=recent_work)


@router.get("/projects/{project_id}/context", response_model=ProjectContextResponse)
async def get_project_context(project_id: str, user: dict = Depends(get_current_agent)):
    """
    Canonical endpoint for project context (clients + units).
    Called when project selection changes.
    Single source of truth. No fallbacks.
    """
    # Get project
    project = await db.projects.find_one(
        {"project_id": project_id, "agent_id": user['user_id']},
        {"_id": 0}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_summary = ProjectSummary(
        project_id=project['project_id'],
        name=project['name'],
        address=project.get('address'),
        status=project.get('status'),
        created_at=project.get('created_at')
    )
    
    # Get clients for this project
    clients_raw = await db.clients.find(
        {"project_id": project_id, "agent_id": user['user_id']},
        {"_id": 0}
    ).to_list(100)
    
    clients = [
        ClientSummary(
            client_id=c['client_id'],
            name=c['name'],
            email=c.get('email'),
            project_id=c.get('project_id'),
            unit_id=c.get('unit_id')
        ) for c in clients_raw
    ]
    
    # Get units for this project
    units_raw = await db.units.find(
        {"project_id": project_id},
        {"_id": 0}
    ).to_list(100)
    
    units = [
        UnitSummary(
            unit_id=u['unit_id'],
            reference=u.get('unit_reference', u.get('reference', '')),
            type=u.get('unit_type', u.get('type')),
            client_id=u.get('client_id')
        ) for u in units_raw
    ]
    
    return ProjectContextResponse(
        project=project_summary,
        clients=clients,
        units=units
    )


@router.get("/projects/{project_id}/timeline/full", response_model=ProjectTimelineResponse)
async def get_project_timeline_full(project_id: str, user: dict = Depends(get_current_user)):
    """
    Canonical endpoint for AgentTimeline.
    Returns: project, timeline_id, steps, progress
    Single source of truth: timeline_steps collection.
    """
    # Access control
    if user['role'] == 'agent':
        project = await db.projects.find_one(
            {"project_id": project_id, "agent_id": user['user_id']},
            {"_id": 0}
        )
    else:
        # Buyer access via client link
        client = await db.clients.find_one(
            {"buyer_id": user['user_id'], "project_id": project_id},
            {"_id": 0}
        )
        if not client:
            raise HTTPException(status_code=403, detail="No access to this project")
        project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_summary = ProjectSummary(
        project_id=project['project_id'],
        name=project['name'],
        address=project.get('address'),
        status=project.get('status'),
        created_at=project.get('created_at')
    )
    
    # Get timeline (via compat layer)
    timeline = await db.timelines.find_one(
        {"project_id": project_id}, {"_id": 0}
    )
    
    if not timeline:
        return ProjectTimelineResponse(
            project=project_summary,
            timeline_id=None,
            steps=[],
            progress_percent=0
        )
    
    timeline_id = timeline.get('timeline_id')
    
    # Get steps from single source of truth
    steps_raw = await db.timeline_steps.find(
        {"timeline_id": timeline_id},
        {"_id": 0}
    ).sort("order_index", 1).to_list(50)
    
    steps = [
        TimelineStepSummary(
            step_id=s['step_id'],
            title=s['title'],
            description=s.get('description'),
            status=s.get('status', 'pending'),
            order_index=s.get('order_index', 0),
            planned_start=s.get('planned_start') or s.get('planned_date'),
            planned_end=s.get('planned_end'),
            progress_percent=s.get('progress_percent', 0)
        ) for s in steps_raw
    ]
    
    # Calculate overall progress
    if steps:
        total_progress = sum(s.progress_percent for s in steps)
        progress_percent = total_progress // len(steps)
    else:
        progress_percent = 0
    
    return ProjectTimelineResponse(
        project=project_summary,
        timeline_id=timeline_id,
        steps=steps,
        progress_percent=progress_percent
    )


@router.get("/projects/{project_id}/workflow/full", response_model=ProjectWorkflowResponse)
async def get_project_workflow_full(project_id: str, user: dict = Depends(get_current_agent)):
    """
    Canonical endpoint for AgentWorkflow.
    Returns: project, timeline, steps, activities, templates
    Single source of truth for all workflow data.
    """
    # Get project
    project = await db.projects.find_one(
        {"project_id": project_id, "agent_id": user['user_id']},
        {"_id": 0}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_summary = ProjectSummary(
        project_id=project['project_id'],
        name=project['name'],
        address=project.get('address'),
        status=project.get('status'),
        created_at=project.get('created_at')
    )
    
    # Get timeline and steps (via compat layer)
    timeline = await db.timelines.find_one(
        {"project_id": project_id}, {"_id": 0}
    )
    
    timeline_id = None
    steps = []
    
    if timeline:
        timeline_id = timeline.get('timeline_id')
        
        steps_raw = await db.timeline_steps.find(
            {"timeline_id": timeline_id},
            {"_id": 0}
        ).sort("order_index", 1).to_list(50)
        
        steps = [
            TimelineStepSummary(
                step_id=s['step_id'],
                title=s['title'],
                description=s.get('description'),
                status=s.get('status', 'pending'),
                order_index=s.get('order_index', 0),
                planned_start=s.get('planned_start') or s.get('planned_date'),
                planned_end=s.get('planned_end'),
                progress_percent=s.get('progress_percent', 0)
            ) for s in steps_raw
        ]
    
    # Get recent activities for this project
    activities_raw = await db.activities.find(
        {"project_id": project_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(20).to_list(20)
    
    # Get templates (agent-specific or global)
    templates_raw = await db.timeline_templates.find(
        {"$or": [{"agent_id": user['user_id']}, {"is_global": True}]},
        {"_id": 0}
    ).to_list(50)
    
    return ProjectWorkflowResponse(
        project=project_summary,
        timeline_id=timeline_id,
        steps=steps,
        activities=activities_raw,
        templates=templates_raw
    )


