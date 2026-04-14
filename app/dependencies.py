"""
FastAPI dependency functions.

These are injected into route handlers via Depends().

    async def my_route(
        db: DbSession,
        current_user: CurrentUser,
    ) -> ...:

Type aliases at the bottom make the injection syntax clean and readable.
"""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import UnauthorisedError, UserNotFoundError
from app.core.security import decode_token, extract_user_id
from app.db.session import get_db
from app.models.user import User

logger = structlog.get_logger(__name__)

_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

async def get_session(
    session: AsyncSession = Depends(get_db),
) -> AsyncSession:
    return session


DbSession = Annotated[AsyncSession, Depends(get_session)]


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_session),
) -> User:
    """Validate Bearer token and return the authenticated User record.

    Local auth mode:  token sub = user.id (UUID)
    Cognito mode:     token sub = user.cognito_sub
    """
    if credentials is None:
        raise UnauthorisedError("No authentication token provided.")

    claims = await decode_token(credentials.credentials)
    sub = extract_user_id(claims)
    settings = get_settings()

    if settings.local_auth:
        # Local mode — sub is the user's UUID primary key
        try:
            user_id = uuid.UUID(sub)
        except ValueError:
            raise UnauthorisedError("Invalid token subject.")
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
    else:
        # Cognito mode — sub is the Cognito user pool sub
        result = await db.execute(
            select(User).where(User.cognito_sub == sub)
        )

    user = result.scalar_one_or_none()

    if user is None:
        logger.warning("authenticated_user_not_in_db", sub=sub)
        raise UserNotFoundError("Authenticated user not found in database.")

    if not user.is_active:
        raise UnauthorisedError("User account is deactivated.")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
