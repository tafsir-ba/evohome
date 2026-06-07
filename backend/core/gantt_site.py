"""
Gantt host detection — shared by auth emails and site-specific configuration.
"""
import os
from typing import Optional

from fastapi import Request

from services.gantt_constants import GANTT_APP_NAME

GANTT_SENDER_EMAIL = os.environ.get("GANTT_SENDER_EMAIL", "").strip()
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


def is_gantt_request(request: Optional[Request]) -> bool:
    origin = request_origin(request)
    return bool(origin and origin in GANTT_ORIGINS)


def gantt_frontend_url(request: Optional[Request]) -> Optional[str]:
    origin = request_origin(request)
    if origin and origin in GANTT_ORIGINS:
        return origin
    return None


def gantt_welcome_email_data(request: Optional[Request], name: str) -> dict:
    """Extra template fields when account is created from the Gantt host."""
    if not is_gantt_request(request):
        return {}
    return {
        "brand": "gantt",
        "app_name": GANTT_APP_NAME,
        "frontend_url": gantt_frontend_url(request) or GANTT_ORIGINS[0],
        "project_name": "your Gantt projects",
        "name": name,
        "role": "agent",
    }
