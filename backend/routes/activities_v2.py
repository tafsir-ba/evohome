"""
Activity Routes — Canonical Implementation.

Thin route layer. No is_demo. No business logic.
File I/O stays here. Everything else delegates to activity_service.
"""
import uuid
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

from database import db
from core.auth import get_current_user, get_current_agent
from services import activity_service

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
ACTIVITY_UPLOAD_DIR = UPLOAD_DIR / "activities"
ACTIVITY_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 20 * 1024 * 1024
ALLOWED_FILE_TYPES = {
    'image': ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/gif'],
    'pdf': ['application/pdf'],
}

router = APIRouter()


# ── Request schemas ──

class ActivityReplyCreate(BaseModel):
    content: str


class ActivityUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


# ── Routes ──

@router.post("/activities")
async def create_activity(
    type: str = Form(...),
    project_id: str = Form(...),
    client_ids: str = Form(...),
    title: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    unit_id: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user: dict = Depends(get_current_agent),
):
    """Create a new activity. Agent only."""
    if type not in activity_service.VALID_ACTIVITY_TYPES:
        raise HTTPException(status_code=400, detail="Invalid activity type")

    recipient_ids = [cid.strip() for cid in client_ids.split(',') if cid.strip()]
    if not recipient_ids:
        raise HTTPException(status_code=400, detail="At least one client_id is required")

    project = await db.projects.find_one(
        {"project_id": project_id, "agent_id": user['user_id']}, {"_id": 0}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    for cid in recipient_ids:
        c = await db.clients.find_one(
            {"client_id": cid, "agent_id": user['user_id']}, {"_id": 0}
        )
        if not c:
            raise HTTPException(status_code=400, detail=f"Client {cid} not found or not owned by you")

    if type in ("message", "status") and not content:
        raise HTTPException(status_code=400, detail="Content is required for message/status activities")
    if type in ("image", "pdf") and not file:
        raise HTTPException(status_code=400, detail=f"File is required for {type} activities")

    # File I/O (route responsibility)
    file_url = file_name = None
    file_size = None
    if file:
        file_content = await file.read()
        file_size = len(file_content)
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File too large. Max {MAX_FILE_SIZE // (1024*1024)}MB")
        ct = file.content_type or 'application/octet-stream'
        if type == "image" and ct not in ALLOWED_FILE_TYPES['image']:
            raise HTTPException(status_code=400, detail="Invalid image type")
        if type == "pdf" and ct not in ALLOWED_FILE_TYPES['pdf']:
            raise HTTPException(status_code=400, detail="Only PDF allowed")

        fid = uuid.uuid4().hex[:12]
        ext = Path(file.filename).suffix if file.filename else ('.jpg' if type == 'image' else '.pdf')
        filename = f"{fid}_{file.filename or f'upload{ext}'}"
        (ACTIVITY_UPLOAD_DIR / filename).write_bytes(file_content)
        file_url = f"/api/activities/files/{filename}"
        file_name = file.filename

    return await activity_service.create_and_distribute_activity(
        author_id=user['user_id'],
        activity_type=type,
        project_id=project_id,
        recipient_client_ids=recipient_ids,
        title=title,
        content=content,
        file_url=file_url,
        file_name=file_name,
        file_size=file_size,
        unit_id=unit_id,
        agent_user=user,
    )


@router.get("/activities")
async def get_activities(
    project_id: Optional[str] = None,
    client_id: Optional[str] = None,
    unit_id: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    user: dict = Depends(get_current_user),
):
    """List activities scoped by role."""
    if user['role'] == 'agent':
        if project_id:
            p = await db.projects.find_one(
                {"project_id": project_id, "agent_id": user['user_id']}
            )
            if not p:
                raise HTTPException(status_code=404, detail="Project not found")
        if client_id:
            c = await db.clients.find_one(
                {"client_id": client_id, "agent_id": user['user_id']}
            )
            if not c:
                raise HTTPException(status_code=404, detail="Client not found")

    return await activity_service.list_activities(
        user_id=user['user_id'],
        role=user['role'],
        project_id=project_id,
        client_id=client_id,
        unit_id=unit_id,
        activity_type=type,
        limit=limit,
        offset=offset,
    )


@router.post("/activities/mark-seen")
async def mark_activities_seen(user: dict = Depends(get_current_user)):
    """Mark activities as seen."""
    ts = await activity_service.mark_seen(user['user_id'])
    return {"last_seen_at": ts}


@router.get("/activities/unread-count")
async def get_unread_count(user: dict = Depends(get_current_user)):
    """Get unread activity count."""
    return await activity_service.get_unread_count(user['user_id'], user['role'])


@router.get("/activities/files/demo/{filename}")
async def get_demo_activity_file(filename: str, user: dict = Depends(get_current_user)):
    """Serve demo activity file attachments."""
    file_path = ACTIVITY_UPLOAD_DIR / "demo" / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type=_media_type(file_path), filename=filename)


@router.get("/activities/files/{filename}")
async def get_activity_file(filename: str, user: dict = Depends(get_current_user)):
    """Serve activity file attachments."""
    file_path = ACTIVITY_UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type=_media_type(file_path), filename=filename)


