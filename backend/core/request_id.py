"""
Request ID Middleware.

Generates a unique request ID for every incoming request.
Propagated via request.state.request_id and X-Request-ID response header.
"""
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


def generate_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:12]}"


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = generate_request_id()
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
