"""
Gantt / CRC site detection — shared by auth emails and site-specific configuration.
"""
import os
from typing import Optional, Set

from fastapi import Request

GANTT_SENDER_EMAIL = os.environ.get("GANTT_SENDER_EMAIL", "").strip()

CARIB_HOSTS: Set[str] = {
    h.strip().lower()
    for h in os.environ.get(
        "CARIB_HOSTS", "carib-recon.org,www.carib-recon.org"
    ).split(",")
    if h.strip()
}

GANTT_ORIGINS = [
    o.strip().rstrip("/")
    for o in os.environ.get(
        "GANTT_ORIGINS",
        "https://carib-recon.org,https://www.carib-recon.org",
    ).split(",")
    if o.strip()
]


def request_origin(request: Optional[Request]) -> str:
    if not request:
        return ""
    return (request.headers.get("origin") or "").strip().rstrip("/")


def _request_host(request: Optional[Request]) -> str:
    if not request:
        return ""
    return (request.headers.get("host") or "").split(":")[0].strip().lower()


def is_gantt_request(request: Optional[Request]) -> bool:
    origin = request_origin(request)
    if origin and origin in GANTT_ORIGINS:
        return True
    host = _request_host(request)
    if host in CARIB_HOSTS:
        return True
    if request:
        referer = (request.headers.get("referer") or "").lower()
        if "carib-recon.org" in referer:
            return True
    return False


def gantt_frontend_url(request: Optional[Request]) -> Optional[str]:
    origin = request_origin(request)
    if origin and origin in GANTT_ORIGINS:
        return origin
    host = _request_host(request)
    if host in CARIB_HOSTS:
        return f"https://{host}"
    return None


def gantt_welcome_email_data(request: Optional[Request], name: str) -> dict:
    """Extra template fields when account is created from the CRC site."""
    if not is_gantt_request(request):
        return {}
    from services.gantt_constants import GANTT_APP_NAME

    return {
        "brand": "gantt",
        "app_name": GANTT_APP_NAME,
        "frontend_url": gantt_frontend_url(request) or GANTT_ORIGINS[0],
        "project_name": "your Gantt projects",
        "name": name,
        "role": "agent",
    }
