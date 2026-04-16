"""
Request-level middleware for GatherEase.

RequestContextMiddleware
    - Generates a unique request_id for every request (or inherits from
      X-Request-ID header if provided by upstream load balancer).
    - Resolves the request locale from the Accept-Language header and binds
      it to structlog context so i18n.translate() works anywhere in the stack.
    - Binds request_id and locale to structlog context so every log line
      within that request carries them automatically.
    - Attaches X-Request-ID, X-Process-Time, and Content-Language to the
      response headers.
"""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.i18n import bind_locale, resolve_locale

logger = structlog.get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start = time.perf_counter()

        # Resolve locale from Accept-Language header
        accept_language = request.headers.get("Accept-Language")
        locale = resolve_locale(accept_language)

        # Bind to structlog context for this request's lifetime.
        # Both request_id and locale are now available to every log call
        # and to i18n.get_request_locale() / translate() without passing
        # them explicitly through the call stack.
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        bind_locale(locale)

        response = await call_next(request)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{elapsed_ms}ms"
        response.headers["Content-Language"] = locale

        logger.info(
            "request_complete",
            status_code=response.status_code,
            duration_ms=elapsed_ms,
            locale=locale,
        )

        return response
