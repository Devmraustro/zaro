import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestSecurityHeadersHardening:
    async def test_csp_present_on_all_responses(self, client: AsyncClient):
        response = await client.get("/health/live")
        csp = response.headers.get("Content-Security-Policy")
        assert csp is not None
        assert "default-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp

    async def test_hsts_absent_in_development(self, client: AsyncClient):
        response = await client.get("/health/live")
        assert "Strict-Transport-Security" not in response.headers

    @pytest.mark.parametrize("environment", ["staging", "production"])
    async def test_hsts_present_in_staging_and_production(self, app_factory, environment: str):
        from httpx import ASGITransport, AsyncClient

        cfg_overrides = {"environment": environment}
        if environment == "production":
            cfg_overrides.update(
                secret_key="x" * 48,
                encryption_key="y" * 48,
                cors_origins=["https://app.example.com"],
            )
        app = app_factory(**cfg_overrides)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/health/live")
        hsts = response.headers.get("Strict-Transport-Security")
        assert hsts is not None
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts


class TestRequestIdSanitization:
    async def test_valid_client_request_id_is_preserved(self, client: AsyncClient):
        request_id = "abcDEF123_-456"
        response = await client.get("/health/live", headers={"X-Request-ID": request_id})
        assert response.headers["X-Request-ID"] == request_id

    @pytest.mark.parametrize(
        "malicious",
        [
            "short",
            "with spaces and-dashes-but-too-long-for-the-format-check-to-pass-alright",
            "injection\r\nX-Injected: true",
            "../../etc/passwd",
            "<script>alert(1)</script>",
            "control\x01\x02chars",
        ],
    )
    async def test_malformed_request_id_is_replaced_with_uuid(self, client: AsyncClient, malicious: str):
        response = await client.get("/health/live", headers={"X-Request-ID": malicious})
        echoed = response.headers["X-Request-ID"]
        assert echoed != malicious
        # A fresh UUID proves regeneration rather than partial sanitization.
        try:
            uuid.UUID(echoed)
        except ValueError as exc:
            raise AssertionError(f"expected regenerated UUID, got {echoed!r}") from exc

    async def test_missing_request_id_generates_uuid(self, client: AsyncClient):
        response = await client.get("/health/live")
        uuid.UUID(response.headers["X-Request-ID"])  # must not raise
