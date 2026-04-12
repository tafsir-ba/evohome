"""
Buyer Portal Route — Single endpoint for the buyer's entire world.
"""
from fastapi import APIRouter, Depends
from core.auth import get_current_user
from services import buyer_portal_service

router = APIRouter()


@router.get("/buyer/portal")
async def get_buyer_portal(user: dict = Depends(get_current_user)):
    """
    Returns everything the buyer needs in one call:
    project, branding, documents, vault files, change requests,
    decisions, team, construction timeline, unread count.
    All URLs resolved. All names enriched. No frontend stitching.
    """
    if user["role"] != "buyer":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Buyer access only"})

    return await buyer_portal_service.get_buyer_portal(user["user_id"])
