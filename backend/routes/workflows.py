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
from core.access_control import can_access_project, can_access_client, can_access_vault_doc, can_access_document, get_accessible_project_ids, get_accessible_client_ids, is_agent, is_buyer, get_is_demo
from core.rate_limit import rate_limit_check, check_rate_limit
from core.monitoring import capture_exception, capture_auth_failure, capture_payment_error, capture_email_error, capture_ai_error, capture_websocket_error, capture_document_error, ErrorContext
from core.responses import AuthSessionResponse, AuthLoginResponse, AuthRefreshResponse, AuthLogoutResponse, DocumentResponse, VaultDocumentResponse, NotificationResponse, ActivityResponse, ActivitiesListResponse, SuccessResponse

from helpers import get_demo_filter, build_query, secure_filename, VALID_TRANSITIONS, validate_transition, SUBSCRIPTION_PLANS, VAULT_CATEGORIES, VAULT_DOC_TYPES
from services.email_service import send_email_async, send_notification_email, create_notification, get_email_template
from services.realtime_service import ws_manager, notify_realtime, send_milestone_notification
from services.qr_service import generate_swiss_qr_code, generate_swiss_qr_code_base64, DEFAULT_IBAN, DEFAULT_COMPANY_NAME
from services.ai_service import extract_document_from_pdf, OPENAI_API_KEY

from models.schemas import *

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter()

# ==================== WORKFLOW ENDPOINTS ====================

# ==================== WORKFLOW ENDPOINTS (Phase 4) ====================

from services.workflow_service import (
    get_workflow_service, 
    WorkflowTemplate, 
    WorkflowExecution,
    WorkflowStatus,
    WorkflowStepStatus
)

class WorkflowExecuteRequest(BaseModel):
    template_id: str
    context: Dict[str, Any] = {}
    mode: str = "automatic"  # "automatic" or "step_by_step"

class WorkflowConfirmRequest(BaseModel):
    skip_step: bool = False

@router.get("/workflows/templates")
async def get_workflow_templates(
    category: Optional[str] = None,
    user: dict = Depends(get_current_agent)
):
    """Get all available workflow templates"""
    service = get_workflow_service(db)
    templates = service.get_templates(category)
    
    return {
        "templates": [
            {
                "template_id": t.template_id,
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "icon": t.icon,
                "estimated_duration": t.estimated_duration,
                "required_context": t.required_context,
                "ui_selectors": t.ui_selectors,
                "steps_count": len(t.steps),
                "steps_preview": [
                    {"name": s["name"], "description": s["description"], "optional": s.get("optional", False)}
                    for s in t.steps
                ]
            }
            for t in templates
        ]
    }

@router.get("/workflows/templates/{template_id}")
async def get_workflow_template(
    template_id: str,
    user: dict = Depends(get_current_agent)
):
    """Get details of a specific workflow template"""
    service = get_workflow_service(db)
    template = service.get_template(template_id)
    
    if not template:
        raise HTTPException(status_code=404, detail="Workflow template not found")
    
    return {
        "template_id": template.template_id,
        "name": template.name,
        "description": template.description,
        "category": template.category,
        "icon": template.icon,
        "estimated_duration": template.estimated_duration,
        "required_context": template.required_context,
        "steps": [
            {
                "name": s["name"],
                "description": s["description"],
                "action": s["action"],
                "optional": s.get("optional", False),
                "requires_confirmation": s.get("requires_confirmation", False)
            }
            for s in template.steps
        ]
    }

