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

from services.email_service import send_email_async, send_notification_email, get_email_template
from services.realtime_service import ws_manager, notify_realtime, send_milestone_notification
from services.qr_service import generate_swiss_qr_code, generate_swiss_qr_code_base64, DEFAULT_IBAN, DEFAULT_COMPANY_NAME
from services.ai_service import extract_document_from_pdf, OPENAI_API_KEY
from services import file_service


logger = logging.getLogger(__name__)

from services.billing_service import get_subscription_status

router = APIRouter()

# ==================== AGENT SETTINGS ====================

# ==================== AGENT SETTINGS ENDPOINTS ====================

class BillingSettings(BaseModel):
    iban: Optional[str] = None
    company_name: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None

class AgentProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None

class AgentSettingsUpdate(BaseModel):
    language: Optional[str] = None
    currency: Optional[str] = None
    company_name: Optional[str] = None
    billing: Optional[BillingSettings] = None
    profile: Optional[AgentProfileUpdate] = None

@router.get("/settings")
async def get_agent_settings(user: dict = Depends(get_current_agent)):
    """Get agent settings including profile info"""
    user_doc = await db.users.find_one({"user_id": user['user_id']}, {"_id": 0})
    settings = user_doc.get('settings', {}) if user_doc else {}
    profile = user_doc.get('profile', {}) if user_doc else {}
    
    return {
        "language": settings.get('language', 'en'),
        "currency": settings.get('currency', 'CHF'),
        "company_name": settings.get('company_name', ''),
        "company_logo_url": user_doc.get('company_logo_url') if user_doc else None,
        "billing": settings.get('billing', {}),
        "profile": {
            "display_name": profile.get('display_name', user_doc.get('name', '') if user_doc else ''),
            "contact_email": profile.get('contact_email', user_doc.get('email', '') if user_doc else ''),
            "contact_phone": profile.get('contact_phone', '')
        }
    }

@router.get("/branding")
async def get_agent_branding_for_buyer(user: dict = Depends(get_current_user)):
    """Get agent branding info for buyer view - returns the agent's branding who manages this buyer"""
    if user['role'] == 'agent':
        # Agents see their own branding
        user_doc = await db.users.find_one({"user_id": user['user_id']}, {"_id": 0})
        return {
            "company_name": user_doc.get('settings', {}).get('company_name', '') if user_doc else '',
            "company_logo_url": user_doc.get('company_logo_url') if user_doc else None,
            "language": user_doc.get('settings', {}).get('language', 'en') if user_doc else 'en',
            "currency": user_doc.get('settings', {}).get('currency', 'CHF') if user_doc else 'CHF'
        }
    
    # For buyers, find their associated agent through client relationship
    client = await db.clients.find_one({"buyer_id": user['user_id']}, {"_id": 0})
    if not client:
        # No client relationship - return defaults
        return {
            "company_name": "",
            "company_logo_url": None,
            "language": "en",
            "currency": "CHF"
        }
    
    # Find the project to get agent_id
    project = await db.projects.find_one({"project_id": client.get('project_id')}, {"_id": 0})
    if not project:
        return {
            "company_name": "",
            "company_logo_url": None,
            "language": "en",
            "currency": "CHF"
        }
    
    agent_id = project.get('agent_id')
    agent = await db.users.find_one({"user_id": agent_id}, {"_id": 0})
    
    if not agent:
        return {
            "company_name": "",
            "company_logo_url": None,
            "language": "en",
            "currency": "CHF"
        }
    
    return {
        "company_name": agent.get('settings', {}).get('company_name', ''),
        "company_logo_url": agent.get('company_logo_url'),
        "language": agent.get('settings', {}).get('language', 'en'),
        "currency": agent.get('settings', {}).get('currency', 'CHF')
    }

@router.put("/settings")
async def update_agent_settings(data: AgentSettingsUpdate, user: dict = Depends(get_current_agent)):
    """Update agent settings including profile info"""
    update_data = {}
    
    if data.language:
        if data.language not in ['en', 'de', 'fr', 'it']:
            raise HTTPException(status_code=400, detail="Invalid language")
        update_data['settings.language'] = data.language
    
    if data.currency:
        if data.currency not in ['CHF', 'EUR', 'USD']:
            raise HTTPException(status_code=400, detail="Invalid currency")
        update_data['settings.currency'] = data.currency
    
    if data.company_name is not None:
        update_data['settings.company_name'] = data.company_name
    
    if data.billing:
        billing_dict = data.billing.dict(exclude_none=True)
        for key, value in billing_dict.items():
            update_data[f'settings.billing.{key}'] = value
    
    # Handle profile updates
    if data.profile:
        if data.profile.display_name is not None:
            update_data['profile.display_name'] = data.profile.display_name
        if data.profile.contact_email is not None:
            update_data['profile.contact_email'] = data.profile.contact_email
        if data.profile.contact_phone is not None:
            update_data['profile.contact_phone'] = data.profile.contact_phone
    
    if update_data:
        await db.users.update_one(
            {"user_id": user['user_id']},
            {"$set": update_data}
        )
    
    return {"message": "Settings updated"}

@router.post("/settings/logo")
async def upload_company_logo(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_agent)
):
    """Upload company logo (Pro plan required)"""
    from core.trace import set_trace_action, set_trace_entity, trace_db_mutation
    set_trace_action("logo_upload")
    set_trace_entity("user", user['user_id'])
    subscription_data = await get_subscription_status(user['user_id'])
    if subscription_data['plan_id'] not in ['pro', 'enterprise']:
        raise HTTPException(status_code=403, detail={"error": "plan_required", "message": "Logo upload requires Pro plan or higher"})

    # Delete old logo
    user_doc = await db.users.find_one({"user_id": user['user_id']}, {"_id": 0})
    if user_doc and user_doc.get('company_logo_stored_filename'):
        file_service.delete_file(user_doc['company_logo_stored_filename'])

    result = await file_service.save_logo(file, user['user_id'])

    await db.users.update_one(
        {"user_id": user['user_id']},
        {"$set": {
            "company_logo_url": result['url'],
            "company_logo_stored_filename": result['stored_filename'],
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    return {"url": result['url'], "filename": result['original_filename'], "size": result['file_size']}


@router.delete("/settings/logo")
async def delete_company_logo(user: dict = Depends(get_current_agent)):
    """Delete company logo."""
    user_doc = await db.users.find_one({"user_id": user['user_id']}, {"_id": 0})
    if user_doc and user_doc.get('company_logo_stored_filename'):
        file_service.delete_file(user_doc['company_logo_stored_filename'])

    await db.users.update_one(
        {"user_id": user['user_id']},
        {"$set": {
            "company_logo_url": None,
            "company_logo_stored_filename": None,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    return {"message": "Logo removed"}

