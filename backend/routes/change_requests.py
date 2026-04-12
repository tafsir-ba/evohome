"""
Change Request routes — thin layer over change_request_service.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List

from core.auth import get_current_user, get_current_agent
from services import change_request_service

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
    try:
        role = user.get("role", "buyer")
        agent_id = user["user_id"] if role == "agent" else user.get("agent_id", "")

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
    return await change_request_service.list_change_requests(
        agent_id=user["user_id"],
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
    items = await change_request_service.get_change_requests_for_entity(entity_type, entity_id)
    return {"change_requests": items}


@router.get("/change-requests/{change_request_id}")
async def get_change_request(change_request_id: str, user: dict = Depends(get_current_user)):
    """Get a single change request."""
    cr = await change_request_service.get_change_request(change_request_id)
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")
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
        cr = await change_request_service.respond_to_change_request(
            change_request_id=change_request_id,
            message=body.message,
            author_id=user["user_id"],
            author_role=role,
            attachments=body.attachments,
        )
        return cr
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


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
        cr = await change_request_service.resolve_change_request(
            change_request_id=change_request_id,
            resolved_by=user["user_id"],
            resolution_note=body.resolution_note,
        )
        return cr
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


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
        cr = await change_request_service.close_change_request(
            change_request_id=change_request_id,
            closed_by=user["user_id"],
        )
        return cr
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