@router.post("/workflows/execute")
async def execute_workflow(
    request: WorkflowExecuteRequest,
    user: dict = Depends(get_current_agent)
):
    """Start executing a workflow"""
    service = get_workflow_service(db)
    is_demo = user.get('is_demo', False)
    
    # Get agent profile for email sending
    agent_profile = await db.agent_profiles.find_one(
        {"user_id": user['user_id']},
        {"_id": 0}
    )
    agent_name = agent_profile.get('display_name', user.get('name', 'Your Agent')) if agent_profile else 'Your Agent'
    agent_email = agent_profile.get('contact_email', user.get('email')) if agent_profile else user.get('email')
    
    try:
        # Enrich context with document/step details if needed
        enriched_context = dict(request.context)
        
        # If document_id provided, fetch document details
        if enriched_context.get('document_id'):
            doc = await db.documents.find_one(
                {"document_id": enriched_context['document_id']},
                {"_id": 0}
            )
            if doc:
                enriched_context['document_type'] = doc.get('type', 'Document')
                enriched_context['document_title'] = doc.get('title', 'Untitled')
                enriched_context['amount'] = doc.get('total_amount', 0)
                enriched_context['client_id'] = doc.get('client_id')
                enriched_context['project_id'] = doc.get('project_id')
        
        # If client_id provided, fetch client details
        if enriched_context.get('client_id'):
            client = await db.clients.find_one(
                {"client_id": enriched_context['client_id']},
                {"_id": 0}
            )
            if client:
                enriched_context['client_name'] = client.get('name', 'Client')
                enriched_context['client_email'] = client.get('email')
        
        # If project_id provided, fetch project details
        if enriched_context.get('project_id'):
            project = await db.projects.find_one(
                {"project_id": enriched_context['project_id']},
                {"_id": 0}
            )
            if project:
                enriched_context['project_name'] = project.get('name', 'Project')
        
        # If step_id provided, fetch step details
        if enriched_context.get('step_id'):
            step = await db.timeline_steps.find_one(
                {"step_id": enriched_context['step_id']},
                {"_id": 0}
            )
            if step:
                enriched_context['step_name'] = step.get('name', 'Milestone')
                enriched_context['project_id'] = step.get('project_id') or enriched_context.get('project_id')
                # Get client from project
                if enriched_context.get('project_id') and not enriched_context.get('client_id'):
                    project = await db.projects.find_one(
                        {"project_id": enriched_context['project_id']},
                        {"_id": 0}
                    )
                    if project and project.get('client_id'):
                        enriched_context['client_id'] = project['client_id']
                        client = await db.clients.find_one(
                            {"client_id": project['client_id']},
                            {"_id": 0}
                        )
                        if client:
                            enriched_context['client_name'] = client.get('name')
                            enriched_context['client_email'] = client.get('email')
        
        # Create execution with enriched context
        execution = await service.create_execution(
            template_id=request.template_id,
            agent_id=user['user_id'],
            context=enriched_context,
            mode=request.mode,
            is_demo=is_demo
        )
        
        # Track step warnings for non-fatal issues
        step_warnings = {}
        
        # Helper to safely send email with error handling
        async def safe_send_email(to_email: str, subject: str, html_content: str, step_name: str) -> dict:
            """Send email with graceful error handling"""
            if not to_email:
                return {"sent": False, "warning": "No recipient email address"}
            
            if not RESEND_API_KEY:
                logger.warning(f"RESEND_API_KEY not configured, skipping email for {step_name}")
                return {"sent": False, "warning": "Email service not configured"}
            
            try:
                await send_email_async(to_email, subject, html_content)
                return {"sent": True}
            except Exception as e:
                logger.warning(f"Email failed for {step_name}: {e}")
                return {"sent": False, "warning": f"Email delivery failed: {str(e)[:100]}"}
        
        # Define action executor with real email sending
        async def action_executor(action: str, params: Dict, context: Dict) -> Dict:
            """Execute a workflow action and return results"""
            result = {}
            
            if action == "create_client":
                client_data = {
                    "client_id": f"cl_{uuid.uuid4().hex[:8]}",
                    "agent_id": user['user_id'],
                    "project_id": params.get("project_id") or context.get("project_id"),
                    "name": params.get("client_name") or context.get("client_name", "New Client"),
                    "email": params.get("client_email") or context.get("client_email"),
                    "phone": params.get("client_phone") or context.get("client_phone"),
                    "status": "active",
                    "is_demo": is_demo,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                await db.clients.insert_one(client_data)
                result["client_id"] = client_data["client_id"]
                result["client_email"] = client_data["email"]
                result["client_name"] = client_data["name"]
                logger.info(f"Workflow created client: {client_data['client_id']}")
                
            elif action == "send_welcome_email":
                client_email = params.get("client_email") or context.get("client_email")
                client_name = params.get("client_name") or context.get("client_name", "")
                project_name = params.get("project_name") or context.get("project_name", "your project")
                
                subject = f"Welcome to {project_name}!"
                html_content = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #3b82f6;">Welcome, {client_name}!</h2>
                    <p>You've been added to <strong>{project_name}</strong> by {agent_name}.</p>
                    <p>You can now:</p>
                    <ul>
                        <li>View project updates and timeline</li>
                        <li>Review and approve quotes</li>
                        <li>Track invoice payments</li>
                        <li>Access shared documents</li>
                    </ul>
                    <p style="margin-top: 24px;">
                        <a href="{os.environ.get('FRONTEND_URL', 'https://evohome.app')}/login" 
                           style="background-color: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                            Access Your Portal
                        </a>
                    </p>
                    <p style="margin-top: 24px; color: #6b7280; font-size: 14px;">
                        If you have any questions, contact {agent_name} at {agent_email}.
                    </p>
                </div>
                """
                email_result = await safe_send_email(client_email, subject, html_content, "send_welcome_email")
                result["email_sent"] = email_result["sent"]
                if email_result.get("warning"):
                    result["_warning"] = email_result["warning"]
                    step_warnings["send_welcome_email"] = email_result["warning"]
                logger.info(f"Workflow welcome email: sent={email_result['sent']}, to={client_email}")
                
            elif action == "update_document_status":
                doc_id = params.get("document_id") or context.get("document_id")
                new_status = params.get("status", "Sent")
                if doc_id:
                    update_data = {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}
                    if new_status == "Paid":
                        update_data["paid_at"] = datetime.now(timezone.utc).isoformat()
                    elif new_status == "Sent":
                        update_data["sent_at"] = datetime.now(timezone.utc).isoformat()
                    
                    await db.documents.update_one(
                        {"document_id": doc_id},
                        {"$set": update_data}
                    )
                    result["status"] = new_status
                    logger.info(f"Workflow updated document {doc_id} to {new_status}")
                    
            elif action == "send_payment_confirmation_email":
                client_email = params.get("client_email") or context.get("client_email")
                client_name = params.get("client_name") or context.get("client_name", "")
                amount = params.get("amount") or context.get("amount", 0)
                doc_id = params.get("document_id") or context.get("document_id")
                
                subject = "Payment Received - Thank You!"
                html_content = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #10b981;">Payment Received!</h2>
                    <p>Dear {client_name},</p>
                    <p>We have received your payment of <strong>CHF {amount:,.2f}</strong>.</p>
                    <p>Your invoice has been marked as paid. Thank you for your prompt payment!</p>
                    <p style="margin-top: 24px; color: #6b7280; font-size: 14px;">
                        Reference: {doc_id}<br>
                        Processed by: {agent_name}
                    </p>
                </div>
                """
                email_result = await safe_send_email(client_email, subject, html_content, "send_payment_confirmation_email")
                result["email_sent"] = email_result["sent"]
                if email_result.get("warning"):
                    result["_warning"] = email_result["warning"]
                    step_warnings["send_payment_confirmation_email"] = email_result["warning"]
                    
            elif action == "complete_timeline_step":
                step_id = params.get("step_id") or context.get("step_id")
                if step_id:
                    await db.timeline_steps.update_one(
                        {"step_id": step_id},
                        {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}}
                    )
                    result["step_status"] = "completed"
                    logger.info(f"Workflow completed step: {step_id}")
                    
            elif action == "send_milestone_email":
                client_email = params.get("client_email") or context.get("client_email")
                client_name = params.get("client_name") or context.get("client_name", "")
                step_name = params.get("step_name") or context.get("step_name", "a milestone")
                project_name = params.get("project_name") or context.get("project_name", "your project")
                
                subject = f"Milestone Completed: {step_name}"
                html_content = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #f59e0b;">Milestone Completed!</h2>
                    <p>Dear {client_name},</p>
                    <p>Great news! The following milestone has been completed for <strong>{project_name}</strong>:</p>
                    <div style="background-color: #fef3c7; padding: 16px; border-radius: 8px; margin: 16px 0;">
                        <strong>{step_name}</strong>
                    </div>
                    <p>View your project timeline for full details and upcoming milestones.</p>
                    <p style="margin-top: 24px;">
                        <a href="{os.environ.get('FRONTEND_URL', 'https://evohome.app')}/buyer/timeline" 
                           style="background-color: #f59e0b; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                            View Timeline
                        </a>
                    </p>
                    <p style="margin-top: 24px; color: #6b7280; font-size: 14px;">
                        Best regards,<br>{agent_name}
                    </p>
                </div>
                """
                email_result = await safe_send_email(client_email, subject, html_content, "send_milestone_email")
                result["email_sent"] = email_result["sent"]
                if email_result.get("warning"):
                    result["_warning"] = email_result["warning"]
                    step_warnings["send_milestone_email"] = email_result["warning"]
                    
            elif action == "send_document_email":
                client_email = params.get("client_email") or context.get("client_email")
                client_name = params.get("client_name") or context.get("client_name", "")
                doc_type = params.get("document_type") or context.get("document_type", "Document")
                doc_title = params.get("document_title") or context.get("document_title", "")
                doc_id = params.get("document_id") or context.get("document_id")
                
                subject = f"New {doc_type}: {doc_title}"
                html_content = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #3b82f6;">New {doc_type} Available</h2>
                    <p>Dear {client_name},</p>
                    <p>{agent_name} has sent you a new {doc_type.lower()}:</p>
                    <div style="background-color: #eff6ff; padding: 16px; border-radius: 8px; margin: 16px 0;">
                        <strong>{doc_title}</strong>
                    </div>
                    <p>Please review and respond at your earliest convenience.</p>
                    <p style="margin-top: 24px;">
                        <a href="{os.environ.get('FRONTEND_URL', 'https://evohome.app')}/buyer/documents/{doc_id}" 
                           style="background-color: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                            View {doc_type}
                        </a>
                    </p>
                    <p style="margin-top: 24px; color: #6b7280; font-size: 14px;">
                        Best regards,<br>{agent_name}
                    </p>
                </div>
                """
                email_result = await safe_send_email(client_email, subject, html_content, "send_document_email")
                result["email_sent"] = email_result["sent"]
                if email_result.get("warning"):
                    result["_warning"] = email_result["warning"]
                    step_warnings["send_document_email"] = email_result["warning"]
                    
            elif action == "create_announcement":
                activity_data = {
                    "activity_id": f"act_{uuid.uuid4().hex[:8]}",
                    "author_id": user['user_id'],
                    "agent_id": user['user_id'],
                    "project_id": params.get("project_id") or context.get("project_id"),
                    "type": "announcement",
                    "title": params.get("message_title") or context.get("message_title", "Announcement"),
                    "content": params.get("message_content") or context.get("message_content", ""),
                    "is_draft": False,
                    "is_demo": is_demo,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                await db.activities.insert_one(activity_data)
                result["activity_id"] = activity_data["activity_id"]
                
            elif action == "send_project_announcement_email":
                project_id = params.get("project_id") or context.get("project_id")
                message_title = params.get("message_title") or context.get("message_title", "Project Update")
                message_content = params.get("message_content") or context.get("message_content", "")
                
                if project_id:
                    # Get all clients in project
                    clients = await db.clients.find(
                        {"project_id": project_id, "is_demo": is_demo, "email": {"$exists": True, "$ne": None}},
                        {"_id": 0, "email": 1, "name": 1}
                    ).to_list(100)
                    
                    emails_sent = 0
                    email_failures = []
                    
                    if not RESEND_API_KEY:
                        result["emails_sent"] = 0
                        result["total_clients"] = len(clients)
                        result["_warning"] = "Email service not configured"
                        step_warnings["send_project_announcement_email"] = "Email service not configured"
                    else:
                        for client in clients:
                            if client.get('email'):
                                subject = f"Project Update: {message_title}"
                                html_content = f"""
                                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                                    <h2 style="color: #8b5cf6;">{message_title}</h2>
                                    <p>Dear {client.get('name', 'Valued Client')},</p>
                                    <div style="background-color: #f5f3ff; padding: 16px; border-radius: 8px; margin: 16px 0;">
                                        {message_content}
                                    </div>
                                    <p style="margin-top: 24px; color: #6b7280; font-size: 14px;">
                                        Best regards,<br>{agent_name}
                                    </p>
                                </div>
                                """
                                try:
                                    await send_email_async(client['email'], subject, html_content)
                                    emails_sent += 1
                                except Exception as e:
                                    email_failures.append(client['email'])
                                    logger.warning(f"Failed to send announcement to {client['email']}: {e}")
                        
                        result["emails_sent"] = emails_sent
                        result["total_clients"] = len(clients)
                        
                        if email_failures:
                            result["_warning"] = f"Failed to send to {len(email_failures)} recipient(s)"
                            step_warnings["send_project_announcement_email"] = result["_warning"]
                        
                        logger.info(f"Workflow sent announcement to {emails_sent}/{len(clients)} clients")
                else:
                    result["emails_sent"] = 0
                    result["_warning"] = "No project_id provided"
                    step_warnings["send_project_announcement_email"] = "No project_id provided"
                    
            else:
                logger.warning(f"Unknown workflow action: {action}")
            
            return result
        
        # Run the workflow
        execution = await service.run_workflow(execution, action_executor)
        
        # Apply warnings to steps
        for step in execution.steps:
            if step.action in step_warnings:
                step.warning = step_warnings[step.action]
                if step.status == WorkflowStepStatus.COMPLETED:
                    step.status = WorkflowStepStatus.COMPLETED_WITH_WARNING
        
        # Update final status if there are warnings
        has_warnings = any(s.status == WorkflowStepStatus.COMPLETED_WITH_WARNING for s in execution.steps)
        if has_warnings and execution.status == WorkflowStatus.COMPLETED:
            execution.status = WorkflowStatus.COMPLETED_WITH_WARNINGS
        
        await service.update_execution(execution)
        
        # Get summary for response
        summary = service.get_execution_summary(execution)
        
        return {
            "success": execution.status in [WorkflowStatus.COMPLETED, WorkflowStatus.COMPLETED_WITH_WARNINGS],
            "execution": summary
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workflows/executions/{execution_id}")
async def get_workflow_execution(
    execution_id: str,
    user: dict = Depends(get_current_agent)
):
    """Get the status of a workflow execution"""
    service = get_workflow_service(db)
    execution = await service.get_execution(execution_id)
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    if execution.agent_id != user['user_id']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return service.get_execution_summary(execution)

@router.get("/workflows/history")
async def get_workflow_history(
    limit: int = 20,
    user: dict = Depends(get_current_agent)
):
    """Get recent workflow executions for the agent"""
    service = get_workflow_service(db)
    is_demo = user.get('is_demo', False)
    
    executions = await service.get_agent_executions(user['user_id'], is_demo, limit)
    
    return {
        "executions": [service.get_execution_summary(e) for e in executions]
    }

@router.get("/workflows/selectors")
async def get_workflow_selectors(
    selector_type: str,
    project_id: Optional[str] = None,
    user: dict = Depends(get_current_agent)
):
    """Get items for workflow selectors (documents, timeline steps, etc.)"""
    is_demo = user.get('is_demo', False)
    
    if selector_type == "document":
        # Get recent documents (invoices and quotes)
        query = {"agent_id": user['user_id']}
        if project_id:
            query["project_id"] = project_id
        
        docs = await db.documents.find(
            query,
            {"_id": 0, "document_id": 1, "type": 1, "title": 1, "status": 1, "client_id": 1, "total_amount": 1, "created_at": 1}
        ).sort("created_at", -1).limit(50).to_list(50)
        
        # Enrich with client names
        for doc in docs:
            if doc.get('client_id'):
                client = await db.clients.find_one(
                    {"client_id": doc['client_id']},
                    {"_id": 0, "name": 1}
                )
                doc['client_name'] = client.get('name', 'Unknown') if client else 'Unknown'
        
        return {"items": docs}
    
    elif selector_type == "timeline_step":
        # Get timeline steps (ownership enforced via project/timeline chain)
        query = {}
        if project_id:
            # Get timeline for this project (via compat layer)
            timeline = await db.timelines.find_one(
                {"project_id": project_id},
                {"_id": 0, "timeline_id": 1}
            )
            if timeline:
                query = {"timeline_id": timeline['timeline_id']}
            else:
                return {"items": []}
        else:
            # Get steps from agent's projects
            projects = await db.projects.find(
                {"agent_id": user['user_id']},
                {"_id": 0, "project_id": 1}
            ).to_list(100)
            project_ids = [p['project_id'] for p in projects]
            
            # Get timelines for these projects (via compat layer)
            timelines = await db.timelines.find(
                {"project_id": {"$in": project_ids}},
                {"_id": 0, "timeline_id": 1, "project_id": 1}
            ).to_list(100)
            timeline_ids = [t['timeline_id'] for t in timelines]
            timeline_project_map = {t['timeline_id']: t['project_id'] for t in timelines}
            
            if not timeline_ids:
                return {"items": []}
            query = {"timeline_id": {"$in": timeline_ids}}
        
        # Use correct field names: title (not name), order_index (not order)
        steps = await db.timeline_steps.find(
            query,
            {"_id": 0, "step_id": 1, "title": 1, "status": 1, "timeline_id": 1, "planned_date": 1}
        ).sort("order_index", 1).limit(100).to_list(100)
        
        # Enrich with project names
        for step in steps:
            # Map title to name for UI consistency
            step['name'] = step.pop('title', 'Untitled')
            
            # Normalize: use timeline_id
            tl_id = step.get('timeline_id')
            
            if tl_id:
                # Get project_id from timeline (via compat layer)
                timeline = await db.timelines.find_one(
                    {"timeline_id": tl_id},
                    {"_id": 0, "project_id": 1}
                )
                if timeline:
                    project = await db.projects.find_one(
                        {"project_id": timeline['project_id']},
                        {"_id": 0, "name": 1}
                    )
                    step['project_name'] = project.get('name', 'Unknown') if project else 'Unknown'
        
        return {"items": steps}
    
    elif selector_type == "client":
        # Get clients
        query = {"agent_id": user['user_id']}
        if project_id:
            query["project_id"] = project_id
        
        clients = await db.clients.find(
            query,
            {"_id": 0, "client_id": 1, "name": 1, "email": 1, "project_id": 1}
        ).sort("name", 1).limit(100).to_list(100)
        
        return {"items": clients}
    
    else:
        raise HTTPException(status_code=400, detail=f"Unknown selector type: {selector_type}")

@router.post("/workflows/executions/{execution_id}/confirm")
async def confirm_workflow_step(
    execution_id: str,
    request: WorkflowConfirmRequest,
    user: dict = Depends(get_current_agent)
):
    """Confirm and continue a paused workflow step"""
    service = get_workflow_service(db)
    execution = service.get_execution(execution_id)
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    if execution.agent_id != user['user_id']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # This would need the action_executor - simplified for now
    raise HTTPException(status_code=501, detail="Step confirmation not yet implemented")

@router.post("/workflows/executions/{execution_id}/cancel")
async def cancel_workflow(
    execution_id: str,
    user: dict = Depends(get_current_agent)
):
    """Cancel a workflow execution"""
    service = get_workflow_service(db)
    
    try:
        execution = await service.cancel_execution(execution_id, user['user_id'])
        return service.get_execution_summary(execution)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/workflows/executions/{execution_id}/steps/{step_index}/retry")
async def retry_workflow_step(
    execution_id: str,
    step_index: int,
    user: dict = Depends(get_current_agent)
):
    """Retry a failed or warning step in a workflow execution"""
    service = get_workflow_service(db)
    execution = await service.get_execution(execution_id)
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    if execution.agent_id != user['user_id']:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    is_demo = user.get('is_demo', False)
    
    # Get agent settings for email
    agent_settings = await db.agent_settings.find_one(
        {"agent_id": user['user_id']},
        {"_id": 0}
    ) or {}
    
    agent_name = agent_settings.get('profile', {}).get('display_name') or user.get('name', 'Your Agent')
    agent_email = agent_settings.get('profile', {}).get('contact_email') or user.get('email', '')
    
    # Helper to safely send email with error handling
    async def safe_send_email(to_email: str, subject: str, html_content: str, step_name: str) -> dict:
        """Send email with graceful error handling"""
        if not to_email:
            return {"sent": False, "warning": "No recipient email address"}
        
        if not RESEND_API_KEY:
            logger.warning(f"RESEND_API_KEY not configured, skipping email for {step_name}")
            return {"sent": False, "warning": "Email service not configured"}
        
        try:
            await send_email_async(to_email, subject, html_content)
            return {"sent": True}
        except Exception as e:
            logger.warning(f"Email failed for {step_name}: {e}")
            return {"sent": False, "warning": f"Email delivery failed: {str(e)[:100]}"}
    
    # Re-create the action executor with the same context
    async def action_executor(action: str, params: dict, context: dict) -> dict:
        """Execute a workflow action and return results"""
        result = {}
        
        if action == "complete_timeline_step":
            step_id = params.get("step_id") or context.get("step_id")
            if step_id:
                await db.timeline_steps.update_one(
                    {"step_id": step_id},
                    {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}}
                )
                result["step_status"] = "completed"
                logger.info(f"Retry: completed step {step_id}")
                
        elif action == "send_milestone_email":
            client_email = params.get("client_email") or context.get("client_email")
            client_name = params.get("client_name") or context.get("client_name", "")
            step_name = params.get("step_name") or context.get("step_name", "a milestone")
            project_name = params.get("project_name") or context.get("project_name", "your project")
            
            subject = f"Milestone Completed: {step_name}"
            html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #f59e0b;">Milestone Completed!</h2>
                <p>Dear {client_name},</p>
                <p>Great news! The following milestone has been completed for <strong>{project_name}</strong>:</p>
                <div style="background-color: #fef3c7; padding: 16px; border-radius: 8px; margin: 16px 0;">
                    <strong>{step_name}</strong>
                </div>
                <p>Best regards,<br>{agent_name}</p>
            </div>
            """
            email_result = await safe_send_email(client_email, subject, html_content, "send_milestone_email")
            result["email_sent"] = email_result["sent"]
            if email_result.get("warning"):
                result["_warning"] = email_result["warning"]
                
        elif action == "update_document_status":
            doc_id = params.get("document_id") or context.get("document_id")
            new_status = params.get("status", "Sent")
            if doc_id:
                update_data = {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}
                if new_status == "Paid":
                    update_data["paid_at"] = datetime.now(timezone.utc).isoformat()
                await db.documents.update_one(
                    {"document_id": doc_id},
                    {"$set": update_data}
                )
                result["status"] = new_status
                logger.info(f"Retry: updated document {doc_id} to {new_status}")
                
        elif action == "send_payment_confirmation_email":
            client_email = params.get("client_email") or context.get("client_email")
            client_name = params.get("client_name") or context.get("client_name", "")
            amount = params.get("amount") or context.get("amount", 0)
            doc_id = params.get("document_id") or context.get("document_id")
            
            subject = "Payment Received - Thank You!"
            html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #10b981;">Payment Received!</h2>
                <p>Dear {client_name},</p>
                <p>We have received your payment of <strong>CHF {amount:,.2f}</strong>.</p>
                <p>Your invoice has been marked as paid.</p>
            </div>
            """
            email_result = await safe_send_email(client_email, subject, html_content, "send_payment_confirmation_email")
            result["email_sent"] = email_result["sent"]
            if email_result.get("warning"):
                result["_warning"] = email_result["warning"]
        else:
            logger.warning(f"Retry: Unknown action {action}")
        
        return result
    
    try:
        execution = await service.retry_step(execution, step_index, action_executor)
        return {
            "success": True,
            "execution": service.get_execution_summary(execution),
            "retried_step": step_index
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Retry workflow step failed: {e}")
        # Still return the updated execution state
        updated_execution = await service.get_execution(execution_id)
        return {
            "success": False,
            "error": str(e),
            "execution": service.get_execution_summary(updated_execution) if updated_execution else None
        }


async def _extract_document_from_image(file_path: str, doc_type: str) -> dict:
    """Extract invoice/quote data from image using Vision API"""
    if not OPENAI_API_KEY:
        return {"extraction_failed": True, "confidence": "low"}
    
    try:
        import base64
        with open(file_path, "rb") as img_file:
            image_data = base64.b64encode(img_file.read()).decode('utf-8')
        
        file_ext = os.path.splitext(file_path)[1].lower()
        mime_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
        mime_type = mime_types.get(file_ext, "image/jpeg")
        
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        prompt = f"""Analyze this {doc_type} image and extract the following information:
- supplier_name: Company or person issuing the document
- amount: Total amount (number only)
- title: Brief description of what this is for
- description: Detailed description if available
- reference: Document/invoice number
- items: List of line items if visible [{{"description": "...", "quantity": 1, "unit_price": 0, "total": 0}}]

Return ONLY a JSON object with these fields. Use null for missing fields."""
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_data}"}}
                ]
            }],
            max_tokens=1500
        )
        
        result_text = response.choices[0].message.content
        
        # Parse JSON from response
        import re
        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            result = json.loads(json_match.group())
            result["confidence"] = "medium"
            return result
        
        return {"extraction_failed": True, "confidence": "low"}
        
    except Exception as e:
        logger.error(f"Image extraction failed: {e}")
        return {"extraction_failed": True, "confidence": "low", "error": str(e)}


