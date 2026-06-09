"""
Gantt invite-only login — allowlist enforced on carib-recon.org auth.
"""
import os
from typing import Optional, Set

from fastapi import HTTPException

GANTT_LOGIN_DENIED_MESSAGE = (
    "Login is not available for this account. Access to this application is by invitation only."
)
GANTT_REGISTRATION_CLOSED_MESSAGE = (
    "Account registration is not available. Access is by invitation only."
)

_DEFAULT_GANTT_ALLOWED_LOGIN_EMAILS = (
    "patricia.r.francis@gmail.com,vanessa@evo-home.ch,tafsir@evo-home.ch"
)
GANTT_ALLOWED_LOGIN_EMAILS: Set[str] = {
    e.strip().lower()
    for e in os.environ.get(
        "GANTT_ALLOWED_LOGIN_EMAILS", _DEFAULT_GANTT_ALLOWED_LOGIN_EMAILS
    ).split(",")
    if e.strip()
}


def normalize_gantt_email(email: str) -> str:
    return (email or "").strip().lower()


def is_gantt_allowed_login_email(email: str) -> bool:
    return normalize_gantt_email(email) in GANTT_ALLOWED_LOGIN_EMAILS


def is_gantt_auth_request(
    request: Optional[object], redirect_uri: Optional[str] = None
) -> bool:
    from core.gantt_site import is_gantt_request

    if is_gantt_request(request):
        return True
    uri = (redirect_uri or "").strip().lower()
    return "carib-recon.org" in uri


def enforce_gantt_login_allowed(
    request: Optional[object],
    email: str,
    *,
    redirect_uri: Optional[str] = None,
) -> None:
    if not is_gantt_auth_request(request, redirect_uri):
        return
    if not is_gantt_allowed_login_email(email):
        raise HTTPException(status_code=403, detail=GANTT_LOGIN_DENIED_MESSAGE)


def enforce_gantt_registration_closed(request: Optional[object]) -> None:
    from core.gantt_site import is_gantt_request

    if is_gantt_request(request):
        raise HTTPException(status_code=403, detail=GANTT_REGISTRATION_CLOSED_MESSAGE)
