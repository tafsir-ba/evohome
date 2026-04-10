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

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

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

# ==================== DOCUMENTS, AI EXTRACTION, PDF GENERATION ====================

# ==================== UNIFIED DOCUMENT ENDPOINTS ====================
# Single source of truth: db.documents collection

@router.post("/documents/upload")
async def upload_document(
    request: Request,
    client_id: str = Form(...),
    file: UploadFile = File(...),
    doc_type: str = "quote",
    user: dict = Depends(get_current_agent)
):
    """
    Upload a PDF for extraction ONLY - does NOT create a document.
    Returns extracted data for user preview/editing.
    Call POST /documents/create to actually create the document after user confirmation.
    
    This follows the draft-first architecture:
    input → extraction → preview → edit → confirm → final object
    """
    # Rate limit: 10 AI extractions per minute per user
    rate_limit_check(request, "ai_extraction")
    
    is_demo = user.get('is_demo', False)
    
    # Validate document type
    if doc_type not in ['quote', 'invoice']:
        doc_type = 'quote'
    
    # Verify client exists
    client = await db.clients.find_one(
        {"client_id": client_id, "agent_id": user['user_id']},
        {"_id": 0}
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Validate file
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # File size limit: 10MB max for PDF uploads
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413, 
            detail=f"File too large. Maximum size is 10MB (received {len(content) / 1024 / 1024:.1f}MB)"
        )
    
    # Save file temporarily for extraction
    file_id = uuid.uuid4().hex[:12]
    filename = f"{file_id}_{file.filename}"
    file_path = UPLOAD_DIR / filename
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Run AI extraction
    extraction = await extract_document_from_pdf(str(file_path), file.filename)
    
    # Calculate total from line items if not extracted
    items_total = sum(item.get('total', 0) for item in extraction.get('items', []))
    amount = extraction.get('amount') or items_total or 0
    
    # Return extraction preview (NO database write!)
    # The frontend will display this for user review, then call /documents/create
    preview_data = {
        "preview_id": file_id,  # Used to reference the uploaded file later
        "type": doc_type,
        "client_id": client_id,
        "project_id": client['project_id'],
        "unit_reference": client['unit_reference'],
        "title": extraction.get('title', 'Untitled Document'),
        "amount": amount,
        "items": extraction.get('items', []),
        "supplier_name": extraction.get('supplier_name'),
        "summary": extraction.get('description', ''),
        "pdf_filename": file.filename,
        "pdf_path": str(file_path),
        "ai_extraction_confidence": extraction.get('confidence', 'low'),
        "extraction_warning": extraction.get('extraction_failed', False) or extraction.get('amount') is None,
        "is_preview": True  # Flag to indicate this is preview data, not a saved document
    }
    
    return preview_data


