"""
Centralised exception hierarchy for GatherEase.

All domain exceptions inherit from AppException.
The register_exception_handlers() function wires them into FastAPI so
every error — expected or not — returns the same JSON envelope:

    {
        "error": {
            "code":    "GATHERING_NOT_FOUND",
            "message": "Gathering not found.",
            "detail":  null          # optional structured payload
        }
    }
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.i18n import translate

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class AppException(Exception):
    """Root of all GatherEase application exceptions."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        detail: object = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.detail = detail
        super().__init__(self.message)


# ---------------------------------------------------------------------------
# 400 Bad Request
# ---------------------------------------------------------------------------


class BadRequestError(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "BAD_REQUEST"
    message = "Invalid request."


class ValidationError(BadRequestError):
    code = "VALIDATION_ERROR"
    message = "Request validation failed."


# ---------------------------------------------------------------------------
# 401 Unauthorised
# ---------------------------------------------------------------------------


class UnauthorisedError(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "UNAUTHORISED"
    message = "Authentication required."


class InvalidTokenError(UnauthorisedError):
    code = "INVALID_TOKEN"
    message = "Token is invalid or expired."


class ExpiredTokenError(UnauthorisedError):
    code = "TOKEN_EXPIRED"
    message = "Token has expired."


# ---------------------------------------------------------------------------
# 403 Forbidden
# ---------------------------------------------------------------------------


class ForbiddenError(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"
    message = "You do not have permission to perform this action."


# ---------------------------------------------------------------------------
# 404 Not Found
# ---------------------------------------------------------------------------


class NotFoundError(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"
    message = "Resource not found."


class UserNotFoundError(NotFoundError):
    code = "USER_NOT_FOUND"
    message = "User not found."


class GatheringNotFoundError(NotFoundError):
    code = "GATHERING_NOT_FOUND"
    message = "Gathering not found."


# ---------------------------------------------------------------------------
# 409 Conflict
# ---------------------------------------------------------------------------


class ConflictError(AppException):
    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"
    message = "Resource already exists."


class EmailAlreadyRegisteredError(ConflictError):
    code = "EMAIL_ALREADY_REGISTERED"
    message = "An account with this email already exists."


# ---------------------------------------------------------------------------
# 402 / 403 Premium required
# ---------------------------------------------------------------------------


class GatheringLimitError(ForbiddenError):
    code = "GATHERING_LIMIT_REACHED"
    message = "Free plan limit reached. Upgrade to Premium for unlimited gatherings."


# ---------------------------------------------------------------------------
# 422 Unprocessable
# ---------------------------------------------------------------------------


class UnprocessableError(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "UNPROCESSABLE"
    message = "Unable to process request."


# ---------------------------------------------------------------------------
# Response builder
# ---------------------------------------------------------------------------


def _error_response(
    status_code: int,
    code: str,
    message: str,
    detail: object = None,
) -> JSONResponse:
    # Translate the message into the request locale (resolved by middleware).
    # Falls back to the English `message` arg if the code is not in the
    # catalogue — this covers dynamic messages set at raise-site.
    translated = translate(code) or message
    body: dict = {"error": {"code": code, "message": translated}}
    if detail is not None:
        body["error"]["detail"] = detail
    return JSONResponse(status_code=status_code, content=body)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to the FastAPI app."""

    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request, exc: AppException
    ) -> JSONResponse:
        logger.warning(
            "app_exception",
            code=exc.code,
            message=exc.message,
            path=request.url.path,
            method=request.method,
        )
        return _error_response(exc.status_code, exc.code, exc.message, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Pydantic v2 puts the raw exception object in error["ctx"]["error"].
        # That is not JSON-serialisable, so we convert it to a string here.
        def _make_serialisable(v: object) -> object:
            """Recursively convert non-JSON-serialisable values to strings.

            Pydantic v2 stores constraint values (e.g. Decimal('0'),
            float('inf')) in the error ctx dict. JSONResponse will raise
            TypeError on these, so we stringify anything that isn't a
            basic JSON type.
            """
            if isinstance(v, dict):
                return {k: _make_serialisable(val) for k, val in v.items()}
            if isinstance(v, (list, tuple)):
                return [_make_serialisable(i) for i in v]
            if isinstance(v, (str, int, float, bool)) or v is None:
                return v
            return str(v)

        def _sanitise(errors: list) -> list:
            clean = []
            for e in errors:
                e = dict(e)
                # loc is a tuple — convert to list for JSON
                if "loc" in e:
                    e["loc"] = list(e["loc"])
                # ctx may contain Decimal, float('inf'), Exception objects, etc.
                if "ctx" in e:
                    e["ctx"] = _make_serialisable(e["ctx"])
                clean.append(e)
            return clean

        sanitised = _sanitise(exc.errors())
        logger.warning(
            "validation_error",
            errors=sanitised,
            path=request.url.path,
        )
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "VALIDATION_ERROR",
            "Request validation failed.",
            sanitised,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "unhandled_exception",
            exc_info=exc,
            path=request.url.path,
            method=request.method,
        )
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "An unexpected error occurred.",
        )
