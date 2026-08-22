import pytest
from httpx import AsyncClient


class TestSecurityHeaders:
    @pytest.mark.asyncio
    async def test_security_headers_present(self, client: AsyncClient):
        response = await client.get("/health/live")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "0"
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "Permissions-Policy" in response.headers

    @pytest.mark.asyncio
    async def test_request_id_header(self, client: AsyncClient):
        response = await client.get("/health/live")
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) > 0

    @pytest.mark.asyncio
    async def test_custom_request_id_preserved(self, client: AsyncClient):
        custom_id = "test-request-id-12345"
        response = await client.get("/health/live", headers={"X-Request-ID": custom_id})
        assert response.headers["X-Request-ID"] == custom_id
