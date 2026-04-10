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

# ==================== PROJECTS, UNITS, TEAM MEMBERS, TEAM DIRECTORY ====================

# ==================== PROJECT ENDPOINTS ====================

@router.get("/projects", response_model=List[Project])
async def get_projects(user: dict = Depends(get_current_user)):
    """
    Get projects for current user.
    - Agents: see all their projects
    - Buyers: see only the project(s) they are associated with via client record
    
    Uses containment filter during migration to separate demo database.
    """
    demo_filter = get_demo_filter(user)
    
    if user['role'] == 'agent':
        query = {"agent_id": user['user_id'], **demo_filter}
    elif user['role'] == 'buyer':
        client = await db.clients.find_one(
            {"buyer_id": user['user_id'], **demo_filter},
            {"_id": 0, "project_id": 1}
        )
        if not client or not client.get('project_id'):
            return []
        query = {"project_id": client['project_id'], **demo_filter}
    else:
        return []
    
    projects = await db.projects.find(query, {"_id": 0}).to_list(100)
    
    # Add client count and unit count to each project
    for project in projects:
        client_count = await db.clients.count_documents({"project_id": project['project_id'], **demo_filter})
        unit_count = await db.units.count_documents({"project_id": project['project_id']})
        project['client_count'] = client_count
        project['unit_count'] = unit_count
    
    return projects

@router.post("/projects", response_model=Project)
async def create_project(data: ProjectCreate, user: dict = Depends(get_current_agent)):
    """Create a new project (agent only) - enforces plan-based unit limits"""
    demo_filter = get_demo_filter(user)
    is_demo = user.get('is_demo', False)
    
    # Unit gating - check subscription limits (skip for demo users)
    # Note: Creating a project adds 1 unit by default (more units can be added later)
    if not is_demo:
        subscription_data = await get_agent_subscription_data(user)
        if not subscription_data['can_create_unit']:
            plan_name = subscription_data['plan_name']
            limit = subscription_data['unit_limit']
            current = subscription_data['unit_usage']
            raise HTTPException(
                status_code=403, 
                detail=f"Unit limit reached. Your {plan_name} plan allows {limit} units ({current} used). Please upgrade to add more units."
            )
    
    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    
    # Store is_demo for backward compatibility during migration
    project_doc = {
        "project_id": project_id,
        "agent_id": user['user_id'],
        "name": data.name,
        "address": data.address,
        "description": data.description,
        "total_units": data.total_units,
        "construction_start": data.construction_start,
        "estimated_completion": data.estimated_completion,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_demo": is_demo  # For migration compatibility
    }
    
    await db.projects.insert_one(project_doc)
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    # Count linked clients and units
    client_count = await db.clients.count_documents({"project_id": project_id, **demo_filter})
    unit_count = await db.units.count_documents({"project_id": project_id})
    project['client_count'] = client_count
    project['unit_count'] = unit_count
    return project

