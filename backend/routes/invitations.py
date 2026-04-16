"""
Team Invitations Routes — Cleaned.

No is_demo. Ownership scoped via invited_by (agent_id).
"""
import os
import uuid
import secrets
import logging
import bcrypt
import html
import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, Depends, Response, Form
from pydantic import BaseModel, EmailStr

from database import db
from core.auth import get_current_user, get_current_agent, create_access_token, JWT_EXPIRY_DAYS
from core.access_control import get_workspace_owner_id, is_workspace_admin, is_workspace_owner
from core.audit import log_audit_event
from services.email_service import send_email_async, send_notification_email, get_email_template

logger = logging.getLogger(__name__)
router = APIRouter()
DEBUG_LOG_PATH = "/Users/tafpro/WD Dropbox/Tafsir Ba/Repo Cursor/evohome/.cursor/debug-b8cd8a.log"
DEBUG_SESSION_ID = "b8cd8a"


def _debug_log(run_id: str, hypothesis_id: str, location: str, message: str, data: dict):
    payload = {
        "sessionId": DEBUG_SESSION_ID,
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
    }
    try:
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        pass


# ── Schemas ──

class TeamInviteCreate(BaseModel):
    email: EmailStr
    role: Literal["member", "admin"] = "member"
    message: Optional[str] = None


class TeamMemberRoleUpdate(BaseModel):
    role: str


# ── Endpoints ──

@router.post("/team/invitations")
async def create_team_invitation(data: TeamInviteCreate, user: dict = Depends(get_current_agent)):
    """Invite a new team member to the agent's workspace"""
    # region agent log
    recipient = data.email.lower().strip()
    _debug_log(
        run_id="run-2",
        hypothesis_id="H5",
        location="backend/routes/invitations.py:create_team_invitation:entry",
        message="team invitation endpoint invoked",
        data={
            "recipient_domain": recipient.split("@", 1)[1] if "@" in recipient else "invalid",
            "recipient_hash": hashlib.sha256(recipient.encode("utf-8")).hexdigest()[:12],
            "actor_user_id": user.get("user_id"),
            "role": data.role,
        },
    )
    # endregion
    if not is_workspace_admin(user):
        raise HTTPException(status_code=403, detail="Only workspace admins can invite team members")
    workspace_owner_id = get_workspace_owner_id(user)
    normalized_email = data.email.lower().strip()
    cleaned_message = (data.message or "").strip()

    existing_agent = await db.users.find_one({"email": normalized_email, "role": "agent"}, {"_id": 0})
    if existing_agent:
        if existing_agent.get('workspace_owner_id') == workspace_owner_id:
            raise HTTPException(status_code=400, detail="This user is already part of your team")
        if existing_agent.get('workspace_owner_id'):
            raise HTTPException(status_code=400, detail="This user is already part of another workspace")

    existing_invite = await db.team_invitations.find_one({
        "email": normalized_email,
        "invited_by": workspace_owner_id,
        "status": "pending",
    })
    if existing_invite:
        raise HTTPException(status_code=400, detail="An invitation has already been sent to this email")

    invitation_id = f"invite_{uuid.uuid4().hex[:12]}"
    invitation_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    invitation_doc = {
        "invitation_id": invitation_id,
        "email": normalized_email,
        "role": data.role,
        "message": cleaned_message if cleaned_message else None,
        "status": "pending",
        "invited_by": workspace_owner_id,
        "invited_by_name": user.get('name', 'Unknown'),
        "invitation_token": invitation_token,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at.isoformat(),
    }

    await db.team_invitations.insert_one(invitation_doc)

    frontend_url = os.environ.get('REACT_APP_BACKEND_URL', 'https://evohome.ch').replace('/api', '')
    invite_link = f"{frontend_url}/team/accept?token={invitation_token}"
    company_name = user.get('settings', {}).get('company_name') or user.get('name', 'Evohome')
    inviter_name = user.get('name', 'Votre equipe')

    subject, html_content = get_email_template("team_invitation", {
        "company_name": html.escape(company_name),
        "invited_by_name": html.escape(inviter_name),
        "role": data.role,
        "invite_link": invite_link,
        "message": html.escape(cleaned_message) if cleaned_message else "",
    })

    email_result = await send_email_async(normalized_email, subject, html_content)
    if email_result.get("status") != "success":
        await db.team_invitations.delete_one({"invitation_id": invitation_id})
        logger.error(
            "Team invitation email failed; rolled back invite %s for %s (%s)",
            invitation_id,
            normalized_email,
            email_result.get("reason") or email_result.get("error") or "unknown",
        )
        raise HTTPException(
            status_code=502,
            detail="Invitation email could not be delivered. Please verify email configuration and try again.",
        )
    logger.info(f"Team invitation sent to {normalized_email} by {user['user_id']}")

    return {
        "invitation_id": invitation_id,
        "email": normalized_email,
        "role": data.role,
        "status": "pending",
        "invited_by": workspace_owner_id,
        "invited_by_name": user.get('name', 'Unknown'),
        "created_at": invitation_doc['created_at'],
        "expires_at": invitation_doc['expires_at'],
        "delivery_status": "sent",
    }


@router.get("/team/invitations")
async def list_team_invitations(user: dict = Depends(get_current_agent)):
    """List all team invitations sent by this agent"""
    workspace_owner_id = get_workspace_owner_id(user)
    invitations = await db.team_invitations.find(
        {"invited_by": workspace_owner_id},
        {"_id": 0, "invitation_token": 0},
    ).sort("created_at", -1).to_list(100)
    return invitations


