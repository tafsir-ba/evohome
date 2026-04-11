"""Auto-extracted route module from server.py — Phase 3 modularization."""
import os
import re
import json
import uuid
import base64
import logging
import secrets
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Literal, Dict, Any
from io import BytesIO

from fastapi import APIRouter, HTTPException, Depends, Request, Response, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field, EmailStr

from database import db
from core.auth import get_current_user, get_current_agent, get_current_buyer, verify_token
from core.access_control import can_access_project, can_access_client, can_access_vault_doc, can_access_document, get_accessible_project_ids, get_accessible_client_ids, is_agent, is_buyer
from core.rate_limit import rate_limit_check, check_rate_limit
from core.monitoring import capture_exception, capture_auth_failure, capture_payment_error, capture_email_error, capture_ai_error, capture_websocket_error, capture_document_error, ErrorContext
from core.responses import AuthSessionResponse, AuthLoginResponse, AuthRefreshResponse, AuthLogoutResponse, DocumentResponse, VaultDocumentResponse, NotificationResponse, ActivityResponse, ActivitiesListResponse, SuccessResponse

from helpers import get_demo_filter, build_query, secure_filename, VALID_TRANSITIONS, validate_transition, SUBSCRIPTION_PLANS, VAULT_CATEGORIES, VAULT_DOC_TYPES
from services.email_service import send_email_async, send_notification_email, get_email_template
from services.realtime_service import ws_manager, notify_realtime, send_milestone_notification
from services.qr_service import generate_swiss_qr_code, generate_swiss_qr_code_base64, DEFAULT_IBAN, DEFAULT_COMPANY_NAME
from services.ai_service import extract_document_from_pdf, OPENAI_API_KEY

from models.schemas import *

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter()

# ==================== COMMAND SERVICE ====================

# ==================== COMMAND SERVICE ENDPOINTS ====================
# Phase 2: Agent Command Workspace
# All execution creates drafts first, then confirms

from services.command_service import (
    CommandInterpreter,
    CommandExecutor,
    CommandContext,
    CommandPlan,
    CommandDraft,
    CommandIntent,
    TOOL_REGISTRY
)

# Initialize command services
command_interpreter = CommandInterpreter(db)
command_executor = CommandExecutor(db)

# Request models for command endpoints
class CommandInterpretRequest(BaseModel):
    command: str
    context: Optional[dict] = None
    
class CommandExecuteRequest(BaseModel):
    draft_id: str
    confirmed: bool = True


@router.post("/command/interpret")
async def interpret_command(
    command: str = Form(...),
    context: str = Form("{}"),
    user: dict = Depends(get_current_agent)
):
    """
    Interpret a command into a structured plan.
    
    This endpoint:
    - Classifies the intent (create_quote, create_invoice, create_message)
    - Extracts fields from the command text
    - Validates required fields
    - Returns a structured plan for confirmation
    
    NO side effects. NO database writes (except logging).
    """
    try:
        # Parse context
        ctx_dict = json.loads(context) if context else {}
        cmd_context = CommandContext(
            project_id=ctx_dict.get("project_id"),
            client_id=ctx_dict.get("client_id"),
            unit_id=ctx_dict.get("unit_id")
        )
        
        # Interpret the command
        plan = await command_interpreter.interpret(
            command_text=command,
            context=cmd_context,
            user_id=user['user_id']
        )
        
        # Convert to dict for response
        plan_dict = plan.model_dump()
        
        # Convert enum values to strings
        plan_dict['intent'] = plan.intent.value
        plan_dict['fields'] = [
            {**f.model_dump(), 'confidence': f.confidence}
            for f in plan.fields
        ]
        plan_dict['missing_fields'] = [
            f.model_dump() for f in plan.missing_fields
        ]
        
        # Convert datetime to ISO string
        plan_dict['created_at'] = plan.created_at.isoformat()
        
        return plan_dict
        
    except Exception as e:
        logging.error(f"Command interpretation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Interpretation failed: {str(e)}")


@router.post("/command/draft")
async def create_command_draft(
    plan: dict,
    user: dict = Depends(get_current_agent)
):
    """
    Create a draft from a validated plan.
    
    This creates a draft object that can be:
    - Reviewed and edited
    - Confirmed for execution
    - Cancelled
    
    Does NOT create the actual object yet.
    """
    try:
        # Reconstruct the CommandPlan
        from services.command_service import ExtractedField, MissingField
        
        cmd_plan = CommandPlan(
            plan_id=plan.get('plan_id', f"plan_{uuid.uuid4().hex[:12]}"),
            intent=CommandIntent(plan['intent']),
            intent_confidence=plan.get('intent_confidence', 1.0),
            entities=plan.get('entities', {}),
            fields=[
                ExtractedField(**f) for f in plan.get('fields', [])
            ],
            missing_fields=[
                MissingField(**f) for f in plan.get('missing_fields', [])
            ],
            is_valid=plan.get('is_valid', False),
            validation_errors=plan.get('validation_errors', []),
            requires_confirmation=True,
            can_execute=plan.get('can_execute', False),
            raw_command=plan.get('raw_command', '')
        )
        
        # Create draft
        draft = await command_executor.create_draft(cmd_plan, user['user_id'])
        
        # Return draft info
        return {
            "draft_id": draft.draft_id,
            "plan_id": draft.plan_id,
            "intent": draft.intent.value,
            "status": draft.status.value,
            "draft_data": draft.draft_data,
            "created_at": draft.created_at.isoformat()
        }
        
    except Exception as e:
        logging.error(f"Draft creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Draft creation failed: {str(e)}")


