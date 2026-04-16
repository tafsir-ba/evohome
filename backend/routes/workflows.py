"""
Workflow Routes — Orchestration layer.

Workflows orchestrate multi-step business processes by composing canonical services.
No direct DB writes. All mutations flow through:
  - client_service   (create_client)
  - document_service  (transition_document_status)
  - step_service      (update_step)
  - activity_service  (create_and_distribute_activity)
"""
import os
import re
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

import openai
import fitz
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from database import db
from core.auth import get_current_agent
from services.email_service import send_email_async, RESEND_API_KEY
from services.ai_service import OPENAI_API_KEY
from services.workflow_service import (
    get_workflow_service,
    WorkflowStatus,
    WorkflowStepStatus,
)
from services import client_service, step_service
from services.document_service import transition_document_status

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

router = APIRouter()


# ── Request Models ──

class WorkflowExecuteRequest(BaseModel):
    template_id: str
    context: Dict[str, Any] = {}
    mode: str = "automatic"

class WorkflowConfirmRequest(BaseModel):
    skip_step: bool = False


# ── Template Endpoints ──

@router.get("/workflows/templates")
async def get_workflow_templates(
    category: Optional[str] = None,
    user: dict = Depends(get_current_agent),
):
    """Get all available workflow templates."""
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
                ],
            }
            for t in templates
        ],
    }


@router.get("/workflows/templates/{template_id}")
async def get_workflow_template(template_id: str, user: dict = Depends(get_current_agent)):
    """Get details of a specific workflow template."""
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
                "requires_confirmation": s.get("requires_confirmation", False),
            }
            for s in template.steps
        ],
    }


# ── Execution Endpoint ──

@router.post("/workflows/execute")
async def execute_workflow(request: WorkflowExecuteRequest, user: dict = Depends(get_current_agent)):
    """Start executing a workflow. All mutations delegated to canonical services."""
    service = get_workflow_service(db)
    agent_id = user['user_id']

    # Resolve agent display name + email for outbound emails
    agent_name, agent_email = await _resolve_agent_identity(user)

    try:
        # Enrich context with entity details from DB (read-only lookups)
        enriched_context = await _enrich_context(dict(request.context))

        execution = await service.create_execution(
            template_id=request.template_id,
            agent_id=agent_id,
            context=enriched_context,
            mode=request.mode,
        )

        step_warnings: Dict[str, str] = {}

        # Build the action executor that delegates to canonical services
        action_executor = _build_action_executor(agent_id, agent_name, agent_email, step_warnings, user)

        execution = await service.run_workflow(execution, action_executor)

        # Apply warnings to steps
        _apply_step_warnings(execution, step_warnings)
        await service.update_execution(execution)

        return {
            "success": execution.status in [WorkflowStatus.COMPLETED, WorkflowStatus.COMPLETED_WITH_WARNINGS],
            "execution": service.get_execution_summary(execution),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Execution Management ──

@router.get("/workflows/executions/{execution_id}")
async def get_workflow_execution(execution_id: str, user: dict = Depends(get_current_agent)):
    """Get the status of a workflow execution."""
    service = get_workflow_service(db)
    execution = await service.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    if execution.agent_id != user['user_id']:
        raise HTTPException(status_code=403, detail="Not authorized")
    return service.get_execution_summary(execution)


@router.get("/workflows/history")
async def get_workflow_history(
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_agent),
):
    """Get recent workflow executions for the agent."""
    service = get_workflow_service(db)
    executions = await service.get_agent_executions(user['user_id'], limit)
    return {"executions": [service.get_execution_summary(e) for e in executions]}


@router.post("/workflows/executions/{execution_id}/cancel")
async def cancel_workflow(execution_id: str, user: dict = Depends(get_current_agent)):
    """Cancel a workflow execution."""
    service = get_workflow_service(db)
    try:
        execution = await service.cancel_execution(execution_id, user['user_id'])
        return service.get_execution_summary(execution)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/workflows/executions/{execution_id}/confirm")
