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

# ==================== CLIENT CRUD ====================

# ==================== CLIENT ENDPOINTS ====================

@router.get("/clients", response_model=List[Client])
async def get_clients(project_id: Optional[str] = None, user: dict = Depends(get_current_agent)):
    """Get all clients for agent, optionally filtered by project"""
    query = {"agent_id": user['user_id'], "is_demo": user.get('is_demo', False)}
    if project_id:
        query["project_id"] = project_id
    clients = await db.clients.find(query, {"_id": 0}).to_list(100)
    return clients

@router.get("/clients/{client_id}", response_model=Client)
async def get_client(client_id: str, user: dict = Depends(get_current_agent)):
    """Get single client"""
    query = {"client_id": client_id, "agent_id": user['user_id'], "is_demo": user.get('is_demo', False)}
    client = await db.clients.find_one(query, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@router.get("/clients/{client_id}/preview")
async def get_client_preview_data(client_id: str, user: dict = Depends(get_current_agent)):
    """
    Get client data for "View as Client" preview.
    Returns client info, their activities, documents, and project details.
    Agent uses this to see what the client sees.
    """
    is_demo = user.get('is_demo', False)
    
    client = await db.clients.find_one(
        {"client_id": client_id, "agent_id": user['user_id']},
        {"_id": 0}
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    project = await db.projects.find_one(
        {"project_id": client['project_id']},
        {"_id": 0}
    )
    
    # Get activities for this client
    recipient_records = await db.activity_recipients.find(
        {"client_id": client_id},
        {"_id": 0, "activity_id": 1}
    ).to_list(1000)
    
    activity_ids = [r['activity_id'] for r in recipient_records]
    
    activities = []
    if activity_ids:
        activities_raw = await db.activities.find(
            {"activity_id": {"$in": activity_ids}},
            {"_id": 0}
        ).sort("created_at", -1).limit(20).to_list(20)
        
        for act in activities_raw:
            activities.append(await enrich_activity(act))
    
    # Get documents for this client
    documents = await db.documents.find(
        {"client_id": client_id, "is_demo": is_demo, "status": {"$ne": "Draft"}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    # Get construction stages for the project (from canonical timeline_steps)
    stages = await db.timeline_steps.find(
        {"project_id": client['project_id']},
        {"_id": 0}
    ).sort("order_index", 1).to_list(50)
    
    # Get team members for the project
    team = await db.team_members.find(
        {"project_id": client['project_id']},
        {"_id": 0}
    ).sort("name", 1).to_list(100)
    
    return {
        "client": client,
        "project": project,
        "activities": activities,
        "documents": documents,
        "stages": stages,
        "team": team,
        "is_preview": True
    }

@router.post("/clients", response_model=Client)
async def create_client(data: ClientCreate, user: dict = Depends(get_current_agent)):
    """Create a new client linked to a project"""
    is_demo = user.get('is_demo', False)
    
    project = await db.projects.find_one(
        {"project_id": data.project_id, "agent_id": user['user_id']},
        {"_id": 0}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Resolve unit_id to unit_reference
    unit_reference = "General"
    unit_id = None
    if data.unit_id:
        unit = await db.units.find_one({
            "unit_id": data.unit_id,
            "project_id": data.project_id,
            "is_demo": is_demo
        }, {"_id": 0})
        if unit:
            unit_id = data.unit_id
            unit_reference = unit.get('unit_reference', unit.get('name', 'Unit'))
        else:
            raise HTTPException(status_code=400, detail="Invalid unit for this project")
        
        # Check if unit is already assigned to another client
        existing_client = await db.clients.find_one({
            "unit_id": data.unit_id,
            "is_demo": is_demo
        }, {"_id": 0, "name": 1})
        if existing_client:
            raise HTTPException(
                status_code=409, 
                detail=f"Unit already assigned to client: {existing_client.get('name', 'Unknown')}"
            )
    
    client_id = f"client_{uuid.uuid4().hex[:12]}"
    buyer = await db.users.find_one({"email": data.email, "role": "buyer"}, {"_id": 0})
    
    client_doc = {
        "client_id": client_id,
        "agent_id": user['user_id'],
        "buyer_id": buyer['user_id'] if buyer else None,
        "name": data.name,
        "email": data.email,
        "phone": data.phone,
        "project_id": data.project_id,
        "unit_id": unit_id,
        "unit_reference": unit_reference,
        "is_demo": is_demo,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.clients.insert_one(client_doc)
    return await db.clients.find_one({"client_id": client_id}, {"_id": 0})

@router.put("/clients/{client_id}", response_model=Client)
async def update_client(client_id: str, data: ClientUpdate, user: dict = Depends(get_current_agent)):
    """Update a client"""
    is_demo = user.get('is_demo', False)
    query = {"client_id": client_id, "agent_id": user['user_id']}
    client = await db.clients.find_one(query, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    update_data = {}
    
    # Handle basic field updates
    if data.name is not None:
        update_data['name'] = data.name
    if data.email is not None:
        update_data['email'] = data.email
    if data.phone is not None:
        update_data['phone'] = data.phone
    
    # Handle project change
    if data.project_id is not None and data.project_id != client.get('project_id'):
        project = await db.projects.find_one({
            "project_id": data.project_id,
            "agent_id": user['user_id'],
            "is_demo": is_demo
        })
        if not project:
            raise HTTPException(status_code=400, detail="Invalid project")
        update_data['project_id'] = data.project_id
        # Reset unit when project changes
        update_data['unit_id'] = None
        update_data['unit_reference'] = "General"
    
    # Handle unit change
    if data.unit_id is not None:
        target_project_id = data.project_id or client.get('project_id')
        if data.unit_id == "":
            update_data['unit_id'] = None
            update_data['unit_reference'] = "General"
        else:
            unit = await db.units.find_one({
                "unit_id": data.unit_id,
                "project_id": target_project_id,
                "is_demo": is_demo
            }, {"_id": 0})
            if not unit:
                raise HTTPException(status_code=400, detail="Invalid unit for this project")
            
            # Check if unit is already assigned to another client
            existing_client = await db.clients.find_one({
                "unit_id": data.unit_id,
                "client_id": {"$ne": client_id},
                "is_demo": is_demo
            }, {"_id": 0, "name": 1, "client_id": 1})
            
            if existing_client:
                if data.force_unit_reassign:
                    # Remove unit from the other client
                    await db.clients.update_one(
                        {"client_id": existing_client['client_id']},
                        {"$set": {"unit_id": None, "unit_reference": "General"}}
                    )
                    logger.info(f"Reassigned unit {data.unit_id} from {existing_client['client_id']} to {client_id}")
                else:
                    raise HTTPException(
                        status_code=409, 
                        detail=f"Unit already assigned to client: {existing_client.get('name', 'Unknown')}"
                    )
            
            update_data['unit_id'] = data.unit_id
            update_data['unit_reference'] = unit.get('unit_reference', unit.get('name', 'Unit'))
    
    if update_data:
        await db.clients.update_one(query, {"$set": update_data})
    
    return await db.clients.find_one(query, {"_id": 0})

@router.delete("/clients/{client_id}")
async def delete_client(client_id: str, user: dict = Depends(get_current_agent)):
    """Delete a client"""
    query = {"client_id": client_id, "agent_id": user['user_id'], "is_demo": user.get('is_demo', False)}
    result = await db.clients.delete_one(query)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"message": "Client deleted"}

