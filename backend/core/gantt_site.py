"""
Gantt / CRC site detection — shared by auth emails and site-specific configuration.
"""
import os
from typing import Optional, Set
from urllib.parse import urlparse

from fastapi import Request

GANTT_SENDER_EMAIL = os.environ.get("GANTT_SENDER_EMAIL", "").strip()

# Deleted from the app. Not a CRC host even if present in CARIB_HOSTS / GANTT_ORIGINS.
REMOVED_CARIB_HOSTS: Set[str] = {"app.carib-recon.org"}


def url_host(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    return (parsed.hostname or "").lower()


def _without_removed_hosts(hosts: Set[str]) -> Set[str]:
    return {h for h in hosts if h not in REMOVED_CARIB_HOSTS}


CARIB_HOSTS: Set[str] = _without_removed_hosts({
    h.strip().lower()
    for h in os.environ.get(
        "CARIB_HOSTS", "carib-recon.org,www.carib-recon.org"
    ).split(",")
    if h.strip()
})

GANTT_ORIGINS = [
    o.strip().rstrip("/")
    for o in os.environ.get(
        "GANTT_ORIGINS",
        "https://carib-recon.org,https://www.carib-recon.org",
    ).split(",")
    if o.strip() and url_host(o) not in REMOVED_CARIB_HOSTS
]


def is_carib_host(hostname: str) -> bool:
    host = (hostname or "").split(":")[0].strip().lower()
    if not host or host in REMOVED_CARIB_HOSTS:
        return False
    return host in CARIB_HOSTS


def filter_removed_origins(origins):
    """Drop app.carib-recon.org even when CORS_ORIGINS or FRONTEND_URL still lists it."""
    kept = []
    for origin in origins:
        if url_host(origin) in REMOVED_CARIB_HOSTS:
            continue
        kept.append(origin)
    return kept


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
    if is_carib_host(host):
        return True
    if request:
        referer = request.headers.get("referer") or ""
        if is_carib_host(url_host(referer)):
            return True
    return False


def gantt_frontend_url(request: Optional[Request]) -> Optional[str]:
    origin = request_origin(request)
    if origin and origin in GANTT_ORIGINS:
        return origin
    host = _request_host(request)
    if is_carib_host(host):
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
