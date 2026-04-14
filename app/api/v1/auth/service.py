"""
Auth service — routes between local mode and AWS Cognito.

LOCAL_AUTH=true  → passwords hashed with bcrypt, stored in the users table,
                   JWTs issued by app/core/security.py. Zero AWS cost.

LOCAL_AUTH=false → all auth delegated to AWS Cognito. Passwords never touch
                   our DB. JWTs issued by Cognito.

The router never changes — it always calls AuthService methods and gets
back the same response shapes regardless of mode.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.config import get_settings
from app.core.exceptions import (
    BadRequestError,
    EmailAlreadyRegisteredError,
    InvalidTokenError,
    UnauthorisedError,
)
from app.core.security import (
    create_local_access_token,
    create_local_refresh_token,
    decode_token,
    extract_user_id,
)
from app.models.user import User

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Password hashing (local mode only)
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    except ImportError:
        # fallback: plain sha256 — install bcrypt for real hashing
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest()


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        import bcrypt
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ImportError:
        import hashlib
        return hashlib.sha256(plain.encode()).hexdigest() == hashed


# ---------------------------------------------------------------------------
# Auth service
# ---------------------------------------------------------------------------

class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._settings = get_settings()

    # ── Register ─────────────────────────────────────────────────────────────

    async def register(self, payload: RegisterRequest) -> dict:
        if self._settings.local_auth:
            return await self._register_local(payload)
        return await self._register_cognito(payload)

    async def _register_local(self, payload: RegisterRequest) -> dict:
        # Check email not already taken
        existing = await self._db.execute(
            select(User).where(User.email == payload.email)
        )
        if existing.scalar_one_or_none():
            raise EmailAlreadyRegisteredError()

        user = User(
            cognito_sub=f"local-{payload.email}",  # stable local identifier
            email=payload.email,
            full_name=payload.full_name,
            preferred_language=payload.preferred_language,
            hashed_password=_hash_password(payload.password),
        )
        self._db.add(user)
        await self._db.flush()
        logger.info("user_registered_local", user_id=str(user.id), email=payload.email)
        return {"message": "Registration successful. You can now log in."}

    async def _register_cognito(self, payload: RegisterRequest) -> dict:
        from botocore.exceptions import ClientError
        from app.services.cognito import get_cognito_client
        client = get_cognito_client()
        try:
            response = client.sign_up(
                ClientId=self._settings.cognito_client_id,
                Username=payload.email,
                Password=payload.password,
                UserAttributes=[
                    {"Name": "email", "Value": payload.email},
                    {"Name": "name", "Value": payload.full_name or ""},
                ],
            )
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code == "UsernameExistsException":
                raise EmailAlreadyRegisteredError() from exc
            if code == "InvalidPasswordException":
                raise BadRequestError(exc.response["Error"]["Message"]) from exc
            raise BadRequestError("Registration failed. Please try again.") from exc

        cognito_sub: str = response["UserSub"]
        user = User(
            cognito_sub=cognito_sub,
            email=payload.email,
            full_name=payload.full_name,
            preferred_language=payload.preferred_language,
        )
        self._db.add(user)
        await self._db.flush()
        logger.info("user_registered_cognito", user_id=str(user.id))
        return {"message": "Registration successful. Please verify your email."}

    # ── Login ────────────────────────────────────────────────────────────────

    async def login(self, payload: LoginRequest) -> TokenResponse:
        if self._settings.local_auth:
            return await self._login_local(payload)
        return await self._login_cognito(payload)

    async def _login_local(self, payload: LoginRequest) -> TokenResponse:
        result = await self._db.execute(
            select(User).where(User.email == payload.email)
        )
        user = result.scalar_one_or_none()

        if not user or not user.hashed_password:
            raise UnauthorisedError("Invalid email or password.")
        if not _verify_password(payload.password, user.hashed_password):
            raise UnauthorisedError("Invalid email or password.")
        if not user.is_active:
            raise UnauthorisedError("Account is deactivated.")

        access_token = create_local_access_token(str(user.id))
        refresh_token = create_local_refresh_token(str(user.id))
        logger.info("user_logged_in_local", user_id=str(user.id))
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self._settings.access_token_expire_minutes * 60,
        )

    async def _login_cognito(self, payload: LoginRequest) -> TokenResponse:
        from botocore.exceptions import ClientError
        from app.services.cognito import get_cognito_client
        client = get_cognito_client()
        try:
            response = client.initiate_auth(
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={
                    "USERNAME": payload.email,
                    "PASSWORD": payload.password,
                },
                ClientId=self._settings.cognito_client_id,
            )
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("NotAuthorizedException", "UserNotFoundException"):
                raise UnauthorisedError("Invalid email or password.") from exc
            if code == "UserNotConfirmedException":
                raise UnauthorisedError("Email address not yet verified.") from exc
            raise UnauthorisedError("Login failed. Please try again.") from exc

        auth = response["AuthenticationResult"]
        return TokenResponse(
            access_token=auth["AccessToken"],
            refresh_token=auth["RefreshToken"],
            expires_in=auth["ExpiresIn"],
        )

    # ── Refresh ──────────────────────────────────────────────────────────────

    async def refresh(self, payload: RefreshRequest) -> TokenResponse:
        if self._settings.local_auth:
            return await self._refresh_local(payload)
        return await self._refresh_cognito(payload)

    async def _refresh_local(self, payload: RefreshRequest) -> TokenResponse:
        try:
            claims = await decode_token(payload.refresh_token)
        except Exception as exc:
            raise InvalidTokenError("Refresh token is invalid or expired.") from exc

        if claims.get("type") != "refresh":
            raise InvalidTokenError("Token is not a refresh token.")

        user_id = extract_user_id(claims)
        access_token = create_local_access_token(user_id)
        return TokenResponse(
            access_token=access_token,
            refresh_token=payload.refresh_token,
            expires_in=self._settings.access_token_expire_minutes * 60,
        )

    async def _refresh_cognito(self, payload: RefreshRequest) -> TokenResponse:
        from botocore.exceptions import ClientError
        from app.services.cognito import get_cognito_client
        client = get_cognito_client()
        try:
            response = client.initiate_auth(
                AuthFlow="REFRESH_TOKEN_AUTH",
                AuthParameters={"REFRESH_TOKEN": payload.refresh_token},
                ClientId=self._settings.cognito_client_id,
            )
        except ClientError as exc:
            raise InvalidTokenError("Refresh token is invalid or expired.") from exc
        auth = response["AuthenticationResult"]
        return TokenResponse(
            access_token=auth["AccessToken"],
            refresh_token=payload.refresh_token,
            expires_in=auth["ExpiresIn"],
        )

    # ── Logout ───────────────────────────────────────────────────────────────

    async def logout(self, access_token: str) -> dict:
        if self._settings.local_auth:
            # Local JWTs are stateless — client just discards the token.
            # For real revocation, a token blocklist (Redis) would be added here.
            return {"message": "Logged out successfully."}

        from app.services.cognito import get_cognito_client
        client = get_cognito_client()
        try:
            client.global_sign_out(AccessToken=access_token)
        except Exception as exc:
            logger.warning("cognito_logout_error", error=str(exc))
        return {"message": "Logged out successfully."}

    # ── Forgot password ──────────────────────────────────────────────────────

    async def forgot_password(self, payload: ForgotPasswordRequest) -> dict:
        if self._settings.local_auth:
            # In local mode, just log — Mailpit will show the email
            logger.info("forgot_password_local", email=payload.email)
            return {"message": "If that email is registered, a reset code has been sent."}

        from app.services.cognito import get_cognito_client
        client = get_cognito_client()
        try:
            client.forgot_password(
                ClientId=self._settings.cognito_client_id,
                Username=payload.email,
            )
        except Exception as exc:
            logger.warning("cognito_forgot_password_error", error=str(exc))
        return {"message": "If that email is registered, a reset code has been sent."}

    # ── Reset password ───────────────────────────────────────────────────────

    async def reset_password(self, payload: ResetPasswordRequest) -> dict:
        if self._settings.local_auth:
            # Local mode: find user and update hashed password directly
            result = await self._db.execute(
                select(User).where(User.email == payload.email)
            )
            user = result.scalar_one_or_none()
            if user:
                user.hashed_password = _hash_password(payload.new_password)
                self._db.add(user)
                await self._db.flush()
            # Always return success to avoid email enumeration
            return {"message": "Password reset successful. You can now log in."}

        from botocore.exceptions import ClientError
        from app.services.cognito import get_cognito_client
        client = get_cognito_client()
        try:
            client.confirm_forgot_password(
                ClientId=self._settings.cognito_client_id,
                Username=payload.email,
                ConfirmationCode=payload.confirmation_code,
                Password=payload.new_password,
            )
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code == "CodeMismatchException":
                raise BadRequestError("Invalid or expired reset code.") from exc
            if code == "InvalidPasswordException":
                raise BadRequestError(exc.response["Error"]["Message"]) from exc
            raise BadRequestError("Password reset failed.") from exc
        return {"message": "Password reset successful. You can now log in."}
