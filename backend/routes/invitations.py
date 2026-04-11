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

# ==================== TEAM INVITATIONS ====================

# ==================== TEAM INVITATIONS ENDPOINTS ====================

class TeamInviteCreate(BaseModel):
    email: EmailStr
    role: str = "member"  # "admin" or "member"
    message: Optional[str] = None

class TeamInviteResponse(BaseModel):
    invitation_id: str
    email: str
    role: str
    status: str  # "pending", "accepted", "declined", "expired"
    invited_by: str
    invited_by_name: str
    created_at: str
    expires_at: str

@router.post("/team/invitations")
async def create_team_invitation(data: TeamInviteCreate, user: dict = Depends(get_current_agent)):
    """Invite a new team member to the agent's workspace"""
    is_demo = user.get('is_demo', False)
    
    # Check if user already exists as an agent
    existing_agent = await db.users.find_one({"email": data.email, "role": "agent"}, {"_id": 0})
    if existing_agent:
        # Check if already part of this workspace
        if existing_agent.get('workspace_owner_id') == user['user_id']:
            raise HTTPException(status_code=400, detail="This user is already part of your team")
        if existing_agent.get('workspace_owner_id'):
            raise HTTPException(status_code=400, detail="This user is already part of another workspace")
    
    # Check for existing pending invitation
    existing_invite = await db.team_invitations.find_one({
        "email": data.email,
        "invited_by": user['user_id'],
        "status": "pending",
        "is_demo": is_demo
    })
    if existing_invite:
        raise HTTPException(status_code=400, detail="An invitation has already been sent to this email")
    
    # Create invitation
    invitation_id = f"invite_{uuid.uuid4().hex[:12]}"
    invitation_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    
    invitation_doc = {
        "invitation_id": invitation_id,
        "email": data.email.lower(),
        "role": data.role,
        "message": data.message,
        "status": "pending",
        "invited_by": user['user_id'],
        "invited_by_name": user.get('name', 'Unknown'),
        "invitation_token": invitation_token,
        "is_demo": is_demo,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at.isoformat()
    }
    
    await db.team_invitations.insert_one(invitation_doc)
    
    # Send invitation email
    frontend_url = os.environ.get('REACT_APP_BACKEND_URL', 'https://evohome.ch').replace('/api', '')
    invite_link = f"{frontend_url}/team/accept?token={invitation_token}"
    
    company_name = user.get('settings', {}).get('company_name') or user.get('name', 'Evohome')
    
    subject = f"You've been invited to join {company_name} on Evohome"
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2563EB;">Team Invitation</h2>
        <p>Hi,</p>
        <p><strong>{user.get('name', 'A team member')}</strong> has invited you to join <strong>{company_name}</strong> on Evohome as a <strong>{data.role}</strong>.</p>
        {f'<p style="color: #666; font-style: italic;">"{data.message}"</p>' if data.message else ''}
        <p style="text-align: center; margin: 30px 0;">
            <a href="{invite_link}" style="background-color: #2563EB; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                Accept Invitation
            </a>
        </p>
        <p style="color: #666; font-size: 14px;">This invitation will expire in 7 days.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
        <p style="color: #999; font-size: 12px;">Evohome - Real Estate Management</p>
    </div>
    """
    
    await send_email_async(data.email, subject, html_content)
    
    logger.info(f"Team invitation sent to {data.email} by {user['user_id']}")
    
    return {
        "invitation_id": invitation_id,
        "email": data.email,
        "role": data.role,
        "status": "pending",
        "invited_by": user['user_id'],
        "invited_by_name": user.get('name', 'Unknown'),
        "created_at": invitation_doc['created_at'],
        "expires_at": invitation_doc['expires_at']
    }

@router.get("/team/invitations")
async def list_team_invitations(user: dict = Depends(get_current_agent)):
    """List all team invitations sent by this agent"""
    is_demo = user.get('is_demo', False)
    
    invitations = await db.team_invitations.find(
        {"invited_by": user['user_id']},
        {"_id": 0, "invitation_token": 0}
    ).sort("created_at", -1).to_list(100)
    
    return invitations

@router.delete("/team/invitations/{invitation_id}")
async def cancel_team_invitation(invitation_id: str, user: dict = Depends(get_current_agent)):
    """Cancel a pending team invitation"""
    is_demo = user.get('is_demo', False)
    
    invitation = await db.team_invitations.find_one({
        "invitation_id": invitation_id,
        "invited_by": user['user_id'],
        "is_demo": is_demo
    })
    
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    
    if invitation['status'] != 'pending':
        raise HTTPException(status_code=400, detail="Can only cancel pending invitations")
    
    await db.team_invitations.delete_one({"invitation_id": invitation_id})
    
    return {"message": "Invitation cancelled"}

@router.get("/team/members")
async def list_team_members(user: dict = Depends(get_current_agent)):
    """List all team members in the agent's workspace"""
    is_demo = user.get('is_demo', False)
    
    # Get the workspace owner - either self or owner if this is a team member
    workspace_owner_id = user.get('workspace_owner_id') or user['user_id']
    
    # Find all agents in this workspace
    team_members = await db.users.find(
        {
            "$or": [
                {"user_id": workspace_owner_id},
                {"workspace_owner_id": workspace_owner_id}
            ],
            "role": "agent",
            "is_demo": is_demo
        },
        {"_id": 0, "password_hash": 0, "password_reset_token": 0, "password_reset_expires": 0}
    ).to_list(100)
    
    # Enrich with role info
    for member in team_members:
        if member['user_id'] == workspace_owner_id:
            member['team_role'] = 'owner'
        else:
            member['team_role'] = member.get('workspace_role', 'member')
    
    return team_members