@router.post("/documents/create")
async def create_document_from_preview(
    request: Request,
    user: dict = Depends(get_current_agent)
):
    """
    Create a document from previewed extraction data.
    This is called AFTER the user reviews and confirms the extraction.
    
    Expected body:
    {
        "preview_id": "...",  # From the upload preview
        "type": "quote" | "invoice",
        "client_id": "...",
        "title": "...",
        "amount": 1234.56,
        "items": [...],
        "supplier_name": "...",
        "summary": "...",
        "notes": "...",
        "due_date": "2026-04-01",
        "pdf_path": "..."  # Path to the uploaded PDF
    }
    """
    body = await request.json()
    is_demo = user.get('is_demo', False)
    
    doc_type = body.get('type', 'quote')
    if doc_type not in ['quote', 'invoice']:
        doc_type = 'quote'
    
    client_id = body.get('client_id')
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id is required")
    
    # Verify client exists
    client = await db.clients.find_one(
        {"client_id": client_id, "agent_id": user['user_id']},
        {"_id": 0}
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Generate document number
    if doc_type == 'invoice':
        count = await db.documents.count_documents({"agent_id": user['user_id'], "type": "invoice"})
        doc_number = f"INV-{datetime.now().year}-{str(count + 1).zfill(4)}"
    else:
        count = await db.documents.count_documents({"agent_id": user['user_id'], "type": "quote"})
        doc_number = f"QT-{datetime.now().year}-{str(count + 1).zfill(4)}"
    
    doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    
    # Parse due date
    due_date = None
    if body.get('due_date'):
        try:
            due_date = datetime.fromisoformat(body['due_date'].replace('Z', '+00:00')).isoformat()
        except (ValueError, AttributeError):
            due_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    elif doc_type == 'invoice':
        due_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    
    doc = {
        "document_id": doc_id,
        "document_number": doc_number,
        "type": doc_type,
        "status": "Draft",
        "agent_id": user['user_id'],  # Required - ownership scoping
        "client_id": client_id,
        "buyer_id": client.get('buyer_id'),
        "project_id": client['project_id'],
        "unit_reference": client['unit_reference'],
        "title": body.get('title', 'Untitled Document'),
        "amount": float(body.get('amount', 0)),
        "items": body.get('items', []),
        "currency": "CHF",
        "supplier_name": body.get('supplier_name'),
        "notes": body.get('notes'),
        "summary": body.get('summary', ''),
        "hero_image_url": None,
        "hero_image_path": None,
        "change_request_comment": None,
        "pdf_filename": body.get('pdf_filename'),
        "pdf_path": body.get('pdf_path'),
        "ai_extraction_confidence": body.get('ai_extraction_confidence', 'low'),
        "parent_document_id": None,
        "due_date": due_date,
        "paid_date": None,
        "is_demo": is_demo,
        "created_at": now,
        "updated_at": now
    }
    
    await db.documents.insert_one(doc)
    
    result = await db.documents.find_one({"document_id": doc_id}, {"_id": 0})
    
    logger.info(f"Document created: {doc_id} ({doc_type}) by user {user['user_id']}")
    
    return result

@router.post("/documents/{document_id}/reupload")
async def reupload_document_pdf(
    document_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_agent)
):
    """Upload a revised PDF for an existing document with version tracking"""
    is_demo = user.get('is_demo', False)
    query = {"document_id": document_id, "agent_id": user['user_id']}
    doc = await db.documents.find_one(query, {"_id": 0})
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Allow revision in Draft, Sent, or Change Requested status
    if doc['status'] not in ['Draft', 'Sent', 'Change Requested']:
        raise HTTPException(status_code=400, detail="Cannot revise document in current status")
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    now = datetime.now(timezone.utc).isoformat()
    current_version = doc.get('version', 1)
    
    # Archive current version in version history
    version_history = doc.get('version_history', []) or []
    if doc.get('pdf_path'):
        version_history.append({
            'version': current_version,
            'pdf_path': doc['pdf_path'],
            'pdf_filename': doc.get('pdf_filename'),
            'title': doc.get('title'),
            'amount': doc.get('amount'),
            'archived_at': now,
            'archived_by': user['user_id']
        })
    
    # Save new file
    file_id = uuid.uuid4().hex[:12]
    filename = f"{file_id}_{file.filename}"
    file_path = UPLOAD_DIR / filename
    
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Run AI extraction on new PDF
    extraction = await extract_document_from_pdf(str(file_path), file.filename)
    
    items_total = sum(item.get('total', 0) for item in extraction.get('items', []))
    amount = extraction.get('amount') or items_total or doc['amount']
    
    update_data = {
        "title": extraction.get('title') or doc['title'],
        "amount": amount,
        "items": extraction.get('items') if extraction.get('items') else doc['items'],
        "supplier_name": extraction.get('supplier_name') or doc.get('supplier_name'),
        "pdf_filename": file.filename,
        "pdf_path": str(file_path),
        "ai_extraction_confidence": extraction.get('confidence', 'low'),
        "updated_at": now,
        "version": current_version + 1,
        "version_history": version_history,
        # Reset to Draft if it was Change Requested
        "status": "Draft" if doc['status'] == 'Change Requested' else doc['status'],
        # Clear change request comment after revision
        "change_request_comment": None
    }
    
    await db.documents.update_one(query, {"$set": update_data})
    
    result = await db.documents.find_one(query, {"_id": 0})
    result['extraction_warning'] = extraction.get('extraction_failed', False) or extraction.get('amount') is None
    
    return result

@router.put("/documents/{document_id}")
async def update_document(document_id: str, data: DocumentUpdate, user: dict = Depends(get_current_agent)):
    """Update document with edited extraction data or reference changes"""
    is_demo = user.get('is_demo', False)
    query = {"document_id": document_id, "agent_id": user['user_id']}
    doc = await db.documents.find_one(query, {"_id": 0})
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Cannot edit finalized documents (Approved, Rejected, Paid)
    if doc['status'] in ['Approved', 'Rejected', 'Paid']:
        raise HTTPException(status_code=400, detail=f"Cannot edit document with status '{doc['status']}'. Create a new version instead.")
    
    update_data = {}
    
    if data.title is not None:
        update_data['title'] = data.title
    if data.amount is not None:
        update_data['amount'] = data.amount
    if data.supplier_name is not None:
        update_data['supplier_name'] = data.supplier_name
    if data.notes is not None:
        update_data['notes'] = data.notes
    if data.summary is not None:
        update_data['summary'] = data.summary
    if data.hero_image_url is not None:
        update_data['hero_image_url'] = data.hero_image_url
    if data.items is not None:
        update_data['items'] = [item.model_dump() for item in data.items]
        if data.amount is None:
            update_data['amount'] = sum(item.total for item in data.items)
    
    # Handle reference changes (client, project, unit)
    if data.project_id is not None and data.project_id != doc.get('project_id'):
        # Validate project exists and belongs to agent
        project = await db.projects.find_one({
            "project_id": data.project_id, 
            "agent_id": user['user_id'], 
            "is_demo": is_demo
        })
        if not project:
            raise HTTPException(status_code=400, detail="Invalid project")
        update_data['project_id'] = data.project_id
    
    if data.client_id is not None and data.client_id != doc.get('client_id'):
        # Validate client exists and belongs to agent
        client = await db.clients.find_one({
            "client_id": data.client_id,
            "agent_id": user['user_id'],
            "is_demo": is_demo
        })
        if not client:
            raise HTTPException(status_code=400, detail="Invalid client")
        update_data['client_id'] = data.client_id
    
    if data.unit_id is not None:
        if data.unit_id == "":
            # Clear unit assignment
            update_data['unit_id'] = None
            update_data['unit_reference'] = "General"
        else:
            # Validate unit exists and belongs to the project
            target_project_id = data.project_id or doc.get('project_id')
            unit = await db.units.find_one({
                "unit_id": data.unit_id,
                "project_id": target_project_id,
                "is_demo": is_demo
            })
            if not unit:
                raise HTTPException(status_code=400, detail="Invalid unit for this project")
            update_data['unit_id'] = data.unit_id
            update_data['unit_reference'] = unit.get('unit_reference', unit.get('name', 'Unit'))
    
    update_data['updated_at'] = datetime.now(timezone.utc).isoformat()
    
    await db.documents.update_one(query, {"$set": update_data})
    return await db.documents.find_one(query, {"_id": 0})

