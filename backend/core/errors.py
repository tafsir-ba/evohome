"""
Canonical Error Normalizer.

Every API error response uses one shape:
{
  "error": "machine_readable_code",
  "message": "Human-readable description",
  "request_id": "req_xxxxxxxxxxxx",
  "source": "validation|api|service|storage|notification|db",
  "details": {}
}

No [object Object]. No raw tracebacks. No ambiguous strings.
"""
import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

# Status code → default source mapping
_STATUS_SOURCE = {
    400: "validation",
    401: "api",
    403: "api",
    404: "api",
    405: "api",
    409: "service",
    422: "validation",
    429: "api",
    500: "service",
    502: "service",
    503: "service",
}


def _get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _normalize_detail(detail, status_code: int) -> dict:
    """Extract error, message, source, details from various detail formats."""
    if isinstance(detail, dict):
        return {
            "error": detail.get("error", "request_failed"),
            "message": detail.get("message", str(detail)),
            "source": detail.get("source", _STATUS_SOURCE.get(status_code, "service")),
            "details": detail.get("details", {}),
        }
    if isinstance(detail, list):
        # Pydantic validation errors
        return {
            "error": "validation_error",
            "message": "; ".join(
                f"{'.'.join(str(loc) for loc in e.get('loc', []))}: {e.get('msg', '')}"
                for e in detail
            ),
            "source": "validation",
            "details": {"errors": detail},
        }
    if isinstance(detail, str):
        return {
            "error": _code_from_status(status_code),
            "message": detail,
            "source": _STATUS_SOURCE.get(status_code, "service"),
            "details": {},
        }
    return {
        "error": _code_from_status(status_code),
        "message": str(detail) if detail else "An error occurred",
        "source": _STATUS_SOURCE.get(status_code, "service"),
        "details": {},
    }


def _code_from_status(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        422: "validation_error",
        429: "rate_limited",
        500: "internal_error",
    }.get(status_code, "request_failed")


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Normalize all HTTP exceptions to canonical error shape."""
    normalized = _normalize_detail(exc.detail, exc.status_code)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": normalized["error"],
            "message": normalized["message"],
            "request_id": _get_request_id(request),
            "source": normalized["source"],
            "details": normalized["details"],
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Normalize Pydantic/FastAPI validation errors."""
    errors = exc.errors()
    message = "; ".join(
        f"{'.'.join(str(loc) for loc in e.get('loc', []))}: {e.get('msg', '')}"
        for e in errors
    )
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": message,
            "request_id": _get_request_id(request),
            "source": "validation",
            "details": {"errors": errors},
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions. Log full traceback, return safe response."""
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred",
            "request_id": _get_request_id(request),
            "source": "service",
            "details": {},
        },
    )