@router.get("/activities/{activity_id}")
async def get_activity(activity_id: str, user: dict = Depends(get_current_user)):
    """Get single activity with replies. Role-based access."""
    if user['role'] == 'buyer':
        if not await activity_service.can_buyer_access_activity(user['user_id'], activity_id):
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        act = await db.activities.find_one({"activity_id": activity_id}, {"_id": 0, "author_id": 1, "project_id": 1})
        if not act:
            raise HTTPException(status_code=404, detail="Activity not found")
        if act['author_id'] != user['user_id']:
            p = await db.projects.find_one(
                {"project_id": act['project_id'], "agent_id": user['user_id']}
            )
            if not p:
                raise HTTPException(status_code=403, detail="Access denied")

    detail = await activity_service.get_activity_detail(activity_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Activity not found")
    return detail


@router.post("/activities/{activity_id}/send")
async def send_draft_activity(activity_id: str, user: dict = Depends(get_current_agent)):
    """Send a draft activity to recipients."""
    activity = await db.activities.find_one(
        {"activity_id": activity_id, "author_id": user['user_id']}, {"_id": 0}
    )
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    if not activity.get('is_draft'):
        raise HTTPException(status_code=400, detail="Activity is not a draft")

    recipients = activity.get('draft_recipients', [])
    if not recipients:
        raise HTTPException(status_code=400, detail="No recipients specified")
    for cid in recipients:
        c = await db.clients.find_one({"client_id": cid, "agent_id": user['user_id']}, {"_id": 0})
        if not c:
            raise HTTPException(status_code=400, detail=f"Client {cid} not found")

    result = await activity_service.send_draft_activity(activity_id, user['user_id'], user)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to send draft")
    return result


@router.post("/activities/{activity_id}/reply")
async def reply_to_activity(
    activity_id: str,
    reply_data: ActivityReplyCreate,
    user: dict = Depends(get_current_user),
):
    """Reply to an activity. Both buyers and agents can reply."""
    activity = await db.activities.find_one({"activity_id": activity_id}, {"_id": 0})
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    if user['role'] == 'buyer':
        if not await activity_service.can_buyer_access_activity(user['user_id'], activity_id):
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        if activity['author_id'] != user['user_id']:
            p = await db.projects.find_one(
                {"project_id": activity['project_id'], "agent_id": user['user_id']}
            )
            if not p:
                raise HTTPException(status_code=403, detail="Access denied")

    return await activity_service.create_reply(
        activity_id, user['user_id'], user['role'], reply_data.content
    )


@router.post("/activities/{activity_id}/request-change")
async def request_activity_change(activity_id: str, user: dict = Depends(get_current_user)):
    """Request changes on a file-type activity. Buyer only."""
    if user['role'] != 'buyer':
        raise HTTPException(status_code=403, detail="Only buyers can request changes")

    activity = await db.activities.find_one({"activity_id": activity_id}, {"_id": 0})
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    if not await activity_service.can_buyer_access_activity(user['user_id'], activity_id):
        raise HTTPException(status_code=403, detail="Access denied")

    if activity['type'] != 'file':
        raise HTTPException(status_code=400, detail="Change requests only for file-type activities")

    await activity_service.request_change(activity_id)
    return {"message": "Change requested", "status": "change_requested"}


@router.delete("/activities/{activity_id}")
async def delete_activity(activity_id: str, user: dict = Depends(get_current_agent)):
    """Delete an activity. Agent only."""
    deleted = await activity_service.delete_activity(activity_id, user['user_id'])
    if not deleted:
        raise HTTPException(status_code=404, detail="Activity not found")
    return {"message": "Activity deleted successfully"}


@router.put("/activities/{activity_id}")
async def update_activity(
    activity_id: str,
    data: ActivityUpdate,
    user: dict = Depends(get_current_agent),
):
    """Update an activity. Agent only."""
    result = await activity_service.update_activity(
        activity_id, user['user_id'], data.title, data.content
    )
    if not result:
        raise HTTPException(status_code=404, detail="Activity not found")
    return result


def _media_type(path: Path) -> str:
    m = {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
        '.webp': 'image/webp', '.gif': 'image/gif', '.pdf': 'application/pdf',
    }
    return m.get(path.suffix.lower(), 'application/octet-stream')
