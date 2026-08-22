import os
import tempfile
import uuid
from datetime import UTC, datetime

os.environ.setdefault("ZARO_ENVIRONMENT", "test")
os.environ.setdefault("ZARO_SECRET_KEY", "test-secret-key-not-for-production-zaro")
os.environ.setdefault("ZARO_STORAGE_LOCAL_DIR", os.path.join(tempfile.gettempdir(), "zaro-api-test-storage"))

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings
from app.core.rate_limit import reset_rate_limiter
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models.enums import Role
from app.models.user import User


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture(autouse=True)
def _fresh_rate_limiter(settings: Settings):
    """Reset the limiter and force the in-memory backend for deterministic tests."""
    reset_rate_limiter()
    from app.core import rate_limit

    rate_limit.get_rate_limiter(settings).mark_redis_unavailable()
    yield
    reset_rate_limiter()


_engine = None
_session_factory = None


@pytest.fixture(scope="session", autouse=True)
def _db_setup(settings):
    global _engine, _session_factory
    _engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    yield


@pytest.fixture(autouse=True)
async def _setup_db(_db_setup):
    assert _engine is not None
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    assert _session_factory is not None
    async with _session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def app_factory(settings: Settings):
    """Build an app instance wired to the test database.

    Accepts Settings overrides, e.g. ``app_factory(login_ip_limit=2)``.
    """

    def _make(**updates) -> FastAPI:
        cfg = settings.model_copy(update=updates) if updates else settings
        app = create_app(cfg)

        assert _session_factory is not None

        async def _override_get_db():
            async with _session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = _override_get_db
        if updates:
            app.dependency_overrides[get_settings] = lambda: cfg
        return app

    return _make


@pytest.fixture
async def client(app_factory) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app_factory())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def user_factory(db_session):
    """Create a user in the test database and return them."""

    async def _create(
        role: Role = Role.WORKER,
        email: str | None = None,
        full_name: str = "Test User",
        is_active: bool = True,
        password: str = "test-password-123",
    ) -> User:
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email=email or f"test-{user_id.hex[:8]}@example.com",
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role,
            is_active=is_active,
            last_login_at=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(user)
        # Commit (not just flush): API requests run in separate sessions on
        # the same pooled connection; a request that ends without committing
        # would otherwise roll back this uncommitted insert on close.
        await db_session.commit()
        return user

    return _create


@pytest.fixture
def auth_header_factory(settings, user_factory):
    """Create a user and return an Authorization header dict."""

    async def _create(role: Role = Role.WORKER, **user_kwargs) -> tuple[dict[str, str], User]:
        user = await user_factory(role=role, **user_kwargs)
        token, _ = create_access_token(settings, subject=str(user.id))
        return {"Authorization": f"Bearer {token}"}, user

    return _create


@pytest.fixture
def login_user():
    """Login via the API and return the parsed response body."""

    async def _login(client: AsyncClient, email: str, password: str) -> dict:
        resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert resp.status_code == 200, resp.text
        return resp.json()

    return _login
