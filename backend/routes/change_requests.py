"""
Change Request routes — thin layer over change_request_service.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List

from core.auth import get_current_user, get_current_agent
from core.access_scope import resolve_agent_access_scope
from database import db
from services import change_request_service
from services.change_request_access import user_can_access_change_request, user_can_access_entity
from services.document_service import document_action

logger = logging.getLogger(__name__)

router = APIRouter()


class CreateChangeRequestBody(BaseModel):
    entity_type: str
    entity_id: str
    message: str
    project_id: Optional[str] = None
    attachments: Optional[List[dict]] = None


class RespondBody(BaseModel):
    message: str
    attachments: Optional[List[dict]] = None


class ResolveBody(BaseModel):
    resolution_note: Optional[str] = None


@router.post("/change-requests")
async def create_change_request(body: CreateChangeRequestBody, user: dict = Depends(get_current_user)):
    """Create a change request (buyer or agent)."""
    role = user.get("role", "buyer")

    if not await user_can_access_entity(user, body.entity_type, body.entity_id):
        raise HTTPException(status_code=403, detail="Forbidden")

    # Buyers on quotes/invoices: single path (one notification, one document write)
    if role == "buyer" and body.entity_type in ("quote", "invoice"):
        try:
            u = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "name": 1})
            user_name = (u or {}).get("name", "")
            result = await document_action(
                document_id=body.entity_id,
                action="request_change",
                user_id=user["user_id"],
                user_role="buyer",
                user_name=user_name,
                comment=body.message,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        cr_id = result.get("change_request_id")
        if not cr_id:
            raise HTTPException(status_code=500, detail="Change request not created")
        cr = await change_request_service.get_change_request(cr_id)
        if not cr:
            raise HTTPException(status_code=500, detail="Change request not found")
        return cr

    if role == "agent":
        scope = await resolve_agent_access_scope(user)
        agent_id = scope.workspace_owner_id
    elif body.entity_type == "decision":
        dec = await db.decisions.find_one({"decision_id": body.entity_id}, {"_id": 0, "agent_id": 1})
        agent_id = (dec or {}).get("agent_id") or ""
    else:
        doc = await db.documents.find_one({"document_id": body.entity_id}, {"_id": 0, "agent_id": 1})
        agent_id = (doc or {}).get("agent_id") or user.get("agent_id", "")

    if not agent_id:
        raise HTTPException(status_code=400, detail="Could not resolve agent for change request")

    try:
        cr = await change_request_service.create_change_request(
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            message=body.message,
            created_by=user["user_id"],
            created_by_role=role,
            agent_id=agent_id,
            project_id=body.project_id,
            attachments=body.attachments,
        )
        return cr
    except Exception as e:
        logger.error(f"Create change request failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/change-requests")
async def list_change_requests(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_agent),
):
    """List change requests for the current agent."""
    scope = await resolve_agent_access_scope(user)
    return await change_request_service.list_change_requests(
        agent_id=scope.workspace_owner_id,
        accessible_project_ids=scope.accessible_project_ids,
        entity_type=entity_type,
        entity_id=entity_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get("/change-requests/entity/{entity_type}/{entity_id}")
async def get_entity_change_requests(
    entity_type: str,
    entity_id: str,
    user: dict = Depends(get_current_user),
):
    """Get all change requests for a specific entity."""
    if not await user_can_access_entity(user, entity_type, entity_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    items = await change_request_service.get_change_requests_for_entity(entity_type, entity_id)
    return {"change_requests": items}


@router.get("/change-requests/{change_request_id}")
async def get_change_request(change_request_id: str, user: dict = Depends(get_current_user)):
    """Get a single change request."""
    cr = await change_request_service.get_change_request(change_request_id)
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")
    if not await user_can_access_change_request(user, cr):
        raise HTTPException(status_code=403, detail="Forbidden")
    return cr


@router.post("/change-requests/{change_request_id}/respond")
async def respond_to_change_request(
    change_request_id: str,
    body: RespondBody,
    user: dict = Depends(get_current_user),
):
    """Add a response to a change request."""
    from core.trace import set_trace_action, set_trace_entity, set_trace_request_summary, trace_service
    set_trace_action("cr_respond")
    set_trace_entity("change_request", change_request_id)
    set_trace_request_summary({"change_request_id": change_request_id, "message_length": len(body.message)})
    trace_service("routes.change_requests.respond_to_change_request")
    try:
        role = user.get("role", "buyer")
        existing = await change_request_service.get_change_request(change_request_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Change request not found")
        if not await user_can_access_change_request(user, existing):
            raise HTTPException(status_code=403, detail="Forbidden")
        cr = await change_request_service.respond_to_change_request(
            change_request_id=change_request_id,
            message=body.message,
            author_id=user["user_id"],
            author_role=role,
            attachments=body.attachments,
            agent_scope_id=(await resolve_agent_access_scope(user)).workspace_owner_id if role == "agent" else None,
        )
        return cr
    except HTTPException:
        raise
    except ValueError as e:
        msg = str(e)
        if "Not authorized" in msg:
            raise HTTPException(status_code=403, detail=msg)
        raise HTTPException(status_code=400, detail={"error": "state_error", "message": msg, "source": "service"})


@router.post("/change-requests/{change_request_id}/resolve")
async def resolve_change_request(
    change_request_id: str,
    body: ResolveBody,
    user: dict = Depends(get_current_agent),
):
    """Resolve a change request (agent only)."""
    from core.trace import set_trace_action, set_trace_entity, set_trace_request_summary, trace_service
    set_trace_action("cr_resolve")
    set_trace_entity("change_request", change_request_id)
    set_trace_request_summary({"change_request_id": change_request_id, "has_note": bool(body.resolution_note)})
    trace_service("routes.change_requests.resolve_change_request")
    try:
        scope = await resolve_agent_access_scope(user)
        cr = await change_request_service.get_change_request(change_request_id)
        if cr and not await user_can_access_change_request(user, cr):
            raise HTTPException(status_code=403, detail="Forbidden")
        cr = await change_request_service.resolve_change_request(
            change_request_id=change_request_id,
            resolved_by=user["user_id"],
            resolution_note=body.resolution_note,
            agent_scope_id=scope.workspace_owner_id,
        )
        return cr
    except HTTPException:
        raise
    except ValueError as e:
        msg = str(e)
        if "Not authorized" in msg:
            raise HTTPException(status_code=403, detail=msg)
        raise HTTPException(status_code=400, detail={"error": "state_error", "message": msg, "source": "service"})


@router.post("/change-requests/{change_request_id}/close")
async def close_change_request(
    change_request_id: str,
    user: dict = Depends(get_current_agent),
):
    """Close a change request (agent only)."""
    from core.trace import set_trace_action, set_trace_entity, trace_service
    set_trace_action("cr_close")
    set_trace_entity("change_request", change_request_id)
    trace_service("routes.change_requests.close_change_request")
    try:
        scope = await resolve_agent_access_scope(user)
        cr = await change_request_service.get_change_request(change_request_id)
        if cr and not await user_can_access_change_request(user, cr):
            raise HTTPException(status_code=403, detail="Forbidden")
        cr = await change_request_service.close_change_request(
            change_request_id=change_request_id,
            closed_by=user["user_id"],
            agent_scope_id=scope.workspace_owner_id,
        )
        return cr
    except HTTPException:
        raise
    except ValueError as e:
        msg = str(e)
        if "Not authorized" in msg:
            raise HTTPException(status_code=403, detail=msg)
        raise HTTPException(status_code=400, detail={"error": "state_error", "message": msg, "source": "service"})
