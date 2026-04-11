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

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter()

# ==================== DASHBOARD STATISTICS ====================

# ==================== DASHBOARD STATS ====================

@router.get("/stats/agent")
async def get_agent_stats(user: dict = Depends(get_current_agent)):
    """Get agent dashboard stats"""
    agent_id = user['user_id']
    
    total_clients = await db.clients.count_documents({"agent_id": agent_id})
    
    # Pending quotes (Sent or Change Requested)
    pending_quotes = await db.documents.count_documents({
        "agent_id": agent_id, "type": "quote",
        "status": {"$in": ["Sent", "Change Requested"]}
    })
    
    # Pending invoices (Sent status)
    pending_invoices = await db.documents.count_documents({
        "agent_id": agent_id, "type": "invoice",
        "status": "Sent"
    })
    
    # Revenue (paid invoices)
    paid_invoices = await db.documents.find(
        {"agent_id": agent_id, "type": "invoice", "status": "Paid"},
        {"_id": 0, "amount": 1}
    ).to_list(1000)
    total_revenue = sum(inv['amount'] for inv in paid_invoices)
    
    # Recent documents
    recent_docs = await db.documents.find(
        {"agent_id": agent_id},
        {"_id": 0}
    ).sort("updated_at", -1).limit(5).to_list(5)
    
    # Change requests (both quotes and invoices) - from documents
    change_requests = await db.documents.find(
        {"agent_id": agent_id, "status": "Change Requested"},
        {"_id": 0}
    ).to_list(20)

    # Enrich change requests with client_name
    cr_client_ids = list({d["client_id"] for d in change_requests if d.get("client_id")})
    if cr_client_ids:
        cr_clients = await db.clients.find(
            {"client_id": {"$in": cr_client_ids}}, {"_id": 0, "client_id": 1, "name": 1}
        ).to_list(len(cr_client_ids))
        cr_client_map = {c["client_id"]: c["name"] for c in cr_clients}
        for d in change_requests:
            if not d.get("client_name"):
                d["client_name"] = cr_client_map.get(d.get("client_id"))
    
    # Open change requests from canonical system
    open_change_requests = await db.change_requests.count_documents(
        {"agent_id": agent_id, "status": {"$in": ["open", "under_review"]}}
    )
    
    # Approved quotes ready to convert
    approved_quotes = await db.documents.find(
        {"agent_id": agent_id, "type": "quote", "status": "Approved"},
        {"_id": 0}
    ).to_list(10)
    
    # Decision stats
    pending_decisions = await db.decisions.count_documents(
        {"agent_id": agent_id, "status": "pending"}
    )
    overdue_decisions = 0
    now_str = datetime.now(timezone.utc).isoformat()
    overdue_decisions = await db.decisions.count_documents(
        {"agent_id": agent_id, "status": "pending", "deadline": {"$lt": now_str, "$ne": None}}
    )
    challenged_decisions = await db.decisions.count_documents(
        {"agent_id": agent_id, "status": "Change Requested"}
    )

    return {
        "total_clients": total_clients,
        "pending_quotes": pending_quotes,
        "pending_invoices": pending_invoices,
        "total_revenue": total_revenue,
        "recent_documents": recent_docs,
        "change_requests": change_requests,
        "open_change_requests": open_change_requests,
        "approved_quotes": approved_quotes,
        "pending_decisions": pending_decisions,
        "overdue_decisions": overdue_decisions,
        "challenged_decisions": challenged_decisions,
    }

@router.get("/stats/buyer")
async def get_buyer_stats(user: dict = Depends(get_current_buyer)):
    """Get buyer dashboard stats"""
    
    clients = await db.clients.find(
        {"buyer_id": user['user_id']},
        {"_id": 0}
    ).to_list(100)
    client_ids = [c['client_id'] for c in clients]
    
    if not client_ids:
        return {
            "pending_quotes": 0,
            "pending_invoices": 0,
            "total_paid": 0,
            "projects": []
        }
    
    pending_quotes = await db.documents.count_documents({
        "client_id": {"$in": client_ids},
        "type": "quote", "status": "Sent"
    })
    
    pending_invoices = await db.documents.count_documents({
        "client_id": {"$in": client_ids},
        "type": "invoice", "status": "Sent"
    })
    
    paid_invoices = await db.documents.find(
        {"client_id": {"$in": client_ids}, "type": "invoice", "status": "Paid"},
        {"_id": 0, "amount": 1}
    ).to_list(1000)
    total_paid = sum(inv['amount'] for inv in paid_invoices)
    
    project_ids = list(set(c['project_id'] for c in clients))
    projects = await db.projects.find({"project_id": {"$in": project_ids}}, {"_id": 0}).to_list(10)
    
    for project in projects:
        client = next((c for c in clients if c['project_id'] == project['project_id']), None)
        if client:
            project['unit_reference'] = client.get('unit_reference', '')
    
    return {
        "pending_quotes": pending_quotes,
        "pending_invoices": pending_invoices,
        "total_paid": total_paid,
        "projects": projects
    }

