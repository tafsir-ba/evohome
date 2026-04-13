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

from fastapi import APIRouter, HTTPException, Depends, Request, Response, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field, EmailStr
import bcrypt

from database import db
from core.auth import get_current_user, get_current_agent, get_current_buyer, verify_token
from core.auth import invalidate_user_sessions, allow_user_sessions
from core.access_control import can_access_project, can_access_client, can_access_vault_doc, can_access_document, get_accessible_project_ids, get_accessible_client_ids, is_agent, is_buyer, get_workspace_owner_id, is_workspace_admin, is_workspace_owner
from core.audit import log_audit_event
from core.rate_limit import rate_limit_check, check_rate_limit
from core.monitoring import capture_exception, capture_auth_failure, capture_payment_error, capture_email_error, capture_ai_error, capture_websocket_error, capture_document_error, ErrorContext
from core.responses import AuthSessionResponse, AuthLoginResponse, AuthRefreshResponse, AuthLogoutResponse, DocumentResponse, VaultDocumentResponse, NotificationResponse, ActivityResponse, ActivitiesListResponse, SuccessResponse

# helpers: no longer needed
from services.email_service import send_email_async, send_notification_email, get_email_template, RESEND_API_KEY, SENDER_EMAIL, FRONTEND_URL
from services.realtime_service import ws_manager, notify_realtime, send_milestone_notification
from services.qr_service import generate_swiss_qr_code, generate_swiss_qr_code_base64, DEFAULT_IBAN, DEFAULT_COMPANY_NAME
from services.ai_service import extract_document_from_pdf, OPENAI_API_KEY

logger = logging.getLogger(__name__)
SUPER_ADMIN_EMAIL = "tafsir@evo-home.ch"

ROOT_DIR = Path(__file__).parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter()


def _require_super_admin(user: Dict[str, Any]) -> None:
    email = (user.get("email") or "").strip().lower()
    if email != SUPER_ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Super admin access required")


def _clean_user_row(user: dict) -> dict:
    row = dict(user)
    # insert_one mutates the document with BSON _id; never return it in JSON APIs.
    row.pop("_id", None)
    for k in ("password_hash", "password_reset_token", "password_reset_expires"):
        row.pop(k, None)
    return row


async def _workspace_user_delete_impact(workspace_owner_id: str, user_id: str) -> Dict[str, Any]:
    """Summarize user-linked records before hard delete."""
    return {
        "activities_authored": await db.activities.count_documents({"author_id": user_id}),
        "activity_replies_authored": await db.activity_replies.count_documents({"author_id": user_id}),
        "notifications_owned": await db.notifications.count_documents({"user_id": user_id}),
        "invitations_accepted_by_user": await db.team_invitations.count_documents(
            {"invited_by": workspace_owner_id, "accepted_by": user_id}
        ),
    }

# ==================== ADMIN/DIAGNOSTIC ENDPOINTS ====================

# ==================== ADMIN / DIAGNOSTIC ENDPOINTS ====================

@router.get("/admin/diagnose-buyer/{email}")
async def diagnose_buyer_account(email: str, user: dict = Depends(get_current_agent)):
    """
    Diagnose buyer account linkage issues.
    Returns detailed information about buyer account, client records, and their linkage.
    """
    _require_super_admin(user)
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
    _require_super_admin(user)
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
    _require_super_admin(user)
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
    _require_super_admin(user)
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


class AdminCreateAgentUserBody(BaseModel):
    email: EmailStr
    name: str
    password: str = Field(min_length=8)
    workspace_role: Literal["member", "admin"] = "member"


class AdminUpdateAgentRoleBody(BaseModel):
    workspace_role: Literal["member", "admin"]


@router.get("/admin/users")
async def list_workspace_users(
    include_inactive: bool = Query(True),
    user: dict = Depends(get_current_agent),
):
    """List agent users in current workspace."""
    if not is_workspace_admin(user):
        raise HTTPException(status_code=403, detail="Workspace admin access required")
    workspace_owner_id = get_workspace_owner_id(user)

    query: Dict[str, Any] = {
        "$or": [{"user_id": workspace_owner_id}, {"workspace_owner_id": workspace_owner_id}],
        "role": "agent",
    }
    if not include_inactive:
        query["is_active"] = {"$ne": False}

    users = await db.users.find(query, {"_id": 0}).to_list(200)
    clean = []
    for u in users:
        row = _clean_user_row(u)
        row["team_role"] = "owner" if row.get("user_id") == workspace_owner_id else row.get("workspace_role", "member")
        row["is_active"] = row.get("is_active", True)
        clean.append(row)
    return clean