@router.post("/command/execute")
async def execute_command(
    request: CommandExecuteRequest,
    user: dict = Depends(get_current_agent)
):
    """
    Execute a confirmed draft.
    
    This:
    - Validates the draft exists and is pending
    - Checks user authorization
    - Creates the actual object through existing services
    - Logs the execution
    - Prevents duplicate execution (idempotent)
    
    If confirmed=false, cancels the draft instead.
    """
    try:
        # Check if draft was already executed (idempotency)
        existing_draft = await db.command_drafts.find_one(
            {"draft_id": request.draft_id},
            {"_id": 0, "status": 1, "result_id": 1, "result_type": 1}
        )
        
        if existing_draft and existing_draft.get("status") == "executed":
            # Already executed - return the existing result
            logger.info(f"Returning cached execution result for draft: {request.draft_id}")
            return {
                "status": "executed",
                "draft_id": request.draft_id,
                "result": {
                    "type": existing_draft.get("result_type"),
                    "id": existing_draft.get("result_id"),
                    "already_executed": True
                }
            }
        
        result = await command_executor.execute_draft(
            draft_id=request.draft_id,
            user_id=user['user_id'],
            confirmed=request.confirmed,
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.error(f"Command execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


@router.get("/command/draft/{draft_id}")
async def get_draft(
    draft_id: str,
    user: dict = Depends(get_current_agent)
):
    """Get a command draft by ID"""
    draft = await db.command_drafts.find_one(
        {"draft_id": draft_id, "created_by": user['user_id']},
        {"_id": 0}
    )
    
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    return draft


@router.get("/command/drafts")
async def list_drafts(
    status: Optional[str] = None,
    user: dict = Depends(get_current_agent)
):
    """List command drafts for the current user"""
    query = {"created_by": user['user_id']}
    if status:
        query["status"] = status
    
    drafts = await db.command_drafts.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(50)
    
    return drafts


@router.get("/command/tools")
async def list_tools(user: dict = Depends(get_current_agent)):
    """
    List available command tools and their definitions.
    Useful for UI hints and validation.
    """
    tools = []
    for intent, tool in TOOL_REGISTRY.items():
        tools.append({
            "intent": intent.value,
            "name": tool.name,
            "description": tool.description,
            "required_fields": tool.required_fields,
            "optional_fields": tool.optional_fields
        })
    return tools


@router.get("/command/logs")
async def get_command_logs(
    draft_id: Optional[str] = None,
    limit: int = 50,
    user: dict = Depends(get_current_agent)
):
    """Get command execution logs"""
    query = {"user_id": user['user_id']}
    if draft_id:
        query["draft_id"] = draft_id
    
    logs = await db.command_logs.find(
        query,
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    
    return logs


@router.get("/command/history")
async def get_command_history(
    limit: int = 20,
    user: dict = Depends(get_current_agent)
):
    """
    Get recent command history for the user.
    Includes both executed drafts and recent extractions.
    """
    
    # Get recent drafts
    drafts = await db.command_drafts.find(
        {"created_by": user['user_id']},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Get recent extraction cache entries
    extractions = await db.extraction_cache.find(
        {"user_id": user['user_id']},
        {"_id": 0, "idempotency_key": 1, "created_at": 1, "result.document_type": 1, "result.intent": 1}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {
        "drafts": drafts,
        "recent_extractions": extractions
    }


@router.post("/command/draft/auto-save")
async def auto_save_draft(
    plan_id: str = Form(...),
    intent: str = Form(...),
    draft_data: str = Form("{}"),
    user: dict = Depends(get_current_agent)
):
    """
    Auto-save a draft in progress.
    Called periodically by the frontend to persist work.
    """
    try:
        data = json.loads(draft_data) if draft_data else {}
        
        # Upsert the auto-save draft
        await db.command_drafts_autosave.update_one(
            {"plan_id": plan_id, "created_by": user['user_id']},
            {"$set": {
                "plan_id": plan_id,
                "intent": intent,
                "draft_data": data,
                "created_by": user['user_id'],
                "updated_at": datetime.now(timezone.utc).isoformat()
            }},
            upsert=True
        )
        
        return {"status": "saved", "plan_id": plan_id}
    except Exception as e:
        logger.error(f"Auto-save failed: {e}")
        raise HTTPException(status_code=500, detail="Auto-save failed")


@router.get("/command/draft/auto-save/{plan_id}")
async def get_auto_saved_draft(
    plan_id: str,
    user: dict = Depends(get_current_agent)
):
    """
    Retrieve an auto-saved draft.
    Used to recover work after browser refresh.
    """
    draft = await db.command_drafts_autosave.find_one(
        {"plan_id": plan_id, "created_by": user['user_id']},
        {"_id": 0}
    )
    
    if not draft:
        raise HTTPException(status_code=404, detail="No auto-saved draft found")
    
    return draft


