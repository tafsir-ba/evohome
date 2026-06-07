"""
Gantt tool auth — logged-in users or anonymous browser sessions (no CMP coupling).
"""
import re

from fastapi import HTTPException, Request

from core.auth import extract_token, get_current_user

GANTT_SESSION_HEADER = "X-Gantt-Session"
_GANTT_SESSION_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


async def get_gantt_actor(request: Request) -> dict:
    """
    Resolve the Gantt actor for a request.
    - Valid login token → authenticated user (owner_user_id = user_id)
    - No token → anonymous guest via X-Gantt-Session (owner_user_id = gantt_guest_{uuid})
    """
    token = extract_token(request)
    if token:
        return await get_current_user(request)

    session_id = (request.headers.get(GANTT_SESSION_HEADER) or "").strip()
    if not session_id or not _GANTT_SESSION_PATTERN.match(session_id):
        raise HTTPException(
            status_code=401,
            detail=(
                "Not authenticated. Log in or provide a valid "
                f"{GANTT_SESSION_HEADER} header."
            ),
        )

    return {
        "user_id": f"gantt_guest_{session_id}",
        "role": "guest",
        "is_guest": True,
    }
