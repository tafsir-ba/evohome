"""
Evohome CMP — FastAPI Application Entry Point
Slim orchestrator that wires up modular routers.
Phase 3 modularization: all domain logic lives in /routes/*.py
"""
import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.config import validate_config
from core.auth import init_auth, verify_token
from core.access_control import init_access_control
from core.monitoring import capture_websocket_error
from database import db

# Initialize config
app_config = validate_config()

# Initialize auth and access control modules with database
init_auth(db)
init_access_control(db)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Upload directory
UPLOAD_DIR = Path("/app/backend/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# ==================== LIFESPAN ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events"""
    logger.info("Starting Evohome CMP...")
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
        await db.vault_documents.create_index("vault_id", unique=True)
        logger.info("Database indexes created/verified")
    except Exception as e:
        logger.warning(f"Index creation warning (may already exist): {e}")
    yield
    logger.info("Shutting down Evohome CMP...")

# ==================== APP SETUP ====================

app = FastAPI(title="UpgradeFlow API", lifespan=lifespan)
api_router = APIRouter(prefix="/api")

# ==================== IMPORT AND REGISTER ROUTERS ====================

from routes.auth import router as auth_router
from routes.projects import router as projects_router
from routes.clients import router as clients_router
from routes.documents import router as documents_router
from routes.timeline_view import router as timeline_view_router
from routes.notifications import router as notifications_router
from routes.steps import router as steps_router
from routes.dashboard import router as dashboard_router
from routes.activities import router as activities_router
from routes.timelines import router as timelines_router
from routes.stats import router as stats_router
from routes.vault import router as vault_router
from routes.analytics import router as analytics_router
from routes.test_endpoints import router as test_endpoints_router
from routes.demo import router as demo_router
from routes.billing import router as billing_router
from routes.invitations import router as invitations_router
from routes.settings import router as settings_router
from routes.admin import router as admin_router
from routes.commands import router as commands_router
from routes.doc_extraction import router as doc_extraction_router
from routes.workflows import router as workflows_router

# Register all domain routers on the api_router
for r in [
    auth_router, projects_router, clients_router, documents_router,
    timeline_view_router, notifications_router, steps_router,
    dashboard_router, activities_router, timelines_router,
    stats_router, vault_router, analytics_router, test_endpoints_router,
    demo_router, billing_router, invitations_router, settings_router,
    admin_router, commands_router, doc_extraction_router, workflows_router,
]:
    api_router.include_router(r)

# ==================== WEBSOCKET ENDPOINT ====================
# Kept in server.py since it needs direct app-level access

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

# ==================== ROOT ENDPOINTS ====================

@api_router.get("/")
async def api_root():
    return {"message": "Evohome CMP API", "version": "3.0", "status": "modular"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy"}

# ==================== MOUNT ====================

app.include_router(api_router)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
