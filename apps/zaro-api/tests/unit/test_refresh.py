"""Refresh token rotation, CSRF-protected cookie flow, and reuse detection."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.auth_session import AuthSession
from app.services import auth_service

pytestmark = pytest.mark.asyncio


async def _make_session(db_session, settings, user):
    session, secret = await auth_service.create_session_for_user(
        db_session, settings, user=user, ip_address=None, user_agent=None
    )
    await db_session.commit()
    return session, secret


class TestRotation:
    async def test_refresh_with_body_token_rotates(self, client: AsyncClient, db_session, settings, user_factory):
        user = await user_factory()
        old_session, secret = await _make_session(db_session, settings, user)

        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": secret})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["access_token"] and data["refresh_token"]
        assert data["refresh_token"] != secret
        assert isinstance(data["csrf_token"], str) and len(data["csrf_token"]) > 20
        assert data["csrf_token"] != data["refresh_token"]

        rows = (await db_session.execute(select(AuthSession))).scalars().all()
        by_id = {str(s.id): s for s in rows}
        assert by_id[str(old_session.id)].revoke_reason == "rotated"
        new_row = next(s for s in rows if str(s.id) not in {str(old_session.id)})
        assert new_row.family_id == old_session.family_id
        assert new_row.revoked_at is None

    async def test_old_credential_rejected_after_rotation(
        self, client: AsyncClient, db_session, settings, user_factory
    ):
        user = await user_factory()
        _, secret = await _make_session(db_session, settings, user)

        first = await client.post("/api/v1/auth/refresh", json={"refresh_token": secret})
        assert first.status_code == 200
        second = await client.post("/api/v1/auth/refresh", json={"refresh_token": secret})
        assert second.status_code == 401

    async def test_cookie_refresh_accepts_body_provided_csrf_and_returns_new_matching_token(
        self, client: AsyncClient, user_factory
    ):
        """The login/refresh csrf_token mirrors the csrf cookie so a cross-origin
        SPA (which cannot read the path-scoped API-origin cookie) can present the
        matching X-CSRF-Token header for cookie-sourced refresh."""
        user = await user_factory()
        login = await client.post("/api/v1/auth/login", json={"email": user.email, "password": "test-password-123"})
        assert login.status_code == 200
        login_data = login.json()

        assert login_data["csrf_token"] == client.cookies.get("zaro_csrf")

        resp = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": login_data["csrf_token"]})
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert isinstance(data["csrf_token"], str) and len(data["csrf_token"]) > 20
        assert data["csrf_token"] == client.cookies.get("zaro_csrf")
        assert data["csrf_token"] != login_data["csrf_token"]
        assert data["csrf_token"] != data["refresh_token"]
        # The HttpOnly refresh cookie is rotated alongside the body value.
        assert data["refresh_token"] == client.cookies.get("zaro_refresh")

    async def test_refresh_via_cookie_requires_csrf_header(
        self, client: AsyncClient, db_session, settings, user_factory
    ):
        user = await user_factory()
        _, secret = await _make_session(db_session, settings, user)
        client.cookies.set("zaro_refresh", secret)

        no_csrf = await client.post("/api/v1/auth/refresh")
        assert no_csrf.status_code == 403

        client.cookies.set("zaro_csrf", "csrf-token-value")
        wrong = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": "different-value"})
        assert wrong.status_code == 403

        ok = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": "csrf-token-value"})
        assert ok.status_code == 200

    async def test_expired_refresh_rejected(self, client: AsyncClient, db_session, settings, user_factory):
        from datetime import UTC, datetime, timedelta

        user = await user_factory()
        session, secret = await _make_session(db_session, settings, user)
        session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await db_session.commit()

        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": secret})
        assert resp.status_code == 401
        assert resp.json()["error"]["message"] == "Invalid or expired refresh token"

    async def test_disabled_account_refresh_revokes_family(
        self, client: AsyncClient, db_session, settings, user_factory
    ):
        user = await user_factory()
        _session, secret = await _make_session(db_session, settings, user)
        user.is_active = False
        await db_session.commit()

        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": secret})
        assert resp.status_code == 401

        rows = (await db_session.execute(select(AuthSession).where(AuthSession.user_id == user.id))).scalars().all()
        assert all(s.revoked_at is not None for s in rows)


class TestReuseDetection:
    async def test_reuse_of_rotated_token_revokes_whole_family(
        self, client: AsyncClient, db_session, settings, user_factory
    ):
        user = await user_factory()
        original_session, secret_v1 = await _make_session(db_session, settings, user)

        r1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": secret_v1})
        assert r1.status_code == 200
        secret_v2 = r1.json()["refresh_token"]

        replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": secret_v1})
        assert replay.status_code == 401

        stolen = await client.post("/api/v1/auth/refresh", json={"refresh_token": secret_v2})
        assert stolen.status_code == 401

        rows = (
            (await db_session.execute(select(AuthSession).where(AuthSession.family_id == original_session.family_id)))
            .scalars()
            .all()
        )
        assert len(rows) >= 2
        assert all(s.revoked_at is not None for s in rows)
        assert any(s.revoke_reason == "reuse_detected" for s in rows)

    async def test_reuse_writes_audit_event(self, client: AsyncClient, db_session, settings, user_factory):
        user = await user_factory()
        _, secret_v1 = await _make_session(db_session, settings, user)
        r1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": secret_v1})
        assert r1.status_code == 200
        await client.post("/api/v1/auth/refresh", json={"refresh_token": secret_v1})

        rows = (
            (await db_session.execute(select(AuditLog).where(AuditLog.action == "AUTH_REFRESH_REUSE_DETECTED")))
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].result == "FAILURE"
        assert str(rows[0].actor_user_id) == str(user.id)


class TestRefreshInputHardening:
    async def test_garbage_token_401(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": "garbage-token-value"})
        assert resp.status_code == 401
        assert resp.json()["error"]["message"] == "Invalid or expired refresh token"

    async def test_no_credentials_401(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401

    async def test_extra_fields_rejected(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "some-token-value-123", "user_id": "11111111-1111-1111-1111-111111111111"},
        )
        assert resp.status_code == 422
