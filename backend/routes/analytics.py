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

from helpers import build_query, secure_filename, VALID_TRANSITIONS, validate_transition, SUBSCRIPTION_PLANS, VAULT_CATEGORIES, VAULT_DOC_TYPES
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

# ==================== ANALYTICS ENDPOINTS ====================

# ==================== ANALYTICS ENDPOINTS ====================

@router.get("/analytics")
async def get_analytics(period: str = "month", user: dict = Depends(get_current_agent)):
    """
    Get comprehensive analytics for the agent dashboard.
    Period can be: week, month, quarter, year, all
    """
    is_demo = user.get('is_demo', False)
    agent_id = user['user_id']
    
    # Calculate date filter based on period
    now = datetime.now(timezone.utc)
    date_filter = None
    
    if period == "week":
        date_filter = (now - timedelta(days=7)).isoformat()
    elif period == "month":
        date_filter = (now - timedelta(days=30)).isoformat()
    elif period == "quarter":
        date_filter = (now - timedelta(days=90)).isoformat()
    elif period == "year":
        date_filter = (now - timedelta(days=365)).isoformat()
    # "all" = no date filter
    
    # Build base query
    base_query = {"agent_id": agent_id}
    if date_filter:
        base_query["created_at"] = {"$gte": date_filter}
    
    # Count total documents by type
    total_quotes = await db.documents.count_documents({**base_query, "type": "quote"})
    total_invoices = await db.documents.count_documents({**base_query, "type": "invoice"})
    
    # Quote status breakdown
    quote_approved = await db.documents.count_documents({**base_query, "type": "quote", "status": "Approved"})
    quote_sent = await db.documents.count_documents({**base_query, "type": "quote", "status": "Sent"})
    quote_rejected = await db.documents.count_documents({**base_query, "type": "quote", "status": "Rejected"})
    quote_draft = await db.documents.count_documents({**base_query, "type": "quote", "status": "Draft"})
    quote_change_requested = await db.documents.count_documents({**base_query, "type": "quote", "status": "Change Requested"})
    
    # Invoice status breakdown
    invoice_paid = await db.documents.count_documents({**base_query, "type": "invoice", "status": "Paid"})
    invoice_sent = await db.documents.count_documents({**base_query, "type": "invoice", "status": "Sent"})
    invoice_draft = await db.documents.count_documents({**base_query, "type": "invoice", "status": "Draft"})
    
    # Revenue from paid invoices (no date filter for total revenue)
    revenue_query = {"agent_id": agent_id, "type": "invoice", "status": "Paid"}
    if date_filter:
        revenue_query["paid_date"] = {"$gte": date_filter}
    
    paid_invoices = await db.documents.find(
        revenue_query,
        {"_id": 0, "amount": 1}
    ).to_list(10000)
    total_revenue = sum(inv.get('amount', 0) for inv in paid_invoices)
    
    # Pending amount (invoices sent but not paid)
    pending_invoices = await db.documents.find(
        {**base_query, "type": "invoice", "status": "Sent"},
        {"_id": 0, "amount": 1}
    ).to_list(10000)
    pending_amount = sum(inv.get('amount', 0) for inv in pending_invoices)
    
    # Client count (all time, regardless of period)
    total_clients = await db.clients.count_documents({"agent_id": agent_id})
    
    # Project count (all time)
    total_projects = await db.projects.count_documents({"agent_id": agent_id})
    
    return {
        "totalQuotes": total_quotes,
        "totalInvoices": total_invoices,
        "totalClients": total_clients,
        "totalProjects": total_projects,
        "totalRevenue": total_revenue,
        "pendingAmount": pending_amount,
        "quoteStats": {
            "approved": quote_approved,
            "sent": quote_sent + quote_change_requested,  # Group pending states
            "rejected": quote_rejected,
            "draft": quote_draft
        },
        "invoiceStats": {
            "paid": invoice_paid,
            "sent": invoice_sent,
            "draft": invoice_draft
        }
    }



