"""
Evohome CMP — FastAPI Application Entry Point
Slim orchestrator that wires up modular routers.
Phase 3 modularization: all domain logic lives in /routes/*.py
Phase D: Production hardening (CORS, health, security headers, exception handling)
"""
import os
import uuid
import time
import logging
import traceback
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import validate_config
from core.auth import init_auth, verify_token
from core.access_control import init_access_control
from core.monitoring import capture_websocket_error, capture_exception, ErrorContext
from database import db

# Initialize config
app_config = validate_config()

# Initialize auth and access control modules with database
init_auth(db)
init_access_control(db)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')
logger = logging.getLogger(__name__)

# Upload directory
UPLOAD_DIR = Path("/app/backend/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# App version (git SHA if available, else static)
APP_VERSION = "3.1.0"
_git_sha_path = Path("/app/.git/refs/heads/main")
if _git_sha_path.exists():
    try:
        APP_VERSION = _git_sha_path.read_text().strip()[:8]
    except Exception:
        pass


# ==================== LIFESPAN ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events"""
    logger.info("Starting Evohome CMP...")

    # ── Single-field indexes (existing) ──
    try:
        await db.users.create_index("user_id", unique=True)
        await db.users.create_index("email")
        await db.projects.create_index("project_id", unique=True)
        await db.projects.create_index("agent_id")
        await db.clients.create_index("client_id", unique=True)
        await db.clients.create_index("agent_id")
        await db.clients.create_index("buyer_id")
        await db.units.create_index("unit_id", unique=True)
        await db.units.create_index("project_id")
        await db.documents.create_index("document_id", unique=True)
        await db.documents.create_index("agent_id")
        await db.documents.create_index("client_id")
        await db.timelines.create_index("timeline_id", unique=True)
        await db.timelines.create_index("project_id")
        await db.timeline_steps.create_index("step_id", unique=True)
        await db.timeline_steps.create_index("timeline_id")
        await db.notifications.create_index("user_id")
        await db.activities.create_index("activity_id", unique=True)
        await db.activities.create_index("project_id")
        await db.vault_documents.create_index("vault_document_id", unique=True)
        logger.info("Single-field indexes created/verified")
    except Exception as e:
        logger.warning(f"Index creation warning: {e}")

    # ── P2: Compound indexes for hot query paths ──
    try:
        # Projects: agent dashboard list
        await db.projects.create_index([("agent_id", 1), ("status", 1)])
        # Units: project detail page
        await db.units.create_index([("project_id", 1), ("status", 1)])
        await db.units.create_index([("agent_id", 1)])
        # Clients: project client list + buyer lookup
        await db.clients.create_index([("agent_id", 1), ("status", 1)])
        await db.clients.create_index([("project_id", 1)])
        await db.clients.create_index([("buyer_id", 1)])
        await db.clients.create_index([("unit_id", 1)])
        # Documents: agent document list
        await db.documents.create_index([("agent_id", 1), ("type", 1)])
        await db.documents.create_index([("project_id", 1)])
        await db.documents.create_index([("client_id", 1)])
        # Timeline steps: ordered by timeline + order_index
        await db.timeline_steps.create_index([("timeline_id", 1), ("order_index", 1)])
        await db.timeline_steps.create_index([("project_id", 1)])
        # Activities: project feed + author lookup
        await db.activities.create_index([("project_id", 1)])
        await db.activities.create_index([("agent_id", 1)])
        await db.activities.create_index([("author_id", 1), ("created_at", -1)])
        # Activity recipients: batch lookup by activity_id and client_id
        await db.activity_recipients.create_index("activity_id")
        await db.activity_recipients.create_index("client_id")
        # Activity replies: batch count and lookup by activity_id
        await db.activity_replies.create_index("activity_id")
        # Change requests: entity lookup and agent listing
        await db.change_requests.create_index([("entity_type", 1), ("entity_id", 1)])
        await db.change_requests.create_index([("agent_id", 1), ("status", 1)])
        # Decisions: agent listing, buyer lookup
        await db.decisions.create_index("decision_id", unique=True)
        await db.decisions.create_index([("agent_id", 1), ("status", 1)])
        await db.decisions.create_index("project_id")
        await db.decision_recipients.create_index("decision_id")
        await db.decision_recipients.create_index("client_id")
        # Notifications: user + read status (unread count query)
        await db.notifications.create_index([("user_id", 1), ("is_read", 1)])
        # Vault: agent vault list
        await db.vault_documents.create_index([("agent_id", 1)])
        logger.info("Compound indexes created/verified")
    except Exception as e:
        logger.warning(f"Compound index creation warning: {e}")

    yield

    # ── Graceful shutdown: close all WebSocket connections ──
    logger.info("Shutting down Evohome CMP...")
    try:
        active = len(ws_manager.active_connections)
        if active > 0:
            logger.info(f"Closing {active} active WebSocket connection(s)...")
            await ws_manager.close_all("Server shutting down")
            logger.info("All WebSocket connections closed")
    except Exception as e:
        logger.warning(f"WebSocket shutdown warning: {e}")


# ==================== APP SETUP ====================

app = FastAPI(title="Evohome CMP API", version=APP_VERSION, lifespan=lifespan)
api_router = APIRouter(prefix="/api")


# ==================== MIDDLEWARE ====================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers and request ID tracking to all responses."""

    async def dispatch(self, request: Request, call_next):
        # Generate or reuse request ID
        request_id = request.headers.get("x-request-id", uuid.uuid4().hex[:16])
        request.state.request_id = request_id

        start = time.time()
        response = await call_next(request)
        elapsed_ms = (time.time() - start) * 1000

        # Request tracking
        response.headers["X-Request-ID"] = request_id

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if app_config.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Log slow requests (>2s)
        if elapsed_ms > 2000:
            logger.warning(f"Slow request: {request.method} {request.url.path} {elapsed_ms:.0f}ms [rid={request_id}]")

        return response


app.add_middleware(SecurityHeadersMiddleware)


# ==================== GLOBAL EXCEPTION HANDLER ====================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions. Sanitizes response, logs full context."""
    request_id = getattr(request.state, 'request_id', uuid.uuid4().hex[:16])

    # Log full detail server-side
    context = ErrorContext(
        request=request,
        endpoint=str(request.url.path),
        extra={"request_id": request_id}
    )
    error_id = capture_exception(exc, context=context, severity="critical")

    logger.error(f"Unhandled exception [rid={request_id}] [eid={error_id}]: {type(exc).__name__}: {exc}")
    logger.error(traceback.format_exc())

    # Sanitized response — no stack trace leakage
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal error occurred. Please try again later.",
            "request_id": request_id,
            "error_id": error_id
        },
        headers={"X-Request-ID": request_id}
    )


