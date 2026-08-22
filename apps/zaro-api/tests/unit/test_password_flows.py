"""Password change and forgot/reset flows, including single-use token semantics."""

import re
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.auth_session import AuthSession
from app.models.enums import Role
from app.models.password_reset import PasswordResetToken

pytestmark = pytest.mark.asyncio


class _CaptureSender:
    def __init__(self):
        self.messages = []

    async def send(self, message):
        self.messages.append(message)


@pytest.fixture
def capture_sender(monkeypatch):
    sender = _CaptureSender()
    monkeypatch.setattr("app.api.v1.endpoints.auth.get_email_sender", lambda: sender)
    return sender


def _extract_token(body: str) -> str:
    match = re.search(r"\n([A-Za-z0-9_\-]{16,})\n", body)
    assert match, f"no token found in email body: {body!r}"
    return match.group(1)


class TestChangePassword:
    async def test_change_keeps_current_session_revokes_others(
        self, client: AsyncClient, db_session, settings, user_factory, login_user
    ):
        user = await user_factory()
        stay = await login_user(client, user.email, "test-password-123")
        other = await login_user(client, user.email, "test-password-123")

        resp = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "test-password-123", "new_password": "BrandNew-Pass-123"},
            headers={"Authorization": f"Bearer {stay['access_token']}"},
        )
        assert resp.status_code == 200

        old_refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": other["refresh_token"]})
        assert old_refresh.status_code == 401

        current_refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": stay["refresh_token"]})
        assert current_refresh.status_code == 200

        rows = (await db_session.execute(select(AuthSession).where(AuthSession.user_id == user.id))).scalars().all()
        reasons = {s.revoke_reason for s in rows if s.revoked_at is not None}
        assert "password_change" in reasons

    async def test_old_password_no_longer_works(self, client: AsyncClient, user_factory, login_user):
        user = await user_factory()
        data = await login_user(client, user.email, "test-password-123")
        resp = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "test-password-123", "new_password": "BrandNew-Pass-123"},
            headers={"Authorization": f"Bearer {data['access_token']}"},
        )
        assert resp.status_code == 200

        old_login = await client.post("/api/v1/auth/login", json={"email": user.email, "password": "test-password-123"})
        assert old_login.status_code == 401

        new_login = await client.post("/api/v1/auth/login", json={"email": user.email, "password": "BrandNew-Pass-123"})
        assert new_login.status_code == 200

    async def test_wrong_current_password_401(self, client: AsyncClient, db_session, user_factory, login_user):
        from app.models.audit_log import AuditLog

        user = await user_factory()
        data = await login_user(client, user.email, "test-password-123")
        resp = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "totally-wrong", "new_password": "BrandNew-Pass-123"},
            headers={"Authorization": f"Bearer {data['access_token']}"},
        )
        assert resp.status_code == 401

        rows = (
            (await db_session.execute(select(AuditLog).where(AuditLog.action == "AUTH_PASSWORD_CHANGE")))
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].result == "FAILURE"

    async def test_weak_new_password_rejected(self, client: AsyncClient, user_factory, login_user):
        user = await user_factory()
        data = await login_user(client, user.email, "test-password-123")
        resp = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "test-password-123", "new_password": "short"},
            headers={"Authorization": f"Bearer {data['access_token']}"},
        )
        assert resp.status_code == 422

    async def test_cannot_target_another_user(self, client: AsyncClient, db_session, user_factory, login_user):
        victim = await user_factory()
        attacker = await user_factory(role=Role.OWNER)
        attacker_login = await login_user(client, attacker.email, "test-password-123")

        resp = await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "whatever",
                "new_password": "Hacked-Pass-123",
                "user_id": str(victim.id),
            },
            headers={"Authorization": f"Bearer {attacker_login['access_token']}"},
        )
        assert resp.status_code == 422

        await db_session.refresh(victim)
        from app.core.security import verify_password

        assert verify_password("test-password-123", victim.hashed_password)