async def confirm_workflow_step(
    execution_id: str,
    request: WorkflowConfirmRequest,
    user: dict = Depends(get_current_agent),
):
    """Confirm and continue a paused workflow step."""
    raise HTTPException(status_code=501, detail="Step confirmation not yet implemented")


@router.post("/workflows/executions/{execution_id}/steps/{step_index}/retry")
async def retry_workflow_step(
    execution_id: str, step_index: int, user: dict = Depends(get_current_agent),
):
    """Retry a failed or warning step in a workflow execution."""
    service = get_workflow_service(db)
    execution = await service.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    if execution.agent_id != user['user_id']:
        raise HTTPException(status_code=403, detail="Not authorized")

    agent_name, agent_email = await _resolve_agent_identity(user)
    step_warnings: Dict[str, str] = {}
    action_executor = _build_action_executor(user['user_id'], agent_name, agent_email, step_warnings, user)

    try:
        execution = await service.retry_step(execution, step_index, action_executor)
        return {
            "success": True,
            "execution": service.get_execution_summary(execution),
            "retried_step": step_index,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Retry workflow step failed: {e}")
        updated = await service.get_execution(execution_id)
        return {
            "success": False,
            "error": str(e),
            "execution": service.get_execution_summary(updated) if updated else None,
        }


# ── Selectors ──

@router.get("/workflows/selectors")
async def get_workflow_selectors(
    selector_type: str,
    project_id: Optional[str] = None,
    user: dict = Depends(get_current_agent),
):
    """Get items for workflow selectors (documents, timeline steps, clients)."""
    agent_id = user['user_id']

    if selector_type == "document":
        return await _select_documents(agent_id, project_id)
    elif selector_type == "timeline_step":
        return await _select_timeline_steps(agent_id, project_id)
    elif selector_type == "client":
        return await _select_clients(agent_id, project_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown selector type: {selector_type}")


# ── Internal: Action Executor Factory ──

def _build_action_executor(
    agent_id: str,
    agent_name: str,
    agent_email: str,
    step_warnings: Dict[str, str],
    agent_user: dict,
):
    """Build the action executor closure that delegates all mutations to canonical services."""

    async def action_executor(action: str, params: Dict, context: Dict) -> Dict:
        result: Dict[str, Any] = {}

        if action == "create_client":
            client = await client_service.create_client(
                agent_id=agent_id,
                name=params.get("client_name") or context.get("client_name", "New Client"),
                email=params.get("client_email") or context.get("client_email"),
                phone=params.get("client_phone") or context.get("client_phone"),
                project_id=params.get("project_id") or context.get("project_id"),
            )
            result["client_id"] = client["client_id"]
            result["client_email"] = client.get("email")
            result["client_name"] = client["name"]

        elif action == "update_document_status":
            doc_id = params.get("document_id") or context.get("document_id")
            new_status = params.get("status", "Sent")
            if doc_id:
                updated = await transition_document_status(doc_id, agent_id, new_status)
                result["status"] = new_status
                if not updated:
                    result["_warning"] = "Document not found"

        elif action == "complete_timeline_step":
            step_id = params.get("step_id") or context.get("step_id")
            if step_id:
                await step_service.update_step(step_id, {"status": "completed"})
                result["step_status"] = "completed"

        elif action == "create_announcement":
            project_id = params.get("project_id") or context.get("project_id")
            title = params.get("message_title") or context.get("message_title", "Announcement")
            content = params.get("message_content") or context.get("message_content", "")

            if project_id:
                # Get all clients in the project for distribution
                clients = await db.clients.find(
                    {"project_id": project_id, "agent_id": agent_id},
                    {"_id": 0, "client_id": 1},
                ).to_list(100)
                client_ids = [c["client_id"] for c in clients]

                from services.activity_service import create_and_distribute_activity
                activity = await create_and_distribute_activity(
                    author_id=agent_id,
                    activity_type="announcement",
                    project_id=project_id,
                    recipient_client_ids=client_ids,
                    title=title,
                    content=content,
                    file_url=None,
                    file_name=None,
                    file_size=None,
                    unit_id=None,
                    agent_user=agent_user,
                )
                result["activity_id"] = activity.get("activity_id")

        # ── Email actions (orchestration, not DB mutation) ──

        elif action == "send_welcome_email":
            email_result = await _send_workflow_email(
                to=params.get("client_email") or context.get("client_email"),
                subject=f"Welcome to {context.get('project_name', 'your project')}!",
                html=_welcome_email_html(
                    client_name=params.get("client_name") or context.get("client_name", ""),
                    project_name=params.get("project_name") or context.get("project_name", "your project"),
                    agent_name=agent_name,
                    agent_email=agent_email,
                ),
                step_name="send_welcome_email",
                step_warnings=step_warnings,
            )
            result["email_sent"] = email_result["sent"]
            if email_result.get("warning"):
                result["_warning"] = email_result["warning"]

        elif action == "send_payment_confirmation_email":
            amount = params.get("amount") or context.get("amount", 0)
            email_result = await _send_workflow_email(
                to=params.get("client_email") or context.get("client_email"),
                subject="Payment Received - Thank You!",
                html=_payment_email_html(
                    client_name=params.get("client_name") or context.get("client_name", ""),
                    amount=amount,
                    doc_id=params.get("document_id") or context.get("document_id", ""),
                    agent_name=agent_name,
                ),
                step_name="send_payment_confirmation_email",
                step_warnings=step_warnings,
            )
            result["email_sent"] = email_result["sent"]
            if email_result.get("warning"):
                result["_warning"] = email_result["warning"]

        elif action == "send_milestone_email":
            email_result = await _send_workflow_email(
                to=params.get("client_email") or context.get("client_email"),
                subject=f"Milestone Completed: {params.get('step_name') or context.get('step_name', 'a milestone')}",
                html=_milestone_email_html(
                    client_name=params.get("client_name") or context.get("client_name", ""),
                    step_name=params.get("step_name") or context.get("step_name", "a milestone"),
                    project_name=params.get("project_name") or context.get("project_name", "your project"),
                    agent_name=agent_name,
                ),
                step_name="send_milestone_email",
                step_warnings=step_warnings,
            )
            result["email_sent"] = email_result["sent"]
            if email_result.get("warning"):
                result["_warning"] = email_result["warning"]

        elif action == "send_document_email":
            doc_type = params.get("document_type") or context.get("document_type", "Document")
            doc_title = params.get("document_title") or context.get("document_title", "")
            doc_id = params.get("document_id") or context.get("document_id", "")
            email_result = await _send_workflow_email(
                to=params.get("client_email") or context.get("client_email"),
                subject=f"New {doc_type}: {doc_title}",
                html=_document_email_html(
                    client_name=params.get("client_name") or context.get("client_name", ""),
                    doc_type=doc_type,
                    doc_title=doc_title,
                    doc_id=doc_id,
                    agent_name=agent_name,
                ),
                step_name="send_document_email",
                step_warnings=step_warnings,
            )
            result["email_sent"] = email_result["sent"]
            if email_result.get("warning"):
                result["_warning"] = email_result["warning"]

        elif action == "send_project_announcement_email":
            project_id = params.get("project_id") or context.get("project_id")
            message_title = params.get("message_title") or context.get("message_title", "Project Update")
            message_content = params.get("message_content") or context.get("message_content", "")

            if not project_id:
                result["emails_sent"] = 0
                result["_warning"] = "No project_id provided"
                step_warnings["send_project_announcement_email"] = "No project_id provided"
            elif not RESEND_API_KEY:
                clients = await db.clients.find(
                    {"project_id": project_id, "email": {"$exists": True, "$ne": None}},
                    {"_id": 0},
                ).to_list(100)
                result["emails_sent"] = 0
                result["total_clients"] = len(clients)
                result["_warning"] = "Email service not configured"
                step_warnings["send_project_announcement_email"] = "Email service not configured"
            else:
                clients = await db.clients.find(
                    {"project_id": project_id, "email": {"$exists": True, "$ne": None}},
                    {"_id": 0, "email": 1, "name": 1},
                ).to_list(100)
                sent, failures = 0, []
                for c in clients:
                    if c.get("email"):
                        try:
                            email_result = await send_email_async(
                                c["email"],
                                f"Project Update: {message_title}",
                                _announcement_email_html(
                                    client_name=c.get("name", "Valued Client"),
                                    message_title=message_title,
                                    message_content=message_content,
                                    agent_name=agent_name,
                                ),
                            )
                            if isinstance(email_result, dict) and email_result.get("status") == "success":
                                sent += 1
                            else:
                                failures.append(c["email"])
                        except Exception as e:
                            failures.append(c["email"])
                            logger.warning(f"Failed announcement to {c['email']}: {e}")
                result["emails_sent"] = sent
                result["total_clients"] = len(clients)
                if failures:
                    result["_warning"] = f"Failed to send to {len(failures)} recipient(s)"
                    step_warnings["send_project_announcement_email"] = result["_warning"]
        else:
            logger.warning(f"Unknown workflow action: {action}")

        return result

    return action_executor


# ── Internal: Context Enrichment (read-only DB lookups) ──

async def _enrich_context(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich workflow context with entity details from DB. Read-only."""
    if ctx.get("document_id"):
        doc = await db.documents.find_one({"document_id": ctx["document_id"]}, {"_id": 0})
        if doc:
            ctx.setdefault("document_type", doc.get("type", "Document"))
            ctx.setdefault("document_title", doc.get("title", "Untitled"))
            ctx.setdefault("amount", doc.get("amount", 0))
            ctx.setdefault("client_id", doc.get("client_id"))
            ctx.setdefault("project_id", doc.get("project_id"))

    if ctx.get("client_id"):
        client = await db.clients.find_one({"client_id": ctx["client_id"]}, {"_id": 0})
        if client:
            ctx.setdefault("client_name", client.get("name", "Client"))
            ctx.setdefault("client_email", client.get("email"))

    if ctx.get("project_id"):
        project = await db.projects.find_one({"project_id": ctx["project_id"]}, {"_id": 0})
        if project:
            ctx.setdefault("project_name", project.get("name", "Project"))

    if ctx.get("step_id"):
        step = await db.timeline_steps.find_one({"step_id": ctx["step_id"]}, {"_id": 0})
        if step:
            ctx.setdefault("step_name", step.get("title", "Milestone"))
            ctx.setdefault("project_id", step.get("project_id"))
            if ctx.get("project_id") and not ctx.get("client_id"):
                project = await db.projects.find_one({"project_id": ctx["project_id"]}, {"_id": 0})
                if project and project.get("client_id"):
                    ctx["client_id"] = project["client_id"]
                    client = await db.clients.find_one({"client_id": project["client_id"]}, {"_id": 0})
                    if client:
                        ctx.setdefault("client_name", client.get("name"))
                        ctx.setdefault("client_email", client.get("email"))

    return ctx


async def _resolve_agent_identity(user: dict) -> tuple:
    """Resolve agent display name and email."""
    profile = await db.agent_profiles.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if profile:
        name = profile.get("display_name", user.get("name", "Your Agent"))
        email = profile.get("contact_email", user.get("email"))
    else:
        name = user.get("name", "Your Agent")
        email = user.get("email", "")
    return name, email


def _apply_step_warnings(execution, step_warnings: Dict[str, str]):
    """Apply accumulated warnings to execution steps."""
    for step in execution.steps:
        if step.action in step_warnings:
            step.warning = step_warnings[step.action]
            if step.status == WorkflowStepStatus.COMPLETED:
                step.status = WorkflowStepStatus.COMPLETED_WITH_WARNING
    if any(s.status == WorkflowStepStatus.COMPLETED_WITH_WARNING for s in execution.steps):
        if execution.status == WorkflowStatus.COMPLETED:
            execution.status = WorkflowStatus.COMPLETED_WITH_WARNINGS


# ── Internal: Email Helpers ──

async def _send_workflow_email(
    to: Optional[str], subject: str, html: str, step_name: str, step_warnings: Dict[str, str],
) -> Dict[str, Any]:
    """Send email with graceful error handling."""
    if not to:
        return {"sent": False, "warning": "No recipient email address"}
    if not RESEND_API_KEY:
        step_warnings[step_name] = "Email service not configured"
        return {"sent": False, "warning": "Email service not configured"}
    try:
        result = await send_email_async(to, subject, html)
        if isinstance(result, dict) and result.get("status") == "success":
            return {"sent": True}
        warning = "Email delivery skipped or failed"
        if isinstance(result, dict) and result.get("reason"):
            warning = f"Email delivery skipped: {result.get('reason')}"
        elif isinstance(result, dict) and result.get("error"):
            warning = f"Email delivery failed: {str(result.get('error'))[:100]}"
        step_warnings[step_name] = warning
        return {"sent": False, "warning": warning}
    except Exception as e:
        warning = f"Email delivery failed: {str(e)[:100]}"
        step_warnings[step_name] = warning
        return {"sent": False, "warning": warning}


def _frontend_url() -> str:
    return os.environ.get("FRONTEND_URL", "https://evohome.app")


def _welcome_email_html(client_name: str, project_name: str, agent_name: str, agent_email: str) -> str:
    return f"""
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
            <a href="{_frontend_url()}/login" style="background-color: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                Access Your Portal
            </a>
        </p>
        <p style="margin-top: 24px; color: #6b7280; font-size: 14px;">
            If you have any questions, contact {agent_name} at {agent_email}.
        </p>
    </div>"""


def _payment_email_html(client_name: str, amount: float, doc_id: str, agent_name: str) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #10b981;">Payment Received!</h2>
        <p>Dear {client_name},</p>
        <p>We have received your payment of <strong>CHF {amount:,.2f}</strong>.</p>
        <p>Your invoice has been marked as paid. Thank you for your prompt payment!</p>
        <p style="margin-top: 24px; color: #6b7280; font-size: 14px;">
            Reference: {doc_id}<br>Processed by: {agent_name}
        </p>
    </div>"""


def _milestone_email_html(client_name: str, step_name: str, project_name: str, agent_name: str) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #f59e0b;">Milestone Completed!</h2>
        <p>Dear {client_name},</p>
        <p>Great news! The following milestone has been completed for <strong>{project_name}</strong>:</p>
        <div style="background-color: #fef3c7; padding: 16px; border-radius: 8px; margin: 16px 0;">
            <strong>{step_name}</strong>
        </div>
        <p>View your project timeline for full details and upcoming milestones.</p>
        <p style="margin-top: 24px;">
            <a href="{_frontend_url()}/buyer/timeline" style="background-color: #f59e0b; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                View Timeline
            </a>
        </p>
        <p style="margin-top: 24px; color: #6b7280; font-size: 14px;">Best regards,<br>{agent_name}</p>
    </div>"""


def _document_email_html(client_name: str, doc_type: str, doc_title: str, doc_id: str, agent_name: str) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #3b82f6;">New {doc_type} Available</h2>
        <p>Dear {client_name},</p>
        <p>{agent_name} has sent you a new {doc_type.lower()}:</p>
        <div style="background-color: #eff6ff; padding: 16px; border-radius: 8px; margin: 16px 0;">
            <strong>{doc_title}</strong>
        </div>
        <p>Please review and respond at your earliest convenience.</p>
        <p style="margin-top: 24px;">
            <a href="{_frontend_url()}/buyer/documents/{doc_id}" style="background-color: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
                View {doc_type}
            </a>
        </p>
        <p style="margin-top: 24px; color: #6b7280; font-size: 14px;">Best regards,<br>{agent_name}</p>
    </div>"""


def _announcement_email_html(client_name: str, message_title: str, message_content: str, agent_name: str) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #8b5cf6;">{message_title}</h2>
        <p>Dear {client_name},</p>
        <div style="background-color: #f5f3ff; padding: 16px; border-radius: 8px; margin: 16px 0;">
            {message_content}
        </div>
        <p style="margin-top: 24px; color: #6b7280; font-size: 14px;">Best regards,<br>{agent_name}</p>
    </div>"""


# ── Internal: Selector Queries (read-only) ──

async def _select_documents(agent_id: str, project_id: Optional[str]) -> Dict:
    query: Dict[str, Any] = {"agent_id": agent_id}
    if project_id:
        query["project_id"] = project_id
    docs = await db.documents.find(
        query,
        {"_id": 0, "document_id": 1, "type": 1, "title": 1, "status": 1, "client_id": 1, "amount": 1, "created_at": 1},
    ).sort("created_at", -1).limit(50).to_list(50)
    for doc in docs:
        if doc.get("client_id"):
            client = await db.clients.find_one({"client_id": doc["client_id"]}, {"_id": 0, "name": 1})
            doc["client_name"] = client.get("name", "Unknown") if client else "Unknown"
    return {"items": docs}


async def _select_timeline_steps(agent_id: str, project_id: Optional[str]) -> Dict:
    if project_id:
        timeline = await db.timelines.find_one({"project_id": project_id}, {"_id": 0, "timeline_id": 1})
        if not timeline:
            return {"items": []}
        query = {"timeline_id": timeline["timeline_id"]}
    else:
        projects = await db.projects.find({"agent_id": agent_id}, {"_id": 0, "project_id": 1}).to_list(100)
        project_ids = [p["project_id"] for p in projects]
        timelines = await db.timelines.find(
            {"project_id": {"$in": project_ids}}, {"_id": 0, "timeline_id": 1},
        ).to_list(100)
        timeline_ids = [t["timeline_id"] for t in timelines]
        if not timeline_ids:
            return {"items": []}
        query = {"timeline_id": {"$in": timeline_ids}}

    steps = await db.timeline_steps.find(
        query,
        {"_id": 0, "step_id": 1, "title": 1, "status": 1, "timeline_id": 1, "planned_date": 1},
    ).sort("order_index", 1).limit(100).to_list(100)

    for step in steps:
        step["name"] = step.pop("title", "Untitled")
        tl_id = step.get("timeline_id")
        if tl_id:
            tl = await db.timelines.find_one({"timeline_id": tl_id}, {"_id": 0, "project_id": 1})
            if tl:
                proj = await db.projects.find_one({"project_id": tl["project_id"]}, {"_id": 0, "name": 1})
                step["project_name"] = proj.get("name", "Unknown") if proj else "Unknown"
    return {"items": steps}


async def _select_clients(agent_id: str, project_id: Optional[str]) -> Dict:
    query: Dict[str, Any] = {"agent_id": agent_id}
    if project_id:
        query["project_id"] = project_id
    clients = await db.clients.find(
        query, {"_id": 0, "client_id": 1, "name": 1, "email": 1, "project_id": 1},
    ).sort("name", 1).limit(100).to_list(100)
    return {"items": clients}


# ── AI Extraction Utilities (read-only, no DB writes) ──

async def _extract_document_from_image(file_path: str, doc_type: str) -> dict:
    """Extract invoice/quote data from image using Vision API."""
    if not OPENAI_API_KEY:
        return {"extraction_failed": True, "confidence": "low"}
    try:
        import base64
        with open(file_path, "rb") as img_file:
            image_data = base64.b64encode(img_file.read()).decode("utf-8")
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
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_data}"}},
            ]}],
            max_tokens=1500,
        )
        result_text = response.choices[0].message.content
        json_match = re.search(r"\{[\s\S]*\}", result_text)
        if json_match:
            result = json.loads(json_match.group())
            result["confidence"] = "medium"
            return result
        return {"extraction_failed": True, "confidence": "low"}
    except Exception as e:
        logger.error(f"Image extraction failed: {e}")
        return {"extraction_failed": True, "confidence": "low", "error": str(e)}


async def _extract_timeline_stages(file_path: str) -> dict:
    """Extract timeline/schedule data from document using AI."""
    if not OPENAI_API_KEY:
        return {"stages": [], "confidence": 0.1, "extraction_failed": True}
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        text_content = ""
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext == ".pdf":
            doc = fitz.open(file_path)
            for page in doc:
                text_content += page.get_text()
            doc.close()
        elif file_ext in [".jpg", ".jpeg", ".png", ".webp"]:
            import base64
            with open(file_path, "rb") as img_file:
                image_data = base64.b64encode(img_file.read()).decode("utf-8")
            mime_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
            mime_type = mime_types.get(file_ext, "image/jpeg")
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": "Extract all text from this document, especially any timeline, schedule, or phase information."},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_data}"}},
                ]}],
                max_tokens=2000,
            )
            text_content = response.choices[0].message.content
        if not text_content:
            return {"stages": [], "confidence": 0.1, "extraction_failed": True}
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": """You extract project timeline/schedule information from documents.

IMPORTANT: Keep all dates as RAW TEXT. Do not convert or normalize them.
Examples of valid date formats: "Q4 2027", "Spring 2026", "Week 12-15", "March 2025", "6 months"

Return ONLY a JSON object:
{"stages": [{"name": "Phase name", "date_text": "Raw date as written", "description": "Brief description"}], "project_duration": "Total duration as text", "confidence": 0.0-1.0}"""},
                {"role": "user", "content": f"Extract timeline stages from this document:\n\n{text_content[:8000]}"},
            ],
            max_tokens=2000,
        )
        response_text = response.choices[0].message.content
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if json_match:
            return json.loads(json_match.group())
        return {"stages": [], "confidence": 0.3}
    except Exception as e:
        logger.error(f"Timeline extraction failed: {e}")
        return {"stages": [], "confidence": 0.1, "extraction_failed": True}


async def _extract_contacts_list(file_path: str) -> dict:
    """Extract contact information from document using AI."""
    if not OPENAI_API_KEY:
        return {"contacts": [], "confidence": 0.1, "extraction_failed": True}
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        text_content = ""
        if file_path.lower().endswith(".pdf"):
            doc = fitz.open(file_path)
            for page in doc:
                text_content += page.get_text()
            doc.close()
        if not text_content:
            return {"contacts": [], "confidence": 0.1, "extraction_failed": True}
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": """You extract contact information from documents.

Extract names, roles, companies, emails, and phone numbers.
Remove duplicates. Only include contacts with at least a name.

Return ONLY a JSON object:
{"contacts": [{"name": "Full Name", "role": "Job title or role", "company": "Company name", "email": "email@example.com", "phone": "+41 XX XXX XX XX"}], "confidence": 0.0-1.0}"""},
                {"role": "user", "content": f"Extract contacts from this document:\n\n{text_content[:8000]}"},
            ],
            max_tokens=2000,
        )
        response_text = response.choices[0].message.content
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if json_match:
            result = json.loads(json_match.group())
            seen = set()
            unique = []
            for c in result.get("contacts", []):
                name = c.get("name", "").strip().lower()
                if name and name not in seen:
                    seen.add(name)
                    unique.append(c)
            result["contacts"] = unique
            return result
        return {"contacts": [], "confidence": 0.3}
    except Exception as e:
        logger.error(f"Contact extraction failed: {e}")
        return {"contacts": [], "confidence": 0.1, "extraction_failed": True}
