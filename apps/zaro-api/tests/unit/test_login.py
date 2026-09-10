"""Login endpoint behaviour: success path, generic failures, input hardening."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.enums import Role

pytestmark = pytest.mark.asyncio


class TestLoginSuccess:
    async def test_returns_tokens_and_user(self, client: AsyncClient, user_factory, login_user):
        user = await user_factory(role=Role.ADMIN)
        data = await login_user(client, user.email, "test-password-123")

        assert data["token_type"] == "bearer"
        assert isinstance(data["access_token"], str) and len(data["access_token"]) > 20
        assert isinstance(data["refresh_token"], str) and len(data["refresh_token"]) > 20
        assert data["access_token"] != data["refresh_token"]
        assert data["expires_in"] > 0
        assert data["user"]["email"] == user.email
        assert data["user"]["role"] == "admin"
        assert data["user"]["is_active"] is True

    async def test_sets_refresh_and_csrf_cookies(self, client: AsyncClient, user_factory, login_user):
        user = await user_factory()
        await login_user(client, user.email, "test-password-123")

        assert client.cookies.get("zaro_refresh") is not None
        assert client.cookies.get("zaro_csrf") is not None

    async def test_refresh_cookie_is_httponly(self, client: AsyncClient, user_factory, login_user):
        user = await user_factory()
        resp = await client.post("/api/v1/auth/login", json={"email": user.email, "password": "test-password-123"})
        refresh_cookie = next(c for c in resp.headers.get_list("set-cookie") if c.startswith("zaro_refresh="))
        csrf_cookie = next(c for c in resp.headers.get_list("set-cookie") if c.startswith("zaro_csrf="))

        assert "httponly" in refresh_cookie.lower()
        assert "httponly" not in csrf_cookie.lower()
        assert "path=/api/v1/auth" in refresh_cookie.lower()

    async def test_login_response_returns_csrf_token_matching_cookie(
        self, client: AsyncClient, user_factory
    ):
        user = await user_factory()
        resp = await client.post("/api/v1/auth/login", json={"email": user.email, "password": "test-password-123"})
        assert resp.status_code == 200
        data = resp.json()

        csrf_cookie = next(c for c in resp.headers.get_list("set-cookie") if c.startswith("zaro_csrf="))
        cookie_value = csrf_cookie.split("=", 1)[1].split(";", 1)[0]

        assert isinstance(data["csrf_token"], str) and len(data["csrf_token"]) > 20
        assert data["csrf_token"] == cookie_value
        assert client.cookies.get("zaro_csrf") == cookie_value
        # The CSRF field must never carry the refresh credential.
        assert data["csrf_token"] != data["refresh_token"]

    async def test_updates_last_login_at(self, client: AsyncClient, db_session, user_factory, login_user):

        user = await user_factory()
        assert user.last_login_at is None
        await login_user(client, user.email, "test-password-123")

        await db_session.refresh(user)
        assert user.last_login_at is not None

    async def test_login_writes_success_audit_event(self, client: AsyncClient, db_session, user_factory, login_user):
        user = await user_factory()
        await login_user(client, user.email, "test-password-123")

        rows = (
            (await db_session.execute(select(AuditLog).where(AuditLog.action == "AUTH_LOGIN_SUCCESS"))).scalars().all()
        )
        assert len(rows) == 1
        assert rows[0].result == "SUCCESS"
        assert str(rows[0].actor_user_id) == str(user.id)


class TestLoginFailures:
    async def test_wrong_password_generic_401(self, client: AsyncClient, user_factory):
        user = await user_factory()
        resp = await client.post("/api/v1/auth/login", json={"email": user.email, "password": "wrong-password"})
        assert resp.status_code == 401
        assert resp.json()["error"]["message"] == "Invalid email or password"

    async def test_unknown_email_same_error_as_wrong_password(self, client: AsyncClient, user_factory):
        known = await user_factory()
        wrong_pw = await client.post("/api/v1/auth/login", json={"email": known.email, "password": "wrong-password"})
        unknown = await client.post(
            "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever-pass"}
        )
        assert unknown.status_code == 401
        assert unknown.json()["error"]["message"] == wrong_pw.json()["error"]["message"]

    async def test_disabled_account_is_rejected_generically(self, client: AsyncClient, user_factory):
        user = await user_factory(is_active=False)
        resp = await client.post("/api/v1/auth/login", json={"email": user.email, "password": "test-password-123"})
        assert resp.status_code == 401
        assert resp.json()["error"]["message"] == "Invalid email or password"

    @pytest.mark.parametrize(
        "payload",
        [
            {"password": "test-password-123"},
            {"email": "someone@example.com"},
            {},
            {"email": "not-an-email", "password": "test-password-123"},
            {"email": "someone@example.com", "password": ""},
            {"email": "someone@example.com", "password": "x" * 129},
        ],
    )
    async def test_malformed_payloads_return_422(self, client: AsyncClient, payload):
        resp = await client.post("/api/v1/auth/login", json=payload)
        assert resp.status_code == 422

    async def test_forged_role_field_is_rejected(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "someone@example.com", "password": "test-password-123", "role": "owner"},
        )
        assert resp.status_code == 422

    async def test_forged_permissions_field_is_rejected(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "someone@example.com",
                "password": "test-password-123",
                "permissions": ["users.read", "audit.read"],
            },
        )
        assert resp.status_code == 422

    async def test_failure_writes_audit_event_without_actor(self, client: AsyncClient, db_session, user_factory):
        user = await user_factory()
        await client.post("/api/v1/auth/login", json={"email": user.email, "password": "nope-nope"})

        rows = (
            (await db_session.execute(select(AuditLog).where(AuditLog.action == "AUTH_LOGIN_FAILURE"))).scalars().all()
        )
        assert len(rows) == 1
        assert rows[0].result == "FAILURE"
        assert rows[0].actor_user_id is None
        assert rows[0].metadata_json["reason"] == "invalid_password"

    async def test_no_password_hash_in_any_response(self, client: AsyncClient, user_factory, login_user):
        user = await user_factory()
        data = await login_user(client, user.email, "test-password-123")
        import json

        assert "$argon2" not in json.dumps(data)