@router.delete("/team/invitations/{invitation_id}")
async def cancel_team_invitation(invitation_id: str, user: dict = Depends(get_current_agent)):
    """Cancel a pending team invitation"""
    if not is_workspace_admin(user):
        raise HTTPException(status_code=403, detail="Only workspace admins can cancel invitations")
    workspace_owner_id = get_workspace_owner_id(user)
    invitation = await db.team_invitations.find_one({
        "invitation_id": invitation_id,
        "invited_by": workspace_owner_id,
    })
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invitation['status'] != 'pending':
        raise HTTPException(status_code=400, detail="Can only cancel pending invitations")
    await db.team_invitations.delete_one({"invitation_id": invitation_id})
    await log_audit_event(
        actor_user=user,
        action="team_invitation_cancelled",
        target_type="team_invitation",
        target_id=invitation_id,
        workspace_owner_id=workspace_owner_id,
        metadata={"email": invitation.get("email")},
    )
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
    await send_notification_email("welcome_onboarding", email, {
        "name": existing_user.get("name", ""),
        "role": "agent",
        "project_name": "your shared workspace",
        "agent_name": invitation.get("invited_by_name", "Your workspace owner"),
    })

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
    email_normalized = email.lower().strip()
    name_cleaned = name.strip()
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if not name_cleaned:
        raise HTTPException(status_code=400, detail="Name is required")

    invitation = await db.team_invitations.find_one({
        "invitation_token": token,
        "status": "pending",
        "email": email_normalized,
    })
    if not invitation:
        raise HTTPException(status_code=404, detail="Invalid invitation token")

    expires_at = datetime.fromisoformat(invitation['expires_at'].replace('Z', '+00:00'))
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail="Invitation has expired")

    existing = await db.users.find_one({"email": email_normalized, "role": "agent"})
    if existing:
        raise HTTPException(status_code=400, detail="Account already exists. Please login and accept the invitation.")

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    user_id = f"agent_{uuid.uuid4().hex[:12]}"

    user_doc = {
        "user_id": user_id,
        "email": email_normalized,
        "name": name_cleaned,
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
    await send_notification_email("welcome_onboarding", email_normalized, {
        "name": name_cleaned,
        "role": "agent",
        "project_name": "your shared workspace",
        "agent_name": invitation.get("invited_by_name", "Your workspace owner"),
    })

    jwt_token = create_access_token(user_id, "agent")

    response.set_cookie(
        key="session_token", value=jwt_token, httponly=True, secure=True,
        samesite="none", path="/", max_age=JWT_EXPIRY_DAYS * 24 * 60 * 60,
    )

    logger.info(f"New team member registered: {user_id} joined workspace of {invitation['invited_by']}")

    return {
        "user_id": user_id,
        "email": email_normalized,
        "name": name_cleaned,
        "role": "agent",
        "workspace_owner_id": invitation['invited_by'],
        "workspace_role": invitation['role'],
        "token": jwt_token,
    }


@router.delete("/team/members/{member_id}")
async def remove_team_member(member_id: str, user: dict = Depends(get_current_agent)):
    """Remove a team member from the workspace with role guards."""
    if not is_workspace_admin(user):
        raise HTTPException(status_code=403, detail="Only workspace admins can remove team members")
    workspace_owner_id = get_workspace_owner_id(user)

    member = await db.users.find_one({
        "user_id": member_id,
        "workspace_owner_id": workspace_owner_id,
    })
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    if member_id == workspace_owner_id:
        raise HTTPException(status_code=400, detail="Cannot remove workspace owner")
    if member.get("workspace_role") == "admin" and not is_workspace_owner(user):
        raise HTTPException(status_code=403, detail="Only workspace owner can remove another admin")

    await db.users.update_one(
        {"user_id": member_id},
        {"$unset": {"workspace_owner_id": "", "workspace_role": ""}},
    )
    await db.team_invitations.update_many(
        {"accepted_by": member_id, "invited_by": workspace_owner_id},
        {"$set": {"status": "revoked", "revoked_at": datetime.now(timezone.utc).isoformat()}},
    )
    await log_audit_event(
        actor_user=user,
        action="team_member_removed",
        target_type="user",
        target_id=member_id,
        workspace_owner_id=workspace_owner_id,
        metadata={"workspace_role": member.get("workspace_role", "member")},
    )

    logger.info(f"Team member {member_id} removed from workspace by {user['user_id']}")
    return {"message": "Team member removed from workspace"}


@router.patch("/team/members/{member_id}/role")
async def update_team_member_role(
    member_id: str,
    data: TeamMemberRoleUpdate,
    user: dict = Depends(get_current_agent),
):
    """Update workspace role for a team member (owner only)."""
    if not is_workspace_owner(user):
        raise HTTPException(status_code=403, detail="Only workspace owner can change team roles")
    if data.role not in {"member", "admin"}:
        raise HTTPException(status_code=400, detail="Invalid role; must be 'member' or 'admin'")

    workspace_owner_id = get_workspace_owner_id(user)
    member = await db.users.find_one(
        {"user_id": member_id, "workspace_owner_id": workspace_owner_id, "role": "agent"},
        {"_id": 0, "user_id": 1},
    )
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")

    await db.users.update_one(
        {"user_id": member_id},
        {"$set": {"workspace_role": data.role}},
    )
    await log_audit_event(
        actor_user=user,
        action="team_member_role_updated",
        target_type="user",
        target_id=member_id,
        workspace_owner_id=workspace_owner_id,
        metadata={"workspace_role": data.role},
    )
    return {"message": "Team member role updated", "member_id": member_id, "role": data.role}
