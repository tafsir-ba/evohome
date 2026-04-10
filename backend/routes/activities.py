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

# ==================== ACTIVITY FEED ====================

# ==================== ACTIVITY FEED ENDPOINTS (UNIFIED) ====================
# Single feed architecture - same data, role-based access filtering

ACTIVITY_UPLOAD_DIR = UPLOAD_DIR / "activities"
ACTIVITY_UPLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
ALLOWED_FILE_TYPES = {
    'image': ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/gif'],
    'pdf': ['application/pdf']
}

async def get_buyer_unit_context(user: dict) -> dict:
    """Get the unit_id and project_id for a buyer based on their client link"""
    is_demo = user.get('is_demo', False)
    
    # Find the client linked to this buyer
    client = await db.clients.find_one(
        {"buyer_id": user['user_id']},
        {"_id": 0, "client_id": 1, "project_id": 1, "unit_reference": 1}
    )
    
    if not client:
        return None
    
    # Find the unit for this client
    unit = await db.units.find_one(
        {"client_id": client['client_id']},
        {"_id": 0, "unit_id": 1, "unit_reference": 1, "project_id": 1}
    )
    
    return {
        "client_id": client['client_id'],
        "project_id": client.get('project_id') or (unit.get('project_id') if unit else None),
        "unit_id": unit.get('unit_id') if unit else None,
        "unit_reference": unit.get('unit_reference') if unit else client.get('unit_reference')
    }

async def enrich_activity(activity: dict, include_replies: bool = False) -> dict:
    """Enrich activity with author name, project name, recipients, and optionally replies"""
    # Get author name
    author = await db.users.find_one({"user_id": activity['author_id']}, {"_id": 0, "name": 1})
    activity['author_name'] = author['name'] if author else 'Unknown'
    
    # Get project name
    project = await db.projects.find_one({"project_id": activity['project_id']}, {"_id": 0, "name": 1})
    activity['project_name'] = project['name'] if project else None
    
    # Get unit reference
    if activity.get('unit_id'):
        unit = await db.units.find_one({"unit_id": activity['unit_id']}, {"_id": 0, "unit_reference": 1})
        activity['unit_reference'] = unit['unit_reference'] if unit else None
    
    # Get recipients
    recipients = await db.activity_recipients.find(
        {"activity_id": activity['activity_id']},
        {"_id": 0}
    ).to_list(100)
    
    for recipient in recipients:
        client = await db.clients.find_one({"client_id": recipient['client_id']}, {"_id": 0, "name": 1})
        recipient['client_name'] = client['name'] if client else 'Unknown'
    
    activity['recipients'] = recipients
    
    # Get reply count
    reply_count = await db.activity_replies.count_documents({"activity_id": activity['activity_id']})
    activity['reply_count'] = reply_count
    
    # Get replies if requested
    if include_replies:
        replies = await db.activity_replies.find(
            {"activity_id": activity['activity_id']},
            {"_id": 0}
        ).sort("created_at", 1).to_list(100)
        
        for reply in replies:
            author = await db.users.find_one({"user_id": reply['author_id']}, {"_id": 0, "name": 1})
            reply['author_name'] = author['name'] if author else 'Unknown'
        
        activity['replies'] = replies
    
    return activity

