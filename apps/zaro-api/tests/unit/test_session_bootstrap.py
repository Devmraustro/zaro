"""Cold-page-load session bootstrap (FD-01 secure refresh-on-load).

GET /auth/session probes the HttpOnly refresh cookie WITHOUT rotating it and
issues only the CSRF double-submit value. These tests pin the security
contract: no token minting, no rotation, no reuse-detection trigger, and the
CSRF cookie re-set uses the same flags as login/refresh.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.auth_session import AuthSession
from app.services import auth_service

pytestmark = pytest.mark.asyncio


async def _make_session(db_session, settings, user, *, expires_in_days=None):
    session, secret = await auth_service.create_session_for_user(
        db_session, settings, user=user, ip_address=None, user_agent=None
    )
    if expires_in_days is not None:
        from datetime import UTC, datetime, timedelta

        session.expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)
    await db_session.commit()
    return session, secret


async def _login(client, user):
    resp = await client.post("/api/v1/auth/login", json={"email": user.email, "password": "test-password-123"})
    assert resp.status_code == 200, resp.text
    return resp


async def _count_sessions(db_session):
    rows = (await db_session.execute(select(AuthSession))).scalars().all()
    return rows


class TestSessionBootstrap:
    async def test_bootstrap_returns_active_and_matching_csrf_cookie(
        self, client: AsyncClient, db_session, settings, user_factory
    ):
        user = await user_factory()
        login = await _login(client, user)
        refresh_secret = login.json()["refresh_token"]

        resp = await client.get("/api/v1/auth/session")

        assert resp.status_code == 200
        data = resp.json()
        assert data["session_active"] is True
        assert isinstance(data["csrf_token"], str) and len(data["csrf_token"]) > 20
        assert data["csrf_token"] == client.cookies.get("zaro_csrf")
        assert data["csrf_token"] != refresh_secret
        assert resp.headers["cache-control"] == "no-store, private"

    async def test_bootstrap_does_not_rotate_refresh_credential(
        self, client: AsyncClient, db_session, settings, user_factory
    ):
        user = await user_factory()
        login = await _login(client, user)
        secret_v1 = login.json()["refresh_token"]

        before = await _count_sessions(db_session)
        resp = await client.get("/api/v1/auth/session")
        assert resp.json()["session_active"] is True

        # Session count unchanged (no sibling row minted) and stale rows
        # untouched => the credential was not rotated.
        after = await _count_sessions(db_session)
        assert len(after) == len(before)

        # The same credential still works for a normal (rotating) refresh.
        refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": secret_v1})
        assert refresh.status_code == 200

    async def test_bootstrap_never_triggers_reuse_detection(
        self, client: AsyncClient, db_session, settings, user_factory
    ):
        user = await user_factory()
        login = await _login(client, user)
        secret = login.json()["refresh_token"]

        # Multiple cold loads in a row must not revoke the session family.
        for _ in range(3):
            resp = await client.get("/api/v1/auth/session")
            assert resp.json()["session_active"] is True

        refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": secret})
        assert refresh.status_code == 200

    async def test_bootstrap_without_cookie_is_inactive(self, client: AsyncClient, settings):
        resp = await client.get("/api/v1/auth/session")

        assert resp.status_code == 200
        data = resp.json()
        assert data["session_active"] is False
        assert data["csrf_token"] is None

    async def test_bootstrap_with_revoked_cookie_is_inactive(
        self, client: AsyncClient, db_session, settings, user_factory
    ):
        user = await user_factory()
        _, secret = await _make_session(db_session, settings, user)
        client.cookies.set("zaro_refresh", secret)
        session = (await db_session.execute(select(AuthSession).where(AuthSession.user_id == user.id))).scalars().all()
        assert len(session) == 1
        await auth_service.revoke_session_by_id(db_session, user_id=user.id, session_id=session[0].id, reason="logout")
        await db_session.commit()

        resp = await client.get("/api/v1/auth/session")

        assert resp.json()["session_active"] is False
        assert resp.json()["csrf_token"] is None

    async def test_bootstrap_with_expired_cookie_is_inactive(
        self, client: AsyncClient, db_session, settings, user_factory
    ):
        user = await user_factory()
        _, secret = await _make_session(db_session, settings, user, expires_in_days=-1)
        client.cookies.set("zaro_refresh", secret)

        resp = await client.get("/api/v1/auth/session")

        assert resp.json()["session_active"] is False

    async def test_bootstrap_with_disabled_user_is_inactive(
        self, client: AsyncClient, db_session, settings, user_factory
    ):
        user = await user_factory()
        _, secret = await _make_session(db_session, settings, user)
        client.cookies.set("zaro_refresh", secret)
        user.is_active = False
        await db_session.commit()

        resp = await client.get("/api/v1/auth/session")

        assert resp.json()["session_active"] is False

    async def test_csrf_from_bootstrap_enables_cookie_refresh(
        self, client: AsyncClient, db_session, settings, user_factory
    ):
        """End-to-end cold-reload flow: bootstrap -> cookie-sourced refresh."""
        user = await user_factory()
        await _login(client, user)

        bootstrap = await client.get("/api/v1/auth/session")
        csrf = bootstrap.json()["csrf_token"]

        refresh = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf})
        assert refresh.status_code == 200, refresh.text
        assert refresh.json()["csrf_token"] == client.cookies.get("zaro_csrf")
