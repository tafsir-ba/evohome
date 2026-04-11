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
from core.access_control import can_access_project, can_access_client, can_access_vault_doc, can_access_document, get_accessible_project_ids, get_accessible_client_ids, is_agent, is_buyer
from core.rate_limit import rate_limit_check, check_rate_limit
from core.monitoring import capture_exception, capture_auth_failure, capture_payment_error, capture_email_error, capture_ai_error, capture_websocket_error, capture_document_error, ErrorContext
from core.responses import AuthSessionResponse, AuthLoginResponse, AuthRefreshResponse, AuthLogoutResponse, DocumentResponse, VaultDocumentResponse, NotificationResponse, ActivityResponse, ActivitiesListResponse, SuccessResponse

# helpers: no longer needed
from services.email_service import send_email_async, send_notification_email, get_email_template
from services.realtime_service import ws_manager, notify_realtime, send_milestone_notification
from services.qr_service import generate_swiss_qr_code, generate_swiss_qr_code_base64, DEFAULT_IBAN, DEFAULT_COMPANY_NAME
from services.ai_service import extract_document_from_pdf, OPENAI_API_KEY

from models.schemas import *

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter()

# ==================== TEST/DEBUG ENDPOINTS ====================

# ==================== TEST ENDPOINTS ====================

@router.get("/test/email-template/{template_type}")
async def test_email_template(template_type: str):
    """Test endpoint to preview email template HTML (for CTA button validation)"""
    valid_templates = ["document_sent", "quote_approved", "invoice_paid", "payment_confirmed", "project_update", "welcome", "milestone_completed", "change_requested", "new_message"]
    if template_type not in valid_templates:
        raise HTTPException(status_code=400, detail=f"Invalid template. Valid: {valid_templates}")
    
    # Sample data for testing
    test_data = {
        "buyer_name": "Test Buyer",
        "agent_name": "Test Agent",
        "company_name": "Test Company SA",
        "doc_type": "quote",
        "title": "Kitchen Renovation",
        "summary": "Complete kitchen remodel with premium appliances",
        "currency": "CHF",
        "amount": 15000.00,
        "project_name": "Alpine View Residence",
        "unit_reference": "Unit A-101",
        "document_number": "QT-2024-0001",
        "document_id": "test_doc_001",
        "link": "buyer/dashboard",
        # Milestone notification specific data
        "milestone_name": "Foundation Complete",
        "milestone_description": "The foundation has been poured and cured successfully.",
        "progress_percent": 35,
        # Change request specific data
        "comment": "Please review the pricing on item 3.",
        # New message specific data
        "sender_name": "Test Sender",
        "message_preview": "Hello, I wanted to discuss the project timeline..."
    }
    
    subject, html = get_email_template(template_type, test_data)
    
    # Validate CTA button has proper inline styles
    cta_checks = {
        "has_bg_color": "background-color: #2563EB" in html,
        "has_text_color": "color: #FFFFFF" in html,
        "has_inline_style_on_a_tag": 'style="display: inline-block; background-color: #2563EB; color: #FFFFFF' in html
    }
    
    return {
        "template_type": template_type,
        "subject": subject,
        "cta_validation": cta_checks,
        "cta_valid": all(cta_checks.values()),
        "html_preview": html[:2000] + "..." if len(html) > 2000 else html
    }

# ==================== DEMO DATA SEEDING ====================

