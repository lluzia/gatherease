"""
Pytest fixtures for GatherEase backend tests.

Key fixtures:
- app          – FastAPI app instance with overridden settings
- client       – AsyncClient wired to the test app
- db_session   – isolated async DB session per test (rolled back after)
- mock_cognito – mocks the Boto3 Cognito client so auth tests don't hit AWS
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Set required environment variables BEFORE any app module is imported.
# app/main.py calls create_app() at module level, which calls get_settings(),
# which reads from the environment. Without these, every import of app.main
# raises a ValidationError for missing fields.
# ---------------------------------------------------------------------------
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("COGNITO_REGION", "eu-west-1")
os.environ.setdefault("COGNITO_USER_POOL_ID", "eu-west-1_TEST")
os.environ.setdefault("COGNITO_CLIENT_ID", "test-client-id")
os.environ.setdefault("S3_BUCKET_NAME", "gatherease-test")
os.environ.setdefault("AWS_REGION", "eu-west-1")
os.environ.setdefault("CORS_ORIGINS", '["http://localhost:3000"]')
os.environ.setdefault("LOCAL_AUTH", "true")

# ---------------------------------------------------------------------------
# Now it is safe to import app modules
# ---------------------------------------------------------------------------
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.dependencies import get_session
from app.main import create_app
from app.models.base import Base
from app.models.user import User

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="session")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        # Use create_all with a custom event that skips enum type creation.
        # Enums with create_type=False are handled by pg_enum() in models,
        # but SQLite (test DB) doesn't need them anyway — they're just strings.
        await conn.run_sync(lambda c: Base.metadata.create_all(c, checkfirst=True))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a session that rolls back after each test."""
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=True)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def app(db_session: AsyncSession):
    # Clear the lru_cache so settings re-read from the env vars we set above
    get_settings.cache_clear()
    fastapi_app = create_app()

    async def override_get_session():
        yield db_session

    fastapi_app.dependency_overrides[get_session] = override_get_session
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        yield c


@pytest.fixture(autouse=True)
def mock_cognito():
    """Auto-used: replaces the Cognito client with a MagicMock in every test."""
    mock = MagicMock()
    mock.sign_up.return_value = {"UserSub": str(uuid.uuid4()), "UserConfirmed": False}
    mock.initiate_auth.return_value = {
        "AuthenticationResult": {
            "AccessToken": "mock-access-token",
            "RefreshToken": "mock-refresh-token",
            "IdToken": "mock-id-token",
            "ExpiresIn": 3600,
        }
    }
    mock.global_sign_out.return_value = {}
    mock.forgot_password.return_value = {}
    mock.confirm_forgot_password.return_value = {}

    # get_cognito_client is imported lazily inside service methods,
    # so we patch it at the source module only.
    with patch("app.services.cognito.get_cognito_client", return_value=mock):
        yield mock


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """A persisted User record for tests that need an authenticated user."""
    user = User(
        cognito_sub=str(uuid.uuid4()),
        email="test@gatherease.app",
        full_name="Test User",
        preferred_language="en",
    )
    db_session.add(user)
    await db_session.flush()
    return user