@router.put("/projects/{project_id}", response_model=Project)
async def update_project(project_id: str, data: ProjectUpdate, user: dict = Depends(get_current_agent)):
    """Update a project (agent only)"""
    demo_filter = get_demo_filter(user)
    query = {"project_id": project_id, "agent_id": user['user_id'], **demo_filter}
    
    project = await db.projects.find_one(query, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if update_data:
        await db.projects.update_one(query, {"$set": update_data})
    
    updated_project = await db.projects.find_one(query, {"_id": 0})
    client_count = await db.clients.count_documents({"project_id": project_id, **demo_filter})
    unit_count = await db.units.count_documents({"project_id": project_id})
    updated_project['client_count'] = client_count
    updated_project['unit_count'] = unit_count
    return updated_project

@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, user: dict = Depends(get_current_agent)):
    """Delete a project (agent only)"""
    demo_filter = get_demo_filter(user)
    is_demo = user.get('is_demo', False)
    query = {"project_id": project_id, "agent_id": user['user_id']}
    
    project = await db.projects.find_one(query, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if project has linked clients
    client_count = await db.clients.count_documents({"project_id": project_id})
    if client_count > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete project with {client_count} linked client(s). Remove clients first.")
    
    await db.projects.delete_one(query)
    return {"message": "Project deleted"}

# ==================== PROJECT UNITS ENDPOINTS ====================

@router.get("/projects/{project_id}/units")
async def get_project_units(project_id: str, user: dict = Depends(get_current_agent)):
    """Get all units for a project with assignment status"""
    demo_filter = get_demo_filter(user)
    query = {"project_id": project_id, "agent_id": user['user_id'], **demo_filter}
    
    project = await db.projects.find_one(query, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Read from canonical units collection
    units = await db.units.find(
        {"project_id": project_id},
        {"_id": 0}
    ).to_list(500)
    
    # Enrich with client assignment info
    for unit in units:
        # Check if any client is assigned to this unit
        assigned_client = await db.clients.find_one(
            {"unit_id": unit['unit_id'], **demo_filter},
            {"_id": 0, "client_id": 1, "name": 1}
        )
        if assigned_client:
            unit['assigned_client_id'] = assigned_client['client_id']
            unit['assigned_client_name'] = assigned_client['name']
            unit['is_available'] = False
        else:
            unit['assigned_client_id'] = None
            unit['assigned_client_name'] = None
            unit['is_available'] = True
        
        # Legacy client_id field for backward compatibility
        if unit.get('client_id'):
            client = await db.clients.find_one({"client_id": unit['client_id'], **demo_filter}, {"_id": 0, "name": 1})
            unit['client_name'] = client['name'] if client else None
    
    return units

@router.post("/projects/{project_id}/units")
async def create_project_unit(project_id: str, data: dict, user: dict = Depends(get_current_agent)):
    """Add a unit to a project - enforces plan-based unit limits"""
    demo_filter = get_demo_filter(user)
    is_demo = user.get('is_demo', False)
    query = {"project_id": project_id, "agent_id": user['user_id'], **demo_filter}
    
    project = await db.projects.find_one(query, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Unit gating - check subscription limits (skip for demo users)
    if not is_demo:
        subscription_data = await get_agent_subscription_data(user)
        if not subscription_data['can_create_unit']:
            plan_name = subscription_data['plan_name']
            limit = subscription_data['unit_limit']
            current = subscription_data['unit_usage']
            raise HTTPException(
                status_code=403, 
                detail=f"Unit limit reached. Your {plan_name} plan allows {limit} units ({current} used). Please upgrade to add more units."
            )
    
    unit_reference = data.get('unit_reference', '').strip()
    if not unit_reference:
        raise HTTPException(status_code=400, detail="Unit reference is required")
    
    # Check for duplicate
    existing = await db.units.find_one({
        "project_id": project_id,
        "unit_reference": unit_reference
    })
    if existing:
        raise HTTPException(status_code=400, detail="Unit reference already exists in this project")
    
    unit_id = f"unit_{uuid.uuid4().hex[:12]}"
    unit_doc = {
        "unit_id": unit_id,
        "project_id": project_id,
        "unit_reference": unit_reference,
        "client_id": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Write to canonical units collection
    await db.units.insert_one(unit_doc)
    return await db.units.find_one({"unit_id": unit_id}, {"_id": 0})

@router.delete("/projects/{project_id}/units/{unit_id}")
async def delete_project_unit(project_id: str, unit_id: str, user: dict = Depends(get_current_agent)):
    """Remove a unit from a project"""
    demo_filter = get_demo_filter(user)
    
    # Verify project ownership
    project = await db.projects.find_one({
        "project_id": project_id,
        "agent_id": user['user_id'],
        **demo_filter
    }, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Read from canonical units collection
    unit = await db.units.find_one({
        "unit_id": unit_id,
        "project_id": project_id
    }, {"_id": 0})
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    
    if unit.get('client_id'):
        raise HTTPException(status_code=400, detail="Cannot delete unit that is assigned to a client")
    
    await db.units.delete_one({"unit_id": unit_id})
    
    return {"message": "Unit deleted"}

# ==================== TEAM MEMBER ENDPOINTS ====================

@router.get("/projects/{project_id}/team")
async def get_team_members(project_id: str, user: dict = Depends(get_current_user)):
    """Get team members for a project - accessible by both agent and linked buyers"""
    is_demo = user.get('is_demo', False)
    
    if user['role'] == 'agent':
        # Agent must own the project
        project = await db.projects.find_one(
            {"project_id": project_id, "agent_id": user['user_id']},
            {"_id": 0}
        )
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
    else:
        # Buyer must be linked to a client in this project
        client = await db.clients.find_one(
            {"buyer_id": user['user_id'], "project_id": project_id},
            {"_id": 0}
        )
        if not client:
            raise HTTPException(status_code=403, detail="Not authorized to view this project's team")
    
    members = await db.team_members.find(
        {"project_id": project_id},
        {"_id": 0}
    ).sort("name", 1).to_list(100)
    
    return members

@router.post("/projects/{project_id}/team")
async def create_team_member(project_id: str, data: TeamMemberCreate, user: dict = Depends(get_current_agent)):
    """Add a team member to a project (agent only)"""
    is_demo = user.get('is_demo', False)
    
    project = await db.projects.find_one(
        {"project_id": project_id, "agent_id": user['user_id']},
        {"_id": 0}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    member_id = f"member_{uuid.uuid4().hex[:12]}"
    member_doc = {
        "member_id": member_id,
        "project_id": project_id,
        "agent_id": user['user_id'],
        "company_name": data.company_name,
        "contact_name": data.contact_name,
        "role": data.role,
        "email": data.email,
        "phone": data.phone,
        "website": data.website,
        "address": data.address,
        "notes": data.notes,
        "is_demo": is_demo,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.team_members.insert_one(member_doc)
    return await db.team_members.find_one({"member_id": member_id}, {"_id": 0})

@router.put("/projects/{project_id}/team/{member_id}")
async def update_team_member(project_id: str, member_id: str, data: TeamMemberUpdate, user: dict = Depends(get_current_agent)):
    """Update a team member (agent only)"""
    is_demo = user.get('is_demo', False)
    
    member = await db.team_members.find_one({
        "member_id": member_id,
        "project_id": project_id,
        "agent_id": user['user_id'],
        "is_demo": is_demo
    }, {"_id": 0})
    
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    if update_data:
        await db.team_members.update_one(
            {"member_id": member_id},
            {"$set": update_data}
        )
    
    return await db.team_members.find_one({"member_id": member_id}, {"_id": 0})

@router.delete("/projects/{project_id}/team/{member_id}")
async def delete_team_member(project_id: str, member_id: str, user: dict = Depends(get_current_agent)):
    """Delete a team member (agent only)"""
    is_demo = user.get('is_demo', False)
    
    member = await db.team_members.find_one({
        "member_id": member_id,
        "project_id": project_id,
        "agent_id": user['user_id'],
        "is_demo": is_demo
    }, {"_id": 0})
    
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    await db.team_members.delete_one({"member_id": member_id})
    return {"message": "Team member deleted"}

# ==================== GLOBAL TEAM DIRECTORY & AI EXTRACTION ====================

@router.get("/team/directory")
async def get_team_directory(
    search: Optional[str] = None,
    project_id: Optional[str] = None,
    limit: int = 50,
    user: dict = Depends(get_current_agent)
):
    """
    Get all team members across all projects for the agent.
    This serves as the global supplier/contact directory.
    """
    is_demo = user.get('is_demo', False)
    query = {"agent_id": user['user_id']}
    
    if project_id:
        query["project_id"] = project_id
    
    members = await db.team_members.find(query, {"_id": 0}).to_list(500)
    
    # Deduplicate by company_name + contact_name
    seen = set()
    unique_members = []
    for member in members:
        key = (member.get('company_name', '').lower(), member.get('contact_name', '').lower())
        if key not in seen:
            seen.add(key)
            unique_members.append(member)
    
    # Apply search filter
    if search:
        search_lower = search.lower()
        unique_members = [
            m for m in unique_members 
            if search_lower in (m.get('company_name', '') or '').lower()
            or search_lower in (m.get('contact_name', '') or '').lower()
            or search_lower in (m.get('role', '') or '').lower()
        ]
    
    # Sort by most recently used (created_at descending)
    unique_members.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    return unique_members[:limit]

@router.post("/team/extract-contacts")
async def extract_contacts_from_document(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_agent)
):
    """
    Extract contact information from uploaded document using AI.
    Supports PDF, Word, Excel, and image files.
    Returns structured list of contacts for review before import.
    """
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="AI extraction not available - OpenAI API key not configured")
    
    # Validate file type
    allowed_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.png', '.jpg', '.jpeg', '.webp']
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Save uploaded file temporarily
    temp_dir = "/tmp/contact_extraction"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"{uuid.uuid4().hex}_{file.filename}")
    
    try:
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)
        
        # Extract text/content based on file type
        extracted_text = ""
        images_base64 = []
        
        if file_ext == '.pdf':
            # Convert PDF to images for vision API
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(temp_path)
                for page_num in range(min(doc.page_count, 5)):  # Limit to first 5 pages
                    page = doc[page_num]
                    # Render page to image
                    mat = fitz.Matrix(2, 2)  # 2x zoom for better quality
                    pix = page.get_pixmap(matrix=mat)
                    img_data = pix.tobytes("png")
                    images_base64.append(base64.b64encode(img_data).decode('utf-8'))
                doc.close()
            except Exception as e:
                logger.error(f"PDF processing error: {e}")
                raise HTTPException(status_code=500, detail="Failed to process PDF")
        
        elif file_ext in ['.png', '.jpg', '.jpeg', '.webp']:
            with open(temp_path, "rb") as f:
                images_base64.append(base64.b64encode(f.read()).decode('utf-8'))
        
        elif file_ext in ['.doc', '.docx', '.xls', '.xlsx']:
            # For Office documents, we'll use a simpler text extraction
            # In production, you'd use python-docx or openpyxl
            try:
                if file_ext == '.docx':
                    from docx import Document
                    doc = Document(temp_path)
                    extracted_text = "\n".join([para.text for para in doc.paragraphs])
                elif file_ext in ['.xlsx', '.xls']:
                    import openpyxl
                    wb = openpyxl.load_workbook(temp_path, data_only=True)
                    texts = []
                    for sheet in wb.worksheets[:3]:  # First 3 sheets
                        for row in sheet.iter_rows(max_row=100, values_only=True):
                            row_text = " | ".join([str(cell) for cell in row if cell])
                            if row_text.strip():
                                texts.append(row_text)
                    extracted_text = "\n".join(texts)
            except ImportError:
                # Fallback: treat as binary and let AI try to extract
                logger.warning(f"Office document libraries not available for {file_ext}")
                raise HTTPException(status_code=400, detail="Office document processing not available")
        
        # Use OpenAI to extract contacts
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        extraction_prompt = """Analyze this document and extract all contact information for companies, suppliers, or individuals.

For each contact found, extract:
- company_name: The company or business name
- contact_name: The person's full name (if available)
- role: Their job title or function (e.g., "Plumber", "Architect", "Sales Manager")
- email: Email address
- phone: Phone number(s)
- website: Website URL
- address: Full address

Rules:
1. Only extract real contacts that appear to be suppliers, contractors, or business partners
2. Ignore generic text that isn't a contact
3. Deduplicate contacts - if the same company appears multiple times, merge into one complete record
4. Accept partial data - not all fields need to be present
5. For role, try to infer from context if not explicitly stated

Return a JSON array of contacts. Example:
[
  {
    "company_name": "SaniTech SA",
    "contact_name": "Pierre Dupont",
    "role": "Plumber",
    "email": "contact@sanitech.ch",
    "phone": "+41 79 123 45 67",
    "website": "https://sanitech.ch",
    "address": "Rue du Lac 15, 1200 Genève"
  }
]

If no contacts are found, return an empty array: []"""

        messages = [{"role": "system", "content": extraction_prompt}]
        
        if images_base64:
            # Use vision model for images/PDFs
            content_parts = [{"type": "text", "text": "Extract all contact information from this document:"}]
            for img_b64 in images_base64[:5]:  # Limit images
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img_b64}", "detail": "high"}
                })
            messages.append({"role": "user", "content": content_parts})
        else:
            # Text-only extraction
            messages.append({
                "role": "user", 
                "content": f"Extract all contact information from this document:\n\n{extracted_text[:10000]}"
            })
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=4000,
            temperature=0.1
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Parse JSON from response
        import json
        try:
            # Try to extract JSON from response (it might be wrapped in markdown)
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text
            
            contacts = json.loads(json_str)
            
            if not isinstance(contacts, list):
                contacts = [contacts] if contacts else []
            
            # Validate and clean contacts
            valid_contacts = []
            for contact in contacts:
                if isinstance(contact, dict) and (contact.get('company_name') or contact.get('contact_name')):
                    valid_contacts.append({
                        "company_name": contact.get('company_name', ''),
                        "contact_name": contact.get('contact_name', ''),
                        "role": contact.get('role', ''),
                        "email": contact.get('email', ''),
                        "phone": contact.get('phone', ''),
                        "website": contact.get('website', ''),
                        "address": contact.get('address', ''),
                        "confidence": 0.85  # Default confidence
                    })
            
            return {
                "contacts": valid_contacts,
                "source_filename": file.filename,
                "extraction_count": len(valid_contacts)
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response: {e}\nResponse: {response_text[:500]}")
            return {
                "contacts": [],
                "source_filename": file.filename,
                "extraction_count": 0,
                "error": "Could not extract contacts from document"
            }
    
    finally:
        # Cleanup temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

class BulkContactsRequest(BaseModel):
    contacts: List[dict]

@router.post("/projects/{project_id}/team/bulk")
async def create_team_members_bulk(
    project_id: str, 
    request: BulkContactsRequest,
    user: dict = Depends(get_current_agent)
):
    """
    Bulk import multiple team members to a project.
    Used after AI extraction review.
    """
    is_demo = user.get('is_demo', False)
    
    project = await db.projects.find_one(
        {"project_id": project_id, "agent_id": user['user_id']},
        {"_id": 0}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    created_members = []
    skipped_count = 0
    
    for contact in request.contacts:
        # Skip if no company name or contact name
        if not contact.get('company_name') and not contact.get('contact_name'):
            skipped_count += 1
            continue
        
        # Check for duplicates in this project
        existing = await db.team_members.find_one({
            "project_id": project_id,
            "agent_id": user['user_id'],
            "company_name": contact.get('company_name', ''),
            "contact_name": contact.get('contact_name', ''),
            "is_demo": is_demo
        })
        if existing:
            skipped_count += 1
            continue
        
        member_id = f"member_{uuid.uuid4().hex[:12]}"
        member_doc = {
            "member_id": member_id,
            "project_id": project_id,
            "agent_id": user['user_id'],
            "company_name": contact.get('company_name', ''),
            "contact_name": contact.get('contact_name', ''),
            "role": contact.get('role', 'Supplier'),
            "email": contact.get('email'),
            "phone": contact.get('phone'),
            "website": contact.get('website'),
            "address": contact.get('address'),
            "notes": contact.get('notes'),
            "is_demo": is_demo,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.team_members.insert_one(member_doc)
        created_members.append(member_doc)
    
    return {
        "created": len(created_members),
        "skipped": skipped_count,
        "members": [{k: v for k, v in m.items() if k != '_id'} for m in created_members]
    }