@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, force: bool = False, user: dict = Depends(get_current_agent)):
    """Delete a document. 
    By default only allowed for Draft status.
    Use force=true to delete documents in any status (for agents only).
    """
    is_demo = user.get('is_demo', False)
    query = {"document_id": document_id, "agent_id": user['user_id']}
    doc = await db.documents.find_one(query, {"_id": 0})
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Only allow deletion of drafts unless force=true
    if doc['status'] != 'Draft' and not force:
        raise HTTPException(
            status_code=400, 
            detail="Can only delete documents in Draft status. Use force=true to delete sent documents, or archive them instead."
        )
    
    # Delete the document
    await db.documents.delete_one(query)
    
    # Clean up associated files if any
    if doc.get('pdf_path') and os.path.exists(doc['pdf_path']):
        try:
            os.remove(doc['pdf_path'])
        except Exception as e:
            logger.warning(f"Failed to delete PDF file: {e}")
    
    if doc.get('hero_image_url') and doc['hero_image_url'].startswith('/uploads/'):
        try:
            file_path = os.path.join(UPLOAD_DIR, doc['hero_image_url'].replace('/uploads/', ''))
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"Failed to delete hero image: {e}")
    
    logger.info(f"Document {document_id} deleted by {user['user_id']} (force={force})")
    
    return {"message": "Document deleted successfully"}

