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

# ==================== DOCUMENT VAULT ====================

# ==================== DOCUMENT VAULT ENDPOINTS ====================

# Vault categories for organization
VAULT_CATEGORIES = ["Contracts", "Plans", "Permits", "Reports", "Other"]

class VaultDocumentCreate(BaseModel):
    name: str
    category: str = "Other"
    project_id: Optional[str] = None
    description: Optional[str] = None
    access_level: str = "private"  # private, shared (with specific buyers)
    shared_with_clients: Optional[List[str]] = None  # List of client_ids

class VaultDocumentUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    project_id: Optional[str] = None
    description: Optional[str] = None
    access_level: Optional[str] = None
    shared_with_clients: Optional[List[str]] = None  # List of client_ids

# Document types for vault
VAULT_DOC_TYPES = ["general", "action_required"]

@router.post("/vault/upload")
async def upload_vault_document(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(...),
    category: str = Form("Other"),
    project_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    access_level: str = Form("private"),
    shared_with_clients: Optional[str] = Form(None),  # JSON string of client_ids
    doc_type: str = Form("general"),  # 'general' or 'action_required'
    user: dict = Depends(get_current_agent)
):
    """Upload a document to the vault"""
    # Rate limit: 20 uploads per minute
    rate_limit_check(request, "file_upload")
    
    is_demo = user.get('is_demo', False)
    
    # Validate category
    if category not in VAULT_CATEGORIES:
        category = "Other"
    
    # Validate access level
    if access_level not in ["private", "shared"]:
        access_level = "private"
    
    # Validate doc_type
    if doc_type not in VAULT_DOC_TYPES:
        doc_type = "general"
    
    # Validate file type
    allowed_types = [
        'application/pdf',
        'image/jpeg', 'image/jpg', 'image/png', 'image/webp',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # xlsx
        'application/vnd.ms-excel',  # xls
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # docx
        'application/msword'  # doc
    ]
    
    if file.content_type not in allowed_types:
        # Build user-friendly error message
        allowed_formats = "PDF, JPG, PNG, WEBP, Excel (XLSX/XLS), Word (DOCX/DOC)"
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type. Allowed formats: {allowed_formats}"
        )
    
    # Read file content
    content = await file.read()
    
    # Check file size (max 20MB)
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File must be less than 20MB")
    
    # Save file
    vault_id = f"vault_{uuid.uuid4().hex[:12]}"
    file_ext = file.filename.split('.')[-1] if '.' in file.filename else 'bin'
    filename = f"{vault_id}_{secure_filename(file.filename)}"
    file_path = UPLOAD_DIR / filename
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    file_url = f"/api/uploads/{filename}"
    
    # Parse shared_with_clients JSON
    shared_clients_list = []
    if shared_with_clients:
        try:
            shared_clients_list = json.loads(shared_with_clients)
            if not isinstance(shared_clients_list, list):
                shared_clients_list = []
        except json.JSONDecodeError:
            shared_clients_list = []
    
    # Create vault document record
    vault_doc = {
        "vault_id": vault_id,
        "agent_id": user['user_id'],
        "name": name,
        "original_filename": file.filename,
        "file_url": file_url,
        "file_path": str(file_path),
        "file_type": file.content_type,
        "file_size": len(content),
        "category": category,
        "project_id": project_id,
        "description": description or "",
        "access_level": access_level,
        "shared_with_clients": shared_clients_list if access_level == "shared" else [],
        "doc_type": doc_type,
        "is_demo": is_demo,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.vault_documents.insert_one(vault_doc)
    
    # Send notifications to shared clients
    if access_level == "shared" and shared_clients_list:
        agent_settings = user.get('settings', {})
        agent_profile = user.get('profile', {})
        agent_name = agent_profile.get('display_name') or user.get('name', 'Your agent')
        company_name = agent_settings.get('company_name', '')
        
        for client_id in shared_clients_list:
            client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
            if client and client.get('buyer_id'):
                # Create in-app notification
                notification_title = "Action Required" if doc_type == "action_required" else "New Document"
                await create_notification(
                    user_id=client['buyer_id'],
                    title=notification_title,
                    message=f"{agent_name} shared a document: {name}",
                    notification_type="vault_document",
                    link="/buyer/vault",
                    is_demo=is_demo
                )
                
                # Send email notification
                if client.get('email'):
                    await send_notification_email(
                        "document_sent",
                        client['email'],
                        {
                            "doc_type": "document",
                            "buyer_name": client.get('name', 'there'),
                            "agent_name": agent_name,
                            "company_name": company_name,
                            "title": name,
                            "summary": description or ("This document requires your attention" if doc_type == "action_required" else "A new document has been shared with you"),
                            "currency": "CHF",
                            "amount": 0,
                            "project_name": "",
                            "unit_reference": client.get('unit_reference', '')
                        }
                    )
    
    # Remove MongoDB _id before returning
    vault_doc.pop('_id', None)
    
    return vault_doc

@router.get("/vault", response_model=List[VaultDocumentResponse])
async def get_vault_documents(
    category: Optional[str] = None,
    project_id: Optional[str] = None,
    user: dict = Depends(get_current_agent)
):
    """Get all vault documents for the agent, optionally filtered - ownership scoped"""
    query = {"agent_id": user['user_id']}
    
    if category and category in VAULT_CATEGORIES:
        query["category"] = category
    
    if project_id:
        query["project_id"] = project_id
    
    docs = await db.vault_documents.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    
    return docs


@router.get("/vault/buyer", response_model=List[VaultDocumentResponse])
async def get_buyer_vault_documents_v2(user: dict = Depends(get_current_user)):
    """Get vault documents shared with the buyer based on their client_id - ownership scoped"""
    if user['role'] != 'buyer':
        raise HTTPException(status_code=403, detail="Buyers only")
    
    # Get the buyer's client record (includes client_id and agent_id)
    client = await db.clients.find_one(
        {"buyer_id": user['user_id']},
        {"_id": 0, "client_id": 1, "agent_id": 1}
    )
    
    if not client:
        return []
    
    client_id = client.get('client_id')
    agent_id = client.get('agent_id')
    
    if not client_id or not agent_id:
        return []
    
    # Find shared documents where this client is in shared_with_clients array
    # Note: Using agent_id from client relationship for ownership scoping
    query = {
        "agent_id": agent_id,
        "access_level": "shared",
        "shared_with_clients": client_id
    }
    
    docs = await db.vault_documents.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    return docs


@router.get("/vault/categories/list")
async def get_vault_categories(user: dict = Depends(get_current_agent)):
    """Get available vault categories"""
    return VAULT_CATEGORIES


@router.get("/vault/{vault_id}", response_model=VaultDocumentResponse)
async def get_vault_document(vault_id: str, user: dict = Depends(get_current_user)):
    """
    Get a specific vault document - ownership scoped.
    - Agents can access their own documents
    - Buyers can access shared documents from their agent
    """
    if user['role'] == 'agent':
        # Agent: must own the document
        doc = await db.vault_documents.find_one(
            {"vault_id": vault_id, "agent_id": user['user_id']},
            {"_id": 0}
        )
    elif user['role'] == 'buyer':
        # Buyer: must have sharing access via client relationship
        client = await db.clients.find_one(
            {"buyer_id": user['user_id']},
            {"_id": 0, "client_id": 1, "agent_id": 1}
        )
        
        if not client:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Document must belong to buyer's agent and be shared with them
        doc = await db.vault_documents.find_one(
            {
                "vault_id": vault_id,
                "agent_id": client.get('agent_id'),
                "access_level": "shared",
                "shared_with_clients": client.get('client_id')
            },
            {"_id": 0}
        )
    else:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return doc

@router.put("/vault/{vault_id}", response_model=VaultDocumentResponse)
async def update_vault_document(
    vault_id: str,
    data: VaultDocumentUpdate,
    user: dict = Depends(get_current_agent)
):
    """Update vault document metadata - ownership scoped"""
    
    doc = await db.vault_documents.find_one(
        {"vault_id": vault_id, "agent_id": user['user_id']}
    )
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if data.name is not None:
        update_data["name"] = data.name
    if data.category is not None and data.category in VAULT_CATEGORIES:
        update_data["category"] = data.category
    if data.project_id is not None:
        update_data["project_id"] = data.project_id
    if data.description is not None:
        update_data["description"] = data.description
    if data.access_level is not None and data.access_level in ["private", "shared"]:
        update_data["access_level"] = data.access_level
        # If switching to private, clear shared_with_clients
        if data.access_level == "private":
            update_data["shared_with_clients"] = []
    if data.shared_with_clients is not None:
        update_data["shared_with_clients"] = data.shared_with_clients
    
    await db.vault_documents.update_one(
        {"vault_id": vault_id},
        {"$set": update_data}
    )
    
    return {"message": "Document updated"}

@router.delete("/vault/{vault_id}")
async def delete_vault_document(vault_id: str, user: dict = Depends(get_current_agent)):
    """Delete a vault document"""
    is_demo = user.get('is_demo', False)
    
    doc = await db.vault_documents.find_one(
        {"vault_id": vault_id, "agent_id": user['user_id']}
    )
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete physical file
    if doc.get('file_path'):
        try:
            Path(doc['file_path']).unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Failed to delete vault file: {e}")
    
    await db.vault_documents.delete_one({"vault_id": vault_id})
    
    return {"message": "Document deleted"}

@router.get("/vault/{vault_id}/download")
async def download_vault_document(vault_id: str, user: dict = Depends(get_current_user)):
    """Download a vault document - accessible by agent owner or buyers with sharing access"""
    is_demo = user.get('is_demo', False)
    
    # Get the document
    doc = await db.vault_documents.find_one(
        {"vault_id": vault_id},
        {"_id": 0}
    )
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check access permissions
    if user['role'] == 'agent':
        # Agent must own the document
        if doc.get('agent_id') != user['user_id']:
            raise HTTPException(status_code=403, detail="Access denied")
    elif user['role'] == 'buyer':
        # Get buyer's client record to verify access
        client = await db.clients.find_one(
            {"buyer_id": user['user_id']},
            {"_id": 0, "client_id": 1, "agent_id": 1}
        )
        
        if not client:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Document must belong to buyer's agent
        if doc.get('agent_id') != client.get('agent_id'):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Check if document is shared with this buyer's client_id
        client_id = client.get('client_id')
        if not client_id or client_id not in doc.get('shared_with_clients', []):
            raise HTTPException(status_code=403, detail="Document not shared with you")
    else:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get file path and serve
    file_path = doc.get('file_path')
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path,
        filename=doc.get('filename', 'document'),
        media_type='application/octet-stream'
    )

