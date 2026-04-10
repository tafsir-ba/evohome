"""
Workflow Service - Phase 4: Multi-step workflow execution engine

This service handles:
- Pre-defined workflow templates
- Sequential command execution with database persistence
- Step tracking and status management
- Real email notifications via Resend
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class WorkflowStepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNING = "completed_with_warning"  # Action succeeded but side-effect (e.g., email) failed
    FAILED = "failed"
    SKIPPED = "skipped"
    AWAITING_CONFIRMATION = "awaiting_confirmation"


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"  # All steps done but some had warnings
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class WorkflowStep(BaseModel):
    step_id: str
    name: str
    description: str
    action: str
    params: Dict[str, Any] = {}
    status: WorkflowStepStatus = WorkflowStepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    warning: Optional[str] = None  # For non-fatal issues like email delivery failure
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    requires_confirmation: bool = False
    optional: bool = False
    rollback_action: Optional[str] = None  # Action to undo this step if later steps fail
    rollback_params: Optional[Dict[str, Any]] = None


class WorkflowTemplate(BaseModel):
    template_id: str
    name: str
    description: str
    category: str
    icon: str
    steps: List[Dict[str, Any]]
    required_context: List[str]
    estimated_duration: str
    # NEW: Define what selectors the UI should show
    ui_selectors: List[str] = []  # e.g., ["document", "timeline_step", "client"]


class WorkflowExecution(BaseModel):
    execution_id: str
    template_id: str
    template_name: str
    agent_id: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    mode: str = "automatic"
    context: Dict[str, Any] = {}
    steps: List[WorkflowStep] = []
    current_step_index: int = 0
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    is_demo: bool = False


# ==================== WORKFLOW TEMPLATES ====================

WORKFLOW_TEMPLATES: Dict[str, WorkflowTemplate] = {
    "new_client_onboarding": WorkflowTemplate(
        template_id="new_client_onboarding",
        name="New Client Onboarding",
        description="Create client record and send welcome email with login instructions",
        category="onboarding",
        icon="UserPlus",
        estimated_duration="1-2 minutes",
        required_context=["project_id", "client_name", "client_email"],
        ui_selectors=[],  # Manual input only
        steps=[
            {
                "name": "Create Client Record",
                "description": "Add new client to the system with project assignment",
                "action": "create_client",
                "params_from_context": ["project_id", "client_name", "client_email", "client_phone"],
                "optional": False
            },
            {
                "name": "Send Welcome Email",
                "description": "Send email with login link and getting started guide",
                "action": "send_welcome_email",
                "params_from_context": ["client_email", "client_name", "project_name"],
                "optional": False
            }
        ]
    ),
    
    "invoice_paid_processing": WorkflowTemplate(
        template_id="invoice_paid_processing",
        name="Invoice Paid Processing",
        description="Mark invoice as paid and send payment confirmation email to buyer",
        category="payment",
        icon="CreditCard",
        estimated_duration="30 seconds",
        required_context=["document_id"],
        ui_selectors=["document"],  # Show document picker
        steps=[
            {
                "name": "Mark Invoice Paid",
                "description": "Update invoice status to Paid with timestamp",
                "action": "update_document_status",
                "params": {"status": "Paid"},
                "params_from_context": ["document_id"],
                "optional": False
            },
            {
                "name": "Send Payment Confirmation",
                "description": "Email buyer confirming payment received",
                "action": "send_payment_confirmation_email",
                "params_from_context": ["document_id", "client_email", "client_name", "amount"],
                "optional": False
            }
        ]
    ),
    
    "milestone_completion": WorkflowTemplate(
        template_id="milestone_completion",
        name="Milestone Completion",
        description="Mark timeline step complete and notify buyer of progress",
        category="milestone",
        icon="Flag",
        estimated_duration="30 seconds",
        required_context=["step_id"],
        ui_selectors=["timeline_step"],  # Show timeline step picker
        steps=[
            {
                "name": "Mark Step Complete",
                "description": "Update timeline step status to completed",
                "action": "complete_timeline_step",
                "params_from_context": ["step_id"],
                "optional": False
            },
            {
                "name": "Notify Buyer",
                "description": "Send milestone completion email to buyer",
                "action": "send_milestone_email",
                "params_from_context": ["client_email", "client_name", "step_name", "project_name"],
                "optional": False
            }
        ]
    ),
    
    "send_document": WorkflowTemplate(
        template_id="send_document",
        name="Send Document to Client",
        description="Send invoice or quote to client via email with PDF attachment link",
        category="communication",
        icon="Send",
        estimated_duration="30 seconds",
        required_context=["document_id"],
        ui_selectors=["document"],
        steps=[
            {
                "name": "Mark as Sent",
                "description": "Update document status to Sent",
                "action": "update_document_status",
                "params": {"status": "Sent"},
                "params_from_context": ["document_id"],
                "optional": False
            },
            {
                "name": "Send Document Email",
                "description": "Email document to client with review link",
                "action": "send_document_email",
                "params_from_context": ["document_id", "client_email", "client_name", "document_type", "document_title"],
                "optional": False
            }
        ]
    ),
    
    "project_announcement": WorkflowTemplate(
        template_id="project_announcement",
        name="Project Announcement",
        description="Send announcement to all clients in a project",
        category="communication",
        icon="Megaphone",
        estimated_duration="1-2 minutes",
        required_context=["project_id", "message_title", "message_content"],
        ui_selectors=[],  # Manual input
        steps=[
            {
                "name": "Create Announcement",
                "description": "Create announcement in activity feed",
                "action": "create_announcement",
                "params_from_context": ["project_id", "message_title", "message_content"],
                "optional": False
            },
            {
                "name": "Email All Clients",
                "description": "Send announcement email to all project clients",
                "action": "send_project_announcement_email",
                "params_from_context": ["project_id", "message_title", "message_content"],
                "optional": False
            }
        ]
    )
}


class WorkflowService:
    """Service for managing and executing multi-step workflows with DB persistence"""
    
    def __init__(self, db):
        self.db = db
    
    def get_templates(self, category: Optional[str] = None) -> List[WorkflowTemplate]:
        """Get all available workflow templates"""
        templates = list(WORKFLOW_TEMPLATES.values())
        if category:
            templates = [t for t in templates if t.category == category]
        return templates
    
    def get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """Get a specific workflow template"""
        return WORKFLOW_TEMPLATES.get(template_id)
    
    def validate_context(self, template: WorkflowTemplate, context: Dict[str, Any]) -> List[str]:
        """Validate required context fields"""
        missing = []
        for field in template.required_context:
            if field not in context or not context[field]:
                missing.append(field)
        return missing
    
    async def create_execution(
        self, 
        template_id: str, 
        agent_id: str, 
        context: Dict[str, Any],
        mode: str = "automatic",
        is_demo: bool = False
    ) -> WorkflowExecution:
        """Create and persist a new workflow execution"""
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Unknown workflow template: {template_id}")
        
        missing = self.validate_context(template, context)
        if missing:
            raise ValueError(f"Missing required context: {', '.join(missing)}")
        
        execution_id = f"wf_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        
        steps = []
        for i, step_def in enumerate(template.steps):
            step = WorkflowStep(
                step_id=f"{execution_id}_step_{i}",
                name=step_def["name"],
                description=step_def["description"],
                action=step_def["action"],
                params=step_def.get("params", {}),
                requires_confirmation=step_def.get("requires_confirmation", False),
                optional=step_def.get("optional", False)
            )
            
            if "params_from_context" in step_def:
                for ctx_key in step_def["params_from_context"]:
                    if ctx_key in context:
                        step.params[ctx_key] = context[ctx_key]
            
            steps.append(step)
        
        execution = WorkflowExecution(
            execution_id=execution_id,
            template_id=template_id,
            template_name=template.name,
            agent_id=agent_id,
            mode=mode,
            context=context,
            steps=steps,
            created_at=now,
            is_demo=is_demo
        )
        
        # Persist to database - use datetime object for TTL to work
        doc = execution.model_dump()
        doc['created_at_date'] = datetime.now(timezone.utc)  # BSON Date for TTL index
        await self.db.workflow_executions.insert_one(doc)
        
        return execution
    
    async def update_execution(self, execution: WorkflowExecution):
        """Update execution in database"""
        await self.db.workflow_executions.update_one(
            {"execution_id": execution.execution_id},
            {"$set": execution.model_dump()}
        )
    
    async def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get execution from database"""
        doc = await self.db.workflow_executions.find_one(
            {"execution_id": execution_id},
            {"_id": 0}
        )
        if doc:
            return WorkflowExecution(**doc)
        return None
    
    async def get_agent_executions(
        self, 
        agent_id: str, 
        is_demo: bool = False,
        limit: int = 20
    ) -> List[WorkflowExecution]:
        """Get recent executions for an agent"""
        cursor = self.db.workflow_executions.find(
            {"agent_id": agent_id, "is_demo": is_demo},
            {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        
        executions = []
        async for doc in cursor:
            executions.append(WorkflowExecution(**doc))
        return executions
    
    async def execute_step(
        self, 
        execution: WorkflowExecution, 
        step_index: int,
        action_executor: callable
    ) -> WorkflowStep:
        """Execute a single workflow step"""
        if step_index >= len(execution.steps):
            raise ValueError("Step index out of range")
        
        step = execution.steps[step_index]
        now = datetime.now(timezone.utc).isoformat()
        
        step.status = WorkflowStepStatus.IN_PROGRESS
        step.started_at = now
        
        try:
            result = await action_executor(step.action, step.params, execution.context)
            
            step.status = WorkflowStepStatus.COMPLETED
            step.result = result
            step.completed_at = datetime.now(timezone.utc).isoformat()
            
            if result and isinstance(result, dict):
                execution.context.update(result)
            
            logger.info(f"Workflow step completed: {step.name} ({step.action})")
            
        except Exception as e:
            step.status = WorkflowStepStatus.FAILED
            step.error = str(e)
            step.completed_at = datetime.now(timezone.utc).isoformat()
            
            logger.error(f"Workflow step failed: {step.name} - {e}")
            
            if not step.optional:
                raise
        
        # Update in database
        await self.update_execution(execution)
        
        return step
    
    async def run_workflow(
        self, 
        execution: WorkflowExecution,
        action_executor: callable,
        rollback_executor: callable = None
    ) -> WorkflowExecution:
        """Run all steps in a workflow with proper status handling"""
        execution.status = WorkflowStatus.IN_PROGRESS
        execution.started_at = datetime.now(timezone.utc).isoformat()
        await self.update_execution(execution)
        
        completed_steps = []  # Track for potential rollback
        
        try:
            for i, step in enumerate(execution.steps):
                execution.current_step_index = i
                await self.execute_step(execution, i, action_executor)
                
                if step.status == WorkflowStepStatus.COMPLETED:
                    completed_steps.append(i)
            
            # Check if any steps had warnings
            has_warnings = any(
                s.status == WorkflowStepStatus.COMPLETED_WITH_WARNING 
                for s in execution.steps
            )
            
            if has_warnings:
                execution.status = WorkflowStatus.COMPLETED_WITH_WARNINGS
            else:
                execution.status = WorkflowStatus.COMPLETED
            
            execution.completed_at = datetime.now(timezone.utc).isoformat()
            
        except Exception as e:
            execution.status = WorkflowStatus.FAILED
            execution.error = str(e)
            execution.completed_at = datetime.now(timezone.utc).isoformat()
            logger.error(f"Workflow failed: {execution.execution_id} - {e}")
            
            # Attempt rollback of completed steps if rollback executor provided
            if rollback_executor and completed_steps:
                logger.info(f"Attempting rollback of {len(completed_steps)} completed steps")
                for step_idx in reversed(completed_steps):
                    step = execution.steps[step_idx]
                    if step.rollback_action:
                        try:
                            await rollback_executor(
                                step.rollback_action, 
                                step.rollback_params or {}, 
                                execution.context
                            )
                            logger.info(f"Rolled back step: {step.name}")
                        except Exception as rollback_error:
                            logger.error(f"Rollback failed for step {step.name}: {rollback_error}")
        
        await self.update_execution(execution)
        return execution
    
    async def cancel_execution(self, execution_id: str, agent_id: str) -> WorkflowExecution:
        """Cancel a workflow execution"""
        execution = await self.get_execution(execution_id)
        if not execution:
            raise ValueError(f"Execution not found: {execution_id}")
        
        if execution.agent_id != agent_id:
            raise ValueError("Not authorized")
        
        execution.status = WorkflowStatus.CANCELLED
        execution.completed_at = datetime.now(timezone.utc).isoformat()
        
        for step in execution.steps:
            if step.status == WorkflowStepStatus.PENDING:
                step.status = WorkflowStepStatus.SKIPPED
        
        await self.update_execution(execution)
        return execution
    
    async def retry_step(
        self,
        execution: WorkflowExecution,
        step_index: int,
        action_executor: callable
    ) -> WorkflowExecution:
        """Retry a failed or warning step in a workflow"""
        if step_index >= len(execution.steps):
            raise ValueError("Step index out of range")
        
        step = execution.steps[step_index]
        
        # Only allow retrying failed or warning steps
        if step.status not in [WorkflowStepStatus.FAILED, WorkflowStepStatus.COMPLETED_WITH_WARNING]:
            raise ValueError(f"Cannot retry step with status: {step.status}")
        
        # Reset step state
        step.status = WorkflowStepStatus.PENDING
        step.error = None
        step.warning = None
        step.result = None
        step.started_at = None
        step.completed_at = None
        
        # Re-run the step
        await self.execute_step(execution, step_index, action_executor)
        
        # Recalculate overall workflow status
        has_failed = any(s.status == WorkflowStepStatus.FAILED for s in execution.steps)
        has_warnings = any(s.status == WorkflowStepStatus.COMPLETED_WITH_WARNING for s in execution.steps)
        all_done = all(s.status in [
            WorkflowStepStatus.COMPLETED, 
            WorkflowStepStatus.COMPLETED_WITH_WARNING,
            WorkflowStepStatus.SKIPPED
        ] for s in execution.steps)
        
        if has_failed:
            execution.status = WorkflowStatus.FAILED
        elif all_done:
            if has_warnings:
                execution.status = WorkflowStatus.COMPLETED_WITH_WARNINGS
            else:
                execution.status = WorkflowStatus.COMPLETED
            execution.completed_at = datetime.now(timezone.utc).isoformat()
        
        await self.update_execution(execution)
        return execution
    
    def get_execution_summary(self, execution: WorkflowExecution) -> Dict[str, Any]:
        """Get summary for UI display"""
        completed = sum(1 for s in execution.steps if s.status in [
            WorkflowStepStatus.COMPLETED, 
            WorkflowStepStatus.COMPLETED_WITH_WARNING
        ])
        warnings = sum(1 for s in execution.steps if s.status == WorkflowStepStatus.COMPLETED_WITH_WARNING)
        failed = sum(1 for s in execution.steps if s.status == WorkflowStepStatus.FAILED)
        skipped = sum(1 for s in execution.steps if s.status == WorkflowStepStatus.SKIPPED)
        
        return {
            "execution_id": execution.execution_id,
            "template_id": execution.template_id,
            "template_name": execution.template_name,
            "status": execution.status,
            "mode": execution.mode,
            "progress": {
                "total": len(execution.steps),
                "completed": completed,
                "warnings": warnings,
                "failed": failed,
                "skipped": skipped,
                "current": execution.current_step_index
            },
            "steps": [
                {
                    "step_index": i,
                    "name": s.name,
                    "description": s.description,
                    "status": s.status,
                    "error": s.error,
                    "warning": s.warning,
                    "optional": s.optional,
                    "can_retry": s.status in [WorkflowStepStatus.FAILED, WorkflowStepStatus.COMPLETED_WITH_WARNING]
                }
                for i, s in enumerate(execution.steps)
            ],
            "created_at": execution.created_at,
            "completed_at": execution.completed_at,
            "error": execution.error
        }


# Singleton instance
_workflow_service: Optional[WorkflowService] = None

def get_workflow_service(db) -> WorkflowService:
    """Get or create the workflow service singleton"""
    global _workflow_service
    if _workflow_service is None:
        _workflow_service = WorkflowService(db)
    return _workflow_service
