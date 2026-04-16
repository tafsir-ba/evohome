"""
Activity Routes — Canonical Implementation.

Thin route layer. No is_demo. No business logic.
File I/O stays here. Everything else delegates to activity_service.

New activity uploads use services.file_service (DigitalOcean Spaces when SPACES_* is set),
same as vault/logos. Legacy rows may still reference /api/activities/files/... on local disk.
"""
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from database import db
from core.auth import get_current_user, get_current_agent
from core.access_control import get_workspace_owner_id, get_accessible_project_ids, can_access_project, can_access_client
from services import activity_service, file_service

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
ACTIVITY_UPLOAD_DIR = UPLOAD_DIR / "activities"
ACTIVITY_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _relative_path_from_file_url(file_url: str) -> Optional[str]:
    """Return path under activities/ from stored file_url (supports multi-segment paths)."""
    if not file_url:
        return None
    fu = file_url.strip().split("?")[0].split("#")[0]
    marker = "/activities/files/"
    if marker not in fu:
        return None
    rel = fu.split(marker, 1)[1].lstrip("/")
    return rel or None


def _resolve_safe_activity_path(rel: str) -> Path:
    """Resolve a path under ACTIVITY_UPLOAD_DIR; reject traversal."""
    if not rel or not isinstance(rel, str):
        raise HTTPException(status_code=400, detail="Invalid file reference")
    rel = rel.strip().replace("\\", "/")
    if ".." in rel or rel.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid file reference")
    parts = [p for p in rel.split("/") if p and p != "."]
    if not parts or ".." in parts:
        raise HTTPException(status_code=400, detail="Invalid file reference")
    file_path = ACTIVITY_UPLOAD_DIR.joinpath(*parts).resolve()
    base = ACTIVITY_UPLOAD_DIR.resolve()
    try:
        file_path.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file reference")
    return file_path


router = APIRouter()


async def _ensure_agent_activity_access(user: dict, activity_id: str) -> dict:
    activity = await db.activities.find_one({"activity_id": activity_id}, {"_id": 0})
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    if not await can_access_project(user, activity.get("project_id")):
        raise HTTPException(status_code=403, detail="Access denied")
    return activity


# ── Request schemas ──

class ActivityReplyCreate(BaseModel):
    content: str


class ActivityUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    project_id: Optional[str] = None
    client_ids: Optional[list[str]] = None


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

    scope_agent_id = get_workspace_owner_id(user)
    if not await can_access_project(user, project_id):
        raise HTTPException(status_code=403, detail="Access denied")

    for cid in recipient_ids:
        c = await db.clients.find_one({"client_id": cid, "agent_id": scope_agent_id}, {"_id": 0})
        if not c:
            raise HTTPException(status_code=400, detail=f"Client {cid} not found or not owned by you")
        if not await can_access_client(user, cid):
            raise HTTPException(status_code=403, detail=f"Access denied to client {cid}")
        if c.get("project_id") != project_id:
            raise HTTPException(status_code=400, detail=f"Client {cid} is not in the selected project")

    if type in ("message", "status") and not content:
        raise HTTPException(status_code=400, detail="Content is required for message/status activities")
    if type in ("image", "pdf") and not file:
        raise HTTPException(status_code=400, detail=f"File is required for {type} activities")

    # Persist via file_service → Spaces when configured (else local /api/uploads/…)
    file_url = file_name = None
    file_size = None
    stored_filename = None
    if file:
        meta = await file_service.save_activity_attachment(file, type)
        file_url = meta["url"]
        file_name = meta["original_filename"]
        file_size = meta["file_size"]
        stored_filename = meta["stored_filename"]

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
        stored_filename=stored_filename,
    )


@router.get("/activities")
async def get_activities(
    project_id: Optional[str] = None,
    client_id: Optional[str] = None,
    unit_id: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    """List activities scoped by role."""
    if user['role'] == 'agent':
        scope_agent_id = get_workspace_owner_id(user)
        if project_id:
            p = await db.projects.find_one(
                {"project_id": project_id, "agent_id": scope_agent_id}
            )
            if not p:
                raise HTTPException(status_code=404, detail="Project not found")
        if client_id:
            c = await db.clients.find_one(
                {"client_id": client_id, "agent_id": scope_agent_id}
            )
            if not c:
                raise HTTPException(status_code=404, detail="Client not found")

    return await activity_service.list_activities(
        user_id=user['user_id'],
        role=user['role'],
        agent_scope_id=get_workspace_owner_id(user) if user['role'] == 'agent' else None,
        accessible_project_ids=await get_accessible_project_ids(user) if user['role'] == 'agent' else None,
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
    return await activity_service.get_unread_count(
        user['user_id'],
        user['role'],
        get_workspace_owner_id(user) if user['role'] == 'agent' else None,
        await get_accessible_project_ids(user) if user['role'] == 'agent' else None,
    )


@router.get("/activities/files/demo/{filename:path}")
async def get_demo_activity_file(filename: str, user: dict = Depends(get_current_user)):
    """Serve demo activity file attachments."""
    file_path = _resolve_safe_activity_path(f"demo/{filename}")
    if not file_path.exists():
        logger.warning("demo activity file missing path=%s", file_path)
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type=_media_type(file_path), filename=file_path.name)


@router.get("/activities/files/{filename:path}")
async def get_activity_file(filename: str, user: dict = Depends(get_current_user)):
    """Serve activity file attachments (path form supports legacy subpaths in file_url)."""
    file_path = _resolve_safe_activity_path(filename)
    if not file_path.exists():
        logger.warning("activity file missing path=%s", file_path)
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type=_media_type(file_path), filename=file_path.name)