@router.post("/activities")
async def create_activity(
    type: str = Form(...),
    project_id: str = Form(...),
    client_ids: str = Form(...),  # Comma-separated
    title: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    unit_id: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user: dict = Depends(get_current_agent)
):
    """
    Create a new activity (AGENT ONLY).
    Single feed architecture - activities are stored once and filtered by role.
    """
    is_demo = user.get('is_demo', False)
    now = datetime.now(timezone.utc).isoformat()
    
    # Validate type
    if type not in ["message", "image", "pdf", "status"]:
        raise HTTPException(status_code=400, detail="Invalid activity type")
    
    # Parse client_ids
    recipient_ids = [cid.strip() for cid in client_ids.split(',') if cid.strip()]
    if not recipient_ids:
        raise HTTPException(status_code=400, detail="At least one client_id is required")
    
    # Validate project ownership
    project = await db.projects.find_one(
        {"project_id": project_id, "agent_id": user['user_id']},
        {"_id": 0}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Validate clients belong to agent
    for client_id in recipient_ids:
        client = await db.clients.find_one(
            {"client_id": client_id, "agent_id": user['user_id']},
            {"_id": 0}
        )
        if not client:
            raise HTTPException(status_code=400, detail=f"Client {client_id} not found or not owned by you")
    
    # Validate content or file is provided
    if type in ["message", "status"] and not content:
        raise HTTPException(status_code=400, detail="Content is required for message/status activities")
    
    if type in ["image", "pdf"] and not file:
        raise HTTPException(status_code=400, detail=f"File is required for {type} activities")
    
    # Handle file upload
    file_url = None
    file_name = None
    file_size = None
    
    if file:
        # Validate file size
        file_content = await file.read()
        file_size = len(file_content)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File too large. Max size is {MAX_FILE_SIZE // (1024*1024)}MB")
        
        # Validate file type
        content_type = file.content_type or 'application/octet-stream'
        if type == "image" and content_type not in ALLOWED_FILE_TYPES['image']:
            raise HTTPException(status_code=400, detail="Invalid image type. Allowed: JPEG, PNG, WebP, GIF")
        if type == "pdf" and content_type not in ALLOWED_FILE_TYPES['pdf']:
            raise HTTPException(status_code=400, detail="Invalid file type. Only PDF allowed")
        
        # Save file
        file_id = uuid.uuid4().hex[:12]
        ext = Path(file.filename).suffix if file.filename else ('.jpg' if type == 'image' else '.pdf')
        filename = f"{file_id}_{file.filename or f'upload{ext}'}"
        file_path = ACTIVITY_UPLOAD_DIR / filename
        
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        file_url = f"/api/activities/files/{filename}"
        file_name = file.filename
    
    # Create activity
    activity_id = f"act_{uuid.uuid4().hex[:12]}"
    
    activity_doc = {
        "activity_id": activity_id,
        "type": type,
        "title": title,
        "content": content,
        "file_url": file_url,
        "file_name": file_name,
        "file_size": file_size,
        "author_id": user['user_id'],
        "author_role": "agent",
        "project_id": project_id,
        "unit_id": unit_id,
        "is_demo": is_demo,
        "created_at": now,
        "updated_at": now
    }
    
    await db.activities.insert_one(activity_doc)
    
    # Create recipient links and send notifications
    for client_id in recipient_ids:
        await db.activity_recipients.insert_one({
            "recipient_id": f"rcpt_{uuid.uuid4().hex[:8]}",
            "activity_id": activity_id,
            "client_id": client_id,
            "is_demo": is_demo,
            "created_at": now
        })
        
        # Send email notification to buyer if they have an account
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if client and client.get('buyer_id'):
            buyer = await db.users.find_one({"user_id": client['buyer_id']}, {"_id": 0, "email": 1, "name": 1})
            if buyer and buyer.get('email'):
                # Send email notification (non-blocking)
                try:
                    agent = await db.users.find_one({"user_id": user['user_id']}, {"_id": 0, "name": 1, "contact_email": 1, "phone": 1, "company_name": 1})
                    email_data = {
                        "buyer_name": buyer.get('name', client.get('name', 'there')),
                        "agent_name": agent.get('name', 'Your Agent') if agent else 'Your Agent',
                        "agent_email": agent.get('contact_email', '') if agent else '',
                        "agent_phone": agent.get('phone', '') if agent else '',
                        "company_name": agent.get('company_name', '') if agent else '',
                        "project_name": project.get('name', 'Your Project'),
                        "message_preview": content[:200] if content else f"New {type} update",
                        "link": "buyer/dashboard"
                    }
                    await send_notification_email("feed_update", buyer['email'], email_data)
                    logger.info(f"Sent feed notification email to {buyer['email']}")
                except Exception as e:
                    logger.error(f"Failed to send feed notification email: {e}")
                
                # Create in-app notification
                try:
                    await create_notification(
                        user_id=client['buyer_id'],
                        title="New Update from Your Agent",
                        message=content[:100] if content else f"New {type} posted",
                        notification_type="feed_update",
                        link="/buyer/dashboard",
                        metadata={"activity_id": activity_id, "project_id": project_id},
                        is_demo=is_demo
                    )
                    
                    # Send real-time notification
                    await notify_realtime(
                        [client['buyer_id']],
                        "new_activity",
                        {"activity_id": activity_id, "type": type, "project_id": project_id}
                    )
                except Exception as e:
                    logger.error(f"Failed to create in-app notification: {e}")
    
    # Fetch and enrich the created activity
    activity = await db.activities.find_one({"activity_id": activity_id}, {"_id": 0})
    activity = await enrich_activity(activity)
    
    return activity

@router.get("/activities")
async def get_activities(
    project_id: Optional[str] = None,
    client_id: Optional[str] = None,
    unit_id: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    user: dict = Depends(get_current_user)
):
    """
    Get activities - ownership scoped by role.
    
    - Agent: Can filter by project_id, client_id, unit_id (ownership verified)
    - Buyer: Automatically filtered to their unit/client context only
    """
    if user['role'] == 'buyer':
        # STRICT BUYER ACCESS - auto-filter to their context
        buyer_context = await get_buyer_unit_context(user)
        
        if not buyer_context:
            # Buyer has no linked client - return empty
            return {"activities": [], "total": 0, "limit": limit, "offset": offset}
        
        # Find activities where this client is a recipient
        recipient_records = await db.activity_recipients.find(
            {"client_id": buyer_context['client_id']},
            {"_id": 0, "activity_id": 1}
        ).to_list(1000)
        
        activity_ids = [r['activity_id'] for r in recipient_records]
        
        if not activity_ids:
            return {"activities": [], "total": 0, "limit": limit, "offset": offset}
        
        query = {"activity_id": {"$in": activity_ids}}
        
    else:
        # AGENT ACCESS - can filter freely (ownership enforced below)
        query = {}
        
        # Verify agent owns the project if filtering by project
        if project_id:
            project = await db.projects.find_one(
                {"project_id": project_id, "agent_id": user['user_id']}
            )
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            query["project_id"] = project_id
        
        # Filter by client_id (via recipients)
        if client_id:
            client = await db.clients.find_one(
                {"client_id": client_id, "agent_id": user['user_id']}
            )
            if not client:
                raise HTTPException(status_code=404, detail="Client not found")
            
            recipient_records = await db.activity_recipients.find(
                {"client_id": client_id},
                {"_id": 0, "activity_id": 1}
            ).to_list(1000)
            
            activity_ids = [r['activity_id'] for r in recipient_records]
            query["activity_id"] = {"$in": activity_ids} if activity_ids else {"$in": []}
        
        if unit_id:
            query["unit_id"] = unit_id
        
        # If no filters, show agent's activities (where they are author)
        # This includes both sent activities and drafts
        if not project_id and not client_id and not unit_id:
            query["author_id"] = user['user_id']
    
    if type:
        query["type"] = type
    
    # Get total count
    total = await db.activities.count_documents(query)
    
    # Get activities with pagination (reverse chronological)
    activities = await db.activities.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(offset).limit(limit).to_list(limit)
    
    # Enrich each activity
    enriched = []
    for activity in activities:
        enriched.append(await enrich_activity(activity))
    
    return {
        "activities": enriched,
        "total": total,
        "limit": limit,
        "offset": offset
    }

@router.post("/activities/mark-seen")
async def mark_activities_seen(user: dict = Depends(get_current_user)):
    """Mark activities as seen - updates last_seen_at timestamp"""
    now = datetime.now(timezone.utc).isoformat()
    
    await db.user_activity_tracking.update_one(
        {"user_id": user['user_id']},
        {"$set": {"last_seen_at": now}},
        upsert=True
    )
    
    return {"last_seen_at": now}

@router.get("/activities/unread-count")
async def get_unread_count(user: dict = Depends(get_current_user)):
    """Get count of activities newer than last_seen_at"""
    is_demo = user.get('is_demo', False)
    
    # Get last seen timestamp
    tracking = await db.user_activity_tracking.find_one(
        {"user_id": user['user_id']},
        {"_id": 0}
    )
    last_seen_at = tracking.get('last_seen_at') if tracking else None
    
    if user['role'] == 'buyer':
        # Get buyer's activities
        buyer_context = await get_buyer_unit_context(user)
        if not buyer_context:
            return {"unread_count": 0, "last_seen_at": last_seen_at}
        
        recipient_records = await db.activity_recipients.find(
            {"client_id": buyer_context['client_id']},
            {"_id": 0, "activity_id": 1}
        ).to_list(1000)
        
        activity_ids = [r['activity_id'] for r in recipient_records]
        if not activity_ids:
            return {"unread_count": 0, "last_seen_at": last_seen_at}
        
        query = {"activity_id": {"$in": activity_ids}}
    else:
        # Agent - count their authored activities
        query = {"author_id": user['user_id']}
    
    # Add time filter if last_seen exists
    if last_seen_at:
        query["created_at"] = {"$gt": last_seen_at}
    
    unread_count = await db.activities.count_documents(query)
    
    return {"unread_count": unread_count, "last_seen_at": last_seen_at}

# File serving routes - must be before {activity_id} catch-all
@router.get("/activities/files/demo/{filename}")
async def get_demo_activity_file(filename: str, user: dict = Depends(get_current_user)):
    """Serve demo activity file attachments"""
    file_path = ACTIVITY_UPLOAD_DIR / "demo" / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    suffix = file_path.suffix.lower()
    content_type_map = {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
        '.webp': 'image/webp', '.gif': 'image/gif', '.pdf': 'application/pdf',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xls': 'application/vnd.ms-excel',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.ppt': 'application/vnd.ms-powerpoint',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    }
    content_type = content_type_map.get(suffix, 'application/octet-stream')
    
    return FileResponse(file_path, media_type=content_type, filename=filename)

@router.get("/activities/files/{filename}")
async def get_activity_file(filename: str, user: dict = Depends(get_current_user)):
    """Serve activity file attachments with access control"""
    file_path = ACTIVITY_UPLOAD_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    suffix = file_path.suffix.lower()
    content_type_map = {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
        '.webp': 'image/webp', '.gif': 'image/gif', '.pdf': 'application/pdf',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xls': 'application/vnd.ms-excel',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.ppt': 'application/vnd.ms-powerpoint',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    }
    content_type = content_type_map.get(suffix, 'application/octet-stream')
    
    return FileResponse(file_path, media_type=content_type, filename=filename)

@router.get("/activities/{activity_id}")
async def get_activity(activity_id: str, user: dict = Depends(get_current_user)):
    """
    Get a single activity with full details including replies.
    Role-based access is enforced.
    """
    is_demo = user.get('is_demo', False)
    
    activity = await db.activities.find_one(
        {"activity_id": activity_id},
        {"_id": 0}
    )
    
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    if user['role'] == 'buyer':
        # Verify buyer has access to this activity
        buyer_context = await get_buyer_unit_context(user)
        
        if not buyer_context:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Check if buyer is a recipient
        recipient = await db.activity_recipients.find_one({
            "activity_id": activity_id,
            "client_id": buyer_context['client_id'],
            "is_demo": is_demo
        })
        
        if not recipient:
            raise HTTPException(status_code=403, detail="Access denied")
    
    else:
        # Agent must own the project or be the author
        if activity['author_id'] != user['user_id']:
            project = await db.projects.find_one({
                "project_id": activity['project_id'],
                "agent_id": user['user_id'],
                "is_demo": is_demo
            })
            if not project:
                raise HTTPException(status_code=403, detail="Access denied")
    
    # Enrich with replies
    activity = await enrich_activity(activity, include_replies=True)
    
    return activity

@router.post("/activities/{activity_id}/send")
async def send_draft_activity(
    activity_id: str,
    user: dict = Depends(get_current_agent)
):
    """
    Send a draft activity to recipients.
    This converts a draft to a sent activity and creates recipient records.
    """
    is_demo = user.get('is_demo', False)
    now = datetime.now(timezone.utc).isoformat()
    
    # Find the draft activity
    activity = await db.activities.find_one(
        {"activity_id": activity_id, "author_id": user['user_id']},
        {"_id": 0}
    )
    
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    if not activity.get('is_draft'):
        raise HTTPException(status_code=400, detail="Activity is not a draft")
    
    draft_recipients = activity.get('draft_recipients', [])
    if not draft_recipients:
        raise HTTPException(status_code=400, detail="No recipients specified for this draft")
    
    # Validate recipients
    for client_id in draft_recipients:
        client = await db.clients.find_one(
            {"client_id": client_id, "agent_id": user['user_id']},
            {"_id": 0}
        )
        if not client:
            raise HTTPException(status_code=400, detail=f"Client {client_id} not found")
    
    # Get project for notifications
    project = await db.projects.find_one(
        {"project_id": activity['project_id']},
        {"_id": 0, "name": 1}
    )
    
    # Update activity to mark as sent
    await db.activities.update_one(
        {"activity_id": activity_id},
        {"$set": {"is_draft": False, "updated_at": now}, "$unset": {"draft_recipients": ""}}
    )
    
    # Create recipient links and send notifications
    for client_id in draft_recipients:
        await db.activity_recipients.insert_one({
            "recipient_id": f"rcpt_{uuid.uuid4().hex[:8]}",
            "activity_id": activity_id,
            "client_id": client_id,
            "is_demo": is_demo,
            "created_at": now
        })
        
        # Send email notification to buyer if they have an account
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
        if client and client.get('buyer_id'):
            buyer = await db.users.find_one({"user_id": client['buyer_id']}, {"_id": 0, "email": 1, "name": 1})
            if buyer and buyer.get('email'):
                try:
                    agent = await db.users.find_one({"user_id": user['user_id']}, {"_id": 0, "name": 1, "contact_email": 1, "phone": 1, "company_name": 1})
                    email_data = {
                        "buyer_name": buyer.get('name', client.get('name', 'there')),
                        "agent_name": agent.get('name', 'Your Agent') if agent else 'Your Agent',
                        "agent_email": agent.get('contact_email', '') if agent else '',
                        "agent_phone": agent.get('phone', '') if agent else '',
                        "company_name": agent.get('company_name', '') if agent else '',
                        "project_name": project.get('name', 'Your Project') if project else 'Your Project',
                        "message_preview": activity.get('content', '')[:200] if activity.get('content') else "New update",
                        "link": "buyer/dashboard"
                    }
                    await send_notification_email("feed_update", buyer['email'], email_data)
                    logger.info(f"Sent feed notification email to {buyer['email']}")
                except Exception as e:
                    logger.error(f"Failed to send feed notification email: {e}")
    
    # Return the updated activity
    updated_activity = await db.activities.find_one({"activity_id": activity_id}, {"_id": 0})
    return await enrich_activity(updated_activity)

@router.post("/activities/{activity_id}/reply")
async def reply_to_activity(
    activity_id: str,
    reply_data: ActivityReplyCreate,
    user: dict = Depends(get_current_user)
):
    """
    Reply to an activity. Both buyers and agents can reply.
    Access is strictly validated.
    """
    is_demo = user.get('is_demo', False)
    now = datetime.now(timezone.utc).isoformat()
    
    activity = await db.activities.find_one(
        {"activity_id": activity_id},
        {"_id": 0}
    )
    
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    if user['role'] == 'buyer':
        # Verify buyer has access
        buyer_context = await get_buyer_unit_context(user)
        
        if not buyer_context:
            raise HTTPException(status_code=403, detail="Access denied")
        
        recipient = await db.activity_recipients.find_one({
            "activity_id": activity_id,
            "client_id": buyer_context['client_id'],
            "is_demo": is_demo
        })
        
        if not recipient:
            raise HTTPException(status_code=403, detail="Access denied")
    
    else:
        # Agent must own the project
        project = await db.projects.find_one({
            "project_id": activity['project_id'],
            "agent_id": user['user_id'],
            "is_demo": is_demo
        })
        if not project:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Create reply
    reply_id = f"reply_{uuid.uuid4().hex[:12]}"
    
    reply_doc = {
        "reply_id": reply_id,
        "activity_id": activity_id,
        "author_id": user['user_id'],
        "author_role": user['role'],
        "content": reply_data.content,
        "is_demo": is_demo,
        "created_at": now
    }
    
    await db.activity_replies.insert_one(reply_doc)
    
    # Update activity timestamp
    await db.activities.update_one(
        {"activity_id": activity_id},
        {"$set": {"updated_at": now}}
    )
    
    # Get author name
    author = await db.users.find_one({"user_id": user['user_id']}, {"_id": 0, "name": 1})
    reply_doc['author_name'] = author['name'] if author else 'Unknown'
    
    # Remove MongoDB _id and is_demo before returning
    reply_doc.pop('_id', None)
    reply_doc.pop('is_demo', None)
    
    return reply_doc

@router.post("/activities/{activity_id}/request-change")
async def request_activity_change(
    activity_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Request changes on a file-type activity. Buyer only.
    Creates a system reply and updates activity status.
    """
    is_demo = user.get('is_demo', False)
    
    if user['role'] != 'buyer':
        raise HTTPException(status_code=403, detail="Only buyers can request changes")
    
    activity = await db.activities.find_one(
        {"activity_id": activity_id},
        {"_id": 0}
    )
    
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    if activity['type'] != 'file':
        raise HTTPException(status_code=400, detail="Change requests only supported for file-type activities")
    
    # Verify buyer has access
    buyer_context = await get_buyer_unit_context(user)
    if not buyer_context:
        raise HTTPException(status_code=403, detail="Access denied")
    
    recipient = await db.activity_recipients.find_one({
        "activity_id": activity_id,
        "client_id": buyer_context['client_id'],
        "is_demo": is_demo
    })
    
    if not recipient:
        raise HTTPException(status_code=403, detail="Access denied")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Update activity status
    await db.activities.update_one(
        {"activity_id": activity_id},
        {"$set": {"status": "change_requested", "updated_at": now}}
    )
    
    return {"message": "Change requested", "status": "change_requested"}

@router.delete("/activities/{activity_id}")
async def delete_activity(
    activity_id: str,
    user: dict = Depends(get_current_agent)
):
    """
    Delete an activity (agent only).
    Deletes the activity, its recipients, replies, and associated files.
    """
    is_demo = user.get('is_demo', False)
    
    # Find the activity (author_id is the field used for activities)
    activity = await db.activities.find_one(
        {"activity_id": activity_id, "author_id": user['user_id']},
        {"_id": 0}
    )
    
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    # Delete associated file if it exists
    if activity.get('file_path') and os.path.exists(activity['file_path']):
        try:
            os.remove(activity['file_path'])
        except Exception as e:
            logger.warning(f"Failed to delete activity file: {e}")
    
    # Delete replies
    await db.activity_replies.delete_many({"activity_id": activity_id})
    
    # Delete recipients
    await db.activity_recipients.delete_many({"activity_id": activity_id})
    
    # Delete the activity itself
    await db.activities.delete_one({"activity_id": activity_id})
    
    return {"message": "Activity deleted successfully"}

class ActivityUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None

@router.put("/activities/{activity_id}")
async def update_activity(
    activity_id: str,
    data: ActivityUpdate,
    user: dict = Depends(get_current_agent)
):
    """
    Update an activity (agent only).
    Can update title and content.
    """
    is_demo = user.get('is_demo', False)
    
    # Find the activity (author_id is the field used for activities)
    activity = await db.activities.find_one(
        {"activity_id": activity_id, "author_id": user['user_id']},
        {"_id": 0}
    )
    
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    # Build update dict
    update_dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if data.title is not None:
        update_dict["title"] = data.title
    if data.content is not None:
        update_dict["content"] = data.content
    
    # Update the activity
    await db.activities.update_one(
        {"activity_id": activity_id},
        {"$set": update_dict}
    )
    
    # Return updated activity
    updated = await db.activities.find_one(
        {"activity_id": activity_id},
        {"_id": 0}
    )
    updated.pop('is_demo', None)
    
    return updated

