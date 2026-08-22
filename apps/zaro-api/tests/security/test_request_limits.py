import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio


class TestBodySizeLimit:
    async def test_oversized_body_rejected_with_413(self, app_factory):
        app = app_factory(max_request_bytes=64)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/auth/login",
                json={"email": "user@example.com", "password": "p" * 200},
            )
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "payload_too_large"

    async def test_body_under_limit_passes_through(self, app_factory):
        app = app_factory(max_request_bytes=4096)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/auth/login",
                json={"email": "nobody@example.com", "password": "wrong-password-1"},
            )
        # Reaches the handler (401 for unknown credentials), not the size guard.
        assert response.status_code == 401

    async def test_invalid_content_length_header_rejected(self, app_factory):
        app = app_factory()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/auth/login",
                json={"email": "a@b.co", "password": "whatever-123"},
                headers={"Content-Length": "not-a-number"},
            )
        assert response.status_code == 400


class TestAllowedHosts:
    async def test_disallowed_host_rejected_with_421(self, app_factory):
        app = app_factory(allowed_hosts=["api.zaro.test"])
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/health/live", headers={"Host": "evil.example.com"})
        assert response.status_code == 421
        assert response.json()["error"]["code"] == "misdirected_request"

    async def test_allowed_host_accepted(self, app_factory):
        app = app_factory(allowed_hosts=["api.zaro.test"])
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/health/live", headers={"Host": "api.zaro.test"})
        assert response.status_code == 200

    async def test_allowed_host_with_port_accepted(self, app_factory):
        app = app_factory(allowed_hosts=["localhost:8001"])
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/health/live", headers={"Host": "localhost:8001"})
        assert response.status_code == 200

    async def test_empty_allowlist_disables_validation(self, client: AsyncClient):
        response = await client.get("/health/live", headers={"Host": "anything.goes"})
        assert response.status_code == 200


class TestGlobalRateLimit:
    async def test_global_ip_limit_trips_with_retry_after(self, app_factory):
        app = app_factory(rate_limit_requests=3, rate_limit_window_seconds=3600)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            statuses: list[int] = []
            for _ in range(5):
                response = await ac.get("/api/v1/auth/me")
                statuses.append(response.status_code)
            assert statuses[:3] == [401, 401, 401]
            assert statuses[3] == 429
            assert statuses[4] == 429
            limited = await ac.get("/api/v1/auth/me")
            assert limited.headers.get("Retry-After") == "3600"
            assert limited.json()["error"]["code"] == "rate_limited"

    async def test_health_endpoints_are_exempt(self, app_factory):
        app = app_factory(rate_limit_requests=2, rate_limit_window_seconds=3600)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(10):
                live = await ac.get("/health/live")
                assert live.status_code == 200

    async def test_options_preflight_is_exempt(self, app_factory):
        app = app_factory(rate_limit_requests=1, rate_limit_window_seconds=3600)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            first = await ac.get("/api/v1/auth/me")
            for _ in range(5):
                preflight = await ac.options(
                    "/api/v1/auth/login",
                    headers={"Origin": "http://localhost:3001", "Access-Control-Request-Method": "POST"},
                )
                assert preflight.status_code in (200, 400)
        assert first.status_code == 401

    async def test_rate_limiting_can_be_disabled(self, app_factory):
        app = app_factory(rate_limit_enabled=False, rate_limit_requests=1)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(5):
                response = await ac.get("/api/v1/auth/me")
                assert response.status_code == 401
