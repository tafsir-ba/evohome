"""
Decision routes — thin layer over decision_service.
Agent CRUD + send, Buyer approve/reject/change-request.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone

from core.auth import get_current_user, get_current_agent, get_current_buyer
from services import decision_service, file_service
from database import db

logger = logging.getLogger(__name__)

router = APIRouter()


class CreateDecisionBody(BaseModel):
    project_id: str
    title: str
    description: str
    deadline: Optional[str] = None
    external_link: Optional[str] = None
    coverage_type: str = "project"
    unit_ids: Optional[List[str]] = None
    client_ids: Optional[List[str]] = None
    attachments: Optional[List[dict]] = None


class UpdateDecisionBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    deadline: Optional[str] = None
    external_link: Optional[str] = None
    coverage_type: Optional[str] = None
    unit_ids: Optional[List[str]] = None
    client_ids: Optional[List[str]] = None
    attachments: Optional[List[dict]] = None


class BuyerRespondBody(BaseModel):
    action: str  # "approved", "rejected", "request_change"
    comment: Optional[str] = None


# ── Agent Routes ──

@router.post("/decisions")
async def create_decision(body: CreateDecisionBody, user: dict = Depends(get_current_agent)):
    """Create a new decision (agent only)."""
    try:
        decision = await decision_service.create_decision(
            agent_id=user["user_id"],
            project_id=body.project_id,
            title=body.title,
            description=body.description,
            deadline=body.deadline,
            attachments=body.attachments,
            external_link=body.external_link,
            coverage_type=body.coverage_type,
            unit_ids=body.unit_ids,
            client_ids=body.client_ids,
        )
        return decision
    except Exception as e:
        logger.error(f"Create decision failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/decisions")
async def list_decisions(
    project_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_agent),
):
    """List decisions for the current agent."""
    return await decision_service.list_decisions(
        agent_id=user["user_id"],
        project_id=project_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get("/decisions/{decision_id}")
async def get_decision(decision_id: str, user: dict = Depends(get_current_user)):
    """Get decision detail with recipients."""
    decision = await decision_service.get_decision_with_recipients(decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    return decision


@router.put("/decisions/{decision_id}")
async def update_decision(decision_id: str, body: UpdateDecisionBody, user: dict = Depends(get_current_agent)):
    """Update a draft decision."""
    try:
        updates = body.dict(exclude_none=True)
        if "coverage_type" in updates or "unit_ids" in updates or "client_ids" in updates:
            updates["coverage"] = {
                "type": updates.pop("coverage_type", "project"),
                "unit_ids": updates.pop("unit_ids", []),
                "client_ids": updates.pop("client_ids", []),
            }
        decision = await decision_service.update_decision(decision_id, user["user_id"], updates)
        return decision
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/decisions/{decision_id}/send")
async def send_decision(decision_id: str, user: dict = Depends(get_current_agent)):
    """Send a decision to buyers."""
    try:
        decision = await decision_service.send_decision(decision_id, user["user_id"])
        return decision
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/decisions/{decision_id}/close")
async def close_decision(decision_id: str, user: dict = Depends(get_current_agent)):
    """Close a decision (final state)."""
    try:
        decision = await decision_service.close_decision(decision_id, user["user_id"])
        return decision
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/decisions/{decision_id}")
async def delete_decision(decision_id: str, user: dict = Depends(get_current_agent)):
    """Delete a draft decision."""
    try:
        await decision_service.delete_decision(decision_id, user["user_id"])
        return {"message": "Decision deleted"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/decisions/{decision_id}/upload-attachment")
async def upload_attachment(
    decision_id: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_agent),
):
    """Upload an attachment for a decision."""
    decision = await decision_service.get_decision(decision_id)
    if not decision or decision["agent_id"] != user["user_id"]:
        raise HTTPException(status_code=404, detail="Decision not found")

    meta = await file_service.save_upload(
        file,
        "decisions",
        file_service.MAX_SIZE_VAULT,
        file_service.VAULT_MIME_TYPES,
        file_service.VAULT_EXTENSIONS,
    )

    attachment = {
        "type": "document",
        "filename": meta["original_filename"],
        "url": meta["url"],
        "stored_filename": meta["stored_filename"],
        "size": meta["file_size"],
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.decisions.update_one(
        {"decision_id": decision_id},
        {"$push": {"attachments": attachment}}
    )

    return attachment


# ── Buyer Routes ──

@router.get("/buyer/decisions")
async def list_buyer_decisions(user: dict = Depends(get_current_buyer)):
    """List decisions visible to the current buyer."""
    decisions = await decision_service.list_buyer_decisions(user["user_id"])
    return {"decisions": decisions}


@router.post("/decisions/{decision_id}/respond")
async def buyer_respond(decision_id: str, body: BuyerRespondBody, user: dict = Depends(get_current_buyer)):
    """Buyer responds to a decision."""
    try:
        # Find the buyer's client_id (by buyer_id or email match)
        buyer = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "email": 1})
        buyer_email = buyer.get("email") if buyer else None
        query = {"buyer_id": user["user_id"]}
        if buyer_email:
            query = {"$or": [{"buyer_id": user["user_id"]}, {"email": buyer_email}]}
        client = await db.clients.find_one(query, {"_id": 0, "client_id": 1})
        if not client:
            raise ValueError("No client record found for this buyer")

        decision = await decision_service.buyer_respond(
            decision_id=decision_id,
            buyer_id=user["user_id"],
            client_id=client["client_id"],
            action=body.action,
            comment=body.comment,
        )
        return decision
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
