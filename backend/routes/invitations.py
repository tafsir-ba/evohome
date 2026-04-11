"""
Team Invitations Routes — Cleaned.

No is_demo. Ownership scoped via invited_by (agent_id).
"""
import os
import uuid
import secrets
import logging
import bcrypt
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Response, Form
from pydantic import BaseModel, EmailStr

from database import db
from core.auth import get_current_user, get_current_agent, create_access_token, JWT_EXPIRY_DAYS
from services.email_service import send_email_async, send_notification_email, get_email_template

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ──

class TeamInviteCreate(BaseModel):
    email: EmailStr
    role: str = "member"
    message: Optional[str] = None


# ── Endpoints ──

@router.post("/team/invitations")
async def create_team_invitation(data: TeamInviteCreate, user: dict = Depends(get_current_agent)):
    """Invite a new team member to the agent's workspace"""
    existing_agent = await db.users.find_one({"email": data.email, "role": "agent"}, {"_id": 0})
    if existing_agent:
        if existing_agent.get('workspace_owner_id') == user['user_id']:
            raise HTTPException(status_code=400, detail="This user is already part of your team")
        if existing_agent.get('workspace_owner_id'):
            raise HTTPException(status_code=400, detail="This user is already part of another workspace")

    existing_invite = await db.team_invitations.find_one({
        "email": data.email,
        "invited_by": user['user_id'],
        "status": "pending",
    })
    if existing_invite:
        raise HTTPException(status_code=400, detail="An invitation has already been sent to this email")

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
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at.isoformat(),
    }

    await db.team_invitations.insert_one(invitation_doc)

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
        "expires_at": invitation_doc['expires_at'],
    }


@router.get("/team/invitations")
async def list_team_invitations(user: dict = Depends(get_current_agent)):
    """List all team invitations sent by this agent"""
    invitations = await db.team_invitations.find(
        {"invited_by": user['user_id']},
        {"_id": 0, "invitation_token": 0},
    ).sort("created_at", -1).to_list(100)
    return invitations


@router.delete("/team/invitations/{invitation_id}")
async def cancel_team_invitation(invitation_id: str, user: dict = Depends(get_current_agent)):
    """Cancel a pending team invitation"""
    invitation = await db.team_invitations.find_one({
        "invitation_id": invitation_id,
        "invited_by": user['user_id'],
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
    workspace_owner_id = user.get('workspace_owner_id') or user['user_id']

    team_members = await db.users.find(
        {
            "$or": [
                {"user_id": workspace_owner_id},
                {"workspace_owner_id": workspace_owner_id},
            ],
            "role": "agent",
        },
        {"_id": 0, "password_hash": 0, "password_reset_token": 0, "password_reset_expires": 0},
    ).to_list(100)

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
        "status": "pending",
    })
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found or already used")

    expires_at = datetime.fromisoformat(invitation['expires_at'].replace('Z', '+00:00'))
    if datetime.now(timezone.utc) > expires_at:
        await db.team_invitations.update_one(
            {"invitation_id": invitation['invitation_id']},
            {"$set": {"status": "expired"}},
        )
        raise HTTPException(status_code=400, detail="Invitation has expired")

    email = invitation['email']
    existing_user = await db.users.find_one({"email": email, "role": "agent"}, {"_id": 0})

    if existing_user:
        if existing_user.get('workspace_owner_id'):
            raise HTTPException(status_code=400, detail="You are already part of another workspace")

        await db.users.update_one(
            {"user_id": existing_user['user_id']},
            {"$set": {"workspace_owner_id": invitation['invited_by'], "workspace_role": invitation['role']}},
        )
        user_id = existing_user['user_id']
    else:
        return {
            "status": "needs_registration",
            "email": email,
            "invited_by_name": invitation['invited_by_name'],
            "role": invitation['role'],
            "token": token,
        }

    await db.team_invitations.update_one(
        {"invitation_id": invitation['invitation_id']},
        {"$set": {"status": "accepted", "accepted_at": datetime.now(timezone.utc).isoformat(), "accepted_by": user_id}},
    )

    jwt_token = create_access_token(user_id, "agent")

    response.set_cookie(
        key="session_token", value=jwt_token, httponly=True, secure=True,
        samesite="none", path="/", max_age=JWT_EXPIRY_DAYS * 24 * 60 * 60,
    )

    return {"status": "accepted", "user_id": user_id, "workspace_owner_id": invitation['invited_by'], "token": jwt_token}


@router.post("/team/register-invited")
async def register_invited_user(
    email: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    token: str = Form(...),
    response: Response = None,
):
    """Register a new user from a team invitation"""
    invitation = await db.team_invitations.find_one({
        "invitation_token": token,
        "status": "pending",
        "email": email.lower(),
    })
    if not invitation:
        raise HTTPException(status_code=404, detail="Invalid invitation token")

    expires_at = datetime.fromisoformat(invitation['expires_at'].replace('Z', '+00:00'))
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail="Invitation has expired")

    existing = await db.users.find_one({"email": email.lower(), "role": "agent"})
    if existing:
        raise HTTPException(status_code=400, detail="Account already exists. Please login and accept the invitation.")

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    user_id = f"agent_{uuid.uuid4().hex[:12]}"

    user_doc = {
        "user_id": user_id,
        "email": email.lower(),
        "name": name,
        "password_hash": hashed_password.decode('utf-8'),
        "role": "agent",
        "picture": None,
        "workspace_owner_id": invitation['invited_by'],
        "workspace_role": invitation['role'],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.users.insert_one(user_doc)

    await db.team_invitations.update_one(
        {"invitation_id": invitation['invitation_id']},
        {"$set": {"status": "accepted", "accepted_at": datetime.now(timezone.utc).isoformat(), "accepted_by": user_id}},
    )

    jwt_token = create_access_token(user_id, "agent")

    response.set_cookie(
        key="session_token", value=jwt_token, httponly=True, secure=True,
        samesite="none", path="/", max_age=JWT_EXPIRY_DAYS * 24 * 60 * 60,
    )

    logger.info(f"New team member registered: {user_id} joined workspace of {invitation['invited_by']}")

    return {
        "user_id": user_id,
        "email": email,
        "name": name,
        "role": "agent",
        "workspace_owner_id": invitation['invited_by'],
        "workspace_role": invitation['role'],
        "token": jwt_token,
    }


@router.delete("/team/members/{member_id}")
async def remove_team_member(member_id: str, user: dict = Depends(get_current_agent)):
    """Remove a team member from the workspace (owner only)"""
    if user.get('workspace_owner_id'):
        raise HTTPException(status_code=403, detail="Only workspace owner can remove team members")

    member = await db.users.find_one({
        "user_id": member_id,
        "workspace_owner_id": user['user_id'],
    })
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")

    await db.users.update_one(
        {"user_id": member_id},
        {"$unset": {"workspace_owner_id": "", "workspace_role": ""}},
    )

    logger.info(f"Team member {member_id} removed from workspace by {user['user_id']}")
    return {"message": "Team member removed from workspace"}