@router.post("/admin/users")
async def create_workspace_user(data: AdminCreateAgentUserBody, user: dict = Depends(get_current_agent)):
    """Create an agent account inside current workspace."""
    if not is_workspace_admin(user):
        raise HTTPException(status_code=403, detail="Workspace admin access required")
    actor_email = (user.get("email") or "").strip().lower()
    if data.workspace_role == "admin" and not is_workspace_owner(user) and actor_email != SUPER_ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Only workspace owner can create admin users")

    workspace_owner_id = get_workspace_owner_id(user)
    existing = await db.users.find_one({"email": data.email.lower(), "role": "agent"}, {"_id": 0})
    if existing:
        existing_workspace_owner = existing.get("workspace_owner_id") or existing.get("user_id")
        if existing_workspace_owner == workspace_owner_id:
            raise HTTPException(status_code=400, detail="An agent with this email already exists in this workspace")
        raise HTTPException(status_code=400, detail="An agent with this email exists in another workspace")

    user_id = f"agent_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    password_hash = bcrypt.hashpw(data.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user_doc = {
        "user_id": user_id,
        "email": data.email.lower(),
        "name": data.name,
        "password_hash": password_hash,
        "role": "agent",
        "picture": None,
        "workspace_owner_id": workspace_owner_id,
        "workspace_role": data.workspace_role,
        "is_active": True,
        "created_at": now,
        "created_by": user.get("user_id"),
        "subscription_plan": "free",
        "subscription_status": "active",
    }
    await db.users.insert_one(user_doc)
    await log_audit_event(
        actor_user=user,
        action="admin_user_created",
        target_type="user",
        target_id=user_id,
        workspace_owner_id=workspace_owner_id,
        metadata={"workspace_role": data.workspace_role, "email": data.email.lower()},
    )
    return _clean_user_row(user_doc)


@router.patch("/admin/users/{member_id}/role")
async def update_workspace_user_role(
    member_id: str,
    data: AdminUpdateAgentRoleBody,
    user: dict = Depends(get_current_agent),
):
    """Update workspace role for an agent member."""
    if not is_workspace_owner(user):
        raise HTTPException(status_code=403, detail="Only workspace owner can change roles")
    workspace_owner_id = get_workspace_owner_id(user)
    if member_id == workspace_owner_id:
        raise HTTPException(status_code=400, detail="Cannot change workspace owner role")

    member = await db.users.find_one(
        {"user_id": member_id, "workspace_owner_id": workspace_owner_id, "role": "agent"},
        {"_id": 0},
    )
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")

    await db.users.update_one({"user_id": member_id}, {"$set": {"workspace_role": data.workspace_role}})
    await log_audit_event(
        actor_user=user,
        action="admin_user_role_updated",
        target_type="user",
        target_id=member_id,
        workspace_owner_id=workspace_owner_id,
        metadata={"workspace_role": data.workspace_role},
    )
    updated = await db.users.find_one({"user_id": member_id}, {"_id": 0})
    return _clean_user_row(updated or member)


@router.post("/admin/users/{member_id}/deactivate")
async def deactivate_workspace_user(member_id: str, user: dict = Depends(get_current_agent)):
    """Deactivate a team member and revoke active sessions."""
    if not is_workspace_admin(user):
        raise HTTPException(status_code=403, detail="Workspace admin access required")
    workspace_owner_id = get_workspace_owner_id(user)
    if member_id == workspace_owner_id:
        raise HTTPException(status_code=400, detail="Cannot deactivate workspace owner")

    member = await db.users.find_one(
        {"user_id": member_id, "workspace_owner_id": workspace_owner_id, "role": "agent"},
        {"_id": 0},
    )
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    if member.get("workspace_role") == "admin" and not is_workspace_owner(user):
        raise HTTPException(status_code=403, detail="Only workspace owner can deactivate an admin")

    await db.users.update_one(
        {"user_id": member_id},
        {"$set": {"is_active": False, "deactivated_at": datetime.now(timezone.utc).isoformat(), "deactivated_by": user["user_id"]}},
    )
    invalidate_user_sessions(member_id)
    await log_audit_event(
        actor_user=user,
        action="admin_user_deactivated",
        target_type="user",
        target_id=member_id,
        workspace_owner_id=workspace_owner_id,
        metadata={"workspace_role": member.get("workspace_role", "member")},
    )
    return {"message": "User deactivated", "user_id": member_id}


