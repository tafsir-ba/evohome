"""
Error Monitoring Module

Centralized error tracking and logging for production visibility.
Captures exceptions with context for debugging without external dependencies.

In production, this can be extended to send to Sentry, Datadog, etc.
For now, implements structured logging with severity levels.
"""

import logging
import traceback
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from functools import wraps
from fastapi import Request, HTTPException

logger = logging.getLogger("evohome.errors")

# Configure structured logging format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)


class ErrorContext:
    """Captures context for error reporting."""
    
    def __init__(
        self,
        request: Optional[Request] = None,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        endpoint: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ):
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.user_id = user_id
        self.user_role = user_role
        self.endpoint = endpoint
        self.extra = extra or {}
        
        if request:
            self.method = request.method
            self.path = str(request.url.path)
            self.query = str(request.url.query) if request.url.query else None
            self.client_ip = request.client.host if request.client else None
            self.user_agent = request.headers.get("user-agent", "")[:200]
        else:
            self.method = None
            self.path = None
            self.query = None
            self.client_ip = None
            self.user_agent = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "user_role": self.user_role,
            "endpoint": self.endpoint,
            "method": self.method,
            "path": self.path,
            "query": self.query,
            "client_ip": self.client_ip,
            "extra": self.extra
        }


def capture_exception(
    exc: Exception,
    context: Optional[ErrorContext] = None,
    severity: str = "error"
) -> str:
    """
    Capture and log an exception with context.
    
    Args:
        exc: The exception to capture
        context: Optional error context
        severity: error, warning, critical
    
    Returns:
        Error ID for reference
    """
    error_id = f"err_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
    
    error_data = {
        "error_id": error_id,
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
        "context": context.to_dict() if context else {}
    }
    
    # Log based on severity
    log_message = json.dumps(error_data, default=str)
    
    if severity == "critical":
        logger.critical(log_message)
    elif severity == "warning":
        logger.warning(log_message)
    else:
        logger.error(log_message)
    
    return error_id


def capture_warning(
    message: str,
    context: Optional[ErrorContext] = None,
    extra: Optional[Dict[str, Any]] = None
):
    """Log a warning without exception."""
    warning_data = {
        "type": "warning",
        "message": message,
        "context": context.to_dict() if context else {},
        "extra": extra or {}
    }
    logger.warning(json.dumps(warning_data, default=str))


def capture_info(
    message: str,
    category: str = "general",
    extra: Optional[Dict[str, Any]] = None
):
    """Log informational event for monitoring."""
    info_data = {
        "type": "info",
        "category": category,
        "message": message,
        "extra": extra or {},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    logger.info(json.dumps(info_data, default=str))


# Specific capture functions for key areas

def capture_auth_failure(
    reason: str,
    email: Optional[str] = None,
    request: Optional[Request] = None
):
    """Track authentication failures for security monitoring."""
    context = ErrorContext(request=request, endpoint="auth")
    capture_warning(
        f"Auth failure: {reason}",
        context=context,
        extra={"email": email[:50] if email else None, "reason": reason}
    )


def capture_payment_error(
    error: Exception,
    user_id: Optional[str] = None,
    operation: str = "unknown",
    request: Optional[Request] = None
):
    """Track Stripe payment errors."""
    context = ErrorContext(request=request, user_id=user_id, endpoint="billing")
    context.extra["operation"] = operation
    capture_exception(error, context=context, severity="error")


def capture_email_error(
    error: Exception,
    recipient: Optional[str] = None,
    template: Optional[str] = None,
    request: Optional[Request] = None
):
    """Track email delivery failures."""
    context = ErrorContext(request=request, endpoint="email")
    context.extra["recipient"] = recipient[:50] if recipient else None
    context.extra["template"] = template
    capture_exception(error, context=context, severity="warning")


def capture_ai_error(
    error: Exception,
    operation: str = "extraction",
    document_id: Optional[str] = None,
    request: Optional[Request] = None
):
    """Track AI/OpenAI operation failures."""
    context = ErrorContext(request=request, endpoint="ai")
    context.extra["operation"] = operation
    context.extra["document_id"] = document_id
    capture_exception(error, context=context, severity="warning")


def capture_websocket_error(
    error: Exception,
    user_id: Optional[str] = None,
    action: str = "unknown"
):
    """Track WebSocket errors."""
    context = ErrorContext(user_id=user_id, endpoint="websocket")
    context.extra["action"] = action
    capture_exception(error, context=context, severity="warning")


def capture_document_error(
    error: Exception,
    document_id: Optional[str] = None,
    operation: str = "unknown",
    user_id: Optional[str] = None,
    request: Optional[Request] = None
):
    """Track document operation failures."""
    context = ErrorContext(request=request, user_id=user_id, endpoint="documents")
    context.extra["document_id"] = document_id
    context.extra["operation"] = operation
    capture_exception(error, context=context, severity="error")
