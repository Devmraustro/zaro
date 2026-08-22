"""Security negative tests and cross-cutting auth invariants.

Maps to the Phase 1.3 security checklist:
- privilege escalation via forged fields/headers must fail
- revoked credentials must never become valid again
- secrets (password hashes, refresh tokens) must never leak via API or audit log
"""

import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.auth_session import AuthSession
from app.models.enums import Role

pytestmark = pytest.mark.asyncio


class TestPrivilegeEscalation:
    async def test_forged_role_in_login_body_rejected(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "x@example.com", "password": "whatever-pass", "role": "owner"},
        )
        assert resp.status_code == 422

    async def test_forged_permissions_in_login_body_rejected(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "x@example.com", "password": "whatever-pass", "permissions": ["*"]},
        )
        assert resp.status_code == 422

    async def test_role_header_cannot_elevate_me_endpoint(self, client: AsyncClient, user_factory, login_user):
        user = await user_factory(role=Role.CUSTOMER)
        data = await login_user(client, user.email, "test-password-123")
        auth = {"Authorization": f"Bearer {data['access_token']}"}

        for extra in (
            {"X-Role": "owner"},
            {"X-Forwarded-Roles": "owner"},
            {"X-Permissions": "users.read,audit.read"},
        ):
            body = (await client.get("/api/v1/auth/me", headers={**auth, **extra})).json()
            assert body["role"] == "customer"
            assert body["permissions"] == ["products.read"]

    async def test_change_password_cannot_target_other_user(
        self, client: AsyncClient, db_session, user_factory, login_user
    ):
        victim = await user_factory()
        attacker = await user_factory(role=Role.ADMIN)
        attacker_login = await login_user(client, attacker.email, "test-password-123")

        resp = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "irrelevant",
                "new_password": "Pwned-Pass-123",
                "user_id": str(victim.id),
            },
            headers={"Authorization": f"Bearer {attacker_login['access_token']}"},
        )
        assert resp.status_code == 422

    async def test_session_revocation_scoped_to_owner(
        self, client: AsyncClient, db_session, settings, user_factory, login_user
    ):
        from app.services import auth_service

        victim = await user_factory()
        _, victim_secret = await auth_service.create_session_for_user(
            db_session, settings, user=victim, ip_address=None, user_agent=None
        )
        victim_session_id = str((await db_session.execute(select(AuthSession))).scalars().all()[-1].id)

        attacker = await user_factory(role=Role.OWNER)
        attacker_login = await login_user(client, attacker.email, "test-password-123")

        resp = await client.post(
            "/api/v1/auth/sessions/revoke",
            json={"session_id": victim_session_id},
            headers={"Authorization": f"Bearer {attacker_login['access_token']}"},
        )
        assert resp.status_code == 404

        still_valid = await client.post("/api/v1/auth/refresh", json={"refresh_token": victim_secret})
        assert still_valid.status_code == 200


class TestCredentialLifecycle:
    async def test_revoked_refresh_never_valid_again(self, client: AsyncClient, db_session, settings, user_factory):
        from app.services import auth_service

        user = await user_factory()
        session, secret = await auth_service.create_session_for_user(
            db_session, settings, user=user, ip_address=None, user_agent=None
        )
        await db_session.commit()

        await auth_service.revoke_session_by_id(db_session, user_id=user.id, session_id=session.id, reason="logout")
        await db_session.commit()

        for _ in range(2):
            resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": secret})
            assert resp.status_code == 401

    async def test_rotated_then_reused_kills_family(self, client: AsyncClient, db_session, settings, user_factory):
        from app.services import auth_service

        user = await user_factory()
        _, v1 = await auth_service.create_session_for_user(
            db_session, settings, user=user, ip_address=None, user_agent=None
        )
        await db_session.commit()

        r1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": v1})
        v2 = r1.json()["refresh_token"]

        assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": v1})).status_code == 401
        assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": v2})).status_code == 401

    async def test_disabled_account_cannot_login_or_refresh(
        self, client: AsyncClient, db_session, settings, user_factory
    ):
        from app.services import auth_service

        user = await user_factory()
        _, secret = await auth_service.create_session_for_user(
            db_session, settings, user=user, ip_address=None, user_agent=None
        )
        user.is_active = False
        await db_session.commit()

        login = await client.post("/api/v1/auth/login", json={"email": user.email, "password": "test-password-123"})
        assert login.status_code == 401

        refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": secret})
        assert refresh.status_code == 401


class TestMalformedCredentials:
    async def test_malformed_bearer_on_protected_endpoints(self, client: AsyncClient):
        garbage_tokens = [
            "garbage",
            "a.b.c",
            "eyJhbGciOiJIUzI1NiJ9.e30.wrong-signature",
            "x" * 2000,
        ]
        for token in garbage_tokens:
            me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert me.status_code == 401

    async def test_access_token_used_as_refresh_rejected(self, client: AsyncClient, user_factory, login_user):
        user = await user_factory()
        data = await login_user(client, user.email, "test-password-123")
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": data["access_token"]})
        assert resp.status_code == 401

    @pytest.mark.parametrize("password_len", [129, 5000])
    async def test_overlong_passwords_rejected(self, client: AsyncClient, password_len):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "x@example.com", "password": "p" * password_len},
        )
        assert resp.status_code == 422

    async def test_overlong_refresh_token_rejected(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": "t" * 513})
        assert resp.status_code == 422


class TestSecretHygiene:
    async def test_no_password_hash_in_auth_responses(self, client: AsyncClient, user_factory, login_user):
        user = await user_factory(role=Role.OWNER)
        login_data = await login_user(client, user.email, "test-password-123")

        me = (await client.get("/api/v1/auth/me")).json()
        sessions = (
            await client.get("/api/v1/auth/sessions", headers={"Authorization": f"Bearer {login_data['access_token']}"})
        ).json()

        for payload in (login_data, me, sessions):
            assert "$argon2" not in json.dumps(payload)
            assert "hashed_password" not in json.dumps(payload)

    async def test_refresh_secrets_never_appear_in_audit_log(
        self, client: AsyncClient, db_session, user_factory, login_user
    ):
        user = await user_factory()
        login_data = await login_user(client, user.email, "test-password-123")
        refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": login_data["refresh_token"]})
        new_secret = refreshed.json()["refresh_token"]
        await client.post(
            "/api/v1/auth/logout", headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"}
        )

        rows = (await db_session.execute(select(AuditLog))).scalars().all()
        blob = json.dumps([r.metadata_json for r in rows]) + json.dumps([r.resource_id for r in rows])
        assert login_data["refresh_token"] not in blob
        assert new_secret not in blob

    async def test_reset_token_hash_not_reversible_in_db(self, client: AsyncClient, db_session, user_factory):
        from app.models.password_reset import PasswordResetToken

        user = await user_factory()
        await client.post("/api/v1/auth/forgot-password", json={"email": user.email})

        rows = (await db_session.execute(select(PasswordResetToken))).scalars().all()
        assert len(rows) == 1
        record = rows[0]
        assert len(record.token_hash) == 64
        assert record.used_at is None
