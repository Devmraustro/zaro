import pytest
from httpx import AsyncClient


class TestHealthEndpoints:
    @pytest.mark.asyncio
    async def test_liveness(self, client: AsyncClient):
        response = await client.get("/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_readiness(self, client: AsyncClient):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "services" in data
        assert data["version"] == "0.1.0"

    @pytest.mark.asyncio
    async def test_liveness_returns_no_sensitive_data(self, client: AsyncClient):
        response = await client.get("/health/live")
        body = response.text
        assert "password" not in body.lower()
        assert "secret" not in body.lower()
        assert "key" not in body.lower()

    @pytest.mark.asyncio
    async def test_nonexistent_route_returns_404(self, client: AsyncClient):
        response = await client.get("/api/v1/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
