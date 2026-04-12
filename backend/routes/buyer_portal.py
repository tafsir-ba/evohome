"""
Buyer Portal Route — Single endpoint for the buyer's entire world.
All reads go through GET /buyer/portal.
All mutations go through POST /buyer/portal/action.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from core.auth import get_current_user
from services import buyer_portal_service

router = APIRouter()


def _require_buyer(user: dict):
    if user["role"] != "buyer":
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Buyer access only"})


@router.get("/buyer/portal")
async def get_buyer_portal(user: dict = Depends(get_current_user)):
    """Single read endpoint. Returns everything the buyer needs."""
    _require_buyer(user)
    return await buyer_portal_service.get_buyer_portal(user["user_id"])


class BuyerAction(BaseModel):
    action: str  # approve, reject, request_change, confirm_payment, respond_decision, mark_seen
    document_id: Optional[str] = None
    decision_id: Optional[str] = None
    comment: Optional[str] = None
    option_id: Optional[str] = None


@router.post("/buyer/portal/action")
async def buyer_portal_action(body: BuyerAction, user: dict = Depends(get_current_user)):
    """
    Single mutation endpoint. All buyer→agent communication goes through here.
    The sync layer processes the action and returns the updated portal state.
    """
    _require_buyer(user)
    try:
        return await buyer_portal_service.process_buyer_action(
            buyer_id=user["user_id"],
            action=body.action,
            document_id=body.document_id,
            decision_id=body.decision_id,
            comment=body.comment,
            option_id=body.option_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
