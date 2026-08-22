"""Rate limiting and brute-force lockout on authentication endpoints."""

import pytest
from httpx import AsyncClient

from app.models.enums import Role

pytestmark = pytest.mark.asyncio


def _make_client(app_factory, **limits):
    from httpx import ASGITransport

    app = app_factory(**limits)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestLoginRateLimits:
    async def test_ip_flood_returns_429(self, app_factory, user_factory):
        await user_factory(role=Role.WORKER)
        async with _make_client(app_factory, login_ip_limit=2, auth_window_seconds=3600) as c:
            for i in range(2):
                resp = await c.post(
                    "/api/v1/auth/login",
                    json={"email": f"user{i}@example.com", "password": "whatever-pass"},
                )
                assert resp.status_code in (200, 401)

            flooded = await c.post(
                "/api/v1/auth/login", json={"email": "another@example.com", "password": "whatever-pass"}
            )
            assert flooded.status_code == 429
            assert flooded.json()["error"]["code"] == "rate_limited"

    async def test_email_limit_hits_before_ip_limit_for_one_mailbox(self, app_factory, user_factory):
        user = await user_factory()
        async with _make_client(app_factory, login_email_limit=2, login_ip_limit=100, auth_window_seconds=3600) as c:
            r1 = await c.post("/api/v1/auth/login", json={"email": user.email, "password": "test-password-123"})
            r2 = await c.post("/api/v1/auth/login", json={"email": user.email, "password": "test-password-123"})
            assert r1.status_code == r2.status_code == 200

            r3 = await c.post("/api/v1/auth/login", json={"email": user.email, "password": "test-password-123"})
            assert r3.status_code == 429

    async def test_failure_lockout_blocks_even_correct_password(self, app_factory, user_factory):
        user = await user_factory()
        async with _make_client(app_factory, login_failure_email_limit=2, login_failure_window_seconds=3600) as c:
            for _ in range(2):
                bad = await c.post("/api/v1/auth/login", json={"email": user.email, "password": "wrong-password"})
                assert bad.status_code == 401

            correct = await c.post("/api/v1/auth/login", json={"email": user.email, "password": "test-password-123"})
            assert correct.status_code == 429


class TestResetRateLimits:
    async def test_reset_request_flood_returns_429(self, app_factory, user_factory):
        user = await user_factory()
        async with _make_client(app_factory, password_reset_request_limit=2, reset_window_seconds=3600) as c:
            r1 = await c.post("/api/v1/auth/forgot-password", json={"email": user.email})
            r2 = await c.post("/api/v1/auth/forgot-password", json={"email": user.email})
            assert r1.status_code == r2.status_code == 200

            r3 = await c.post("/api/v1/auth/forgot-password", json={"email": user.email})
            assert r3.status_code == 429

    async def test_reset_confirm_flood_returns_429(self, app_factory):
        async with _make_client(app_factory, password_reset_confirm_limit=2, reset_window_seconds=3600) as c:
            for i in range(3):
                resp = await c.post(
                    "/api/v1/auth/reset-password",
                    json={"token": f"not-a-real-token-value-{i}123456", "new_password": "Whatever-Pass-1"},
                )
                if i < 2:
                    assert resp.status_code == 401
                else:
                    assert resp.status_code == 429
