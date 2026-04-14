"""
JWT authentication — local mode and Cognito (production) mode.

LOCAL_AUTH=true  → JWTs are issued and validated by this backend using
                   SECRET_KEY. No AWS account needed. Tokens look identical
                   to the client — the switch is invisible to Flutter.

LOCAL_AUTH=false → JWTs are issued by AWS Cognito and validated here
                   using Cognito's public JWKS keys. Production behaviour.

The public surface — decode_token() and extract_user_id() — is the same
in both modes. The dependency in dependencies.py never needs to change.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from jose import ExpiredSignatureError, JWTError, jwk, jwt

from app.config import get_settings
from app.core.exceptions import ExpiredTokenError, InvalidTokenError


# ---------------------------------------------------------------------------
# Local JWT helpers (LOCAL_AUTH=true)
# ---------------------------------------------------------------------------

def _create_local_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
) -> str:
    """Sign a JWT locally using SECRET_KEY."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "iss": "gatherease-local",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_local_access_token(user_id: str) -> str:
    settings = get_settings()
    return _create_local_token(
        subject=user_id,
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_local_refresh_token(user_id: str) -> str:
    settings = get_settings()
    return _create_local_token(
        subject=user_id,
        token_type="refresh",
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def _decode_local_token(token: str) -> dict[str, Any]:
    """Validate a locally-issued JWT."""
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
    except ExpiredSignatureError as exc:
        raise ExpiredTokenError() from exc
    except JWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    return claims


# ---------------------------------------------------------------------------
# Cognito JWT helpers (LOCAL_AUTH=false)
# ---------------------------------------------------------------------------

_jwks_cache: dict[str, Any] | None = None
_jwks_fetched_at: float = 0
_JWKS_TTL = 3600


async def _get_jwks() -> dict[str, Any]:
    global _jwks_cache, _jwks_fetched_at
    now = time.monotonic()
    if _jwks_cache is None or (now - _jwks_fetched_at) > _JWKS_TTL:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(settings.cognito_jwks_url)
            resp.raise_for_status()
            _jwks_cache = resp.json()
            _jwks_fetched_at = now
    return _jwks_cache  # type: ignore[return-value]


async def _decode_cognito_token(token: str) -> dict[str, Any]:
    """Validate a Cognito-issued JWT against the JWKS public keys."""
    settings = get_settings()
    try:
        headers = jwt.get_unverified_headers(token)
        kid = headers.get("kid")
        if not kid:
            raise InvalidTokenError("Token header missing 'kid'.")

        jwks = await _get_jwks()
        key_data = next(
            (k for k in jwks.get("keys", []) if k["kid"] == kid), None
        )
        if key_data is None:
            raise InvalidTokenError("No matching public key found for token.")

        public_key = jwk.construct(key_data)
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=settings.cognito_client_id,
            issuer=(
                f"https://cognito-idp.{settings.cognito_region}.amazonaws.com"
                f"/{settings.cognito_user_pool_id}"
            ),
        )
    except ExpiredSignatureError as exc:
        raise ExpiredTokenError() from exc
    except JWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    return claims


# ---------------------------------------------------------------------------
# Public interface — used by dependencies.py (same in both modes)
# ---------------------------------------------------------------------------

async def decode_token(token: str) -> dict[str, Any]:
    """Validate a JWT and return its claims.

    Routes to local or Cognito validation based on LOCAL_AUTH setting.
    """
    settings = get_settings()
    if settings.local_auth:
        return _decode_local_token(token)
    return await _decode_cognito_token(token)


def extract_user_id(claims: dict[str, Any]) -> str:
    """Return the user UUID from decoded claims (same field in both modes)."""
    sub = claims.get("sub")
    if not sub:
        raise InvalidTokenError("Token claims missing 'sub'.")
    return sub


# Keep old name as alias so nothing else breaks
decode_cognito_token = decode_token