async def _extract_timeline_stages(file_path: str) -> dict:
    """Extract timeline/schedule data from document using AI"""
    if not OPENAI_API_KEY:
        return {"stages": [], "confidence": 0.1, "extraction_failed": True}
    
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        # Extract text from PDF or image
        text_content = ""
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == '.pdf':
            doc = fitz.open(file_path)
            for page in doc:
                text_content += page.get_text()
            doc.close()
        elif file_ext in ['.jpg', '.jpeg', '.png', '.webp']:
            # Use Vision API for images
            import base64
            with open(file_path, "rb") as img_file:
                image_data = base64.b64encode(img_file.read()).decode('utf-8')
            
            mime_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
            mime_type = mime_types.get(file_ext, "image/jpeg")
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract all text from this document, especially any timeline, schedule, or phase information."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_data}"}}
                    ]
                }],
                max_tokens=2000
            )
            text_content = response.choices[0].message.content
        
        if not text_content:
            return {"stages": [], "confidence": 0.1, "extraction_failed": True}
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """You extract project timeline/schedule information from documents.
                    
IMPORTANT: Keep all dates as RAW TEXT. Do not convert or normalize them.
Examples of valid date formats: "Q4 2027", "Spring 2026", "Week 12-15", "March 2025", "6 months"

Return ONLY a JSON object:
{
  "stages": [
    {"name": "Phase name", "date_text": "Raw date as written", "description": "Brief description"}
  ],
  "project_duration": "Total duration as text",
  "confidence": 0.0-1.0
}"""
                },
                {
                    "role": "user",
                    "content": f"Extract timeline stages from this document:\n\n{text_content[:8000]}"
                }
            ],
            max_tokens=2000
        )
        
        response_text = response.choices[0].message.content
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            return json.loads(json_match.group())
        
        return {"stages": [], "confidence": 0.3}
        
    except Exception as e:
        logger.error(f"Timeline extraction failed: {e}")
        return {"stages": [], "confidence": 0.1, "extraction_failed": True}


