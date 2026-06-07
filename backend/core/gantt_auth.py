"""
Gantt tool auth — authenticated users only (projects tied to real accounts).
"""
from fastapi import HTTPException, Request

from core.auth import extract_token, get_current_user


async def get_gantt_actor(request: Request) -> dict:
    """
    Resolve the Gantt actor for a request.
    Requires a valid login session — guest/anonymous access is not allowed.
    """
    token = extract_token(request)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please log in to access Gantt projects.",
        )

    user = await get_current_user(request)
    user_id = str(user.get("user_id", ""))
    if user_id.startswith("gantt_guest_"):
        raise HTTPException(
            status_code=401,
            detail="Guest access is no longer supported. Please log in.",
        )
    return user