# ==================== IMPORT AND REGISTER ROUTERS ====================

from routes.auth import router as auth_router
from routes.projects_v2 import router as projects_router
from routes.clients_v2 import router as clients_router
from routes.documents_v2 import router as documents_router
from routes.notifications_v2 import router as notifications_router
from routes.steps_v2 import router as steps_router
from routes.dashboard import router as dashboard_router
from routes.activities_v2 import router as activities_router
from routes.timelines_v2 import router as timelines_router
from routes.stats import router as stats_router
from routes.vault_v2 import router as vault_router
from routes.analytics import router as analytics_router
from routes.test_endpoints import router as test_endpoints_router
from routes.demo import router as demo_router
from routes.billing import router as billing_router
from routes.invitations import router as invitations_router
from routes.settings import router as settings_router
from routes.admin import router as admin_router
from routes.commands import router as commands_router
from routes.units import router as units_router
from routes.doc_extraction import router as doc_extraction_router
from routes.workflows import router as workflows_router
from routes.team_v2 import router as team_router
from routes.change_requests import router as change_requests_router
from routes.decisions import router as decisions_router

for r in [
    auth_router, projects_router, clients_router, documents_router,
    notifications_router, steps_router,
    dashboard_router, activities_router, timelines_router,
    stats_router, vault_router, analytics_router, test_endpoints_router,
    demo_router, billing_router, invitations_router, settings_router,
    admin_router, commands_router, doc_extraction_router, workflows_router,
    units_router, team_router, change_requests_router, decisions_router,
]:
    api_router.include_router(r)


# ==================== WEBSOCKET ENDPOINT ====================

from services.realtime_service import ws_manager

@api_router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time updates with JWT auth"""
    token = websocket.query_params.get("token")

    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        capture_websocket_error(Exception("No token provided"), user_id=user_id, action="connect")
        return

    try:
        payload = verify_token(token, expected_type='access')
        token_user_id = payload.get('user_id')
        if token_user_id != user_id:
            await websocket.close(code=4003, reason="User ID mismatch")
            capture_websocket_error(
                Exception(f"Token user_id {token_user_id} does not match URL user_id {user_id}"),
                user_id=user_id, action="connect"
            )
            return
    except HTTPException as e:
        await websocket.close(code=4001, reason=str(e.detail))
        capture_websocket_error(e, user_id=user_id, action="connect")
        return
    except Exception as e:
        await websocket.close(code=4001, reason="Invalid token")
        capture_websocket_error(e, user_id=user_id, action="connect")
        return

    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        await websocket.close(code=4004, reason="User not found")
        capture_websocket_error(Exception("User not found"), user_id=user_id, action="connect")
        return

    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id)
    except Exception as e:
        capture_websocket_error(e, user_id=user_id, action="message")
        ws_manager.disconnect(websocket, user_id)


# ==================== HEALTH & READINESS ====================

@api_router.get("/health")
async def health_liveness():
    """Liveness probe — is the process alive and accepting requests?"""
    return {"status": "alive", "version": APP_VERSION}


@api_router.get("/ready")
async def health_readiness():
    """Readiness probe — is the app ready to serve traffic (DB connected)?"""
    checks = {"app": "ok", "version": APP_VERSION, "environment": app_config.ENVIRONMENT}

    # DB connectivity check
    try:
        result = await db.command("ping")
        checks["database"] = "ok" if result.get("ok") == 1.0 else "degraded"
    except Exception as e:
        checks["database"] = "unreachable"
        logger.error(f"Readiness check failed — DB unreachable: {e}")
        return JSONResponse(status_code=503, content={"status": "not_ready", **checks})

    # Feature flags
    checks["features"] = {
        "email": app_config.email_enabled,
        "billing": app_config.billing_enabled,
        "ai_extraction": app_config.ai_enabled,
        "google_oauth": app_config.google_oauth_enabled,
    }

    return {"status": "ready", **checks}


@api_router.get("/")
async def api_root():
    return {"message": "Evohome CMP API", "version": APP_VERSION, "status": "production"}


# ==================== MOUNT ====================

app.include_router(api_router)
app.mount("/api/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# CORS — config-driven, no wildcard fallback
_cors_origins = list(app_config.CORS_ORIGINS)

# Auto-include FRONTEND_URL if set (covers preview/staging deployments)
if app_config.FRONTEND_URL and app_config.FRONTEND_URL not in _cors_origins:
    _cors_origins.append(app_config.FRONTEND_URL)

if app_config.is_production:
    logger.info(f"CORS (production): {_cors_origins}")
else:
    _dev_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
    _cors_origins = list(set(_cors_origins + _dev_origins))
    logger.info(f"CORS (development): {_cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Accept"],
)