@router.post("/documents/{document_id}/revert-to-draft")
async def revert_document_to_draft(document_id: str, user: dict = Depends(get_current_agent)):
    """Revert a document back to Draft status.
    Allowed for: Sent, Change Requested statuses.
    Not allowed for: Approved, Rejected, Paid.
    """
    is_demo = user.get('is_demo', False)
    query = {"document_id": document_id, "agent_id": user['user_id']}
    doc = await db.documents.find_one(query, {"_id": 0})
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Cannot revert finalized documents
    if doc['status'] in ['Approved', 'Rejected', 'Paid']:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot revert document with status '{doc['status']}'. This status is final."
        )
    
    if doc['status'] == 'Draft':
        return {"message": "Document is already in Draft status", "status": "Draft"}
    
    # Update status to Draft
    await db.documents.update_one(
        query,
        {"$set": {"status": "Draft", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    logger.info(f"Document {document_id} reverted to Draft by {user['user_id']}")
    
    return {"message": "Document reverted to Draft", "status": "Draft"}

@router.get("/documents", response_model=List[DocumentResponse])
async def get_documents(
    doc_type: Optional[str] = None,
    status: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get documents for current user - ownership scoped, schema validated"""
    query = {}
    
    if user['role'] == 'agent':
        query["agent_id"] = user['user_id']
    else:
        # Buyer: get documents via client relationship
        clients = await db.clients.find(
            {"buyer_id": user['user_id']},
            {"_id": 0, "client_id": 1}
        ).to_list(100)
        client_ids = [c['client_id'] for c in clients]
        query["client_id"] = {"$in": client_ids}
    
    if doc_type:
        query["type"] = doc_type
    if status:
        query["status"] = status
    
    docs = await db.documents.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return docs

@router.get("/documents/{document_id}")
async def get_document(document_id: str, user: dict = Depends(get_current_user)):
    """Get single document"""
    is_demo = user.get('is_demo', False)
    query = {"document_id": document_id}
    
    if user['role'] == 'agent':
        query["agent_id"] = user['user_id']
    else:
        clients = await db.clients.find(
            {"buyer_id": user['user_id']},
            {"_id": 0, "client_id": 1}
        ).to_list(100)
        client_ids = [c['client_id'] for c in clients]
        query["client_id"] = {"$in": client_ids}
    
    doc = await db.documents.find_one(query, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Include client and project info
    client = await db.clients.find_one({"client_id": doc['client_id']}, {"_id": 0})
    project = await db.projects.find_one({"project_id": doc['project_id']}, {"_id": 0})
    
    return {**doc, "client": client, "project": project}

@router.get("/documents/{document_id}/source-pdf")
async def get_document_source_pdf(document_id: str, user: dict = Depends(get_current_user)):
    """Get the original uploaded PDF for a document"""
    is_demo = user.get('is_demo', False)
    
    if user.get('role') == 'agent':
        query = {"document_id": document_id, "agent_id": user['user_id']}
    else:
        clients = await db.clients.find(
            {"buyer_id": user['user_id']},
            {"_id": 0, "client_id": 1}
        ).to_list(100)
        client_ids = [c['client_id'] for c in clients]
        query = {"document_id": document_id, "client_id": {"$in": client_ids}}
    
    doc = await db.documents.find_one(query, {"_id": 0})
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not doc.get('pdf_path') or not os.path.exists(doc['pdf_path']):
        raise HTTPException(status_code=404, detail="Source PDF not found")
    
    return FileResponse(
        doc['pdf_path'],
        media_type="application/pdf",
        filename=doc.get('pdf_filename', f"document_{document_id}.pdf")
    )

@router.post("/documents/{document_id}/hero-image")
async def upload_hero_image(
    document_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_agent)
):
    """Upload a hero/banner image for a document"""
    is_demo = user.get('is_demo', False)
    query = {"document_id": document_id, "agent_id": user['user_id']}
    doc = await db.documents.find_one(query, {"_id": 0})
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Validate image file
    allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, and WebP images are allowed")
    
    # Delete old hero image if exists
    if doc.get('hero_image_path') and os.path.exists(doc['hero_image_path']):
        try:
            os.remove(doc['hero_image_path'])
        except OSError:
            pass
    
    # Save new image
    file_ext = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
    image_filename = f"hero_{document_id}_{uuid.uuid4().hex[:8]}.{file_ext}"
    image_path = UPLOAD_DIR / image_filename
    
    content = await file.read()
    with open(image_path, "wb") as f:
        f.write(content)
    
    # Generate URL for the image
    hero_image_url = f"/api/documents/{document_id}/hero-image"
    
    await db.documents.update_one(query, {
        "$set": {
            "hero_image_url": hero_image_url,
            "hero_image_path": str(image_path),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
    })
    
    return {"hero_image_url": hero_image_url}

@router.get("/documents/{document_id}/hero-image")
async def get_hero_image(document_id: str, user: dict = Depends(get_current_user)):
    """Get the hero image for a document"""
    is_demo = user.get('is_demo', False)
    
    if user.get('role') == 'agent':
        query = {"document_id": document_id, "agent_id": user['user_id']}
    else:
        clients = await db.clients.find(
            {"buyer_id": user['user_id']},
            {"_id": 0, "client_id": 1}
        ).to_list(100)
        client_ids = [c['client_id'] for c in clients]
        query = {"document_id": document_id, "client_id": {"$in": client_ids}}
    
    doc = await db.documents.find_one(query, {"_id": 0})
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not doc.get('hero_image_path') or not os.path.exists(doc['hero_image_path']):
        raise HTTPException(status_code=404, detail="Hero image not found")
    
    # Determine media type
    file_ext = doc['hero_image_path'].split('.')[-1].lower()
    media_types = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}
    media_type = media_types.get(file_ext, 'image/jpeg')
    
    return FileResponse(doc['hero_image_path'], media_type=media_type)

@router.delete("/documents/{document_id}/hero-image")
async def delete_hero_image(document_id: str, user: dict = Depends(get_current_agent)):
    """Delete the hero image from a document"""
    is_demo = user.get('is_demo', False)
    query = {"document_id": document_id, "agent_id": user['user_id']}
    doc = await db.documents.find_one(query, {"_id": 0})
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete file if exists
    if doc.get('hero_image_path') and os.path.exists(doc['hero_image_path']):
        try:
            os.remove(doc['hero_image_path'])
        except OSError:
            pass
    
    await db.documents.update_one(query, {
        "$set": {
            "hero_image_url": None,
            "hero_image_path": None,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
    })
    
    return {"message": "Hero image deleted"}

@router.get("/documents/{document_id}/qr-code")
async def get_document_qr_code(document_id: str, user: dict = Depends(get_current_user)):
    """Get Swiss QR payment code for an invoice"""
    is_demo = user.get('is_demo', False)
    
    if user.get('role') == 'agent':
        query = {"document_id": document_id, "agent_id": user['user_id']}
    else:
        clients = await db.clients.find(
            {"buyer_id": user['user_id']},
            {"_id": 0, "client_id": 1}
        ).to_list(100)
        client_ids = [c['client_id'] for c in clients]
        query = {"document_id": document_id, "client_id": {"$in": client_ids}}
    
    doc = await db.documents.find_one(query, {"_id": 0})
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if doc['type'] != 'invoice':
        raise HTTPException(status_code=400, detail="QR code only available for invoices")
    
    # Get buyer name
    client = await db.clients.find_one({"client_id": doc['client_id']}, {"_id": 0})
    buyer_name = client.get('name', 'Client') if client else 'Client'
    
    # Get agent settings for IBAN
    agent = await db.users.find_one({"user_id": doc['agent_id']}, {"_id": 0})
    agent_settings = agent.get('settings', {}) if agent else {}
    billing_info = agent_settings.get('billing', {})
    
    # Generate QR code as base64 using agent's billing info or defaults
    qr_base64 = generate_swiss_qr_code_base64(
        amount=doc['amount'],
        reference=doc['document_number'],
        buyer_name=buyer_name,
        iban=billing_info.get('iban'),
        creditor_name=billing_info.get('company_name') or agent_settings.get('company_name'),
        creditor_address=billing_info.get('address'),
        creditor_pcode=billing_info.get('postal_code'),
        creditor_city=billing_info.get('city')
    )
    
    if not qr_base64:
        raise HTTPException(status_code=500, detail="Failed to generate QR code")
    
    # Get the IBAN used (from agent settings or default)
    iban_used = billing_info.get('iban') or DEFAULT_IBAN
    company_used = billing_info.get('company_name') or agent_settings.get('company_name') or DEFAULT_COMPANY_NAME
    
    return {
        "qr_code_svg_base64": qr_base64,
        "amount": doc['amount'],
        "currency": doc['currency'],
        "document_number": doc['document_number'],
        "payment_info": {
            "beneficiary": company_used,
            "iban": iban_used,
            "reference": doc['document_number']
        }
    }

@router.post("/documents/{document_id}/send")
async def send_document(document_id: str, user: dict = Depends(get_current_agent)):
    """
    Send document to buyer (transition from Draft/Change Requested to Sent).
    Returns detailed status including email delivery result.
    """
    is_demo = user.get('is_demo', False)
    query = {"document_id": document_id, "agent_id": user['user_id']}
    doc = await db.documents.find_one(query, {"_id": 0})
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Validate client exists
    client = await db.clients.find_one({"client_id": doc.get('client_id')}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=400, detail="Client not found. Please assign a client to this document first.")
    
    # Validate client has email
    if not client.get('email'):
        raise HTTPException(status_code=400, detail="Client has no email address. Please update client details first.")
    
    # Enforce state machine
    if not validate_transition(doc['type'], doc['status'], 'Sent'):
        raise HTTPException(status_code=400, detail=f"Cannot send document from status: {doc['status']}")
    
    now = datetime.now(timezone.utc).isoformat()
    
    await db.documents.update_one(query, {
        "$set": {
            "status": "Sent",
            "sent_at": now,
            "change_request_comment": None,
            "updated_at": now
        }
    })
    
    # Get related info for notifications
    project = await db.projects.find_one({"project_id": doc.get('project_id')}, {"_id": 0})
    agent_settings = user.get('settings', {})
    agent_profile = user.get('profile', {})
    
    # Track delivery status
    delivery_status = {
        "notification_created": False,
        "websocket_sent": False,
        "email_sent": False,
        "email_error": None
    }
    
    # Create notification for buyer if exists
    buyer_id = doc.get('buyer_id') or client.get('buyer_id')
    if buyer_id:
        try:
            await create_notification(
                user_id=buyer_id,
                title=f"New {doc['type'].title()} Received",
                message=f"You have a new {doc['type']} for {doc['title']} - CHF {doc['amount']:,.2f}",
                notification_type="document_sent",
                link="/buyer",
                is_demo=is_demo
            )
            delivery_status["notification_created"] = True
        except Exception as e:
            logger.warning(f"Failed to create notification: {e}")
        
        # Send real-time update via WebSocket
        try:
            await notify_realtime(
                [buyer_id],
                "document_sent",
                {
                    "document_id": document_id,
                    "type": doc['type'],
                    "title": doc['title'],
                    "amount": doc['amount']
                }
            )
            delivery_status["websocket_sent"] = True
        except Exception as e:
            logger.warning(f"Failed to send WebSocket notification: {e}")
    
    # Send email notification to buyer
    if client.get('email'):
        try:
            email_result = await send_notification_email(
                "document_sent",
                client['email'],
                {
                    "doc_type": doc['type'],
                    "buyer_name": client.get('name', 'there'),
                    "agent_name": agent_profile.get('display_name') or user.get('name', 'Your agent'),
                    "company_name": agent_settings.get('company_name', 'the agency'),
                    "agent_email": agent_profile.get('contact_email', ''),
                    "agent_phone": agent_profile.get('contact_phone', ''),
                    "title": doc.get('title', 'Document'),
                    "summary": doc.get('summary', ''),
                    "currency": doc.get('currency', 'CHF'),
                    "amount": doc.get('amount', 0),
                    "project_name": project.get('name', 'N/A') if project else 'N/A',
                    "unit_reference": doc.get('unit_reference', 'N/A')
                }
            )
            # Check if email was sent - status is "success" on success, "error" or "skipped" on failure
            if isinstance(email_result, dict):
                delivery_status["email_sent"] = email_result.get("status") == "success"
                if not delivery_status["email_sent"]:
                    delivery_status["email_error"] = email_result.get("error") or email_result.get("reason", "Unknown error")
            else:
                delivery_status["email_sent"] = True
        except Exception as e:
            logger.warning(f"Failed to send email notification: {e}")
            delivery_status["email_error"] = str(e)
    
    # Return detailed response
    return {
        "message": "Document sent successfully",
        "status": "Sent",
        "document_id": document_id,
        "recipient": {
            "name": client.get('name'),
            "email": client.get('email')
        },
        "delivery": delivery_status,
        "warnings": [] if delivery_status["email_sent"] else [
            f"Email may not have been delivered: {delivery_status['email_error'] or 'Unknown reason'}"
        ]
    }

@router.post("/documents/{document_id}/action")
async def document_action(document_id: str, action_data: DocumentAction, user: dict = Depends(get_current_user)):
    """Perform action on document (buyer or agent)"""
    is_demo = user.get('is_demo', False)
    action = action_data.action
    
    # Get document
    if user['role'] == 'agent':
        query = {"document_id": document_id, "agent_id": user['user_id']}
    else:
        clients = await db.clients.find(
            {"buyer_id": user['user_id']},
            {"_id": 0, "client_id": 1}
        ).to_list(100)
        client_ids = [c['client_id'] for c in clients]
        query = {"document_id": document_id, "client_id": {"$in": client_ids}}
    
    doc = await db.documents.find_one(query, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Handle different actions based on document type and user role
    if action == 'approve' and doc['type'] == 'quote' and user['role'] == 'buyer':
        if not validate_transition('quote', doc['status'], 'Approved'):
            raise HTTPException(status_code=400, detail="Cannot approve quote in current status")
        
        await db.documents.update_one(
            {"document_id": document_id},
            {"$set": {"status": "Approved", "updated_at": now}}
        )
        
        # Get agent info for email
        agent = await db.users.find_one({"user_id": doc.get('agent_id')}, {"_id": 0, "email": 1, "name": 1})
        
        # Notify agent
        if doc.get('agent_id'):
            await create_notification(
                user_id=doc['agent_id'],
                title="Quote Approved",
                message=f"{user.get('name', 'Buyer')} approved quote {doc['document_number']}",
                notification_type="quote_approved",
                link=f"/agent/documents/{document_id}",
                is_demo=is_demo
            )
            # Send real-time update via WebSocket
            await notify_realtime(
                [doc['agent_id']],
                "quote_approved",
                {
                    "document_id": document_id,
                    "title": doc['title'],
                    "buyer_name": user.get('name', 'Buyer')
                }
            )
            
            # Send email notification to agent (instant - critical event)
            if agent and agent.get('email'):
                await send_notification_email(
                    "quote_approved",
                    agent['email'],
                    {
                        "buyer_name": user.get('name', 'Your client'),
                        "document_number": doc.get('document_number', ''),
                        "document_id": document_id,
                        "title": doc.get('title', 'Quote'),
                        "currency": doc.get('currency', 'CHF'),
                        "amount": doc.get('amount', 0)
                    }
                )
        
        return {"message": "Quote approved", "status": "Approved"}
    
    elif action == 'reject' and doc['type'] == 'quote' and user['role'] == 'buyer':
        if not validate_transition('quote', doc['status'], 'Rejected'):
            raise HTTPException(status_code=400, detail="Cannot reject quote in current status")
        
        await db.documents.update_one(
            {"document_id": document_id},
            {"$set": {"status": "Rejected", "updated_at": now}}
        )
        
        return {"message": "Quote rejected", "status": "Rejected"}
    
    elif action == 'request_change' and doc['type'] == 'quote' and user['role'] == 'buyer':
        if not action_data.comment:
            raise HTTPException(status_code=400, detail="Comment required for change request")
        
        if not validate_transition('quote', doc['status'], 'Change Requested'):
            raise HTTPException(status_code=400, detail="Cannot request changes in current status")
        
        await db.documents.update_one(
            {"document_id": document_id},
            {"$set": {
                "status": "Change Requested",
                "change_request_comment": action_data.comment,
                "updated_at": now
            }}
        )
        
        # Notify agent
        if doc.get('agent_id'):
            await create_notification(
                user_id=doc['agent_id'],
                title="Change Requested",
                message=f"Changes requested for quote {doc['document_number']}",
                notification_type="change_requested",
                link=f"/agent/documents/{document_id}",
                metadata={"comment": action_data.comment},
                is_demo=is_demo
            )
            
            # Send email notification to agent (instant - critical event)
            agent = await db.users.find_one({"user_id": doc.get('agent_id')}, {"_id": 0, "email": 1})
            if agent and agent.get('email'):
                await send_notification_email(
                    "change_requested",
                    agent['email'],
                    {
                        "buyer_name": user.get('name', 'Your client'),
                        "document_number": doc.get('document_number', ''),
                        "document_id": document_id,
                        "title": doc.get('title', 'Quote'),
                        "comment": action_data.comment
                    }
                )
        
        return {"message": "Change requested", "status": "Change Requested"}
    
    elif action == 'request_change' and doc['type'] == 'invoice' and user['role'] == 'buyer':
        if not action_data.comment:
            raise HTTPException(status_code=400, detail="Comment required for change request")
        
        if not validate_transition('invoice', doc['status'], 'Change Requested'):
            raise HTTPException(status_code=400, detail="Cannot request changes in current status")
        
        await db.documents.update_one(
            {"document_id": document_id},
            {"$set": {
                "status": "Change Requested",
                "change_request_comment": action_data.comment,
                "updated_at": now
            }}
        )
        
        # Notify agent
        if doc.get('agent_id'):
            await create_notification(
                user_id=doc['agent_id'],
                title="Change Requested",
                message=f"Changes requested for invoice {doc['document_number']}",
                notification_type="change_requested",
                link=f"/agent/documents/{document_id}",
                metadata={"comment": action_data.comment},
                is_demo=is_demo
            )
            
            # Send email notification to agent (instant - critical event)
            agent = await db.users.find_one({"user_id": doc.get('agent_id')}, {"_id": 0, "email": 1})
            if agent and agent.get('email'):
                await send_notification_email(
                    "change_requested",
                    agent['email'],
                    {
                        "buyer_name": user.get('name', 'Your client'),
                        "document_number": doc.get('document_number', ''),
                        "document_id": document_id,
                        "title": doc.get('title', 'Invoice'),
                        "comment": action_data.comment
                    }
                )
        
        return {"message": "Change requested", "status": "Change Requested"}
    
    elif action == 'confirm_payment' and doc['type'] == 'invoice' and user['role'] == 'buyer':
        if not validate_transition('invoice', doc['status'], 'Paid'):
            raise HTTPException(status_code=400, detail="Cannot confirm payment in current status")
        
        await db.documents.update_one(
            {"document_id": document_id},
            {"$set": {"status": "Paid", "paid_date": now, "updated_at": now}}
        )
        
        # Notify agent
        if doc.get('agent_id'):
            await create_notification(
                user_id=doc['agent_id'],
                title="Payment Confirmed",
                message=f"Payment confirmed for invoice {doc['document_number']}",
                notification_type="payment_confirmed",
                link=f"/agent/documents/{document_id}",
                is_demo=is_demo
            )
            
            # Send email notification to agent (instant - critical event)
            agent = await db.users.find_one({"user_id": doc.get('agent_id')}, {"_id": 0, "email": 1})
            if agent and agent.get('email'):
                await send_notification_email(
                    "payment_confirmed",
                    agent['email'],
                    {
                        "document_number": doc.get('document_number', ''),
                        "document_id": document_id,
                        "title": doc.get('title', 'Invoice'),
                        "currency": doc.get('currency', 'CHF'),
                        "amount": doc.get('amount', 0)
                    }
                )
        
        return {"message": "Payment confirmed", "status": "Paid"}
    
    elif action == 'convert_to_invoice' and doc['type'] == 'quote' and user['role'] == 'agent':
        if doc['status'] != 'Approved':
            raise HTTPException(status_code=400, detail="Only approved quotes can be converted to invoices")
        
        # ATOMIC: Create new invoice document from quote
        count = await db.documents.count_documents({"agent_id": user['user_id'], "type": "invoice"})
        invoice_number = f"INV-{datetime.now().year}-{str(count + 1).zfill(4)}"
        invoice_id = f"doc_{uuid.uuid4().hex[:12]}"
        
        invoice_doc = {
            "document_id": invoice_id,
            "document_number": invoice_number,
            "type": "invoice",
            "status": "Draft",
            "agent_id": doc['agent_id'],
            "client_id": doc['client_id'],
            "buyer_id": doc.get('buyer_id'),
            "project_id": doc['project_id'],
            "unit_reference": doc['unit_reference'],
            "title": doc['title'],  # Copy from quote
            "amount": doc['amount'],  # Copy from quote
            "items": doc['items'],  # Copy from quote
            "currency": doc['currency'],
            "supplier_name": doc.get('supplier_name'),
            "notes": doc.get('notes'),
            "change_request_comment": None,
            "pdf_filename": None,
            "pdf_path": None,
            "ai_extraction_confidence": None,
            "parent_document_id": document_id,  # Link to source quote
            "due_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "paid_date": None,
            "is_demo": is_demo,
            "created_at": now,
            "updated_at": now
        }
        
        await db.documents.insert_one(invoice_doc)
        
        # Notify buyer
        if doc.get('buyer_id'):
            await create_notification(
                user_id=doc['buyer_id'],
                title="Invoice Ready",
                message=f"Invoice {invoice_number} for CHF {doc['amount']:,.2f} is ready for payment",
                notification_type="invoice_created",
                link="/buyer",
                is_demo=is_demo
            )
        
        return {
            "message": "Invoice created",
            "document_id": invoice_id,
            "document_number": invoice_number
        }
    
    else:
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")

# ==================== TIMELINE ENDPOINT (SINGLE SOURCE) ====================

@router.get("/timeline")
async def get_timeline(user: dict = Depends(get_current_user)):
    """Get unified timeline - ALL documents sorted by created_at - ownership scoped"""
    if user['role'] == 'buyer':
        # Get buyer's clients (ownership scoped)
        clients = await db.clients.find(
            {"buyer_id": user['user_id']},
            {"_id": 0, "client_id": 1, "project_id": 1, "unit_reference": 1}
        ).to_list(100)
        client_ids = [c['client_id'] for c in clients]
        
        if not client_ids:
            return {"documents": [], "project_info": None}
        
        # Get all documents for buyer's clients (not Draft status for buyers)
        # Note: ownership scoped by client_id, not is_demo
        docs = await db.documents.find(
            {"client_id": {"$in": client_ids}, "status": {"$ne": "Draft"}},
            {"_id": 0}
        ).sort("created_at", -1).to_list(100)
        
        # Get project info
        project_id = clients[0]['project_id'] if clients else None
        project = await db.projects.find_one({"project_id": project_id}, {"_id": 0}) if project_id else None
        
        if project and clients:
            project['unit_reference'] = clients[0].get('unit_reference', '')
        
        # Format for frontend
        timeline_events = []
        for doc in docs:
            timeline_events.append({
                "id": doc['document_id'],
                "type": doc['type'],
                "title": doc['title'],
                "status": doc['status'],
                "amount": doc['amount'],
                "date": doc['updated_at'] or doc['created_at'],
                "dueDate": doc.get('due_date'),
                "items": doc.get('items', []),
                "changeComment": doc.get('change_request_comment'),
                "actionRequired": (doc['type'] == 'quote' and doc['status'] == 'Sent') or 
                                 (doc['type'] == 'invoice' and doc['status'] == 'Sent'),
                "hasSourcePdf": bool(doc.get('pdf_path')),
                "supplierName": doc.get('supplier_name'),
                "documentNumber": doc['document_number'],
                "parentDocumentId": doc.get('parent_document_id'),
                "summary": doc.get('summary', ''),
                "heroImageUrl": doc.get('hero_image_url'),
                "currency": doc.get('currency', 'CHF')
            })
        
        return {"documents": timeline_events, "project_info": project}
    
    else:
        # Agent view - all their documents
        docs = await db.documents.find(
            {"agent_id": user['user_id']},
            {"_id": 0}
        ).sort("created_at", -1).to_list(100)
        
        return {"documents": docs}

# ==================== PDF GENERATION ====================

@router.get("/documents/{document_id}/pdf")
async def get_document_pdf(document_id: str, user: dict = Depends(get_current_user)):
    """Generate and return PDF for document"""
    is_demo = user.get('is_demo', False)
    
    if user['role'] == 'agent':
        query = {"document_id": document_id, "agent_id": user['user_id']}
    else:
        clients = await db.clients.find(
            {"buyer_id": user['user_id']},
            {"_id": 0, "client_id": 1}
        ).to_list(100)
        client_ids = [c['client_id'] for c in clients]
        query = {"document_id": document_id, "client_id": {"$in": client_ids}}
    
    doc = await db.documents.find_one(query, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    client = await db.clients.find_one({"client_id": doc['client_id']}, {"_id": 0})
    project = await db.projects.find_one({"project_id": doc['project_id']}, {"_id": 0})
    
    # Generate PDF
    buffer = BytesIO()
    pdf_doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='CompanyName', fontSize=18, fontName='Helvetica-Bold', spaceAfter=6))
    styles.add(ParagraphStyle(name='DocTitle', fontSize=24, fontName='Helvetica-Bold', spaceAfter=20))
    styles.add(ParagraphStyle(name='SectionTitle', fontSize=12, fontName='Helvetica-Bold', spaceBefore=16, spaceAfter=8))
    styles.add(ParagraphStyle(name='Normal12', fontSize=10, fontName='Helvetica', spaceAfter=4))
    
    elements = []
    
    # Header
    elements.append(Paragraph("UpgradeFlow", styles['CompanyName']))
    elements.append(Paragraph("Real Estate Post-Sale Management", styles['Normal12']))
    elements.append(Spacer(1, 10*mm))
    
    # Title
    doc_type_label = "INVOICE" if doc['type'] == 'invoice' else "QUOTE"
    elements.append(Paragraph(doc_type_label, styles['DocTitle']))
    
    # Info table
    created_date = doc['created_at']
    if isinstance(created_date, str):
        created_date = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
    
    info_data = [
        [f"{doc_type_label[0]}# :", doc['document_number']],
        ["Date:", created_date.strftime("%d %B %Y")],
        ["Status:", doc['status']],
        ["Project:", project['name'] if project else 'N/A'],
        ["Unit:", doc['unit_reference']],
    ]
    
    if doc['type'] == 'invoice' and doc.get('due_date'):
        due_date = doc['due_date']
        if isinstance(due_date, str):
            due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
        info_data.append(["Due Date:", due_date.strftime("%d %B %Y") if isinstance(due_date, datetime) else due_date])
    
    info_table = Table(info_data, colWidths=[35*mm, 100*mm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10*mm))
    
    # Client info
    elements.append(Paragraph("Bill To:", styles['SectionTitle']))
    if client:
        elements.append(Paragraph(client['name'], styles['Normal12']))
        elements.append(Paragraph(client['email'], styles['Normal12']))
    elements.append(Spacer(1, 8*mm))
    
    # Title and description
    elements.append(Paragraph(doc['title'], styles['SectionTitle']))
    elements.append(Spacer(1, 6*mm))
    
    # Line items
    if doc.get('items') and len(doc['items']) > 0:
        table_data = [["Description", "Qty", "Unit Price", "Total"]]
        for item in doc['items']:
            table_data.append([
                item['description'],
                str(item['quantity']),
                f"CHF {item['unit_price']:,.2f}",
                f"CHF {item['total']:,.2f}"
            ])
        
        # Add total row
        table_data.append(["", "", "Total:", f"CHF {doc['amount']:,.2f}"])
        
        items_table = Table(table_data, colWidths=[85*mm, 15*mm, 35*mm, 35*mm])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#e5e7eb')),
            ('FONTNAME', (-2, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
        ]))
        elements.append(items_table)
    else:
        # No line items, just show total
        elements.append(Paragraph(f"Total: CHF {doc['amount']:,.2f}", styles['SectionTitle']))
    
    elements.append(Spacer(1, 10*mm))
    
    # Notes
    if doc.get('notes'):
        elements.append(Paragraph("Notes:", styles['SectionTitle']))
        elements.append(Paragraph(doc['notes'], styles['Normal12']))
    
    # Footer
    elements.append(Spacer(1, 20*mm))
    footer_style = ParagraphStyle(name='Footer', fontSize=8, textColor=colors.grey)
    elements.append(Paragraph("UpgradeFlow SA • Rue du Rhône 1, 1204 Genève • Switzerland", footer_style))
    
    pdf_doc.build(elements)
    buffer.seek(0)
    
    filename = f"{doc['type']}_{doc['document_number']}.pdf"
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

