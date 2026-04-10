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

# ==================== TIMELINE VIEW ENDPOINT ====================

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