@router.get("/activities/{activity_id}/attachment")
async def get_activity_attachment(activity_id: str, user: dict = Depends(get_current_user)):
    """
    Stream the file for an activity using the same auth rules as viewing the activity.
    Prefer this from the SPA so fetch() uses /api/activities/{id}/attachment with Bearer
    (avoids cross-origin/CORS issues with direct /activities/files/... URLs).
    """
    activity = await db.activities.find_one({"activity_id": activity_id}, {"_id": 0})
    if not activity or not activity.get("file_url"):
        raise HTTPException(status_code=404, detail="Attachment not found")

    if user["role"] == "buyer":
        if not await activity_service.can_buyer_access_activity(user["user_id"], activity_id):
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        await _ensure_agent_activity_access(user, activity_id)

    fu = (activity.get("file_url") or "").strip()
    stored = activity.get("stored_filename")

    candidates = []
    if isinstance(stored, str) and stored.strip():
        candidates.append(stored.strip())
    if fu:
        s = file_service.stored_filename_from_public_url(fu)
        if s and s not in candidates:
            candidates.append(s)

    for sf in candidates:
        try:
            body, ct = file_service.read_stored_file_bytes(sf)
            return Response(content=body, media_type=ct)
        except FileNotFoundError:
            logger.warning(
                "activity attachment missing in storage activity_id=%s stored_filename=%s",
                activity_id,
                sf,
            )
        except ValueError:
            pass

    rel = _relative_path_from_file_url(fu)
    if rel:
        file_path = _resolve_safe_activity_path(rel)
        if file_path.exists():
            return FileResponse(
                file_path, media_type=_media_type(file_path), filename=file_path.name
            )

    logger.warning(
        "activity attachment not found activity_id=%s file_url=%s",
        activity_id,
        fu,
    )
    raise HTTPException(status_code=404, detail="File not found")


@router.get("/activities/{activity_id}")
async def get_activity(activity_id: str, user: dict = Depends(get_current_user)):
    """Get single activity with replies. Role-based access."""
    if user['role'] == 'buyer':
        if not await activity_service.can_buyer_access_activity(user['user_id'], activity_id):
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        await _ensure_agent_activity_access(user, activity_id)

    detail = await activity_service.get_activity_detail(activity_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Activity not found")
    return detail


@router.post("/activities/{activity_id}/send")
async def send_draft_activity(activity_id: str, user: dict = Depends(get_current_agent)):
    """Send a draft activity to recipients."""
    activity = await _ensure_agent_activity_access(user, activity_id)
    if not activity.get('is_draft'):
        raise HTTPException(status_code=400, detail="Activity is not a draft")

    recipients = activity.get('draft_recipients', [])
    if not recipients:
        raise HTTPException(status_code=400, detail="No recipients specified")
    for cid in recipients:
        c = await db.clients.find_one({"client_id": cid, "agent_id": get_workspace_owner_id(user)}, {"_id": 0})
        if not c:
            raise HTTPException(status_code=400, detail=f"Client {cid} not found")
        if not await can_access_client(user, cid):
            raise HTTPException(status_code=403, detail=f"Access denied to client {cid}")

    result = await activity_service.send_draft_activity(activity_id, activity.get("author_id"), user)
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
        await _ensure_agent_activity_access(user, activity_id)

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
    activity = await _ensure_agent_activity_access(user, activity_id)
    deleted = await activity_service.delete_activity(activity_id, activity.get("author_id"))
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
    activity = await _ensure_agent_activity_access(user, activity_id)
    update_payload = data.model_dump(exclude_none=True)
    target_project_id = update_payload.get("project_id") or activity.get("project_id")
    scope_agent_id = get_workspace_owner_id(user)

    if "project_id" in update_payload:
        if not await can_access_project(user, update_payload["project_id"]):
            raise HTTPException(status_code=403, detail="Access denied to project")

    if "client_ids" in update_payload:
        client_ids = [
            str(cid).strip()
            for cid in (update_payload.get("client_ids") or [])
            if str(cid).strip()
        ]
        if not client_ids:
            raise HTTPException(status_code=400, detail="At least one recipient is required")
        clients = await db.clients.find(
            {
                "client_id": {"$in": client_ids},
                "agent_id": scope_agent_id,
                "project_id": target_project_id,
            },
            {"_id": 0, "client_id": 1},
        ).to_list(len(client_ids))
        found = {c["client_id"] for c in clients}
        missing = [cid for cid in client_ids if cid not in found]
        if missing:
            raise HTTPException(status_code=400, detail=f"Invalid recipients for selected project: {', '.join(missing)}")
        for cid in client_ids:
            if not await can_access_client(user, cid):
                raise HTTPException(status_code=403, detail=f"Access denied to client {cid}")
        update_payload["client_ids"] = client_ids

    result = await activity_service.update_activity(
        activity_id, activity.get("author_id"), update_payload
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