async def _extract_contacts_list(file_path: str) -> dict:
    """Extract contact information from document using AI"""
    if not OPENAI_API_KEY:
        return {"contacts": [], "confidence": 0.1, "extraction_failed": True}
    
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        # Extract text from PDF
        text_content = ""
        if file_path.lower().endswith('.pdf'):
            doc = fitz.open(file_path)
            for page in doc:
                text_content += page.get_text()
            doc.close()
        
        if not text_content:
            return {"contacts": [], "confidence": 0.1, "extraction_failed": True}
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """You extract contact information from documents.
                    
Extract names, roles, companies, emails, and phone numbers.
Remove duplicates. Only include contacts with at least a name.

Return ONLY a JSON object:
{
  "contacts": [
    {"name": "Full Name", "role": "Job title or role", "company": "Company name", "email": "email@example.com", "phone": "+41 XX XXX XX XX"}
  ],
  "confidence": 0.0-1.0
}"""
                },
                {
                    "role": "user",
                    "content": f"Extract contacts from this document:\n\n{text_content[:8000]}"
                }
            ],
            max_tokens=2000
        )
        
        response_text = response.choices[0].message.content
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            result = json.loads(json_match.group())
            # Deduplicate by name
            seen_names = set()
            unique_contacts = []
            for contact in result.get("contacts", []):
                name = contact.get("name", "").strip().lower()
                if name and name not in seen_names:
                    seen_names.add(name)
                    unique_contacts.append(contact)
            result["contacts"] = unique_contacts
            return result
        
        return {"contacts": [], "confidence": 0.3}
        
    except Exception as e:
        logger.error(f"Contact extraction failed: {e}")
        return {"contacts": [], "confidence": 0.1, "extraction_failed": True}