@router.post("/team/accept")
async def accept_team_invitation(token: str, response: Response):
    """Accept a team invitation (public endpoint, creates/links account)"""
    
    invitation = await db.team_invitations.find_one({
        "invitation_token": token,
        "status": "pending"
    })
    
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found or already used")
    
    # Check expiry
    expires_at = datetime.fromisoformat(invitation['expires_at'].replace('Z', '+00:00'))
    if datetime.now(timezone.utc) > expires_at:
        await db.team_invitations.update_one(
            {"invitation_id": invitation['invitation_id']},
            {"$set": {"status": "expired"}}
        )
        raise HTTPException(status_code=400, detail="Invitation has expired")
    
    is_demo = invitation.get('is_demo', False)
    email = invitation['email']
    
    # Check if user already exists
    existing_user = await db.users.find_one({"email": email, "role": "agent"}, {"_id": 0})
    
    if existing_user:
        # Link existing user to workspace
        if existing_user.get('workspace_owner_id'):
            raise HTTPException(status_code=400, detail="You are already part of another workspace")
        
        await db.users.update_one(
            {"user_id": existing_user['user_id']},
            {"$set": {
                "workspace_owner_id": invitation['invited_by'],
                "workspace_role": invitation['role']
            }}
        )
        user_id = existing_user['user_id']
    else:
        # Return info for registration - user needs to complete signup
        return {
            "status": "needs_registration",
            "email": email,
            "invited_by_name": invitation['invited_by_name'],
            "role": invitation['role'],
            "token": token
        }
    
    # Mark invitation as accepted
    await db.team_invitations.update_one(
        {"invitation_id": invitation['invitation_id']},
        {"$set": {
            "status": "accepted",
            "accepted_at": datetime.now(timezone.utc).isoformat(),
            "accepted_by": user_id
        }}
    )
    
    # Create session token
    token = create_jwt_token(user_id, "agent", is_demo)
    
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=JWT_EXPIRY_DAYS * 24 * 60 * 60
    )
    
    return {
        "status": "accepted",
        "user_id": user_id,
        "workspace_owner_id": invitation['invited_by'],
        "token": token
    }

@router.post("/team/register-invited")
async def register_invited_user(
    email: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    token: str = Form(...),
    response: Response = None
):
    """Register a new user from a team invitation"""
    
    invitation = await db.team_invitations.find_one({
        "invitation_token": token,
        "status": "pending",
        "email": email.lower()
    })
    
    if not invitation:
        raise HTTPException(status_code=404, detail="Invalid invitation token")
    
    # Check expiry
    expires_at = datetime.fromisoformat(invitation['expires_at'].replace('Z', '+00:00'))
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail="Invitation has expired")
    
    is_demo = invitation.get('is_demo', False)
    
    # Check if user already exists
    existing = await db.users.find_one({"email": email.lower(), "role": "agent"})
    if existing:
        raise HTTPException(status_code=400, detail="Account already exists. Please login and accept the invitation.")
    
    # Create new user
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    user_id = f"agent_{uuid.uuid4().hex[:12]}"
    
    user_doc = {
        "user_id": user_id,
        "email": email.lower(),
        "name": name,
        "password_hash": hashed_password.decode('utf-8'),
        "role": "agent",
        "picture": None,
        "is_demo": is_demo,
        "workspace_owner_id": invitation['invited_by'],
        "workspace_role": invitation['role'],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user_doc)
    
    # Mark invitation as accepted
    await db.team_invitations.update_one(
        {"invitation_id": invitation['invitation_id']},
        {"$set": {
            "status": "accepted",
            "accepted_at": datetime.now(timezone.utc).isoformat(),
            "accepted_by": user_id
        }}
    )
    
    # Create session
    jwt_token = create_jwt_token(user_id, "agent", is_demo)
    
    response.set_cookie(
        key="session_token",
        value=jwt_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=JWT_EXPIRY_DAYS * 24 * 60 * 60
    )
    
    logger.info(f"New team member registered: {user_id} joined workspace of {invitation['invited_by']}")
    
    return {
        "user_id": user_id,
        "email": email,
        "name": name,
        "role": "agent",
        "workspace_owner_id": invitation['invited_by'],
        "workspace_role": invitation['role'],
        "token": jwt_token
    }

@router.delete("/team/members/{member_id}")
async def remove_team_member(member_id: str, user: dict = Depends(get_current_agent)):
    """Remove a team member from the workspace (owner only)"""
    is_demo = user.get('is_demo', False)
    
    # Only workspace owner can remove members
    if user.get('workspace_owner_id'):
        raise HTTPException(status_code=403, detail="Only workspace owner can remove team members")
    
    # Find the member
    member = await db.users.find_one({
        "user_id": member_id,
        "workspace_owner_id": user['user_id'],
        "is_demo": is_demo
    })
    
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    
    # Remove from workspace (don't delete the user)
    await db.users.update_one(
        {"user_id": member_id},
        {"$unset": {"workspace_owner_id": "", "workspace_role": ""}}
    )
    
    logger.info(f"Team member {member_id} removed from workspace by {user['user_id']}")
    
    return {"message": "Team member removed from workspace"}