@router.post("/admin/users/{member_id}/reactivate")
async def reactivate_workspace_user(member_id: str, user: dict = Depends(get_current_agent)):
    """Reactivate a team member."""
    if not is_workspace_admin(user):
        raise HTTPException(status_code=403, detail="Workspace admin access required")
    workspace_owner_id = get_workspace_owner_id(user)
    member = await db.users.find_one(
        {"user_id": member_id, "workspace_owner_id": workspace_owner_id, "role": "agent"},
        {"_id": 0},
    )
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    if member.get("workspace_role") == "admin" and not is_workspace_owner(user):
        raise HTTPException(status_code=403, detail="Only workspace owner can reactivate an admin")

    await db.users.update_one(
        {"user_id": member_id},
        {"$set": {"is_active": True, "reactivated_at": datetime.now(timezone.utc).isoformat(), "reactivated_by": user["user_id"]}},
    )
    allow_user_sessions(member_id)
    await log_audit_event(
        actor_user=user,
        action="admin_user_reactivated",
        target_type="user",
        target_id=member_id,
        workspace_owner_id=workspace_owner_id,
    )
    return {"message": "User reactivated", "user_id": member_id}


@router.get("/admin/users/{member_id}/delete-impact")
async def get_workspace_user_delete_impact(member_id: str, user: dict = Depends(get_current_agent)):
    """Preview linked records before hard-deleting a user."""
    if not is_workspace_owner(user):
        raise HTTPException(status_code=403, detail="Only workspace owner can preview hard delete impact")
    workspace_owner_id = get_workspace_owner_id(user)
    if member_id == workspace_owner_id:
        raise HTTPException(status_code=400, detail="Cannot delete workspace owner")

    member = await db.users.find_one(
        {"user_id": member_id, "workspace_owner_id": workspace_owner_id, "role": "agent"},
        {"_id": 0, "user_id": 1, "email": 1, "workspace_role": 1, "is_active": 1},
    )
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")
    impact = await _workspace_user_delete_impact(workspace_owner_id, member_id)
    impact["has_linked_data"] = any(v > 0 for v in impact.values() if isinstance(v, int))
    return {"member": member, "impact": impact}


@router.delete("/admin/users/{member_id}")
async def hard_delete_workspace_user(
    member_id: str,
    force: bool = Query(False),
    user: dict = Depends(get_current_agent),
):
    """Hard delete team user (owner only, with impact guard)."""
    if not is_workspace_owner(user):
        raise HTTPException(status_code=403, detail="Only workspace owner can hard delete users")
    workspace_owner_id = get_workspace_owner_id(user)
    if member_id == workspace_owner_id:
        raise HTTPException(status_code=400, detail="Cannot delete workspace owner")

    member = await db.users.find_one(
        {"user_id": member_id, "workspace_owner_id": workspace_owner_id, "role": "agent"},
        {"_id": 0, "user_id": 1, "email": 1, "workspace_role": 1},
    )
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")

    impact = await _workspace_user_delete_impact(workspace_owner_id, member_id)
    has_linked_data = any(v > 0 for v in impact.values() if isinstance(v, int))
    if has_linked_data and not force:
        raise HTTPException(status_code=400, detail="User has linked records. Re-run with force=true after reviewing delete impact.")

    invalidate_user_sessions(member_id)
    await db.user_activity_tracking.delete_many({"user_id": member_id})
    await db.notifications.delete_many({"user_id": member_id})
    await db.team_invitations.update_many(
        {"accepted_by": member_id, "invited_by": workspace_owner_id},
        {"$set": {"status": "revoked", "revoked_at": datetime.now(timezone.utc).isoformat(), "revoked_by": user["user_id"]}},
    )
    result = await db.users.delete_one({"user_id": member_id, "workspace_owner_id": workspace_owner_id, "role": "agent"})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Team member not found")

    await log_audit_event(
        actor_user=user,
        action="admin_user_hard_deleted",
        target_type="user",
        target_id=member_id,
        workspace_owner_id=workspace_owner_id,
        metadata={"impact": impact, "email": member.get("email")},
    )
    return {"message": "User hard deleted", "user_id": member_id, "impact": impact}


@router.get("/admin/audit-logs")
async def list_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_agent),
):
    """List workspace audit logs."""
    if not is_workspace_admin(user):
        raise HTTPException(status_code=403, detail="Workspace admin access required")
    workspace_owner_id = get_workspace_owner_id(user)
    rows = await db.audit_logs.find(
        {"workspace_owner_id": workspace_owner_id}, {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return rows

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

