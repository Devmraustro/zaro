"""Session introspection and revocation endpoints (/me, /sessions, logout)."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.auth_session import AuthSession
from app.models.enums import Role

pytestmark = pytest.mark.asyncio


class TestMe:
    async def test_returns_identity_and_server_derived_permissions(self, client: AsyncClient, user_factory, login_user):
        user = await user_factory(role=Role.WORKER)
        data = await login_user(client, user.email, "test-password-123")

        resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(user.id)
        assert body["email"] == user.email
        assert body["role"] == "worker"
        assert body["status"] == "ACTIVE"
        assert body["permissions"] == ["materials.read", "production.read", "products.read"]

    async def test_owner_permissions_include_admin_capabilities(self, client: AsyncClient, user_factory, login_user):
        user = await user_factory(role=Role.OWNER)
        data = await login_user(client, user.email, "test-password-123")

        resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
        body = resp.json()
        perms = set(body["permissions"])
        assert {"users.read", "audit.read", "products.manage_price"} <= perms
        assert body["permissions"] == sorted(body["permissions"])

    async def test_requires_authentication(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_client_cannot_inject_role_via_headers(self, client: AsyncClient, user_factory, login_user):
        user = await user_factory(role=Role.WORKER)
        data = await login_user(client, user.email, "test-password-123")
        auth = {"Authorization": f"Bearer {data['access_token']}"}

        for extra in (
            {"X-Role": "owner"},
            {"X-Forwarded-Roles": "owner"},
            {"X-Permissions": "users.read,audit.read"},
        ):
            body = (await client.get("/api/v1/auth/me", headers={**auth, **extra})).json()
            assert body["role"] == "worker"
            assert "users.read" not in body["permissions"]


class TestSessionListing:
    async def test_lists_current_session(self, client: AsyncClient, db_session, settings, user_factory, login_user):

        user = await user_factory()
        data = await login_user(client, user.email, "test-password-123")

        resp = await client.get("/api/v1/auth/sessions", headers={"Authorization": f"Bearer {data['access_token']}"})
        assert resp.status_code == 200
        sessions = resp.json()["sessions"]
        assert len(sessions) == 1
        assert sessions[0]["current"] is True
        assert sessions[0]["revoked"] is False
        assert sessions[0]["id"]

    async def test_marks_only_callers_session_as_current(
        self, client: AsyncClient, db_session, settings, user_factory, login_user
    ):
        user = await user_factory()
        _first = await login_user(client, user.email, "test-password-123")
        second = await login_user(client, user.email, "test-password-123")

        resp = await client.get("/api/v1/auth/sessions", headers={"Authorization": f"Bearer {second['access_token']}"})
        sessions = resp.json()["sessions"]
        assert len(sessions) == 2
        current_flags = sorted(s["current"] for s in sessions)
        assert current_flags == [False, True]

    async def test_requires_authentication(self, client: AsyncClient):
        assert (await client.get("/api/v1/auth/sessions")).status_code == 401


class TestRevocation:
    async def test_revoke_specific_session_kills_its_refresh(
        self, client: AsyncClient, db_session, settings, user_factory, login_user
    ):
        user = await user_factory()
        first = await login_user(client, user.email, "test-password-123")
        second = await login_user(client, user.email, "test-password-123")

        sessions = (
            await client.get("/api/v1/auth/sessions", headers={"Authorization": f"Bearer {first['access_token']}"})
        ).json()["sessions"]
        target = next(s for s in sessions if not s["current"])

        resp = await client.post(
            "/api/v1/auth/sessions/revoke",
            json={"session_id": target["id"]},
            headers={"Authorization": f"Bearer {first['access_token']}"},
        )
        assert resp.status_code == 200

        dead = await client.post("/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]})
        assert dead.status_code == 401
        alive = await client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
        assert alive.status_code == 200

    async def test_cannot_revoke_another_users_session(
        self, client: AsyncClient, db_session, settings, user_factory, login_user
    ):
        victim = await user_factory()
        victim_login = await login_user(client, victim.email, "test-password-123")

        other = await user_factory(role=Role.OWNER)
        other_login = await login_user(client, other.email, "test-password-123")

        victim_sessions = (
            await client.get(
                "/api/v1/auth/sessions", headers={"Authorization": f"Bearer {victim_login['access_token']}"}
            )
        ).json()["sessions"]

        resp = await client.post(
            "/api/v1/auth/sessions/revoke",
            json={"session_id": victim_sessions[0]["id"]},
            headers={"Authorization": f"Bearer {other_login['access_token']}"},
        )
        assert resp.status_code == 404

        still_valid = await client.post("/api/v1/auth/refresh", json={"refresh_token": victim_login["refresh_token"]})
        assert still_valid.status_code == 200

    async def test_revoke_all_revokes_every_session(
        self, client: AsyncClient, db_session, settings, user_factory, login_user
    ):
        user = await user_factory()
        first = await login_user(client, user.email, "test-password-123")
        second = await login_user(client, user.email, "test-password-123")

        resp = await client.post(
            "/api/v1/auth/sessions/revoke-all",
            headers={"Authorization": f"Bearer {first['access_token']}"},
        )
        assert resp.status_code == 200
        assert "2" in resp.json()["message"]

        for secret in (first["refresh_token"], second["refresh_token"]):
            dead = await client.post("/api/v1/auth/refresh", json={"refresh_token": secret})
            assert dead.status_code == 401

        rows = (await db_session.execute(select(AuthSession).where(AuthSession.user_id == user.id))).scalars().all()
        assert all(s.revoked_at is not None for s in rows)

    async def test_revoke_unknown_session_404(self, client: AsyncClient, user_factory, login_user):
        import uuid

        user = await user_factory(role=Role.OWNER)
        data = await login_user(client, user.email, "test-password-123")
        resp = await client.post(
            "/api/v1/auth/sessions/revoke",
            json={"session_id": str(uuid.uuid4())},
            headers={"Authorization": f"Bearer {data['access_token']}"},
        )
        assert resp.status_code == 404


class TestLogout:
    async def test_logout_revokes_and_clears_cookies(self, client: AsyncClient, user_factory, login_user):
        user = await user_factory()
        data = await login_user(client, user.email, "test-password-123")

        resp = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {data['access_token']}"})
        assert resp.status_code == 204

        cleared = "\n".join(resp.headers.get_list("set-cookie"))
        assert "zaro_refresh" in cleared
        assert "zaro_csrf" in cleared

        dead = await client.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
        assert dead.status_code == 401

    async def test_logout_writes_audit_event(self, client: AsyncClient, db_session, user_factory, login_user):
        user = await user_factory()
        data = await login_user(client, user.email, "test-password-123")
        await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {data['access_token']}"})

        rows = (await db_session.execute(select(AuditLog).where(AuditLog.action == "AUTH_LOGOUT"))).scalars().all()
        assert len(rows) == 1
        assert str(rows[0].actor_user_id) == str(user.id)

    async def test_refresh_after_logout_never_recovers(self, client: AsyncClient, user_factory, login_user):
        user = await user_factory()
        data = await login_user(client, user.email, "test-password-123")
        await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {data['access_token']}"})

        for _ in range(3):
            resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
            assert resp.status_code == 401
