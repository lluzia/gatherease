"""
Request-level middleware for GatherEase.

RequestContextMiddleware
    - Generates a unique request_id for every request (or inherits from
      X-Request-ID header if provided by upstream load balancer).
    - Binds it to structlog context so every log line within that request
      carries the same request_id automatically.
    - Attaches X-Request-ID and X-Process-Time to the response headers.
"""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start = time.perf_counter()

        # Bind to structlog context for this request's lifetime
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{elapsed_ms}ms"

        logger.info(
            "request_complete",
            status_code=response.status_code,
            duration_ms=elapsed_ms,
        )

        return response
