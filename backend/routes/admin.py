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

from helpers import get_demo_filter, build_query, secure_filename, VALID_TRANSITIONS, validate_transition, SUBSCRIPTION_PLANS, VAULT_CATEGORIES, VAULT_DOC_TYPES
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

# ==================== ADMIN/DIAGNOSTIC ENDPOINTS ====================

# ==================== ADMIN / DIAGNOSTIC ENDPOINTS ====================

@router.get("/admin/diagnose-buyer/{email}")
async def diagnose_buyer_account(email: str, user: dict = Depends(get_current_agent)):
    """
    Diagnose buyer account linkage issues.
    Returns detailed information about buyer account, client records, and their linkage.
    """
    is_demo = user.get('is_demo', False)
    
    # Find buyer user
    buyer_user = await db.users.find_one(
        {"email": email, "role": "buyer"},
        {"_id": 0, "password_hash": 0}
    )
    
    # Find client records with this email
    client_records = await db.clients.find(
        {"email": email},
        {"_id": 0}
    ).to_list(100)
    
    # Find client records linked to this buyer (if buyer exists)
    linked_clients = []
    if buyer_user:
        linked_clients = await db.clients.find(
            {"buyer_id": buyer_user['user_id']},
            {"_id": 0}
        ).to_list(100)
    
    # Find activities for these clients
    all_client_ids = list(set([c['client_id'] for c in client_records] + [c['client_id'] for c in linked_clients]))
    
    activity_recipients = await db.activity_recipients.find(
        {"client_id": {"$in": all_client_ids}},
        {"_id": 0}
    ).to_list(500)
    
    # Diagnose issues
    issues = []
    
    if not buyer_user:
        issues.append({
            "type": "NO_BUYER_ACCOUNT",
            "message": f"No buyer user account exists for email {email}. Buyer needs to register first."
        })
    
    if not client_records:
        issues.append({
            "type": "NO_CLIENT_RECORD",
            "message": f"No client record exists for email {email}. Agent needs to create a client."
        })
    
    # Check for unlinked clients (buyer exists but client.buyer_id is null)
    unlinked_clients = [c for c in client_records if not c.get('buyer_id') and buyer_user]
    if unlinked_clients:
        issues.append({
            "type": "UNLINKED_CLIENTS",
            "message": f"Found {len(unlinked_clients)} client record(s) not linked to buyer account",
            "client_ids": [c['client_id'] for c in unlinked_clients]
        })
    
    # Check for mismatched buyer_id
    if buyer_user:
        mismatched = [c for c in client_records if c.get('buyer_id') and c['buyer_id'] != buyer_user['user_id']]
        if mismatched:
            issues.append({
                "type": "BUYER_ID_MISMATCH",
                "message": f"Found {len(mismatched)} client(s) linked to different buyer account",
                "details": [(c['client_id'], c['buyer_id']) for c in mismatched]
            })
    
    if not activity_recipients:
        issues.append({
            "type": "NO_ACTIVITIES",
            "message": "No feed activities have been posted to this client"
        })
    
    return {
        "email": email,
        "buyer_user": buyer_user,
        "client_records": client_records,
        "linked_via_buyer_id": linked_clients,
        "activity_recipient_count": len(activity_recipients),
        "issues": issues,
        "can_auto_fix": len(unlinked_clients) > 0 and buyer_user is not None
    }

@router.post("/admin/fix-buyer-linkage/{email}")
async def fix_buyer_client_linkage(email: str, user: dict = Depends(get_current_agent)):
    """
    Fix buyer-client linkage for a specific email.
    Links all client records with this email to the corresponding buyer account.
    """
    is_demo = user.get('is_demo', False)
    
    # Find buyer user
    buyer_user = await db.users.find_one(
        {"email": email, "role": "buyer"},
        {"_id": 0}
    )
    
    if not buyer_user:
        raise HTTPException(
            status_code=404, 
            detail=f"No buyer account found for {email}. Buyer must register first."
        )
    
    # Find and update unlinked client records
    result = await db.clients.update_many(
        {"email": email, "buyer_id": None},
        {"$set": {"buyer_id": buyer_user['user_id']}}
    )
    
    # Also check for clients with matching email but no buyer_id set
    result2 = await db.clients.update_many(
        {"email": email, "buyer_id": {"$exists": False}},
        {"$set": {"buyer_id": buyer_user['user_id']}}
    )
    
    total_fixed = result.modified_count + result2.modified_count
    
    logger.info(f"Fixed buyer linkage for {email}: {total_fixed} client records updated")
    
    return {
        "message": f"Successfully linked {total_fixed} client record(s) to buyer account",
        "email": email,
        "buyer_id": buyer_user['user_id'],
        "records_fixed": total_fixed
    }

@router.get("/admin/email-status")
async def check_email_configuration(user: dict = Depends(get_current_agent)):
    """
    Check email system configuration status.
    Returns configuration status and allows sending test emails.
    """
    return {
        "resend_api_key_configured": bool(RESEND_API_KEY),
        "sender_email_configured": bool(SENDER_EMAIL),
        "sender_email": SENDER_EMAIL if SENDER_EMAIL else "NOT SET",
        "frontend_url": FRONTEND_URL,
        "status": "ready" if (RESEND_API_KEY and SENDER_EMAIL) else "not_configured",
        "issues": [
            issue for issue in [
                "RESEND_API_KEY not set" if not RESEND_API_KEY else None,
                "SENDER_EMAIL not set" if not SENDER_EMAIL else None,
            ] if issue
        ]
    }

@router.post("/admin/test-email")
async def send_test_email(to_email: str, user: dict = Depends(get_current_agent)):
    """
    Send a test email to verify email system is working.
    """
    if not RESEND_API_KEY:
        raise HTTPException(status_code=503, detail="RESEND_API_KEY not configured")
    if not SENDER_EMAIL:
        raise HTTPException(status_code=503, detail="SENDER_EMAIL not configured")
    
    subject = "Evohome Test Email"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h1 style="color: #2563EB;">Test Email from Evohome</h1>
        <p>This is a test email to verify your email configuration is working correctly.</p>
        <p><strong>Configuration:</strong></p>
        <ul>
            <li>Sender: {SENDER_EMAIL}</li>
            <li>Frontend URL: {FRONTEND_URL}</li>
            <li>Sent by: {user.get('name', user['user_id'])}</li>
        </ul>
        <p>If you received this email, your Resend integration is working!</p>
    </body>
    </html>
    """
    
    result = await send_email_async(to_email, subject, html_content)
    
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=f"Email failed: {result.get('error')}")
    
    return {
        "message": f"Test email sent to {to_email}",
        "result": result
    }

# ==================== END ADMIN ENDPOINTS ====================

@router.delete("/settings/logo")
async def delete_company_logo(user: dict = Depends(get_current_agent)):
    """Delete company logo"""
    user_doc = await db.users.find_one({"user_id": user['user_id']}, {"_id": 0})
    
    if user_doc and user_doc.get('company_logo_path'):
        logo_path = Path(user_doc['company_logo_path'])
        if logo_path.exists():
            try:
                logo_path.unlink()
            except OSError:
                pass
    
    await db.users.update_one(
        {"user_id": user['user_id']},
        {"$unset": {"company_logo_url": "", "company_logo_path": ""}}
    )
    
    return {"message": "Logo deleted"}