class TestForgotResetFlow:
    async def test_known_and_unknown_emails_get_identical_response(
        self, client: AsyncClient, user_factory, capture_sender
    ):
        user = await user_factory()
        known = await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
        unknown = await client.post("/api/v1/auth/forgot-password", json={"email": "ghost@example.com"})

        assert known.status_code == unknown.status_code == 200
        assert known.json() == unknown.json()

    async def test_reset_email_contains_single_use_token(
        self, client: AsyncClient, db_session, user_factory, capture_sender
    ):
        user = await user_factory()
        await client.post("/api/v1/auth/forgot-password", json={"email": user.email})

        assert len(capture_sender.messages) == 1
        message = capture_sender.messages[0]
        assert message.to_address == user.email
        token = _extract_token(message.body)

        stored = (await db_session.execute(select(PasswordResetToken))).scalars().all()
        assert len(stored) == 1
        assert token not in stored[0].token_hash
        assert len(stored[0].token_hash) == 64

    async def test_full_reset_changes_password_and_revokes_sessions(
        self, client: AsyncClient, db_session, settings, user_factory, login_user, capture_sender
    ):
        user = await user_factory()
        pre_existing = await login_user(client, user.email, "test-password-123")

        await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
        token = _extract_token(capture_sender.messages[0].body)

        resp = await client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "Reset-Pass-456"})
        assert resp.status_code == 200

        old_pw = await client.post("/api/v1/auth/login", json={"email": user.email, "password": "test-password-123"})
        assert old_pw.status_code == 401

        new_pw = await client.post("/api/v1/auth/login", json={"email": user.email, "password": "Reset-Pass-456"})
        assert new_pw.status_code == 200

        dead = await client.post("/api/v1/auth/refresh", json={"refresh_token": pre_existing["refresh_token"]})
        assert dead.status_code == 401

    async def test_reset_token_is_single_use(self, client: AsyncClient, user_factory, capture_sender):
        user = await user_factory()
        await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
        token = _extract_token(capture_sender.messages[0].body)

        first = await client.post(
            "/api/v1/auth/reset-password", json={"token": token, "new_password": "Reset-Pass-456"}
        )
        assert first.status_code == 200

        second = await client.post(
            "/api/v1/auth/reset-password", json={"token": token, "new_password": "Another-Pass-789"}
        )
        assert second.status_code == 401

    async def test_new_request_invalidates_previous_unused_token(
        self, client: AsyncClient, user_factory, capture_sender
    ):
        user = await user_factory()
        await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
        first_token = _extract_token(capture_sender.messages[0].body)

        await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
        second_token = _extract_token(capture_sender.messages[1].body)
        assert first_token != second_token

        stale = await client.post(
            "/api/v1/auth/reset-password", json={"token": first_token, "new_password": "Reset-Pass-456"}
        )
        assert stale.status_code == 401

        fresh = await client.post(
            "/api/v1/auth/reset-password", json={"token": second_token, "new_password": "Reset-Pass-456"}
        )
        assert fresh.status_code == 200

    async def test_expired_reset_token_rejected(
        self, client: AsyncClient, db_session, settings, user_factory, capture_sender
    ):
        from datetime import UTC, datetime, timedelta

        user = await user_factory()
        await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
        token = _extract_token(capture_sender.messages[0].body)

        record = (await db_session.execute(select(PasswordResetToken))).scalars().one()
        record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await db_session.commit()

        resp = await client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "Reset-Pass-456"})
        assert resp.status_code == 401

    async def test_garbage_or_short_tokens_rejected(self, client: AsyncClient):
        garbage = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": uuid.uuid4().hex + uuid.uuid4().hex, "new_password": "Reset-Pass-456"},
        )
        assert garbage.status_code == 401

        too_short = await client.post(
            "/api/v1/auth/reset-password", json={"token": "abc", "new_password": "Reset-Pass-456"}
        )
        assert too_short.status_code == 422

    async def test_reset_with_weak_password_fails_without_consuming_token(
        self, client: AsyncClient, user_factory, capture_sender
    ):
        user = await user_factory()
        await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
        token = _extract_token(capture_sender.messages[0].body)

        weak = await client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "short"})
        assert weak.status_code == 422

        retry = await client.post(
            "/api/v1/auth/reset-password", json={"token": token, "new_password": "Reset-Pass-456"}
        )
        assert retry.status_code == 200

    async def test_disabled_account_gets_generic_response_and_no_email(
        self, client: AsyncClient, user_factory, capture_sender
    ):
        user = await user_factory(is_active=False)
        resp = await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
        assert resp.status_code == 200
        assert len(capture_sender.messages) == 0
